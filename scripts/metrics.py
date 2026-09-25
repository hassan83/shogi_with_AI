#!/usr/bin/env python3
"""棋譜から学習用の各種指標を集計する。

  python3 metrics.py game.kif [depth] --name <自分の対局者名>

--name は必須（先手/後手のどちらが自分かを対局者名で判定するため）。

集計する指標:
  1. 大駒(飛角金)の停滞手数    … 優勢局面で動かなかった大駒を検出
  2. 評価値ピークからの目減り  … 優位を築いた後どれだけ失ったか
  3. 消費時間の分布            … 特に「評価値が動いていない局面での長考」を抽出
  4. 手番(先後)別の内容        … 勝敗だけでなく評価値推移で確認
  5. 悪手の発生する手数帯      … 序盤/中盤/終盤のどこで失点しやすいか
  6. 相手の戦型                … game_classify.py の判定を併記

結果は「棋譜メトリクス.md」に追記される（累積記録用）。
"""
import sys, re, os, datetime, shogi
from shogi_engine import Engine
from ja_notation import move_to_japanese

# 停滞を追跡する大駒。金は初期配置で複数あり「動かないのが自然」なケースが多く
# ノイズになるため対象外とする（飛・角・成駒のみ）
BIG_PIECES = {shogi.ROOK, shogi.BISHOP,
              shogi.PROM_ROOK, shogi.PROM_BISHOP}
STALL_THRESHOLD = 12      # 何手動かなければ「停滞」とみなすか
ADVANTAGE_CP = 500        # 「優勢」とみなす評価値
LONG_THINK_SEC = 20       # 「長考」とみなす秒数
QUIET_DIFF_CP = 80        # 「局面が動いていない」とみなす評価差
MAX_USEFUL_MATE_LEN = 9       # 実用範囲外(11手詰め以上)は記録しない（アプリの学習範囲が九手詰めまでのため）
MATE_SOLVER_MS = 4000         # go mate(詰将棋ソルバ)の思考時間[ms]。
                              # 2026/09/03: 専用ビルド(YANEURAOU_MATE_ENGINE)を使うよう変更。
                              # 通常ビルドは go mate を解釈せず通常探索にフォールバックし、
                              # 連続王手でない強制勝ちまで詰みとして拾っていた。
                              # 詰み手数の確定は必ずこのソルバで行う。通常探索の
                              # mateスコアは深さ依存で過大に出るうえ、王手が途切れる
                              # 変化も含むため、記録に使ってはいけない。


def parse_kif(path):
    """KIF/将皇HTMLから 手のUSI列・対局者名・各手の消費時間(秒) を取り出す。
    将皇HTML形式には消費時間が含まれないため、その場合は全て0とする
    （長考関連の指標は算出されないが、悪手数・大駒停滞等は通常通り機能する）。
    """
    if path.endswith((".html", ".htm")):
        from shogiou_conv import from_html
        moves, board, names = from_html(open(path, encoding="utf-8", errors="replace").read())
        return moves, names, [0] * len(moves), None

    txt = open(path, encoding="utf-8", errors="replace").read()
    import shogi.KIF as KIF
    g = KIF.Parser.parse_file(path)[0]
    times = []
    for line in txt.splitlines():
        m = re.match(r"\s*(\d+)\s+\S+.*?\(\s*(\d+):(\d+)\s*/", line)
        if m:
            times.append(int(m.group(2)) * 60 + int(m.group(3)))
    # 投了/詰み等の行で手数がずれる場合に合わせる
    times = times[:len(g["moves"])]
    while len(times) < len(g["moves"]):
        times.append(0)
    return g["moves"], g["names"], times, g.get("win")


def to_cp(score):
    if score is None:
        return 0
    kind, val = score
    if kind == "cp":
        return val
    return 100000 if val > 0 else -100000


def phase_of(i, total):
    if i <= total * 0.3:
        return "序盤"
    if i <= total * 0.7:
        return "中盤"
    return "終盤"


