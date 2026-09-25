#!/usr/bin/env python3
"""同一局面から複数の候補手を比較する（変化の検証用）。

  python3 compare.py "<sfen>" 16 "P*4d" "P*2d" "7g6e"
評価値は「その手を指した後の手番側視点」で返るので、
指した本人の視点にするには符号を反転して読むこと。
"""
import sys
from shogi_engine import Engine

sfen, depth, cands = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
for mv in cands:
    e = Engine()          # 1手ごとに起動し直すと落ちにくい
    s, b, pv = e.analyze_from_sfen(sfen, [mv], depth=depth)
    e.quit()
    print(f"--- {mv} ---")
    print(f"  eval(手番側視点)={s}   相手の応手={b}")
    print(f"  pv: {' '.join(pv[:10])}\n")
