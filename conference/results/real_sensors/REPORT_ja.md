# 指示書027 段階A 実装・検証報告（2026-11-09）

## 1. コミット・対象・実装

- ブランチ：`codex/027-real-sensors`
- 起点：`realtime-map` の作業開始時の最新 `ad2d90cfd7e56fab1b0c79ac75bc9f5ae43a18c2`
- 実装コミット：`e4b9bef3b94343827d534412d1e482fab788ecce`
- Gitの通常pushは認証情報がなく失敗したため、接続済みGitHub機能で同一の実装ツリーを保存した。
  実装ツリーSHAはローカルの検証済みツリーと一致する。
- 本報告・テスト出力・幾何学の表と図は後続の記録コミットに保存する。最終HEADはブランチのHEADを参照。
- マージなし。段階A 1〜6だけ。Gazebo・Dockerの実行、段階Bの10か所は未実行。

### 変更・追加ファイル（実装コミット）

- `conference/experiments/sensor_coverage.py`
- `conference/results/real_sensors/legacy_sha256.json`
- `conference/ros2_jazzy/gz_checks/lidar_checks.py`
- `conference/ros2_jazzy/gz_checks/lidar_map.py`
- `conference/ros2_jazzy/gz_checks/lidar_planner.py`
- `conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/lidar.py`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/model.py`
- `conference/tapp/pointcloud_map_multi.py`
- `conference/tapp/sensor_geometry.py`
- `conference/tests/test_real_sensors.py`

### 実装の要点

- `sensor_preset='real_bunker'`：LiDARは模型原点から(-0.24,0,1.40)、base_linkから(-0.24,0,1.05)。
  カメラは模型原点から(0.40,±0.27,0.76)、base_linkから(0.40,±0.27,0.41)、yaw±0.345、水平。
- 従来LiDARは位置中央・高さ0.8m・最短0.1mのまま。実機LiDARのみ最短0.9m。
  16本・±15°・水平1800サンプル・10Hz・最長30m・雑音0.02mは維持。
- 深度カメラは既定で付けない。87°×58°、0.6〜6m、10Hz、212×120、雑音0.01m。
  これらは仮定。独立のfx/fyをSDFに書き、解像度変更で縦視野が変わらないようにした。
- `--sensors lidar_real` / `lidar_real+depth2` は `--map fine` と一緒に明示選択する。
  既定のmanifest・SDF・地図は従来どおり。カメラ橋渡しYAMLは選択時だけ生成。
- 地図は新しい `PointCloudMapMulti` から、既存の `PointCloudMapFine` を再利用する。
  点群のセンサー位置・向きと、その時刻の本当の模型姿勢でworld登録する。
  元の `pointcloud_map.py` / `pointcloud_map_fine.py` は変更していない。
- 0.1m障害物格子、古い地図より0.3m高い点が3点、直近64点、半径0.5mで1回だけ膨張を維持。
  センサー別に先に膨張して合成する処理はない。
- 3ソースそれぞれ最大1件の待ち行列で、古い点群時刻から処理する。センサーごとに
  受信数・処理数・破棄数・最終時刻を記録し、選択した全ソースの鮮度を確認する。
- 障害物の初回検出時に、細格子・トリガーセンサー・直近履歴のセンサー別寄与点数・sim時刻・
  ロボットからの水平距離を `.sensors.json` に残す。「物体数」でなく「細格子数」。
- 026のブランチをマージしていない。起点には `THESIS_FINE_PROTOCOL` / `THESIS_ONLY_PATCH` がなく、
  この実装から追加・削除していない。既存 `fine_protocol()` 本体とその既定は無変更。

### 既定の互換性

変更前に、生成模型SDF（LiDARなし・あり）と、固定の偽点群によるfine地図NPZのSHA256を採取した。
`legacy_sha256.json` に保存し、新テストで変更後とバイト単位一致を確認した。
従来のmanifest互換性も既存 `tests.test_pointcloud_map_fine` で確認する。
既存結果、地形データ、論文、元の地図実装はgit差分なし。

## 2. 幾何学だけの死角の表

正面の最短可視距離（模型原点からの水平距離、刻み0.01m）。遠方には離散ビームによる死角がある。

| 物体の高さ | 従来LiDAR | 実機LiDAR | 実機LiDAR＋カメラ2台 |
|---|---|---|---|
| 0.1m | 2.62m | 4.62m | 1.77m |
| 0.2m | 2.24m | 4.24m | 1.58m |
| 0.3m | 1.87m | 3.87m | 1.38m |
| 0.5m | 1.12m | 3.12m | 1.14m |

全72行（4高さ×3構成×6方向）と遠方の可視区間：`coverage.csv` / `coverage_ja.md`。
図：`coverage.png`。正面の集計出力全文：

```text
height_m | sensors | front_first_visible_m | front_visible_intervals_m
0.1 | legacy_lidar | 2.62 | [[2.62,2.98],[3.04,3.46],[3.61,4.11],[4.42,5.05],[5.71,6.51],[8.01,9.14],[13.36,15.26]]
0.1 | lidar_real | 4.62 | [[4.62,4.98],[5.4,5.82],[6.45,6.96],[7.97,8.59],[10.35,11.16],[14.62,15.76],[24.57,26.47]]
0.1 | lidar_real+depth2 | 1.77 | [[1.77,6.35],[6.45,6.96],[7.97,8.59],[10.35,11.16],[14.62,15.76],[24.57,26.47]]
0.2 | legacy_lidar | 2.24 | [[2.24,6.51],[6.86,9.14],[11.45,15.26]]
0.2 | lidar_real | 4.24 | [[4.24,5.82],[5.94,6.96],[7.34,8.59],[9.54,11.16],[13.48,15.76],[22.66,26.47]]
0.2 | lidar_real+depth2 | 1.58 | [[1.58,6.96],[7.34,8.59],[9.54,11.16],[13.48,15.76],[22.66,26.47]]
0.3 | legacy_lidar | 1.87 | [[1.87,9.14],[9.55,15.26],[28.65,29.99]]
0.3 | lidar_real | 3.87 | [[3.87,8.59],[8.72,11.16],[12.34,15.76],[20.75,26.47]]
0.3 | lidar_real+depth2 | 1.38 | [[1.38,8.59],[8.72,11.16],[12.34,15.76],[20.75,26.47]]
0.5 | legacy_lidar | 1.12 | [[1.12,15.26],[17.19,29.99]]
0.5 | lidar_real | 3.12 | [[3.12,15.76],[16.94,26.47]]
0.5 | lidar_real+depth2 | 1.14 | [[1.14,15.76],[16.94,26.47]]

