# 指示書021：漂着物のあるLAS砂浜10地形の固定経路・オンライン再計画

基準日：2026-11-04（利用者の日付、日本時間）。
ブランチ：`codex/021-gazebo-online`。基点：`origin/realtime-map` の `603efb23595c8331b8badaf32c32f373f872f0b3`。020のマージを確認してから、その時点の最新から独立して作成した。他の作業ブランチを積まず、マージしていない。

## 結果と未実行の部分

実装、10地形の事前計画、ROS2なしの新規テストと既存テストを完了した。**Gazeboでの20走行は未実行**。通常のDockerラッパーを起動したが、`thesis/jazzy-gz:1` がなくexit=125で終了した。既存の `ros:jazzy-ros-base` の確認でもGazeboが見つからず、SciPyのimportに失敗した。colcon buildや新しいGazeboプロセスは開始していない。特殊な名前空間・chrootでの実行は行っていない。依存関係の追加インストール、ホストのsudo、パラメータの調整も行っていない。

先頭10地形すべてで、既定の膨張ありTA*-Sによる事前地図上の巡回を計画できた。これはPythonで実際に計画した結果であり、走行の完走・転倒・漂着物回避を測った結果ではない。

```text
       patch planning_status  fixed_plan_calls              order
08OB86_00294         planned                 6 [0, 5, 1, 3, 4, 2]
08OB86_-0205         planned                 6 [0, 3, 1, 5, 2, 4]
08OB87_-0706         planned                 6 [0, 4, 5, 3, 2, 1]
08OB88_-1417         planned                 6 [0, 3, 1, 2, 4, 5]
08OB88_-0167         planned                 6 [0, 4, 2, 5, 3, 1]
08OB88_00332         planned                 6 [0, 2, 5, 4, 3, 1]
08OB88_01832         planned                 6 [0, 5, 3, 4, 1, 2]
08OB89_00152         planned                 6 [0, 4, 2, 1, 5, 3]
08OB89_-0347         planned                 6 [0, 5, 1, 4, 3, 2]
08OB89_-0847         planned                 6 [0, 1, 4, 5, 3, 2]
```

## 実装したもの

- `ros2_jazzy/gz_checks/online_batch_checks.py`：10地形×固定/オンラインの20条件を同じworld・地点・初期位置で順に実行する。地図とworldは一時フォルダ、worldは4097画素上限、Gazebo seed=0。実行途中のエラーと計画不能もmanifestに残す。
- `online_batch_runtime.py`：014の `scenarios` と同じ地点の抽出、元の事前地図での巡回順の決定、020の0.5m急斜面膨張を組み合わせる。既存の `AsyncOnlineMission` の探索・観測・遅延経路の引き継ぎを再利用し、出発前の順番を固定する。探索の失敗や経路を適用できなかった場合もワーカー側で計画時間を記録する。CSVの分割・読み込みも実装した。
- `online_batch_planner.py`：014のROS2ノードのコールバックを継承し、未使用の既定runtimeを新しいruntimeに差し替える。既存ファイル、既存のエントリーポイント、既定動作は変更しない。
- `run_online_batch_checks.sh`：通常のDockerでソースを読み取り専用マウントし、colconのビルドとインストールを一時領域で行う。`--planner` と出力先を転送する。ローカルのイメージを使い、既存manifestの上書きを拒否する。
- `experiments/gz_online_batch_report.py`：元の記録から結果・到達した地点・接触・計画時間・ずれ・姿勢を集計し、20行の表、2条件の集計、対の差、漂着物を重ねた10枚の図を出す。020の厳密な転倒判定を再利用し、最大値と最初の転倒地点も出す。未測定は空欄・None・NaNに保つ。
- `tests/test_gz_online_batch.py`：直接呼び出しとの10地形の一致、合成記録での分類と到達数、元データの不変性、全探索の記録、CSV分割と欠落の検出、未実行の分母、完走した対だけの集計、エネルギー列がないことを確認する。合成記録の値は試験専用の一時フォルダ・メモリ内だけで使い、実験の値として保存しない。

## 固定した条件と集計の定義

`shizuoka_beach_las` のtest先頭10地形、200m、seed 0。真値は漂着物あり、事前地図は同じパッチの漂着物なし。地点は014と同じ `SeedSequence([0, 3000, 200, patch_index])` から12点を抽出した先頭5点である。巡回順は膨張前の事前地図で決め、両条件とすべての区間で共有する。地点はずらさない。計画と観測の走行可能マスクには020の急斜面膨張を適用し、地形コストを変えない。既定は `TA*-S+inflate`、後日の比較用に `TA*-S` を引数で選べる。半径や重みをtestの成績で選んでいない。

