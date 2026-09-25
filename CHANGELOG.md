# 変更履歴

このプロジェクトの主な変更を記録する。
バージョン番号は [セマンティックバージョニング](https://semver.org/lang/ja/)（MAJOR.MINOR.PATCH）に従う。

- **MAJOR**：使い方が変わる変更（コマンドの引数・出力CSVの列・ファイル配置の変更など、既存の手順やデータがそのままでは使えなくなるもの）
- **MINOR**：後方互換のある機能追加（新しいスクリプト・指標・オプションなど）
- **PATCH**：不具合修正・文書の修正

## [Unreleased]

### 追加
- `導入マニュアル.md`：claude.ai のプロジェクトで使う手順と、手元の Linux で使う手順、困ったときの対処

### 変更
- エンジン・評価関数の作業ディレクトリを環境変数 `SHOGI_WORK` で変えられるようにした（`shogi_setup.sh`・`shogi_engine.py`）。
  未設定時は、`/home/claude` があればそこ（従来どおり）、なければ `~/.shogi_with_AI`

## [1.0.1] - 2026-09-25

一般公開に向けて、ライセンスと各種ポリシーを追加。

### 追加
- `LICENSE`：MIT License
- `PRIVACY.md`：プライバシーポリシー（本ソフトウェアは利用者の情報を収集・送信しない。環境構築時の通信先、claude.aiに保存する情報の扱い、対戦相手の情報の保護）
- `THIRD_PARTY_NOTICES.md`：環境構築で取得する YaneuraOu・評価関数・python-shogi などのライセンス
- `SECURITY.md`：脆弱性・秘密情報の混入の報告方法
- `CONTRIBUTING.md`：Issue・Pull Request の出し方（棋譜の対局者名を伏せる）

## [1.0.0] - 2026-09-25

最初の公開版。

### 追加
- 棋譜解析スクリプト一式（`scripts/`）：YaneuraOu v9.40 + Háo 評価関数による解析、指標集計（悪手・大駒停滞・長考の質・詰み逃し・遠回りの詰みなど）、詰将棋専用エンジンでの詰み判定
- `scripts/shogi_setup.sh`：環境構築と動作確認（詰将棋エンジンの1手詰め検出まで）
- `profile/ユーザープロファイル.md`：初回にAIがヒアリングする項目と、Knowledgeへの保存手順
- `profile/AIキャラ設定.md`：振り返りの相手をするAIの役割・話し方・分析の姿勢
- `CLAUDE.md`：セッション開始時に必ず行う手順（初回判定とヒアリング）
- バージョン管理：`VERSION`・`CHANGELOG.md`、Release を作る GitHub Actions ワークフロー

### 変更
- `metrics.py`：対局者名の既定値を削除し、`--name` を必須にした

### 修正
- `metrics.py`：`--name` の値が深さ（depth）の引数として解釈される不具合

[1.0.1]: https://github.com/hassan83/shogi_with_AI/releases/tag/v1.0.1
[1.0.0]: https://github.com/hassan83/shogi_with_AI/releases/tag/v1.0.0
