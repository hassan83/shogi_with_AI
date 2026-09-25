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
#
#  GitHub Actions（.github/workflows/test.yml）が次の3パターンで実行する：
#    - SHOGI_WORK を設定した場合
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

echo "=== 環境構築（SHOGI_WORK=${SHOGI_WORK:-未設定} / 期待する作業ディレクトリ=$EXPECTED）==="
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

rm -rf "$DOCS" "$LOG"
echo ""
if [ $FAILED -eq 0 ]; then echo "テスト成功"; else echo "テスト失敗"; exit 1; fi
