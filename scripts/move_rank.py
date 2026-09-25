#!/usr/bin/env python3
"""指した手がエンジンの何番目の候補だったかを出す（MultiPV）。

  python3 scripts/move_rank.py kifu/gNN.kif 16 "39,41,47" [候補数]

出力は各手数について：
  - 実際に指した手とその順位（候補数位に入らなければ「圏外」）
  - 上位候補の一覧（順位・手・評価値）

評価値は「その局面の手番側＝指す側の視点」。順位1位が推奨手。

用途：
  差分の大きさだけでは「第2候補を選んだ」のか「論外の手だった」のかが分からない。
  順位を併記すると、精度の問題（2-3位）と候補生成の問題（圏外）を区別できる。
"""
import sys, shogi
from shogi_engine import Engine
from ja_notation import move_to_japanese


def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0]
    import shogi.KIF as KIF
    return KIF.Parser.parse_file(path)[0]["moves"]


def main():
    path = sys.argv[1]
    depth = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    targets = [int(x) for x in sys.argv[3].split(",")] if len(sys.argv) > 3 else []
    topn = int(sys.argv[4]) if len(sys.argv) > 4 else 8

    moves = load(path)
    for t in targets:
        b = shogi.Board()
        for mv in moves[:t - 1]:
            b.push_usi(mv)
        sfen = b.sfen()
        actual = moves[t - 1]
        e = Engine()                      # 1手ごとに起動し直すと落ちにくい
        rank, cands = e.rank_of(actual, sfen=sfen, depth=depth, multipv=topn)
        e.quit()

        ja = move_to_japanese(b, actual)
        pos = f"{rank}位" if rank else f"圏外（{topn}位以下）"
        print(f"=== {t}手目  実際: {ja}  → {pos} ===")
        for r, mv, sc in cands:
            mark = " ←実際の手" if mv == actual else ""
            val = sc[1] if sc[0] == "cp" else f"詰{sc[1]}"
            print(f"  {r}. {move_to_japanese(b, mv):14s} {val:>7}{mark}")
        print()


if __name__ == "__main__":
    main()
