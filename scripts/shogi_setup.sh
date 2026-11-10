#!/usr/bin/env bash
# ============================================================
#  将棋解析環境 セットアップスクリプト
#  YaneuraOu v9.40 + Háo(tanuki- halfkp_256x2-32-32) + python-shogi
#  （SHOGI_EVAL=tsuyoura11mini / tsuyoura11micro で つようら王11 + YaneuraOu 開発版）
#  使い方:  bash shogi_setup.sh
#           SHOGI_EVAL=tsuyoura11mini bash shogi_setup.sh
#  所要時間: 3〜6分程度（ビルドとダウンロードのため）
# ============================================================
set -e
# cd する前にスクリプト自身の場所を絶対パスで確定させる
SCRIPTS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPTS/.." && pwd)"
# エンジン・評価関数の置き場所（作業ディレクトリ）。決め方は shogi_engine.py と同じ：
#   1. 環境変数 SHOGI_WORK があればそこ
#   2. なければ /home/claude（claude.ai のコード実行環境）が存在すればそこ
#   3. どちらもなければ ~/.shogi_with_AI
if [ -n "${SHOGI_WORK:-}" ]; then WORK="$SHOGI_WORK"
elif [ -d /home/claude ]; then WORK=/home/claude
else WORK="$HOME/.shogi_with_AI"; fi
mkdir -p "$WORK"
WORK="$(cd "$WORK" && pwd)"
echo "作業ディレクトリ: $WORK"
cd "$WORK"

echo "=== [1/6] 依存パッケージ ==="
apt-get install -y p7zip-full >/dev/null 2>&1 || true
pip3 install python-shogi --break-system-packages >/dev/null 2>&1 || true

# 評価関数の選択。環境変数 SHOGI_EVAL で選ぶ（未設定なら hao）。
#   hao             : Háo（tanuki- halfkp_256x2-32-32 2023-05-08）+ YaneuraOu v9.40（従来どおり）
#   tsuyoura11mini  : つようら王11mini（MIT License）+ YaneuraOu 開発版（SFNN 対応）
#   tsuyoura11micro : つようら王11micro（MIT License）+ YaneuraOu 開発版（SFNN 対応）
# つようら王11 は SFNN（進行度つき）の評価関数で、v9.40 では読めない。
# 対応する YaneuraOu はまだタグが無いので、動作を確認した開発版のコミットに固定する。
# 評価関数を切り替えたら、もう一度 shogi_setup.sh を実行する（ビルドし直す）。
SHOGI_EVAL="${SHOGI_EVAL:-hao}"
YO_DEV_REV=5c8972db7f6a511a212bf2ed43ad2695802edd4a   # 2026-11-10 の master
case "$SHOGI_EVAL" in
  hao)
    YO_REV=v9.40
    EDITION=YANEURAOU_ENGINE_NNUE
    EVAL_LABEL="Háo" ;;
  tsuyoura11mini)
    YO_REV=$YO_DEV_REV
    EDITION=YANEURAOU_ENGINE_SFNN_ka2_4096_8_64_progress8
    EVAL_LABEL="つようら王11mini"
    EVAL_FILE=TuyouraOu11mini-SFNN_ka2_4096_8_64_progress8-epoch0010-20261003.7z
    EVAL_SHA256=bd5cd719e000ee3e8c4f158ecd7b56913655569fa73911bd95209f55bbb772ea ;;
  tsuyoura11micro)
    YO_REV=$YO_DEV_REV
    EDITION=YANEURAOU_ENGINE_SFNN_ka2_2048_8_64_progress8
    EVAL_LABEL="つようら王11micro"
    EVAL_FILE=TuyouraOu11micro-SFNN_ka2_2048_8_64_progress8-epoch0010-20261001.7z
    EVAL_SHA256=d1326e9a620c30d40ae553259dd0b6828d2f4e9fca3b6ab9440566579ab0e8c2 ;;
  *)
    echo "✗ SHOGI_EVAL=$SHOGI_EVAL は未対応です（hao / tsuyoura11mini / tsuyoura11micro）"
    exit 1 ;;
esac
echo "評価関数: $EVAL_LABEL（SHOGI_EVAL=$SHOGI_EVAL）"

# 7z アーカイブの展開。7z コマンドが無い環境（apt で p7zip-full が入らない
# claude.ai の Code タブなど）では pip で入る py7zr を使う
extract_7z() {  # extract_7z <アーカイブ> <展開先>
  if command -v 7z >/dev/null 2>&1; then
    7z x "$1" -o"$2" -y >/dev/null
  else
    echo "    7z コマンドが無いため py7zr で展開します"
    python3 -c "import py7zr" 2>/dev/null \
      || pip3 install py7zr --break-system-packages >/dev/null 2>&1 || true
    python3 "$SCRIPTS/extract_7z.py" "$1" "$2"
  fi
}

