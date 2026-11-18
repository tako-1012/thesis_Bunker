# 038 点群地図の更新時間

## 実装

- 基準コミット（取得時の `realtime-map`）は `9b3b1efb89ffb9ab1b5982b062bc20821444237f`。
- 計測・テスト対象の実装コミットは `484ef5758b658b2b4f9777efb3be73cc5019e5ed`。計測・報告の記録はその直後のコミットに収録。
- `conference/tapp/pointcloud_map_fine.py` は、走査の順序を保って粗いマスごとの履歴の末尾を組み立て、中央値と細かいマスの障害物候補をまとめて計算する。新しい障害物の近傍でのみ膨張と粗いマスへの反映を行う。標高の変化がある範囲で勾配とガウス平滑化を更新する。
- `conference/tapp/pointcloud_map_multi.py` は、`prior` と `local` で同じ出所履歴を使い、新規障害物の ID から検出履歴を作る。通常の `prior` では登録した座標と事前地図の補間結果を共有する。履歴の標高には従来の仮想センサーを通した丸めを適用する。
- `conference/tapp/local_ground.py` の `update_local` は、平面あてはめと判定の後に Fine と同じ地図更新を呼ぶ。
- `conference/tests/test_map_speed.py` と `conference/results/map_speed/expected.json` を追加した。期待値は基準版で生成した更新ごとの SHA-256。標高・観測済みマス・通行可否・細粒度の障害物と膨張マスク、粗い障害物マスク、`tm` の全配列、点・細粒度 ID・センサー出所の履歴、検出記録を比較する。
- `conference/results/map_speed/` に `benchmark.py`、`timing.csv`、`timing_log.txt`、この `REPORT_ja.md` を追加した。
- 粗さの移動平均は、入力値の変化を通過した後も逐次加算の丸めが残る。軸 0 は影響列を始端から終端まで再計算し、軸 1 は影響する可能性がある行を全幅で計算する。走査途中に地図を読む処理に対しては、従来のロックで地図を一括公開し、更新前の地図を参照している側の配列を書き換えない。粗さの中間結果として粗い地図と同サイズの float64 配列を 3 枚保持する。

## 計測条件

AMD EPYC 9V74 80-Core Processor の Codex クラウド。Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0。BLAS は 1 スレッド。401×401 マスの事前地図を使用し、LiDAR は 28,800 点、カメラは各 26,750 点の合成入力とした。各条件で 6 更新を続け、履歴を初期化してこれを 6 回繰り返した。各更新で高さを変えた。全条件で入力点数と受理点数は同じ。初期化時間は集計外。時間は `perf_counter` で測り、テストの合否には使っていない。

計測段は実装の処理境界に合わせた。変更後の `history_and_detection` には点のグループ分けを含む。変更前の `source_history` には細粒度マスクのコピーを、`attribution_and_misc` には細粒度地図からの新規セル抽出を、変更後の `prior_lookup_attribution_and_misc` には共有した事前地図の補間を含む。段ごとの分位点は個別に集計した。

以下の各行は中央値／95% 値／最大（ms）。該当する計測段がない欄は「—」。集計スクリプトの標準出力は `timing_log.txt` に収録した。

### PointCloudMapFine / all_returns / lidar（28800 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `fine_registration` | 3.882 / 4.301 / 4.492 | 1.498 / 2.124 / 3.499 |
| `fine_binning_and_result` | — | 0.425 / 0.598 / 0.627 |
| `copies` | 0.063 / 0.087 / 0.322 | — |
| `prior_lookup_and_grouping` | 1.696 / 1.954 / 1.999 | — |
| `history_and_detection` | 138.868 / 144.283 / 145.824 | 11.539 / 17.136 / 17.996 |
| `fine_inflation` | 0.005 / 12.215 / 12.508 | 0.003 / 0.304 / 0.372 |
| `traversability` | 6.389 / 7.212 / 9.507 | — |
| `steep_inflation_and_publish` | 1.316 / 1.430 / 1.590 | — |
| `traversability_and_publish` | — | 2.875 / 3.930 / 5.429 |
| `result` | 0.058 / 0.078 / 0.093 | — |
| `total` | 154.993 / 165.793 / 168.800 | 16.556 / 23.960 / 25.374 |

