# 指示書019：LAS砂浜のA*・TA*-S Gazebo比較

作業日：2026-11-02（日本時間）。ブランチ：`codex/019-gazebo-compare`。
基点：`origin/realtime-map` の `b4c92a1ccaf60eff85362564d2f0d9915c3d10ae`。
他の指示書の変更を取り込まず、この基点から独立して実装した。

## 実装したもの

- `ros2_jazzy/gz_checks/compare_checks.py`：`scenario_cases` がLASデータのtest先頭6か所について、200m・seed 0・漂着物なしの `build_real` と既定の `run_planner_exact` を呼ぶ。開始・終了点はそのまま使用する。
- `prepare_cases`：解析用NPZ、経路、計画時の地図指標、world変換結果をmanifestへ記録する。worldは既存 `export_gazebo` を呼び、一時フォルダにだけ作る。変換できない地形は原因を残して両方法を実行失敗とし、他の地形の処理を継続する。既存exporterの上限や地形は変えない。
- `run_checks`：各方法で同じworldを新規起動し、同じ位置・yaw=0から5秒静置後、既存 `path_follower` で走らせる。乱数seed 0、先読み1m、速度・角速度・到着許容・停滞監視は既存値を使う。環境を記録し、記録を上書きせず、プロセスエラーと未実行を記録する。
- `run_compare_checks.sh`：既存Dockerfile（`osrf/ros:jazzy-desktop-full` + pandas）を使用し、`THESIS_ROS_IMAGE` にも対応する。ソースは読取専用、colconのbuild/install/logとworldはコンテナの一時領域、出力だけを保存先にマウントする。
- `experiments/gz_compare_report.py`：既存 `analyze_run` を変更せず使用する。12走行の表、完走した対だけのTA*-S−A*の中央値、各砂浜の2軌跡・roll時系列図を作る。実測roll/pitchの絶対値の95%と最大、記録zの正の増分の総和、計画経路への `evaluate` の地図指標を併記する。元のmission JSONは書き換えず、一時ビューで移動後の地図パスを解決する。
- `tests/test_gz_compare.py`：ROS2なしで、直接呼出しとの経路一致、運動学の試験用記録と `analyze_run` の値の一致、最大角度・登り・地図指標・対の中央値、元ログの不変性、エネルギー列がないことを検証する。未実行・world変換失敗を測定値0にしないことも確かめる。

エネルギーは集計しない。6砂浜での記述比較として傾向を見るだけであり、検定は行わない。
登りの指標は記録zの正の増分をそのまま足すため、車体の揺れ・記録ノイズも含む。

## 変更ファイル一覧

- `conference/experiments/gz_compare_report.py`
- `conference/results/gazebo_compare/REPORT_ja.md`
- `conference/results/gazebo_compare/docker_attempt_log.txt`
- `conference/results/gazebo_compare/verification/all_tests_log.txt`
- `conference/results/gazebo_compare/verification/baseline_audit.json`
- `conference/results/gazebo_compare/verification/environment_log.txt`
- `conference/results/gazebo_compare/verification/planners_before_log.txt`
- `conference/results/gazebo_compare/verification/test_beach_terrain_log.txt`
- `conference/results/gazebo_compare/verification/test_collision_log.txt`
- `conference/results/gazebo_compare/verification/test_dstar_log.txt`
- `conference/results/gazebo_compare/verification/test_gz_compare_final_log.txt`
- `conference/results/gazebo_compare/verification/test_gz_compare_log.txt`
- `conference/results/gazebo_compare/verification/test_mapfiles_sim_log.txt`
- `conference/results/gazebo_compare/verification/test_mission_log.txt`
- `conference/results/gazebo_compare/verification/test_natural_terrain_log.txt`
- `conference/results/gazebo_compare/verification/test_online_log.txt`
- `conference/results/gazebo_compare/verification/test_online_mission_log.txt`
- `conference/results/gazebo_compare/verification/test_planners_log.txt`
- `conference/results/gazebo_compare/verification/test_real_beach_las_log.txt`
- `conference/results/gazebo_compare/verification/test_real_beach_log.txt`
- `conference/results/gazebo_compare/verification/test_risk_prior_log.txt`
- `conference/results/gazebo_compare/verification/test_ros2_gz_log.txt`
- `conference/results/gazebo_compare/verification/test_summary.txt`
- `conference/results/gazebo_compare/verification/test_tour_log.txt`
- `conference/results/gazebo_compare/verification/world_preparation_log.txt`
- `conference/ros2_jazzy/gz_checks/README_compare_ja.md`
- `conference/ros2_jazzy/gz_checks/compare_checks.py`
- `conference/ros2_jazzy/gz_checks/run_compare_checks.sh`
- `conference/tests/test_gz_compare.py`

