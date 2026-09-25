#!/usr/bin/env python3
"""YaneuraOu(USI) の薄いラッパー。

重要な落とし穴（過去にハマった点）:
  - ハンドシェイクは usi / usinewgame（uci だと position の moves が反映されない）
  - go を送った直後に quit を送ると探索前にプロセスが死ぬ。必ず bestmove を待つ
  - サンドボックスは 1コアなので taskset で固定すると安定する
"""
import subprocess, threading, queue, time

ENGINE_PATH = "/home/claude/YaneuraOu/source/YaneuraOu-by-gcc"
ENGINE_CWD  = "/home/claude/YaneuraOu/source"

# 詰将棋専用ビルド (YANEURAOU_MATE_ENGINE)。
# 通常の NNUE ビルドは "go mate" を解釈せず通常探索にフォールバックするため、
# その出力の "score mate N" を拾うと連続王手でない強制勝ちまで詰みとして
# 記録してしまう（2026/09/03に判明。詰み逃し8件・遠回り10件が汚染されていた）。
# 専用エンジンは "checkmate <手順>" / "checkmate nomate" を返すので確実。
MATE_ENGINE_PATH = "/home/claude/mate_build/YaneuraOu-by-gcc"
MATE_ENGINE_CWD  = "/home/claude/mate_build"