### PointCloudMapFine / non_obstacle / lidar（28800 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `fine_registration` | 3.724 / 4.005 / 4.158 | 1.487 / 1.809 / 2.317 |
| `fine_binning_and_result` | — | 0.422 / 0.463 / 0.513 |
| `copies` | 0.066 / 0.083 / 0.113 | — |
| `prior_lookup_and_grouping` | 1.694 / 1.902 / 1.958 | — |
| `history_and_detection` | 144.353 / 151.337 / 154.688 | 12.663 / 15.006 / 15.895 |
| `fine_inflation` | 0.005 / 11.601 / 11.715 | 0.003 / 0.248 / 0.293 |
| `traversability` | 6.260 / 7.088 / 8.261 | — |
| `steep_inflation_and_publish` | 1.315 / 1.479 / 1.528 | — |
| `traversability_and_publish` | — | 2.714 / 3.708 / 6.237 |
| `result` | 0.057 / 0.073 / 0.233 | — |
| `total` | 162.127 / 171.523 / 173.683 | 17.431 / 20.570 / 21.037 |

### PointCloudMapMulti / all_returns / lidar（28800 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.619 / 4.096 / 4.295 | 1.686 / 1.798 / 3.223 |
| `source_history` | 22.388 / 24.059 / 24.343 | 3.025 / 3.862 / 3.964 |
| `fine_registration` | 3.716 / 4.222 / 4.843 | — |
| `fine_binning_and_result` | — | 0.436 / 0.475 / 0.507 |
| `copies` | 0.088 / 0.112 / 0.115 | — |
| `prior_lookup_and_grouping` | 1.643 / 2.014 / 2.120 | — |
| `history_and_detection` | 134.523 / 147.775 / 157.156 | 10.715 / 13.646 / 14.431 |
| `fine_inflation` | 0.006 / 11.802 / 12.059 | 0.003 / 0.254 / 0.272 |
| `traversability` | 6.196 / 6.942 / 7.186 | — |
| `steep_inflation_and_publish` | 1.317 / 1.505 / 1.621 | — |
| `traversability_and_publish` | — | 2.669 / 3.085 / 3.157 |
| `result` | 0.056 / 0.075 / 0.092 | — |
| `attribution_and_misc` | 8.719 / 10.312 / 10.843 | — |
| `prior_lookup_attribution_and_misc` | — | 1.072 / 1.267 / 1.277 |
| `total` | 188.388 / 204.927 / 209.401 | 20.248 / 22.869 / 24.415 |

### PointCloudMapMulti / all_returns / camera1（26750 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.505 / 4.052 / 5.728 | 1.610 / 1.719 / 1.763 |
| `source_history` | 1.613 / 1.949 / 2.333 | 0.762 / 0.798 / 0.808 |
| `fine_registration` | 3.443 / 3.893 / 4.123 | — |
| `fine_binning_and_result` | — | 0.375 / 0.417 / 0.435 |
| `copies` | 0.091 / 0.109 / 0.114 | — |
| `prior_lookup_and_grouping` | 1.302 / 1.458 / 1.525 | — |
| `history_and_detection` | 2.919 / 3.291 / 3.554 | 0.908 / 0.962 / 0.991 |
| `fine_inflation` | 0.003 / 11.775 / 13.131 | 0.001 / 0.207 / 0.294 |
| `traversability` | 5.974 / 6.802 / 7.090 | — |
| `steep_inflation_and_publish` | 1.277 / 1.499 / 1.636 | — |
| `traversability_and_publish` | — | 1.704 / 2.087 / 2.765 |
| `result` | 0.054 / 0.081 / 0.442 | — |
| `attribution_and_misc` | 8.487 / 9.761 / 10.483 | — |
| `prior_lookup_attribution_and_misc` | — | 0.921 / 1.041 / 1.073 |
| `total` | 29.346 / 42.624 / 44.521 | 6.299 / 6.994 / 7.439 |

