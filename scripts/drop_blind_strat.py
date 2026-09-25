#!/usr/bin/env python3
"""drop_blind.py の出力を層別集計する。

交絡の切り分け：
  「推奨手が打である確率」は持ち駒が増えるほど自然に上がる。
  中終盤ほど悪手も増える。したがって素の比較には
  「持ち駒枚数」「手数帯」の交絡が乗っている。
  同一層の内部で悪手候補とそれ以外を比べ、差が残るかを見る。

  python3 scripts/drop_blind_strat.py [threshold]
"""
import csv, os, sys, shogi
import shogi.KIF as KIF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def load_moves(name):
    p = os.path.join(ROOT, "kifu", name)
    if not os.path.exists(p):
        p = os.path.join(ROOT, "kifu", "com", name)
    if p.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(p, encoding="utf-8", errors="replace").read())[0]
    return KIF.Parser.parse_file(p)[0]["moves"]


def hand_counts(name):
    """各ply(1始まり)を指す直前の、指す側の持ち駒枚数"""
    moves = load_moves(name)
    b = shogi.Board()
    out = {}
    for i, mv in enumerate(moves, 1):
        out[i] = sum(b.pieces_in_hand[b.turn].values())
        b.push_usi(mv)
    return out


def band_hand(n):
    if n == 0:
        return "0枚"
    if n <= 2:
        return "1-2枚"
    if n <= 4:
        return "3-4枚"
    return "5枚以上"


def band_ply(p):
    if p <= 40:
        return "1-40手"
    if p <= 80:
        return "41-80手"
    return "81手以上"


def main():
    thr = int(sys.argv[1]) if len(sys.argv) > 1 else -300
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "打ち手見落とし.csv"),
                                    encoding="utf-8")))
    cache = {}
    for r in rows:
        r["ply"] = int(r["ply"]); r["diff"] = int(r["diff"])
        r["rec_is_drop"] = int(r["rec_is_drop"])
        r["actual_is_drop"] = int(r["actual_is_drop"])
        r["prev_opp_is_drop"] = int(r["prev_opp_is_drop"]) if r["prev_opp_is_drop"] != "" else None
        if r["file"] not in cache:
            cache[r["file"]] = hand_counts(r["file"])
        r["hand"] = cache[r["file"]][r["ply"]]
        r["bad"] = r["diff"] <= thr

    def tab(keyfn, title):
        print(f"\n=== {title} ===")
        print(f"{'層':<10} {'悪手n':>6} {'推奨が打':>8} {'非悪手n':>8} {'推奨が打':>8} {'差':>7}")
        keys = sorted({keyfn(r) for r in rows})
        for k in keys:
            sub = [r for r in rows if keyfn(r) == k]
            bad = [r for r in sub if r["bad"]]
            ok = [r for r in sub if not r["bad"]]
            rb = 100 * sum(r["rec_is_drop"] for r in bad) / len(bad) if bad else float("nan")
            ro = 100 * sum(r["rec_is_drop"] for r in ok) / len(ok) if ok else float("nan")
            print(f"{k:<10} {len(bad):>6} {rb:>7.1f}% {len(ok):>8} {ro:>7.1f}% {rb-ro:>+6.1f}pt")

    tab(lambda r: band_hand(r["hand"]), "持ち駒枚数で層別：推奨手が打である割合")
    tab(lambda r: band_ply(r["ply"]), "手数帯で層別：推奨手が打である割合")

    print("\n=== 相手が打った直後か（持ち駒枚数で層別）：悪手率 ===")
    print(f"{'層':<10} {'打直後n':>8} {'悪手率':>8} {'それ以外n':>10} {'悪手率':>8} {'差':>7}")
    for k in ["0枚", "1-2枚", "3-4枚", "5枚以上"]:
        sub = [r for r in rows if band_hand(r["hand"]) == k and r["prev_opp_is_drop"] is not None]
        a = [r for r in sub if r["prev_opp_is_drop"] == 1]
        b = [r for r in sub if r["prev_opp_is_drop"] == 0]
        if not a or not b:
            continue
        ra = 100 * len([r for r in a if r["bad"]]) / len(a)
        rb = 100 * len([r for r in b if r["bad"]]) / len(b)
        print(f"{k:<10} {len(a):>8} {ra:>7.1f}% {len(b):>10} {rb:>7.1f}% {ra-rb:>+6.1f}pt")

    print("\n=== 推奨が打だった悪手の駒種別 ===")
    from collections import Counter
    c = Counter(r["recommended"].split("*")[0] for r in rows if r["bad"] and r["rec_is_drop"])
    ja = {"P": "歩", "L": "香", "N": "桂", "S": "銀", "G": "金", "B": "角", "R": "飛"}
    for k, v in c.most_common():
        print(f"  {ja.get(k, k)}打 : {v}")


if __name__ == "__main__":
    main()
