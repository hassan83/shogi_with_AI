#!/usr/bin/env bash
# ============================================================
#  将棋解析環境 セットアップスクリプト
#  YaneuraOu v9.40 + Háo(tanuki- halfkp_256x2-32-32) + python-shogi
#  使い方:  bash shogi_setup.sh
#  所要時間: 3〜6分程度（ビルドとダウンロードのため）
# ============================================================
set -e
# cd する前にスクリプト自身の場所を絶対パスで確定させる
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPTS/.." && pwd)"
WORK=/home/claude
cd "$WORK"

echo "=== [1/6] 依存パッケージ ==="
apt-get install -y p7zip-full >/dev/null 2>&1 || true
pip3 install python-shogi --break-system-packages >/dev/null 2>&1 || true

echo "=== [2/6] YaneuraOu ソース取得 (v9.40) ==="
if [ ! -d YaneuraOu ]; then
  git clone --depth 1 https://github.com/yaneurao/YaneuraOu.git >/dev/null 2>&1
  cd YaneuraOu
  git fetch --tags --depth 200 >/dev/null 2>&1
  git checkout v9.40 >/dev/null 2>&1
  cd "$WORK"
fi

echo "=== [3/6] CPU判定してビルド ==="
FLAGS=$(grep -m1 flags /proc/cpuinfo)
if echo "$FLAGS" | grep -q avx512_vnni; then TARGET=AVX512VNNI
elif echo "$FLAGS" | grep -q avx512f;    then TARGET=AVX512
elif echo "$FLAGS" | grep -q avx2;       then TARGET=AVX2
else TARGET=SSE42; fi
echo "    TARGET_CPU=$TARGET"
cd "$WORK/YaneuraOu/source"
if [ ! -x YaneuraOu-by-gcc ]; then
  make -j"$(nproc)" YANEURAOU_EDITION=YANEURAOU_ENGINE_NNUE \
       TARGET_CPU=$TARGET COMPILER=g++ normal >/dev/null 2>&1
fi

echo "=== [3b/6] 詰将棋専用エンジンのビルド ==="
# 通常の NNUE ビルドは "go mate" を解釈せず通常探索にフォールバックするため、
# 連続王手でない強制勝ちまで詰みとして拾ってしまう（2026/09/03に判明）。
# 連続王手の詰み判定には専用ビルドが必須。
MATE_DIR="$WORK/mate_build"
if [ ! -x "$MATE_DIR/YaneuraOu-by-gcc" ]; then
  rm -rf "$MATE_DIR"
  cp -r "$WORK/YaneuraOu/source" "$MATE_DIR"
  rm -f "$MATE_DIR/YaneuraOu-by-gcc"
  ( cd "$MATE_DIR" && make -j"$(nproc)" YANEURAOU_EDITION=YANEURAOU_MATE_ENGINE \
       TARGET_CPU=$TARGET COMPILER=g++ normal >/dev/null 2>&1 )
fi
if [ -x "$MATE_DIR/YaneuraOu-by-gcc" ]; then
  echo "    詰将棋エンジン: OK"
else
  echo "    ✗ 詰将棋エンジンのビルドに失敗。詰み逃し指標は使えません"
fi

echo "=== [4/6] 評価関数 Háo 取得 ==="
cd "$WORK"
if [ ! -f "$WORK/YaneuraOu/source/eval/nn.bin" ]; then
  URL="https://github.com/nodchip/tanuki-/releases/download/tanuki-.halfkp_256x2-32-32.2023-05-08/tanuki-.halfkp_256x2-32-32.2023-05-08.7z"
  curl -sL -o hao.7z "$URL"
  mkdir -p hao_extracted && 7z x hao.7z -ohao_extracted -y >/dev/null
  mkdir -p "$WORK/YaneuraOu/source/eval"
  cp hao_extracted/eval/nn.bin "$WORK/YaneuraOu/source/eval/nn.bin"
fi

echo "=== [5/6] 解析スクリプトの確認 ==="
# スクリプトはリポジトリの scripts/ が正本。
# 以前はこのファイル内にヒアドキュメントで実体を埋め込んでいたが、
# リポジトリ側を更新しても埋め込みが古いまま残り、
# 新しいセッションで古い metrics.py / shogi_engine.py を動かす事故が起きた。
# そのため生成をやめ、リポジトリのスクリプトをそのまま使う方式に変更した（2026/08/31）。
REQUIRED="shogi_engine.py ja_notation.py shogiou_conv.py analyze.py best_moves.py compare.py game_classify.py king_track.py metrics.py"
MISSING=""
for f in $REQUIRED; do
  [ -f "$SCRIPTS/$f" ] || MISSING="$MISSING $f"
done
if [ -n "$MISSING" ]; then
  echo "    ✗ scripts/ に見つかりません:$MISSING"
  echo "      リポジトリが正しくcloneされているか確認してください。"
  exit 1
fi
echo "    scripts/ を使用: $SCRIPTS"

echo "=== [6/6] 動作確認 ==="
python3 "$SCRIPTS/shogi_engine.py"

# 詰将棋エンジンは「ファイルがある」だけでは不十分。
# 通常ビルドは go mate を解釈せず通常探索にフォールバックし、
# 連続王手でない強制勝ちまで詰みとして返してしまうため、
# 実際に1手詰めを解かせて checkmate 応答が返ることを確認する。
if ! PYTHONPATH="$SCRIPTS" python3 - <<'PYCHK'
import sys
try:
    from shogi_engine import Engine
    e = Engine(mate=True)
    # 1手詰めの局面（▲1一に金を打てば詰み）を解かせる
    # ５一玉・５三金・先手持駒金 → ５二金打で1手詰め（python-shogiで検証済み）
    n, best = e.mate_search([], movetime_ms=3000,
                            sfen="4k4/9/4G4/9/9/9/9/9/4K4 b G 1")
    e.quit()
    if n is None:
        print("    ✗ 詰将棋エンジンが詰みを検出できません（指標が使えません）")
        sys.exit(1)
    print(f"    詰将棋エンジン: OK（{n}手詰めを検出）")
except Exception as ex:
    print(f"    ✗ 詰将棋エンジンの動作確認に失敗: {ex}")
    sys.exit(1)
PYCHK
then
  echo ""
  echo "  ※ 詰将棋エンジンが正しく動いていません。"
  echo "     連続王手の詰み判定（詰み逃し・遠回りの詰み）は使えない状態です。"
  echo "     rm -rf $MATE_DIR してから再実行してください。"
  exit 1
fi

echo ""
echo "セットアップ完了。"
echo "  解析は深さ16でスクリーニングし、疑わしい局面を深さ20で再確認する（既定値）。"
echo ""
echo "  棋譜解析      : python3 scripts/analyze.py kifu/gNN.kif"
echo "  指標の集計    : cd docs && python3 ../scripts/metrics.py ../kifu/gNN.kif --name <自分の対局者名>"
echo "  悪手の再確認  : python3 scripts/recheck.py kifu/gNN.kif 20 \"38,52,58\""
echo "  推奨手の確認  : python3 scripts/best_moves.py kifu/gNN.kif 20 \"37,51,63\""
echo "  変化の比較    : python3 scripts/compare.py \"<sfen>\" 20 \"P*4d\" \"P*2d\""
echo ""
echo "  ※ いずれもリポジトリ直下($REPO)から実行する。"
echo "     metrics.py だけは docs/ から実行すること（出力がcwdに作られるため）。"