すべて新規ファイル。既存14テストの変更なし。既存コード・データ・地図・world・結果の804ファイルは、作業前のSHA-256とすべて一致した。

```json
{
  "tracked_baseline_files": 804,
  "changed": []
}
```

## 実行環境

```text
executable: /tmp/thesis-apt-compat/bin/python
python: 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
{
  "numpy": "2.3.5",
  "scipy": "1.17.0",
  "matplotlib": "3.10.8",
  "pandas": "2.2.3",
  "pydantic": "2.13.4",
  "fastapi": "0.141.1",
  "httpx": "0.28.1"
}
Docker client=28.4.0 server=28.4.0
```

テストでは `/tmp/thesis-apt-compat/bin/python` を使用した。
`OPENBLAS_NUM_THREADS=1`、`MPLCONFIGDIR=/tmp/thesis-batch-mpl`、`XDG_CACHE_HOME=/tmp/thesis-batch-cache` を設定した。
Gazebo本体はホストにない。ホストへのsudo・ROS2/Gazeboのインストールは行っていない。

## 実行したコマンドとテスト出力の全文

変更前：

```bash
cd conference
python3 -m tests.test_planners
```

```text
all planner tests passed
roll-aware tests passed
```

変更後は `conference/tests/test_*.py` の全モジュールを次のドライバーで順に実行した（各コマンドは以下の全文に記載）。

```bash
python3 /tmp/thesis_batch_tools.py suite /workspace/thesis-019 /workspace/thesis-019/conference/results/gazebo_compare/verification
```

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

$ python3 -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ python3 -m tests.test_mapfiles_sim
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ python3 -m tests.test_online_mission
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

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
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
```

全実行結果：

```text
test_beach_terrain exit=0
test_collision exit=0
test_dstar exit=0
test_gz_compare exit=0
test_mapfiles_sim exit=0
test_mission exit=0
test_natural_terrain exit=0
test_online exit=0
test_online_mission exit=0
test_planners exit=0
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_tour exit=0
Failed modules: []
```

world生成失敗の扱いを追加した後、影響のある新規モジュールを最後に再実行した。以下もexit=0。

```bash
cd conference
python3 -m tests.test_gz_compare
```

```text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)
```

シェルは `bash -n ros2_jazzy/gz_checks/run_compare_checks.sh`、新規Pythonは `compile`、差分は `git diff --check` で確認した。

## Gazebo実行：未実行

実行したコマンド：

```bash
cd conference
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/gazebo_compare
```

最初はサンドボックスによる `~/.docker/buildx` への書込制限で失敗したため、サンドボックス外で再試行した。
Docker daemonには接続でき、既定イメージのダウンロードまで進んだが、レイヤー展開時に容量不足で失敗した（exit=1）。
実行ログ（行末の空白だけ除去）は `docker_attempt_log.txt`。末尾をそのまま示す。

```text
#4 sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 808.45MB / 965.91MB 43.9s
#4 sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 858.78MB / 965.91MB 46.3s
#4 sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 909.12MB / 965.91MB 48.7s
#4 sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 958.40MB / 965.91MB 51.0s
#4 sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 965.91MB / 965.91MB 51.5s done
#4 extracting sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45
#4 extracting sha256:dd4185219e03a01423809840312f0982ad8e9deea9bb03ab0540ef999a8a7f45 5.3s
#4 ERROR: failed to register layer: write /usr/include/vtk-9.1/vtkLegacy.h: no space left on device
------
 > [1/2] FROM docker.io/osrf/ros:jazzy-desktop-full@sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8:
