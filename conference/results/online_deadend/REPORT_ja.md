# 指示書016 実装報告

ブランチ: `codex/016-deadend`。土台: `b4c92a1ccaf60eff85362564d2f0d9915c3d10ae` (`realtime-map`)。マージしない。

走行中の新しい障害による行き止まりに対し、未知セルのコストを上げる記憶Aと、区間内で再計画が増えた際のhard prior切替Bを追加した。
基準法の成功・計画回数・接触数・巡回順は014の全288走行と一致し、J・dJ・長さ・oracle Jの最大絶対差もゼロだった。時間は今回の実測であり、014の時間との一致は要求しない。

## 実装と選定

- `tapp/online_deadend.py`: `DeadendPlanner` は既存 `OnlinePlanner` を継承。Aは新たな障害が残り経路を塞いだとき、周囲の未知セルだけを加算的ではなく係数で重くする。観測済みの真値が常に優先する。記憶は巡回を通して保持する。
- Bは区間の再計画回数が閾値を**超えた**呼出しからhardに切り替え、次区間で元のモードへ戻す。観測の蓄積は保持する。
- `run_deadend_mission` は014の移動・観測・発火規則・経路結合・6倍制限を保つ。対策なしの軌跡・計画回数は既存関数と完全一致することを検査した。既存 `online_mission.py` を変更していない。
- `experiments/online_deadend.py`: 同じLAS砂浜、5点、巡回順、oracleの分母で4方法を評価。失敗走行も接触監査に含める。dJは完走時のみ。各走行の対の差は `paired_runs.csv`、旧too_longの全ケースは `former_too_long.csv`、図は `former_failure_*.png`。
- `tests/test_online_deadend.py`: 記憶と切替の意味、無効時の完全一致、3砂浜での接触監査、指定された行き止まりのBによる完走。

validationの12砂浜だけを、両事前地図・R10で走らせた。Aは半径3候補×係数3候補、Bは閾値3候補。
接触、未完走、既存完走の喪失、too_longを先に減らし、次に既存完走走行の正のdJ差の平均、dJ差の平均の順で選んだ。
中央値の差は全候補で同じだったため、test実行前に保存済みvalidation結果を平均で再集計した。元の中央値診断ログも `validation_initial_median_*` に保持した。
AとBは個別に選び、A+Bではその値をそのまま組み合わせた。組み合わせの追加チューニングはしていない。

選定結果（`selection.json` から生成）:
```json
{
  "A": {
    "r_A": 10.0,
    "k_A": 2.0
  },
  "B": {
    "N_B": 30
  }
}
```
選定後、testの結果によるパラメータ変更は行っていない。

## 結果の読み方・制約

全条件を合算した件数（実行CSVから生成）:
```text
          runs  completed  too_long  touching
method
A          288        279         9         0
A+B        288        279         9         0
B          288        278        10         0
baseline   288        276        12         0
```
すべての方法で、以前完走していた走行の未完走化はなかった。一方、Aを含む方法にはdJの悪化があり、万能な改善とは言えない。条件別・走行別の対の差を下に示す。
指定された `08OC99_01733` のstale・R10はBで完走した。AとA+Bは同条件でtoo_longのままだった。組み合わせがB単独より良いとは言えない。
coarseではBの幾何学的な結果が基準法と同じだった。記憶Aは未知セルの局所的な重み変更であり、完全な行き止まり探索・後戻り保証ではない。残るtoo_longを解消できなかった。
計画時間は014と同じ探索＋厳密平滑化の区間を測る。地図の組立・記憶更新・観測は含まない。総時間は `runtime.json` に別途保存。4ワーカーのCPU負荷に依存し、実機の応答時間や物理走行を保証する測定ではない。
Gazeboの新規実験は本タスクの対象外。Claudeには、dJが悪化した走行、A+BでB単独の完走が失われる例、残るtoo_longを確認してほしい。

## 実行環境とコマンド

Python `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`、NumPy `2.3.5`、SciPy `1.17.0`、Pandas `2.2.3`。
Python実行ファイル: `/tmp/thesis-apt-compat/bin/python`。Matplotlib/cacheは書込可能な `/tmp` を指定。

