022の障害物の粗格子丸めによる過大な通行不可領域を調べるため、障害物だけ0.1mで判定し、そこで半径0.5mの膨張を1回だけ行う方式を追加する。地面・コスト・探索・既存方式は維持する。

**新方式のGazebo実走は未実行**（通常Dockerイメージ不足、起動exit=125）。保存済みの3条件と未実行の新方式を並べた。

## 実装

- `tapp/pointcloud_map_fine.py`：`PointCloudMapFine.update/snapshot/save` と `coarse_overlap`。障害物だけを0.1mで検出し、円盤膨張をその格子で1回だけ行う。地面・特徴量は既存の0.5mの式と保持履歴を維持する。
- `ros2_jazzy/gz_checks/lidar_map.py`：`make_pointcloud_map`、`fine_protocol`、`matched_task022_maps`。既定は022の元のクラスそのもの。新方式は022の実走条件と実走時の標高を再利用する。
- `lidar_planner.py`：既定coarseのROSパラメータを追加し、選択したクラスへ渡す。探索・コスト式・再計画・センサー処理は変えない。
- `lidar_checks.py` と `run_lidar_checks.sh`：`--map fine` を追加。省略/明示coarseの既定値とmanifestは維持する。fineでは同一地点・順番・初期配置、メッシュ、0.3倍速、期限1.0秒を使う。
- `experiments/lidar_fine_report.py`：`map_audit`、`box_footprints`、`evaluation_maps`、`summary_table`、`summarize`。保存済み3条件の30行と新方式10行を並べ、観測済みマスクのFP/FN、箱への隣接、更新時間、接触を集計する。
- `tests/test_pointcloud_map_fine.py`：平地、0.02m測距雑音付きの箱、中心の保持、膨張の幾何・再観測・追加シード、保存、旧方式のバイト一致、manifestとDocker引数、4条件の欠測と旧値の保持を確認する。
- `tasks/023_lidar_fine_grid.md`：今回の利用者の指示内容を同じブランチに保存した。

## 方法と固定値

0.1m・高さ0.3m・3点・半径0.5mは指示書で事前指定された値として固定し、変更・選択・調整していない。
新方式ではこれらと異なる設定を拒否する。点群の登録・範囲除外・古い地面の双線形補間は022と同じで、真値ラベルを観測に流用しない。

0.5mセルを境界に合わせて5×5の0.1mセルに分ける。地面の高さは従来どおり粗セル内の直近64点の中央値。
判定もこの同じ履歴の中で細セルIDを区別する。履歴の長さや保持期間を新たに延ばしていない。
したがって、地面・傾斜・凸凹・コスト・観測済みマスクの計算は同じで、細分化するのは障害物の位置と証拠だけである。

検出した細セルを半径5細セルの円盤で膨張し、その後5×5内に膨張セルが1つでもある粗セルを通行不可にする。
粗セルへまとめたマスクは再膨張させない。追加の観測では新しい生の障害物の膨張との和を取り、膨張済みマスクを入力にしない。
既存の岩の膨張は1回のまま、急斜面は変更していない `footprint.inflate_steep` を使う。
セルの「重なり」は領域の重なりであり、距離の検証も細セル領域と粗セル領域との最小距離で行う。セル中心の距離ではない。

新しい方式のNPZは、従来のelev/seen/obstacle/cost/lethalに加え、細格子の検出・膨張マスクをpackbitsで保存する。
地図更新の公開APIは元と同じ。TA*・TA*-Sのコスト式や探索ロジックを変更していない。

## 実走条件

021と022の10地形・world・地点・順番・スタートを共用する。メッシュの見た目とheightmapの衝突、0.3倍速と途切れ期限1.0秒をmanifestに明記した。
fineの場合は、環境変数でこれらと異なる条件を指定すると停止する。LiDARの仕様、取り付け位置、測距雑音も022の実走と同じ設定だけを受け付ける。

ライブラリ版の差で漂着物の標高のビットが変わる問題を避けるため、新しいworldには022の実走時の評価用標高配列を使う。
生の障害物・水・欠損マスクと、通行不能マスクの一致を検査し、開始点・目的地をずらさない。
旧worldファイルそのものは一時領域にしか残っていないためSDF全体のバイト比較は未実施だが、同じ入力標高・マスクと既存のエクスポーター/メッシュ生成処理を使う。
world/入力地図とbuild/installは一時領域に作り、既存の結果は更新しない。

