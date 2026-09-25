#!/usr/bin/env python3
"""指定手数でのエンジン推奨手と実際の手を比較。

  python3 best_moves.py game.kif 14 "37,51,63"
  python3 best_moves.py game.html 14 "37,51,63"
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
    path, depth, targets = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    moves = load(path)
    eng = Engine()
    for t in [int(x) for x in targets.split(",")]:
        hist = moves[:t - 1]
        b = shogi.Board()
        for mv in hist:
            b.push_usi(mv)
        score, best = eng.analyze(hist, depth=depth)
        print(f"=== {t}手目 ===")
        print(f"  実際  : {move_to_japanese(b, moves[t-1])}")
        print(f"  推奨  : {move_to_japanese(b, best) if best else '?'}   (指す前の評価値 {score})")
        print(f"  sfen  : {b.sfen()}\n")
    eng.quit()


if __name__ == "__main__":
    main()
