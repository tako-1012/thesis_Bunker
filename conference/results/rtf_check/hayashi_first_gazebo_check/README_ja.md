# 研究 PC「hayashi」での最初の Gazebo 確認（3 か所、fine 地図）

`conference/RESEARCH_PC_ja.md` の「まだ確かめていないこと」に対応する、研究 PC での最初のミッション走行。
研究の新しい比較ではなく、クラウドの Docker の結果と同じ動きになるかを確かめるためのもの。

## シナリオ
- 既存の手順：`ros2_jazzy/gz_checks/run_lidar_checks.sh <保存先> --patch-count 3 --map fine`
- 砂浜：`shizuoka_beach_las` の test の先頭 3 か所（`08OB86_00294`、`08OB86_-0205`、`08OB87_-0706`）。TA*-S+inflate、LiDAR
- 設定：コードの固定値のまま（実時間の 0.3 倍、途切れの基準 1.0 秒、ソフトウェア描画、Docker `thesis/jazzy-gz:1`）。
  `--patch-count` の選択肢は 3 と 10 だけなので、コードを変えない最小の規模として 3 か所を選んだ。
- 時間の上限：外側の `timeout` で 3 時間（10800 秒）。クラウドでの走行は 3 か所の合計で壁時計 約 65 分。

## 成功条件（走らせる前に決めたもの）
1. **実行の成立**：終了コード 0、`manifest.json` の `execution` が `finished`、3 件とも `error` が空。
2. **クラウドとの一致**：`results/lidar_fine/physical_10/` の同じ 3 か所はいずれも `completed`。研究 PC でも 3 件とも `completed` なら一致とする。
   終わり方だけでなく、シミュレーション時間の差も記録する。一致しなくても設定は変えず、そのまま報告する。

## 比較の前に知っておくこと
- 参照の結果は Gazebo 8.11.0。研究 PC のイメージの版は `physical_3/manifest.json` に残る（ベースイメージの版を固定していないため、違う可能性がある）。
- `--map fine` は 023 の設定を固定しているので、GPU 描画や実時間の 1 倍は試していない。
- 3 か所 1 回ずつの結果であり、統計的な比較ではない。

## ファイル
- `image_build/`：イメージのビルドのスクリプト・ログ・終了コード
- `run_check.sh`：実行スクリプト。`run_conditions.txt`：コミット・環境・コマンド
- `console.log`、`exit_code.txt`：実行のログと終了コード
- `physical_3/`：`manifest.json`、`raw/`、集計（既存の実験スクリプトが作る）

## 結果（2026-11-07、コミット f1bda2c、イメージ e1cbc1bb388d、Gazebo 8.11.0）
| 砂浜 | 研究 PC | クラウド（023） | シミュレーション時間（研究 PC／クラウド） |
|---|---|---|---|
| 08OB86_00294 | completed | completed | 467.44 秒／463.75 秒 |
| 08OB86_-0205 | completed | completed | 242.19 秒／239.75 秒 |
| 08OB87_-0706 | **no_path** | completed | 95.89 秒で停止／457.67 秒 |

- 条件 1（実行の成立）：満たした。終了コード 0、`execution` は `finished`、`error` は 3 件とも空。既存の集計も成功。
- 条件 2（クラウドとの一致）：**満たしていない**（3 件中 2 件）。`08OB87_-0706` は (76.9, 71.0) 付近、シミュレーション時刻 101.05 秒に、71 回目の計画が失敗した。原因は未解明。
- 実測倍率は 3 件とも 0.300。`queue_drops` は 0、受信数と地図更新数は同じ。
- 図：`tracks_hayashi_vs_cloud.png`（保存済みの軌跡をそのまま描いたもの）。
