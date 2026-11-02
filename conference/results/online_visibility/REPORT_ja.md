# 指示書017 実装報告

ブランチ: `codex/017-visibility`。土台: `b4c92a1` (`realtime-map`)。016を継承せず、マージしない。

半径内の全セルを完全に観測する014のセンサーを、地形による影を考慮するモデルと比較した。
全48砂浜・2事前地図・4センサー条件の384走行を実行した。半径対照は014の96走行と成功・計画回数・再計画回数・接触数が完全一致し、dJの最大絶対差は0だった。

## 実装

- `tapp/visibility.py`: `visible_cells` / `virtual_sense_los`。`segment_cells` と同じ全通過セルを列挙し、途中セル中心を視線へ射影した地点の高さで遮蔽を判定する。半径外を見せない。
- `run_visibility_mission`: 014の観測位置丸め・1mごとの移動・発火/接合・6倍打切りを保ち、観測マスクだけを変える。見えないセルは既知にせず、蓄積済みの知識を保持する。
- 岩の隆起は既に `build_real` の標高に含まれるので二重に加えない。標高に高さのない流木の膨張前マスクにだけ、仮定の0.3mを足す。水・欠損・安全余白を含む `tm.rock` を遮蔽物の高さには使わない。追加キーワード `rock_mask` で生のマスクを渡す。
- `experiments/online_visibility.py`: 014と同じLASシナリオ・5点・巡回順・oracle分母。半径10mで陰なしと0.5/0.8/1.2mを比較する。高さは全て仮定で、test結果から選定しない。
- `experiments/audit_visibility.py`: 同じセルへの初回侵入を抽出し、その前の知識・可視性・急斜面/障害物マスクを照合する。既に侵入したセルから出る際の接触を、既知の危険への新規侵入と混同しない。
- `tests/test_visibility.py`: 平地、壁、高さによる可視集合の包含、戻り値、元の半径対照との軌跡/回数一致、接触監査。
- `README_ja.md`: 仮定、コマンド、出力の意味。`contact_*.png` は実行した接触例。`traces/`, `observations/`, `contact_details/` は軌跡・毎観測の割合・侵入時状態。

## 結果と原因

接触があったのは高さ0.5mだけ。初回侵入は8砂浜・8走行・10セルで、全て `known_before=False`, `visible_last=False`, `cause=occluded` だった。
再生成したtruthで全て急斜面セルであることを確認した。影でtruthの通行不可が分からないセルに、従来どおりsoft priorを使って進むことで侵入した。
6走行は接触しても最後まで到達しており、完走と安全は別に確認する必要がある。

0.8m・1.2mでは今回の条件の接触はなかった。0.8mで両条件完走の対のdJ差の中央値はcoarseで0.947752ポイント、staleで0.172516ポイントだった。条件別の完走喪失・新規完走・悪い側の差も下の表に残す。
可視割合は失敗走行も含む全観測を連結した中央値。各走行の中央値の中央値ではない。dJは完走時だけで、接触は失敗走行も監査した。

### 修論の限界の節に使う文章

「半径内を完全に観測できる」という条件に対し、DEMによる遮蔽を入れると、低いセンサーでは未観測の急斜面への接触が発生した。
 仮定した0.8mでは本データの接触はなかったが、地形コストの差は悪化した。本実験は0.5mの補完済み標高を使う離散モデルで、実際のLiDARの走査・反射・測距誤差、連続地形、動的な物体、計画遅延や追従物理を検証していない。
高さと流木の高さは実測の校正値ではない。従来の接触ゼロという結果は、観測条件を明示して解釈する必要がある。

計画時間は探索と平滑化だけで、視線計算・地図組立を含まない。総時間は `runtime.json`。CPU負荷に依存する時間を実機の応答保証とは扱わない。
Claudeには、通過セル中心を射影する離散遮蔽の近似、流木高さの仮定、初回侵入と退出時の接触の区別、限界の文章を確認してほしい。

## 実行環境とコマンド

Python `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`、NumPy `2.3.5`、SciPy `1.17.0`、Pandas `2.2.3`。
実行ファイル `/tmp/thesis-apt-compat/bin/python`、Matplotlib/cacheは `/tmp`、BLAS 1スレッド、実験4ワーカー。