def analyze(path, depth, my_name):
    moves, names, times, win = parse_kif(path)
    total = len(moves)
    my_side = (shogi.BLACK if (names[0] == my_name or names[0].startswith("プレイヤー"))
               else shogi.WHITE)
    my_label = "先手" if my_side == shogi.BLACK else "後手"

    eng = Engine()
    mate_eng = Engine(mate=True)   # 連続王手の詰み判定は専用ビルドで行う
    board = shogi.Board()
    hist = []
    recs = []          # (手数, 自分の手か, 日本語表記, 自分視点eval, 差分, 消費時間)

    def eval_position(hist_moves):
        """局面を解析。 -> (自分視点eval, 生score, 手番, 通常探索のbestmove)
        追加のエンジン呼び出しなしで、通常評価のスコア種別が"mate"かどうかから
        詰みの有無・手数(N)をそのまま読み取れる（99999級の評価値と同じ元データ）。
        """
        raw, best = eng.analyze(hist_moves, depth=depth)
        turn = shogi.BLACK if len(hist_moves) % 2 == 0 else shogi.WHITE
        cp = to_cp(raw)
        mine = cp if turn == my_side else -cp
        return mine, raw, turn, best

    def verify_mate(hist_moves):
        """専用の詰み探索(go mate)で「連続王手の詰み」の手数を確定する。

        通常探索の mate スコアを使ってはいけない：
          - 探索が浅いほど手数を過大に読む（深さ12で13手→深さ20で11手→深さ28で9手 等）。
            深さをいくら上げても確定する保証がなく、記録値が安定しない。
          - 通常探索の mate は「強制的に詰む」の意味で、途中で王手が途切れ
            相手の反撃を受けながら寄せ切る変化も含む。詰将棋とは別物。
        go mate は詰将棋と同じ連続王手の詰みを厳密に解くので、
        詰将棋の練習成果と対応づけられる。

        -> (詰み手数 or None, 初手の日本語表記 or None)
        """
        b0 = shogi.Board()
        for m in hist_moves:
            b0.push_usi(m)
        n, best = mate_eng.mate_search(hist_moves, movetime_ms=MATE_SOLVER_MS)
        if n is None:
            return None, None
        return n, (move_to_japanese(b0, best) if best else "?")

    prev_mine, prev_raw, prev_turn, prev_best = eval_position([])
    missed_mates = []      # (手数, 最短N手, 実際の手, 最短の初手)
    slow_mates = []        # (手数, 最短N手, 実際N手, 実際の手, 最短の初手)
    my_recommended = {}                 # 自分の手番における、その時点の推奨手(USI)
    for i, mv in enumerate(moves, 1):
        side = shogi.BLACK if i % 2 == 1 else shogi.WHITE
        is_mine = (side == my_side)
        ja = move_to_japanese(board, mv)
        prev_board = shogi.Board(board.sfen())

        # 指す前の局面が「自分の手番」かつ通常探索で詰み(mate)スコアが
        # 出ている場合、指した手が詰みを維持しているか確認する。
        # 推奨手と一致するかどうかで判定してはいけない：別の手順でも同じ手数で
        # 詰むことは珍しくなく、それは詰み逃しではないため（誤検出の原因）。
        # スクリーニング深さでは手数を過大に読むので、候補として拾うだけにし、
        # 手数の確定は verify_mate（深さMATE_VERIFY_DEPTH）で行う。
        mate_candidate = (is_mine and prev_turn == my_side
                          and prev_raw is not None
                          and prev_raw[0] == "mate" and prev_raw[1] > 0)

        board.push_usi(mv)
        hist.append(mv)

        cur_mine, cur_raw, cur_turn, cur_best = eval_position(hist)

        if mate_candidate:
            shortest, best_ja = verify_mate(hist[:-1])
            if shortest is not None and shortest <= MAX_USEFUL_MATE_LEN:
                # 指した手の後に、まだ連続王手の詰みが残っているかを測る。
                # 注意: go mate は「手番側が詰ます」手順を探すので、自分の手を
                # 指した直後(相手番)の局面にそのまま掛けてはいけない。
                # 相手の応手をすべて試し、どの受けに対しても詰みが残るなら
                # 詰みは継続しており、その最大手数が実際の詰み手数になる。
                if board.is_checkmate():
                    actual_n = 1
                elif not board.is_check():
                    # 王手でない＝連続王手の詰み手順から外れた
                    actual_n = None
                else:
                    worst = 0
                    for reply in board.legal_moves:
                        nb = shogi.Board(board.sfen())
                        nb.push(reply)
                        if nb.is_checkmate():
                            sub = 0
                        else:
                            sub, _ = mate_eng.mate_search(
                                hist + [reply.usi()], movetime_ms=MATE_SOLVER_MS)
                        if sub is None:
                            worst = None
                            break
                        worst = max(worst, sub)
                    actual_n = (worst + 2) if worst is not None else None
                best_ja = best_ja or "?"
                if actual_n is None:
                    missed_mates.append((i, shortest, ja, best_ja))
                elif actual_n > shortest:
                    slow_mates.append((i, shortest, actual_n, ja, best_ja))
        # 差分は「自分が指した手によって自分の評価値がどう動いたか」のみ
        diff = (cur_mine - prev_mine) if is_mine else None
        # 詰みスコア(mate)が前後どちらかに絡む差分は、フラグの切り替わりであって
        # 悪手ではない（引き継ぎメモの既存ルール。2026/09/03に実装）。
        # エンジンの mate スコアは「連続王手の詰み」ではなく静かな手を含む強制勝ちを
        # 指すため、詰将棋的な詰み逃しとも別物。詰み逃しは go mate で別途判定している。
        mate_flag = ((prev_raw is not None and prev_raw[0] == "mate")
                     or (cur_raw is not None and cur_raw[0] == "mate"))
        recs.append((i, is_mine, ja, cur_mine, diff,
                     times[i-1] if i-1 < len(times) else 0, mate_flag))
        if is_mine and prev_best is not None:
            my_recommended[i] = prev_best
        prev_mine, prev_raw, prev_turn, prev_best = cur_mine, cur_raw, cur_turn, cur_best
    eng.quit()
    mate_eng.quit()

    # ---- 1. 大駒の停滞（自分の飛角金が優勢局面で動かない区間） ----
    # piece_last_move[sq] = その地点にある自分の駒が最後に動いた手数（0=開局から未移動）
    # 停滞は「機械的に何手動かなかったか」だけでは判定しない。その区間の自分の手番で
    # エンジンがその駒(その升)を動かす手を一度も推奨していなければ、そもそも動かす
    # べきではなかった可能性が高く、停滞として報告する意味がないため除外する。
    eval_by_move = {r[0]: r[3] for r in recs}
    board2 = shogi.Board()
    piece_last_move = {sq: 0 for sq in shogi.SQUARES}
    stalls = []
    for i, mv in enumerate(moves, 1):
        side = shogi.BLACK if i % 2 == 1 else shogi.WHITE
        m = shogi.Move.from_usi(mv)
        board2.push_usi(mv)
        if m.from_square is not None:
            piece_last_move[m.from_square] = 0
        piece_last_move[m.to_square] = i

        if eval_by_move.get(i, 0) >= ADVANTAGE_CP:
            for sq in shogi.SQUARES:
                p = board2.piece_at(sq)
                if p and p.color == my_side and p.piece_type in BIG_PIECES:
                    since = i - piece_last_move[sq]
                    if since >= STALL_THRESHOLD:
                        never = (piece_last_move[sq] == 0)
                        stalls.append((i, shogi.PIECE_JAPANESE_SYMBOLS[p.piece_type], since, never, sq))

    def _engine_ever_recommended_moving(sq, start_ply, end_ply):
        for ply, rec_usi in my_recommended.items():
            if start_ply < ply <= end_ply:
                rm = shogi.Move.from_usi(rec_usi)
                if rm.from_square == sq:
                    return True
        return False

    confirmed_stalls = []
    for i, pc, since, never, sq in stalls:
        # start_ply は「その升に居座っている駒が最後に動いた手数」。
        # piece_last_move[sq] は対局全体を処理し終えた後の最終状態を指しており、
        # この駒が停滞判定より後(例:このi手より後)に動くと上書きされ、
        # 過去の停滞判定には使えなくなる。since は判定時点で確定した値なので、
        # start_ply は since から逆算する(= i - since)ほうが安全。
        start_ply = i - since
        if _engine_ever_recommended_moving(sq, start_ply, i):
            confirmed_stalls.append((i, pc, since, never))

    stall_summary = {}
    for i, pc, since, never in confirmed_stalls:
        if pc not in stall_summary or since > stall_summary[pc][1]:
            stall_summary[pc] = (i, since, never)

    # ---- 2. 評価値ピークからの目減り ----
    mine_evals = [(r[0], r[3]) for r in recs]
    peak_i, peak_v = max(mine_evals, key=lambda x: x[1]) if mine_evals else (0, 0)
    after = [v for i, v in mine_evals if i > peak_i]
    final_v = mine_evals[-1][1] if mine_evals else 0
    drop = peak_v - min(after) if after else 0

    # ---- 3. 消費時間 ----
    # 詰みフラグ絡みの差分は悪手ではないので、時間分析でも差分をNone扱いにする
    my_times = [(r[0], r[5], (None if r[6] else r[4])) for r in recs if r[1]]
    total_time = sum(t for _, t, _ in my_times)
    long_thinks = [(i, t, d) for i, t, d in my_times if t >= LONG_THINK_SEC]
    quiet_long = [(i, t, d) for i, t, d in long_thinks
                  if d is not None and abs(d) <= QUIET_DIFF_CP]

    # ---- 3b. 長考と手の質の相関（基準A: 差分がマイナスでなければ好手扱い） ----
    # 差分がNone（＝詰みフラグ絡みで判定対象外）の手は分母からも除く。
    # 分母に残すと「好手でない」と数えられ、好手率が不当に下がるため。
    long_judged = [x for x in long_thinks if x[2] is not None]
    short_moves = [(i, t, d) for i, t, d in my_times if t < LONG_THINK_SEC]
    short_judged = [x for x in short_moves if x[2] is not None]

    long_bad = [x for x in long_judged if x[2] <= -300]
    short_bad = [x for x in short_judged if x[2] <= -300]
    long_rate = ((len(long_judged) - len(long_bad)) / len(long_judged) * 100) if long_judged else None
    short_rate = ((len(short_judged) - len(short_bad)) / len(short_judged) * 100) if short_judged else None

    # ---- 3c. 悪手を指した時の消費時間 vs 通常手 ----
    bad_times = [t for i, t, d in my_times if d is not None and d <= -300]
    ok_times = [t for i, t, d in my_times if d is not None and d > -300]
    avg_bad_time = sum(bad_times) / len(bad_times) if bad_times else None
    avg_ok_time = sum(ok_times) / len(ok_times) if ok_times else None

    # ---- 5. 悪手の手数帯 ----
    # r[6]=mate_flag が立つ差分は詰みフラグの切り替わりなので悪手に数えない
    bad = [(r[0], r[2], r[4]) for r in recs
           if r[1] and r[4] is not None and r[4] <= -300 and not r[6]]
    phase_count = {"序盤": 0, "中盤": 0, "終盤": 0}
    for i, _, _ in bad:
        phase_count[phase_of(i, total)] += 1

    # ---- 6. 戦型 ----
    try:
        from game_classify import classify
        cls = classify(path)
    except Exception as e:
        cls = {"先手戦型": f"判定エラー({e})", "後手戦型": "", "先手囲い": "", "後手囲い": ""}

    # 勝敗判定（KIFの最終行から推定。HTML形式はテキストに終局語が無いため
    # board.is_checkmate()で判定する）
    last_moves_n = len(moves)
    if path.endswith((".html", ".htm")):
        if board.is_checkmate():
            # 詰まされたのは「最終手の次の手番」側 = 最終手を指した側の勝ち
            winner = shogi.BLACK if last_moves_n % 2 == 1 else shogi.WHITE
            result = "勝ち" if winner == my_side else "負け"
        else:
            result = "不明(HTML形式・終局理由不明)"
    else:
        txt = open(path, encoding="utf-8", errors="replace").read()
        if "詰み" in txt.splitlines()[-1] or "詰み" in txt.splitlines()[-2]:
            winner = shogi.BLACK if last_moves_n % 2 == 1 else shogi.WHITE
            result = "勝ち" if winner == my_side else "負け"
        elif "投了" in txt:
            winner = shogi.BLACK if last_moves_n % 2 == 1 else shogi.WHITE
            result = "勝ち" if winner == my_side else "負け"
        elif "切れ負け" in txt:
            # 切れ負けは「最終手の次の手番」が時間切れになった側。詰み/投了とはパリティが逆
            loser = shogi.WHITE if last_moves_n % 2 == 1 else shogi.BLACK
            result = "負け(切れ負け)" if loser == my_side else "勝ち(相手切れ負け)"
        else:
            result = "不明"

    return {
        "path": path, "names": names, "total": total, "my_label": my_label,
        "win": win, "result": result, "recs": recs,
        "stalls": stall_summary,
        "peak": (peak_i, peak_v), "final": final_v, "drop": drop,
        "total_time": total_time, "long_thinks": long_thinks, "quiet_long": quiet_long,
        "long_rate": long_rate, "short_rate": short_rate,
        "n_long": len(long_thinks), "n_long_judged": len(long_judged), "n_long_bad": len(long_bad),
        "avg_bad_time": avg_bad_time, "avg_ok_time": avg_ok_time,
        "bad": bad, "phase_count": phase_count, "cls": cls,
        "missed_mates": missed_mates,
        "slow_mates": slow_mates,
    }