## コマンドとテスト全文

```bash
cd conference
python3 -m tests.test_planners
python3 -m tests.test_pointcloud_map_fine
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only --patch-count 10 --map fine --output results/lidar_fine
python3 experiments/lidar_fine_report.py
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/lidar_fine/physical_10 --patch-count 10 --map fine
python3 results/lidar_fine/verification/run_tests.py
python3 -m tests.test_pointcloud_map_fine
python3 results/lidar_fine/verification/plot_fixture.py
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
/workspace/thesis-023/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ python3 -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: independent full disk, repeated/additive seeds, rectangle-distance radius bound, packed save passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:163: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
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
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

```text
/workspace/thesis-023/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: independent full disk, repeated/additive seeds, rectangle-distance radius bound, packed save passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)
```

## 集計表（そのまま）

```text
Task023: fixed / perfect R10 / task022 LiDAR / fine-grid LiDAR; identical ten-beach cohort.
First three methods are cached measurements. New fine-grid physical outcomes are 未実行 when missing.
       patch   mode    status map_seen_cells map_lethal_cells truth_lethal_cells map_fp_cells map_fn_cells map_fp_box_adjacent_cells detected_obstacle_cells detector_fp_cells detector_fn_cells detector_fp_box_adjacent_cells  map_update_s_median  map_update_s_p95  map_update_s_max debris_cells
08OB86_00294  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB86_00294 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB86_-0205  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB86_-0205 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB87_-0706  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB87_-0706 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-1417  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-1417 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB88_-0167  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_-0167 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_00332  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_00332 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_01832  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB88_01832 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_00152  fixed  rollover           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_00152 online  rollover           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_-0347  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB89_-0347 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            0
08OB89_-0847  fixed     stuck           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            2
08OB89_-0847 online completed           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN            1
08OB86_00294  lidar completed          79882            19909              18975          939            5                        25                     760               601                 1                            404            0.0838974          0.156605          0.594992            0
08OB86_-0205  lidar completed          39575             7837               6888          958            9                        39                     752               601                 1                            370            0.0886842          0.117759          0.280268            0
08OB87_-0706  lidar completed          75398            10179               8480         1725           26                        31                    1448              1119                 0                            752             0.086177          0.173824          0.580021            0
08OB88_-1417  lidar   no_path          19490             1064                691          374            1                        19                     333               249                 2                            180            0.0849492          0.120034          0.408273            0
08OB88_-0167  lidar   no_path          58426             7273               5139         2149           15                        11                    1106               895                 1                            567            0.0878073            0.1176          0.732807            0
08OB88_00332  lidar completed          39025             9148               6980         2180           12                        22                    1233              1014                 1                            633            0.0991531          0.134696          0.309379            0
08OB88_01832  lidar  rollover          43762             1878                147         1737            6                         8                     157               113                 0                             78             0.081546          0.120131          0.306029            0
08OB89_00152  lidar  rollover          27105             2583                255         2335            7                         0                     293               234                 0                            157            0.0852749          0.125799          0.565805            0
08OB89_-0347  lidar   no_path          44732             1824                765         1070           11                        12                     779               600                 1                            403            0.0948189           0.12949          0.684387            0
08OB89_-0847  lidar   no_path          31921            11593              10378         1218            3                         6                     866               711                 0                            454             0.095285          0.129591          0.757749            0
08OB86_00294   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB86_-0205   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB87_-0706   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_-1417   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_-0167   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_00332   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB88_01832   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_00152   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_-0347   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None
08OB89_-0847   fine       未実行           None             None               None         None         None                      None                    None              None              None                           None                  NaN               NaN               NaN         None

Counts and per-run metric medians; all contact counts use recorded centre trajectories.
  mode execution  scheduled  executed  unexecuted  completed  stuck  rollover  no_path  timeout  runtime_error  incomplete_waypoints  debris_audited_runs  debris_touching_runs  map_seen_cells_median  map_lethal_cells_median  truth_lethal_cells_median  map_fp_cells_median  map_fn_cells_median  map_fp_box_adjacent_cells_median  clearance_fp_cells_median  clearance_fn_cells_median  detected_obstacle_cells_median  truth_obstacle_cells_median  detector_fp_cells_median  detector_fn_cells_median  detector_fp_box_adjacent_cells_median  detector_on_unusable_cells_median  map_update_s_median_median  map_update_s_p95_median  map_update_s_max_median
 fixed      記録あり         10        10           0          0      9         1        0        0              0                     0                   10                     3                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
