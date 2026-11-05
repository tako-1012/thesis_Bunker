点群から0.5m地図を作って既存の非同期再計画に渡す処理と、VLP-16相当の模型・3→10地形の実行手順を追加した。

**実走は未実行**（Dockerイメージ不足、起動exit=125）。022は試験的な指示書のため、点群処理とスクリプト・ROS2不要のテストまで完了した。

## 実装

- `tapp/pointcloud_map.py`：`decode_xyz`、`transform_points`、`PoseBuffer.add/at`、`PointCloudMap.update/snapshot/save`。PointCloud2互換バッファのデコード、時刻付き姿勢のSO(3)補間、6自由度の座標変換、0.5mセルの中央値融合、観測済みマスク、事前高さを基準にした障害物検出、既存式による傾斜・凸凹・コストと0.5m膨張。
- `thesis_bunker_gz/model.py`：LiDARなしを既定に保つキーワード引数を追加。`lidar.py` に設定とgpu_lidar生成を置き、通常と質量指定の既存SDFのバイト一致を検証した。
- `lidar_bridge.yaml`：PointCloudPackedをROS2のPointCloud2へ渡す。既存bridgeは変更していない。
- `lidar_runtime.py`：`LidarOnlineMission._plan_work/_join`。021の非同期計画・経路引き継ぎを再利用し、観測の両箇所を点群由来に置換。truthはNoneで、virtual_senseを呼ばないことをテストした。
- `lidar_planner.py`：真値地図をロードせず、古い地図・点群・点群時刻のground_truth姿勢だけを使うROS2ノード。別ワーカー、最新1走査の待ち行列、時刻不一致の拒否、センサー停止要求、全探索と地図更新の記録を追加した。
- `lidar_checks.py` と `run_lidar_checks.sh`：021の保存済みの10地形・地点・順番を共有し、最初の3か所から10か所へ広げる。world/入力地図/colconは一時領域。実走時の解析用参照配列を保存する。
- `experiments/gz_lidar_report.py`：`map_quality/tables/summarize`。021の20行の保存値とLiDARの10行を並べ、同じ走行項目、最終観測セルの高さ誤差、地図更新時間を集計する。欠測はNone/NaN/空欄のまま、検定・エネルギー集計は行わない。
- `tests/test_pointcloud_map.py`：平地、箱、未知セル、座標・時刻・データ形式、既存模型、真値を使わないワーカーと経路引き継ぎ、誤差集計、保存済み対照の不変性を確認する。
- `experiments/pointcloud_validation.py`：事前固定した設定でvalidation12地形の人工入力を監査する。パラメータを選択・調整するスクリプトではない。

## 仕様と仮定

利用者から示されたVLP-16の公称値に合わせ、16本、垂直−15°〜+15°を2°刻み、水平360°、10Hzとした。
水平方向1800サンプル、最小距離0.1m、距離の刻み0.01m、平均0・標準偏差0.02mのGaussian測距雑音は未校正の模型の仮定である。
最大距離30mは指示書の条件を維持し、0.5m地図での近傍再計画を扱う試験として描画・処理量を抑えるための上限とした。
実機の100mを検証した値でも、testの成績から最適化した距離でもない。R10対照とは範囲も異なり、遮蔽だけの効果の比較にはならない。

取り付け高さ0.8mは実測値不明のため、017に合わせた仮定である。モデル原点（平地での接地時は地面付近）から車体z方向に測る。
base_linkの原点が0.35mなので、センサーの局所zは `height-0.35` とする。傾斜で地面から常に鉛直0.8mという意味ではない。
`--sensor-height-m` で変更でき、モデルと座標変換に同じ値を渡す。水平の取付位置はモデル中央、姿勢は車体と同じという仮定である。

漂着物の高さ判定0.3mは、017の仮定の流木高さを参考に事前固定した未校正の仮定である。
古い地図の高さの双線形補間より0.3m以上高い点が同じセルに3点以上ある場合に検出する。
実測の地面分離ではなく、地形変化・位置誤差を障害物と誤認することもある。testで閾値や半径を調整していない。
セルの高さは直近64点の中央値で、障害物上面しか見えなければ地面ではなく上面を表す。
既に検出した障害物は保持し、移動物体が去った後の除去や光線による空き領域の推定は行わない。

点のないセルは未知のままで、特徴量の周辺再計算・膨張をしても観測済みに昇格させない。
未知部分は021と同じsoft priorに依存するため、未観測の危険箇所へ進むことはありうる。
時刻の合う姿勢がない点群は使わず、真値ラベルや最新姿勢で穴埋めしない。最大距離で飽和した返り値も地形にしない。
実機の発光順、走査中の運動歪み、反射率・水面・欠測の特性は再現していない。
017は地表セルへ直接視線を調べるモデルであり、今回の疎な上下方向の走査線とは観測条件が違う。