完走はfollowerのcompletedに加えて、事前に決めた順の5点それぞれの0.3m以内を通り、出発点に戻ったことを要求する。途中の到達は、記録点間の線分も調べた順番付きの接頭部分として数える。followerがcompletedでも途中地点が欠ける場合は `incomplete_waypoints` とし、原状態は保持する。転倒はどこかで絶対rollが90度を超えた場合で、立ち往生・時間切れより優先する。時間切れは019と同じ、120秒と「事前経路長×6＋60秒」の大きい方のシミュレーション時間上限。ROS/Gazeboの異常終了や時計の停止は実行エラーとして分ける。

接触は元のtruth lethalと、014と同じ `truth.rock & ~prior.rock` の一意なセル数。中心軌跡に基づく地図との照合であり、接触力センサーの実測ではない。ずれはfollowerがstateで確認した適用経路に対して計算し、まだ経路がない初回待機のサンプルは除く。計画時間は探索と平滑化だけで、膨張・地点選択・巡回順決定・ROSの受け渡しを含まない。固定経路では出発前の6区間、オンラインでは成功・失敗・適用を拒否されたものを含む全探索を記録する。`start_leg` 以外の探索を再計画として数えるため、区間の初期計画とROSへの置換通知数は区別する。

対の差は、両条件とも完走した同じ地形だけを対象に `online - fixed` の中央値と対の数を出す。完走できなかったケースも走行別表と件数に残す。10地形に検定は行わず、エネルギーは集計しない。詳細なファイル仕様と通常のDocker手順は [README_ja.md](README_ja.md) に記載した。

## 実行したコマンド

```bash
cd conference
python3 -m tests.test_planners
python3 ros2_jazzy/gz_checks/online_batch_checks.py --prepare-only --output results/gazebo_online
python3 -m tests.test_gz_online_batch
python3 results/gazebo_online/verification/run_tests.py
python3 -m tests.test_gz_online_batch
python3 experiments/gz_online_batch_report.py
bash ros2_jazzy/gz_checks/run_online_batch_checks.sh results/gazebo_online/physical_run
```

最後のDocker起動だけexit=125であり、テストの失敗ではない。Pythonには `OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/thesis-021-mpl XDG_CACHE_HOME=/tmp/thesis-021-cache` を指定した。新規Pythonの `py_compile` とシェルの `bash -n` も成功した。

Docker起動の実際の出力：

```text
docker: Error response from daemon: No such image: thesis/jazzy-gz:1

Run 'docker run --help' for more information
```

既存のros:jazzy-ros-base内での依存確認の出力：

```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
ModuleNotFoundError: No module named 'scipy'
```

## テスト出力の全文

変更前：

```text
all planner tests passed
roll-aware tests passed
```

全モジュール：

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
test_real_beach exit=0
test_real_beach_las exit=0
test_risk_prior exit=0
test_ros2_gz exit=0
test_thesis_figures exit=0
test_tour exit=0
test_visibility exit=0
```

新規の記録処理を最終確認した後の再実行：

```text
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)
```

## 集計表（スクリプトの出力をそのまま）

以下の20行はすべて実走未実行である。成功数・転倒数・到達数・接触数・所要時間・計画時間の空欄を0と解釈しない。

```text
Task021: ten LAS test beaches x fixed/online; descriptive only, no hypothesis tests or energy.
Missing physical values are blank/None/NaN; planning failure is not a completed or safe trial.
       patch   mode       planner planning_status status recorded_status completed data_source error goals_reached lethal_cells debris_cells n_replans elapsed_s deviation_mean_m deviation_max_m roll_p95_deg roll_max_deg pitch_p95_deg pitch_max_deg plan_s_median plan_s_p95 plan_s_max returned_to_start n_plans calls_over_1s deviation_samples out_of_bounds_samples rolled_over rollover_t_s rollover_elapsed_s rollover_x_m rollover_y_m
08OB86_00294  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB86_00294 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB86_-0205  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB86_-0205 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB87_-0706  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB87_-0706 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_-1417  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_-1417 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_-0167  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_-0167 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_00332  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_00332 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_01832  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB88_01832 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_00152  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_00152 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_-0347  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_-0347 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_-0847  fixed TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None
08OB89_-0847 online TA*-S+inflate         planned    未実行            None      None        None                None         None         None      None      None             None            None         None         None          None          None          None       None       None              None    None          None              None                  None        None         None               None         None         None

