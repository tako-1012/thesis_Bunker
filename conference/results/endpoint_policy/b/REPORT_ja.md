# 指示書028b：始点の連結成分による解除（完了条件未達）

**保存済み始点型2例で経路を見つける条件は未達。急斜面の保護条件と衝突している。テストを弱めず、失敗したまま記録した。**

実装・検証ログのコミットID：`3dbc7a8bf1f7c84512b6cbd078f268b949501b60`。この報告書は後続の文書コミットで追加する。

作業ブランチ：`codex/028b-start-component`。基点：`0009471845c506fbee9c3f5242163511ff5cf628`（作業開始時の最新realtime-map）。日付：2026-11-10（日本時間）。マージしない。

## 定義と実装

**この定義は test の砂浜の失敗を見たあとで決めた。** 保存済みの失敗を使う再現は独立した評価ではない。新しいGazeboの反復評価は今回実施していない。

- `tapp/endpoint_policy.py`：`escape_maps(snapshot, policy='escape')` に `escape_component` を追加。`lethal & ~(detected | prior_raw | steep)` のうち、始点セルを含む4近傍の成分だけを解除する。始点が生の障害物なら解除は0。始点が元から通行可能な場合も成分は作らない。
- 4近傍を明示した `binary_propagation` を使用する。通行可能セルや斜めだけの接触を経由して広げない。距離・面積・セル数の上限や新しい数値パラメータは加えていない。既存の0.5m解除は `escape` のまま。
- `ros2_jazzy/gz_checks/endpoint_runtime.py`：探索時と、最新地図での受け渡し時の両方で選択した方針を使う。代替終点・有限の再試行・停止・次地点への移行・診断・解除マスクの保存を両方式で利用する。
- `ros2_jazzy/gz_checks/lidar_checks.py`：`--endpoint-policy escape_component` を追加し、manifestとROSパラメータへ渡す。既定は `none`。
- `experiments/endpoint_replay.py`：`compare_replay()` と `--compare` を追加。3例×2定義の6行をJSON/CSV/表示ログに保存する。真値は計画後の監査だけで読み込む。引数なしの従来の3例の再現はそのまま。
- `tests/test_endpoint_component.py`：4近傍の独立BFSとの一致、禁止マスクの保護、コピーの不変性、合成地図での脱出と実際の非同期アダプターの受け渡し、代替終点・再試行・遅延した経路の拒否、旧出力のバイト一致を検証。保存例での要求された成功条件のassertionも残した。

既定のnoneランタイムは従来の `LidarOnlineMission` そのもの。既存の0.5m・1.0m・1.0秒、障害物判定・コスト式は変えない。
旧none/coarse、none/fine、escape、escape＋診断の準備出力を変更前のJSONバイトと比較し、実行機のPython/NumPy欄だけを合わせた上で一致した。
旧escapeによる3例の再現のJSONも、変更前に保存した全文と一致した。既存テストファイルは変更していない。

## 保存データで見つかった条件の衝突

既存の `saved_snapshot` は、保存済み推定DEMから `TraversabilityMap(...).steep` を作る。既存の `raw_mask` は検出障害物・事前の生マスク・この急斜面マスクのORである。
指定された始点型2例では、始点 `(154,142)` の `steep` がどちらもtrueだった。推定傾斜は下記の診断結果のとおりで、既存上限（診断の `max_slope_deg`）を超えている。
`detected` と `prior_raw` はfalseだが、急斜面そのものとして保護するマスクに含まれる。そのため、膨張のみの成分に始点は入らず、解除数は0になる。

同じセルは真値では通行可能だが、真値を使って計画用の急斜面判定を置き換えることはしていない。
現在のrawマスク定義を維持したまま、「急斜面を決して開けない」と「この2例で始点から経路を得る」を同時に満たすことはできない。
これは保存済みの最後の地図についての事実であり、実走の失敗瞬間も同じ急斜面だったと確定するものではない。

利用者に急斜面の扱いの確認を求めた。追加の急斜面解除やしきい値変更は行わず、依頼で明示された保護条件を維持している。
始点のrawラベルを書き換えたり、真値を計画へ渡したり、要求された成功assertionを削除・skip・xfailにしたりしていない。