### PointCloudMapMulti / all_returns / camera2（26750 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.501 / 4.076 / 6.598 | 1.602 / 1.747 / 2.048 |
| `source_history` | 1.652 / 2.668 / 3.571 | 0.773 / 0.801 / 0.849 |
| `fine_registration` | 3.362 / 4.160 / 5.227 | — |
| `fine_binning_and_result` | — | 0.384 / 0.482 / 0.494 |
| `copies` | 0.094 / 0.134 / 0.182 | — |
| `prior_lookup_and_grouping` | 1.358 / 1.546 / 3.758 | — |
| `history_and_detection` | 2.967 / 3.597 / 5.097 | 0.981 / 1.105 / 1.249 |
| `fine_inflation` | 0.003 / 12.957 / 17.828 | 0.001 / 0.220 / 0.248 |
| `traversability` | 6.178 / 8.881 / 11.329 | — |
| `steep_inflation_and_publish` | 1.294 / 1.461 / 3.273 | — |
| `traversability_and_publish` | — | 1.695 / 1.913 / 2.075 |
| `result` | 0.054 / 0.059 / 0.071 | — |
| `attribution_and_misc` | 8.499 / 9.860 / 10.498 | — |
| `prior_lookup_attribution_and_misc` | — | 0.920 / 1.087 / 1.158 |
| `total` | 29.757 / 45.059 / 56.191 | 6.388 / 7.066 / 7.319 |

### PointCloudMapMulti / non_obstacle / lidar（28800 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.604 / 4.547 / 5.602 | 1.698 / 1.800 / 2.518 |
| `source_history` | 22.576 / 24.776 / 29.881 | 3.041 / 3.923 / 5.042 |
| `fine_registration` | 3.706 / 4.025 / 6.888 | — |
| `fine_binning_and_result` | — | 0.443 / 0.603 / 0.658 |
| `copies` | 0.079 / 0.105 / 0.152 | — |
| `prior_lookup_and_grouping` | 1.682 / 1.814 / 5.648 | — |
| `history_and_detection` | 144.730 / 159.373 / 161.683 | 11.531 / 14.245 / 16.839 |
| `fine_inflation` | 0.006 / 11.815 / 15.165 | 0.003 / 0.279 / 0.364 |
| `traversability` | 6.187 / 6.928 / 9.425 | — |
| `steep_inflation_and_publish` | 1.296 / 1.457 / 2.620 | — |
| `traversability_and_publish` | — | 2.762 / 3.851 / 5.056 |
| `result` | 0.055 / 0.101 / 0.116 | — |
| `attribution_and_misc` | 8.745 / 10.591 / 14.942 | — |
| `prior_lookup_attribution_and_misc` | — | 1.129 / 1.436 / 2.075 |
| `total` | 198.047 / 213.846 / 232.807 | 20.808 / 24.034 / 30.628 |

### PointCloudMapMulti / non_obstacle / camera1（26750 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.444 / 3.652 / 3.770 | 1.660 / 3.456 / 14.683 |
| `source_history` | 1.551 / 1.679 / 1.754 | 0.774 / 0.850 / 1.275 |
| `fine_registration` | 3.320 / 3.626 / 3.907 | — |
| `fine_binning_and_result` | — | 0.388 / 0.418 / 0.422 |
| `copies` | 0.086 / 0.106 / 0.114 | — |
| `prior_lookup_and_grouping` | 1.283 / 1.447 / 1.493 | — |
| `history_and_detection` | 3.101 / 3.606 / 3.704 | 0.960 / 1.068 / 1.103 |
| `fine_inflation` | 0.003 / 11.712 / 13.040 | 0.002 / 0.218 / 0.227 |
| `traversability` | 5.993 / 6.329 / 6.647 | — |
| `steep_inflation_and_publish` | 1.277 / 1.408 / 1.478 | — |
| `traversability_and_publish` | — | 1.834 / 2.499 / 2.517 |
| `result` | 0.053 / 0.072 / 0.084 | — |
| `attribution_and_misc` | 8.494 / 8.891 / 9.487 | — |
| `prior_lookup_attribution_and_misc` | — | 0.935 / 1.110 / 1.627 |
| `total` | 29.113 / 41.031 / 41.827 | 6.670 / 9.066 / 19.687 |

### PointCloudMapMulti / non_obstacle / camera2（26750 点）