```bash
cd conference
python3 -m tests.test_planners  # 変更前
python3 experiments/online_deadend.py --phase validation --workers 4
python3 experiments/online_deadend.py --phase validation --reuse-validation --workers 4
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_mapfiles_sim
python3 -m tests.test_mission
python3 -m tests.test_natural_terrain
python3 -m tests.test_online
python3 -m tests.test_online_deadend
python3 -m tests.test_online_mission
python3 -m tests.test_planners
python3 -m tests.test_real_beach
python3 -m tests.test_real_beach_las
python3 -m tests.test_risk_prior
python3 -m tests.test_ros2_gz
python3 -m tests.test_tour
python3 experiments/online_deadend.py --phase test --workers 4
python3 -m tests.test_online_deadend  # 指定ケースの完走回帰テストを加えた後
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

$ python3 -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
all online dead-end tests passed

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

## 完走回帰テスト追加後の該当モジュールの出力全文
```text
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed
```

## validation集計（そのまま）
```text

Validation-only parameter selection: both priors, R10; lower lexicographic score wins
  method  runs  touching  failed  too_long  baseline_completed_lost  positive_delta_median  delta_median  positive_delta_mean  delta_mean
A_r10_k2    24         0       1         1                        0                      0             0            0.0850048   -0.547587
A_r10_k4    24         0       1         1                        0                      0             0              1.00496    0.592193
A_r10_k8    24         0       1         1                        0                      0             0               3.5002     3.19536
 A_r3_k2    24         0       1         1                        0                      0             0             0.203748  -0.0661801
 A_r3_k4    24         0       1         1                        0                      0             0             0.195862   -0.147644
 A_r3_k8    24         0       1         1                        0                      0             0             0.217188   -0.178349
 A_r6_k2    24         0       1         1                        0                      0             0              2.69089     2.38705
 A_r6_k4    24         0       1         1                        0                      0             0              3.10368     2.75154
 A_r6_k8    24         0       1         1                        0                      0             0              1.57713      1.2854
   B_N10    24         0       1         1                        0                      0             0           0.00374396    -3.11222
   B_N30    24         0       1         1                        0                      0             0                    0    -1.90627
   B_N60    24         0       1         1                        0                      0             0                    0   -0.901539
Frozen parameters: {"A": {"k_A": 2.0, "r_A": 10.0}, "B": {"N_B": 30}}
```

## test集計（そのまま）
```text
Frozen parameters: {"A": {"k_A": 2.0, "r_A": 10.0}, "B": {"N_B": 30}}

Test: same task-014 tours, fixed validation-only parameters
     prior  radius_m   method  runs  completed  too_long  touching  dJ_median  dJ_p90  dJ_max  replans_median  replans_max  plan_calls  plan_s_median  plan_s_p95  plan_s_max