SRC="$WORK/YaneuraOu/source"
BUILD_ID="$YO_REV $EDITION"
# 以前の版で作った作業ディレクトリには目印が無い。中身は v9.40 + NNUE なので、そうみなす
if [ -x "$SRC/YaneuraOu-by-gcc" ] && [ ! -f "$SRC/.shogi_build" ]; then
  echo "v9.40 YANEURAOU_ENGINE_NNUE" > "$SRC/.shogi_build"
fi
CUR_BUILD="$(cat "$SRC/.shogi_build" 2>/dev/null || true)"

echo "=== [2/6] YaneuraOu ソース取得 ($YO_REV) ==="
if [ ! -d YaneuraOu ]; then
  git clone --depth 1 https://github.com/yaneurao/YaneuraOu.git >/dev/null 2>&1
  CUR_BUILD=""
fi
if [ "$CUR_BUILD" != "$BUILD_ID" ]; then
  cd YaneuraOu
  if [ "$YO_REV" = v9.40 ]; then git fetch --depth 1 origin tag v9.40 >/dev/null 2>&1
  else git fetch --depth 1 origin "$YO_REV" >/dev/null 2>&1; fi
  git -c advice.detachedHead=false checkout -q "$YO_REV" >/dev/null 2>&1
  cd "$WORK"
fi

echo "=== [3/6] CPU判定してビルド ==="
FLAGS=$(grep -m1 flags /proc/cpuinfo)
if echo "$FLAGS" | grep -q avx512_vnni; then TARGET=AVX512VNNI
elif echo "$FLAGS" | grep -q avx512f;    then TARGET=AVX512
elif echo "$FLAGS" | grep -q avx2;       then TARGET=AVX2
else TARGET=SSE42; fi
echo "    TARGET_CPU=$TARGET"
cd "$SRC"
if [ ! -x YaneuraOu-by-gcc ] || [ "$CUR_BUILD" != "$BUILD_ID" ]; then
  if [ -n "$CUR_BUILD" ]; then echo "    ビルドし直します（$CUR_BUILD → $BUILD_ID）"; fi
  make clean >/dev/null 2>&1 || true
  rm -f YaneuraOu-by-gcc
  # PYTHON は SFNN のアーキテクチャのヘッダを生成するのに使われる
  make -j"$(nproc)" YANEURAOU_EDITION=$EDITION \
       TARGET_CPU=$TARGET COMPILER=g++ PYTHON=python3 normal >/dev/null 2>&1
  echo "$BUILD_ID" > .shogi_build
fi

echo "=== [3b/6] 詰将棋専用エンジンのビルド ==="
# 通常の NNUE ビルドは "go mate" を解釈せず通常探索にフォールバックするため、
# 連続王手でない強制勝ちまで詰みとして拾ってしまう（2026/09/03に判明）。
# 連続王手の詰み判定には専用ビルドが必須。
MATE_DIR="$WORK/mate_build"
if [ -x "$MATE_DIR/YaneuraOu-by-gcc" ] && [ ! -f "$MATE_DIR/.shogi_build" ]; then
  echo "v9.40" > "$MATE_DIR/.shogi_build"
fi
if [ ! -x "$MATE_DIR/YaneuraOu-by-gcc" ] || [ "$(cat "$MATE_DIR/.shogi_build")" != "$YO_REV" ]; then
  rm -rf "$MATE_DIR"
  cp -r "$SRC" "$MATE_DIR"
  rm -f "$MATE_DIR/YaneuraOu-by-gcc" "$MATE_DIR/.shogi_build"
  ( cd "$MATE_DIR" && make clean >/dev/null 2>&1; \
    make -j"$(nproc)" YANEURAOU_EDITION=YANEURAOU_MATE_ENGINE \
       TARGET_CPU=$TARGET COMPILER=g++ PYTHON=python3 normal >/dev/null 2>&1 ) || true
  if [ -x "$MATE_DIR/YaneuraOu-by-gcc" ]; then echo "$YO_REV" > "$MATE_DIR/.shogi_build"; fi
fi
if [ -x "$MATE_DIR/YaneuraOu-by-gcc" ]; then
  echo "    詰将棋エンジン: OK"
else
  echo "    ✗ 詰将棋エンジンのビルドに失敗。詰み逃し指標は使えません"
fi

