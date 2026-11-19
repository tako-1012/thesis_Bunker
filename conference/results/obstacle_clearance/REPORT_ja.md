# 指示書 041　障害物の余白をマス全体で判定

Codex クラウドの `thesis_Bunker` で作業した。土台は `realtime-map` の `72253c6c07f5fb39dcb5398427c423fd0e42694a`。作業ブランチは `codex/041-obstacle-clearance`、実装と検証の対象は `33d6c1afb01a143bad644bc759966ee73d90e7f5`。Python 3.12.14 と `conference/requirements-venv.txt` の指定版を入れた既存 venv を使った。

## 変更・追加ファイル

| ファイル | 内容 |
|---|---|
| `tapp/pointcloud_map_fine.py` | 0.1 m 格子の面を使う overlap の膨張と局所集約。検出した障害物の余白は未観測マスでも計画に反映 |
| `tapp/obstacle_clearance.py` | 点・折れ線から閉じた障害物矩形への最短距離 |
| `tapp/online_safety.py` | C2。残りの経路を切り出して `path_distance` を使用。閾値付近の停止判定は従来の演算順を維持 |
| `ros2_jazzy/gz_checks/lidar_checks.py` | CLI、ROS 引数、manifest、診断の漂着物形状、C4 の終了分岐 |
| `ros2_jazzy/gz_checks/lidar_map.py`、`lidar_planner.py`、`run_lidar_checks.sh` | overlap を fine マッパーへ渡す。診断時に距離記録を有効化 |
| `ros2_jazzy/gz_checks/lidar_runtime.py`、`endpoint_runtime.py` | 計画と診断で余白のマスクを使用。診断スナップショットと同じ時点の距離を記録 |
| `ros2_jazzy/gz_checks/clearance_log.py` | world が実際に定義する漂着物の衝突箱を記録 |
| `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_safety.py`、`path_follower.py` | C1 の履歴取得と C3 のクラス既定値 |
| `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_planner.py` | v2 を既存の安全ランタイムに接続 |
| `experiments/obstacle_clearance_report.py` | 走行後の真値と検出地図の最短距離を CSV へ出力 |
| `tests/test_obstacle_clearance.py`、`tests/reference/obstacle_clearance_legacy.json` | 回帰テストと実装前の比較用ハッシュ |
| `results/obstacle_clearance/compare_saved_maps.py`、`saved_maps.csv`、`assessment_log.txt`、`REPORT_ja.md` | 保存地図でのマス数と到達性の比較、集計出力、この報告 |

ファイル名は `conference/` からの相対パス。既定の `centre` は manifest 上の項目省略で表し、明示 `centre` でも従来と同じバイト列になる。明示 `overlap` は `--map fine` で使用し、その選択と膨張方法を manifest に記録する。

## 判定と互換性

- 既存の細格子中心で半径を判定した膨張マスクを集約するだけでは、細格子中心が 0.5 m の外側にあり、マスの角が内側に入る場合がある。座標 `(15,17)` の細格子に対して粗格子 `(4,2)` がその例。overlap では閉じた細格子同士の最短距離で、同じ 0.5 m の範囲との交差を判定し、同じ粗格子内のいずれかが交差すれば通行不可とする。
- 離れた少数の検出は膨張オフセットを直接加え、密な領域では変化の矩形を粗格子に合わせて集約する。20 回の点群更新のたびに全体の計算結果と比較し、疎な増分・密な増分と地図端の条件も確認した。センサーで標高を観測した印 `seen` を維持し、経路計画には検出から確定した膨張範囲も入力する。
- `centre` の暗黙・明示、`prior`・`local`、Fine・Multi の地図、履歴、NPZ と出所の記録を実装前と照合した。診断で新しいファイルを追加した場合も、`none`・`v1`・`v2` の模擬 ROS 指令、状態、manifest と従来のログ・NPZ は一致した。比較では実行時間を決める時計を固定した。
- C1 で `plan_history` 省略時は直前の履歴を保持する。C2 は 300 点で従来の停止判定と一致し、0.75 m 付近で演算順を変えるだけでは判定が異なる 23 例も含む。C3 はクラス既定値を設定した。C4 は CLI と既存の環境変数のどちらで 1.0 倍にしても、fine の manifest を見て 0.3 倍対照の task023 集計を省く。
- ROS 側の初期化に、v2 が既存の安全ランタイムの代わりに通常ランタイムに渡される分岐があった。v2 を既存の v2 ランタイムへつなぎ、モデル化したノードの初期化で overlap・v2・診断を同時に選べることを確かめた。Pure Pursuit の制御と閾値には手を加えていない。

