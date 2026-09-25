#!/usr/bin/env python3
"""各局面で「相手に詰めろがかかっているか」を手数順に出す（速度計算の検証用）。

  python3 scripts/tumero.py kifu/gNN.kif 44 60

手番を一方に渡した局面（sfenの手番だけ反転）に go mate を掛け、
詰みがあれば「その側が詰ませる＝相手は詰めろ」と読む。

制限：詰めエンジンは連続王手の詰みしか見ないので、
王手をかけずに詰ます順は検出できない。詰めろの検出漏れがありうる。
""" 
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shogi, shogi.KIF as KIF
from shogi_engine import Engine
path, lo, hi = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
mv=KIF.Parser.parse_file(path)[0]["moves"]
m=Engine(mate=True)
def flip(sfen):
    p=sfen.split(" "); p[1]="w" if p[1]=="b" else "b"; return " ".join(p)
print("各局面で『その側に手番を渡したら詰むか』= 相手に詰めろがかかっているか")
for n in range(lo,hi+1):
    b=shogi.Board()
    for x in mv[:n]: b.push_usi(x)
    out=[f"{n:3d}手目終了時"]
    for side,label in ((shogi.BLACK,"先手が詰ませる"),(shogi.WHITE,"後手が詰ませる")):
        s=b.sfen() if b.turn==side else flip(b.sfen())
        try:
            nb=shogi.Board(s)
            bad = nb.was_suicide() if hasattr(nb,"was_suicide") else False
        except Exception:
            out.append(f"{label}:判定不可"); continue
        r=m.mate_search([], movetime_ms=3000, sfen=s)
        out.append(f"{label}:{'%d手' % r[0] if r[0] else '-'}")
    print("  ".join(out), flush=True)
m.quit()