class Engine:
    def __init__(self, threads=1, mate=False):
        """mate=True で詰将棋専用ビルドを起動する。

        詰将棋専用エンジンは評価関数を持たないので通常探索(analyze)には使えない。
        逆に通常ビルドは go mate を解釈しないので詰み判定には使えない。用途で分ける。
        """
        self.is_mate_engine = mate
        path = MATE_ENGINE_PATH if mate else ENGINE_PATH
        cwd = MATE_ENGINE_CWD if mate else ENGINE_CWD
        cmd = ["taskset", "-c", "0", path]
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, bufsize=1, cwd=cwd)
        self.q = queue.Queue()
        threading.Thread(target=self._read_loop, daemon=True).start()
        self._send("usi"); self._wait_for("usiok")
        self._send("setoption name USI_OwnBook value false")
        self._send(f"setoption name Threads value {threads}")
        self._send("isready"); self._wait_for("readyok")
        self._send("usinewgame")   # ゲーム開始は1回だけ。以後は毎回呼ばない(ハッシュクリアが重いため)

    def _read_loop(self):
        for line in self.proc.stdout:
            self.q.put(line.rstrip("\n"))

    def _send(self, cmd):
        self.proc.stdin.write(cmd + "\n"); self.proc.stdin.flush()

    def _wait_for(self, token, timeout=30):
        start, lines = time.time(), []
        while time.time() - start < timeout:
            try:
                line = self.q.get(timeout=0.2)
                lines.append(line)
                if token in line:
                    return lines
            except queue.Empty:
                continue
        return lines

    def _wait_bestmove(self, timeout=30):
        """bestmove を待つ。時間内に来なければ stop を送って必ず回収する。

        過去の不具合（g28, 9/22）: 深い局面で depth 指定の探索が30秒を超えると
        bestmove を待たずに次の局面へ進み、以後の出力が1局面ずつズレていた。
        analyze.py の88手目以降の評価値が符号ごと崩れたのはこれが原因。
        """
        lines = self._wait_for("bestmove", timeout=timeout)
        if not any(l.startswith("bestmove") for l in lines):
            self._send("stop")
            lines += self._wait_for("bestmove", timeout=30)
        return lines

    @staticmethod
    def _parse(lines):
        score = bestmove = None
        pv = []
        for line in lines:
            if line.startswith("info") and " score " in line:
                p = line.split()
                if "cp" in p:
                    score = ("cp", int(p[p.index("cp") + 1]))
                elif "mate" in p:
                    score = ("mate", int(p[p.index("mate") + 1]))
                if "pv" in p:
                    pv = p[p.index("pv") + 1:]
            if line.startswith("bestmove"):
                bestmove = line.split()[1]
        return score, bestmove, pv

    @staticmethod
    def _parse_multipv(lines):
        """MultiPV探索の出力を順位つきで返す。

        -> [(rank, move, score), ...]  rank は1始まり、scoreは ("cp"|"mate", 値)
        同じ multipv 番号は深さが進むたびに上書きされるので、
        最後に残るのが最深の結果になる。
        """
        best = {}
        for line in lines:
            if not line.startswith("info") or " score " not in line or " pv " not in line:
                continue
            p = line.split()
            if "multipv" not in p:
                continue
            k = int(p[p.index("multipv") + 1])
            if "cp" in p:
                sc = ("cp", int(p[p.index("cp") + 1]))
            elif "mate" in p:
                sc = ("mate", int(p[p.index("mate") + 1]))
            else:
                continue
            mv = p[p.index("pv") + 1]
            best[k] = (mv, sc)
        return [(k, best[k][0], best[k][1]) for k in sorted(best)]

    def analyze_multipv(self, sfen=None, moves_usi=None, depth=16, multipv=8):
        """候補手を上位 multipv 件まで順位つきで返す。

        -> [(順位, 手, 評価値), ...]  評価値は「その局面の手番側の視点」
        指した手が上位に入っていなければリストに現れない（= multipv位より下）。
        """
        self._send(f"setoption name MultiPV value {multipv}")
        cmd = f"position sfen {sfen}" if sfen else "position startpos"
        if moves_usi:
            cmd += " moves " + " ".join(moves_usi)
        self._send(cmd); self._send(f"go depth {depth}")
        out = self._parse_multipv(self._wait_for("bestmove", timeout=300))
        self._send("setoption name MultiPV value 1")
        return out

    def rank_of(self, actual_usi, sfen=None, moves_usi=None, depth=16, multipv=8):
        """実際に指した手がエンジンの何番目の候補だったかを返す。

        -> (順位 or None, 候補リスト)  None は multipv 位内に入らなかったことを表す
        """
        cands = self.analyze_multipv(sfen=sfen, moves_usi=moves_usi,
                                     depth=depth, multipv=multipv)
        for rank, mv, _sc in cands:
            if mv == actual_usi:
                return rank, cands
        return None, cands

    def analyze(self, moves_usi, depth=14):
        """startpos から moves_usi を適用した局面を解析。 -> (score, bestmove)"""
        cmd = "position startpos"
        if moves_usi:
            cmd += " moves " + " ".join(moves_usi)
        self._send(cmd); self._send(f"go depth {depth}")
        s, b, _ = self._parse(self._wait_bestmove())
        return s, b

    def analyze_from_sfen(self, sfen, extra_moves=None, depth=14):
        """任意のsfenから解析。 -> (score, bestmove, pv)"""
        cmd = f"position sfen {sfen}"
        if extra_moves:
            cmd += " moves " + " ".join(extra_moves)
        self._send(cmd); self._send(f"go depth {depth}")
        return self._parse(self._wait_bestmove())

    def mate_search(self, moves_usi, movetime_ms=4000, sfen=None):
        """連続王手の詰みを厳密に判定する。詰将棋専用エンジンでのみ有効。

        -> (mate_plies, first_move)  詰みなしなら (None, None)
        mate_plies は詰将棋の「N手詰め」のNと同じ数え方（半手数）。

        専用エンジンは USI の正式応答を返す:
          checkmate <手順...>  … 詰みあり。手数は手順の長さ
          checkmate nomate     … 詰みなし
          checkmate timeout    … 時間内に判定できず（詰みなしと区別すること）
        通常ビルドで呼ぶと go mate を解釈せず通常探索の結果を拾ってしまい、
        連続王手でない強制勝ちまで詰みとして扱ってしまうため、明示的に弾く。
        """
        if not getattr(self, "is_mate_engine", False):
            raise RuntimeError(
                "mate_search は詰将棋専用エンジンでのみ使用可能です。"
                "Engine(mate=True) で起動してください。")

        if sfen:
            cmd = f"position sfen {sfen}"
        else:
            cmd = "position startpos"
        if moves_usi:
            cmd += " moves " + " ".join(moves_usi)
        # 前回の探索の遅れた応答が残っていると、以後の結果が1回ずつズレる
        # （9/22に発覚。mate_rate.py の初回実行で g16 の85手目の3手詰が87手目に出た）。
        # 送る前に残りを捨て、時間切れ時は stop を送って応答を回収してから返す。
        while True:
            try:
                self.q.get_nowait()
            except queue.Empty:
                break
        self._send(cmd)
        self._send(f"go mate {movetime_ms}")

        deadline = time.time() + movetime_ms / 1000 + 5
        while time.time() < deadline:
            try:
                line = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            if not line.startswith("checkmate"):
                continue
            parts = line.split()
            if len(parts) < 2 or parts[1] in ("nomate", "timeout", "notimplemented"):
                return None, None
            seq = parts[1:]
            return len(seq), seq[0]
        self._send("stop")
        end = time.time() + 10
        while time.time() < end:
            try:
                if self.q.get(timeout=0.2).startswith("checkmate"):
                    break
            except queue.Empty:
                continue
        return None, None

    def quit(self):
        try:
            self._send("quit"); self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


if __name__ == "__main__":
    e = Engine()
    print("smoke test:", e.analyze(["7g7f", "3c3d"], depth=12))
    e.quit()