| 計測段 | 変更前 | 変更後 |
|---|---:|---:|
| `multi_registration` | 3.454 / 3.836 / 3.949 | 1.659 / 2.404 / 2.515 |
| `source_history` | 1.585 / 1.734 / 1.772 | 0.790 / 1.053 / 1.112 |
| `fine_registration` | 3.333 / 3.627 / 3.786 | — |
| `fine_binning_and_result` | — | 0.384 / 0.632 / 1.427 |
| `copies` | 0.089 / 0.128 / 0.148 | — |
| `prior_lookup_and_grouping` | 1.340 / 1.523 / 1.762 | — |
| `history_and_detection` | 3.112 / 3.528 / 3.973 | 1.007 / 1.546 / 2.547 |
| `fine_inflation` | 0.003 / 11.495 / 11.987 | 0.001 / 0.223 / 0.327 |
| `traversability` | 5.992 / 6.399 / 9.648 | — |
| `steep_inflation_and_publish` | 1.277 / 1.485 / 1.584 | — |
| `traversability_and_publish` | — | 1.705 / 2.402 / 2.611 |
| `result` | 0.054 / 0.082 / 0.179 | — |
| `attribution_and_misc` | 8.543 / 9.047 / 9.836 | — |
| `prior_lookup_attribution_and_misc` | — | 0.930 / 1.737 / 1.999 |
| `total` | 29.139 / 40.876 / 43.955 | 6.636 / 9.875 / 10.607 |

## 実時間 1 倍の見込み

`PointCloudMapMulti` の `prior / all_returns` で LiDAR とカメラ 2 台を各 10 Hz とし、各センサーの 1 更新の時間に 10 を掛けて合計した。

| 見積もり | 変更前（秒／秒） | 変更後（秒／秒） |
|---|---:|---:|
| 中央値の和 | 2.475 | 0.329 |
| 95% 値の和 | 2.926 | 0.369 |
| 最大値の和 | 3.101 | 0.392 |

変更前の LiDAR では履歴・中央値・障害物候補の処理が最も重く、変更後も LiDAR の残り時間の中心はその処理だった。カメラでは通りやすさの更新・公開が変更後も最も重い計測段。クラウドの合成入力では、LiDAR 30 ms、カメラ 10 ms の各 95% 値目標を満たした。既定設定の 95% 値を足した場合は 1 秒当たり約 0.37 秒で、地図更新だけで見れば 1 倍に追いつく余地がある。各センサーの 95% 値の和は、同時負荷で測定した合計時間の 95% 値とは異なる。

## 未確認の範囲

- Gazebo と研究 PC は使用していない。実行時のキュー落ち、古い点群、計画・制御と同時に動かしたときの処理時間、実際の倍率は未計測。今回の合成ベンチマークはセンサーごとに計測したため、重なる更新の影響は 039 の走行確認に残る。
- 保存済み点群は B0b の Gazebo 記録を再利用した。LiDAR・カメラ 2 台の NPZ 計約 372 KiB。実機から収録した点群との比較は未実施。
- 合成点群と保存済み点群でバイト単位の一致を調べた。異なる NumPy・SciPy の組み合わせ、全地形・全入力での一致は実測していない。最大値にはばらつきがあり、例えば `non_obstacle` のカメラ 1 では 19.687 ms の更新があった。

## 実行したコマンド

```bash
git fetch origin realtime-map
git switch -c codex/038-map-speed FETCH_HEAD
python -m venv /tmp/venv038
/tmp/venv038/bin/pip install -r conference/requirements-venv.txt
(cd conference && OPENBLAS_NUM_THREADS=1 /tmp/venv038/bin/python -m tests.test_planners)
# 変更前／変更後をそれぞれの tapp で計測。スクリプトは両方の版で動作する。
(cd conference && OPENBLAS_NUM_THREADS=1 PYTHONPATH=. /tmp/venv038/bin/python results/map_speed/benchmark.py)
# 現在の作業ツリーから変更前を再計測する場合は基準版 tapp を先に検索。
mkdir -p /tmp/038-base
git archive 9b3b1efb89ffb9ab1b5982b062bc20821444237f conference/tapp | tar -x -C /tmp/038-base
OPENBLAS_NUM_THREADS=1 PYTHONPATH=/tmp/038-base/conference:conference /tmp/venv038/bin/python conference/results/map_speed/benchmark.py
# 期待値は基準版で生成。通常のテストは保存した期待値を読む。
OPENBLAS_NUM_THREADS=1 PYTHONPATH=/tmp/038-base/conference:conference /tmp/venv038/bin/python -c 'import json; from tests.test_map_speed import replay, digest; print(json.dumps({name: digest(mapper) for name, mapper in replay()}, indent=2))'
cd conference
export MPLCONFIGDIR=/tmp/038-mpl OPENBLAS_NUM_THREADS=1 XDG_CACHE_HOME=/tmp/038-cache
for path in tests/test_*.py; do
    name="${path##*/}"
    /tmp/venv038/bin/python -m "tests.${name%.py}"
done
# 実装と報告を別コミットに収録し、作業用ブランチを push。
git push -u origin codex/038-map-speed
```

