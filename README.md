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

- `tests/` — リリース前に必須の通しテスト（`setup_test.sh`）とテスト用棋譜（`fixtures/sample.kif`、実在しない対局）

解析時に置くデータ（リポジトリには含まない）:

- `kifu/` — KIF形式の対局棋譜（`kifu/com/` はCOM戦）
- `docs/` — 集計結果のCSV等。CSVは再実行時に該当行を上書きする

## 使い方

初めて使う場合は **[導入マニュアル](導入マニュアル.md)** を参照（claude.ai のプロジェクトで使う手順と、手元の Linux で使う手順）。

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

**リリース前に、環境構築〜解析の通しテストが全部成功していることが必須。**
テストは `tests/setup_test.sh` で、GitHub Actions（`.github/workflows/test.yml`）が次の3パターンで実行する。

| パターン | 期待する作業ディレクトリ |
|---|---|
| `SHOGI_WORK` を設定 | 設定した場所 |
| 未設定・`/home/claude` あり（claude.ai と同じ） | `/home/claude` |
| 未設定・`/home/claude` なし（一般の Linux と同じ） | `~/.shogi_with_AI` |

各パターンで、環境構築の完了・エンジンと評価関数の配置・詰将棋エンジンの1手詰め検出・
テスト用棋譜（`tests/fixtures/sample.kif`、実在しない対局）での `metrics.py`／`analyze.py` の実行を確認する。

1. `CHANGELOG.md` の `## [Unreleased]` を `## [X.Y.Z] - YYYY-MM-DD` に置き換える
2. `VERSION` を同じ番号に更新する
3. commit して main に push する（push で Test ワークフローが自動実行される）
4. GitHub の Actions タブ →「Release」→「Run workflow」（main）を実行する

Release ワークフロー（`.github/workflows/release.yml`）は、**まず Test ワークフローの3パターンを実行し、
全部成功したときだけ** `VERSION` の番号で `vX.Y.Z` タグと Release を作る（本文は `CHANGELOG.md` の該当節）。
1つでも失敗した場合は Release は作られない。原因を直してからやり直すこと。

- GitHub の画面から手動で Release を作ったり、タグを直接作ったりしない（テストを通らずに公開されてしまうため）
- 手元でテストする場合：`bash tests/setup_test.sh <期待する作業ディレクトリ>`（例：`bash tests/setup_test.sh ~/.shogi_with_AI`）

## ライセンス・ポリシー

- ライセンス：[MIT License](LICENSE)
- 環境構築で取得する YaneuraOu・評価関数・python-shogi は別ライセンス：[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)
- プライバシーポリシー：[PRIVACY.md](PRIVACY.md)（本ソフトウェアは利用者の情報を収集・送信しない）
- セキュリティ上の報告：[SECURITY.md](SECURITY.md)
- 不具合報告・Pull Request：[CONTRIBUTING.md](CONTRIBUTING.md)（棋譜を貼るときは対局者名を伏せる）

本ソフトウェアは無保証で提供される。解析結果はエンジンの評価に基づく参考情報であり、その正確性は保証しない。
