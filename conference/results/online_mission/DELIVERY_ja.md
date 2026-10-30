# 提出状況

作業ブランチ：`codex/online-replanning-ros2`。PRの対象：`realtime-map`。

実装・全Python実験・日本語報告を含むコミット `830adbb` を `origin/codex/online-replanning-ros2` へpushした。

```text
$ git push -u origin codex/online-replanning-ros2
To https://github.com/tako-1012/thesis_Bunker.git
 * [new branch]      codex/online-replanning-ros2 -> codex/online-replanning-ros2
branch 'codex/online-replanning-ros2' set up to track 'origin/codex/online-replanning-ros2'.
```

日本語報告全文（変更ファイル、テスト全文、集計表全文、制約を含む）を説明本文にしてdraft PRを作成しようとしたが、GitHub APIが拒否した。PRは作成されていない。

```text
$ gh pr create --draft --base realtime-map --head codex/online-replanning-ros2 --title '走行中の地図更新・再計画をROS2へ接続し古い地図での巡回を比較' --body-file /tmp/online-mission-pr-body.md
Post "https://api.github.com/graphql": Forbidden
exit code: 1
```

指示書014の代替手順として、push済みブランチと [REPORT_ja.md](REPORT_ja.md) を提出する。この提出状況の追記も追加コミットして同じブランチへpushする。

手動でPRを作る場合の比較リンク：
https://github.com/tako-1012/thesis_Bunker/compare/realtime-map...codex/online-replanning-ros2

既存LAS地図枚数テストの変更案は未適用。Gazeboの依存取得はプロキシ403で失敗したため物理測定値は未取得。