## テスト出力全文

既存 32 本と新規 1 本の計 33 本が終了コード 0。標準出力と標準エラーを採取した。

### 変更前の `tests.test_planners`（終了コード 0）

```text
all planner tests passed
roll-aware tests passed
```

### `tests.test_beach_terrain`（終了コード 0）

```text
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
```

### `tests.test_collision`（終了コード 0）

```text
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
```

### `tests.test_dstar`（終了コード 0）

```text
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
```

### `tests.test_edge_margin`（終了コード 0）

```text
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)
```

### `tests.test_endpoint_component`（終了コード 0）

```text
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: only two corrected start_steep labels differ in replay; all other fields and four preparation variants unchanged
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
saved component contract: both start_steep cases clear ZERO cells, protect all raw masks, retry once and advance to the next stop
all task028b component tests passed (Python only; Gazebo not run)
```

### `tests.test_endpoint_policy`（終了コード 0）

```text
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).
```

### `tests.test_footprint`（終了コード 0）

```text
dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed
proximity: analytic line-circle lengths, overlapping unions and tangencies passed
requested LAS case: inflated planner reports no_path without moving endpoints
online: zero radius preserves exact task014 trajectory and planning count
rollover: strict +/-90deg threshold, first time/position and immutable fake records passed
statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)
Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed
comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)
three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)
all footprint and rollover tests passed
```