```

距離はすべて**模型原点からの水平距離**。実機LiDARから高さ0.3m物までの最短は約4.105mだが、
LiDARは模型原点より0.24m後ろなので、正面の表は約3.87mになる。
カメラの前0.40m・左右0.27m・外向き0.345radも含めるため、カメラ2台込みは約1.38m。
正面1m付近はカメラ込みでも死角として残る。1.5/2/3mの箱の偽点群で検出を確認した。

カメラの表は連続視野、LiDARは16本の離散縦ビーム・連続方位。
物体幅・画素命中・遮蔽・ノイズ・姿勢変動・3点の判定条件は含まない。
高さ0.1/0.2m物体の可視性は、既存の0.3mしきい値による障害物判定の成功を意味しない。
宣言された16本のビームから直接計算すると、小さな遠方の死角も生じる。
資料の「4.1〜11.4mは連続」をそのまま仮定していない。仕様値やしきい値は調整していない。

## 3. 実行したコマンドとテストの出力全文

環境は `environment.json`。NumPy 2.3.5 / SciPy 1.17.0 / Matplotlib 3.10.8 / Pandas 2.2.3。
ROS2・Gazebo・追加の重いライブラリは不要。既存のPython環境を使用した。

- 変更前：`cd conference && python3 -m tests.test_planners` → `all planner tests passed` / `roll-aware tests passed`。
- 変更前：`make_model()` と `PointCloudMapFine.update()/save()` の固定入力出力のSHA256を保存。
- 作業中：`python3 /tmp/task027_baseline.py "$PWD/conference" /tmp/task027-baseline`。
  先行実行23モジュールの出力全文・終了コードを `work_in_progress_tests/` に保存。
  これは作業中の回帰確認で、全項目を変更前だけに実行したという意味ではない。
- 最終確認：下のランナー（保存した `run_python_tests.py` と同じ内容）で、全24モジュールを列挙して実行。
  各モジュールの上限240秒。終了コードと標準出力・標準エラー全文を保存。

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 /tmp/task027_baseline.py \
  "$PWD/conference" "$PWD/conference/results/real_sensors/tests"
```

再実行する場合は保存したランナーを用い、既存ログを上書きしないよう新しい出力先を指定する：

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python3 conference/results/real_sensors/run_python_tests.py \
  "$PWD/conference" /tmp/task027-tests-new
