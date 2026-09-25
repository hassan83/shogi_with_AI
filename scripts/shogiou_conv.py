#!/usr/bin/env python3
"""将皇(ken1shogi掲示板)の棋譜形式 -> USI手列

掲示板ページのHTML内 var initKihu="..." の中身を渡す。
形式: +7968GI-3334FU...
  +/- = 先手/後手, 4桁 = 移動元(筋段)+移動先, 00は打, 末尾2文字 = 移動後の駒
"""
import re, sys, shogi

PROMOTED = {"TO", "NY", "NK", "NG", "UM", "RY"}
DROP = {"FU": "P", "KY": "L", "KE": "N", "GI": "S", "KI": "G", "KA": "B", "HI": "R"}
RANK = "abcdefghi"


def sq(d):
    return f"{int(d[0])}{RANK[int(d[1]) - 1]}"


def convert(kihu_str):
    m = re.search(r"[+-]\d{4}[A-Z]{2}", kihu_str)
    if not m:
        raise ValueError("棋譜が見つかりません")
    toks = re.findall(r"([+-])(\d{2})(\d{2})([A-Z]{2})", kihu_str[m.start():])
    board, out = shogi.Board(), []
    for _sign, frm, to, code in toks:
        if frm == "00":
            mv = f"{DROP[code]}*{sq(to)}"
        else:
            mv = sq(frm) + sq(to)
            if code in PROMOTED:
                s = shogi.SQUARES[(int(frm[1]) - 1) * 9 + (9 - int(frm[0]))]
                pt = board.piece_type_at(s)
                if pt is not None and pt < 9:
                    mv += "+"
        if not board.is_legal(shogi.Move.from_usi(mv)):
            raise ValueError(f"不正な手 #{len(out)+1}: {frm}{to}{code} -> {mv}")
        board.push_usi(mv); out.append(mv)
    return out, board


def from_html(html):
    m = re.search(r'var initKihu="([^"]+)"', html)
    if not m:
        raise ValueError("initKihu が見つかりません")
    b = re.search(r'var black\s*=\s*"([^"]*)"', html)
    w = re.search(r'var white\s*=\s*"([^"]*)"', html)
    moves, board = convert(m.group(1))
    names = (b.group(1) if b else "先手", w.group(1) if w else "後手")
    return moves, board, names


if __name__ == "__main__":
    txt = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    if "initKihu" in txt:
        moves, board, names = from_html(txt)
        print(f"先手: {names[0]} / 後手: {names[1]}")
    else:
        moves, board = convert(txt)
    print(f"手数: {len(moves)}")
    print(" ".join(moves))
    print(board.kif_str())