## 経路と障害物の最短距離

合成地図上で、両条件とも同じ始点・終点と検出格子から TA*-S を実行した。距離はすべての経路線分と検出した閉じた細格子との厳密な最短値。座標は粗格子のインデックス。

```text
2 mode min_path_clearance_m lethal_cells path_grid
centre 0.477533728 4 [(10, 15), (11, 7)]
overlap 1.123456796 12 [(10, 15), (12, 10), (12, 8), (11, 7)]
```

## 保存地図での通れるマスと到達性

4 枚の保存済み走行末尾の地図を使った。検出した細格子から overlap を計算し、既存の centre の通行不可マスクに重ねた。比較は地図全体で、古い地図と急斜面の制約も含む。到達性は各マスクの通行可能なマスを 4 近傍で連結し、記録上の出発点と同じ成分にある地点を数えた。地点の個数には巡回の帰着点を含む。

| 保存地図 | centre の通行可 | overlap の通行可 | 減少（centre 比） | 出発点から到達する地点 |
|---|---:|---:|---:|---:|
| 08OB86_00294 | 76,654 | 76,026 | 628（0.82%） | 6 → 6 |
| 08OB86_-0205 | 73,032 | 72,503 | 529（0.72%） | 6 → 6 |
| 08OB87_-0706 | 75,150 | 74,063 | 1,087（1.45%） | 6 → 6 |
| 08OB89_-0847 | 117,368 | 115,152 | 2,216（1.89%） | 6 → 5 |

08OB89_-0847 では最後の地図で 1 地点の到達性が失われた。狭い所や目標が余白にかかる場合に、経路なしが増える可能性がある。この比較は保存時点のマスク上の連結性を示す。地図の更新順や走行中の別経路は評価していない。

```text
run,cells,detected_fine_cells,centre_free,overlap_free,lost_free,lost_free_seen,reachable_centre_goals,reachable_overlap_goals
results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB86_00294,160000,89707,76654,76026,628,608,6,6
results/rtf_check/hayashi_rtf1_check/rtf_0.3/physical_1/raw/08OB86_-0205,160000,24572,73032,72503,529,508,6,6
results/rtf_check/hayashi_rtf_repeat/rtf_0.3_rep1/physical_1/raw/08OB87_-0706,160000,10660,75150,74063,1087,1053,6,6
results/eval_ground_endpoint/runs/08OB89_-0847/C2_r3/physical_1/raw/08OB89_-0847,160000,51725,117368,115152,2216,2097,6,5
```

## 診断と走行後の集計

`--diagnostics` では既存の周期スナップショットと同時に、`clearance.csv` にシミュレーション時刻、地図の版、中心座標、未膨張の検出格子までの距離を記録する。周期は既存と同じ 10 秒以上の間隔。検出が無い場合は距離欄を空にする。従来のログの形式と内容は維持し、追加の CSV に記録する。

`debris_footprints.csv` には生成した world の漂着物の衝突箱の XY 矩形が入る。走行後の集計は、軌跡のサンプル間を線分で結んで真値の矩形までの最短距離を求める。古い記録では `--truth-map` で漂着物のマスクを含む評価用 NPZ を指定すると、0.5 m の閉じたマスで近似できる。

```bash
# conference/ から。RAW_RUN_DIR は trajectory.csv がある raw/<砂浜>。
python -m experiments.obstacle_clearance_report RAW_RUN_DIR
python -m experiments.obstacle_clearance_report OLD_RAW_RUN_DIR --truth-map TRUTH_MAP.npz
```

08OB86_-0205 の旧軌跡で、元と同じ砂浜・シードから world を Python で再生成して集計を試した。記録 4,811 点。再生成した箱 218 個とマスクの 379 マスのどちらでも最短は 1.044259 m。この旧記録の走行中の診断距離は記録されていない。