online      記録あり         10        10           0          9      0         1        0        0              0                     0                   10                     2                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
 lidar      記録あり         10        10           0          4      0         2        4        0              0                     0                   10                     0                41668.5                     7555                     6013.5               1471.5                    8                              15.5                       1388                         30                           769.5                        157.5                       601                         1                                  403.5                              161.5                   0.0869922                 0.127645                 0.572913
  fine       未実行         10         0          10        NaN    NaN       NaN      NaN      NaN            NaN                   NaN                    0                   NaN                    NaN                      NaN                        NaN                  NaN                  NaN                               NaN                        NaN                        NaN                             NaN                          NaN                       NaN                       NaN                                    NaN                                NaN                         NaN                      NaN                      NaN
Map FP/FN use unique seen cells against original truth lethal; CSV also reports same-steep-clearance FP/FN.
Detector FP/FN compare uninflated detections to raw obstacles, excluding water/nodata; these differ from final lethal FP/FN.
Box adjacency is one four-connected cell outside the actual exported component bounding rectangles.
Missing task021 map snapshots are unrecorded, not zero. New fine-grid values are not inferred from fixtures.
Grid=0.1m, height threshold=0.3m, cluster=3, radius=0.5m were fixed in advance; no tuning or hypothesis tests.
```

## 指標

`map_*` は最終lethalを元のtruth lethalと比較した、観測済みの一意な粗セルでのFP/FNである。
CSVの `clearance_*` には、真値にも同じ急斜面の膨張を入れた参照とのFP/FNを併記する。意図した安全余裕まで誤りと解釈しないためである。

`detector_*` は膨張前の検出を生の障害物と比較した指標で、水・欠損を除く。既に事前地図にある障害物も含むため、点群検出器の見落としと最終lethalの見落としは同じではない。
箱の領域はexport_gazeboと同じ連結成分の外接長方形。その外側で4方向に1粗セルだけ隣接する領域を `*_box_adjacent_cells` とする。
022の約7割という原因分析は主に膨張前の検出についてのものなので、最終lethalのFPと区別して表示する。

021の2条件には最終の点群地図スナップショットがないため、地図誤りの欄は未記録とし、0を入れない。
観測した範囲は走行ごとに異なる。件数だけで精度の優劣を断定しない。
漂着物への接触は記録された中心軌跡によるため、車体前端の接触を過少評価する。
地図更新時間は走行ごとの中央値・95%・最大と、その走行単位の集計であり、計画時間とは別である。

## 未実行と限界

**新しいfine方式のGazebo実走は未実行**。通常のDockerラッパーは標準イメージ `thesis/jazzy-gz:1` がなくexit=125で終了した。
新方式の完走・経路なし・誤検出・見落とし・更新時間・接触の実測値はない。表の空欄/NaNを0として扱わない。
合成箱の外側セルが減った結果を、10地形の完走率改善や実機の安全性へ置き換えていない。

細セル内に3点を要求するため、疎な物体や側面の検出を落とす可能性がある。逆に、同じ場所の雑音が繰り返し蓄積すれば外側の細セルが検出される場合もある。
中央値の高さによる急斜面や誤った地面高さ、古い地面基準の限界、観測されない場所のsoft prior、地図境界の転倒は今回変更していない。
細格子化のCPU・メモリ負荷と、点群の取りこぼしも実走では未評価である。

Claudeには、READMEのコマンドで新方式だけを走らせ、022と同じworld/地点/設定を確認した上で、通路の閉塞、見落とし、箱の隣のFP、更新時間、取りこぼしを確認してほしい。
10地形の検定・エネルギー集計は行わない。境界の転倒を除外したり、地点・パラメータを変えて結果を良くしたりしていない。

変更一覧・入力/保持の監査・合成図は [REPORT_ja.md](https://github.com/tako-1012/thesis_Bunker/blob/codex/023-lidar-fine-grid/conference/results/lidar_fine/REPORT_ja.md)。