診断は元ファイルのSHA-256を処理前後で照合した読み取り専用の処理である。傾斜はPythonで保存配列から計算した。

```text
[
  {
    "case": "results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706",
    "start": [
      154,
      142
    ],
    "pose": [
      76.88376807463277,
      71.02522261229389,
      1.1045702484245299,
      0.052334621166215636,
      0.05732322789624599,
      -0.03824034704554496
    ],
    "start_flags": {
      "lethal": true,
      "seen": true,
      "detected": false,
      "prior_raw": false,
      "steep": true
    },
    "estimated_slope_deg": 30.881264011006785,
    "max_slope_deg": 25.0,
    "truth_slope_deg": 3.8367825193935903,
    "truth_lethal": false,
    "source_sha256": {
      "results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706/pointcloud_map.npz": "e629598282432128a9211a821e9d6f402b47764efb433e207ad2356196745072",
      "results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706/evaluation_reference.npz": "2df6074987e91901af3746f92351a330a26faa00fe978d43f98693738c27f9ff",
      "results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706/mission.json": "c523ea47671c743a009ff60de35f7f1325cf1dc98b0f1aa6c8ebb8d7aeceb1fa"
    }
  },
  {
    "case": "results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706",
    "start": [
      154,
      142
    ],
    "pose": [
      76.89779640631312,
      71.00667463909443,
      1.1021476010414557,
      0.049752738653402205,
      0.05712842069278519,
      -0.05176698214392848
    ],
    "start_flags": {
      "lethal": true,
      "seen": true,
      "detected": false,
      "prior_raw": false,
      "steep": true
    },
    "estimated_slope_deg": 30.507702988076584,
    "max_slope_deg": 25.0,
    "truth_slope_deg": 3.8367825193935903,
    "truth_lethal": false,
    "source_sha256": {
      "results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706/pointcloud_map.npz": "babb938869c1ffc117e6b46350dbc2ece4d82bbdbcf90c232b6e61597bb69d39",
      "results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706/evaluation_reference.npz": "2df6074987e91901af3746f92351a330a26faa00fe978d43f98693738c27f9ff",
      "results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706/mission.json": "447c9fc7e7c6323afb36fca95a66b6d16702c12e41237f82d6d5239f218517e4"
    }
  }
]
```

## 3例×両定義の再現の表（表示をそのまま）

```text
Task028b: replay saved final maps with both start-clearance definitions; no Gazebo runs.
The component definition was chosen after inspecting failures on test beaches.
                                                                    case failure_class           policy    none  result     outcome       goal  relaxed_cells  relaxed_truth_lethal_cells  raw_cells_cleared  raw_path_cells
          results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706    start_cell           escape no_path no_path unreachable [347, 145]              1                           0                  0               0
          results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706    start_cell escape_component no_path no_path unreachable [347, 145]              0                           0                  0               0
results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706    start_cell           escape no_path no_path unreachable [347, 145]              1                           0                  0               0
results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706    start_cell escape_component no_path no_path unreachable [347, 145]              0                           0                  0               0
                         results/lidar_fine/physical_10/raw/08OB88_-1417     goal_cell           escape no_path    path      nearby [198, 151]              0                           0                  0               0
                         results/lidar_fine/physical_10/raw/08OB88_-1417     goal_cell escape_component no_path    path      nearby [198, 151]              0                           0                  0               0
```

解除マス数と、解除マス中の真値lethal数を別々に表示した。生の障害物の解除と、返された経路が生の障害物を通ったマス数は全行0。
失敗行の空の経路で0と出ることは、安全に走行・脱出した証拠ではない。始点型2例は両方とも未解決で、終点型1例では両方式で同じ仮の終点への経路が得られた。
この再現は最後の地図での計画であり、実走の地図更新や再試行を時間順に再生したものではない。有限の再試行と次地点への移行は合成地図のアダプターテストで確認した。