coarse c10         5 baseline    48         46         2         0    6.51596 51.8432 78.3836           217.5          457       11142      0.0254293    0.144794    0.603819
coarse c10         5        A    48         46         2         0    6.01498 51.9883 76.2151           211.5          523       10885      0.0268048    0.148977    0.608122
coarse c10         5        B    48         46         2         0    6.51596 51.8432 78.3836           217.5          457       11142      0.0260497    0.144713    0.609814
coarse c10         5      A+B    48         46         2         0    6.01498 51.9883 76.2151           211.5          523       10885      0.0274321    0.150749    0.604384
coarse c10        10 baseline    48         45         3         0     4.2116 27.6546 58.1804           181.5          443        9347      0.0296146    0.173689    0.642573
coarse c10        10        A    48         46         2         0    3.90202 29.9212 57.1692             187          391        9378       0.031091    0.173267    0.611572
coarse c10        10        B    48         45         3         0     4.2116 27.6546 58.1804           181.5          443        9347      0.0314489    0.190137     0.61707
coarse c10        10      A+B    48         46         2         0    3.90202 29.9212 57.1692             187          391        9378      0.0317297    0.178572    0.616638
coarse c10        15 baseline    48         46         2         0    2.92738 19.8007 51.9435           156.5          356        8236      0.0350347    0.174482    0.584866
coarse c10        15        A    48         46         2         0    2.87747 23.1069 50.2353           154.5          375        8088      0.0347437    0.173468    0.607189
coarse c10        15        B    48         46         2         0    2.92738 19.8007 51.9435           156.5          356        8236      0.0348127    0.171258    0.454009
coarse c10        15      A+B    48         46         2         0    2.87747 23.1069 50.2353           154.5          375        8088      0.0351313    0.169333     0.46271
     stale         5 baseline    48         46         2         0    1.95421 10.2739 30.3772             101          240        6010      0.0278865    0.169759    0.613606
     stale         5        A    48         47         1         0    2.17071 9.42774 37.1691            99.5          341        6015      0.0286295    0.182732    0.741568
     stale         5        B    48         47         1         0    2.02754 9.22268 21.2192            99.5          346        6085      0.0288577    0.175289    0.741588
     stale         5      A+B    48         47         1         0    2.17071 7.74396 25.9962              98          333        5979      0.0287471    0.184098    0.713691
     stale        10 baseline    48         46         2         0   0.945069 6.60292 22.8123            94.5          224        5428      0.0323494    0.177852    0.643621
     stale        10        A    48         46         2         0    1.28185 6.69846 21.7571              92          219        5277      0.0311357    0.178625    0.642973
     stale        10        B    48         47         1         0    0.95184 6.73941 15.3136              93          316        5560      0.0302814    0.169611    0.633784
     stale        10      A+B    48         46         2         0    1.28185 6.69846 19.4537            89.5          219        5238       0.030022    0.174257    0.666108
     stale        15 baseline    48         47         1         0   0.688622 5.29695 18.6182              85          301        5153      0.0335537    0.166183    0.663355
     stale        15        A    48         48         0         0   0.964253 5.12445 20.7014            85.5          277        5051      0.0339094     0.17017    0.662841
     stale        15        B    48         47         1         0   0.688622 5.37548 11.8795            84.5          304        5110      0.0328201    0.157929     0.64674
     stale        15      A+B    48         48         0         0   0.964253 5.12895 17.5318            85.5          279        5038       0.033727    0.172066    0.659765

Paired dJ differences (new minus baseline); losses include all previously completed runs
     prior  radius_m method  paired_completed  baseline_completed_lost  newly_completed  worsened  delta_median  delta_p90  delta_max
coarse c10         5      A                46                        0                0        11             0    1.63731    17.8267
coarse c10         5      B                46                        0                0         0             0          0          0
coarse c10         5    A+B                46                        0                0        11             0    1.63731    17.8267
coarse c10        10      A                45                        0                1        10             0   0.368429    4.74875
coarse c10        10      B                45                        0                0         0             0          0          0
coarse c10        10    A+B                45                        0                1        10             0   0.368429    4.74875
coarse c10        15      A                46                        0                0         7             0  0.0819485    9.24543
coarse c10        15      B                46                        0                0         0             0          0          0
coarse c10        15    A+B                46                        0                0         7             0  0.0819485    9.24543
     stale         5      A                46                        0                1        21             0   0.970635    10.9051
     stale         5      B                46                        0                1         0             0          0          0
     stale         5    A+B                46                        0                1        20    -0.0017642   0.782144    10.7518
     stale        10      A                46                        0                0        22             0   0.623754    9.92052
     stale        10      B                46                        0                1         0             0          0          0
     stale        10    A+B                46                        0                0        22             0   0.623754    9.92052
     stale        15      A                47                        0                1        21             0    1.20802     2.2965
     stale        15      B                47                        0                0         1             0          0   0.196334
     stale        15    A+B                47                        0                1        21             0    1.11309     2.2965

Unchanged baseline vs task 014 (wall timings are newly measured)
       field  matching  runs  max_abs_difference
     success       288   288                 NaN
     n_plans       288   288                 NaN
   n_replans       288   288                 NaN
lethal_cells       288   288                 NaN
debris_cells       288   288                 NaN
       order       288   288                 NaN
    oracle_J       NaN   NaN                   0
           J       NaN   NaN                   0
          dJ       NaN   NaN                   0
   length_xy       NaN   NaN                   0

Every formerly too_long tour: all methods
       patch      prior  radius_m   method  success   reason      dJ  n_replans  lethal_cells