### `tests.test_geo`（終了コード 0）

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
zone VIII reference differences [latitude_deg, longitude_deg]:
-4.25145429972e-09 2.46816966865e-09
-4.06389943919e-09 -3.64556740351e-09
2.36028796508e-09 -3.05306002701e-10
2.78198797332e-10 -4.38916458734e-10
projection round-trip max error [m]: 7.10133463144e-09
geographic sidecars: 13 maps; source axes, coastline anchor, half-cell offset, round trips and NPZ hashes passed
Web APIs: geographic map conversions, unavailable-map response and unchanged legacy metadata/image passed
all geographic conversion tests passed
```

### `tests.test_ground_estimate`（終了コード 0）

```text
1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes
2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged
ground_estimate x y slope_deg steep box_lethal
all_returns 9 10 28.810793742973065 True True
all_returns 11 10 28.810793742973065 True True
all_returns 10 9 28.810793742973065 True True
all_returns 10 11 28.810793742973065 True True
non_obstacle 9 10 0.0 False True
non_obstacle 11 10 0.0 False True
non_obstacle 10 9 0.0 False True
non_obstacle 10 11 0.0 False True
3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume
4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used
5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells
configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected
all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)
```

### `tests.test_gz_compare`（終了コード 0）

```text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)
```

### `tests.test_gz_online_batch`（終了コード 0）

```text
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)
```

### `tests.test_lab_geometry`（終了コード 0）

```text
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite
```

### `tests.test_local_speed`（終了コード 0）

```text
Task036 preparation only: /tmp/tmpw89ard3r/ten
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
024 08OB86_00294 start=[52, 195] points=[[309, 113], [273, 232], [104, 176], [46, 121], [250, 270]] unchanged=False
024 08OB86_-0205 start=[49, 270] points=[[114, 102], [114, 214], [42, 179], [135, 255], [93, 197]] unchanged=True
024 08OB87_-0706 start=[50, 200] points=[[89, 197], [263, 259], [59, 119], [347, 145], [39, 236]] unchanged=False
024 08OB88_-1417 start=[70, 169] points=[[337, 140], [313, 165], [199, 151], [264, 194], [203, 229]] unchanged=True
024 08OB88_-0167 start=[38, 231] points=[[137, 294], [249, 150], [202, 281], [31, 208], [348, 149]] unchanged=True
024 08OB88_00332 start=[45, 228] points=[[142, 207], [38, 131], [203, 180], [136, 171], [70, 116]] unchanged=True
024 08OB88_01832 start=[36, 214] points=[[223, 254], [335, 247], [159, 229], [264, 180], [133, 240]] unchanged=False
024 08OB89_00152 start=[48, 341] points=[[296, 173], [183, 372], [207, 192], [328, 186], [193, 222]] unchanged=False
024 08OB89_-0347 start=[55, 326] points=[[294, 224], [164, 169], [213, 144], [195, 352], [264, 374]] unchanged=False
024 08OB89_-0847 start=[70, 146] points=[[269, 98], [75, 211], [227, 332], [281, 117], [350, 279]] unchanged=True
024 PASS: 10/10 archived waypoint lists, 5/5 unchanged scenarios, default manifest bytes and wrapper forwarding
032 slope=0 box=False shift=0: fine/coarse=(0, 0)
032 slope=0 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0: fine/coarse=(0, 0)
032 slope=0 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0: fine/coarse=(0, 0)
032 slope=20 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0: fine/coarse=(0, 0)
032 slope=20 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0.4: fine/coarse=(0, 0)
CPU AMD EPYC 9V74 80-Core Processor
fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff
synthetic lidar 28800 28800 12 3.307259 3.445282 0.110674 0.117836 0 0
synthetic camera1 26750 26750 12 4.456208 5.318249 0.018629 0.020025 0 0
saved_b0b lidar 28800 11741 1 1.233873 1.233873 0.038198 0.038198 1 1
saved_b0b camera1 26750 9604 1 1.885578 1.885578 0.027648 0.027648 0 0
saved_b0b camera2 26750 9242 1 2.082939 2.082939 0.031544 0.031544 0 0
all local speed tests passed
```

### `tests.test_map_speed`（終了コード 0）

```text
byte-identical replay: 88 update states
```

### `tests.test_mapfiles_sim`（終了コード 0）

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 lossless scenario round trips, float32+residual, NaN, all 23 files and all 17 legacy IDs passed
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
API: 40 maps, file metadata/PNG, five-point planning/simulation, 404/422, immediate 409 and guard recovery passed
all mapfiles/simulation tests passed
```

### `tests.test_mission`（終了コード 0）

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
maps: 5 synthetic + 12 validation, cache, PNG dimensions/orientation passed
parity: 5-point terrain order/cost/path and Euclidean order/physical legs passed
validation: outside, water, blocked, unreachable, counts, rounding, duplicate/invalid base passed
safety: synthetic/beach_gentle/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_steep/200/100, 5 points, terrain/euclid contact=0
safety: synthetic/beach_scarp/200/100, 5 points, terrain/euclid contact=0
safety: real/08OB87_-0206/200, 5 points, terrain/euclid contact=0
safety: real/08OB88_01332/200, 5 points, terrain/euclid contact=0
API: maps/info/PNG/plan/static, 404/422, responsive worker, immediate 409 and guard recovery passed
all mission tests passed
```

### `tests.test_natural_terrain`（終了コード 0）

```text
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
```

### `tests.test_online`（終了コード 0）

```text
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
```

### `tests.test_online_deadend`（終了コード 0）

```text
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed
```

### `tests.test_online_mission`（終了コード 0）

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
beach_gentle: no-prior/coarse exact trajectory and plan-count parity; contact=0
beach_steep: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB88_01332: no-prior/coarse exact trajectory and plan-count parity; contact=0
08OB87_-0206 stale five-point tour: online contact=0; fixed debris cells= 11
08OB88_01332 stale five-point tour: online contact=0; fixed debris cells= 18
08OB89_-1597 stale five-point tour: online contact=0; fixed debris cells= 6
async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed
follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run
maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed
all online-mission tests passed
```

### `tests.test_online_safety`（終了コード 0）