def report(r):
    L = []
    A = L.append
    A(f"## {os.path.basename(r['path'])}")
    A(f"- 対局者: 先手={r['names'][0]} / 後手={r['names'][1]}  （自分は{r['my_label']}）")
    A(f"- 手数: {r['total']}")
    A(f"- 戦型: 先手={r['cls']['先手戦型']} / 後手={r['cls']['後手戦型']}")
    A(f"- 囲い: 先手={r['cls']['先手囲い']} / 後手={r['cls']['後手囲い']}")
    A("")
    A(f"### 1. 大駒の停滞（優勢時に{STALL_THRESHOLD}手以上動かず、かつその間にエンジンが当該駒を動かす手を推奨していた自分の飛角金）")
    if r["stalls"]:
        for pc, (i, since, never) in sorted(r["stalls"].items(), key=lambda x: -x[1][1]):
            tag = "（開局から一度も動かず）" if never else ""
            A(f"- {pc}: 最大{since}手停滞（{i}手目時点）{tag}")
    else:
        A("- 該当なし")
    A("")
    A("### 2. 評価値ピークからの目減り")
    A(f"- 最大評価値: {r['peak'][1]:+d}（{r['peak'][0]}手目）")
    A(f"- 終局時: {r['final']:+d}")
    A(f"- ピーク後の最大下落幅: {r['drop']}")
    A("")
    A("### 3. 消費時間")
    A(f"- 自分の総消費: {r['total_time']}秒")
    if r["quiet_long"]:
        A(f"- **局面が動いていないのに長考した手**（{LONG_THINK_SEC}秒以上・評価差{QUIET_DIFF_CP}以内）:")
        for i, t, d in r["quiet_long"]:
            A(f"  - {i}手目: {t}秒（差分{d:+d}）")
    else:
        A("- 静かな局面での長考: なし")
    A("")
    A(f"### 3b. 長考と手の質（基準A: 差分-300超なら好手扱い）")
    if r["long_rate"] is not None:
        A(f"- 長考({LONG_THINK_SEC}秒以上) {r['n_long_judged']}手中 好手率 {r['long_rate']:.0f}%（うち悪手{r['n_long_bad']}手／長考{r['n_long']}手中、詰み絡み{r['n_long'] - r['n_long_judged']}手は判定対象外）")
    else:
        A(f"- 長考({LONG_THINK_SEC}秒以上): なし")
    if r["short_rate"] is not None:
        A(f"- 短考({LONG_THINK_SEC}秒未満) 好手率 {r['short_rate']:.0f}%")
    A("")
    A("### 3c. 悪手を指した時の消費時間")
    if r["avg_bad_time"] is not None:
        A(f"- 悪手時の平均: {r['avg_bad_time']:.1f}秒")
    else:
        A("- 悪手なし")
    if r["avg_ok_time"] is not None:
        A(f"- 通常手の平均: {r['avg_ok_time']:.1f}秒")
    A("")
    A("### 5. 悪手の手数帯（差分-300以下）")
    A(f"- 序盤{r['phase_count']['序盤']} / 中盤{r['phase_count']['中盤']} / 終盤{r['phase_count']['終盤']}")
    for i, ja, d in r["bad"]:
        A(f"  - {i}手目 {ja}  差分{d:+d}  ({phase_of(i, r['total'])})")
    A("")
    A(f"### 詰み逃し（連続王手の詰み、{MAX_USEFUL_MATE_LEN}手まで／go mateで確定）")
    if r["missed_mates"]:
        for i, n, actual, best in r["missed_mates"]:
            A(f"- {i}手目: **{n}手詰めを逃す**（実際={actual} / 詰み初手={best}）")
    else:
        A("- 該当なし")
    A("")
    A("### 遠回りの詰み（詰ませたが最短ではなかった手）")
    if r["slow_mates"]:
        for i, n, an, actual, best in r["slow_mates"]:
            A(f"- {i}手目: 最短{n}手詰めのところ{an}手詰め（実際={actual} / 最短の初手={best}）")
    else:
        A("- 該当なし")
    A("")
    return "\n".join(L)