## 研究 PC での評価案

037 の砂浜・センサー構成、倍率、乱数、診断をそろえ、比較ペアには `centre` と `overlap` を指定する。たとえば LC 条件の砂浜 1 か所では、新しい出力先を使う。以下は overlap の例。

```bash
THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH=08OB86_-0205 \
  bash conference/ros2_jazzy/gz_checks/run_lidar_checks.sh OUTPUT \
  --map fine --real-time-factor 0.3 --sensors lidar_real+depth2 \
  --ground-estimate non_obstacle --online-fixes v2 --diagnostics \
  --obstacle-clearance overlap
```

037 と同じ 5 か所で 3 回ずつ比較し、真値への最短距離と 0.5 m 未満の回数、検出地図での距離、完走・経路なしの件数を対で記録する。経路なしは、到達地点・目標マス・狭い区間のどこで遮断されたかを診断で確かめる。追従のずれ、経路の置換、`off_path`・`unsafe_tilt` も比較する。

## できなかったこと・確認範囲

Gazebo と研究 PC での走行は未実施。最短距離は水平面の中心軌跡と検出格子または箱の距離で、回転した車体の実際の接触は未確認。overlap と診断記録による処理時間の変化は未計測。真値に 0.5 m のマスしかない場合は、実物の外形や箱が占める部分を解像できない。周期診断の間の接近は観測距離の最小に含まれない。0.5 m の幾何条件は通行可能なマスの内部と境界に適用される。未検出の障害物、既存の始点例外や明示的な端点緩和、追従誤差には別の影響が残る。

## 実行コマンドとテストの出力全文

```bash
git status -sb
git fetch origin realtime-map
git switch -c codex/041-obstacle-clearance FETCH_HEAD
git rev-parse HEAD
mkdir -p /tmp/041-logs /tmp/041-mpl /tmp/041-cache
cd conference
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/041-mpl XDG_CACHE_HOME=/tmp/041-cache
/tmp/thesis036-venv/bin/python -u -m tests.test_planners
```

実装前に、同じ venv で既定出力のハッシュを採取した。

```bash
/tmp/thesis036-venv/bin/python - <<'PY'
import json
from tests.test_obstacle_clearance import FIXTURE, capture_defaults
FIXTURE.write_text(json.dumps(capture_defaults(), sort_keys=True, indent=2)+'\n')
PY
```

検証と保存地図の比較を実施した。

```bash
# リポジトリから
git diff --check
bash -n conference/ros2_jazzy/gz_checks/run_lidar_checks.sh
cd conference
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/041-mpl XDG_CACHE_HOME=/tmp/041-cache
/tmp/thesis036-venv/bin/python -u -m tests.test_obstacle_clearance
PYTHONPATH=. /tmp/thesis036-venv/bin/python results/obstacle_clearance/compare_saved_maps.py \
  results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB86_00294 \
  results/rtf_check/hayashi_rtf1_check/rtf_0.3/physical_1/raw/08OB86_-0205 \
  results/rtf_check/hayashi_rtf_repeat/rtf_0.3_rep1/physical_1/raw/08OB87_-0706 \
  results/eval_ground_endpoint/runs/08OB89_-0847/C2_r3/physical_1/raw/08OB89_-0847 \
  | tee results/obstacle_clearance/saved_maps.csv
for f in tests/test_*.py; do printf '%s\n' "${f%.py}"; done | tr / . | xargs -P 4 -I '{}' bash -c '
module=$1
log=/tmp/041-logs/${module}.txt
printf "\$ /tmp/thesis036-venv/bin/python -u -m %s\n" "$module" >"$log"
/tmp/thesis036-venv/bin/python -u -m "$module" >>"$log" 2>&1
status=$?
printf "\nexit=%s\n" "$status" >>"$log"
printf "%s exit=%s\n" "$module" "$status"
exit "$status"
' bash '{}'
```

初回実行では、既存のテストが本体の `main` を単独で読み込むため、新しい選択肢のモジュール変数が見つからなかった。参照する定数を `main` 内の import に移して修正し、既存テストの内容は維持した。最終版で `tests.test_ground_estimate`、`tests.test_endpoint_policy`、`tests.test_endpoint_component` を個別に再実行した。以下は最終結果。