```bash
cd conference
python3 -m tests.test_planners  # 変更前
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_mapfiles_sim
python3 -m tests.test_mission
python3 -m tests.test_natural_terrain
python3 -m tests.test_online
python3 -m tests.test_online_mission
python3 -m tests.test_planners
python3 -m tests.test_real_beach
python3 -m tests.test_real_beach_las
python3 -m tests.test_risk_prior
python3 -m tests.test_ros2_gz
python3 -m tests.test_tour
python3 -m tests.test_visibility
python3 experiments/online_visibility.py --workers 4
python3 experiments/audit_visibility.py
```

## 変更前プランナーテストの出力全文
```text
all planner tests passed
roll-aware tests passed
```

## 全15テストの出力全文
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

$ python3 -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0
```

## 実験の集計表（出力そのまま）
```text

Test: task-014 tours, R10; sensor/obstacle heights are assumptions
     prior   sensor  runs  completed  too_long  touching  debris_touching  dJ_median  dJ_p90  dJ_max  replans_median  replans_max  plan_calls  plan_s_median  plan_s_p95  plan_s_max  visible_fraction_median
coarse c10   radius    48         45         3         0                0     4.2116 27.6546 58.1804           181.5          443        9347      0.0338989    0.214052    0.617529                        1
coarse c10 LOS h0.5    48         45         2         6                0    6.58038 50.6507 87.9287           181.5          373        9413      0.0329212    0.184331    0.648725                 0.929992
coarse c10 LOS h0.8    48         46         2         0                0    5.40638 45.1416 81.2774             190          417        9784      0.0329725    0.198266    0.623101                 0.979615
coarse c10 LOS h1.2    48         46         2         0                0    4.31989 39.0019  70.039             188          385        9523      0.0322046    0.174012    0.618155                 0.996022
     stale   radius    48         46         2         0                0   0.945069 6.60292 22.8123            94.5          224        5428      0.0319496    0.182882    0.618836                        1
     stale LOS h0.5    48         46         2         2                0     1.3719 7.70953 36.3317            92.5          237        5592      0.0316194     0.18155    0.633089                 0.838504
     stale LOS h0.8    48         46         2         0                0    1.16265  7.0726 35.8381              96          224        5587      0.0328615    0.184374    0.685261                 0.926014
     stale LOS h1.2    48         46         2         0                0    1.16535 7.09318 28.9627              97          228        5547      0.0330384    0.180476    0.665912                 0.968974
Radius control: scenario identities, outcomes, plan/replan/contact counts and dJ match task 014.

LOS minus radius-control dJ; paired completed runs only, completion losses reported separately
     prior   sensor  paired_completed  completed_lost  newly_completed  delta_median  delta_p90  delta_max
coarse c10 LOS h0.5                44               1                1       1.36657    20.8139    41.4519
coarse c10 LOS h0.8                45               0                1      0.947752    12.0621    34.5992
coarse c10 LOS h1.2                45               0                1      0.108124    6.65766    31.0182
     stale LOS h0.5                46               0                0      0.439088    1.74441    14.1416
     stale LOS h0.8                46               0                0      0.172516    2.47329    13.0257
     stale LOS h1.2                46               0                0     0.0319652    2.14855    12.1538

Contact cases (includes failed tours)
       patch  side_m  seed      prior  radius_m   sensor  success   reason  n_plans  n_replans  lethal_cells  debris_cells  oracle_J  visible_fraction_median  observations       J      dJ
08OB88_-0167     200     0 coarse c10        10 LOS h0.5    False  no_path      166        164             3             0   1252.46                 0.768496           255     NaN     NaN
08OB89_-0347     200     0 coarse c10        10 LOS h0.5     True               185        179             1             0   885.943                 0.949483           504 1013.81 14.4324
08OC80_00660     200     0 coarse c10        10 LOS h0.5     True               249        243             1             0     925.9                 0.887033           511 1029.27 11.1644
08OC95_00928     200     0      stale        10 LOS h0.5     True                99         93             1             0   861.169                   0.8572           458 1030.51 19.6646
08OC97_-0577     200     0 coarse c10        10 LOS h0.5     True               214        208             1             0   795.861                 0.712808           491 1304.89 63.9595
08OC98_00148     200     0 coarse c10        10 LOS h0.5     True               234        228             1             0   815.468                 0.960223           467  955.11 17.1242
08OC99_00483     200     0 coarse c10        10 LOS h0.5     True               204        198             1             0   885.828                 0.833731           409 979.876  10.617
08OC99_01733     200     0      stale        10 LOS h0.5    False too_long      109        107             1             0   1451.17                 0.505171           257     NaN     NaN

