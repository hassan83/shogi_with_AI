#!/usr/bin/env python3
"""悪手疑いの手を深く調べる（recheck.py と move_rank.py をまとめて速くしたもの）。

  python3 scripts/deep_check.py kifu/gNN.kif 20 "39,45,49" [候補数=8] [順位の深さ=16]

各手数について、その手を指す前の局面で次を出す：
  - 差分：推奨手と実際の手の評価値の差（深さ20など、指定した深さ）
      1. 普通に探索して推奨手とその評価値を出す
      2. 実際の手が推奨手と違えば、その手だけに絞って（searchmoves）同じ深さで探索する
      同じ局面・同じ深さの探索どうしで比べる
  - 順位：実際に指した手がエンジンの何番目の候補か（MultiPV。既定は深さ16で上位8手）
      候補数位に入らなければ「圏外」

速くするための工夫：
  - 上位8手（MultiPV）の探索は重く、深さ20では1局面に5分以上かかることがある。
    差分は上位1手の探索で出し、順位だけを浅い深さの MultiPV で出す
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
    rank_depth = int(sys.argv[5]) if len(sys.argv) > 5 else min(16, depth)
    moves = load(path)
    pr = Prober(threads=available_cores())

    for t in [int(x) for x in targets.split(",")]:
        b = shogi.Board()
        for mv in moves[:t - 1]:
            b.push_usi(mv)
        sfen = b.sfen()
        actual = moves[t - 1]
        ja = move_to_japanese(b, actual)

        top = pr.multipv(sfen=sfen, depth=depth, multipv=1)
        best = top[0] if top else None
        if best and best[1] == actual:
            sc_actual = best[2]
        else:
            only = pr.multipv(sfen=sfen, depth=depth, multipv=1, searchmoves=[actual])
            sc_actual = only[0][2] if only else None

        cands = pr.multipv(sfen=sfen, depth=rank_depth, multipv=topn)
        rank = next((r for r, mv, _ in cands if mv == actual), None)
        pos = f"{rank}位" if rank else f"圏外（{topn}位以下）"

        print(f"=== {t}手目  実際: {ja}  → 順位 {pos}（深さ{rank_depth}） ===")
        if best and sc_actual is not None:
            diff = to_cp(sc_actual) - to_cp(best[2])
            print(f"  推奨  : {move_to_japanese(b, best[1])}  eval={fmt(best[2])}（深さ{depth}）")
            print(f"  実際  : {ja}  eval={fmt(sc_actual)}（深さ{depth}）")
            print(f"  差分（実際-推奨）= {diff}")
        else:
            print("  ✗ 探索に失敗しました")
        print(f"  候補（深さ{rank_depth}）:")
        for r, mv, sc in cands:
            mark = " ←実際の手" if mv == actual else ""
            print(f"  {r}. {move_to_japanese(b, mv):14s} {fmt(sc):>7}{mark}")
        print(f"  sfen  : {sfen}\n", flush=True)

    pr.close()


if __name__ == "__main__":
    main()