## コマンドとテスト全文

```bash
cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map
python3 experiments/pointcloud_validation.py
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 3 --output results/gazebo_lidar
python3 experiments/gz_lidar_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/gazebo_lidar/physical_3 --patch-count 3
python3 results/gazebo_lidar/verification/run_tests.py
```

```text
all planner tests passed
roll-aware tests passed
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
/workspace/thesis-022/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

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

## 集計表（そのまま）

```text
Task022: task021 fixed/R10 controls plus LiDAR, ten identical LAS scenarios; descriptive only.
Controls are cached task021 physical measurements. Unknown LiDAR outcomes remain blank/None/NaN.
       patch   mode       planner planning_status    status recorded_status completed data_source error goals_reached lethal_cells debris_cells n_replans  elapsed_s  deviation_mean_m  deviation_max_m  roll_p95_deg  roll_max_deg  pitch_p95_deg  pitch_max_deg  plan_s_median  plan_s_p95  plan_s_max returned_to_start n_plans calls_over_1s deviation_samples out_of_bounds_samples rolled_over  rollover_t_s  rollover_elapsed_s  rollover_x_m  rollover_y_m  selected height_cells height_abs_error_median_m height_abs_error_p95_m height_abs_error_max_m map_update_s_median map_update_s_p95 map_update_s_max map_updates map_failed_updates queue_drops sim_to_wall_ratio sensor_error
08OB86_00294  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0       29.2         0.0652804         0.612124       4.49186       8.22018        5.59533        8.97691       0.131676    0.257081    0.283574             False       6             0               585                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_00294 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       106    473.408         0.0376759          1.05408       3.91119        6.6159        5.04514        17.9686      0.0776092     0.29242    0.733161              True     112             0              9465                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_-0205  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            1            1         0       64.7          0.129093          0.62619        4.9228       9.68489         4.7532        10.4313      0.0684066    0.101999      0.1069             False       6             0              1295                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_-0205 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0        92    244.199         0.0591287          1.00063       4.82593       11.2399        6.09306        11.2888       0.069355    0.134001    0.261372              True      98             0              4881                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB87_-0706  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0      42.45         0.0381514         0.446409       2.72025       6.16175        4.55938        6.67419       0.114647    0.447735    0.513411             False       6             0               849                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB87_-0706 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       105     458.65         0.0448017          1.53707       3.60804        18.629        5.08675        19.5165       0.110614    0.617138     1.04776              True     111             2              9170                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-1417  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0     19.652          0.460207         0.611346       4.28389       5.30703        4.31249        4.31769      0.0646924    0.122185    0.123105             False       6             0               394                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-1417 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            1            1       103     299.45         0.0413632         0.813067       5.09445       18.8408        4.60072        18.6673      0.0593737    0.157099    0.182353              True     109             0              5985                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-0167  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            0            0         0     119.15         0.0257854         0.569815       2.92837        5.2383        3.42202         5.7893       0.132403    0.223228    0.225747             False       6             0              2384                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_-0167 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5           27            0       304    612.901           0.10154          4.03871         7.394       42.9836        8.88529        52.4828      0.0785826    0.384144    0.567933              True     310             0             12256                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_00332  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            0            0         0     51.549         0.0682241         0.574867       3.51936       4.69489        10.4422        14.4091      0.0377247   0.0866617   0.0977732             False       6             0              1031                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_00332 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       185     241.85         0.0604261         0.967311       5.48962       9.31724          6.885        14.4478      0.0452776   0.0907293    0.192564              True     191             0              4833                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_01832  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            0            0         0    251.401         0.0329133         0.350719       3.40124       8.21047        3.13815        15.0864       0.102191    0.218828    0.253852             False       6             0              5028                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB88_01832 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0        90      427.4         0.0316318          1.05007       2.88807       7.20092        3.22917        11.9953       0.106325    0.868195     1.15409              True      96             1              8542                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_00152  fixed TA*-S+inflate         planned  rollover           stuck     False      gazebo   NaN             2            0            0         0    110.249          0.163156          2.68832       90.0564       178.441        7.74643        15.7963       0.140243     0.52322    0.541079             False       6             0              2206                   242        True       103.851                98.8       100.112       199.653      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_00152 online TA*-S+inflate         planned  rollover         no_path     False      gazebo   NaN             2            0            0        14     100.45           0.15281          1.34311       22.1221       172.636        6.81007        41.9431       0.115844    0.361512    0.361652             False      17             0              2003                   161        True         105.2              100.15        99.631       199.564      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0347  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             0            1            1         0      37.25         0.0893584         0.349333       3.65141       4.14532        3.44566        4.78677      0.0917351      0.1884    0.196287             False       6             0               745                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0347 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            0            0       130    385.849         0.0373097          1.18912        3.8667        7.5727        4.99498        9.37978      0.0879499    0.195575    0.319513              True     136             0              7713                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0847  fixed TA*-S+inflate         planned     stuck           stuck     False      gazebo   NaN             1            2            2         0     126.75         0.0282698         0.497471       4.60119       7.53312         3.6828        8.49752       0.110015    0.203834    0.215019             False       6             0              2535                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB89_-0847 online TA*-S+inflate         planned completed       completed      True      gazebo   NaN             5            1            1       303      421.6         0.0394325         0.709465       3.33601       7.59398        3.68824        13.6144       0.112321     0.27778    0.386705              True     309             0              8428                     0       False           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None          NaN
08OB86_00294  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB86_-0205  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB87_-0706  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN      True         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_-1417  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_-0167  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_00332  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB88_01832  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_00152  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_-0347  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None
08OB89_-0847  lidar TA*-S+inflate         planned       未実行            None      None        None                None         None         None      None        NaN               NaN              NaN           NaN           NaN            NaN            NaN            NaN         NaN         NaN              None    None          None              None                  None        None           NaN                 NaN           NaN           NaN     False         None                      None                   None                   None                None             None             None        None               None        None              None         None