CSV_PATH = "対局指標.csv"
CSV_HEADER = ("file,date,opponent_type,my_side,result,total_moves,opp_style,my_style,"
              "n_bad,bad_opening,bad_middle,bad_endgame,peak_eval,final_eval,drop,"
              "total_time,n_long,long_good_rate,short_good_rate,avg_bad_time,avg_ok_time,"
              "max_stall_piece,max_stall_moves,n_missed_mate,missed_mate_lengths,"
              "n_slow_mate,opp_rank\n")

MISSED_MATE_CSV = "詰み逃しログ.csv"
SLOW_MATE_CSV = "遠回りの詰みログ.csv"
SLOW_MATE_HEADER = ["date", "file", "move", "shortest_len", "actual_len", "actual_move", "best_move"]
MISSED_MATE_HEADER = ["date", "file", "move", "mate_length", "actual_move", "best_move"]


def get_date(path):
    try:
        txt = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r"開始日時：(\d{4}/\d{2}/\d{2})", txt)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def get_opponent_type(path):
    """COM戦かどうかを判定。kifu/com/配下、または拡張子がhtmlならCOM扱い。"""
    norm = path.replace("\\", "/")
    if "/com/" in norm or path.endswith((".html", ".htm")):
        return "com"
    return "human"


def upsert_missed_mate_csv(r, date):
    """同じファイル名の既存行を削除してから新しい行を書き込む(再実行しても重複しない)。"""
    import csv
    basename = os.path.basename(r["path"])
    rows = []
    if os.path.exists(MISSED_MATE_CSV):
        with open(MISSED_MATE_CSV, encoding="utf-8") as f:
            rows = [row for row in csv.DictReader(f) if row["file"] != basename]
    for i, n, actual, best in r["missed_mates"]:
        rows.append({"date": date, "file": basename, "move": i,
                     "mate_length": n, "actual_move": actual,
                     "best_move": best})
    with open(MISSED_MATE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=MISSED_MATE_HEADER)
        w.writeheader()
        w.writerows(rows)


