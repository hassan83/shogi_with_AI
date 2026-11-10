#!/usr/bin/env python3
"""悪手疑いの手を深く調べる（recheck.py と move_rank.py を1回の探索にまとめたもの）。

  python3 scripts/deep_check.py kifu/gNN.kif 20 "39,45,49" [候補数]

各手数について、その手を指す前の局面を MultiPV（既定8）で1回だけ探索し、次を出す：
  - 推奨手（1位）と、実際に指した手の順位（候補数位に入らなければ「圏外」）
  - 差分（実際の手の評価値 − 推奨手の評価値）。同じ探索の中の値どうしで比べる
  - 上位候補の一覧（順位・手・評価値）
実際の手が圏外のときだけ、その手に絞って（searchmoves）同じ深さでもう1回探索し、評価値を出す。

recheck.py・move_rank.py より速い理由：
  - 局面ごとの探索が1回（圏外のときだけ2回）で済む（recheck.py は3回、move_rank.py は1回）
  - エンジンを起動したまま使い回す（落ちたときだけ起動し直す）
  - 使えるCPUコアをすべて使う（Threads）
評価値は「その局面の手番側＝指す側の視点」。
"""
import sys
import shogi
import shogi.KIF as KIF
from shogi_engine import Engine, available_cores
from ja_notation import move_to_japanese


def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0]
    return KIF.Parser.parse_file(path)[0]["moves"]


def to_cp(sc):
    if sc is None:
        return None
    kind, val = sc
    if kind == "cp":
        return val
    return 100000 if val > 0 else -100000


def fmt(sc):
    return str(sc[1]) if sc[0] == "cp" else f"詰{sc[1]}"


class Prober:
    """エンジンを使い回す。落ちたら（BrokenPipe など）起動し直して1回だけやり直す。"""

    def __init__(self, threads):
        self.threads = threads
        self.e = None

    def multipv(self, **kw):
        for attempt in range(2):
            try:
                if self.e is None:
                    self.e = Engine(threads=self.threads)
                return self.e.analyze_multipv(**kw)
            except Exception:
                self.close()
                if attempt == 1:
                    return []
        return []

    def close(self):
        if self.e is not None:
            try:
                self.e.quit()
            except Exception:
                pass
            self.e = None


def main():
    path, depth, targets = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    topn = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    moves = load(path)
    pr = Prober(threads=available_cores())

    for t in [int(x) for x in targets.split(",")]:
        b = shogi.Board()
        for mv in moves[:t - 1]:
            b.push_usi(mv)
        sfen = b.sfen()
        actual = moves[t - 1]

        cands = pr.multipv(sfen=sfen, depth=depth, multipv=topn)
        rank = next((r for r, mv, _ in cands if mv == actual), None)
        best = cands[0] if cands else None
        if rank:
            sc_actual = cands[rank - 1][2]
        else:
            only = pr.multipv(sfen=sfen, depth=depth, multipv=1, searchmoves=[actual])
            sc_actual = only[0][2] if only else None

        ja = move_to_japanese(b, actual)
        pos = f"{rank}位" if rank else f"圏外（{topn}位以下）"
        print(f"=== {t}手目  実際: {ja}  → {pos} ===")
        if best and sc_actual is not None:
            diff = to_cp(sc_actual) - to_cp(best[2])
            print(f"  推奨  : {move_to_japanese(b, best[1])}  eval={fmt(best[2])}")
            print(f"  実際  : {ja}  eval={fmt(sc_actual)}")
            print(f"  差分（実際-推奨）= {diff}")
        else:
            print("  ✗ 探索に失敗しました")
        for r, mv, sc in cands:
            mark = " ←実際の手" if mv == actual else ""
            print(f"  {r}. {move_to_japanese(b, mv):14s} {fmt(sc):>7}{mark}")
        print(f"  sfen  : {sfen}\n", flush=True)

    pr.close()


if __name__ == "__main__":
    main()
