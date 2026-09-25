#!/usr/bin/env python3
"""短い詰みの「機会」と「詰ませた率」を数える（詰み逃しの分母）。

  python3 scripts/mate_rate.py                # docs/対局指標.csv の全対局
  python3 scripts/mate_rate.py kifu/g28.kif   # 指定した棋譜だけ

metrics.py の詰み逃しは「通常探索が mate を出した局面」だけを候補にし、
逃した件数しか記録しない。ここでは自分の手番の全局面に go mate を掛け、
MAX_LEN 手以内の連続王手の詰みがあった局面をすべて「機会」として数える。

判定（metrics.py と同じ基準）:
  - 指した手の後も連続王手の詰みが続いていれば「継続」
    （王手でない手、または受けのどれかで詰みが切れたら「逃し」）
  - 継続した手順が詰みで終われば、その一連を1回の「詰ませた」とする
エピソード単位:
  詰みが現れてから、詰ませる／逃すまでの一連を1回と数える。
  逃したあとに再び詰みが現れたら別の1回。

出力: docs/詰み機会.csv（1行＝1エピソード）と標準出力の集計
"""
import csv, os, sys
import shogi
sys.path.insert(0, os.path.dirname(__file__))
from shogi_engine import Engine
from ja_notation import move_to_japanese

MAX_LEN = 9
MS = 2000
ROOT = os.path.join(os.path.dirname(__file__), "..")


def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        moves, _b, names = from_html(open(path, encoding="utf-8", errors="replace").read())
        return moves, names
    import shogi.KIF as KIF
    g = KIF.Parser.parse_file(path)[0]
    return g["moves"], g["names"]


def find_path(fname):
    for d in ("kifu", "kifu/com"):
        p = os.path.join(ROOT, d, fname)
        if os.path.exists(p):
            return p
    return None


def kept_mate(me, hist, board):
    """指した直後の board（相手番）で連続王手の詰みが続いているか。"""
    if board.is_checkmate():
        return True
    if not board.is_check():
        return False
    for reply in board.legal_moves:
        nb = shogi.Board(board.sfen()); nb.push(reply)
        if nb.is_checkmate():
            continue
        n, _ = me.mate_search(hist + [reply.usi()], movetime_ms=MS)
        if n is None:
            return False
    return True


def scan(path, my_side_label):
    moves, _names = load(path)
    my_black = (my_side_label == "先手")
    me = Engine(mate=True)
    board, hist = shogi.Board(), []
    episodes, cur = [], None
    for i, mv in enumerate(moves, 1):
        mine = (i % 2 == 1) == my_black
        if mine:
            if cur is None:
                n, best = me.mate_search(hist, movetime_ms=MS)
                if n is not None and n <= MAX_LEN:
                    cur = {"start": i, "len": n,
                           "best": move_to_japanese(board, best) if best else "?"}
            if cur is not None:
                ja = move_to_japanese(board, mv)
                nb = shogi.Board(board.sfen()); nb.push_usi(mv)
                if not kept_mate(me, hist + [mv], nb):
                    cur.update(result="逃し", at=i, actual=ja)
                    episodes.append(cur); cur = None
                elif nb.is_checkmate():
                    cur.update(result="詰ませた", at=i, actual=ja)
                    episodes.append(cur); cur = None
        board.push_usi(mv); hist.append(mv)
    if cur is not None:     # 詰み手順の途中で棋譜が終わった（相手投了など）
        cur.update(result="詰ませた(投了)", at=len(moves), actual="")
        episodes.append(cur)
    me.quit()
    return episodes


def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "docs", "対局指標.csv"), encoding="utf-8")))
    if len(sys.argv) > 1:
        want = {os.path.basename(a) for a in sys.argv[1:]}
        rows = [r for r in rows if r["file"] in want]
    out_path = os.path.join(ROOT, "docs", "詰み機会.csv")
    done = set()
    if os.path.exists(out_path):
        done = {r["file"] for r in csv.DictReader(open(out_path, encoding="utf-8"))}
    new_file = not os.path.exists(out_path)
    f = open(out_path, "a", encoding="utf-8", newline="")
    w = csv.writer(f, lineterminator="\r\n")
    if new_file:
        w.writerow(["date", "file", "opponent_type", "start_move", "mate_length",
                    "best_first", "result", "end_move", "actual_move"])
    for r in rows:
        if r["file"] in done:
            continue
        p = find_path(r["file"])
        if p is None:
            print("見つからない:", r["file"], flush=True); continue
        eps = scan(p, r["my_side"])
        if not eps:
            w.writerow([r["date"], r["file"], r["opponent_type"], "", "", "", "機会なし", "", ""])
        for e in eps:
            w.writerow([r["date"], r["file"], r["opponent_type"], e["start"], e["len"],
                        e["best"], e["result"], e["at"], e["actual"]])
        f.flush()
        print(r["file"], [(e["start"], e["len"], e["result"]) for e in eps], flush=True)
    f.close()


if __name__ == "__main__":
    main()
