`codex/022-gazebo-lidar` はpush済み。実装コミットは `ce2790e04f9ed85062fc84b9b78514a12cb89867`。
マージは行っていない。報告の追記はこのコミットの後に保存する。

`realtime-map` 向けのPR作成を試みたが、GraphQLとRESTの両方が `Forbidden` で拒否されたため、PRは作成していない。
実際の出力は `verification/pr_create_log.txt` と `verification/pr_rest_log.txt` に保存した。
共通ルールの代替手順に従い、全テスト出力・集計表・仮定・未実行事項を含む本文を `PR_DESCRIPTION_ja.md` に保存した。

通常Docker用の標準イメージがないため、LiDARの3か所・10か所でのGazebo実走は未実行。
点群処理とROS2不要の検証、通常Dockerでの実行・集計スクリプトまでを提出する。
