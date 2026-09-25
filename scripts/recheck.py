#!/usr/bin/env python3
"""深さ16スクリーニングでの悪手疑いを深さ20で再確認する。

測定1回ごとにエンジンを起動し直すため、長い棋譜でも途中で落ちない。

指定手数について、その手を指す前のsfenから
「実際の手を指した後」と「推奨手を指した後」の評価値を
同一エンジンプロセス・同一depthで測り、真の差分を出す。

  python3 recheck.py game.kif 20 "38,52,58"
"""
import sys, shogi
from shogi_engine import Engine
from ja_notation import move_to_japanese


def load(path):
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        return from_html(open(path, encoding="utf-8", errors="replace").read())[0]
    import shogi.KIF as KIF
    return KIF.Parser.parse_file(path)[0]["moves"]


def main():
    path, depth, targets = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    moves = load(path)

    def probe(sfen, extra, depth):
        """1回の測定ごとにエンジンを起動し直す。

        長い棋譜・深い探索では同一プロセスを使い回すと途中で落ち、
        BrokenPipeError で残りの局面が測れなくなる（piyo_game8で発生）。
        compare.py が同じ理由で1手ごとに起動し直しているのに合わせた。
        """
        for attempt in range(3):
            e = None
            try:
                e = Engine()
                return e.analyze_from_sfen(sfen, extra, depth=depth)
            except Exception:
                if attempt == 2:
                    return (None, None, [])
            finally:
                if e is not None:
                    try:
                        e.quit()
                    except Exception:
                        pass
        return (None, None, [])

    for t in [int(x) for x in targets.split(",")]:
        hist = moves[:t - 1]
        b = shogi.Board()
        for mv in hist:
            b.push_usi(mv)
        sfen = b.sfen()
        actual = moves[t - 1]

        # 推奨手を特定（指す前の局面）
        _, best, _ = probe(sfen, [], depth)

        # 実際の手を指した後の評価値（相手視点）→ 手番側視点に反転
        s_actual, _, _ = probe(sfen, [actual], depth)
        # 推奨手を指した後の評価値
        s_best, _, _ = probe(sfen, [best], depth) if best else (None, None, None)

        def to_cp(score):
            if score is None:
                return None
            kind, val = score
            if kind == "cp":
                return -val
            return -100000 if val > 0 else 100000  # 反転

        cp_actual = to_cp(s_actual)
        cp_best = to_cp(s_best)
        diff = (cp_actual - cp_best) if (cp_actual is not None and cp_best is not None) else None

        print(f"=== {t}手目 ===")
        print(f"  実際  : {move_to_japanese(b, actual)}  (指した後 手番側視点 eval={cp_actual})")
        print(f"  推奨  : {move_to_japanese(b, best) if best else '?'}  (指した後 手番側視点 eval={cp_best})")
        print(f"  真の差分（実際-推奨）= {diff}")
        print(f"  sfen  : {sfen}\n", flush=True)


if __name__ == "__main__":
    main()
