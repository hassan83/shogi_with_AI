#!/usr/bin/env python3
"""相手が悪手を指した直後に、自分の悪手率が上がるかを検証する。

`docs/打ち手見落とし.csv`（drop_blind.py の出力）だけで計算できる。
本人の手しか記録されていないが、相手の手の差分は次の式で復元できる：

  s[i]   = eval_before（本人の手を指す前の評価値）
  s[i+1] = -(diff[i] + s[i])       ← 本人が指した後の局面（相手番視点）
  相手の差分 = -s[i+2] - s[i+1]

  python3 scripts/punish_rate.py [threshold]
"""
import csv, os, sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def band(p):
    return "1-40手" if p <= 40 else ("41-80手" if p <= 80 else "81手以上")


def main():
    thr = int(sys.argv[1]) if len(sys.argv) > 1 else -300
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "打ち手見落とし.csv"),
                                    encoding="utf-8")))
    g = defaultdict(list)
    for r in rows:
        r["ply"] = int(r["ply"]); r["diff"] = int(r["diff"])
        r["eval_before"] = int(r["eval_before"])
        g[r["file"]].append(r)

    data = []
    for f, v in g.items():
        v.sort(key=lambda x: x["ply"])
        for a, b in zip(v, v[1:]):
            if b["ply"] != a["ply"] + 2:
                continue
            s1 = -(a["diff"] + a["eval_before"])          # 本人の手の直後
            opp = -b["eval_before"] - s1                  # 相手の手の差分
            if abs(opp) >= 50000:
                continue
            data.append((f, b["ply"], opp, b["diff"] <= thr))

    print(f"{'層':<10}{'相手が悪手の直後':>20}{'それ以外':>22}{'差':>10}")
    for k in ["1-40手", "41-80手", "81手以上", "全体"]:
        sub = [d for d in data if k == "全体" or band(d[1]) == k]
        a = [d for d in sub if d[2] <= thr]
        b = [d for d in sub if d[2] > thr]
        ra = 100 * sum(1 for d in a if d[3]) / len(a) if a else 0
        rb = 100 * sum(1 for d in b if d[3]) / len(b) if b else 0
        print(f"{k:<10} {len(a):>5}手 {ra:>6.1f}%  "
              f"{len(b):>7}手 {rb:>6.1f}%  {ra-rb:>+8.1f}pt")

    print("\n注意：相手が悪手を指した直後は「咎める手が存在する」局面なので、")
    print("      外せば差分が出る。静かな局面では失うものが無い。")
    print("      この機会の非対称性が差の一部を作っている（交絡）。")


if __name__ == "__main__":
    main()