Contact cause at the last observation (cell counts may overlap across causes)
       patch      prior   sensor         cause  unique_cells
08OB88_-0167 coarse c10 LOS h0.5 already_known             2
08OB88_-0167 coarse c10 LOS h0.5      occluded             3
08OB89_-0347 coarse c10 LOS h0.5 already_known             1
08OB89_-0347 coarse c10 LOS h0.5      occluded             1
08OC80_00660 coarse c10 LOS h0.5 already_known             1
08OC80_00660 coarse c10 LOS h0.5      occluded             1
08OC95_00928      stale LOS h0.5 already_known             1
08OC95_00928      stale LOS h0.5      occluded             1
08OC97_-0577 coarse c10 LOS h0.5 already_known             1
08OC97_-0577 coarse c10 LOS h0.5      occluded             1
08OC98_00148 coarse c10 LOS h0.5 already_known             1
08OC98_00148 coarse c10 LOS h0.5      occluded             1
08OC99_00483 coarse c10 LOS h0.5 already_known             1
08OC99_00483 coarse c10 LOS h0.5      occluded             1
08OC99_01733      stale LOS h0.5 already_known             1
08OC99_01733      stale LOS h0.5      occluded             1
```

## 初回接触の監査（出力そのまま）
```text
First entry of each lethal cell per run; later exits/repeated touches are excluded.
     prior   sensor    cause  contact_runs  unique_contact_cells
coarse c10 LOS h0.5 occluded             6                     8
     stale LOS h0.5 occluded             2                     2

First-contact cell coordinates and observation state
       patch      prior   sensor    cause  cell_x  cell_y   x_m   y_m  known_before  visible_last sensor_cell  slope_deg  steep  obstacle_buffer  water  nodata