Counts use actual recordings; selected is the requested 3/10 LiDAR rollout stage.
  mode  scheduled  selected  executed  unexecuted  completed  stuck  rollover  timeout  no_path  incomplete_waypoints  runtime_error  goals_reached_median  lethal_cells_median  debris_cells_median  n_replans_median  elapsed_s_median  deviation_mean_m_median  deviation_max_m_median  roll_p95_deg_median  roll_max_deg_median  pitch_p95_deg_median  pitch_max_deg_median  plan_s_median_median  plan_s_p95_median  plan_s_max_median height_cells_median height_abs_error_median_m_median height_abs_error_p95_m_median height_abs_error_max_m_median map_update_s_median_median map_update_s_p95_median map_update_s_max_median map_updates_median map_failed_updates_median queue_drops_median sim_to_wall_ratio_median
 fixed         10        10        10           0          0      9         1        0        0                     0              0                   0.5                    0                    0                 0           58.1245                0.0667522                0.572341              3.96765              6.84744               4.43593               8.73722              0.106103           0.211331           0.220383                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None
online         10        10        10           0          9      0         1        0        0                     0              0                     5                    0                    0             105.5           403.725                0.0430825                 1.05207              4.36856              10.2786               5.06595               16.2082             0.0832662             0.2851           0.374179                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None
 lidar         10         3         0          10        NaN    NaN       NaN      NaN      NaN                   NaN            NaN                   NaN                  NaN                  NaN               NaN               NaN                      NaN                     NaN                  NaN                  NaN                   NaN                   NaN                   NaN                NaN                NaN                None                             None                          None                          None                       None                    None                    None               None                      None               None                     None

Method minus reference; only both completed physical tours; no hypothesis tests or energy.
method reference           metric  paired_completed delta_median
online     fixed    goals_reached                 0         None
online     fixed     lethal_cells                 0         None
online     fixed     debris_cells                 0         None
online     fixed        n_replans                 0         None
online     fixed        elapsed_s                 0         None
online     fixed deviation_mean_m                 0         None
online     fixed  deviation_max_m                 0         None
online     fixed     roll_p95_deg                 0         None
online     fixed     roll_max_deg                 0         None
online     fixed    pitch_p95_deg                 0         None
online     fixed    pitch_max_deg                 0         None
online     fixed    plan_s_median                 0         None
online     fixed       plan_s_p95                 0         None
online     fixed       plan_s_max                 0         None
 lidar     fixed    goals_reached                 0         None
 lidar     fixed     lethal_cells                 0         None
 lidar     fixed     debris_cells                 0         None
 lidar     fixed        n_replans                 0         None
 lidar     fixed        elapsed_s                 0         None
 lidar     fixed deviation_mean_m                 0         None
 lidar     fixed  deviation_max_m                 0         None
 lidar     fixed     roll_p95_deg                 0         None
 lidar     fixed     roll_max_deg                 0         None
 lidar     fixed    pitch_p95_deg                 0         None
 lidar     fixed    pitch_max_deg                 0         None
 lidar     fixed    plan_s_median                 0         None
 lidar     fixed       plan_s_p95                 0         None
 lidar     fixed       plan_s_max                 0         None
 lidar    online    goals_reached                 0         None
 lidar    online     lethal_cells                 0         None
 lidar    online     debris_cells                 0         None
 lidar    online        n_replans                 0         None
 lidar    online        elapsed_s                 0         None
 lidar    online deviation_mean_m                 0         None
 lidar    online  deviation_max_m                 0         None
 lidar    online     roll_p95_deg                 0         None
 lidar    online     roll_max_deg                 0         None
 lidar    online    pitch_p95_deg                 0         None
 lidar    online    pitch_max_deg                 0         None
 lidar    online    plan_s_median                 0         None
 lidar    online       plan_s_p95                 0         None
 lidar    online       plan_s_max                 0         None
