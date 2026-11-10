#!/usr/bin/env bash
# ============================================================
#  環境構築〜解析の通しテスト（リリース前に必須）
#  使い方:  bash tests/setup_test.sh <期待する作業ディレクトリ>
#
#  scripts/shogi_setup.sh を実行し、次をすべて確認する。
#    1. 環境構築が終了コード0で終わる
#    2. 作業ディレクトリが期待どおり（SHOGI_WORK の有無による切り替え）
#    3. 通常エンジン・詰将棋エンジンがその場所にビルドされている
#    4. 詰将棋エンジンが1手詰めを検出する
#    5. shogi_engine.py が同じ作業ディレクトリを参照する
#    6. テスト用棋譜で metrics.py（先手/後手の判定、--name 必須）と analyze.py が動く
#    7. 7z コマンドが無い環境用の展開（extract_7z.py / py7zr）で、評価関数が同じ内容に展開できる
#    8. 評価関数の選択（SHOGI_EVAL）どおりのファイルがそろっている
#       - hao           : nn.bin のみ（progress.bin・eval_options.txt が残っていない）
#       - tsuyoura11*   : nn.bin・progress.bin・eval_options.txt（FV_SCALE 24）。エンジンが進行度ファイルを読み込む
#
#  GitHub Actions（.github/workflows/test.yml）が次の3パターンで実行する：
#    - SHOGI_WORK を設定した場合（評価関数は SHOGI_EVAL=tsuyoura11mini）
#    - 未設定で /home/claude がある場合（claude.ai と同じ）
#    - 未設定で /home/claude がない場合（~/.shogi_with_AI）
# ============================================================
set -u
EXPECTED="${1:?usage: bash tests/setup_test.sh <期待する作業ディレクトリ>}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="$REPO/tests/fixtures/sample.kif"
LOG="$(mktemp)"
FAILED=0

ok()   { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=1; }

SHOGI_EVAL="${SHOGI_EVAL:-hao}"
echo "=== 環境構築（SHOGI_WORK=${SHOGI_WORK:-未設定} / SHOGI_EVAL=$SHOGI_EVAL / 期待する作業ディレクトリ=$EXPECTED）==="
( cd "$REPO/scripts" && bash shogi_setup.sh ) > "$LOG" 2>&1
RC=$?
cat "$LOG"
echo ""
echo "=== 確認 ==="
[ $RC -eq 0 ] && ok "shogi_setup.sh が終了コード0で完了" || fail "shogi_setup.sh の終了コード: $RC"

EXPECTED_ABS="$(cd "$EXPECTED" 2>/dev/null && pwd || echo "$EXPECTED")"
if grep -qxF "作業ディレクトリ: $EXPECTED_ABS" "$LOG"; then ok "作業ディレクトリ: $EXPECTED_ABS"
else fail "作業ディレクトリが期待と違う（期待: $EXPECTED_ABS / 実際: $(grep '^作業ディレクトリ:' "$LOG")）"; fi

[ -x "$EXPECTED_ABS/YaneuraOu/source/YaneuraOu-by-gcc" ] && ok "通常エンジンがビルドされている" || fail "通常エンジンがない"
[ -x "$EXPECTED_ABS/mate_build/YaneuraOu-by-gcc" ] && ok "詰将棋エンジンがビルドされている" || fail "詰将棋エンジンがない"
[ -f "$EXPECTED_ABS/YaneuraOu/source/eval/nn.bin" ] && ok "評価関数がある" || fail "評価関数（eval/nn.bin）がない"
grep -q "詰将棋エンジン: OK（" "$LOG" && ok "詰将棋エンジンが1手詰めを検出" || fail "詰将棋エンジンの動作確認に失敗"

PY_WORK="$(cd "$REPO/scripts" && python3 -c 'import shogi_engine as s; print(s.WORK_DIR)' 2>&1)"
[ "$PY_WORK" = "$EXPECTED_ABS" ] && ok "shogi_engine.py も同じ作業ディレクトリを参照" \
  || fail "shogi_engine.py の作業ディレクトリが違う: $PY_WORK"

DOCS="$(mktemp -d)"
cd "$DOCS"
OUT="$(python3 "$REPO/scripts/metrics.py" "$FIXTURE" 8 --name テスト先手 2>&1)"; RC=$?
if [ $RC -eq 0 ] && grep -q "自分は先手" <<<"$OUT" && grep -q "手数: 40" <<<"$OUT"; then ok "metrics.py（--name テスト先手 → 先手と判定）"
else fail "metrics.py（先手）: 終了コード $RC"; echo "$OUT" | tail -20; fi

