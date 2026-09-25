#!/usr/bin/env python3
"""棋譜中の両玉の段位置を追跡し、中段玉・入玉圏への到達を検出・集計する。

  python3 king_track.py game.html

定義:
  先手玉: 4~6段目=中段, 1~3段目=入玉圏
  後手玉: 4~6段目=中段, 7~9段目=入玉圏

重要: 終局が詰みの場合、「詰みルートに突入した時点」の玉位置のみを記録する。
      詰みまでの追い込みの間、玉が中段を通過し続けても重複カウントしない。
      詰みルート＝終局(詰み)から遡り、攻め方の着手が連続して王手になっている区間。
      投了・切れ負け等、詰みで終わっていない対局は従来通り全手フラグする。
出力は「詰み形ログ.csv」に保存する（同じファイルの既存行は上書き=再実行しても重複しない）。
"""
import sys, os, csv, shogi, datetime

CSV_PATH = "詰み形ログ.csv"
CSV_HEADER = ["date", "file", "opponent_type", "move", "pattern"]

def get_opponent_type(path):
    norm = path.replace("\\", "/")
    if "/com/" in norm or path.endswith((".html", ".htm")):
        return "com"
    return "human"

def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0:2]
    import shogi.KIF as KIF
    g = KIF.Parser.parse_file(path)[0]
    return g["moves"], None

def find_kings(b):
    s = g = None
    for sq in shogi.SQUARES:
        p = b.piece_at(sq)
        if p and p.piece_type == shogi.KING:
            if p.color == shogi.BLACK: s = sq
            else: g = sq
    return s, g

def rank_of(sq):
    return sq // 9 + 1

def flag_for(sr, gr):
    flags = []
    if sr and 4 <= sr <= 6: flags.append("先手玉:中段")
    if sr and sr <= 3: flags.append("先手玉:入玉圏")
    if gr and 4 <= gr <= 6: flags.append("後手玉:中段")
    if gr and gr >= 7: flags.append("後手玉:入玉圏")
    return flags

def get_date(path):
    try:
        import re
        txt = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r"開始日時：(\d{4}/\d{2}/\d{2})", txt)
        if m: return m.group(1)
    except Exception:
        pass
    return str(datetime.date.today())

def upsert_csv(path_basename, date, opponent_type, entries):
    """同じファイル名の既存行を削除してから新しい行を追記する(再実行しても重複しない)。"""
    rows = []
    if os.path.exists(CSV_PATH):
        with open(CSV_PATH, encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["file"] != path_basename]
    for move, pattern in entries:
        rows.append({"date": date, "file": path_basename, "opponent_type": opponent_type,
                     "move": move, "pattern": pattern})
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_HEADER)
        w.writeheader()
        w.writerows(rows)

def main():
    path = sys.argv[1]
    moves, _ = load(path)
    board = shogi.Board()

    is_check_after = []
    king_state = []
    for i, mv in enumerate(moves, 1):
        board.push_usi(mv)
        sk, gk = find_kings(board)
        sr, gr = (rank_of(sk) if sk is not None else None), (rank_of(gk) if gk is not None else None)
        king_state.append((i, sr, gr))
        is_check_after.append(board.is_check())

    is_mate_end = len(moves) > 0 and board.is_checkmate()

    entries = []
    if is_mate_end:
        n = len(moves)
        chain_start = n
        idx = n - 1
        while idx - 2 >= 0 and is_check_after[idx - 2]:
            idx -= 2
            chain_start = idx + 1
        i, sr, gr = king_state[chain_start - 1]
        for flag in flag_for(sr, gr):
            entries.append((i, flag + "(詰みルート突入)"))
        for i, sr, gr in king_state[:chain_start - 1]:
            for flag in flag_for(sr, gr):
                entries.append((i, flag))
    else:
        for i, sr, gr in king_state:
            for flag in flag_for(sr, gr):
                entries.append((i, flag))

    print(f"手数: {len(moves)}  終局形: {'詰み' if is_mate_end else '投了/切れ負け等'}")
    if entries:
        for i, flag in entries:
            print(f"{i}手目  {flag}")
    else:
        print("中段玉・入玉圏の出現なし")

    upsert_csv(os.path.basename(path), get_date(path), get_opponent_type(path), entries)

if __name__ == "__main__":
    main()