def upsert_slow_mate_csv(r, date):
    """遠回りの詰み(詰ませたが最短ではなかった手)を記録。再実行時は該当行を上書き。"""
    import csv
    basename = os.path.basename(r["path"])
    rows = []
    if os.path.exists(SLOW_MATE_CSV):
        with open(SLOW_MATE_CSV, encoding="utf-8") as f:
            rows = [row for row in csv.DictReader(f) if row["file"] != basename]
    for i, n, an, actual, best in r["slow_mates"]:
        rows.append({"date": date, "file": basename, "move": i,
                     "shortest_len": n, "actual_len": an,
                     "actual_move": actual, "best_move": best})
    with open(SLOW_MATE_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SLOW_MATE_HEADER)
        w.writeheader()
        w.writerows(rows)


def append_csv(r):
    import csv
    date = get_date(r["path"])
    my_style = r["cls"]["先手戦型"] if r["my_label"] == "先手" else r["cls"]["後手戦型"]
    opp_style = r["cls"]["後手戦型"] if r["my_label"] == "先手" else r["cls"]["先手戦型"]
    if r["stalls"]:
        pc, (i, since, never) = max(r["stalls"].items(), key=lambda x: x[1][1])
    else:
        pc, since = "", 0
    row = [
        os.path.basename(r["path"]), date, get_opponent_type(r["path"]), r["my_label"], r["result"], r["total"],
        opp_style, my_style,
        len(r["bad"]), r["phase_count"]["序盤"], r["phase_count"]["中盤"], r["phase_count"]["終盤"],
        r["peak"][1], r["final"], r["drop"],
        r["total_time"], r["n_long"],
        f"{r['long_rate']:.0f}" if r["long_rate"] is not None else "",
        f"{r['short_rate']:.0f}" if r["short_rate"] is not None else "",
        f"{r['avg_bad_time']:.1f}" if r["avg_bad_time"] is not None else "",
        f"{r['avg_ok_time']:.1f}" if r["avg_ok_time"] is not None else "",
        pc, since,
        len(r["missed_mates"]),
        "/".join(str(x[1]) for x in r["missed_mates"]),
        len(r["slow_mates"]),
        "",  # opp_rank: 対戦相手.csv/手動記録との連携用。COM戦は級位概念なしのため空欄
    ]
    exists = os.path.exists(CSV_PATH)
    with open(CSV_PATH, "a", encoding="utf-8", newline="") as f:
        if not exists:
            f.write(CSV_HEADER)
        csv.writer(f).writerow(row)
    upsert_missed_mate_csv(r, date)
    upsert_slow_mate_csv(r, date)