## 実行したコマンドとテスト出力の全文

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-028b-mpl XDG_CACHE_HOME=/tmp/thesis-028b-cache` を指定した。

```bash
cd conference
python3 -m tests.test_planners
python3 results/endpoint_policy/b/verification/capture_legacy.py  # 変更前に一度実行
python3 -m experiments.endpoint_replay --compare --output results/endpoint_policy/b
python3 -m tests.test_endpoint_component
python3 results/endpoint_policy/b/verification/diagnose_saved_starts.py
python3 results/endpoint_policy/b/verification/run_tests.py
python3 results/endpoint_policy/b/verification/run_tests.py --resume
python3 results/endpoint_policy/b/verification/refresh_replay.py
python3 results/endpoint_policy/b/verification/build_report.py --implementation-commit <上記ID>
```

全体のランナーは既知の新規テストの失敗を隠さず、独立した残りのモジュールも実行して全出力を集めた。終了コードは非0である。
最初のランナーは13モジュールのログを保存した後にプロセスが失われたため、ソースのSHA-256と既存の完了ログを照合し、`--resume` で未完了の残りを実行した。既知の非0終了もそのまま保持した。
全テスト実行後、静的再現の失敗の表示だけを `no_path` に直した。再現と、それに依存する新規テストを再実行し、全文ログを更新した。時間順の再試行を実施したように読める表示を避けるためで、計画・実行時の処理は変えていない。従来の `replay()` の出力はそのままである。

変更前のプランナー：

```text
all planner tests passed
roll-aware tests passed
```

```text
Captured legacy none/escape preparation bytes and three-case escape replay; Python only.
Original tracked conference files: 3713
```

対象テストの出力全文：

```text
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: original three-case escape replay and four preparation variants unchanged; new CLI choice/manifest accepted
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis-028b/conference/tests/test_endpoint_component.py", line 170, in <module>
    test_saved_component_contract()
  File "/workspace/thesis-028b/conference/tests/test_endpoint_component.py", line 161, in test_saved_component_contract
    assert not failed, ('Required saved-start paths conflict with immutable raw-start protection', failed)
           ^^^^^^^^^^