```

- `cd conference && python3 -m experiments.sensor_coverage --output results/real_sensors > results/real_sensors/coverage_log.txt`
- `git diff --check` → 出力なし、終了コード0。
- `bash -n conference/ros2_jazzy/gz_checks/run_lidar_checks.sh` → 出力なし、終了コード0。
- Python AST構文確認 → `Python AST parse: PASS`。

### 最終テスト結果

| モジュール | 終了コード |
|---|---|
| tests.test_beach_terrain | 0 |
| tests.test_collision | 0 |
| tests.test_dstar | 0 |
| tests.test_footprint | 0 |
| tests.test_geo | 0 |
| tests.test_gz_compare | 0 |
| tests.test_gz_online_batch | 0 |
| tests.test_mapfiles_sim | 0 |
| tests.test_mission | 0 |
| tests.test_natural_terrain | 0 |
| tests.test_online | 0 |
| tests.test_online_deadend | 0 |
| tests.test_online_mission | 0 |
| tests.test_planners | 0 |
| tests.test_pointcloud_map | 0 |
| tests.test_pointcloud_map_fine | 0 |
| tests.test_real_beach | 0 |
| tests.test_real_beach_las | 0 |
| tests.test_real_sensors | 0 |
| tests.test_risk_prior | 0 |
| tests.test_ros2_gz | 0 |
| tests.test_thesis_figures | 0 |
| tests.test_tour | 0 |
| tests.test_visibility | 0 |

全24モジュール成功。以下は実際に保存した標準出力・標準エラーの全文。

### `python3 -m tests.test_beach_terrain`

```text
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

```

### `python3 -m tests.test_collision`

```text
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

```

### `python3 -m tests.test_dstar`

```text
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

```

### `python3 -m tests.test_footprint`

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

### `python3 -m tests.test_geo`

```text
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

```

### `python3 -m tests.test_gz_compare`

```text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

```

### `python3 -m tests.test_gz_online_batch`

```text
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

```

### `python3 -m tests.test_mapfiles_sim`

```text
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

```

### `python3 -m tests.test_mission`

```text
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

```

### `python3 -m tests.test_natural_terrain`

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

### `python3 -m tests.test_online`

```text
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

```

### `python3 -m tests.test_online_deadend`

```text
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

```

### `python3 -m tests.test_online_mission`

```text
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

```

### `python3 -m tests.test_planners`

```text
all planner tests passed
roll-aware tests passed

```

### `python3 -m tests.test_pointcloud_map`

```text
/workspace/scratch/593ad3384f78/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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

### `python3 -m tests.test_pointcloud_map_fine`

```text
/workspace/scratch/593ad3384f78/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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

### `python3 -m tests.test_real_beach`

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

### `python3 -m tests.test_real_beach_las`

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
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

```

### `python3 -m tests.test_real_sensors`

```text
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

```

### `python3 -m tests.test_risk_prior`

```text
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

```

### `python3 -m tests.test_ros2_gz`

```text
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

```

### `python3 -m tests.test_thesis_figures`

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

### `python3 -m tests.test_tour`

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

### `python3 -m tests.test_visibility`

```text
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

```

## 4. 未実行・不確かなこと

- Gazebo、ROS2通信、Docker、段階Bの走行は**未実行**。完走率や負荷の数値を作っていない。
- SDFの深度カメラ・点群軸・87×58度の投影・クリップの実動作は研究PCで短時間確認が必要。
  Gazebo Sensors 8 / Ogre2 / SDFormatの公式ソースを確認して実装した（URLはREADME）。
  実際の描画結果やカメラ2台の負荷は未測定。
- 新テストでは実際のROSアダプターのメソッドを抽出して、通信だけを模したハーネスで
  公平なキュー・点群時刻の姿勢・フレーム検査・各ソースの鮮度とログを検証した。
  ROS通信を実行したことにはならない。
- カメラの特性は指定の仮定のまま。実機D455の点群との較正・比較はしていない。
- ROS optical座標（z前）の実機点群を直接入れるためのTF処理ではない。
  今回生成したGazeboのx前・y左・z上の点群を対象とする。
- 026の作業ブランチとの統合や1倍設定への変更はしていない。通常既定は0.3倍のまま。
- 既存の023比較集計は新センサーの比較には使わない。段階B用の集計は今回未実装。
- 漂着物は従来の箱モデルのまま（実際の漂着物より発見しやすい）。
- 段階Bは026の結論を踏まえ、研究PCへの別の実行依頼で行う。