Height errors: absolute errors in the final unique hit cells; median return surface versus truth DEM.
Mapping times include PointCloud2 decoding, registration, fusion and feature recomputation; not planning/ROS handoff.
R10 control and 30m LiDAR differ in range/beam sparsity/occlusion/noise; this is not an isolated occlusion comparison.
Keep 08OB89_00152: task021 rollover is a map-boundary artifact, not a measured planner effect.
```

## 高さ・地図更新時間

LiDARの実測は未取得。以下はvalidation12地形のセル中心から作った密な人工入力の監査であり、走査線・遮蔽・動力学を省いている。設定の選択・調整はしていない。

```text
VALIDATION ONLY: dense artificial DEM returns, not Gazebo/VLP-16 measurements; no tuning.
                             source        patch  observed_cells  error_median_m  error_p95_m  update_s  input_points
validation_dense_artificial_returns 08OB87_-0206           11086     0.000352349   0.00193533  0.384788         33258
validation_dense_artificial_returns 08OB88_01332           11250     0.000377498   0.00221333  0.281524         33750
validation_dense_artificial_returns 08OB89_-1597            9887     0.000330137   0.00274032  0.241511         29664
validation_dense_artificial_returns 08OC90_00270           10081     0.000351986   0.00212163  0.236031         30243
validation_dense_artificial_returns 08OC91_00811           11256     0.000263028    0.0020687  0.267921         33768
validation_dense_artificial_returns 08OC93_-1519           11144     0.000323986   0.00191017  0.274128         33435
validation_dense_artificial_returns 08OC95_-0321           11260     0.000308378   0.00232001  0.320561         33780
validation_dense_artificial_returns 08OC96_-0676            8818     0.000491998   0.00334322  0.226692         26454
validation_dense_artificial_returns 08OC97_-0077           11261     0.000318206   0.00206651  0.286032         33783
validation_dense_artificial_returns 08OC98_-1101           10647     0.000383787   0.00225024  0.269964         31941
validation_dense_artificial_returns 08OC98_01898           10299     0.000542452   0.00259834  0.259226         30897
validation_dense_artificial_returns 08OC99_00983            9802      0.00040039    0.0021909  0.245144         29409
```

## 未実行と限界

優先順位(1)の点群処理とROS2なしのテストは完了した。(2)のGazebo3か所と(3)の10か所は未実行である。
通常Dockerの起動は標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了し、Gazebo・colconは開始していない。
ホストにパッケージを追加せず、特殊な名前空間やchrootによる実行も行っていない。
LiDARの場合の完走・接触・転倒・計画時間・実測の高さ誤差・実測の地図更新時間は測れていない。
以下の人工入力の数値をLiDARの実測欄に埋めていない。

Claudeには、通常Dockerでまず3か所を走らせ、PointCloud2のtopic/frame/timestamp、模型の局所座標、ground_truthとの時間整合、
ogre2の画面なし描画、実際の戻り点の密度、待ち行列の取りこぼし、0.5シミュレーション秒のセンサー停止期限を確認してほしい。
実走できた場合にのみ、新しい保存先で10か所へ広げる。処理・探索の壁時計時間と、Gazeboの進行速度を分けて読む必要がある。
模型のmu2=0.1や急旋回による転倒は残りうる。中心軌跡の接触数は車体前端の接触を過少評価する。
021で両条件が転倒した `08OB89_00152` は地図境界の問題として除外せず注記している。
完全な点群ストリームは保存せず、最初の点群と各処理入力のSHA-256、最終地図、更新ログを残すため、全走査の再生はできない。

021との標高SHAはNumPy環境で異なったが、LAS・事前高さ・マスクは一致した。元の値を更新せず、新しい実走の評価用配列を保存して正確な入力で高さを評価する。

変更一覧・全環境・入力監査は [REPORT_ja.md](https://github.com/tako-1012/thesis_Bunker/blob/codex/022-gazebo-lidar/conference/results/gazebo_lidar/REPORT_ja.md)。