echo "=== [4/6] 評価関数 $EVAL_LABEL 取得 ==="
cd "$WORK"
EVAL_DIR="$SRC/eval"
mkdir -p "$EVAL_DIR"
if [ -f "$EVAL_DIR/nn.bin" ] && [ ! -f "$EVAL_DIR/.shogi_eval" ]; then
  echo "hao" > "$EVAL_DIR/.shogi_eval"   # 以前の版で入れた評価関数は Háo
fi
if [ ! -f "$EVAL_DIR/nn.bin" ] || [ "$(cat "$EVAL_DIR/.shogi_eval")" != "$SHOGI_EVAL" ]; then
  # 前の評価関数のファイルを残さない（eval_options.txt の FV_SCALE が別の評価関数に効いてしまう）
  rm -f "$EVAL_DIR/nn.bin" "$EVAL_DIR/progress.bin" "$EVAL_DIR/eval_options.txt" \
        "$EVAL_DIR/tag.json" "$EVAL_DIR/banner.png" "$EVAL_DIR/.shogi_eval"
  if [ "$SHOGI_EVAL" = hao ]; then
    URL="https://github.com/nodchip/tanuki-/releases/download/tanuki-.halfkp_256x2-32-32.2023-05-08/tanuki-.halfkp_256x2-32-32.2023-05-08.7z"
    curl -sL -o hao.7z "$URL"
    rm -rf hao_extracted && mkdir -p hao_extracted
    extract_7z hao.7z hao_extracted
    cp hao_extracted/eval/nn.bin "$EVAL_DIR/nn.bin"
  else
    # つようら王11：nn.bin・progress.bin・eval_options.txt（FV_SCALE 24）・tag.json・banner.png の5つ。
    # ダウンロードしたものが配布物と同じか SHA-256 で確かめてから展開する
    curl -sL -o "$EVAL_FILE" "https://storage.yaneu.com/yaneuraou/$EVAL_FILE"
    GOT="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$EVAL_FILE")"
    if [ "$GOT" != "$EVAL_SHA256" ]; then
      echo "    ✗ $EVAL_FILE の SHA-256 が一致しません（ダウンロードの失敗か、配布物が変わった可能性）"
      echo "      期待: $EVAL_SHA256"
      echo "      実際: $GOT"
      exit 1
    fi
    X="${SHOGI_EVAL}_extracted"
    rm -rf "$X" && mkdir -p "$X"
    extract_7z "$EVAL_FILE" "$X"
    for f in nn.bin progress.bin eval_options.txt tag.json banner.png; do
      if [ -f "$X/$f" ]; then cp "$X/$f" "$EVAL_DIR/$f"; fi
    done
  fi
  echo "$SHOGI_EVAL" > "$EVAL_DIR/.shogi_eval"
fi

echo "=== [5/6] 解析スクリプトの確認 ==="
# スクリプトはリポジトリの scripts/ が正本。
# 以前はこのファイル内にヒアドキュメントで実体を埋め込んでいたが、
# リポジトリ側を更新しても埋め込みが古いまま残り、
# 新しいセッションで古い metrics.py / shogi_engine.py を動かす事故が起きた。
# そのため生成をやめ、リポジトリのスクリプトをそのまま使う方式に変更した（2026/08/31）。
REQUIRED="extract_7z.py shogi_engine.py ja_notation.py shogiou_conv.py analyze.py best_moves.py compare.py game_classify.py king_track.py metrics.py"
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
echo "セットアップ完了。（評価関数: $EVAL_LABEL）"
echo "  解析は深さ16でスクリーニングし、疑わしい局面を深さ20で再確認する（既定値）。"
echo ""
echo "  棋譜解析      : python3 scripts/analyze.py kifu/gNN.kif"
echo "  指標の集計    : cd docs && python3 ../scripts/metrics.py ../kifu/gNN.kif --name <自分の対局者名>"
echo "  悪手の再確認  : python3 scripts/recheck.py kifu/gNN.kif 20 \"38,52,58\""
echo "  推奨手の確認  : python3 scripts/best_moves.py kifu/gNN.kif 20 \"37,51,63\""
echo "  変化の比較    : python3 scripts/compare.py \"<sfen>\" 20 \"P*4d\" \"P*2d\""
echo ""
echo "  ※ いずれもリポジトリ直下($REPO)から実行する。"
if [ -n "${SHOGI_WORK:-}" ]; then
  echo "     解析時も同じ SHOGI_WORK=$SHOGI_WORK を設定しておくこと（エンジンの場所の判定に使う）。"
fi
echo "     metrics.py だけは docs/ から実行すること（出力がcwdに作られるため）。"