旧軌跡の集計は、`conference/` で次のコードを venv の `python -` に渡して実施した。

```python
from pathlib import Path
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET
from data_prep.export_gazebo import export_gazebo
from experiments.obstacle_clearance_report import summarize
from ros2_jazzy.gz_checks.clearance_log import save_debris_footprints
from tapp.mapfile import save_map
from tapp.real_beach import build_real

patch = '08OB86_-0205'
source = Path(f'results/rtf_check/hayashi_rtf1_check/rtf_0.3/physical_1/raw/{patch}')
truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
with TemporaryDirectory() as tmp:
    root = Path(tmp)
    truth_map = root/'truth.npz'
    terrain = truth['terrain']
    save_map(truth_map, truth['tmap'].elev, obstacle=terrain['rock'],
             water=terrain['water'], nodata=terrain['nodata'])
    export_gazebo(truth_map, root/'world', max_pixels=4097)
    save_debris_footprints(root/'debris_footprints.csv', ET.parse(root/'world/world.sdf').find('world'))
    (root/'trajectory.csv').symlink_to((source/'trajectory.csv').resolve())
    print(source)
    for option in (None, truth_map):
        row = summarize(root, option)
        row.pop('run')
        print(row)
```

### 変更前のプランナーテスト

```text
all planner tests passed
roll-aware tests passed

exit=0
```

### 実装後の全 36 テストモジュール

全モジュールが終了コード 0。

#### `tests.test_beach_terrain`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0
```

#### `tests.test_collision`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0
```

#### `tests.test_dstar`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0
```

#### `tests.test_edge_margin`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_edge_margin
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)

exit=0
```

#### `tests.test_endpoint_component`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_component
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

exit=0
```

#### `tests.test_endpoint_policy`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_policy
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

exit=0
```

#### `tests.test_footprint`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_footprint
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
```

#### `tests.test_geo`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_geo
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

#### `tests.test_ground_estimate`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_ground_estimate
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

exit=0
```

#### `tests.test_gz_compare`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0
```

#### `tests.test_gz_online_batch`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0
```

#### `tests.test_lab_geometry`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_lab_geometry
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite

exit=0
```

#### `tests.test_local_speed`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_local_speed
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpqg14m8_5/ten
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
synthetic lidar 28800 28800 12 7.310387 10.730477 0.289303 0.390566 0 0
synthetic camera1 26750 26750 12 8.732042 11.453494 0.045963 0.068145 0 0
saved_b0b lidar 28800 11741 1 3.041000 3.041000 0.075382 0.075382 1 1
saved_b0b camera1 26750 9604 1 2.811205 2.811205 0.060075 0.060075 0 0
saved_b0b camera2 26750 9242 1 2.776525 2.776525 0.029457 0.029457 0 0
all local speed tests passed

exit=0
```

#### `tests.test_map_speed`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_map_speed
byte-identical replay: 88 update states

exit=0
```

#### `tests.test_mapfiles_sim`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_mapfiles_sim
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

#### `tests.test_mission`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

#### `tests.test_natural_terrain`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0
```

#### `tests.test_obstacle_clearance`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_obstacle_clearance
1 PASS: centre default/explicit, prior/local, fine/multi; map, manifest, ROS-mocked commands and existing none/v1/v2 files match baseline
2 mode min_path_clearance_m lethal_cells path_grid
centre 0.477533728 4 [(10, 15), (11, 7)]
overlap 1.123456796 12 [(10, 15), (12, 10), (12, 8), (11, 7)]
3 PASS: full recompute after 20 updates across prior/local and fine/multi, plus dense/sparse edge cases
3 planning PASS: inferred overlap halo blocks unseen cells in normal and diagnostic planner snapshots
4 B PASS: periodic observed data incl. empty map, exact trajectory-to-box distance, CSV parts and truth-mask fallback
4 C1-C3 PASS: missing plan_history, shared path_distance (300 decisions, 23 rounding cases), class default
4 C4 and routing PASS: env-selected 1.0 honoured, overlap manifest, ROS command and wrapper
4 ROS constructor PASS: v2 runtime, overlap mapper and diagnostics selected together
all task041 obstacle clearance tests passed

