# 指示書027・段階A2：深度カメラの投影の修正

実装・テストログのコミットID：`8f9c103facab66effc8bfb9d3aefdb12248ae64b`。この報告書は後続の文書コミットで追加する。

作業ブランチ：`codex/027a2-camera-fov`。基点は最新取得したrealtime-mapの `0009471845c506fbee9c3f5242163511ff5cf628`。基準日は2026-11-10（日本時間）。マージしない。

## 実装したものと変更範囲

指定された段階A2の1〜4だけを実装した。背景は [段階B0の報告](../b0/REPORT_ja.md) を参照する。

- `tapp/sensor_geometry.py`：`DepthCameraSpec.width/height` を事前指定の214×125へ変更した。それ以外の仕様・取り付け位置・向きは変えていない。
- `ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py`：`add_depth_camera` が `lens/intrinsics` を出力する処理を削除した。`horizontal_fov` と画像の縦横比からGazeboが投影を決める。
- `ros2_jazzy/gz_checks/run_lidar_checks.sh`：`THESIS_FINE_PROTOCOL` と `THESIS_ONLY_PATCH` を、設定されている場合だけ `-e` で転送する。未設定なら引数を追加しない。個別・両方・空文字を明示設定した場合の転送をテストした。
- `tests/test_real_sensors.py`：カメラ有効時の旧212×120・独立fx/fyの期待値を、指定された214×125・intrinsicsなし・縦FOV58°±0.1°の条件へ置き換えた。取り付け位置・向き・範囲・頻度・雑音の検証は保持した。さらに全SDFの差分、既定のバイト一致、起動引数の転送を確認するテストを追加した。

`prepare_cases` は既存の `sensor_configuration` を使うため、新しい画素数は実走時のmanifestの `sensor_configuration.depth_camera_spec` にそのまま記録される。既存の「仮定」という記載も維持する。manifestへの記録はPythonのテストで確認した。

現在のカメラ仕様（Pythonの `asdict(DepthCameraSpec())`）：

```json
{
  "horizontal_fov_deg": 87.0,
  "vertical_fov_deg": 58.0,
  "width": 214,
  "height": 125,
  "min_range_m": 0.6,
  "max_range_m": 6.0,
  "update_hz": 10.0,
  "noise_stddev_m": 0.01
}
```

## 投影と既定出力の検証

生成したSDFの横FOVと画素数から `2*atan(height/width*tan(horizontal_fov/2))` を計算した。結果の全文は下の対象テスト出力に含めた。両カメラで58°±0.1°を満たし、生成するSDFにintrinsicsはない。

変更前に保存した比較入力と、カメラなしの既定SDF・既定LiDAR付きSDF・実機位置のLiDARだけのSDFを**そのままのバイトで比較**し、一致した。既存の既定Fine地図NPZのSHA-256も一致した。
カメラ付きSDFは、旧SDFから指定された画素数とintrinsicsの削除だけを反映したものと全体で一致した。カメラ仕様もwidth/height以外は変更前の辞書と一致した。

Docker起動引数は、実行機固有のソース/出力パスとUID/GIDだけを置き換え、変更前に捕捉した既定/coarse・fineの全引数のJSONバイトと比較した。2変数の未設定時は一致した。追加される引数以外も一致した。
この確認では実際のDockerを使わず、引数を保存するだけのPythonスタブをPATHの先頭へ置いた。コンテナやGazeboは起動していない。

`verification/legacy/` のSDFと仕様は変更前の比較入力として保持した。新しいSDFの出力を確認するのはテスト中の一時領域である。