Counts use actual Gazebo recordings only; 5 ordered targets plus return required for completion.
  mode  scheduled  executed  unexecuted  planning_infeasible completed stuck rollover timeout no_path incomplete_waypoints runtime_error other_failure  goals_reached_median  lethal_cells_median  debris_cells_median  n_replans_median  elapsed_s_median  deviation_mean_m_median  deviation_max_m_median  roll_p95_deg_median  roll_max_deg_median  pitch_p95_deg_median  pitch_max_deg_median  plan_s_median_median  plan_s_p95_median  plan_s_max_median
 fixed         10         0          10                    0      None  None     None    None    None                 None          None          None                   NaN                  NaN                  NaN               NaN               NaN                      NaN                     NaN                  NaN                  NaN                   NaN                   NaN                   NaN                NaN                NaN
online         10         0          10                    0      None  None     None    None    None                 None          None          None                   NaN                  NaN                  NaN               NaN               NaN                      NaN                     NaN                  NaN                  NaN                   NaN                   NaN                   NaN                NaN                NaN

Online minus fixed; paired medians among two completed physical tours only.
          metric  paired_completed  online_minus_fixed_median
   goals_reached                 0                        NaN
    lethal_cells                 0                        NaN
    debris_cells                 0                        NaN
       n_replans                 0                        NaN
       elapsed_s                 0                        NaN
deviation_mean_m                 0                        NaN
 deviation_max_m                 0                        NaN
    roll_p95_deg                 0                        NaN
    roll_max_deg                 0                        NaN
   pitch_p95_deg                 0                        NaN
   pitch_max_deg                 0                        NaN
   plan_s_median                 0                        NaN
      plan_s_p95                 0                        NaN
      plan_s_max                 0                        NaN