------
Dockerfile:1
--------------------
   1 | >>> FROM osrf/ros:jazzy-desktop-full
   2 |     RUN rm -f /etc/apt/sources.list.d/ros2*.list /etc/apt/sources.list.d/ros2.sources 2>/dev/null; ls /etc/apt/sources.list.d/; apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-pandas && rm -rf /var/lib/apt/lists/*
   3 |
--------------------
ERROR: failed to build: failed to solve: failed to register layer: write /usr/include/vtk-9.1/vtkLegacy.h: no space left on device

exit=1
```

**物理走行は未実行。Gazeboの12走行の集計表、対の差、軌跡・rollの比較図は未生成。測定値は埋めていない。**
ROS2不要のテスト用記録は `kinematic_test_fixture` と明示し、一時フォルダでのみ生成・集計して破棄した。これらをGazebo実験結果として保存・報告していない。

## world生成だけの確認（Gazebo走行ではない）

Dockerに依存しない部分について、`prepare_cases` を一時フォルダに対して実行した。
対象6地形・12ケースを保持すること、成功したworld数が生成ファイル数と一致すること、失敗理由が両方法に付くこと、manifestをJSON化できることを確認した。
すべての一時world・解析用地図は終了時に削除した。使用したコマンド：

```bash
cd conference
python3 - <<'PY'
import json, tempfile
from pathlib import Path
from ros2_jazzy.gz_checks.compare_checks import prepare_cases
with tempfile.TemporaryDirectory(prefix='task019-world-check-') as tmp:
    root=Path(tmp)
    manifest=prepare_cases(root/'output',root/'worlds')
    assert len(manifest['cases'])==12
    assert len(manifest['world_exports'])+len(manifest['world_errors'])==6
    assert len(list((root/'worlds').glob('*/world.sdf')))==len(manifest['world_exports'])
    for case in manifest['cases']:
        assert ('error' in case)==(case['patch'] in manifest['world_errors'])
    json.dumps(manifest)
    print('Temporary preparation only; no Gazebo physical run was performed.')
    print(json.dumps({k:manifest[k] for k in ['world_exports','world_errors']},ensure_ascii=False,indent=2))
    print('All six world preparations attempted; 12 portable case definitions validated; export failures are explicit; temporary worlds removed on exit.')
PY
```

出力全文（地形変換の検証値であり、走行実験の集計表ではない）：

```text
Temporary preparation only; no Gazebo physical run was performed.
{
  "world_exports": {
    "08OB86_00294": {
      "map": "real_las_08OB86_00294_200m_0.npz",
      "pixels": 2049,
      "side_m": 200.0,
      "z_min": -1.3849999904632568,
      "z_span": 7.694166421890259,
      "max_error_m": 0.061695935096075516,
      "quantization_bound_m": 5.8702726954224906e-05,
      "obstacle_boxes": 0
    },
    "08OB86_-0205": {
      "map": "real_las_08OB86_-0205_200m_0.npz",
      "pixels": 2049,
      "side_m": 200.0,
      "z_min": -1.2760000228881836,
      "z_span": 6.869285583496094,
      "max_error_m": 0.06354209578655112,
      "quantization_bound_m": 5.240928956661397e-05,
      "obstacle_boxes": 0
    },
    "08OB87_-0706": {
      "map": "real_las_08OB87_-0706_200m_0.npz",
      "pixels": 1025,
      "side_m": 200.0,
      "z_min": -1.2669999599456787,
      "z_span": 7.20799994468689,
      "max_error_m": 0.09197745315509853,
      "quantization_bound_m": 5.4993514493681925e-05,
      "obstacle_boxes": 0
    }
  },
  "world_errors": {
    "08OB88_-1417": "ValueError: 高さ地図の補間誤差が0.1mを超えています: 0.12298041835012263",
    "08OB88_-0167": "ValueError: 高さ地図の補間誤差が0.1mを超えています: 0.16549192188655937",
    "08OB88_00332": "ValueError: 高さ地図の補間誤差が0.1mを超えています: 0.10710643607727643"
  }
}
All six world preparations attempted; 12 portable case definitions validated; export failures are explicit; temporary worlds removed on exit.
```

この環境では3地形が既存exporterの補間誤差上限0.1mを満たせなかった。
上限を緩めたり、対象を別の砂浜に替えたりせず、失敗を保持する実装を選んだ。
現在のスクリプトは、Dockerを使える環境でもこの失敗が生じれば該当する両方法を実行失敗として残し、残りを試行して最後に非0で終了する。
**6地形すべての物理比較には、実行環境でのworld生成の再確認と、必要なら既存exporter側の対応が残る。**
保護対象の `data_prep/export_gazebo.py` は変更していない。

## 再実行手順・Claudeに確認してほしいこと

十分なディスク容量のあるDocker環境で、`ros2_jazzy/gz_checks/README_compare_ja.md` のworld生成確認を先に実行する。
その後、新しい出力先を指定する：

```bash
git switch codex/019-gazebo-compare
cd conference
bash ros2_jazzy/gz_checks/run_compare_checks.sh results/gazebo_compare/physical_run
python3 experiments/gz_compare_report.py results/gazebo_compare/physical_run
```

既存イメージを使う場合は `THESIS_ROS_IMAGE=...` を付ける。既存manifestがある出力先は上書きせず停止するので、再走行では別の出力先を選ぶ。
原記録は出力先の `manifest.json`、`maps/`、`raw/`、再集計は `report/` に保存される。

ROS2の起動・初期静置・追従・プロセス終了、Gazeboでの実測記録、実測図の見た目は未確認。
車体形状・接地摩擦・heightmap補間・水面の扱いは既存exporter/modelの仮定を引き継ぐ。
world生成の制約と物理走行の確認を優先してレビューしてほしい。
