"""USI手 -> 日本語表記（７六歩(７七) 形式）"""
import shogi

FILE_K = ["", "１", "２", "３", "４", "５", "６", "７", "８", "９"]
RANK_K = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]


def sq_to_kanji(sq):
    return f"{FILE_K[9 - (sq % 9)]}{RANK_K[sq // 9 + 1]}"


def move_to_japanese(board, usi_move):
    """board は「その手を指す前」の状態であること"""
    mv = shogi.Move.from_usi(usi_move)
    to_s = sq_to_kanji(mv.to_square)
    if mv.from_square is None:
        return f"{to_s}{shogi.PIECE_JAPANESE_SYMBOLS[mv.drop_piece_type]}打"
    pt = board.piece_type_at(mv.from_square)
    kanji = shogi.PIECE_JAPANESE_SYMBOLS[pt] if pt else "?"
    promo = "成" if mv.promotion else ""
    return f"{to_s}{kanji}{promo}({sq_to_kanji(mv.from_square)})"