08OB88_-0167 coarse c10         5 baseline    False too_long     NaN        213             0
08OB88_-0167 coarse c10         5        A    False too_long     NaN        211             0
08OB88_-0167 coarse c10         5        B    False too_long     NaN        213             0
08OB88_-0167 coarse c10         5      A+B    False too_long     NaN        211             0
08OB88_-0167 coarse c10        10 baseline    False too_long     NaN        404             0
08OB88_-0167 coarse c10        10        A    False too_long     NaN        388             0
08OB88_-0167 coarse c10        10        B    False too_long     NaN        404             0
08OB88_-0167 coarse c10        10      A+B    False too_long     NaN        388             0
08OB88_-0167 coarse c10        15 baseline    False too_long     NaN        162             0
08OB88_-0167 coarse c10        15        A    False too_long     NaN        164             0
08OB88_-0167 coarse c10        15        B    False too_long     NaN        162             0
08OB88_-0167 coarse c10        15      A+B    False too_long     NaN        164             0
08OC95_00928 coarse c10        10 baseline    False too_long     NaN        129             0
08OC95_00928 coarse c10        10        A     True          43.9299        290             0
08OC95_00928 coarse c10        10        B    False too_long     NaN        129             0
08OC95_00928 coarse c10        10      A+B     True          43.9299        290             0
08OC96_-1426 coarse c10         5 baseline    False too_long     NaN        410             0
08OC96_-1426 coarse c10         5        A    False too_long     NaN        257             0
08OC96_-1426 coarse c10         5        B    False too_long     NaN        410             0
08OC96_-1426 coarse c10         5      A+B    False too_long     NaN        257             0
08OC96_-1426 coarse c10        10 baseline    False too_long     NaN        268             0
08OC96_-1426 coarse c10        10        A    False too_long     NaN        263             0
08OC96_-1426 coarse c10        10        B    False too_long     NaN        268             0
08OC96_-1426 coarse c10        10      A+B    False too_long     NaN        263             0
08OC96_-1426 coarse c10        15 baseline    False too_long     NaN        256             0
08OC96_-1426 coarse c10        15        A    False too_long     NaN        235             0
08OC96_-1426 coarse c10        15        B    False too_long     NaN        256             0
08OC96_-1426 coarse c10        15      A+B    False too_long     NaN        235             0
08OC96_-1426      stale         5 baseline    False too_long     NaN         85             0
08OC96_-1426      stale         5        A    False too_long     NaN         62             0
08OC96_-1426      stale         5        B    False too_long     NaN         68             0
08OC96_-1426      stale         5      A+B    False too_long     NaN         60             0
08OC96_-1426      stale        10 baseline    False too_long     NaN         93             0
08OC96_-1426      stale        10        A    False too_long     NaN         60             0
08OC96_-1426      stale        10        B    False too_long     NaN         74             0
08OC96_-1426      stale        10      A+B    False too_long     NaN         59             0
08OC96_-1426      stale        15 baseline    False too_long     NaN         80             0
08OC96_-1426      stale        15        A     True          4.60618         89             0
08OC96_-1426      stale        15        B    False too_long     NaN         72             0
08OC96_-1426      stale        15      A+B     True          4.60618         89             0
08OC99_01733      stale         5 baseline    False too_long     NaN        148             0
08OC99_01733      stale         5        A     True          16.9298        341             0
08OC99_01733      stale         5        B     True          11.4594        346             0
08OC99_01733      stale         5      A+B     True          14.4578        333             0
08OC99_01733      stale        10 baseline    False too_long     NaN        123             0
08OC99_01733      stale        10        A    False too_long     NaN        110             0
08OC99_01733      stale        10        B     True          14.5579        316             0
08OC99_01733      stale        10      A+B    False too_long     NaN         88             0
```

## 保全と提出

既存管理対象の804ファイルをSHA-256で照合し、差分ゼロ。既存結果・地図・world・データ・論文・保護対象実装は変更していない。新規ファイルは全て5MB未満。
PR作成APIがこの環境で `Forbidden` を返すため、PRは未作成。共通ルールに従い、この報告書を作業ブランチに保存してpushする。マージは行わない。

## 追加したファイル一覧

- `conference/experiments/online_deadend.py`
- `conference/results/online_deadend/REPORT_ja.md`
- `conference/results/online_deadend/baseline_014_audit.csv`
- `conference/results/online_deadend/former_failure_01.png`
- `conference/results/online_deadend/former_failure_02.png`
- `conference/results/online_deadend/former_failure_03.png`
- `conference/results/online_deadend/former_too_long.csv`
- `conference/results/online_deadend/missions.csv`
- `conference/results/online_deadend/online_deadend_log.txt`
- `conference/results/online_deadend/paired_runs.csv`
- `conference/results/online_deadend/paired_summary.csv`
- `conference/results/online_deadend/plan_times_A_coarse_c10.csv`
- `conference/results/online_deadend/plan_times_A_stale.csv`
- `conference/results/online_deadend/plan_times_AplusB_coarse_c10.csv`
- `conference/results/online_deadend/plan_times_AplusB_stale.csv`
- `conference/results/online_deadend/plan_times_B_coarse_c10.csv`
- `conference/results/online_deadend/plan_times_B_stale.csv`
- `conference/results/online_deadend/plan_times_baseline_coarse_c10.csv`
- `conference/results/online_deadend/plan_times_baseline_stale.csv`
- `conference/results/online_deadend/runtime.json`
- `conference/results/online_deadend/selection.json`
- `conference/results/online_deadend/summary.csv`
- `conference/results/online_deadend/test_console_log.txt`
- `conference/results/online_deadend/traces/08OB86_-0205.npz`
- `conference/results/online_deadend/traces/08OB86_00294.npz`
- `conference/results/online_deadend/traces/08OB87_-0706.npz`
- `conference/results/online_deadend/traces/08OB88_-0167.npz`
- `conference/results/online_deadend/traces/08OB88_-1417.npz`
- `conference/results/online_deadend/traces/08OB88_00332.npz`
- `conference/results/online_deadend/traces/08OB88_01832.npz`
- `conference/results/online_deadend/traces/08OB89_-0347.npz`
- `conference/results/online_deadend/traces/08OB89_-0847.npz`
- `conference/results/online_deadend/traces/08OB89_00152.npz`
- `conference/results/online_deadend/traces/08OC80_-0589.npz`
- `conference/results/online_deadend/traces/08OC80_-1089.npz`
- `conference/results/online_deadend/traces/08OC80_00160.npz`
- `conference/results/online_deadend/traces/08OC80_00660.npz`
- `conference/results/online_deadend/traces/08OC91_-0438.npz`
- `conference/results/online_deadend/traces/08OC91_-0938.npz`
- `conference/results/online_deadend/traces/08OC91_-1688.npz`
- `conference/results/online_deadend/traces/08OC91_00061.npz`
- `conference/results/online_deadend/traces/08OC91_01311.npz`
- `conference/results/online_deadend/traces/08OC92_-0141.npz`
- `conference/results/online_deadend/traces/08OC92_-0891.npz`
- `conference/results/online_deadend/traces/08OC92_00608.npz`
- `conference/results/online_deadend/traces/08OC94_-0954.npz`
- `conference/results/online_deadend/traces/08OC95_-0821.npz`
- `conference/results/online_deadend/traces/08OC95_-1321.npz`
- `conference/results/online_deadend/traces/08OC95_-2071.npz`
- `conference/results/online_deadend/traces/08OC95_00428.npz`
- `conference/results/online_deadend/traces/08OC95_00928.npz`
- `conference/results/online_deadend/traces/08OC95_01428.npz`
- `conference/results/online_deadend/traces/08OC96_-1426.npz`
- `conference/results/online_deadend/traces/08OC96_00073.npz`
- `conference/results/online_deadend/traces/08OC97_-0577.npz`
- `conference/results/online_deadend/traces/08OC97_-1077.npz`
- `conference/results/online_deadend/traces/08OC97_-1827.npz`
- `conference/results/online_deadend/traces/08OC97_00422.npz`
- `conference/results/online_deadend/traces/08OC97_01172.npz`
- `conference/results/online_deadend/traces/08OC97_01672.npz`
- `conference/results/online_deadend/traces/08OC98_-0351.npz`
- `conference/results/online_deadend/traces/08OC98_-1601.npz`
- `conference/results/online_deadend/traces/08OC98_00148.npz`
- `conference/results/online_deadend/traces/08OC98_00648.npz`
- `conference/results/online_deadend/traces/08OC98_01398.npz`
- `conference/results/online_deadend/traces/08OC99_-0016.npz`
- `conference/results/online_deadend/traces/08OC99_-1016.npz`
- `conference/results/online_deadend/traces/08OC99_-1516.npz`
- `conference/results/online_deadend/traces/08OC99_00483.npz`
- `conference/results/online_deadend/traces/08OC99_01733.npz`
- `conference/results/online_deadend/traces/08PD00_-1730.npz`
- `conference/results/online_deadend/validation/missions.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k2_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k2_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k4_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k4_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k8_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r10_k8_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k2_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k2_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k4_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k4_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k8_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r3_k8_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k2_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k2_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k4_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k4_stale.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k8_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_A_r6_k8_stale.csv`
- `conference/results/online_deadend/validation/plan_times_B_N10_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_B_N10_stale.csv`
- `conference/results/online_deadend/validation/plan_times_B_N30_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_B_N30_stale.csv`
- `conference/results/online_deadend/validation/plan_times_B_N60_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_B_N60_stale.csv`
- `conference/results/online_deadend/validation/plan_times_baseline_coarse_c10.csv`
- `conference/results/online_deadend/validation/plan_times_baseline_stale.csv`
- `conference/results/online_deadend/validation/runtime.json`
- `conference/results/online_deadend/validation/traces/08OB87_-0206.npz`
- `conference/results/online_deadend/validation/traces/08OB88_01332.npz`
- `conference/results/online_deadend/validation/traces/08OB89_-1597.npz`
- `conference/results/online_deadend/validation/traces/08OC90_00270.npz`
- `conference/results/online_deadend/validation/traces/08OC91_00811.npz`
- `conference/results/online_deadend/validation/traces/08OC93_-1519.npz`
- `conference/results/online_deadend/validation/traces/08OC95_-0321.npz`
- `conference/results/online_deadend/validation/traces/08OC96_-0676.npz`
- `conference/results/online_deadend/validation/traces/08OC97_-0077.npz`
- `conference/results/online_deadend/validation/traces/08OC98_-1101.npz`
- `conference/results/online_deadend/validation/traces/08OC98_01898.npz`
- `conference/results/online_deadend/validation/traces/08OC99_00983.npz`
- `conference/results/online_deadend/validation_console_log.txt`
- `conference/results/online_deadend/validation_initial_median_log.txt`
- `conference/results/online_deadend/validation_initial_median_selection.json`
- `conference/results/online_deadend/validation_log.txt`
- `conference/results/online_deadend/validation_scores.csv`
- `conference/results/online_deadend/validation_selection_console_log.txt`
- `conference/results/online_deadend/verification/all_tests_log.txt`
- `conference/results/online_deadend/verification/planners_before_log.txt`
- `conference/results/online_deadend/verification/preservation_audit.json`
- `conference/results/online_deadend/verification/test_beach_terrain_log.txt`
- `conference/results/online_deadend/verification/test_collision_log.txt`
- `conference/results/online_deadend/verification/test_dstar_log.txt`
- `conference/results/online_deadend/verification/test_mapfiles_sim_log.txt`
- `conference/results/online_deadend/verification/test_mission_log.txt`
- `conference/results/online_deadend/verification/test_natural_terrain_log.txt`
- `conference/results/online_deadend/verification/test_online_deadend_final_log.txt`
- `conference/results/online_deadend/verification/test_online_deadend_log.txt`
- `conference/results/online_deadend/verification/test_online_log.txt`
- `conference/results/online_deadend/verification/test_online_mission_log.txt`
- `conference/results/online_deadend/verification/test_planners_log.txt`
- `conference/results/online_deadend/verification/test_real_beach_las_log.txt`
- `conference/results/online_deadend/verification/test_real_beach_log.txt`
- `conference/results/online_deadend/verification/test_risk_prior_log.txt`
- `conference/results/online_deadend/verification/test_ros2_gz_log.txt`
- `conference/results/online_deadend/verification/test_summary.txt`
- `conference/results/online_deadend/verification/test_tour_log.txt`
- `conference/tapp/online_deadend.py`
- `conference/tests/test_online_deadend.py`