Deviation uses the follower-acknowledged active path; pre-first-plan samples are excluded.
Planning times: A* plus smoothing only, excluding map inflation, tour ordering and ROS handoff.
One second corresponds to 1m travel at the 1m/s speed cap; these timings alone do not prove real-time safety.
Sensor: perfect R10 traversability labels, including the dilation halo; no LiDAR, occlusion or error.
```

## できなかったこと・レビューで確認してほしいこと

Gazeboを実行していないため、古い地図で漂着物に停止したか・転倒したか、オンラインでどの地形が完走できなかったかとその原因は判断できない。1回の計画が1m/sでの移動に間に合うかも未測定である。速度上限1m/sでは1秒に1m進むが、探索時間の中央値・95%・最大だけで安全性を判断せず、ROS受け渡し・経路追従・停止・接触を合わせて確認する必要がある。

センサーは半径10m以内の走行可能ラベルが誤差なく得られる簡略化で、LiDAR・遮蔽・誤差を模擬しない。膨張済みラベルのため、観測円のすぐ外の急斜面の影響が円内のラベルに入ることもある。車体の追従ずれや急旋回、模型の横摩擦mu2=0.1による転倒は、膨張しても残りうる。ROS2でのアダプター統合と通常Dockerでのcolcon buildは未検証なので、準備した手順で実走とログを確認してほしい。

実走時は次の新しい保存先を使う。今回の事前確認用manifestを上書きしない。

```bash
docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference
cd conference
bash ros2_jazzy/gz_checks/run_online_batch_checks.sh results/gazebo_online/physical_run
python3 experiments/gz_online_batch_report.py results/gazebo_online/physical_run
```

## 図

各地形の図は真値の地形と漂着物マスク、実際に計画した事前経路だけを表示し、実走未実行と明記した。実走後は同じスクリプトが2条件の記録軌跡を重ねる。`08OB88_-0167.png` は目視確認した。

[08OB86_00294](08OB86_00294.png)

[08OB86_-0205](08OB86_-0205.png)

[08OB87_-0706](08OB87_-0706.png)

[08OB88_-1417](08OB88_-1417.png)

[08OB88_-0167](08OB88_-0167.png)

[08OB88_00332](08OB88_00332.png)

[08OB88_01832](08OB88_01832.png)

[08OB89_00152](08OB89_00152.png)

[08OB89_-0347](08OB89_-0347.png)

[08OB89_-0847](08OB89_-0847.png)

## 保存の監査と環境

既存ファイルは1つも変更していない。既存テストの弱体化・枚数確認の修正も行っていない。地図・worldはこの結果フォルダに保存しておらず、rawの実走記録も作っていない。

```json
{
  "baseline_files": 1819,
  "changed": []
}
```

```json
{
  "base": "603efb23595c8331b8badaf32c32f373f872f0b3",
  "branch": "codex/021-gazebo-online",
  "execution": "prepare-only; no Gazebo physical recording",
  "planner": "TA*-S+inflate",
  "dataset": "shizuoka_beach_las",
  "sense_radius_m": 10,
  "python": "3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]",
  "platform": "Linux-6.18.57-x86_64-with-glibc2.41",
  "versions": {
    "numpy": "2.3.5",
    "scipy": "1.17.0",
    "pandas": "2.2.3",
    "matplotlib": "3.10.8",
    "fastapi": "0.141.1",
    "pydantic": "2.13.4"
  },
  "host_executables": {
    "gz": null,
    "ros2": null,
    "docker": "/usr/local/bin/docker",
    "colcon": null
  },
  "source_sha256": {
    "data_prep/export_gazebo.py": "55adbeaa53478c53701bb31c31e928deb0cd220537f4d165c90dcd2bba6f8af0",
    "experiments/gz_online_batch_report.py": "5b3863e994dedf7de033ba9346685876680dba20634cba9437de306d6f9692e6",
    "ros2_jazzy/gz_checks/online_batch_checks.py": "8e833b5bdc2752e3fb7df13e6ece70006bfe32dd711921ccc1ef732fdcd44005",
    "ros2_jazzy/gz_checks/online_batch_planner.py": "c555096807c826b28b19fe87fdae7938208c8f994d9d205cb109d24c6d8f1af6",
    "ros2_jazzy/gz_checks/online_batch_runtime.py": "719f6d71043755c082ab648be67ea3ca67e7c273269ed50f45838e25c42dd7d1",
    "ros2_jazzy/gz_checks/run_online_batch_checks.sh": "e980982c25bc92bab68e5c5622ce348aca38b0519d2e0fec57bd5967c16ce2e2",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/__init__.py": "37764e5d2ddcc218f3b9ea1990270f44ae82957b8175d07b05ed9554197fa659",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_planner.py": "cf6a4a62eb6ed2216215a3785e793e67f1bb1d73e368ce2688f346a9596d7c21",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_runtime.py": "a911ffdb8b8fb55f771d92872551f40a0e9df4e1db693db46c02095a1e735c7b",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py": "eae676fb2864bf6de66455a4d2cb4e7688845d8e488747917484f4c899780bbc",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/transport.py": "c09e31b58053e70835ba8b3d15bbc0825c75a16daff71f5e4b1f747d3f986025",
    "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/webui_bridge.py": "067aa327c04a88c7730ad7aeae3849c28425e0a2c05e922af750241cac39cd17",
    "tapp/__init__.py": "6a7303859dfc82ceb05625b64cad5ecba7d947bc6b7a3151d241ab8a34c336c6",
    "tapp/aniso.py": "0bcf1d6474ecb451374b20c6289b3557d67585582ab4560c479ac4ae2559d282",
    "tapp/beach_scenario.py": "e481f68612cf5337f2ec0e3654c8e5fb13cae526a8e757c1e22692dc9efb5528",
    "tapp/beach_terrain.py": "837b9a80cfc8cb79714531e3c010ad7b12ce068a93de6ddb0ca8dedc65966017",
    "tapp/collision.py": "d70551c6bda534a8fdccdc87e20f6599f64fc1b484721fc643158b9b9b9d5f95",
    "tapp/config.py": "5c4cfe860b16f2d4540e970f2ca19a634f563a24deb361d0e85b7daa6e6c7895",
    "tapp/directional.py": "97d7cedcacd6f4883969ced561c8aa79cbbaac15b7f72832ba0316127ac2aba4",
    "tapp/dstar_lite.py": "9bb2a4a801a2e5143822eb1fb7eb834b1fb879b2fe023a6da7de26b8213108a9",
    "tapp/exact_planners.py": "e33e53cbc64ff281c4f9f764de4b910d38dd867abea41dfbd4fd93ea95c3f3ea",
    "tapp/follower.py": "73aa7556390a43f1ddff7e02aa02cf6e43844204a8511bc5d7b77e344de54034",
    "tapp/footprint.py": "2dcfd352570fbbcd9666439dbfeecd1d98fc911e083ff5f489d1a6c7739b1b4e",
    "tapp/geo.py": "a46cad85748b27610be65f53359aff32e85be8e6c63a9d5c20b5c61446c2ab5a",
    "tapp/mapfile.py": "d113b98de911cb86671bbe4087e160f7bc24d735059a2cd01cd269b2e982d6ed",
    "tapp/metrics.py": "ca47f87528abd20e8c87be461d53f5f28a901e9e120cfe6201e6bcf8931d4d1b",
    "tapp/mission.py": "bc1a43794f3a0e9d78792fa6b933719d659e28184b61e286d41c3d402356d24e",
    "tapp/natural_scenario.py": "24f9a2813c3c91d727a01c92f60f7f93f117435b83610abe460d04d0b7b2db8a",
    "tapp/natural_terrain.py": "b697774741c396e8e47dcfc3fe48c26a832f268a8ab07b155888a3313fefc494",
    "tapp/online.py": "b0d42ba2c9dc87c46d831a6f59fd65c038783b823b55ecce0b904831e6ff5a3e",
    "tapp/online_deadend.py": "d76f63a3f39c9dae64e22fe6ab8ff32139787b8341b5c51d539d72798a3cfe50",
    "tapp/online_mission.py": "cb6256d33524a7121a79c4cb12e406b3be32f741bc072ebb4eb01481935882b9",
    "tapp/planners.py": "0b7fae68b5df6c3930e8b2311727f8a721fc64d8e9d8b66f0512df4a34a70b35",
    "tapp/prior.py": "7d88a2f97d57eeacc44b454a1cdfb271982646cf6b7e8ed839fdb05349ac21c2",
    "tapp/pure_pursuit.py": "117e82c76afa4d458d24d717cbd31989bcd9fc4821f932c86de7d9330e775ad1",
    "tapp/real_beach.py": "34e61730bbf27f4156d7533f93eaf3e1200678e0de21ace6a9707080d7cddf67",
    "tapp/risk_prior.py": "45e1c7e2d0b2c95797ffd685fdc6c2d1b3b75290db7d4b44234892dc1d8a6388",
    "tapp/robot_sim.py": "72945c0e7869798990d2dabc501eb59fd8b58c8425e1c6940840bcc9f5ddafc3",
    "tapp/run_log.py": "49f90c088cb72b92fb51c8b1127256657d7bb59fc9b679c101dcb2fbc2d0c3a3",
    "tapp/scenario.py": "1b72375f95c8f8deaa07c16dbacbea282ce52f20cd9d23fdc546ea0bbc7ccce7",
    "tapp/terrain.py": "57eede9a8dde604c067f00973e6e9a3a966629d166cb5a6dd70e74a98ebd8864",
    "tapp/terrain_baselines.py": "72ee46f517bc0e50e8a8483473c138bff921f3030e62ec37d3ad68ac1745bc4d",
    "tapp/tour.py": "f95e6d95c456a887768596e2e32d10ae1d8960ebfac6af0a1b1697eaac9d37a9",
    "tapp/traversability.py": "b655d1b97aef36a74a636bb1ff5089b421f9f5ef1aa8a3e489ac024d4597d9c2",
    "tapp/visibility.py": "45e5a3e78553acf571651d00e855044948018603fec10c17bbc5c57df8e65482",
    "tests/test_gz_online_batch.py": "ade329bd3673f7396a29ee692b4d1ac1652459aac62ed12df99e03e30e74fc70"
  },
  "data_sha256": {
    "08OB86_00294": "a28761a28ecd3b99b26d1d7e9899c0eba55a43047c726a74361f08e022b81e72",
    "08OB86_-0205": "5a363b942c0991542b46e1e8657088b641647726fd5a2af684327cb3cdb762c9",
    "08OB87_-0706": "040ed7b94cd70b41e9d2b94259b40ab8c1210d849732b1132f34cb5230c64d64",
    "08OB88_-1417": "f0ecb31bd4d851ea4c88ce0057e3c379591572d3b2308066f6120c061dd7c7cd",
    "08OB88_-0167": "9896a3892eef5fc439daad325c22f149e0a2157c94daec0be60296ebbc5f06dc",
    "08OB88_00332": "36aa756efe874f15dbd9ce45d1ccb85997c6d9131ac20bbaeab3ed2c368e172d",
    "08OB88_01832": "709d8f2f68753a49293a315091a595bc6f489439cbfcf763920c23abbeb71d84",
    "08OB89_00152": "82dfbd220de3f07afa0161c884941f8dba65c3d8d2ad4d8fef59d18d5efd7b50",
    "08OB89_-0347": "4308458273952d62958f2f4a080253e9a676337594dd1c6ea87f277c92e12882",
    "08OB89_-0847": "c530894cc3784c412abc8a15837e638b852236450421106136e63463814e6476"
  },
  "physical_trials_recorded": 0,
  "docker_launcher_exit": 125,
  "client_date": "2026-11-04"
}
```

## 変更ファイル一覧

- `conference/experiments/gz_online_batch_report.py`
- `conference/results/gazebo_online/08OB86_-0205.png`
- `conference/results/gazebo_online/08OB86_00294.png`
- `conference/results/gazebo_online/08OB87_-0706.png`
- `conference/results/gazebo_online/08OB88_-0167.png`
- `conference/results/gazebo_online/08OB88_-1417.png`
- `conference/results/gazebo_online/08OB88_00332.png`
- `conference/results/gazebo_online/08OB88_01832.png`
- `conference/results/gazebo_online/08OB89_-0347.png`
- `conference/results/gazebo_online/08OB89_-0847.png`
- `conference/results/gazebo_online/08OB89_00152.png`
- `conference/results/gazebo_online/README_ja.md`
- `conference/results/gazebo_online/REPORT_ja.md`
- `conference/results/gazebo_online/changed_files.txt`
- `conference/results/gazebo_online/gazebo_online_log.txt`
- `conference/results/gazebo_online/manifest.json`
- `conference/results/gazebo_online/paired_differences.csv`
- `conference/results/gazebo_online/runs.csv`
- `conference/results/gazebo_online/summary.csv`
- `conference/results/gazebo_online/verification/all_tests_log.txt`
- `conference/results/gazebo_online/verification/baseline_audit.json`
- `conference/results/gazebo_online/verification/baseline_sha256.json`
- `conference/results/gazebo_online/verification/build_report.py`
- `conference/results/gazebo_online/verification/docker_launcher_log.txt`
- `conference/results/gazebo_online/verification/docker_probe_log.txt`
- `conference/results/gazebo_online/verification/planners_before_log.txt`
- `conference/results/gazebo_online/verification/prepare_console_log.txt`
- `conference/results/gazebo_online/verification/protocol.json`
- `conference/results/gazebo_online/verification/report_console_log.txt`
- `conference/results/gazebo_online/verification/run_tests.py`
- `conference/results/gazebo_online/verification/test_beach_terrain_log.txt`
- `conference/results/gazebo_online/verification/test_collision_log.txt`
- `conference/results/gazebo_online/verification/test_dstar_log.txt`
- `conference/results/gazebo_online/verification/test_footprint_log.txt`
- `conference/results/gazebo_online/verification/test_geo_log.txt`
- `conference/results/gazebo_online/verification/test_gz_compare_log.txt`
- `conference/results/gazebo_online/verification/test_gz_online_batch_final_log.txt`
- `conference/results/gazebo_online/verification/test_gz_online_batch_initial_log.txt`
- `conference/results/gazebo_online/verification/test_gz_online_batch_log.txt`
- `conference/results/gazebo_online/verification/test_mapfiles_sim_log.txt`
- `conference/results/gazebo_online/verification/test_mission_log.txt`
- `conference/results/gazebo_online/verification/test_natural_terrain_log.txt`
- `conference/results/gazebo_online/verification/test_online_deadend_log.txt`
- `conference/results/gazebo_online/verification/test_online_log.txt`
- `conference/results/gazebo_online/verification/test_online_mission_log.txt`
- `conference/results/gazebo_online/verification/test_planners_log.txt`
- `conference/results/gazebo_online/verification/test_real_beach_las_log.txt`
- `conference/results/gazebo_online/verification/test_real_beach_log.txt`
- `conference/results/gazebo_online/verification/test_risk_prior_log.txt`
- `conference/results/gazebo_online/verification/test_ros2_gz_log.txt`
- `conference/results/gazebo_online/verification/test_summary.txt`
- `conference/results/gazebo_online/verification/test_thesis_figures_log.txt`
- `conference/results/gazebo_online/verification/test_tour_log.txt`
- `conference/results/gazebo_online/verification/test_visibility_log.txt`
- `conference/ros2_jazzy/gz_checks/online_batch_checks.py`
- `conference/ros2_jazzy/gz_checks/online_batch_planner.py`
- `conference/ros2_jazzy/gz_checks/online_batch_runtime.py`
- `conference/ros2_jazzy/gz_checks/run_online_batch_checks.sh`
- `conference/tests/test_gz_online_batch.py`
