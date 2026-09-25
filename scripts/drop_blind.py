#!/usr/bin/env python3
"""仮説検証：「深く読んだ局面になかった駒」が絡む筋を見逃しやすいか。

各局の全局面を1回ずつ解析し、局面ごとに (評価値, エンジン推奨手) を取る。
本人の手について 差分 = -score(次局面) - score(現局面) を出し、
悪手候補（差分 <= 閾値）とそれ以外で「推奨手が打（持ち駒）である割合」を比べる。

  python3 scripts/drop_blind.py [depth] [threshold]

出力: docs/打ち手見落とし.csv と集計のサマリ
"""
import csv, os, sys, shogi
import shogi.KIF as KIF
from shogi_engine import Engine

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def to_cp(score):
    if score is None:
        return 0
    kind, val = score
    if kind == "cp":
        return val
    return 100000 if val > 0 else -100000


def load_moves(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0]
    return KIF.Parser.parse_file(path)[0]["moves"]


def kif_path(name):
    p = os.path.join(ROOT, "kifu", name)
    return p if os.path.exists(p) else os.path.join(ROOT, "kifu", "com", name)


def is_drop(usi):
    return usi is not None and "*" in usi


def scan(name, my_side, depth):
    """-> list of per-move records for 本人の手"""
    moves = load_moves(kif_path(name))
    my_parity = 0 if my_side == "先手" else 1
    eng = Engine()
    scores, bests = [], []
    board = shogi.Board()
    for i in range(len(moves) + 1):
        s, b = eng.analyze(moves[:i], depth=depth)
        scores.append(to_cp(s))
        bests.append(b)
    eng.quit()

    recs = []
    for i, mv in enumerate(moves):
        if i % 2 != my_parity:
            continue
        if i + 1 >= len(scores):
            break
        diff = -scores[i + 1] - scores[i]
        if abs(diff) >= 50000:      # 詰みフラグの切り替わりは除外
            continue
        recs.append(dict(
            file=name, ply=i + 1,
            actual=mv, recommended=bests[i], diff=diff,
            actual_is_drop=int(is_drop(mv)),
            rec_is_drop=int(is_drop(bests[i])),
            prev_opp_is_drop=int(is_drop(moves[i - 1])) if i > 0 else "",
            eval_before=scores[i],
        ))
    return recs


def main():
    depth = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    thr = int(sys.argv[2]) if len(sys.argv) > 2 else -300

    idx = list(csv.DictReader(open(os.path.join(ROOT, "docs", "対局指標.csv"),
                                   encoding="utf-8-sig")))
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    cache = os.path.join(ROOT, ".scan_cache")
    os.makedirs(cache, exist_ok=True)

    out = []
    for row in idx:
        name = row["file"]
        cf = os.path.join(cache, name + ".csv")
        if os.path.exists(cf):                       # 済みは読み直すだけ
            r = list(csv.DictReader(open(cf, encoding="utf-8")))
            for x in r:
                for k in ("ply", "diff", "actual_is_drop", "rec_is_drop", "eval_before"):
                    x[k] = int(x[k])
                x["prev_opp_is_drop"] = int(x["prev_opp_is_drop"]) if x["prev_opp_is_drop"] != "" else ""
            out += r
            continue
        if only is not None and name not in only:
            continue
        try:
            r = scan(name, row["my_side"], depth)
        except Exception as e:
            print(f"!! {name}: {e}", flush=True)
            continue
        with open(cf, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(r[0].keys()))
            w.writeheader(); w.writerows(r)
        out += r
        bad = [x for x in r if x["diff"] <= thr]
        print(f"{name}: 本人の手 {len(r)}  悪手候補 {len(bad)}"
              f"  うち推奨が打 {sum(x['rec_is_drop'] for x in bad)}", flush=True)

    if not out:
        print("集計対象なし"); return
    path = os.path.join(ROOT, "docs", "打ち手見落とし.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)

    bad = [x for x in out if x["diff"] <= thr]
    ok = [x for x in out if x["diff"] > thr]

    def rate(rows, key):
        return 100 * sum(r[key] for r in rows) / len(rows) if rows else 0

    print("\n=== 集計 ===")
    print(f"本人の手 総数 {len(out)} / 悪手候補 {len(bad)}（閾値 {thr}）")
    print(f"推奨手が打である割合   悪手候補 {rate(bad,'rec_is_drop'):.1f}%"
          f" / それ以外 {rate(ok,'rec_is_drop'):.1f}%")
    print(f"実際に打を指した割合   悪手候補 {rate(bad,'actual_is_drop'):.1f}%"
          f" / それ以外 {rate(ok,'actual_is_drop'):.1f}%")

    pv = [x for x in out if x["prev_opp_is_drop"] != ""]
    after_drop = [x for x in pv if x["prev_opp_is_drop"] == 1]
    after_move = [x for x in pv if x["prev_opp_is_drop"] == 0]
    def badrate(rows):
        return 100 * len([r for r in rows if r["diff"] <= thr]) / len(rows) if rows else 0
    print(f"直前の相手の手が打 {len(after_drop)}手 → 悪手率 {badrate(after_drop):.1f}%")
    print(f"           それ以外 {len(after_move)}手 → 悪手率 {badrate(after_move):.1f}%")
    print(f"\n書き出し: {path}")


if __name__ == "__main__":
    main()