OUT="$(python3 "$REPO/scripts/metrics.py" "$FIXTURE" 8 --name テスト後手 2>&1)"; RC=$?
if [ $RC -eq 0 ] && grep -q "自分は後手" <<<"$OUT"; then ok "metrics.py（--name テスト後手 → 後手と判定）"
else fail "metrics.py（後手）: 終了コード $RC"; echo "$OUT" | tail -20; fi

[ -s "$DOCS/対局指標.csv" ] && ok "metrics.py が 対局指標.csv を出力" || fail "対局指標.csv が出力されていない"

if python3 "$REPO/scripts/metrics.py" "$FIXTURE" 8 >/dev/null 2>&1; then fail "metrics.py が --name なしで実行できてしまう"
else ok "metrics.py は --name なしだとエラーで止まる"; fi

cd "$REPO"
OUT="$(python3 scripts/analyze.py "$FIXTURE" 6 2>&1)"; RC=$?
if [ $RC -eq 0 ] && grep -q "差分=" <<<"$OUT"; then ok "analyze.py が動く"
else fail "analyze.py: 終了コード $RC"; echo "$OUT" | tail -20; fi

# 7z が無い環境（claude.ai の Code タブなど）用の展開経路。CI には 7z があり
# shogi_setup.sh ではこの経路を通らないため、同じアーカイブを py7zr で展開して比べる
python3 -c "import py7zr" 2>/dev/null || pip3 install py7zr --break-system-packages >/dev/null 2>&1 || pip3 install py7zr >/dev/null 2>&1
X7="$(mktemp -d)"
case "$SHOGI_EVAL" in
  hao)             ARC="$EXPECTED_ABS/hao.7z";                      ARC_NN="eval/nn.bin" ;;
  tsuyoura11mini)  ARC="$(ls "$EXPECTED_ABS"/TuyouraOu11mini-*.7z 2>/dev/null | head -1)";  ARC_NN="nn.bin" ;;
  tsuyoura11micro) ARC="$(ls "$EXPECTED_ABS"/TuyouraOu11micro-*.7z 2>/dev/null | head -1)"; ARC_NN="nn.bin" ;;
esac
if [ ! -f "$ARC" ]; then fail "評価関数のアーカイブがない（SHOGI_EVAL=$SHOGI_EVAL）"
elif python3 "$REPO/scripts/extract_7z.py" "$ARC" "$X7" \
     && cmp -s "$X7/$ARC_NN" "$EXPECTED_ABS/YaneuraOu/source/eval/nn.bin"; then
  ok "7z が無いときの展開（py7zr）でも同じ評価関数になる"
else fail "py7zr での評価関数の展開に失敗、または内容が違う"; fi

EVAL_DIR="$EXPECTED_ABS/YaneuraOu/source/eval"
if [ "$SHOGI_EVAL" = hao ]; then
  if [ ! -e "$EVAL_DIR/progress.bin" ] && [ ! -e "$EVAL_DIR/eval_options.txt" ]; then ok "Háo：つようら王用のファイル（progress.bin・eval_options.txt）が残っていない"
  else fail "Háo なのに progress.bin か eval_options.txt が残っている"; fi
else
  [ -f "$EVAL_DIR/progress.bin" ] && ok "進行度ファイル（progress.bin）がある" || fail "progress.bin がない"
  grep -qx "FV_SCALE 24" "$EVAL_DIR/eval_options.txt" 2>/dev/null && ok "eval_options.txt が FV_SCALE 24" || fail "eval_options.txt がないか FV_SCALE 24 でない"
  OUT="$(cd "$EXPECTED_ABS/YaneuraOu/source" && printf 'usi\nisready\nquit\n' | timeout 60 ./YaneuraOu-by-gcc 2>&1)"
  if grep -q "loading progress file" <<<"$OUT" && grep -q "readyok" <<<"$OUT"; then ok "エンジンが評価関数と進行度ファイルを読み込む"
  else fail "エンジンが評価関数・進行度ファイルを読み込めない"; echo "$OUT" | tail -10; fi
fi

rm -rf "$DOCS" "$LOG" "$X7"
echo ""
if [ $FAILED -eq 0 ]; then echo "テスト成功"; else echo "テスト失敗"; exit 1; fi
