# 指示書 019：Gazebo（物理シミュレーター）で、本物の砂浜の TA*-S と A* の経路を走らせて比べる

> **状態：未着手**。最初に `AGENTS.md` と `conference/tasks/BATCH_RULES_ja.md` を読むこと。ブランチは `codex/019-gazebo-compare`。
> Codex の環境では Gazebo を動かせない可能性が高い。その場合は、スクリプトとテスト（ROS2 なし）まで作り、実行は Claude が Docker で行う。

## 背景
TA\*-S が A\* より急斜面・登り・横傾きを避けることは、地図の上の計算で示した（`results/real_beach_las/`）。
これを、物理のある Gazebo で BUNKER を実際に走らせても言えるかを確かめる。走らせ方は指示書012・014の確認スクリプトと同じにする。

## 作るもの
1. `conference/ros2_jazzy/gz_checks/compare_checks.py`（`checks.py`・`online_checks.py` と同じ作り）と、Docker で動かす `run_compare_checks.sh`
   （既定のイメージは `osrf/ros:jazzy-desktop-full` に pandas を足したもの。`gz_checks/Dockerfile` を使う。`THESIS_ROS_IMAGE` で変えられる）。
2. シナリオ：点群の砂浜の **`test` の最初の 6 か所**、200m、漂着物なし、シード 0。スタートとゴールは `build_real` のもの（指示書009と同じ、海岸線に沿った移動）。
   - world は、走らせるときに一時フォルダへ `data_prep/export_gazebo.py` の関数で作る（リポジトリには置かない。大きいため）。
   - 経路：`run_planner_exact` の A\* と TA\*-S（指示書009と同じ設定）。両方を同じ world・同じスタートで、`path_follower` で走らせる。
3. 記録と集計（`experiments/gz_run_report.py` の `analyze_run` を使う）：完走、所要時間、経路からのずれ、通れない場所に触れたマス、
   Gazebo で測った roll・pitch の 95% 値と最大、登った高さ（軌跡の z から）。走行ごとに、地図から計算した値（`tapp.metrics.evaluate`）も並べる。
   **エネルギーは集計しない。**
4. 集計スクリプト `conference/experiments/gz_compare_report.py`：6 か所 × 2 方法の表と、TA\*-S と A\* の差（対にした差の中央値）。
   6 か所しかないので**検定はしない**（傾向を見るだけと報告に書く）。図：各砂浜の 2 本の軌跡と、roll の時間変化。
5. 結果の置き場所：`conference/results/gazebo_compare/`（Claude が実行したあとに置く。Codex が実行できた場合は Codex が置く）。

## テスト：`conference/tests/test_gz_compare.py`（ROS2・Gazebo なしで動くこと）
1. シナリオの作り方：6 か所のスタート・ゴール・経路が、`build_real` と `run_planner_exact` を直接呼んだ結果と一致する。
2. 集計：`robot_sim.simulate` で作った偽の記録から `gz_compare_report.py` が表を作れ、値が `analyze_run` と一致する。
3. 出力にエネルギーの列がない。

## 報告：`conference/results/gazebo_compare/REPORT_ja.md`（Codex が実行できなかった場合は、スクリプトの使い方と「未実行」を書く）
