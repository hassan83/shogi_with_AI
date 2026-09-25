#!/usr/bin/env python3
"""棋譜を一手ずつ解析して評価値の落差を出す。

  python3 analyze.py game.kif [depth] [--side 先手|後手]
  python3 analyze.py game.html [depth]     # 将皇掲示板のHTML
  python3 analyze.py --usi "7g7f 3c3d ..." [depth]

方針メモ:
  - 差分は「その手を指した側の視点」で算出する
  - マイナス差分のみを悪手候補とする（プラスは探索ノイズ）
  - 深さ16は一次スクリーニング。疑わしい局面は深さ20で測り直すこと
"""
import sys, shogi, shogi.KIF as KIF
from shogi_engine import Engine
from ja_notation import move_to_japanese


def to_cp(score):
    if score is None:
        return 0
    kind, val = score
    if kind == "cp":
        return val
    return 100000 if val > 0 else -100000


def load(path_or_usi):
    if path_or_usi[0] == "--usi":
        return path_or_usi[1].split(), ("先手", "後手")
    path = path_or_usi[0]
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        moves, _b, names = from_html(open(path, encoding="utf-8", errors="replace").read())
        return moves, names
    g = KIF.Parser.parse_file(path)[0]
    return g["moves"], g["names"]


def main():
    args = sys.argv[1:]
    if args[0] == "--usi":
        moves, names = load(args[:2]); depth = int(args[2]) if len(args) > 2 else 16
    else:
        moves, names = load(args); depth = int(args[1]) if len(args) > 1 else 16

    print(f"先手: {names[0]} / 後手: {names[1]}   手数: {len(moves)}\n")
    eng = Engine()
    board = shogi.Board()
    prev = to_cp(eng.analyze([], depth=depth)[0])
    hist, recs = [], []

    for i, mv in enumerate(moves, 1):
        side = "先手" if i % 2 else "後手"
        ja = move_to_japanese(board, mv)
        board.push_usi(mv); hist.append(mv)
        opp = to_cp(eng.analyze(hist, depth=depth)[0])
        cur = -opp
        diff = cur - prev
        flag = "  ← 悪手疑い" if diff <= -300 else ("  ← やや悪化" if diff <= -150 else "")
        recs.append((i, side, ja, cur, diff))
        print(f"{i:3d} {side} {ja:14s} eval={cur:+6d}  差分={diff:+6d}{flag}")
        prev = opp
    eng.quit()

    print("\n=== 差分 -300 以下（深さ20で要再確認）===")
    for i, side, ja, cur, diff in recs:
        if diff <= -300:
            print(f"{i:3d}手目 {side} {ja}  差分={diff:+d}  eval={cur:+d}")


if __name__ == "__main__":
    main()