## 実行したコマンドとテストの出力全文

Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-027a2-mpl XDG_CACHE_HOME=/tmp/thesis-027a2-cache` を指定した。

```bash
cd conference
python3 -m tests.test_planners
python3 results/real_sensors/a2/verification/capture_legacy.py  # 修正前に一度実行
python3 -m tests.test_real_sensors
python3 results/real_sensors/a2/verification/run_tests.py
python3 results/real_sensors/a2/verification/build_report.py --implementation-commit <上記の実装コミットID>
```

変更前のプランナー：

```text
all planner tests passed
roll-aware tests passed
```

変更前の比較入力の保存：

```text
Captured unchanged baseline SDF/spec and default/fine Docker argv; fake Docker only.
Original tracked conference files: 3713
```

変更後の対象テスト：

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

全Pythonテストの出力全文：

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
/workspace/thesis-027a2/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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
/workspace/thesis-027a2/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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

## 既存ファイルの保持と実行環境

既存ファイルの変更は上記4ファイルだけ。B0を含む既存結果、地図、world、入力データ、LiDAR仕様、既定のfine_protocol、地図更新・経路計画の処理は変更していない。

```json
{
  "original_files": 3713,
  "changed": [
    "conference/ros2_jazzy/gz_checks/run_lidar_checks.sh",
    "conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py",
    "conference/tapp/sensor_geometry.py",
    "conference/tests/test_real_sensors.py"
  ],
  "unchanged_original_files": 3709,
  "old_results_maps_worlds_data_unchanged": true
}
```

```json
{
  "client_date": "2026-11-10",
  "client_timezone": "Asia/Tokyo",
  "base": "0009471845c506fbee9c3f5242163511ff5cf628",
  "branch": "codex/027a2-camera-fov",
  "scope": "task027 stage A2 steps1-4; Python tests only",
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "platform": "Linux-6.18.57-x86_64-with-glibc2.41",
  "numpy": "2.3.5",
  "scipy": "1.17.0",
  "gazebo_executed": false,
  "docker_executed": false,
  "source_sha256": {
    "conference/ros2_jazzy/gz_checks/run_lidar_checks.sh": "96215e9c8f76de172db1e3f10950af9049de0400bcf2c8dfbdace3e849fd6245",
    "conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py": "cb2c28df142e62e4119ac3e44a1707c427c165be626647f0e2f5cf867f7f583c",
    "conference/tapp/sensor_geometry.py": "7fd490ba7853fb79252ea2257a2c213fcf1dab763dea0e967d3c0599d07cba57",
    "conference/tests/test_real_sensors.py": "1180a0cb6a4b70160f2506c84d3f94fc468dae884cef1aea43813bab9e982650"
  }
}
```

## できなかったこと・研究PCで確認してほしいこと

利用者の指定どおり、Gazebo・実際のDocker・研究PCでの実走は実施していない。PythonのSDF・幾何学・既定出力のテストで確認した。
点群の地面の8〜10cmの差が解消したかは**実測未確認**。原因がintrinsicsであることも、今回のPythonテストだけでは確定しない。
研究PCで段階B0の確認2（点群の向き・高さ）を再実行して確かめる必要がある。新しい高さ誤差や完走率の数値は作っていない。
範囲外の段階B0/Bの実行、別の値の調整、他の条件の変更は行っていない。

## 変更・追加ファイル一覧

- `conference/results/real_sensors/a2/REPORT_ja.md`
- `conference/results/real_sensors/a2/changed_files.txt`
- `conference/results/real_sensors/a2/implementation_commit.txt`
- `conference/results/real_sensors/a2/verification/all_tests_log.txt`
- `conference/results/real_sensors/a2/verification/baseline_sha256.json`
- `conference/results/real_sensors/a2/verification/build_report.py`
- `conference/results/real_sensors/a2/verification/capture_legacy.py`
- `conference/results/real_sensors/a2/verification/capture_legacy_log.txt`
- `conference/results/real_sensors/a2/verification/legacy/default.sdf`
- `conference/results/real_sensors/a2/verification/legacy/depth2.sdf`
- `conference/results/real_sensors/a2/verification/legacy/depth_camera_spec.json`
- `conference/results/real_sensors/a2/verification/legacy/lidar.sdf`
- `conference/results/real_sensors/a2/verification/legacy/real_lidar.sdf`
- `conference/results/real_sensors/a2/verification/legacy/wrapper_args.json`
- `conference/results/real_sensors/a2/verification/planners_before_log.txt`
- `conference/results/real_sensors/a2/verification/preservation_audit.json`
- `conference/results/real_sensors/a2/verification/protocol.json`
- `conference/results/real_sensors/a2/verification/real_sensors_log.txt`
- `conference/results/real_sensors/a2/verification/run_tests.py`
- `conference/results/real_sensors/a2/verification/test_beach_terrain_log.txt`
- `conference/results/real_sensors/a2/verification/test_collision_log.txt`
- `conference/results/real_sensors/a2/verification/test_dstar_log.txt`
- `conference/results/real_sensors/a2/verification/test_endpoint_policy_log.txt`
- `conference/results/real_sensors/a2/verification/test_footprint_log.txt`
- `conference/results/real_sensors/a2/verification/test_geo_log.txt`
- `conference/results/real_sensors/a2/verification/test_gz_compare_log.txt`
- `conference/results/real_sensors/a2/verification/test_gz_online_batch_log.txt`
- `conference/results/real_sensors/a2/verification/test_mapfiles_sim_log.txt`
- `conference/results/real_sensors/a2/verification/test_mission_log.txt`
- `conference/results/real_sensors/a2/verification/test_natural_terrain_log.txt`
- `conference/results/real_sensors/a2/verification/test_online_deadend_log.txt`
- `conference/results/real_sensors/a2/verification/test_online_log.txt`
- `conference/results/real_sensors/a2/verification/test_online_mission_log.txt`
- `conference/results/real_sensors/a2/verification/test_planners_log.txt`
- `conference/results/real_sensors/a2/verification/test_pointcloud_map_fine_log.txt`
- `conference/results/real_sensors/a2/verification/test_pointcloud_map_log.txt`
- `conference/results/real_sensors/a2/verification/test_real_beach_las_log.txt`
- `conference/results/real_sensors/a2/verification/test_real_beach_log.txt`
- `conference/results/real_sensors/a2/verification/test_real_sensors_log.txt`
- `conference/results/real_sensors/a2/verification/test_risk_prior_log.txt`
- `conference/results/real_sensors/a2/verification/test_ros2_gz_log.txt`
- `conference/results/real_sensors/a2/verification/test_summary.txt`
- `conference/results/real_sensors/a2/verification/test_thesis_figures_log.txt`
- `conference/results/real_sensors/a2/verification/test_tour_log.txt`
- `conference/results/real_sensors/a2/verification/test_visibility_log.txt`
- `conference/ros2_jazzy/gz_checks/run_lidar_checks.sh`
- `conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py`
- `conference/tapp/sensor_geometry.py`
- `conference/tests/test_real_sensors.py`

## 追加確認（2026-11-10）

同名ブランチに先に公開されていた実装と報告（`cbf2cae378b9021211b987edf7ca9aa43111eb7c`）を保持した。独立した作業ツリーで `OPENBLAS_NUM_THREADS=1 PYTHONPATH=conference python3 -m tests.test_real_sensors` を再実行し、終了コード0を確認した。追加確認ではコードも既存の結果も変更せず、Gazeboと実コンテナも起動していない。出力全文は `verification/independent_real_sensors_log.txt`。既存の全25モジュールの出力と一覧も確認した。
