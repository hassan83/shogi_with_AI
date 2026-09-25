#!/usr/bin/env python3
"""棋譜から戦型を推定する（自動判定は目安。最終的な確認は目視推奨）。

判定項目:
  1. 居飛車 / 振り飛車（先手・後手それぞれ）: 序盤（デフォルト24手目）時点の
     飛車の位置の筋で判定。※最終局面ではなく序盤で見るのがポイント
     （終盤の戦術的な飛車移動を戦型と誤認しないため）
  2. 囲いの推定: 最終局面の玉位置と周辺の金銀配置パターンから簡易マッチング
     （矢倉/美濃/穴熊/舟囲い/金無双 の代表形のみ。精度は粗く、崩れた囲いや
     発展途中の形は「不明(個別確認要)」になりやすい。目視確認の補助として使う）

  python3 game_classify.py game.html [序盤判定の手数(デフォルト24)]
"""
import sys, shogi

def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0:2]
    import shogi.KIF as KIF
    return KIF.Parser.parse_file(path)[0]["moves"], None

def sq(file_, rank_):
    return (rank_ - 1) * 9 + (9 - file_)

CASTLES_SENTE = {
    "矢倉":   ((8,8), [(7,8,shogi.GOLD),(6,7,shogi.GOLD),(7,7,shogi.SILVER)]),
    "美濃":   ((2,8), [(3,8,shogi.SILVER),(2,7,shogi.GOLD),(1,8,shogi.KNIGHT)]),
    "穴熊":   ((1,9), [(2,8,shogi.SILVER),(2,9,shogi.GOLD),(1,8,shogi.KNIGHT)]),
    "舟囲い": ((6,8), [(7,8,shogi.GOLD),(5,8,shogi.GOLD),(6,7,shogi.SILVER)]),
    "金無双": ((7,8), [(6,8,shogi.GOLD),(6,7,shogi.GOLD)]),
}
def mirror(coords):
    return [(10-f, 10-r, pt) for f, r, pt in coords]

def detect_castle(board, color):
    king_sq = None
    for s in shogi.SQUARES:
        p = board.piece_at(s)
        if p and p.piece_type == shogi.KING and p.color == color:
            king_sq = s
    if king_sq is None:
        return "不明"
    best = "不明(個別確認要)"
    for name, (kpos, pieces) in CASTLES_SENTE.items():
        cand_pieces = pieces if color == shogi.BLACK else mirror(pieces)
        cand_kf, cand_kr = kpos if color == shogi.BLACK else (10-kpos[0], 10-kpos[1])
        if king_sq != sq(cand_kf, cand_kr):
            continue
        hit = sum(1 for f, r, pt in cand_pieces
                   if (p := board.piece_at(sq(f, r))) and p.piece_type == pt and p.color == color)
        if hit >= len(cand_pieces) - 1:
            best = name
            break
    return best

def rook_style(board, color, threshold_files):
    """飛車の筋から戦型を分類。
    先手: 1~2筋=居飛車, 7~9筋=向かい飛車方向(相手の飛車先), 3~6筋=振り飛車
    後手: 8~9筋=居飛車, 1~3筋=向かい飛車方向, 4~7筋=振り飛車
    """
    for s in shogi.SQUARES:
        p = board.piece_at(s)
        if p and p.piece_type in (shogi.ROOK, shogi.PROM_ROOK) and p.color == color:
            file_ = 9 - (s % 9)
            if file_ in threshold_files:
                return "居飛車", file_
            if color == shogi.BLACK:
                far = file_ >= 7
            else:
                far = file_ <= 3
            return ("向かい飛車系" if far else "振り飛車"), file_
    return "不明(飛車不在/駒台)", None

def classify(path, early_move=24):
    """他スクリプトから呼び出し可能な形。戻り値: dict"""
    moves, _ = load(path)
    board = shogi.Board()
    early_board = None
    for i, mv in enumerate(moves, 1):
        board.push_usi(mv)
        if i == early_move:
            early_board = shogi.Board(board.sfen())
    if early_board is None:
        early_board = board
    s_style, s_file = rook_style(early_board, shogi.BLACK, {2, 1})
    g_style, g_file = rook_style(early_board, shogi.WHITE, {8, 9})
    return {
        "先手戦型": f"{s_style}(飛車{s_file}筋)", "後手戦型": f"{g_style}(飛車{g_file}筋)",
        "先手囲い": detect_castle(board, shogi.BLACK), "後手囲い": detect_castle(board, shogi.WHITE),
    }

if __name__ == "__main__":
    path = sys.argv[1]
    early_move = int(sys.argv[2]) if len(sys.argv) > 2 else 24
    r = classify(path, early_move)
    print(f"--- {early_move}手目時点（序盤・戦型判定用） ---")
    print(f"先手: {r['先手戦型']}")
    print(f"後手: {r['後手戦型']}")
    print(f"\n--- 最終局面（囲い判定・精度は粗め） ---")
    print(f"先手 囲い: {r['先手囲い']}")
    print(f"後手 囲い: {r['後手囲い']}")
