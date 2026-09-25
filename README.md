# shogi_with_AI

将棋の棋譜解析スクリプト集（YaneuraOu + Háo）。
棋譜データはリポジトリに含まない。解析時は `docs/` と `kifu/` にデータを置いて使う
（どちらも `.gitignore` 済みなので誤ってcommitされない）。

## AIへ：最初に必ず行うこと

このリポジトリで作業するAIは、作業を始める前に **`CLAUDE.md` の「セッション開始時に必ず行うこと」を実行する**。
要点：Knowledgeに `ユーザープロファイル.md` がなければ初回としてヒアリングし、結果をKnowledgeに保存する。
あれば、本人から依頼がない限り再ヒアリングしない。

## 構成

- `scripts/` — 解析スクリプト一式
  - `shogi_setup.sh` — 環境構築（YaneuraOu v9.40 + Háo評価関数のビルド、詰将棋専用エンジンのビルドと動作確認）
  - `metrics.py` — 棋譜から各種指標を集計（悪手・大駒停滞・長考の質・詰み逃し等）
  - `king_track.py` — 中段玉・入玉圏の出現、戦型・囲いを集計
  - `game_classify.py` — 戦型(居飛車/振り飛車)・囲いの簡易判定
  - `analyze.py` / `best_moves.py` / `compare.py` — 個別局面の解析・比較
  - `shogi_engine.py` — YaneuraOu(USI)の薄いラッパー
  - `shogiou_conv.py` — 将皇形式棋譜のUSI変換
  - `ja_notation.py` — USI手 → 日本語表記変換

- `profile/` — AIと進めるための設定
  - `ユーザープロファイル.md` — 最初にAIがヒアリングする項目（実力・目標・取り組みペース）と記入形式。記入済みのものはKnowledgeに保存し、リポジトリには置かない
  - `AIキャラ設定.md` — 振り返りの相手をするAIの役割・話し方・分析の姿勢

解析時に置くデータ（リポジトリには含まない）:

- `kifu/` — KIF形式の対局棋譜（`kifu/com/` はCOM戦）
- `docs/` — 集計結果のCSV等。CSVは再実行時に該当行を上書きする

## 使い方

```bash
git clone https://github.com/hassan83/shogi_with_AI.git
cd shogi_with_AI

cd scripts && bash shogi_setup.sh && cd ..      # 環境構築（scripts/ の中から実行）
cd docs && python3 ../scripts/metrics.py ../kifu/g01.kif --name <自分の対局者名> && cd ..   # 指標集計（docs/ から実行）
python3 scripts/analyze.py kifu/g01.kif        # 1局解析（リポジトリ直下から）
```

## 指標の見方

`docs/対局指標.csv` に対局ごとの集計が累積される。主な列:
- `n_bad` — 悪手数（差分-300以下）
- `n_missed_mate` / `missed_mate_lengths` — 詰み逃し（詰まさなかった）の回数と手数
- `n_slow_mate` — 遠回りの詰み（詰ませたが最短ではなかった）の回数
- `long_good_rate` / `short_good_rate` — 長考/短考時の好手率
- `max_stall_piece` / `max_stall_moves` — 優勢時に最も長く停滞した大駒

## バージョン

現在のバージョンは `VERSION` に記載（[セマンティックバージョニング](https://semver.org/lang/ja/)）。
変更内容は `CHANGELOG.md`、各版のダウンロードは [Releases](https://github.com/hassan83/shogi_with_AI/releases) を参照。

### リリース手順

1. `CHANGELOG.md` に新しいバージョンの節（`## [X.Y.Z] - YYYY-MM-DD`）を追加する
2. `VERSION` を同じ番号に更新する
3. commit して main に push する
4. GitHub の Actions タブ →「Release」→「Run workflow」（main）を実行する

ワークフロー（`.github/workflows/release.yml`）が `VERSION` の番号で `vX.Y.Z` タグを作り、
`CHANGELOG.md` の該当節を本文にした Release を作成する。
手元から `git tag vX.Y.Z && git push origin vX.Y.Z` でタグをpushしても同じ Release が作られる
（タグと `VERSION` が一致しない場合は失敗する）。