08OB88_-0167 coarse c10 LOS h0.5 occluded     172     296  86.0 148.0         False         False  [170, 295]  35.617242   True            False  False   False
08OB88_-0167 coarse c10 LOS h0.5 occluded     189     295  94.5 147.5         False         False  [188, 294]  30.678599   True            False  False   False
08OB88_-0167 coarse c10 LOS h0.5 occluded     190     296  95.0 148.0         False         False  [189, 295]  42.709174   True            False  False   False
08OB89_-0347 coarse c10 LOS h0.5 occluded     231     378 115.5 189.0         False         False  [230, 376]  33.348348   True            False  False   False
08OC80_00660 coarse c10 LOS h0.5 occluded     323     350 161.5 175.0         False         False  [322, 348]  48.399260   True            False  False   False
08OC95_00928      stale LOS h0.5 occluded      67     276  33.5 138.0         False         False   [68, 278]  33.505318   True            False  False   False
08OC97_-0577 coarse c10 LOS h0.5 occluded     142     264  71.0 132.0         False         False  [141, 266]  40.578045   True            False  False   False
08OC98_00148 coarse c10 LOS h0.5 occluded     338     310 169.0 155.0         False         False  [340, 312]  25.325087   True            False  False   False
08OC99_00483 coarse c10 LOS h0.5 occluded     297     211 148.5 105.5         False         False  [295, 213]  28.879275   True            False  False   False
08OC99_01733      stale LOS h0.5 occluded     108     308  54.0 154.0         False         False  [110, 306]  41.319655   True            False  False   False
```

## 保全・提出

既存管理対象804ファイルのSHA-256は全て一致。計測に使ったコードのハッシュも `protocol.json` と一致した。
既存結果・データ・地図・world・論文・保護対象実装・既存テストは変更していない。新規ファイルは全て5MB未満。
PR作成APIが `Forbidden` を返す環境のため、PRは未作成。共通ルールに従いこの報告を作業ブランチへ保存してpushする。マージしない。

## 追加ファイル一覧

- `conference/experiments/audit_visibility.py`
- `conference/experiments/online_visibility.py`
- `conference/results/online_visibility/README_ja.md`
- `conference/results/online_visibility/REPORT_ja.md`
- `conference/results/online_visibility/contact_01.png`
- `conference/results/online_visibility/contact_02.png`
- `conference/results/online_visibility/contact_03.png`
- `conference/results/online_visibility/contact_audit_console_log.txt`
- `conference/results/online_visibility/contact_audit_sha256.json`
- `conference/results/online_visibility/contact_details/08OB86_-0205.json`
- `conference/results/online_visibility/contact_details/08OB86_00294.json`
- `conference/results/online_visibility/contact_details/08OB87_-0706.json`
- `conference/results/online_visibility/contact_details/08OB88_-0167.json`
- `conference/results/online_visibility/contact_details/08OB88_-1417.json`
- `conference/results/online_visibility/contact_details/08OB88_00332.json`
- `conference/results/online_visibility/contact_details/08OB88_01832.json`
- `conference/results/online_visibility/contact_details/08OB89_-0347.json`
- `conference/results/online_visibility/contact_details/08OB89_-0847.json`
- `conference/results/online_visibility/contact_details/08OB89_00152.json`
- `conference/results/online_visibility/contact_details/08OC80_-0589.json`
- `conference/results/online_visibility/contact_details/08OC80_-1089.json`
- `conference/results/online_visibility/contact_details/08OC80_00160.json`
- `conference/results/online_visibility/contact_details/08OC80_00660.json`
- `conference/results/online_visibility/contact_details/08OC91_-0438.json`
- `conference/results/online_visibility/contact_details/08OC91_-0938.json`
- `conference/results/online_visibility/contact_details/08OC91_-1688.json`
- `conference/results/online_visibility/contact_details/08OC91_00061.json`
- `conference/results/online_visibility/contact_details/08OC91_01311.json`
- `conference/results/online_visibility/contact_details/08OC92_-0141.json`
- `conference/results/online_visibility/contact_details/08OC92_-0891.json`
- `conference/results/online_visibility/contact_details/08OC92_00608.json`
- `conference/results/online_visibility/contact_details/08OC94_-0954.json`
- `conference/results/online_visibility/contact_details/08OC95_-0821.json`
- `conference/results/online_visibility/contact_details/08OC95_-1321.json`
- `conference/results/online_visibility/contact_details/08OC95_-2071.json`
- `conference/results/online_visibility/contact_details/08OC95_00428.json`
- `conference/results/online_visibility/contact_details/08OC95_00928.json`
- `conference/results/online_visibility/contact_details/08OC95_01428.json`
- `conference/results/online_visibility/contact_details/08OC96_-1426.json`
- `conference/results/online_visibility/contact_details/08OC96_00073.json`
- `conference/results/online_visibility/contact_details/08OC97_-0577.json`
- `conference/results/online_visibility/contact_details/08OC97_-1077.json`
- `conference/results/online_visibility/contact_details/08OC97_-1827.json`
- `conference/results/online_visibility/contact_details/08OC97_00422.json`
- `conference/results/online_visibility/contact_details/08OC97_01172.json`
- `conference/results/online_visibility/contact_details/08OC97_01672.json`
- `conference/results/online_visibility/contact_details/08OC98_-0351.json`
- `conference/results/online_visibility/contact_details/08OC98_-1601.json`
- `conference/results/online_visibility/contact_details/08OC98_00148.json`
- `conference/results/online_visibility/contact_details/08OC98_00648.json`
- `conference/results/online_visibility/contact_details/08OC98_01398.json`
- `conference/results/online_visibility/contact_details/08OC99_-0016.json`
- `conference/results/online_visibility/contact_details/08OC99_-1016.json`
- `conference/results/online_visibility/contact_details/08OC99_-1516.json`
- `conference/results/online_visibility/contact_details/08OC99_00483.json`
- `conference/results/online_visibility/contact_details/08OC99_01733.json`
- `conference/results/online_visibility/contact_details/08PD00_-1730.json`
- `conference/results/online_visibility/contact_reasons.csv`
- `conference/results/online_visibility/contacts.csv`
- `conference/results/online_visibility/experiment_console_log.txt`
- `conference/results/online_visibility/first_contact_causes.csv`
- `conference/results/online_visibility/first_contacts.csv`
- `conference/results/online_visibility/first_contacts_log.txt`
- `conference/results/online_visibility/missions.csv`
- `conference/results/online_visibility/observations/08OB86_-0205.npz`
- `conference/results/online_visibility/observations/08OB86_00294.npz`
- `conference/results/online_visibility/observations/08OB87_-0706.npz`
- `conference/results/online_visibility/observations/08OB88_-0167.npz`
- `conference/results/online_visibility/observations/08OB88_-1417.npz`
- `conference/results/online_visibility/observations/08OB88_00332.npz`
- `conference/results/online_visibility/observations/08OB88_01832.npz`
- `conference/results/online_visibility/observations/08OB89_-0347.npz`
- `conference/results/online_visibility/observations/08OB89_-0847.npz`
- `conference/results/online_visibility/observations/08OB89_00152.npz`
- `conference/results/online_visibility/observations/08OC80_-0589.npz`
- `conference/results/online_visibility/observations/08OC80_-1089.npz`
- `conference/results/online_visibility/observations/08OC80_00160.npz`
- `conference/results/online_visibility/observations/08OC80_00660.npz`
- `conference/results/online_visibility/observations/08OC91_-0438.npz`
- `conference/results/online_visibility/observations/08OC91_-0938.npz`
- `conference/results/online_visibility/observations/08OC91_-1688.npz`
- `conference/results/online_visibility/observations/08OC91_00061.npz`
- `conference/results/online_visibility/observations/08OC91_01311.npz`
- `conference/results/online_visibility/observations/08OC92_-0141.npz`
- `conference/results/online_visibility/observations/08OC92_-0891.npz`
- `conference/results/online_visibility/observations/08OC92_00608.npz`
- `conference/results/online_visibility/observations/08OC94_-0954.npz`
- `conference/results/online_visibility/observations/08OC95_-0821.npz`
- `conference/results/online_visibility/observations/08OC95_-1321.npz`
- `conference/results/online_visibility/observations/08OC95_-2071.npz`
- `conference/results/online_visibility/observations/08OC95_00428.npz`
- `conference/results/online_visibility/observations/08OC95_00928.npz`
- `conference/results/online_visibility/observations/08OC95_01428.npz`
- `conference/results/online_visibility/observations/08OC96_-1426.npz`
- `conference/results/online_visibility/observations/08OC96_00073.npz`
- `conference/results/online_visibility/observations/08OC97_-0577.npz`
- `conference/results/online_visibility/observations/08OC97_-1077.npz`
- `conference/results/online_visibility/observations/08OC97_-1827.npz`
- `conference/results/online_visibility/observations/08OC97_00422.npz`
- `conference/results/online_visibility/observations/08OC97_01172.npz`
- `conference/results/online_visibility/observations/08OC97_01672.npz`
- `conference/results/online_visibility/observations/08OC98_-0351.npz`
- `conference/results/online_visibility/observations/08OC98_-1601.npz`
- `conference/results/online_visibility/observations/08OC98_00148.npz`
- `conference/results/online_visibility/observations/08OC98_00648.npz`
- `conference/results/online_visibility/observations/08OC98_01398.npz`
- `conference/results/online_visibility/observations/08OC99_-0016.npz`
- `conference/results/online_visibility/observations/08OC99_-1016.npz`
- `conference/results/online_visibility/observations/08OC99_-1516.npz`
- `conference/results/online_visibility/observations/08OC99_00483.npz`
- `conference/results/online_visibility/observations/08OC99_01733.npz`
- `conference/results/online_visibility/observations/08PD00_-1730.npz`
- `conference/results/online_visibility/online_visibility_log.txt`
- `conference/results/online_visibility/paired_runs.csv`
- `conference/results/online_visibility/paired_summary.csv`
- `conference/results/online_visibility/plan_times_coarse_c10_LOS_h0.5.csv`
- `conference/results/online_visibility/plan_times_coarse_c10_LOS_h0.8.csv`
- `conference/results/online_visibility/plan_times_coarse_c10_LOS_h1.2.csv`
- `conference/results/online_visibility/plan_times_coarse_c10_radius.csv`
- `conference/results/online_visibility/plan_times_stale_LOS_h0.5.csv`
- `conference/results/online_visibility/plan_times_stale_LOS_h0.8.csv`
- `conference/results/online_visibility/plan_times_stale_LOS_h1.2.csv`
- `conference/results/online_visibility/plan_times_stale_radius.csv`
- `conference/results/online_visibility/protocol.json`
- `conference/results/online_visibility/runtime.json`
- `conference/results/online_visibility/summary.csv`
- `conference/results/online_visibility/traces/08OB86_-0205.npz`
- `conference/results/online_visibility/traces/08OB86_00294.npz`
- `conference/results/online_visibility/traces/08OB87_-0706.npz`
- `conference/results/online_visibility/traces/08OB88_-0167.npz`
- `conference/results/online_visibility/traces/08OB88_-1417.npz`
- `conference/results/online_visibility/traces/08OB88_00332.npz`
- `conference/results/online_visibility/traces/08OB88_01832.npz`
- `conference/results/online_visibility/traces/08OB89_-0347.npz`
- `conference/results/online_visibility/traces/08OB89_-0847.npz`
- `conference/results/online_visibility/traces/08OB89_00152.npz`
- `conference/results/online_visibility/traces/08OC80_-0589.npz`
- `conference/results/online_visibility/traces/08OC80_-1089.npz`
- `conference/results/online_visibility/traces/08OC80_00160.npz`
- `conference/results/online_visibility/traces/08OC80_00660.npz`
- `conference/results/online_visibility/traces/08OC91_-0438.npz`
- `conference/results/online_visibility/traces/08OC91_-0938.npz`
- `conference/results/online_visibility/traces/08OC91_-1688.npz`
- `conference/results/online_visibility/traces/08OC91_00061.npz`
- `conference/results/online_visibility/traces/08OC91_01311.npz`
- `conference/results/online_visibility/traces/08OC92_-0141.npz`
- `conference/results/online_visibility/traces/08OC92_-0891.npz`
- `conference/results/online_visibility/traces/08OC92_00608.npz`
- `conference/results/online_visibility/traces/08OC94_-0954.npz`
- `conference/results/online_visibility/traces/08OC95_-0821.npz`
- `conference/results/online_visibility/traces/08OC95_-1321.npz`
- `conference/results/online_visibility/traces/08OC95_-2071.npz`
- `conference/results/online_visibility/traces/08OC95_00428.npz`
- `conference/results/online_visibility/traces/08OC95_00928.npz`
- `conference/results/online_visibility/traces/08OC95_01428.npz`
- `conference/results/online_visibility/traces/08OC96_-1426.npz`
- `conference/results/online_visibility/traces/08OC96_00073.npz`
- `conference/results/online_visibility/traces/08OC97_-0577.npz`
- `conference/results/online_visibility/traces/08OC97_-1077.npz`
- `conference/results/online_visibility/traces/08OC97_-1827.npz`
- `conference/results/online_visibility/traces/08OC97_00422.npz`
- `conference/results/online_visibility/traces/08OC97_01172.npz`
- `conference/results/online_visibility/traces/08OC97_01672.npz`
- `conference/results/online_visibility/traces/08OC98_-0351.npz`
- `conference/results/online_visibility/traces/08OC98_-1601.npz`
- `conference/results/online_visibility/traces/08OC98_00148.npz`
- `conference/results/online_visibility/traces/08OC98_00648.npz`
- `conference/results/online_visibility/traces/08OC98_01398.npz`
- `conference/results/online_visibility/traces/08OC99_-0016.npz`
- `conference/results/online_visibility/traces/08OC99_-1016.npz`
- `conference/results/online_visibility/traces/08OC99_-1516.npz`
- `conference/results/online_visibility/traces/08OC99_00483.npz`
- `conference/results/online_visibility/traces/08OC99_01733.npz`
- `conference/results/online_visibility/traces/08PD00_-1730.npz`
- `conference/results/online_visibility/verification/all_tests_log.txt`
- `conference/results/online_visibility/verification/planners_before_log.txt`
- `conference/results/online_visibility/verification/preservation_audit.json`
- `conference/results/online_visibility/verification/radius_baseline_audit.json`
- `conference/results/online_visibility/verification/test_beach_terrain_log.txt`
- `conference/results/online_visibility/verification/test_collision_log.txt`
- `conference/results/online_visibility/verification/test_dstar_log.txt`
- `conference/results/online_visibility/verification/test_mapfiles_sim_log.txt`
- `conference/results/online_visibility/verification/test_mission_log.txt`
- `conference/results/online_visibility/verification/test_natural_terrain_log.txt`
- `conference/results/online_visibility/verification/test_online_log.txt`
- `conference/results/online_visibility/verification/test_online_mission_log.txt`
- `conference/results/online_visibility/verification/test_planners_log.txt`
- `conference/results/online_visibility/verification/test_real_beach_las_log.txt`
- `conference/results/online_visibility/verification/test_real_beach_log.txt`
- `conference/results/online_visibility/verification/test_risk_prior_log.txt`
- `conference/results/online_visibility/verification/test_ros2_gz_log.txt`
- `conference/results/online_visibility/verification/test_summary.txt`
- `conference/results/online_visibility/verification/test_tour_log.txt`
- `conference/results/online_visibility/verification/test_visibility_log.txt`
- `conference/tapp/visibility.py`
- `conference/tests/test_visibility.py`