exit=0
```

#### `tests.test_online`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0
```

#### `tests.test_online_deadend`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0
```

#### `tests.test_online_mission`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

#### `tests.test_online_safety`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_safety
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

exit=0
```

#### `tests.test_planners`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0
```

#### `tests.test_pointcloud_map`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0
```

#### `tests.test_pointcloud_map_fine`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0
```

#### `tests.test_prior_free`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_prior_free
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

exit=0
```

#### `tests.test_real_beach`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach
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
```

#### `tests.test_real_beach_las`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach_las
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
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0
```

#### `tests.test_real_sensors`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_sensors
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

exit=0
```

#### `tests.test_review_fixes`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_review_fixes
1 PASS: none/v1 commands, ROS follower state and log bytes unchanged; full manifest hashes 8/8
A1 v1 second tilt after 9s: replanned
A1 v2 second tilt after 9s: terminal unsafe_tilt
A1 v2 second tilt after 10s: terminal unsafe_tilt
A1 v2 second tilt after 10.1s: replanned
A2 v1 duplicate segment, 0.8m: running
A2 v2 duplicate segment, 0.8m: off_path
A3 v1 near passed segment and 0.8m from remaining route: running
A3 v2 near passed segment and 0.8m from remaining route: off_path
B6 PASS: the box is detected with support 0.70m from its centre
B9 PASS: dense/cKDTree agree on 298 heights, including unknown support
B8 5f36770 local_ground_032.py SHA-256 5a57c07f09d31e0fcf7508de6ddc28e05253cca13939eeda767ffca2ef7491f5
B8 5f36770 pointcloud_map_multi_032.py SHA-256 710d81185c5a945e9c89d1d679414c6846832f779edbc6a9e9065823ba67dc96
v2 configuration PASS: manifest, CLI, both ROS parameters and async factory
B10 PASS: fine world input NPZ, world SDF and heightmap match byte for byte; coarse matching remains explicit
Task036 task023 aggregation skipped: the waypoint cohort differs from the cached task022 controls. Manifest and available raw results: /tmp/tmpeux3914q/edge
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpeux3914q/coarse
Task036 task023 aggregation skipped: opt-in conditions require separate evaluation from task023. Manifest and available raw results: /tmp/tmpeux3914q/opt-in
B11 PASS: standard aggregation selected only for a comparable fine cohort
B7 controlled scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 0
6 0 0 0
7 0 0 0
8 0 0 0
9 0 0 0
10 0 0 0
11 0 0 0
B7 review scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 2
6 2 2 1
7 4 2 0
8 8 2 0
9 10 3 5
10 13 3 0
11 11 2 0
all task040 review-fix tests passed

exit=0
```

#### `tests.test_risk_prior`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0
```

#### `tests.test_ros2_gz`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_ros2_gz
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

#### `tests.test_rtf_option`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_rtf_option
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
default 0.3 PASS: omitted/explicit match, manifest and report match pre-change hashes (full manifest)
1.0 PASS: historical overlay manifest settings and world target match; stale=1.0, step=0.001, LiDAR=10Hz
validation PASS: explicit 0.3 overrides environment; legacy rtf_check still works; invalid factor, stale and coarse rejected
wrapper PASS: split and equals options forward unchanged, with identical Docker setup
run finalization PASS: explicit 1.0 preserves manifest and skips incompatible task023 summary
all task039 RTF option tests passed

exit=0
```

#### `tests.test_thesis_figures`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_thesis_figures

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
```

#### `tests.test_tour`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0
```

#### `tests.test_visibility`

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

### 保存軌跡の診断距離の集計出力

```text
results/rtf_check/hayashi_rtf1_check/rtf_0.3/physical_1/raw/08OB86_-0205
{'truth_source': 'exported world collision rectangles', 'trajectory_points': 4811, 'truth_footprints': 218, 'min_truth_clearance_m': 1.0442589250641288, 'finite_diagnostic_samples': 0, 'min_observed_clearance_m': None}
{'truth_source': 'truth map occupied 0.5m cells', 'trajectory_points': 4811, 'truth_footprints': 379, 'min_truth_clearance_m': 1.0442589250641288, 'finite_diagnostic_samples': 0, 'min_observed_clearance_m': None}
```
