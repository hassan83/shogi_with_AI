# コントリビューションガイド

不具合報告・改善提案・Pull Request を歓迎する。

## 報告・提案（Issue）

- 不具合報告には、実行したコマンド、エラーメッセージ全文、環境（OS・Python のバージョン・CPU）を書く
- **棋譜や集計結果を貼るときは、対局者名を伏せる**（例：`先手：自分` `後手：相手`）。
  対戦相手のハンドル名は第三者の情報なので、公開の場に載せない（[PRIVACY.md](PRIVACY.md)）
- 脆弱性や秘密情報の混入は Issue に書かず、[SECURITY.md](SECURITY.md) の方法で報告する

## Pull Request

- `kifu/`・`docs/`・記入済みのユーザープロファイルなど、個人の対局データを含めない
- 利用者に見える変更は `CHANGELOG.md` の `## [Unreleased]` の節に追記する
- `scripts/shogi_setup.sh` で環境構築し、変更したスクリプトが動くことを確認してから出す
- Pull Request では GitHub Actions の Test（環境構築〜解析の通しテスト3パターン）が自動で実行される。全部成功していることを確認する
- テスト用の棋譜は `tests/fixtures/` に置く。実在の対局・対局者名は使わない
- 投稿したコードは、本リポジトリの [MIT License](LICENSE) で公開されることに同意したものとする