```text
1 PASS: implicit/explicit none match pre-change runtime command JSON, plans/diagnostic bytes, follower trajectory/mission bytes and manifests
2 PASS: LiDAR and perfect-radius joins exempt only the start cell; later lethal cells remain rejected
3 PASS: actual stuck_0847_C1_r2_t1345 fixture search and handoff
online_fixes search_success handoff path_points outside_start_lethal_cells start_lethal
none True False 0 0 True
v1 True True 5 0 True
4 PASS: consecutive join rejection terminates at exactly 10 simulation seconds; acceptance resets the interval
5 PASS: known free-to-lethal on remaining path triggers lethal_changed only in v1; off-path changes do not replan; pending changes reset on planning
6 PASS: +/-26deg roll/pitch and 0.8m deviation stop; 24/25deg and 0.7/0.75m do not; zero linear and angular speed
safety recovery PASS: stop invalidates old work, replans from measured position, accepts replacement, ignores stale status and ends on no-path
ROS adapter PASS: real callbacks publish zero/status, preserve the open run, relay the stop and resume on a replanned path
diagnostics/concurrency PASS: v1 records diagnostics without 028b relaxation; busy pre-stop work cannot hand off and recovery uses the latest pose
configuration PASS: v1 manifest/CLI and both ROS parameter commands; 028b unchanged and excluded from v1
all online-safety tests passed; requirement 7 is checked by the complete conference/tests run
```

### `tests.test_planners`（終了コード 0）

```text
all planner tests passed
roll-aware tests passed
```

### `tests.test_pointcloud_map`（終了コード 0）

```text
/workspace/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)
```

### `tests.test_pointcloud_map_fine`（終了コード 0）

```text
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)
```

### `tests.test_prior_free`（終了コード 0）

```text
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors
slope_deg box prior_shift_m reference false_positive_cells missed_cells
0.0 False 0.0 prior 0 0
0.0 False 0.0 local 0 0
0.0 False -0.4 prior 81 0
0.0 False -0.4 local 0 0
0.0 False 0.4 prior 0 0
0.0 False 0.4 local 0 0
0.0 True 0.0 prior 0 0
0.0 True 0.0 local 0 0
0.0 True -0.4 prior 80 0
0.0 True -0.4 local 0 0
0.0 True 0.4 prior 0 1
0.0 True 0.4 local 0 0
20.0 False 0.0 prior 0 0
20.0 False 0.0 local 0 0
20.0 False -0.4 prior 81 0
20.0 False -0.4 local 0 0
20.0 False 0.4 prior 0 0
20.0 False 0.4 local 0 0
20.0 True 0.0 prior 0 0
20.0 True 0.0 local 0 0
20.0 True -0.4 prior 80 0
20.0 True -0.4 local 0 0
20.0 True 0.4 prior 0 1
20.0 True 0.4 local 0 0
local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution
5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged
6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays
configuration PASS: factory/CLI/manifest/ROS command forwarding; invalid coarse/local rejected; Gazebo not started
all prior-free tests passed; requirement 7 is checked by the separate complete test-module run
```

### `tests.test_real_beach`（終了コード 0）

```text
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
all 60 patches satisfy sea-to-land orientation
08OB86_00294: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_-0205: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0706: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-1417: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0167: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00294: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB86_-0205: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0706: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-1417: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0167: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 0
all real-beach tests passed
```

### `tests.test_real_beach_las`（終了コード 0）

```text
data: all 60 LAS patches, 12/48 split, exact names/order/origin/axes, npts and sea-to-land orientation passed
quantized_0.1m_fraction: new_max 0.0035301084084904803 old_min 0.27882342564826246
defaults: implicit/explicit shizuoka_beach are bit-identical for the first 3 test patches
08OB86_00294: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_-0205: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB87_-0706: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-1417: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB88_-0167: LAS 100/200m clean/debris repeatability, masks and reachability passed
08OB86_00294: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB86_-0205: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB87_-0706: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-1417: exact offline and coarse R5 c10 safety, clean/debris contact=0
08OB88_-0167: exact offline and coarse R5 c10 safety, clean/debris contact=0
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed
```

### `tests.test_real_sensors`（終了コード 0）

```text
PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes
PASS real preset mounts, symmetry, unchanged LiDAR spec and camera FOV/ranges without intrinsics
A2 camera1: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
A2 camera2: image=214x125, horizontal_deg=87.000000000000, vertical_deg=57.999358468411, intrinsics=absent
PASS A2: three camera-free SDFs byte-identical; depth SDF/spec change only prescribed resolution and intrinsics
PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform
PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance
PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed
PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input
PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags
PASS A2 wrapper: unset flags preserve full legacy argv bytes; individual/both/empty supplied values forwarded (fake Docker only)
PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry
PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)
all real sensor tests passed (synthetic/geometry only; Gazebo not run)
```