def strict_check(path, targets, depth=20):
    """基準B: 指定手数でエンジン推奨手と実際の手が一致するか確認する。"""
    import shogi.KIF as KIF
    moves = KIF.Parser.parse_file(path)[0]["moves"]
    eng = Engine()
    out = []
    for t in targets:
        if t > len(moves):
            continue
        hist = moves[:t-1]
        b = shogi.Board()
        for mv in hist:
            b.push_usi(mv)
        score, best = eng.analyze(hist, depth=depth)
        actual = moves[t-1]
        out.append((t, move_to_japanese(b, actual),
                    move_to_japanese(b, best) if best else "?",
                    actual == best))
    eng.quit()
    return out


def main():
    argv = sys.argv[1:]
    if "--name" not in argv or argv.index("--name") + 1 >= len(argv):
        sys.exit("usage: python3 metrics.py game.kif [depth] --name <自分の対局者名>")
    name_i = argv.index("--name")
    my_name = argv[name_i + 1]
    # --name の値は位置引数として扱わない
    args = [a for i, a in enumerate(argv) if not a.startswith("--") and i != name_i + 1]
    path = args[0]
    depth = int(args[1]) if len(args) > 1 else 16

    r = analyze(path, depth, my_name)
    text = report(r)

    # --strict: 長考手と悪手候補をエンジン推奨手と照合（基準B）
    if "--strict" in sys.argv:
        targets = sorted({i for i, _, _ in r["long_thinks"]} | {i for i, _, _ in r["bad"]})
        if targets:
            res = strict_check(path, targets)
            lines = ["### 基準B: エンジン推奨手との一致（深さ20）"]
            match = sum(1 for _, _, _, ok in res if ok)
            lines.append(f"- 対象{len(res)}手中 一致 {match}手 ({match/len(res)*100:.0f}%)")
            for t, act, best, ok in res:
                mark = "○" if ok else "×"
                lines.append(f"  - {mark} {t}手目 実際={act} / 推奨={best}")
            text += "\n" + "\n".join(lines) + "\n"

    print(text)
    with open("棋譜メトリクス.md", "a", encoding="utf-8") as f:
        f.write(f"\n<!-- {datetime.date.today()} -->\n" + text + "\n")
    append_csv(r)


if __name__ == "__main__":
    main()