AssertionError: ('Required saved-start paths conflict with immutable raw-start protection', [{'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'start': [154, 142], 'raw_start': {'detected': False, 'prior_raw': False, 'steep': True}}, {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'start': [154, 142], 'raw_start': {'detected': False, 'prior_raw': False, 'steep': True}}])
```

全テストの出力全文：

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ python3 -m tests.test_endpoint_component
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: original three-case escape replay and four preparation variants unchanged; new CLI choice/manifest accepted
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis-028b/conference/tests/test_endpoint_component.py", line 170, in <module>
    test_saved_component_contract()
  File "/workspace/thesis-028b/conference/tests/test_endpoint_component.py", line 161, in test_saved_component_contract
    assert not failed, ('Required saved-start paths conflict with immutable raw-start protection', failed)
           ^^^^^^^^^^
AssertionError: ('Required saved-start paths conflict with immutable raw-start protection', [{'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'start': [154, 142], 'raw_start': {'detected': False, 'prior_raw': False, 'steep': True}}, {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'start': [154, 142], 'raw_start': {'detected': False, 'prior_raw': False, 'steep': True}}])

exit=1

$ python3 -m tests.test_endpoint_policy
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).

exit=0

$ python3 -m tests.test_footprint
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

exit=0

$ python3 -m tests.test_geo
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

exit=0

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ python3 -m tests.test_mapfiles_sim
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

exit=0

$ python3 -m tests.test_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

exit=0

$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ python3 -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ python3 -m tests.test_online_mission
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

exit=0

$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ python3 -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis-028b/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ python3 -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis-028b/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0

$ python3 -m tests.test_real_beach
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

exit=0

$ python3 -m tests.test_real_beach_las
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
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ python3 -m tests.test_real_sensors
PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes
PASS real preset mounts, symmetry, LiDAR unchanged beam/noise spec and camera FOV/ranges/intrinsics
PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform
PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance
PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed
PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input
PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags
PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry
PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)
all real sensor tests passed (synthetic/geometry only; Gazebo not run)

exit=0

$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ python3 -m tests.test_ros2_gz
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

exit=0

$ python3 -m tests.test_thesis_figures

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

exit=0

$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ python3 -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_endpoint_component exit=1
test_endpoint_policy exit=0
test_footprint exit=0
test_geo exit=0
test_gz_compare exit=0
test_gz_online_batch exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_deadend exit=0
test_online_mission exit=0
test_planners exit=0
test_pointcloud_map exit=0
test_pointcloud_map_fine exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_real_sensors exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

## 既存ファイルと実行環境

```json
{
  "original_files": 3713,
  "changed": [
    "conference/experiments/endpoint_replay.py",
    "conference/ros2_jazzy/gz_checks/endpoint_runtime.py",
    "conference/ros2_jazzy/gz_checks/lidar_checks.py",
    "conference/tapp/endpoint_policy.py"
  ],
  "unchanged_original_files": 3709,
  "existing_tests_unchanged": true,
  "old_results_maps_worlds_data_unchanged": true
}
```

```json
{
  "base": "0009471845c506fbee9c3f5242163511ff5cf628",
  "branch": "codex/028b-start-component",
  "client_date": "2026-11-10",
  "client_timezone": "Asia/Tokyo",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "numpy": "2.3.5",
  "scipy": "1.17.0",
  "platform": "Linux-6.18.57-x86_64-with-glibc2.41",
  "policy": "escape_component",
  "definition": "four-neighbour inflated-only component containing the start; exclude detected/prior_raw/steep; no new numeric threshold",
  "post_hoc": "この定義は test の砂浜の失敗を見たあとで決めた",
  "gazebo_executed": false,
  "docker_executed": false,
  "source_sha256": {
    "conference/experiments/endpoint_replay.py": "3405bf03d7fe480735cf658dfb595eb8d673a8417413cc3fec1da4c0a27e9c91",
    "conference/ros2_jazzy/gz_checks/endpoint_runtime.py": "385e4859c53f1c191e77853f2dc097d1526f625284c5684e6455568fe4d0028e",
    "conference/ros2_jazzy/gz_checks/lidar_checks.py": "2641cc740edc4f9fbe63375c622a254625a37afd6c8bbe58351ec5218e51aec7",
    "conference/tapp/endpoint_policy.py": "3d661425149027f56916943ea407ffe842c35a5d5ee16abae25501f44fdc4e22",
    "conference/tests/test_endpoint_component.py": "4ca0fea0dc3952e6186ce5c00af882abc7c84cbc5295f63cda5770478525c273"
  },
  "report_label_revision": {
    "reason": "Only compare_replay failure display changed to no_path; no runtime or planner change. Replay and its dependent test rerun after the complete suite.",
    "previous_replay_sha256": "3e23a4d4db865935efb7bc744f69e086812c8a4ce8cba4ee8bd03cb6429238d9",
    "final_replay_sha256": "3405bf03d7fe480735cf658dfb595eb8d673a8417413cc3fec1da4c0a27e9c91"
  }
}
```

## できなかったこと・次に確認が必要なこと

完了条件の「保存済み始点型2例の成功」と「全テスト成功」は未達。既存25モジュールは成功し、新規 `test_endpoint_component` の保存済み成功条件が1モジュール分失敗した。
合成地図の新しい解除・受け渡し・保護・旧出力の比較はその失敗より前にすべて成功している。
どのマスクを「急斜面そのもの」とするか、既存の推定DEM由来の定義と今回の期待が一致しているかを再確認する必要がある。

Gazebo・実際のDocker・研究PCでの実走は、指定どおり実行していない。走行の完走率や、物理的に安全に脱出できるかは未評価である。
成分が長くつながる地図では、解除範囲も長くなる。0.5m以内という距離制限は新方式にはない。生マスクが推定である限り、真の障害物をすべて除外できるという保証もない。
定義を確認してから、別途研究PCで旧escape・新escape_componentを同じ条件で繰り返し評価する必要がある。
実行時の選択引数は `--map fine --endpoint-policy escape` と `--map fine --endpoint-policy escape_component`。既定はnoneのままである。

## 変更・追加ファイル一覧

- `conference/experiments/endpoint_replay.py`
- `conference/results/endpoint_policy/b/REPORT_ja.md`
- `conference/results/endpoint_policy/b/changed_files.txt`
- `conference/results/endpoint_policy/b/implementation_commit.txt`
- `conference/results/endpoint_policy/b/replay.csv`
- `conference/results/endpoint_policy/b/replay.json`
- `conference/results/endpoint_policy/b/replay_log.txt`
- `conference/results/endpoint_policy/b/verification/all_tests_log.txt`
- `conference/results/endpoint_policy/b/verification/baseline_sha256.json`
- `conference/results/endpoint_policy/b/verification/build_report.py`
- `conference/results/endpoint_policy/b/verification/capture_legacy.py`
- `conference/results/endpoint_policy/b/verification/capture_legacy_log.txt`
- `conference/results/endpoint_policy/b/verification/component_log.txt`
- `conference/results/endpoint_policy/b/verification/diagnose_saved_starts.py`
- `conference/results/endpoint_policy/b/verification/legacy/coarse_manifest.json`
- `conference/results/endpoint_policy/b/verification/legacy/escape_diag_manifest.json`
- `conference/results/endpoint_policy/b/verification/legacy/escape_manifest.json`
- `conference/results/endpoint_policy/b/verification/legacy/fine_manifest.json`
- `conference/results/endpoint_policy/b/verification/legacy/replay.json`
- `conference/results/endpoint_policy/b/verification/planners_before_log.txt`
- `conference/results/endpoint_policy/b/verification/preservation_audit.json`
- `conference/results/endpoint_policy/b/verification/protocol.json`
- `conference/results/endpoint_policy/b/verification/refresh_replay.py`
- `conference/results/endpoint_policy/b/verification/replay_console_log.txt`
- `conference/results/endpoint_policy/b/verification/run_tests.py`
- `conference/results/endpoint_policy/b/verification/saved_start_diagnosis.json`
- `conference/results/endpoint_policy/b/verification/saved_start_diagnosis_log.txt`
- `conference/results/endpoint_policy/b/verification/test_beach_terrain_log.txt`
- `conference/results/endpoint_policy/b/verification/test_collision_log.txt`
- `conference/results/endpoint_policy/b/verification/test_dstar_log.txt`
- `conference/results/endpoint_policy/b/verification/test_endpoint_component_log.txt`
- `conference/results/endpoint_policy/b/verification/test_endpoint_policy_log.txt`
- `conference/results/endpoint_policy/b/verification/test_footprint_log.txt`
- `conference/results/endpoint_policy/b/verification/test_geo_log.txt`
- `conference/results/endpoint_policy/b/verification/test_gz_compare_log.txt`
- `conference/results/endpoint_policy/b/verification/test_gz_online_batch_log.txt`
- `conference/results/endpoint_policy/b/verification/test_mapfiles_sim_log.txt`
- `conference/results/endpoint_policy/b/verification/test_mission_log.txt`
- `conference/results/endpoint_policy/b/verification/test_natural_terrain_log.txt`
- `conference/results/endpoint_policy/b/verification/test_online_deadend_log.txt`
- `conference/results/endpoint_policy/b/verification/test_online_log.txt`
- `conference/results/endpoint_policy/b/verification/test_online_mission_log.txt`
- `conference/results/endpoint_policy/b/verification/test_planners_log.txt`
- `conference/results/endpoint_policy/b/verification/test_pointcloud_map_fine_log.txt`
- `conference/results/endpoint_policy/b/verification/test_pointcloud_map_log.txt`
- `conference/results/endpoint_policy/b/verification/test_real_beach_las_log.txt`
- `conference/results/endpoint_policy/b/verification/test_real_beach_log.txt`
- `conference/results/endpoint_policy/b/verification/test_real_sensors_log.txt`
- `conference/results/endpoint_policy/b/verification/test_risk_prior_log.txt`
- `conference/results/endpoint_policy/b/verification/test_ros2_gz_log.txt`
- `conference/results/endpoint_policy/b/verification/test_summary.txt`
- `conference/results/endpoint_policy/b/verification/test_thesis_figures_log.txt`
- `conference/results/endpoint_policy/b/verification/test_tour_log.txt`
- `conference/results/endpoint_policy/b/verification/test_visibility_log.txt`
- `conference/ros2_jazzy/gz_checks/endpoint_runtime.py`
- `conference/ros2_jazzy/gz_checks/lidar_checks.py`
- `conference/tapp/endpoint_policy.py`
- `conference/tests/test_endpoint_component.py`