### `tests.test_risk_prior`（終了コード 0）

```text
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
```

### `tests.test_ros2_gz`（終了コード 0）

```text
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed
packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed
follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 34.2 0.02959598405434589 0.3173397734180379 0
kinematic True 34.2 0.02959598405434589 0.3173397734180379 0
attitude actual_p95_deg map_p95_deg
roll 0.0 0.0
pitch 0.0 0.0
data_source synthetic_robot_sim
source completed elapsed_s deviation_mean_m deviation_max_m lethal_cells
recorded True 7.7 0.0 0.0 0
kinematic True 7.7 0.0 0.0 0
attitude actual_p95_deg map_p95_deg
roll 0.0 11.309932474020224
pitch 0.0 5.710593137499648
report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)
API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed
worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added
all ROS-free ROS2/Gazebo tests passed
```

### `tests.test_thesis_figures`（終了コード 0）

```text

T1
 debris    metric  n    A_median   TAS_median  delta_median              p         p_holm
  False mean_cost 48 0.110342949 0.0767774554 -0.0352167333 7.10542736e-15 5.68434189e-14
  False     climb 48  1.50126915  0.890802236  -0.410943017 7.10542736e-15 5.68434189e-14
  False  p95_roll 48  5.45746622     3.567633   -1.89097743 7.10542736e-15 5.68434189e-14
  False length_xy 48         NaN          NaN   -2.00026809   0.0276182014   0.0552364028
   True mean_cost 48 0.154226921 0.0855587032 -0.0582350381 7.10542736e-15 5.68434189e-14
   True     climb 48  2.07159806   1.30575231  -0.803948405 2.13162821e-14 6.39488462e-14
   True  p95_roll 48  6.86720155   3.63401103   -2.80093993 7.10542736e-15 5.68434189e-14
   True length_xy 48         NaN          NaN  -0.764154874    0.947340222    0.947340222

T2
 radius_m   mode  runs  completed  touching   dJ_median     dJ_p90  replans_median  plan_s_median  plan_s_p95  plan_s_max
        5  fixed    48         48        46   3.8297614 10.8951737               0   0.0943159025 0.513914058  1.09228056
        5 online    48         46         0   1.9542052 10.2738521             101   0.0464642375  0.28593965  1.26618145
       10  fixed    48         48        46   3.8297614 10.8951737               0   0.0960627685 0.506711613  1.25659096
       10 online    48         46         0 0.945069248  6.6029207            94.5   0.0510014495 0.292423272  1.32438343
       15  fixed    48         48        46   3.8297614 10.8951737               0    0.094235528 0.485409814  1.26557115
       15 online    48         47         0 0.688622405 5.29694595              85    0.057362561 0.305458798  1.76405173

T3
                                world         mode  completed  path_lethal_cells  elapsed_s  roll_p95_actual_deg  pitch_p95_actual_deg  roll_p95_map_deg  pitch_p95_map_deg
              file/flat_test_100m.npz offline tour       True                  0    249.412       8.05631294e-09        6.79662109e-10                 0                  0
    file/real_08OB87_-0206_200m_0.npz offline tour       True                  0      348.2           4.76005563            6.20167607        4.58473933         6.31735413
file/real_las_08OB87_-0206_200m_0.npz offline tour       True                  0    289.516           3.83941424            2.47900287        3.84957483         2.58651471
       real_las_08OB87_-0206 / debris        fixed      False                  0      96.15           4.54713144            5.69114628        5.33797683         6.55378208
       real_las_08OB87_-0206 / debris       online       True                  0     190.95           4.31378469            4.21973305        4.30333238         3.67841423
thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated
statistics: 48 paired beaches, size means, medians and archived contact counts verified
outputs: no excluded measurement columns or values; all thesis figure tests passed
```

### `tests.test_tour`（終了コード 0）

```text
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed
```

### `tests.test_visibility`（終了コード 0）

```text
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed
```
