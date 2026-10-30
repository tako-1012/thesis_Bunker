# 指示書013：LAS点群版の実測砂浜での再実験

土台は取得済みの `realtime-map` (`3bfd55b`)、作業ブランチは `codex/real-beach-las`。
地形コスト、プランナー、重み、センサー半径、粗地図セル幅、シード、実験A〜Dの集計方法は調整していない。
LAS版の全実験と旧版CSVとの比較は最後まで実行した。

## 実装と変更範囲

- `tapp/real_beach.py`：`list_patches`・`load_patch`・`build_real` の最後にキーワード専用の `dataset="shizuoka_beach"` を追加。`dataset_dir` で旧版／LAS版の2種類を検査する。シード生成の式とパッチ順序を維持。
- `experiments/real_beach.py`：`--dataset` とワーカーへのデータ選択の伝達を追加。LAS版だけ出力先・キャッシュ識別子・出典表示を切り替える。旧版の出力先は従来どおり。
- `experiments/compare_real_beach_las.py`：A〜DのCSVをシナリオキーで1対1対応させ、欠落・重複を拒否。比較表とCSVを出力。
- `data_prep/export_maps.py`：既存地図を上書きせず検証し、LAS版validation地図を追加する `export_las_maps` を追加。旧来のフォルダ合計15 MB制限は追加12枚と両立しないため、ファイルごと5 MB未満の確認へ変更。
- `maps/README_ja.md`、新しいLAS地図12枚、新しいworld1組を追加。既存地図・既存worldは不変。
- `data_prep/compress_heightmap_png.py`：新規高さ画像が5 MBを超えたため、PNGのフィルターとzlib圧縮だけを変更。高さサンプルは完全一致。既存のエクスポーターは変更していない。
- `tests/test_real_beach_las.py`：指示書のデータ・既定動作・再現性・到達可能性・安全性・地図一致に加え、API地図一覧、比較の対応検査、標準PNGデコーダーでの一致を検証。

実際の変更ファイル一覧（下記の新規ログ・図・監査資料を含む）：

- `conference/data_prep/compress_heightmap_png.py`
- `conference/data_prep/export_maps.py`
- `conference/experiments/compare_real_beach_las.py`
- `conference/experiments/real_beach.py`
- `conference/gazebo_worlds/real_las_08OB87_-0206/README_ja.md`
- `conference/gazebo_worlds/real_las_08OB87_-0206/heightmap.png`
- `conference/gazebo_worlds/real_las_08OB87_-0206/world.sdf`
- `conference/maps/README_ja.md`
- `conference/maps/real_las_08OB87_-0206_200m_0.npz`
- `conference/maps/real_las_08OB88_01332_200m_0.npz`
- `conference/maps/real_las_08OB89_-1597_200m_0.npz`
- `conference/maps/real_las_08OC90_00270_200m_0.npz`
- `conference/maps/real_las_08OC91_00811_200m_0.npz`
- `conference/maps/real_las_08OC93_-1519_200m_0.npz`
- `conference/maps/real_las_08OC95_-0321_200m_0.npz`
- `conference/maps/real_las_08OC96_-0676_200m_0.npz`
- `conference/maps/real_las_08OC97_-0077_200m_0.npz`
- `conference/maps/real_las_08OC98_-1101_200m_0.npz`
- `conference/maps/real_las_08OC98_01898_200m_0.npz`
- `conference/maps/real_las_08OC99_00983_200m_0.npz`
- `conference/results/real_beach_las/COMPARISON_METHOD_ja.md`
- `conference/results/real_beach_las/DELIVERY_ja.md`
- `conference/results/real_beach_las/REPORT_ja.md`
- `conference/results/real_beach_las/artificial_outside.csv`
- `conference/results/real_beach_las/baseline_sha256.json`
- `conference/results/real_beach_las/compare_A_outside.csv`
- `conference/results/real_beach_las/compare_A_statistics.csv`
- `conference/results/real_beach_las/compare_B_conclusion_changes.csv`
- `conference/results/real_beach_las/compare_B_original009_10.csv`
- `conference/results/real_beach_las/compare_B_original_test_audit.csv`
- `conference/results/real_beach_las/compare_B_requested_12.csv`
- `conference/results/real_beach_las/compare_C_online.csv`
- `conference/results/real_beach_las/compare_D_euclid_excess.csv`
- `conference/results/real_beach_las/compare_D_original_tests.csv`
- `conference/results/real_beach_las/compare_D_tours.csv`
- `conference/results/real_beach_las/compare_D_waypoint_alignment.csv`
- `conference/results/real_beach_las/compare_log.txt`
- `conference/results/real_beach_las/compare_runtime.json`
- `conference/results/real_beach_las/compare_scenario_alignment.csv`
- `conference/results/real_beach_las/comparison_checks_log.txt`
- `conference/results/real_beach_las/conclusion_D_ja.txt`
- `conference/results/real_beach_las/data_audit.json`
- `conference/results/real_beach_las/default_regression_log.txt`
- `conference/results/real_beach_las/detour_01.png`
- `conference/results/real_beach_las/detour_02.png`
- `conference/results/real_beach_las/detour_03.png`
- `conference/results/real_beach_las/detour_04.png`
- `conference/results/real_beach_las/detour_05.png`
- `conference/results/real_beach_las/detour_06.png`
- `conference/results/real_beach_las/detour_07.png`
- `conference/results/real_beach_las/detour_08.png`
- `conference/results/real_beach_las/detour_09.png`
- `conference/results/real_beach_las/detour_10.png`
- `conference/results/real_beach_las/detours.csv`
- `conference/results/real_beach_las/environment.json`
- `conference/results/real_beach_las/existing_tests_log.txt`
- `conference/results/real_beach_las/experiment_artifact_sha256.json`
- `conference/results/real_beach_las/experiment_progress_log.txt`
- `conference/results/real_beach_las/export_gazebo_log.txt`
- `conference/results/real_beach_las/export_maps_log.txt`
- `conference/results/real_beach_las/heightmap_lossless.json`
- `conference/results/real_beach_las/legacy_api_failure_log.txt`
- `conference/results/real_beach_las/legacy_map_checks_proposed.patch`
- `conference/results/real_beach_las/mapfiles_unaffected_log.txt`
- `conference/results/real_beach_las/offline.csv`
- `conference/results/real_beach_las/offline_tests.csv`
- `conference/results/real_beach_las/online.csv`
- `conference/results/real_beach_las/orientation_violations.csv`
- `conference/results/real_beach_las/pair_costs.csv`
- `conference/results/real_beach_las/patch_asymmetry.csv`
- `conference/results/real_beach_las/planner_before_log.txt`
- `conference/results/real_beach_las/preservation_audit.json`
- `conference/results/real_beach_las/real_beach_log.txt`
- `conference/results/real_beach_las/run_source_sha256.json`
- `conference/results/real_beach_las/runtime.json`
- `conference/results/real_beach_las/source_invariants.json`
- `conference/results/real_beach_las/statistics.csv`
- `conference/results/real_beach_las/test_real_beach_las_log.txt`
- `conference/results/real_beach_las/tour_example_debris_0.png`
- `conference/results/real_beach_las/tour_example_debris_1.png`
- `conference/results/real_beach_las/tour_patch_summary.csv`
- `conference/results/real_beach_las/tour_tests.csv`
- `conference/results/real_beach_las/tours.csv`
- `conference/tapp/real_beach.py`
- `conference/tests/test_real_beach_las.py`


## 再現コマンド

以下は `conference/` で実行した。依存バージョン・CPU割当・実行時の環境変数は `environment.json` に保存した。
数値はすべて実行済みコードまたは旧版の保存CSVから計算し、欠測値の補完や結果の手入力はしていない。

```bash
cd conference
python3 -m tests.test_planners  # 変更前
# 既存12モジュールは各コマンドの成否を保存し、失敗後も次のモジュールを実行
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_mapfiles_sim
python3 -m tests.test_mission
python3 -m tests.test_natural_terrain
python3 -m tests.test_online
python3 -m tests.test_planners
python3 -m tests.test_real_beach
python3 -m tests.test_risk_prior
python3 -m tests.test_ros2_gz
python3 -m tests.test_tour
python3 -m tests.test_real_beach_las
python3 data_prep/export_maps.py
python3 data_prep/export_gazebo.py maps/real_las_08OB87_-0206_200m_0.npz gazebo_worlds/real_las_08OB87_-0206
python3 data_prep/compress_heightmap_png.py gazebo_worlds/real_las_08OB87_-0206/heightmap.png
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/las-mpl XDG_CACHE_HOME=/tmp/las-cache python3 experiments/real_beach.py --dataset shizuoka_beach_las
OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/las-mpl XDG_CACHE_HOME=/tmp/las-cache python3 experiments/compare_real_beach_las.py
```

既存 `test_mapfiles_sim` は最初の固定件数チェックで停止するため、`test_controller`・`test_tours`・`test_gazebo` も個別に実行した。
その際はテストモジュールの `RESULTS` だけを一時ディレクトリへ向け、既存結果を上書きしないようにした。テストの関数本体は変更していない。
APIの固定件数チェックの失敗も別途実行して記録した。

## テスト結果と指示の矛盾

新しいLASテストは通過。既存12モジュール中11モジュールが通過し、`tests.test_mapfiles_sim` が失敗した。
この既存テストは地図23枚・API40件・地図フォルダ合計15 MB未満を固定している。
指示書013に従って12枚を追加した結果は地図35枚・API52件となり、旧地図のバイト列を保つと合計15 MBも超える。
指示書の「それ以外の既存ファイルは変更しない」に従い、既存テストは変更していない。
したがって「すべてのテストが通る」という完了条件は未達であり、成功と扱わない。
`legacy_map_checks_proposed.patch` は既存23枚の件数・容量の検査を残して追加分を区別する修正案で、未適用。
追加12枚と全API地図IDの一致は新しいLASテストで別に厳密に確認している。

変更前のplannerテスト全文：


```text
all planner tests passed
roll-aware tests passed
```


既存全モジュールの実行出力全文：

```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
exit code: 0
$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
exit code: 0
$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
exit code: 0
$ python3 -m tests.test_mapfiles_sim
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_mapfiles_sim.py", line 362, in <module>
    check()
  File "/workspace/thesis_Bunker/conference/tests/test_mapfiles_sim.py", line 72, in test_maps
    assert len(files) == 23
           ^^^^^^^^^^^^^^^^
AssertionError
exit code: 1
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
exit code: 0
$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
exit code: 0
$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
exit code: 0
$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed
exit code: 0
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
exit code: 0
$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
exit code: 0
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
exit code: 0
$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed
exit code: 0
Failed modules: ['test_mapfiles_sim']
```


新規LASテストの出力全文：

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


固定件数チェック以外のmapfilesテストの出力全文：

```text
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Unchanged test functions; write-only test output redirected to a temporary folder to preserve old results.
$ test_controller
straight completed True max_deviation_m 3.552713678800501e-15 elapsed_s 19.700000000000003
right_angle completed True max_deviation_m 0.20226302369017546 elapsed_s 39.650000000000006
closed completed True max_deviation_m 0.3173559828528229 elapsed_s 68.35000000000001
controller: reverse-heading spin then advance, curvature-preserving saturation, timeout passed
$ test_tours
tour map=flat_test_100m.npz elapsed_s=248.15 deviation_mean_m=0.006614475997696592 deviation_max_m=0.33848962758007467 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
tour map=beach_gentle_200m_100.npz elapsed_s=418.45000000000005 deviation_mean_m=0.01568040573287969 deviation_max_m=0.20112452978749665 path_lethal_cells=0 out_of_bounds_samples=0 completed=True
contact_cells_xy_m []
$ test_gazebo
gazebo flat_test_100m.npz pixels 257 size_m 100.0 max_error_m 0.0 boxes 3
gazebo real_08OB87_-0206_200m_0.npz pixels 2049 size_m 200.0 max_error_m 0.06374200885325632 boxes 0
all unaffected mapfiles/simulation test functions passed
```


既存APIテストの出力全文：

```text
/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Traceback (most recent call last):
  File "<stdin>", line 2, in <module>
  File "/workspace/thesis_Bunker/conference/tests/test_mapfiles_sim.py", line 269, in test_api
    assert len(rows) == 40
           ^^^^^^^^^^^^^^^
AssertionError
```


比較の最終確認の出力全文：

```text
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
full experiment and comparison stdout are byte-identical to saved logs
both D sign/denominator presentations retain original raw CSV identities and statistics
```


## 既存結果の保全と生成物の検証

`baseline_sha256.json` は作業前の追跡済みconferenceファイルのSHA-256。
最終照合結果は `preservation_audit.json`。変更した既存ファイルは指示書が明示した4ファイルだけであり、
両データフォルダ・旧実験結果・既存地図・既存world・既存テストはすべてバイト単位で不変。
実行中の2ソースも起動時のハッシュと一致する（`run_source_sha256.json`）。
主要計算関数のASTが旧版と同じことは `source_invariants.json` に保存した。
変更前のGitソースを別モジュールとして実行し、変更後の既定値と配列・生成情報が完全一致することも確認した：


```text
Original Git source vs new default: bit-identical arrays and generation metadata for 12 scenarios
```


新規高さ画像の可逆圧縮の実測結果：

```text
{
  "before_bytes": 5053014,
  "after_bytes": 2623704,
  "png_filter": 1,
  "decoded_height_samples_sha256": "a0234e983dac6a5c7b0f0f6fd98a257ec974706c4ff5295c6e921531b59f714f",
  "samples_unchanged": true
}
```


地図とworldの生成出力全文：

```text
filename bytes shape
beach_gentle_100m_100.npz 350414 (200, 200)
beach_gentle_200m_100.npz 1387328 (400, 400)
beach_scarp_100m_100.npz 345052 (200, 200)
beach_scarp_200m_100.npz 1385591 (400, 400)
beach_steep_100m_100.npz 343970 (200, 200)
beach_steep_200m_100.npz 1366333 (400, 400)
flat_test_100m.npz 2679 (200, 200)
hills_100m_100.npz 336678 (200, 200)
hills_200m_100.npz 1344189 (400, 400)
real_08OB87_-0206_200m_0.npz 289106 (400, 400)
real_08OB88_01332_200m_0.npz 330826 (400, 400)
real_08OB89_-1597_200m_0.npz 342021 (400, 400)
real_08OC90_00270_200m_0.npz 314247 (400, 400)
real_08OC91_00811_200m_0.npz 329359 (400, 400)
real_08OC93_-1519_200m_0.npz 283523 (400, 400)
real_08OC95_-0321_200m_0.npz 373060 (400, 400)
real_08OC96_-0676_200m_0.npz 424352 (400, 400)
real_08OC97_-0077_200m_0.npz 403776 (400, 400)
real_08OC98_-1101_200m_0.npz 292594 (400, 400)
real_08OC98_01898_200m_0.npz 337849 (400, 400)
real_08OC99_00983_200m_0.npz 369582 (400, 400)
real_las_08OB87_-0206_200m_0.npz 398591 (400, 400)
real_las_08OB88_01332_200m_0.npz 526941 (400, 400)
real_las_08OB89_-1597_200m_0.npz 525882 (400, 400)
real_las_08OC90_00270_200m_0.npz 544691 (400, 400)
real_las_08OC91_00811_200m_0.npz 494585 (400, 400)
real_las_08OC93_-1519_200m_0.npz 381091 (400, 400)
real_las_08OC95_-0321_200m_0.npz 490627 (400, 400)
real_las_08OC96_-0676_200m_0.npz 525716 (400, 400)
real_las_08OC97_-0077_200m_0.npz 557198 (400, 400)
real_las_08OC98_-1101_200m_0.npz 376698 (400, 400)
real_las_08OC98_01898_200m_0.npz 392838 (400, 400)
real_las_08OC99_00983_200m_0.npz 452698 (400, 400)
rolling_100m_100.npz 338249 (200, 200)
rolling_200m_100.npz 1348342 (400, 400)
map_count 35 total_bytes 18310635
```

```text
map pixels side_m max_error_m quantization_bound_m obstacle_boxes
real_las_08OB87_-0206_200m_0.npz 2049 200.0 0.07634298480037804 6.236107878547843e-05 0
```


## 指示書009の結論との比較

比較方法は `COMPARISON_METHOD_ja.md` に固定した。
Bは元の5指標×漂着物2条件の10検定を再現する群と、今回依頼された6指標×2条件の補足12検定群を分けた。
同じCSV内の成功したTA*-S exactとA*を対応させ、両側WilcoxonとHolm補正を行う。
向きは対応のある順位二分相関rの符号。有意でない向きは記述的なものに限定する。
C/Dの各データの分布はそれぞれで成功したケース、データ間の対応差は両方で成功したケースで計算する。

A：凸凹の中央値は下がった。人工地形の凸凹が旧版では実測p10〜p90内でも、新版では外れる項目があり、
旧報告の「凸凹がよく合う」という一般化はそのまま維持できない。項目ごとの判定は下表のとおり。


```text
            metric  n  old_median  new_median  paired_delta_median
           slope50 60    4.387505    3.374561            -0.898305
           slope90 60   10.151660    9.464966            -0.369965
           slope99 60   24.088752   24.417334             0.351147
        steep_land 60    0.008754    0.009349             0.000234
foreshore_gradient 60    0.054286    0.053837            -0.000487
      land_width_m 60  102.500000   97.750000            -0.500000
             rough 60    0.019081    0.008300            -0.010720
          spectrum 60   -2.927093   -2.926401            -0.000889
       lethal_land 60    0.016606    0.019217             0.001040
   nodata_fraction 60    0.132631    0.130853             0.002116
    water_fraction 60    0.244400    0.240016            -0.002566
```


```text
        kind             metric  old_outside  new_outside   change  synthetic_old  synthetic_new   old_p10    old_p90   new_p10    new_p90
beach_gentle            slope90         True         True     both      39.952982      39.952982  7.256274  18.534176  6.902917  18.957478
beach_gentle            slope99         True         True     both      42.133279      42.133279 12.842008  36.299895 13.018389  37.850422
beach_gentle         steep_land         True         True     both       0.138051       0.138051  0.000434   0.058391  0.000612   0.060777
beach_gentle              rough        False         True new_only       0.019339       0.019339  0.017168   0.020750  0.006088   0.011521
beach_gentle        lethal_land         True         True     both       0.153638       0.153638  0.007798   0.069193  0.008629   0.071420
 beach_scarp            slope90         True         True     both      40.285310      40.285310  7.256274  18.534176  6.902917  18.957478
 beach_scarp            slope99         True         True     both      42.747419      42.747419 12.842008  36.299895 13.018389  37.850422
 beach_scarp         steep_land         True         True     both       0.213943       0.213943  0.000434   0.058391  0.000612   0.060777
 beach_scarp       land_width_m         True         True     both      16.000000      16.000000 71.950000 148.550000 66.625000 147.650000
 beach_scarp              rough        False         True new_only       0.019135       0.019135  0.017168   0.020750  0.006088   0.011521
 beach_scarp        lethal_land         True         True     both       0.229267       0.229267  0.007798   0.069193  0.008629   0.071420
 beach_steep            slope90         True         True     both      40.092516      40.092516  7.256274  18.534176  6.902917  18.957478
 beach_steep            slope99         True         True     both      42.210822      42.210822 12.842008  36.299895 13.018389  37.850422
 beach_steep         steep_land         True         True     both       0.161693       0.161693  0.000434   0.058391  0.000612   0.060777
 beach_steep foreshore_gradient         True         True     both       0.000726       0.000726  0.026634   0.090459  0.038980   0.075523
 beach_steep       land_width_m         True         True     both      29.000000      29.000000 71.950000 148.550000 66.625000 147.650000
 beach_steep              rough        False         True new_only       0.020247       0.020247  0.017168   0.020750  0.006088   0.011521
 beach_steep        lethal_land         True         True     both       0.172530       0.172530  0.007798   0.069193  0.008629   0.071420
```


B：急斜面の回避、平均地形コスト・登り・エネルギー・横傾き95%値の低下というTA*-S exactの利点は維持された。
急斜面を通る経路の割合の旧／新の値は、下の比較ログの `steep_exposed_pct` を参照。
経路長の結論は変わった。漂着物なしでは旧版の「exactが長い」から新版の「exactが短い」へ、有意な順位方向が反転した。
漂着物ありでは旧版の有意な延長が新版では有意でなくなった。新しい周辺中央値の大小だけで対応差の向きを判断してはいない。
元の検定群で結論が変わった行は次のとおり（補足群の同じ行を重複掲載しない）。


```text
        family  debris    metric  n_old center      A_old  exact_old  delta_median_old        p_old    r_old   p_holm_old  significant_old direction_old  n_new      A_new  exact_new  delta_median_new    p_new     r_new  p_holm_new  significant_new direction_new  significance_changed  direction_changed
original009_10   False length_xy     96 median 120.556252 121.927353          2.388019 7.186126e-08 0.633162 3.593063e-07             True        higher     96 120.556252 120.845079         -2.531013 0.000352 -0.420103    0.001407             True         lower                 False               True
original009_10    True length_xy     96 median 121.754076 126.545869          3.823231 1.041361e-10 0.759450 6.248165e-10             True        higher     96 120.746068 121.498341         -0.657586 0.301057 -0.121564    0.301057            False         lower                  True               True
```


C：非oracle再計画方式の全条件でdJの中央値とp90が低下した。全走行成功・接触0件という安全性の結論は変わらない。
一方、条件ごとの最大値はすべてが改善したわけではなく、理想との差が大きい走行も残る。
dJは `J=length_xy*(1+w*mean_cost)` の理想比であり、登りだけの指標ではない。
旧報告の「人工地形より実測砂浜のほうが一律にはっきり悪い」は、LAS版の条件別数値を踏まえて限定する必要がある。
粗地図・センサー条件による差と、悪いケースが残るという課題は維持される。


```text
 debris  side_m             variant  old_median  new_median   old_p90   new_p90    old_max    new_max  paired_delta_median
  False     100      coarse R10 c10    3.919959    2.338669 15.436609 10.465466  26.186679  23.393576            -2.603381
  False     100       coarse R15 c5    2.049860    1.100970  7.471233  2.794366  25.517642  39.061705            -0.424609
  False     100       coarse R5 c10   12.050919    3.206860 25.172574 17.168507  44.769916  33.157836            -7.669307
  False     100       coarse R5 c20   16.480875    6.575690 37.509418 27.897445  75.460354  48.631234           -10.120827
  False     100 online adaptive R15    7.023523    2.609656 18.305210 10.651708  27.123833  23.040218            -3.579961
  False     200      coarse R10 c10    8.788571    5.581599 26.728529 22.029183 127.846940 112.148633            -2.935136
  False     200       coarse R15 c5    2.962478    1.867533 10.628386  7.980006  95.858952  91.190833            -1.155284
  False     200       coarse R5 c10   17.961466    6.838625 35.929726 23.986218 162.392533 132.758440            -9.295420
  False     200       coarse R5 c20   22.930745   10.873800 41.614864 35.415341 204.053544 143.099312            -8.635555
  False     200 online adaptive R15   21.305976   10.040866 39.934192 27.121856 130.658253 108.128446            -8.656784
   True     100      coarse R10 c10    5.300609    3.541320 12.146801  9.593664  28.053196  23.305156            -1.273090
   True     100       coarse R15 c5    2.644415    1.508827  6.286856  5.416225  11.914968  32.248812            -0.670589
   True     100       coarse R5 c10   10.447602    6.471225 24.244198 14.877626  39.597509  32.077633            -4.583291
   True     100       coarse R5 c20   14.576964    9.233347 32.342965 25.237399  64.757384  45.867977            -6.716260
   True     100 online adaptive R15    6.731344    4.464567 13.612464  9.276607  27.461841  12.551185            -2.806280
   True     200      coarse R10 c10    7.117927    6.025369 20.811536 14.480009 123.859773 111.260017            -0.754757
   True     200       coarse R15 c5    3.157773    2.699064  9.641318  8.818788  93.962623  59.141939            -0.433700
   True     200       coarse R5 c10   16.642045    9.809825 31.377017 22.493658 153.397389 162.311135            -5.302173
   True     200       coarse R5 c20   20.468678   13.424759 42.612866 31.858610 195.457777 138.201230            -7.778291
   True     200 online adaptive R15   19.488763   12.858493 35.469563 23.983535 127.316816 100.021040            -5.505907
```


D：次表は `100*(terrain dir/euclid-1)`。負ならterrain dirが小さく、p90はこの符号で悪い側の裾である。
旧報告のeuclidの過剰率（euclid/dir−1）とは分母・符号が異なるので、数値をそのまま置換しない。
地点数ごとの元の検定もcompare_log末尾にそのまま掲載した。


```text
 debris  n_goals    metric  n  paired_success  old_success  new_success  old_median  old_p90  new_median  new_p90  paired_delta_median
  False        5  cost_dir 48              48           48           48   -0.049098 0.000000   -0.088970 0.000000             0.000000
  False        5 energy_kj 48              48           48           48    0.000000 0.943002    0.000000 0.250663            -0.003636
  False        8  cost_dir 48              48           48           48   -0.084125 0.000000   -0.079906 0.000000             0.000000
  False        8 energy_kj 48              48           48           48    0.000000 1.017967    0.000000 0.283432             0.000000
  False       12  cost_dir 48              48           48           48   -0.162020 0.000000   -0.116424 0.000000            -0.035876
  False       12 energy_kj 48              48           48           48    0.000000 1.250485    0.000000 1.053664            -0.001622
   True        5  cost_dir 48              48           48           48   -0.068221 0.000000   -0.089465 0.000000             0.000000
   True        5 energy_kj 48              48           48           48    0.000000 0.285900    0.000000 0.274946             0.000000
   True        8  cost_dir 48              48           48           48   -0.137120 0.000000   -0.122656 0.000000             0.026608
   True        8 energy_kj 48              48           48           48    0.000000 0.180144    0.000000 0.421158             0.087716
   True       12  cost_dir 48              48           48           48   -0.187688 0.000000   -0.262398 0.000000             0.002743
   True       12 energy_kj 48              48           48           48    0.000000 0.732722    0.000000 0.322986            -0.067250
```


旧報告と同じ分母・符号のeuclid過剰率：

```text
 debris  n_goals    metric  n  paired_success  old_success  new_success  old_median  old_p90  new_median  new_p90  paired_delta_median
  False        5  cost_dir 48              48           48           48    0.049122 1.404404    0.089050 0.946608             0.000000
  False        5 energy_kj 48              48           48           48    0.000000 0.352756    0.000000 1.154028             0.003636
  False        8  cost_dir 48              48           48           48    0.084196 4.059831    0.079970 3.043834             0.000000
  False        8 energy_kj 48              48           48           48    0.000000 1.499169    0.000000 2.542933             0.000000
  False       12  cost_dir 48              48           48           48    0.162283 5.010939    0.116560 9.824849             0.035964
  False       12 energy_kj 48              48           48           48    0.000000 1.831711    0.000000 6.038719             0.001622
   True        5  cost_dir 48              48           48           48    0.068270 1.076173    0.089550 1.510071             0.000000
   True        5 energy_kj 48              48           48           48    0.000000 0.846048    0.000000 0.667110             0.000000
   True        8  cost_dir 48              48           48           48    0.137312 3.113590    0.122807 2.176099            -0.026663
   True        8 energy_kj 48              48           48           48    0.000000 1.726978    0.000000 0.961838            -0.087792
   True       12  cost_dir 48              48           48           48    0.188041 5.697898    0.263089 5.516242            -0.002747
   True       12 energy_kj 48              48           48           48    0.000000 2.527536    0.000000 4.325577             0.067072
```


巡回の物理コスト過剰率の中央値は小さいという結論と、元の検定の有意性は維持された（有意性変化 0/12 行）。
ただし、裾の変化は一方向ではない。12地点・漂着物なしのeuclid過剰率p90は旧 5.010939% →新 9.824849% と増えた。
中央値が小さいことは、すべての巡回で順番が重要でないことを意味しない。また物理コストを最小にする順序が、エネルギーも常に最小にするとは限らない。
巡回点の集合は対応監査上すべての名目ケースで旧／新が異なるため、効果量の差を同一地点集合での変化とは解釈しない。



同じ名目のパッチ・大きさ・シード・漂着物条件を対にした再実験であり、標高データだけを替えて全座標を固定した因果比較ではない。
地形マスクが変わるとリトライ、切り出し、開始終了点、漂着物中心、巡回地点も変わり得る。対応監査表を比較ログに掲載した。
したがって差のすべてを0.1m量子化の除去だけに帰属させない。

## 実測時間

以下は `runtime.json` と `compare_runtime.json` の値そのまま。
旧版と新版はワーカー数・実行機・負荷が異なるため、処理速度の比較には使わない。


```text
{
  "phase_wall_s": {
    "A": 4.953430665002088,
    "B": 62.35352810299082,
    "C": 1902.2930275440012,
    "D": 1077.7792965300032,
    "figures": 13.845099055004539
  },
  "total_wall_s": 3061.597141278995,
  "workers": 5,
  "resume": false,
  "cache_fingerprint": "0a4089c6c548ddc8",
  "per_job_elapsed_sum_s": {
    "A": 22.94389558804687,
    "B": 308.7925888680329,
    "C": 9361.066424898032,
    "D": 5336.5233459280425
  }
}
```

```text
{
  "wall_time_s": 0.847068744013086
}
```


## 全実験の集計出力（そのまま）

```text

A: supplied patches violating the requested mean-profile orientation (data unchanged)
Empty DataFrame
Columns: [kind, split, sea_side_mean, front_profile_max]
Index: []

A: terrain statistics; medians over patches / artificial validation seeds
   source        group  slope50  slope90  slope99  steep_land  foreshore_gradient  land_width_m      rough  spectrum  lethal_land
     real         test  3.39872    9.688  25.0103   0.0103591           0.0538368         97.75 0.00822506  -2.92516    0.0210039
     real   validation  3.25159  8.67002  22.1032  0.00605305           0.0553454       100.875 0.00862752  -2.93679    0.0157128
synthetic beach_gentle  3.52068   39.953  42.1333    0.138051           0.0432445          89.5  0.0193392  -2.93473     0.153638
synthetic  beach_scarp  3.87395  40.2853  42.7474    0.213943           0.0716077            16  0.0191346  -2.93929     0.229267
synthetic  beach_steep  3.88004  40.0925  42.2108    0.161693         0.000726161            29  0.0202472  -2.93737      0.17253

A: real-patch 10th/90th percentiles (all 60; descriptive, never used for tuning)
 quantile  slope50  slope90  slope99  steep_land  foreshore_gradient  land_width_m      rough  spectrum  lethal_land
      0.1  2.40174  6.90292  13.0184 0.000612472             0.03898        66.625 0.00608757  -2.97125   0.00862912
      0.9   4.4866  18.9575  37.8504   0.0607766           0.0755233        147.65  0.0115208  -2.90395    0.0714204

A: artificial medians outside real 10..90% range
        kind             metric  synthetic_median    real_p10  real_p90
beach_gentle            slope90            39.953     6.90292   18.9575
beach_gentle            slope99           42.1333     13.0184   37.8504
beach_gentle         steep_land          0.138051 0.000612472 0.0607766
beach_gentle              rough         0.0193392  0.00608757 0.0115208
beach_gentle        lethal_land          0.153638  0.00862912 0.0714204
 beach_scarp            slope90           40.2853     6.90292   18.9575
 beach_scarp            slope99           42.7474     13.0184   37.8504
 beach_scarp         steep_land          0.213943 0.000612472 0.0607766
 beach_scarp       land_width_m                16      66.625    147.65
 beach_scarp              rough         0.0191346  0.00608757 0.0115208
 beach_scarp        lethal_land          0.229267  0.00862912 0.0714204
 beach_steep            slope90           40.0925     6.90292   18.9575
 beach_steep            slope99           42.2108     13.0184   37.8504
 beach_steep         steep_land          0.161693 0.000612472 0.0607766
 beach_steep foreshore_gradient       0.000726161     0.03898 0.0755233
 beach_steep       land_width_m                29      66.625    147.65
 beach_steep              rough         0.0202472  0.00608757 0.0115208
 beach_steep        lethal_land           0.17253  0.00862912 0.0714204

B: offline medians; energy only relative to A* [%]
 debris     planner  success  exposed  steep_len      cost    climb  energy_vs_A_pct  max_roll  p95_roll  roll_frac  length      time  touching
  False          A*        1  0.09375          0  0.114426   1.4402                0   7.54186   5.57075          0 120.556 0.0388447        10
  False       A*-HC        1        0          0   0.11314  1.43798                0   7.54186   5.49912          0 120.556 0.0327955         0
  False         TA*        1        0          0 0.0697229  1.06447          0.36477   4.64334   3.03726          0 123.588  0.132308         0
  False       TA*-S        1        0          0  0.077346 0.959826         -4.06554   5.19929   3.52955          0 120.845   0.21052         1
  False TA*-S exact        1        0          0  0.077346 0.959826         -4.06554   5.19929   3.52955          0 120.845  0.200334         0
   True          A*        1  0.09375          0  0.144652  2.22844                0    9.9395    6.1046          0 120.746 0.0368271        10
   True       A*-HC        1        0          0  0.143453  2.20715                0    9.9395    6.0842          0 120.746 0.0303251         0
   True         TA*        1        0          0 0.0795201  1.35294        0.0215213   5.50826   3.35916          0 127.891  0.137049         0
   True       TA*-S        1        0          0 0.0887103  1.25993         -4.49297   6.43402   3.73449          0 121.498    0.2158        10
   True TA*-S exact        1        0          0 0.0887103  1.25993         -4.49297   6.35616   3.74967          0 121.498  0.217766         0

B: paired two-sided Wilcoxon; Holm over ten tests
 debris          metric  n           p         r      delta      p_holm
  False       steep_len 96  0.00390625        -1          0   0.0117188
  False       mean_cost 96  4.0231e-17 -0.988832 -0.0280918 3.62079e-16
  False           climb 96 2.12358e-16 -0.965636  -0.286006  1.4865e-15
  False energy_vs_A_pct 96 3.50869e-10 -0.737543   -4.06554 2.10521e-09
  False       length_xy 96 0.000351682 -0.420103   -2.53101  0.00140673
   True       steep_len 96  0.00390625        -1          0   0.0117188
   True       mean_cost 96 1.78129e-17        -1 -0.0450661 1.78129e-16
   True           climb 96 4.70068e-17 -0.986684   -0.55376 3.76055e-16
   True energy_vs_A_pct 96 1.22361e-09 -0.714347   -4.49297 6.11805e-09
   True       length_xy 96    0.301057 -0.121564  -0.657586    0.301057

B: failures
Empty DataFrame
Columns: [kind, side_m, seed, debris, planner, reason]
Index: []

C: online medians and tails; dJ/dL/dE relative to exact oracle [%]
 debris             variant  success  exposed      dJ        dL        dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax      dL90   dLmax
  False      coarse R10 c10        1        0 3.56819 -0.597338 -0.233341 -5.46912  5.12235   42.5    3.72034         0 17.4858 112.149   1.72976 83.7075
  False       coarse R15 c5        1        0 1.47224 -0.398279 -0.177903 -4.95365  4.89136     34    3.19128         0 7.71131 91.1908   1.10167 72.3785
  False       coarse R5 c10        1        0 5.29899 -0.823635 -0.354789 -5.13266  5.23252   45.5    3.81874         0 22.5308 132.758   2.00685 58.5615
  False       coarse R5 c20        1        0 8.30604  -1.08499 -0.479488  -5.7659  5.87188   52.5    4.40457         0 33.8012 143.099   3.49473 63.7171
  False online adaptive R15        1        0 5.93198  -1.71328   -1.2914 -6.15216  5.46061   17.5    2.21973         0 19.9673 108.128 0.0869126  48.466
  False           oracle A*        1  0.09375 16.2809   2.18971   4.23786        0  6.06691      1  0.0388447        10 44.4052 183.095   6.89465 8.14806
  False        oracle TA*-S        1        0       0         0         0 -4.06554  4.66544      1   0.200334         0       0       0         0       0
   True      coarse R10 c10        1        0   4.163  -1.02132 -0.401582 -4.89358  5.30414     62    5.52725         0 12.9794  111.26   2.25477 83.6078
   True       coarse R15 c5        1        0  1.9271 -0.217183   -0.1499 -4.54618  5.04178     57    5.07463         0 7.38801 59.1419   1.57611 54.6364
   True       coarse R5 c10        1        0 7.93078  -1.55193  -0.59463 -5.13661  5.57613   66.5    5.32911         0 20.4334 162.311   1.52174 57.4176
   True       coarse R5 c20        1        0 11.6255  -1.60904 -0.601576 -5.58786  6.15314   71.5    5.71411         0 29.4531 138.201   3.91831 57.2726
   True online adaptive R15        1        0 7.68121  -1.59426 -0.694534 -5.97522  5.71569     26    3.14006         0  18.205 100.021  0.599099 72.1412
   True           oracle A*        1  0.09375 21.3221  0.839346   4.70435        0   6.9419      1  0.0368271        10 52.3038 171.187   4.99976 8.05843
   True        oracle TA*-S        1        0       0         0         0 -4.49297  4.94659      1   0.217766         0       0       0         0       0

C: per patch median dJ [%], debris=False
        kind  coarse R10 c10  coarse R15 c5  coarse R5 c10  coarse R5 c20  online adaptive R15  oracle A*  oracle TA*-S
08OB86_-0205          1.8034        1.51697        2.28483        33.0595              5.89702    25.6828             0
08OB86_00294         3.85464       0.209554        4.29364         4.0829              4.02563    11.1113             0
08OB87_-0706         5.59662        3.16221        6.33974        8.70125              9.35766    20.6118             0
08OB88_-0167         57.3272        46.5337        67.6599        72.8303              55.3449    20.2865             0
08OB88_-1417         1.22598       0.108316        6.54903          9.931              1.58339    25.9564             0
08OB88_00332         5.88673        3.02868        8.63353         13.031               11.225    7.06813             0
08OB88_01832         2.54153       0.406848        2.18574        19.7912              11.9174    40.1893             0
08OB89_-0347         0.94765         0.3565        2.36117        9.82841              5.02869    10.5104             0
08OB89_-0847         5.50334        4.00419        7.26894        14.2191               9.3461    22.1185             0
08OB89_00152         6.81187        1.66258        7.24689        6.54849              7.24689    12.2546             0
08OC80_-0589         2.16308        1.81605        1.92473        2.21368              4.78899    13.5832             0
08OC80_-1089         7.07726        4.21029        8.70688        8.77041              17.7478    14.7276             0
08OC80_00160         5.32412        1.41352        11.3009        9.37114              8.66201    45.6394             0
08OC80_00660          4.8044        4.17709        5.82118        6.54954              17.7933    22.8978             0
08OC91_-0438          4.0967        3.21759        4.35803        7.13908              6.52339    17.2427             0
08OC91_-0938         3.26886        1.56824        7.42331         8.6472              9.80394     23.419             0
08OC91_-1688         2.63954        1.19637        4.74308        10.1925              3.68389    35.9635             0
08OC91_00061         4.27156       0.941402        3.14082        8.45868              4.16077    33.6004             0
08OC91_01311         1.75258        1.04102        2.03181        20.8614              19.2719    36.0179             0
08OC92_-0141         15.6896        12.3375        14.8319        17.9018              16.0557    27.2207             0
08OC92_-0891         7.93441        2.21939        11.5596        13.6685              13.4461    17.0293             0
08OC92_00608         2.97211        1.09351         4.5962        12.3198              5.80956     10.495             0
08OC94_-0954         21.4897        7.48849        50.4615        42.4524              11.8039    100.197             0
08OC95_-0821         1.71338       0.530901        2.40627        2.24846              2.12377    10.2212             0
08OC95_-1321         12.2734        2.80529        12.3801         13.415              10.8983    20.6449             0
08OC95_-2071         1.51758       0.821785        2.76452        6.86128                3.277    11.5568             0
08OC95_00428         10.8676        20.0946        10.9025        41.4692              15.5798    18.1597             0
08OC95_00928         2.18329       0.957359        3.54734          4.371               3.1053     12.789             0
08OC95_01428         14.5523       0.404713        23.1616        26.8295              5.97924     14.532             0
08OC96_-1426         5.17351      -0.209094        6.94922        9.04993              5.61021    38.3144             0
08OC96_00073         2.81217        1.19247        2.92771        4.09526              2.89957    13.5356             0
08OC97_-0577         14.0677        5.59621        15.8582        18.8379              15.3264    23.1154             0
08OC97_-1077         3.13952         1.3134        6.47645        16.7732              9.87367    16.6476             0
08OC97_-1827         10.6335        2.76746        11.3312        5.50832              9.78566    43.3591             0
08OC97_00422         2.13619        4.63742        2.37841        3.78234              6.59663    10.1911             0
08OC97_01172         6.05953        1.48891        6.51737        23.7416              5.85703    15.7795             0
08OC97_01672         4.69172        2.56995        5.01853        5.43597              4.14707    10.9064             0
08OC98_-0351         2.49481        2.46834        12.3159        11.9149              8.70576    14.2969             0
08OC98_-1601         2.77217        1.10399        3.60289        4.24195              3.88313    15.5157             0
08OC98_00148         1.41769        1.35883        7.69018        36.0668              3.87565    30.7855             0
08OC98_00648        0.529172        0.43244       0.563427        2.82759              1.07221    13.2336             0
08OC98_01398         0.43198      -0.487128       0.280825     -0.0167194            0.0712405    8.91344             0
08OC99_-0016         1.67701       0.626274        1.74466        2.99779              6.87693    3.49782             0
08OC99_-1016         8.56576        2.97488        20.6674        17.0766              5.22348    30.0212             0
08OC99_-1516         13.0495        4.94632        13.0923        11.8965              11.7311    15.2744             0
08OC99_00483         15.6265        12.0727        22.7674        20.5125              18.7584    17.1659             0
08OC99_01733         4.41654        5.54873        5.64972        5.30165              4.20587    18.9746             0
08PD00_-1730         11.3937         5.0947        19.4897        17.0114              17.1316    41.3909             0

C: per patch median dJ [%], debris=True
        kind  coarse R10 c10  coarse R15 c5  coarse R5 c10  coarse R5 c20  online adaptive R15  oracle A*  oracle TA*-S
08OB86_-0205         2.56668        1.82059        3.26826        31.2677              5.78672    30.2997             0
08OB86_00294         4.95016        2.15964        8.83226        9.25676              7.83601    15.9156             0
08OB87_-0706         5.72958        4.32945        6.81288        9.59299               7.4879    25.7363             0
08OB88_-0167           56.98        29.9425        66.9995        72.8298              53.1088    19.7932             0
08OB88_-1417         5.06335        2.12251        7.56566          9.323              5.98638    90.5137             0
08OB88_00332         10.2825         9.3559        13.2588        14.1995              9.82218    20.8529             0
08OB88_01832         2.06642       0.884934        3.66482        18.9196              14.7525    40.4101             0
08OB89_-0347         3.71555        1.87828        5.68324        5.30943              3.80071    19.9804             0
08OB89_-0847         2.31006        1.13109         5.5914        11.6838              10.6907    35.5985             0
08OB89_00152         4.97454        1.98562        10.9122        9.05599              9.01472    15.2039             0
08OC80_-0589         6.92744        2.07057        11.4117        10.5417              11.6732    33.2884             0
08OC80_-1089         7.75604        4.23894        10.2855        12.6937              13.4778    22.6848             0
08OC80_00160         4.28072        2.37162        9.85653         9.7466              15.1984     54.937             0
08OC80_00660         2.00049       0.995808        2.81067        3.95553              20.6868    28.4616             0
08OC91_-0438          2.4747        2.40603        4.34809         13.434              6.70355    20.7438             0
08OC91_-0938         3.12261        1.83087        8.94968        12.3468              10.8359    31.8915             0
08OC91_-1688         4.80011        0.48198        9.06717        11.4375              4.81039    35.4822             0
08OC91_00061         6.73942        1.56154        5.18331        12.9503              7.32306    34.6732             0
08OC91_01311         2.25916        1.35678        2.27236        22.3569              23.6369    39.7375             0
08OC92_-0141         9.46059        7.44278        10.9743        16.1043              7.45718    12.1088             0
08OC92_-0891         6.16588        3.42234         9.8501        13.5461              10.9331     16.713             0
08OC92_00608         4.02123        1.58915        6.28705        16.5475              7.83991    20.0206             0
08OC94_-0954         18.3465        5.57412         87.305        41.1396              13.7032     95.646             0
08OC95_-0821         2.36379       0.972006        4.53153        4.01257              2.55146    13.2851             0
08OC95_-1321         7.91649        3.54231        13.3351        14.8895               8.4345    19.6719             0
08OC95_-2071         5.96173        5.82154        8.45643        13.0332              11.5667    22.5502             0
08OC95_00428         8.62139         16.839        12.9408        34.2321              11.0329    21.3747             0
08OC95_00928         5.80759        1.65262        6.54417        7.92349              5.73774    29.9136             0
08OC95_01428         7.89334        1.22751        18.3163        37.1508              7.63445     39.036             0
08OC96_-1426         5.94435        1.11662        6.97253        9.85007               5.5189    33.9407             0
08OC96_00073         4.42703        1.98162        6.27856        5.66837              5.41753    13.7944             0
08OC97_-0577         14.7037        4.98714        17.0879        16.8231              14.5997    24.7783             0
08OC97_-1077         2.79305        1.24475        7.72827        16.2875              9.91823    21.8337             0
08OC97_-1827         7.60423        5.42191        8.64896        5.69271              3.76727    41.6516             0
08OC97_00422         3.39589        3.90762        5.83116        4.81214              8.46859    16.0177             0
08OC97_01172         5.28789        1.22219        8.76158        23.2428              6.33846    20.9471             0
08OC97_01672         6.58242        1.43509        6.08587        13.0549              8.14112    25.5439             0
08OC98_-0351         4.18615        4.65956        12.7038        10.0236              9.96701    18.0202             0
08OC98_-1601         2.85083        1.12924         5.2003        7.14622              5.64858     18.385             0
08OC98_00148         1.98265        1.19922         11.052        34.2159              5.23929    33.8392             0
08OC98_00648          5.9445        4.08533        5.56534        8.04798              4.83552    19.3681             0
08OC98_01398         3.30444        3.19856        5.51335        5.28674              4.41737    17.9961             0
08OC99_-0016          4.9136        2.08876        7.59022         8.7537              9.69901    15.1728             0
08OC99_-1016         17.8966        4.46317        24.6138        21.7125              7.58302    43.7479             0
08OC99_-1516         14.9396        7.41247        14.6159        14.8677              5.37457    19.5013             0
08OC99_00483         8.22336        5.27592        15.4565        15.5345              7.80817    20.0025             0
08OC99_01733         7.38985        3.06178        15.9203        13.8676              6.71593    26.1415             0
08PD00_-1730         12.0554        1.93856        19.9923        14.3713               12.757    37.6331             0

C: all dJ > 25% trajectories (largest ten plotted)
        kind  side_m  seed  debris             variant      dJ        dL  n_plans
08OC94_-0954     200     0    True       coarse R5 c10 162.311   11.2314      161
08OB88_-0167     200     0   False       coarse R5 c20 143.099   63.7171      395
08OB88_-0167     200     0    True       coarse R5 c20 138.201   57.2726      392
08OB88_-0167     200     0   False       coarse R5 c10 132.758   58.5615      358
08OB88_-0167     200     0    True       coarse R5 c10 127.893   57.4176      361
08OB88_-0167     200     0   False      coarse R10 c10 112.149   83.7075      335
08OB88_-0167     200     0    True      coarse R10 c10  111.26   83.6078      361
08OB88_-0167     200     0   False online adaptive R15 108.128    48.466      182
08OB88_-0167     200     0    True online adaptive R15 100.021   72.1412      193
08OB88_-0167     200     0   False       coarse R15 c5 91.1908   72.3785      291
08OC94_-0954     200     0   False       coarse R5 c10 89.3092   6.80996      153
08OC94_-0954     200     0   False       coarse R5 c20  71.318   3.08273      141
08OC94_-0954     200     0    True       coarse R5 c20 68.3749   2.89014      146
08OB86_-0205     200     0   False       coarse R5 c20 59.3626   9.51528      142
08OB88_-0167     200     0    True       coarse R15 c5 59.1419   54.6364      304
08OB86_-0205     200     0    True       coarse R5 c20 55.9061   9.50801      138
08OC98_00148     100     0   False       coarse R5 c20 48.6312 -0.531785       48
08OC98_00148     100     0    True       coarse R5 c20  45.868   1.21901       56
08OC95_01428     100     0    True       coarse R5 c20 43.4389   10.0261       44
08OC95_00428     100     0   False       coarse R5 c20 41.9641  0.314841       71
08OC95_01428     100     0   False       coarse R5 c20 41.6772   9.50044       43
08OC95_00428     200     0   False       coarse R5 c20 40.9742    8.9175      126
08OC95_00428     200     0    True       coarse R5 c20 40.4207   7.40232      160
08OC80_00660     200     0    True online adaptive R15 39.2602  -8.25134       46
08OC95_00428     100     0   False       coarse R15 c5 39.0617   4.91321       62
08OC91_01311     200     0    True online adaptive R15 37.7476   -12.067       41
08OC99_00483     200     0   False       coarse R5 c20 35.8661  -13.1904      139
08OC80_00660     200     0   False online adaptive R15 35.5866  -3.45223       15
08OC99_00483     200     0   False online adaptive R15 35.5541  -10.4632       75
08OC97_01172     100     0   False       coarse R5 c20 35.4914   4.12574       51
08OC91_01311     200     0   False       coarse R5 c20 35.2221  -8.09814      141
08OC91_01311     200     0   False online adaptive R15 35.0873  -11.5436       40
08OC99_00483     200     0   False       coarse R5 c10 34.9448  -12.7938      134
08OC91_01311     200     0    True       coarse R5 c20 34.1821  -8.90095      140
08OC99_-1016     100     0   False       coarse R5 c10 33.1578   1.71095       71
08OC97_01172     100     0    True       coarse R5 c20 33.0063   4.71248       57
08PD00_-1730     200     0   False online adaptive R15  32.923  -6.13893       92
08OC94_-0954     200     0   False      coarse R10 c10 32.4935   1.90401      135
08OB88_01832     100     0   False       coarse R5 c20 32.3802  0.284133       57
08OC95_00428     100     0    True       coarse R15 c5 32.2488  0.695237       64
08OC99_-1016     100     0    True       coarse R5 c10 32.0776     1.927       73
08OB88_01832     100     0    True       coarse R5 c20  31.156 -0.805927       59
08OC95_01428     200     0    True       coarse R5 c20 30.8628  0.524002       97
08OC95_01428     200     0   False       coarse R5 c10 30.1838  -2.41726      107
08PD00_-1730     100     0    True       coarse R5 c10 30.1458   8.02423       63
08PD00_-1730     100     0   False       coarse R5 c10 29.2641   6.19819       61
08OC97_-0577     200     0   False       coarse R5 c20 28.5455   9.24153      148
08OC95_00428     100     0    True       coarse R5 c20 28.0434  -1.09787       72
08OC94_-0954     200     0    True      coarse R10 c10 27.4364   3.58674      134
08OC99_00483     200     0   False      coarse R10 c10 26.9698   -13.624      123
08OC95_01428     200     0   False      coarse R10 c10  26.505  -1.34816       98
08OC99_01733     200     0    True       coarse R5 c10  26.161  -1.57366      158
08OC99_-1016     100     0   False       coarse R5 c20 25.9763   3.90673       80
08OC92_-0141     100     0   False       coarse R5 c20 25.9547  -16.4467       73
08OB88_01832     200     0    True online adaptive R15 25.2587  -1.40754       94

C: failures
Empty DataFrame
Columns: [kind, side_m, seed, debris, variant, reason]
Index: []

D: tour metrics; relative cost and energy vs terrain dir [%]
 debris  n_goals      method  success  cost_rel_pct_median  cost_rel_pct_p90  energy_rel_pct_median  energy_rel_pct_p90  length_xy_median  length_xy_p90  climb_median  climb_p90  p95_roll_median  p95_roll_p90  steep_len_median  steep_len_p90
  False        5      euclid        1            0.0890499          0.946608                      0             1.15403            413.79        517.542       7.38666    11.7746          4.34278       7.68494                 0              0
  False        5 terrain dir        1                    0                 0                      0                   0           415.113        516.901       7.26286    11.5904          4.36693       7.19808                 0              0
  False        5 terrain sym        1                    0         0.0969095                      0           0.0370069           415.113        516.901       7.26286    11.6725          4.36693       7.12989                 0              0
  False        8      euclid        1            0.0799695           3.04383                      0             2.54293           477.363        569.899       8.89422    13.6891          4.68422       7.74846                 0              0
  False        8 terrain dir        1                    0                 0                      0                   0           476.953        576.352       8.79367    13.1809          4.56855       7.57132                 0              0
  False        8 terrain sym        1            0.0096036           0.10713                      0            0.188257           476.784        576.029       8.95468    13.1611           4.6013       7.55097                 0              0
  False       12      euclid        1              0.11656           9.82485                      0             6.03872            547.15        686.011       10.9892    18.4191          5.29414       8.17569                 0              0
  False       12 terrain dir        1                    0                 0                      0                   0           549.552        637.725       10.8394    16.2849          5.11519       7.84697                 0              0
  False       12 terrain sym        1                    0           0.17267                      0           0.0673117           549.552        638.707       10.8394    16.2872          5.05071       7.86274                 0              0
   True        5      euclid        1            0.0895497           1.51007                      0             0.66711           407.875        482.372       7.56817    11.5161          4.89798       6.42011                 0              0
   True        5 terrain dir        1                    0                 0                      0                   0           407.755        478.297       7.57283     11.716          4.89798       6.42482                 0              0
   True        5 terrain sym        1                    0           0.12981                      0            0.211362           407.828        478.825       7.56817     11.716          4.86502       6.42482                 0              0
   True        8      euclid        1             0.122807            2.1761                      0            0.961838           484.052        558.949       9.46804    14.1032          5.14238       7.08777                 0              0
   True        8 terrain dir        1                    0                 0                      0                   0           484.517        558.909       9.51833    14.0422          4.98651       6.80248                 0              0
   True        8 terrain sym        1                    0          0.157761                      0            0.290219           484.717        558.949       9.63875     13.972          4.98651       6.91949                 0              0
   True       12      euclid        1             0.263089           5.51624                      0             4.32558           539.915        672.997       11.4374    18.5017          5.30391       7.47157                 0              0
   True       12 terrain dir        1                    0                 0                      0                   0           542.458        661.356       11.4374     16.575          5.11572       7.37636                 0              0
   True       12 terrain sym        1                    0          0.106666                      0            0.163923           542.179        661.143       11.4374    16.5409          5.11572       7.37636                 0              0

D: per-patch directed cost relative to Euclidean ordering [%]
        kind  n_goals   clean_pct  debris_pct
08OB86_-0205        5           0           0
08OB86_-0205        8           0   -0.167304
08OB86_-0205       12  -0.0578358   -0.269809
08OB86_00294        5  -0.0810226     -2.5009
08OB86_00294        8           0     -1.6546
08OB86_00294       12   -0.181806    -2.69643
08OB87_-0706        5   -0.288022   -0.277996
08OB87_-0706        8  -0.0186917   -0.141776
08OB87_-0706       12           0   -0.295071
08OB88_-0167        5    -4.22881    -0.16271
08OB88_-0167        8    -8.54302    -0.51918
08OB88_-0167       12    -25.5414    -19.2029
08OB88_-1417        5           0   -0.149244
08OB88_-1417        8   -0.293277           0
08OB88_-1417       12   -0.363783   -0.583908
08OB88_00332        5   -0.287108           0
08OB88_00332        8           0           0
08OB88_00332       12    -0.24204           0
08OB88_01832        5  -0.0402916  -0.0224316
08OB88_01832        8           0           0
08OB88_01832       12    -2.07786   -0.100205
08OB89_-0347        5   -0.113298   -0.298106
08OB89_-0347        8     -0.3519   -0.115576
08OB89_-0347       12           0           0
08OB89_-0847        5           0           0
08OB89_-0847        8    -4.21044           0
08OB89_-0847       12    -1.92369  -0.0632528
08OB89_00152        5           0   -0.162035
08OB89_00152        8  -0.0732891    -0.92372
08OB89_00152       12     -0.1338   -0.214683
08OC80_-0589        5           0   -0.442644
08OC80_-0589        8  -0.0257643   -0.640673
08OC80_-0589       12           0    -2.95439
08OC80_-1089        5    -7.52125   -0.210895
08OC80_-1089        8    -2.04947    -6.59813
08OC80_-1089       12  -0.0778479   -0.449914
08OC80_00160        5           0  -0.0047247
08OC80_00160        8  -0.0838357           0
08OC80_00160       12           0  -0.0922448
08OC80_00660        5   -0.159948           0
08OC80_00660        8  -0.0767983    -1.05859
08OC80_00660       12           0   -0.853022
08OC91_-0438        5           0   -0.016785
08OC91_-0438        8  -0.0111647           0
08OC91_-0438       12   -0.080739           0
08OC91_-0938        5    -1.24684   -0.894296
08OC91_-0938        8   -0.958221   -0.678399
08OC91_-0938       12   -0.107497   -0.832374
08OC91_-1688        5  -0.0159666   -0.226649
08OC91_-1688        8   -0.145894  -0.0786619
08OC91_-1688       12   -0.113247           0
08OC91_00061        5   -0.190883           0
08OC91_00061        8 -0.00765931   -0.126163
08OC91_00061       12    -7.84577    -7.03645
08OC91_01311        5           0    -4.35772
08OC91_01311        8  -0.0807181           0
08OC91_01311       12  -0.0992663    -1.28934
08OC92_-0141        5  -0.0809062           0
08OC92_-0141        8           0   -0.371087
08OC92_-0141       12    -5.06482           0
08OC92_-0891        5   -0.226139           0
08OC92_-0891        8  -0.0937758           0
08OC92_-0891       12  -0.0159942           0
08OC92_00608        5  -0.0969174           0
08OC92_00608        8    -2.24795   -0.386748
08OC92_00608       12   -0.142757  -0.0803887
08OC94_-0954        5   -0.411978   -0.384259
08OC94_-0954        8     -0.3181   -0.363642
08OC94_-0954       12   -0.231433  -0.0187208
08OC95_-0821        5    -0.26848  -0.0226694
08OC95_-0821        8   -0.324217           0
08OC95_-0821       12   -0.119601    -1.23363
08OC95_-1321        5   -0.233954           0
08OC95_-1321        8  -0.0790932   -0.379818
08OC95_-1321       12           0    -3.00311
08OC95_-2071        5  -0.0553657           0
08OC95_-2071        8  -0.0896851           0
08OC95_-2071       12  -0.0865503   -0.025956
08OC95_00428        5   -0.372996   -0.114414
08OC95_00428        8           0    -2.09826
08OC95_00428       12   -0.063752   -0.750994
08OC95_00928        5    -20.6972  -0.0691158
08OC95_00928        8     -19.034  -0.0142046
08OC95_00928       12    -17.1691    -25.3953
08OC95_01428        5           0    -2.30684
08OC95_01428        8     -0.3227    -1.67785
08OC95_01428       12  -0.0237825    -4.43103
08OC96_-1426        5   -0.912827    -1.21755
08OC96_-1426        8    -7.87627    -1.11312
08OC96_-1426       12    -11.4136    -11.4669
08OC96_00073        5    -0.10353           0
08OC96_00073        8           0           0
08OC96_00073       12   -0.464108     -2.5864
08OC97_-0577        5  -0.0496063           0
08OC97_-0577        8           0           0
08OC97_-0577       12           0           0
08OC97_-1077        5           0   -0.215846
08OC97_-1077        8    -2.40527   -0.138619
08OC97_-1077       12    -2.56912    -1.88501
08OC97_-1827        5   -0.344596   -0.109815
08OC97_-1827        8           0   -0.119148
08OC97_-1827       12           0   -0.254986
08OC97_00422        5           0           0
08OC97_00422        8 -0.00963418  -0.0539154
08OC97_00422       12  -0.0574823   -0.146946
08OC97_01172        5           0   -0.165044
08OC97_01172        8           0    -2.20315
08OC97_01172       12  -0.0294409 -0.00930418
08OC97_01672        5           0           0
08OC97_01672        8     -1.6644   -0.452412
08OC97_01672       12    -12.8611    -1.13483
08OC98_-0351        5           0           0
08OC98_-0351        8           0           0
08OC98_-0351       12  -0.0250218           0
08OC98_-1601        5   -0.186897           0
08OC98_-1601        8    -0.02778 -0.00428201
08OC98_-1601       12    -3.82544           0
08OC98_00148        5           0           0
08OC98_00148        8  -0.0182503     -4.3885
08OC98_00148       12     -12.161   -0.231222
08OC98_00648        5           0   -0.120476
08OC98_00648        8  -0.0342455   -0.116237
08OC98_00648       12 -0.00465667           0
08OC98_01398        5           0   -0.211596
08OC98_01398        8   -0.230203    -0.32363
08OC98_01398       12   -0.127107   -0.294388
08OC99_-0016        5     -0.1422   -0.212629
08OC99_-0016        8    -1.60939  -0.0274879
08OC99_-0016       12   -0.189512   -0.754229
08OC99_-1016        5   -0.517013   -0.109972
08OC99_-1016        8    -7.66425           0
08OC99_-1016       12    -5.29211           0
08OC99_-1516        5           0  -0.0209763
08OC99_-1516        8   -0.117272           0
08OC99_-1516       12           0 -0.00294631
08OC99_00483        5   -0.240501    -2.11204
08OC99_00483        8           0    -5.11371
08OC99_00483       12    -3.42195    -3.66402
08OC99_01733        5   -0.995793    -7.71282
08OC99_01733        8    -1.11194    -12.1452
08OC99_01733       12           0    -13.7566
08PD00_-1730        5   -0.220889           0
08PD00_-1730        8           0           0
08PD00_-1730       12   -0.338158   -0.104137

D: per-patch asymmetry |Cij-Cji|/(Cij+Cji)
        kind  debris    median       p90
08OB86_-0205   False 0.0343668 0.0650313
08OB86_-0205    True 0.0354261 0.0641506
08OB86_00294   False 0.0312222 0.0708724
08OB86_00294    True 0.0344539 0.0675101
08OB87_-0706   False 0.0347523 0.0726964
08OB87_-0706    True 0.0219609 0.0685377
08OB88_-0167   False 0.0337545 0.0863799
08OB88_-0167    True  0.034546 0.0796574
08OB88_-1417   False 0.0327085 0.0808201
08OB88_-1417    True 0.0230603  0.076191
08OB88_00332   False 0.0367936 0.0940469
08OB88_00332    True 0.0372575 0.0765598
08OB88_01832   False 0.0236358 0.0642716
08OB88_01832    True 0.0172536 0.0460112
08OB89_-0347   False 0.0187474 0.0621583
08OB89_-0347    True 0.0211322 0.0562838
08OB89_-0847   False 0.0371688 0.0627933
08OB89_-0847    True 0.0236333 0.0528241
08OB89_00152   False 0.0186775   0.04343
08OB89_00152    True 0.0139035  0.047949
08OC80_-0589   False 0.0229207 0.0533963
08OC80_-0589    True 0.0267898   0.05115
08OC80_-1089   False 0.0224568   0.05298
08OC80_-1089    True  0.021228 0.0533143
08OC80_00160   False 0.0407524  0.074204
08OC80_00160    True 0.0311581 0.0546948
08OC80_00660   False  0.018608 0.0601641
08OC80_00660    True 0.0306514 0.0662243
08OC91_-0438   False 0.0473642 0.0872582
08OC91_-0438    True 0.0450422 0.0808931
08OC91_-0938   False 0.0509691  0.079874
08OC91_-0938    True 0.0281417 0.0659365
08OC91_-1688   False 0.0361861 0.0664662
08OC91_-1688    True 0.0324342   0.06404
08OC91_00061   False 0.0431922 0.0783186
08OC91_00061    True 0.0410732 0.0760073
08OC91_01311   False  0.039513  0.076542
08OC91_01311    True 0.0383372 0.0716338
08OC92_-0141   False 0.0610392 0.0961258
08OC92_-0141    True 0.0334269 0.0748264
08OC92_-0891   False 0.0506216 0.0861093
08OC92_-0891    True 0.0469647 0.0827828
08OC92_00608   False 0.0339523  0.081419
08OC92_00608    True 0.0356976 0.0731959
08OC94_-0954   False 0.0264555 0.0617445
08OC94_-0954    True 0.0148172 0.0638718
08OC95_-0821   False 0.0258798 0.0594019
08OC95_-0821    True 0.0194555 0.0465627
08OC95_-1321   False 0.0202818 0.0625951
08OC95_-1321    True  0.035039 0.0597011
08OC95_-2071   False 0.0150478 0.0394569
08OC95_-2071    True 0.0186394 0.0486587
08OC95_00428   False 0.0482897 0.0836301
08OC95_00428    True 0.0245072 0.0527774
08OC95_00928   False 0.0556076 0.0854855
08OC95_00928    True 0.0611161 0.0862715
08OC95_01428   False 0.0395029 0.0825506
08OC95_01428    True 0.0240577 0.0726971
08OC96_-1426   False 0.0170074 0.0483795
08OC96_-1426    True 0.0214447 0.0434088
08OC96_00073   False 0.0502131 0.0691307
08OC96_00073    True 0.0462178 0.0749643
08OC97_-0577   False 0.0345203 0.0618718
08OC97_-0577    True 0.0285643 0.0690281
08OC97_-1077   False 0.0318736 0.0763677
08OC97_-1077    True 0.0411406 0.0671521
08OC97_-1827   False 0.0469273 0.0806143
08OC97_-1827    True  0.036794 0.0800873
08OC97_00422   False 0.0431617 0.0869485
08OC97_00422    True 0.0442321 0.0723102
08OC97_01172   False 0.0575793 0.0862326
08OC97_01172    True 0.0582969  0.101028
08OC97_01672   False 0.0632191  0.088851
08OC97_01672    True 0.0568114  0.097321
08OC98_-0351   False  0.042611 0.0920522
08OC98_-0351    True 0.0509755 0.0883549
08OC98_-1601   False 0.0387126 0.0743317
08OC98_-1601    True 0.0438875 0.0643766
08OC98_00148   False 0.0450579 0.0750795
08OC98_00148    True 0.0442952 0.0702029
08OC98_00648   False 0.0294668   0.05723
08OC98_00648    True 0.0194392  0.046881
08OC98_01398   False 0.0300604 0.0741833
08OC98_01398    True 0.0475317 0.0754094
08OC99_-0016   False  0.067154  0.111946
08OC99_-0016    True 0.0531166  0.107796
08OC99_-1016   False 0.0555195  0.118249
08OC99_-1016    True 0.0366491 0.0898913
08OC99_-1516   False 0.0269269 0.0711471
08OC99_-1516    True 0.0342643 0.0728977
08OC99_00483   False 0.0613826  0.102154
08OC99_00483    True 0.0509267  0.108268
08OC99_01733   False 0.0578439 0.0868604
08OC99_01733    True  0.056005 0.0754461
08PD00_-1730   False 0.0350373  0.109729
08PD00_-1730    True 0.0571708 0.0924799

D: terrain dir relative to euclid ordering [%]
 debris  n_goals  dir_vs_euclid_pct_median
  False        5                  -0.08897
  False        8                -0.0799056
  False       12                 -0.116424
   True        5                -0.0894655
   True        8                 -0.122656
   True       12                 -0.262398

D: changed orders [%]
 debris  n_goals  euclid_vs_dir_pct  sym_vs_dir_pct
  False        5               62.5           31.25
  False        8            72.9167         54.1667
  False       12            79.1667         41.6667
   True        5               62.5         41.6667
   True        8            66.6667         47.9167
   True       12            77.0833         39.5833

D: pair-matrix asymmetry; zero-kappa audit included
 debris  pairs    median       p90  zero_kappa_median  zero_kappa_p90
  False   3744 0.0359418 0.0820331        0.000838627      0.00315918
   True   3744 0.0333634 0.0756041         0.00116059      0.00343594

D: paired two-sided Wilcoxon; Holm over all twelve comparisons
 debris  n_goals                 comparison  n           p  r  median_cost_difference      p_holm
  False        5      euclid vs terrain dir 48 1.86265e-09  1                 1.26468 1.49012e-08
  False        5 terrain sym vs terrain dir 48 6.10352e-05  1                       0 6.10352e-05
  False        8      euclid vs terrain dir 48 5.82077e-11  1                 1.53458 5.82077e-10
  False        8 terrain sym vs terrain dir 48 2.98023e-08  1                0.169026 1.78814e-07
  False       12      euclid vs terrain dir 48 7.27596e-12  1                  2.3494 8.73115e-11
  False       12 terrain sym vs terrain dir 48 1.90735e-06  1                       0 7.62939e-06
   True        5      euclid vs terrain dir 48 1.86265e-09  1                 1.35829 1.49012e-08
   True        5 terrain sym vs terrain dir 48 1.90735e-06  1                       0 7.62939e-06
   True        8      euclid vs terrain dir 48 4.65661e-10  1                 2.46327 4.19095e-09
   True        8 terrain sym vs terrain dir 48 2.38419e-07  1                       0 1.19209e-06
   True       12      euclid vs terrain dir 48 1.45519e-11  1                 5.96524 1.60071e-10
   True       12 terrain sym vs terrain dir 48  3.8147e-06  1                       0 7.62939e-06

D: matrix / Held-Karp time [s]; full 13-point matrices reused by all prefixes
 debris  n_goals      method  matrix_median  matrix_max  solve_median   solve_max
  False        5      euclid    0.000255811 0.000687325    0.00053986  0.00118491
  False        5 terrain dir          27.72     57.9628    0.00034759 0.000467659
  False        5 terrain sym         25.638     45.2346   0.000351748 0.000432968
  False        8      euclid    0.000255811 0.000687325    0.00673629   0.0310173
  False        8 terrain dir          27.72     57.9628    0.00596283   0.0235724
  False        8 terrain sym         25.638     45.2346    0.00603383   0.0069798
  False       12      euclid    0.000255811 0.000687325      0.283159    0.580572
  False       12 terrain dir          27.72     57.9628      0.262613    0.812371
  False       12 terrain sym         25.638     45.2346      0.274812    0.644008
   True        5      euclid    0.000266986 0.000668354   0.000622199  0.00368963
   True        5 terrain dir        28.2057     52.2485   0.000346303 0.000412879
   True        5 terrain sym         26.851     47.1395   0.000356088  0.00062675
   True        8      euclid    0.000266986 0.000668354    0.00700741   0.0258405
   True        8 terrain dir        28.2057     52.2485    0.00582669  0.00847733
   True        8 terrain sym         26.851     47.1395    0.00597355   0.0214785
   True       12      euclid    0.000266986 0.000668354      0.281009    0.659489
   True       12 terrain dir        28.2057     52.2485      0.267415    0.835646
   True       12 terrain sym         26.851     47.1395      0.261587    0.792092

D: failures
Empty DataFrame
Columns: [kind, side_m, seed, debris, n_goals, method, reason]
Index: []

Comparison B: artificial 007, matching 100/200m beach families
                          debris     planner  success  exposed  steep_len     cost   climb  energy_vs_A_pct  max_roll  p95_roll  roll_frac  length      time  touching
artificial 007 (includes debris)          A*        1      0.1          0 0.176599 2.89105                0   8.81679    5.4834          0 120.414 0.0776359         0
artificial 007 (includes debris)       A*-HC        1        0          0 0.176599 2.83132                0   8.71321   5.52829          0 124.751 0.0817081         0
artificial 007 (includes debris)         TA*        1        0          0 0.120661 1.99114         -1.41143   5.28948    3.3163          0 126.792  0.323069         0
artificial 007 (includes debris)       TA*-S        1        0          0 0.132132 1.87914         -6.10245    6.3271   3.87571          0  121.44  0.465019         0
artificial 007 (includes debris) TA*-S exact        1        0          0 0.132132 1.87914         -6.10245    6.3271   3.87571          0  121.44  0.500044         0

Comparison C: artificial 007, 100m beach families
                                debris             variant  success  exposed      dJ         dL        dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax    dL90   dLmax
artificial 007 (100m, includes debris)      coarse R10 c10        1        0 6.59482   -1.01021 -0.114314 -6.59716  5.52081     71    3.20132         0 8.26758  28.363 2.17856 17.3831
artificial 007 (100m, includes debris)       coarse R15 c5        1        0 2.80683  -0.673633  -0.25699 -6.51151  5.56835     65    3.41026         0 6.24849 14.4205 1.61568 4.86538
artificial 007 (100m, includes debris)       coarse R5 c10        1        0 7.78997    -1.8513 -0.194124 -6.46896   5.9917   73.5    2.79991         0 13.3689 45.8038 1.43751 27.3179
artificial 007 (100m, includes debris)       coarse R5 c20        1        0  10.264 -0.0591482   1.46637   -4.252  6.18201   75.5    3.23859         0 17.2041 47.3065  6.2985 29.9331
artificial 007 (100m, includes debris) online adaptive R15        1        0 6.14845   -1.70182 -0.169576 -6.20524  6.20043   18.5    1.44294         0 9.95202 19.1195 1.03518 9.04657
artificial 007 (100m, includes debris)           oracle A*        1 0.133333 18.1426    2.65982   6.49906        0  6.52691      1  0.0548636         4 25.4288 35.5313 4.97741  6.2874
artificial 007 (100m, includes debris)        oracle TA*-S        1        0       0          0         0 -6.10245  5.15441      1   0.277212         0       0       0       0       0

Comparison C: real 100m subset (200m is additional)
 debris             variant  success  exposed      dJ        dL        dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax     dL90   dLmax
  False      coarse R10 c10        1        0 2.33867 -0.650228 -0.743211 -5.73151  4.64217   25.5    1.65389         0 10.4655 23.3936  0.25672 3.87259
  False       coarse R15 c5        1        0 1.10097 -0.471314 -0.326324 -4.82173  4.62793   23.5    1.49326         0 2.79437 39.0617 0.441549 4.91321
  False       coarse R5 c10        1        0 3.20686 -0.902119 -0.624293 -6.07568  4.90122   30.5    1.68591         0 17.1685 33.1578 0.531586 6.19819
  False       coarse R5 c20        1        0 6.57569 -0.704766 -0.442347 -5.59682  5.61109   39.5     2.2983         0 27.8974 48.6312  2.26402 9.50044
  False online adaptive R15        1        0 2.60966 -0.885181 -0.880487 -5.96458  4.77307     11   0.764934         0 10.6517 23.0402 0.110011 1.18498
  False           oracle A*        1        0 13.0448   1.45439   3.36279        0  5.57371      1   0.022025         0 30.0299 56.3921  7.55416 8.14806
  False        oracle TA*-S        1        0       0         0         0 -3.25337  4.58853      1   0.138765         0       0       0        0       0
   True      coarse R10 c10        1        0 3.54132  -1.02132 -0.475815 -5.19217  5.01105     47    2.55506         0 9.59366 23.3052  1.98352 5.30502
   True       coarse R15 c5        1        0 1.50883   -0.2232 -0.178807 -4.54618  4.83866   43.5    2.40612         0 5.41622 32.2488  1.50175 6.83958
   True       coarse R5 c10        1        0 6.47122  -1.02133 -0.890056 -4.72772  5.26488   51.5    2.73806         0 14.8776 32.0776  1.47826 8.02423
   True       coarse R5 c20        1        0 9.23335  -1.18832 -0.601576 -5.25336  5.84945     56    2.90579         0 25.2374  45.868  2.20624 10.0261
   True online adaptive R15        1        0 4.46457 -0.648581  -0.45828 -5.80931  5.24389   17.5    1.30509         0 9.27661 12.5512 0.886554 4.82495
   True           oracle A*        1        0 18.2664  0.974355   4.22853        0  6.15992      1  0.0147658         0 31.7125 62.7128  5.64681 8.05843
   True        oracle TA*-S        1        0       0         0         0 -4.05697  4.94088      1   0.109905         0       0       0        0       0

C: real 200m subset (additional experiment)
 debris             variant  success  exposed      dJ        dL        dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax      dL90   dLmax
  False      coarse R10 c10        1        0  5.5816 -0.493395  -0.18785 -5.24812  5.80879     67    12.4604         0 22.0292 112.149   3.12786 83.7075
  False       coarse R15 c5        1        0 1.86753 -0.333082 -0.123552 -5.13604  5.03679   59.5    10.1201         0 7.98001 91.1908   2.09046 72.3785
  False       coarse R5 c10        1        0 6.83863 -0.745656 -0.159265 -4.98362  5.89193     74    12.7471         0 23.9862 132.758   3.48373 58.5615
  False       coarse R5 c20        1        0 10.8738  -1.60395 -0.537345 -5.98741  6.60239     75    12.3822         0 35.4153 143.099   6.47393 63.7171
  False online adaptive R15        1        0 10.0409  -2.20085  -1.49435 -6.38122  5.90806   28.5    8.21858         0 27.1219 108.128 0.0612574  48.466
  False           oracle A*        1   0.1875 20.6732   2.36186   4.82566        0  6.96099      1  0.0767779        10 50.8304 183.095   5.15897 6.99683
  False        oracle TA*-S        1        0       0         0         0  -4.6035  4.75418      1   0.397828         0       0       0         0       0
   True      coarse R10 c10        1        0 6.02537  -1.06614 -0.343401 -4.80186  5.99055  107.5    16.7259         0   14.48  111.26   3.82195 83.6078
   True       coarse R15 c5        1        0 2.69906 -0.195811 -0.035096 -4.46303  5.13211    101    14.3606         0 8.81879 59.1419   1.97359 54.6364
   True       coarse R5 c10        1        0 9.80982  -1.73875 -0.124867 -5.28118  6.41835    114    17.3714         0 22.4937 162.311   1.74456 57.4176
   True       coarse R5 c20        1        0 13.4248  -2.19832  -0.50114 -5.89125  7.21461    117    22.1296         0 31.8586 138.201   4.53412 57.2726
   True online adaptive R15        1        0 12.8585  -2.63441  -1.37986 -6.09839  6.38876   41.5    9.88676         0 23.9835 100.021  0.118861 72.1412
   True           oracle A*        1   0.1875 26.7837  0.188134   5.02457        0  8.81505      1  0.0965014        10 56.7788 171.187   3.33578 6.69711
   True        oracle TA*-S        1        0       0         0         0 -4.78417  5.02634      1   0.497137         0       0       0         0       0

Comparison D: artificial 008, 200m beach families
                                debris  n_goals      method  success  cost_rel_pct_median  cost_rel_pct_p90  energy_rel_pct_median  energy_rel_pct_p90  length_xy_median  length_xy_p90  climb_median  climb_p90  p95_roll_median  p95_roll_p90  steep_len_median  steep_len_p90
artificial 008 (200m, includes debris)        5      euclid        1                    0          0.278084                      0           0.0652999           424.972        474.166       7.16238    8.63987          3.88995       5.56747                 0              0
artificial 008 (200m, includes debris)        5 terrain dir        1                    0                 0                      0                   0           424.972        474.543       7.16238    8.63987          3.84865       5.58356                 0              0
artificial 008 (200m, includes debris)        5 terrain sym        1                    0            0.1501                      0         0.000230621           424.897        474.543       7.12379    8.63987          3.85347       5.55633                 0              0
artificial 008 (200m, includes debris)        8      euclid        1            0.0425286          0.300553                      0           0.0094831           499.596        556.874       8.67536    10.1908          3.96417       5.07567                 0              0
artificial 008 (200m, includes debris)        8 terrain dir        1                    0                 0                      0                   0           500.114        558.219        8.5957    10.1679          3.95711       5.12568                 0              0
artificial 008 (200m, includes debris)        8 terrain sym        1           0.00224052          0.200804                      0          0.00630378           498.621        558.219        8.6327    10.1495          3.96212       5.14413                 0              0
artificial 008 (200m, includes debris)       12      euclid        1           0.00862348          0.190124                      0            0.151463           565.078        623.445       10.0622    11.7721          4.10191         5.112                 0              0
artificial 008 (200m, includes debris)       12 terrain dir        1                    0                 0                      0                   0           567.372        623.401       10.0622    11.7721          4.16156       5.11419                 0              0
artificial 008 (200m, includes debris)       12 terrain sym        1            0.0118841          0.102719                      0             0.14681           567.243        623.445       9.94051    11.7721          4.11041       5.11419                 0              0

Measured phase wall times [s]; includes cache reads only if --resume was requested
  phase  wall_time_s
      A      4.95343
      B      62.3535
      C      1902.29
      D      1077.78
figures      13.8451
Total wall time [s]: 3061.597141; workers=5; resume=False
Source: 静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB 地面の点群（Ground）
https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
ライセンス：CC BY 4.0 / ODbL。このフォルダのデータは、上のデータを加工して作成したものです。
Caveats: nearest-data fill affects spectra; zero-kappa greedy smoothing need not be symmetric; closed-tour endpoint elevation potentials cancel.
```


## 比較スクリプトの全出力（そのまま）

```text
Paired scenario identities; fixed parameters, no calibration. Old=0.1m source grid; new=LAS Ground.
B original009_10: five outcomes x debris, unchanged family. B requested_12: six requested outcomes x debris, separate supplementary family.

A: matched real-patch statistics; new minus old (all 60)
            metric  n  old_median  new_median  paired_delta_median
           slope50 60      4.3875     3.37456            -0.898305
           slope90 60     10.1517     9.46497            -0.369965
           slope99 60     24.0888     24.4173             0.351147
        steep_land 60  0.00875393  0.00934883          0.000234165
foreshore_gradient 60   0.0542857   0.0538368         -0.000486597
      land_width_m 60       102.5       97.75                 -0.5
             rough 60   0.0190807  0.00830043           -0.0107202
          spectrum 60    -2.92709     -2.9264         -0.000889163
       lethal_land 60   0.0166063   0.0192172           0.00103983
   nodata_fraction 60    0.132631    0.130853           0.00211563
    water_fraction 60      0.2444    0.240016          -0.00256562

A: artificial medians outside the real p10..p90 range, before/after
        kind             metric  old_outside  new_outside   change  synthetic_old  synthetic_new     old_p10   old_p90     new_p10   new_p90
beach_gentle            slope90         True         True     both         39.953         39.953     7.25627   18.5342     6.90292   18.9575
beach_gentle            slope99         True         True     both        42.1333        42.1333      12.842   36.2999     13.0184   37.8504
beach_gentle         steep_land         True         True     both       0.138051       0.138051 0.000433524 0.0583909 0.000612472 0.0607766
beach_gentle              rough        False         True new_only      0.0193392      0.0193392   0.0171683 0.0207502  0.00608757 0.0115208
beach_gentle        lethal_land         True         True     both       0.153638       0.153638   0.0077981 0.0691932  0.00862912 0.0714204
 beach_scarp            slope90         True         True     both        40.2853        40.2853     7.25627   18.5342     6.90292   18.9575
 beach_scarp            slope99         True         True     both        42.7474        42.7474      12.842   36.2999     13.0184   37.8504
 beach_scarp         steep_land         True         True     both       0.213943       0.213943 0.000433524 0.0583909 0.000612472 0.0607766
 beach_scarp       land_width_m         True         True     both             16             16       71.95    148.55      66.625    147.65
 beach_scarp              rough        False         True new_only      0.0191346      0.0191346   0.0171683 0.0207502  0.00608757 0.0115208
 beach_scarp        lethal_land         True         True     both       0.229267       0.229267   0.0077981 0.0691932  0.00862912 0.0714204
 beach_steep            slope90         True         True     both        40.0925        40.0925     7.25627   18.5342     6.90292   18.9575
 beach_steep            slope99         True         True     both        42.2108        42.2108      12.842   36.2999     13.0184   37.8504
 beach_steep         steep_land         True         True     both       0.161693       0.161693 0.000433524 0.0583909 0.000612472 0.0607766
 beach_steep foreshore_gradient         True         True     both    0.000726161    0.000726161   0.0266336 0.0904585     0.03898 0.0755233
 beach_steep       land_width_m         True         True     both             29             29       71.95    148.55      66.625    147.65
 beach_steep              rough        False         True new_only      0.0202472      0.0202472   0.0171683 0.0207502  0.00608757 0.0115208
 beach_steep        lethal_land         True         True     both        0.17253        0.17253   0.0077981 0.0691932  0.00862912 0.0714204

A: unchanged artificial generator audit (maximum absolute old/new difference)
            metric  max_abs_difference
           slope50                   0
           slope90                   0
           slope99                   0
        steep_land                   0
foreshore_gradient                   0
      land_width_m                   0
             rough                   0
          spectrum         6.66134e-15
       lethal_land                   0

B: nominal identity pairing audit; endpoints can change with terrain masks
 debris  rows  same_seed_stream  same_crop  old_success  new_success
  False   480               475        480          480          480
   True   480               475        480          480          480

B: original009_10; paired two-sided Wilcoxon, Holm within each dataset/family
        family  debris          metric  n_old center    A_old  exact_old  delta_median_old       p_old     r_old  p_holm_old  significant_old direction_old  n_new    A_new  exact_new  delta_median_new       p_new     r_new  p_holm_new  significant_new direction_new  significance_changed  direction_changed
original009_10   False           climb     96 median  1.72385   0.584851         -0.894315 2.85324e-17 -0.993557 2.28259e-16             True         lower     96   1.4402   0.959826         -0.286006 2.12358e-16 -0.965636  1.4865e-15             True         lower                 False              False
original009_10   False energy_vs_A_pct     96 median        0   -2.03554          -2.03554 4.67536e-06  -0.53823 1.40261e-05             True         lower     96        0   -4.06554          -4.06554 3.50869e-10 -0.737543 2.10521e-09             True         lower                 False              False
original009_10   False       length_xy     96 median  120.556    121.927           2.38802 7.18613e-08  0.633162 3.59306e-07             True        higher     96  120.556    120.845          -2.53101 0.000351682 -0.420103  0.00140673             True         lower                 False               True
original009_10   False       mean_cost     96 median 0.164558  0.0717415        -0.0873069 1.78129e-17        -1 1.78129e-16             True         lower     96 0.114426   0.077346        -0.0280918  4.0231e-17 -0.988832 3.62079e-16             True         lower                 False              False
original009_10   False       steep_len     96 median        0          0                 0  0.00390625        -1   0.0078125             True         lower     96        0          0                 0  0.00390625        -1   0.0117188             True         lower                 False              False
original009_10    True           climb     96 median  2.45084   0.882012          -1.18527 3.66381e-17  -0.99012 2.56467e-16             True         lower     96  2.22844    1.25993          -0.55376 4.70068e-17 -0.986684 3.76055e-16             True         lower                 False              False
original009_10    True energy_vs_A_pct     96 median        0   -2.49006          -2.49006 9.74215e-07 -0.575601 3.89686e-06             True         lower     96        0   -4.49297          -4.49297 1.22361e-09 -0.714347 6.11805e-09             True         lower                 False              False
original009_10    True       length_xy     96 median  121.754    126.546           3.82323 1.04136e-10   0.75945 6.24817e-10             True        higher     96  120.746    121.498         -0.657586    0.301057 -0.121564    0.301057            False         lower                  True               True
original009_10    True       mean_cost     96 median 0.182026  0.0888778        -0.0911477 1.78129e-17        -1 1.78129e-16             True         lower     96 0.144652  0.0887103        -0.0450661 1.78129e-17        -1 1.78129e-16             True         lower                 False              False
original009_10    True       steep_len     96 median        0          0                 0  0.00390625        -1   0.0078125             True         lower     96        0          0                 0  0.00390625        -1   0.0117188             True         lower                 False              False

B: requested_12; paired two-sided Wilcoxon, Holm within each dataset/family
      family  debris            metric  n_old       center    A_old  exact_old  delta_median_old       p_old     r_old  p_holm_old  significant_old direction_old  n_new    A_new  exact_new  delta_median_new       p_new     r_new  p_holm_new  significant_new direction_new  significance_changed  direction_changed
requested_12   False             climb     96       median  1.72385   0.584851         -0.894315 2.85324e-17 -0.993557 2.28259e-16             True         lower     96   1.4402   0.959826         -0.286006 2.12358e-16 -0.965636 1.59844e-15             True         lower                 False              False
requested_12   False   energy_vs_A_pct     96       median        0   -2.03554          -2.03554 4.67536e-06  -0.53823 1.40261e-05             True         lower     96        0   -4.06554          -4.06554 3.50869e-10 -0.737543 2.10521e-09             True         lower                 False              False
requested_12   False         length_xy     96       median  120.556    121.927           2.38802 7.18613e-08  0.633162 3.59306e-07             True        higher     96  120.556    120.845          -2.53101 0.000351682 -0.420103  0.00140673             True         lower                 False               True
requested_12   False         mean_cost     96       median 0.164558  0.0717415        -0.0873069 1.78129e-17        -1 2.13755e-16             True         lower     96 0.114426   0.077346        -0.0280918  4.0231e-17 -0.988832  4.0231e-16             True         lower                 False              False
requested_12   False          p95_roll     96       median  5.72724    3.22593          -3.09506  1.8383e-17  -0.99957 2.13755e-16             True         lower     96  5.57075    3.52955          -1.85643 1.99805e-16 -0.966495 1.59844e-15             True         lower                 False              False
requested_12   False steep_exposed_pct     96 mean_percent    9.375          0                 0  0.00390625        -1   0.0078125             True         lower     96    9.375          0                 0  0.00390625        -1   0.0117188             True         lower                 False              False
requested_12    True             climb     96       median  2.45084   0.882012          -1.18527 3.66381e-17  -0.99012 2.56467e-16             True         lower     96  2.22844    1.25993          -0.55376 4.70068e-17 -0.986684 4.23062e-16             True         lower                 False              False
requested_12    True   energy_vs_A_pct     96       median        0   -2.49006          -2.49006 9.74215e-07 -0.575601 3.89686e-06             True         lower     96        0   -4.49297          -4.49297 1.22361e-09 -0.714347 6.11805e-09             True         lower                 False              False
requested_12    True         length_xy     96       median  121.754    126.546           3.82323 1.04136e-10   0.75945 6.24817e-10             True        higher     96  120.746    121.498         -0.657586    0.301057 -0.121564    0.301057            False         lower                  True               True
requested_12    True         mean_cost     96       median 0.182026  0.0888778        -0.0911477 1.78129e-17        -1 2.13755e-16             True         lower     96 0.144652  0.0887103        -0.0450661 1.78129e-17        -1 2.13755e-16             True         lower                 False              False
requested_12    True          p95_roll     96       median  6.61923    3.50932          -3.49593 1.78129e-17        -1 2.13755e-16             True         lower     96   6.1046    3.74967          -2.33866 2.76527e-17 -0.993986  3.0418e-16             True         lower                 False              False
requested_12    True steep_exposed_pct     96 mean_percent    9.375          0                 0  0.00390625        -1   0.0078125             True         lower     96    9.375          0                 0  0.00390625        -1   0.0117188             True         lower                 False              False

B: changed significance or rank direction (non-significant direction is descriptive only)
        family  debris    metric  n_old center   A_old  exact_old  delta_median_old       p_old    r_old  p_holm_old  significant_old direction_old  n_new   A_new  exact_new  delta_median_new       p_new     r_new  p_holm_new  significant_new direction_new  significance_changed  direction_changed
original009_10   False length_xy     96 median 120.556    121.927           2.38802 7.18613e-08 0.633162 3.59306e-07             True        higher     96 120.556    120.845          -2.53101 0.000351682 -0.420103  0.00140673             True         lower                 False               True
original009_10    True length_xy     96 median 121.754    126.546           3.82323 1.04136e-10  0.75945 6.24817e-10             True        higher     96 120.746    121.498         -0.657586    0.301057 -0.121564    0.301057            False         lower                  True               True
  requested_12   False length_xy     96 median 120.556    121.927           2.38802 7.18613e-08 0.633162 3.59306e-07             True        higher     96 120.556    120.845          -2.53101 0.000351682 -0.420103  0.00140673             True         lower                 False               True
  requested_12    True length_xy     96 median 121.754    126.546           3.82323 1.04136e-10  0.75945 6.24817e-10             True        higher     96 120.746    121.498         -0.657586    0.301057 -0.121564    0.301057            False         lower                  True               True

B: reproduce stored task-009 tests from original raw CSV
statistic  max_abs_difference
        p         1.29247e-26
        r         1.11022e-16
   p_holm                   0

C: dJ [%] paired on patch/size/seed/debris/variant; bad tail=p90
 debris  side_m             variant  n  paired_success  old_success  new_success  old_median  old_p90  old_max  new_median  new_p90  new_max  paired_delta_median  old_touching  new_touching  old_contact_audited  new_contact_audited
  False     100      coarse R10 c10 48              48           48           48     3.91996  15.4366  26.1867     2.33867  10.4655  23.3936             -2.60338             0             0                   48                   48
  False     100       coarse R15 c5 48              48           48           48     2.04986  7.47123  25.5176     1.10097  2.79437  39.0617            -0.424609             0             0                   48                   48
  False     100       coarse R5 c10 48              48           48           48     12.0509  25.1726  44.7699     3.20686  17.1685  33.1578             -7.66931             0             0                   48                   48
  False     100       coarse R5 c20 48              48           48           48     16.4809  37.5094  75.4604     6.57569  27.8974  48.6312             -10.1208             0             0                   48                   48
  False     100 online adaptive R15 48              48           48           48     7.02352  18.3052  27.1238     2.60966  10.6517  23.0402             -3.57996             0             0                   48                   48
  False     100           oracle A* 48              48           48           48     30.8223  57.8185  110.071     13.0448  30.0299  56.3921             -15.3535             0             0                   48                   48
  False     100        oracle TA*-S 48              48           48           48           0        0        0           0        0        0                    0             0             0                   48                   48
  False     200      coarse R10 c10 48              48           48           48     8.78857  26.7285  127.847      5.5816  22.0292  112.149             -2.93514             0             0                   48                   48
  False     200       coarse R15 c5 48              48           48           48     2.96248  10.6284   95.859     1.86753  7.98001  91.1908             -1.15528             0             0                   48                   48
  False     200       coarse R5 c10 48              48           48           48     17.9615  35.9297  162.393     6.83863  23.9862  132.758             -9.29542             0             0                   48                   48
  False     200       coarse R5 c20 48              48           48           48     22.9307  41.6149  204.054     10.8738  35.4153  143.099             -8.63556             0             0                   48                   48
  False     200 online adaptive R15 48              48           48           48      21.306  39.9342  130.658     10.0409  27.1219  108.128             -8.65678             0             0                   48                   48
  False     200           oracle A* 48              48           48           48     47.0926  68.9886  122.402     20.6732  50.8304  183.095             -22.6443            10            10                   48                   48
  False     200        oracle TA*-S 48              48           48           48           0        0        0           0        0        0                    0             0             0                   48                   48
   True     100      coarse R10 c10 48              48           48           48     5.30061  12.1468  28.0532     3.54132  9.59366  23.3052             -1.27309             0             0                   48                   48
   True     100       coarse R15 c5 48              48           48           48     2.64441  6.28686   11.915     1.50883  5.41622  32.2488            -0.670589             0             0                   48                   48
   True     100       coarse R5 c10 48              48           48           48     10.4476  24.2442  39.5975     6.47122  14.8776  32.0776             -4.58329             0             0                   48                   48
   True     100       coarse R5 c20 48              48           48           48      14.577   32.343  64.7574     9.23335  25.2374   45.868             -6.71626             0             0                   48                   48
   True     100 online adaptive R15 48              48           48           48     6.73134  13.6125  27.4618     4.46457  9.27661  12.5512             -2.80628             0             0                   48                   48
   True     100           oracle A* 48              48           48           48     30.1613  51.6094  83.1875     18.2664  31.7125  62.7128             -11.0389             0             0                   48                   48
   True     100        oracle TA*-S 48              48           48           48           0        0        0           0        0        0                    0             0             0                   48                   48
   True     200      coarse R10 c10 48              48           48           48     7.11793  20.8115   123.86     6.02537    14.48   111.26            -0.754757             0             0                   48                   48
   True     200       coarse R15 c5 48              48           48           48     3.15777  9.64132  93.9626     2.69906  8.81879  59.1419              -0.4337             0             0                   48                   48
   True     200       coarse R5 c10 48              48           48           48      16.642   31.377  153.397     9.80982  22.4937  162.311             -5.30217             0             0                   48                   48
   True     200       coarse R5 c20 48              48           48           48     20.4687  42.6129  195.458     13.4248  31.8586  138.201             -7.77829             0             0                   48                   48
   True     200 online adaptive R15 48              48           48           48     19.4888  35.4696  127.317     12.8585  23.9835  100.021             -5.50591             0             0                   48                   48
   True     200           oracle A* 48              48           48           48     42.2209  66.8666  116.125     26.7837  56.7788  171.187             -13.7656            11            10                   48                   48
   True     200        oracle TA*-S 48              48           48           48           0        0        0           0        0        0                    0             0             0                   48                   48

C: contact runs, replanning methods only (oracles excluded)
 debris  old_touching  new_touching  old_contact_audited  new_contact_audited  old_success  new_success
  False             0             0                  480                  480          480          480
   True             0             0                  480                  480          480          480

D: nominal scenario pairing audit; sampled waypoints can differ with masks
 debris  n_goals  cases  same_waypoint_sets
  False        5     48                   0
  False        8     48                   0
  False       12     48                   0
   True        5     48                   0
   True        8     48                   0
   True       12     48                   0

D: terrain dir / euclid - 1 [%]; lower is better, bad tail=p90
 debris  n_goals    metric  n  paired_success  old_success  new_success  old_median  old_p90  new_median  new_p90  paired_delta_median
  False        5  cost_dir 48              48           48           48   -0.049098        0    -0.08897        0                    0
  False        5 energy_kj 48              48           48           48           0 0.943002           0 0.250663          -0.00363583
  False        8  cost_dir 48              48           48           48  -0.0841249        0  -0.0799056        0                    0
  False        8 energy_kj 48              48           48           48           0  1.01797           0 0.283432                    0
  False       12  cost_dir 48              48           48           48    -0.16202        0   -0.116424        0           -0.0358762
  False       12 energy_kj 48              48           48           48           0  1.25049           0  1.05366          -0.00162194
   True        5  cost_dir 48              48           48           48  -0.0682206        0  -0.0894655        0                    0
   True        5 energy_kj 48              48           48           48           0   0.2859           0 0.274946                    0
   True        8  cost_dir 48              48           48           48    -0.13712        0   -0.122656        0            0.0266081
   True        8 energy_kj 48              48           48           48           0 0.180144           0 0.421158            0.0877163
   True       12  cost_dir 48              48           48           48   -0.187688        0   -0.262398        0           0.00274332
   True       12 energy_kj 48              48           48           48           0 0.732722           0 0.322986           -0.0672505

D: task-009 euclid / terrain dir - 1 [%]; euclid excess, bad tail=p90
 debris  n_goals    metric  n  paired_success  old_success  new_success  old_median  old_p90  new_median  new_p90  paired_delta_median
  False        5  cost_dir 48              48           48           48   0.0491222   1.4044   0.0890499 0.946608                    0
  False        5 energy_kj 48              48           48           48           0 0.352756           0  1.15403            0.0036361
  False        8  cost_dir 48              48           48           48   0.0841958  4.05983   0.0799695  3.04383                    0
  False        8 energy_kj 48              48           48           48           0  1.49917           0  2.54293                    0
  False       12  cost_dir 48              48           48           48    0.162283  5.01094     0.11656  9.82485            0.0359641
  False       12 energy_kj 48              48           48           48           0  1.83171           0  6.03872           0.00162189
   True        5  cost_dir 48              48           48           48   0.0682695  1.07617   0.0895497  1.51007                    0
   True        5 energy_kj 48              48           48           48           0 0.846048           0  0.66711                    0
   True        8  cost_dir 48              48           48           48    0.137312  3.11359    0.122807   2.1761           -0.0266633
   True        8 energy_kj 48              48           48           48           0  1.72698           0 0.961838           -0.0877918
   True       12  cost_dir 48              48           48           48    0.188041   5.6979    0.263089  5.51624          -0.00274694
   True       12 energy_kj 48              48           48           48           0  2.52754           0  4.32558            0.0670719

D: original task-009 Holm-corrected tour tests, before/after
 debris  n_goals                 comparison  n_old       p_old  r_old  median_cost_difference_old  p_holm_old  n_new       p_new  r_new  median_cost_difference_new  p_holm_new  significance_changed
  False        5      euclid vs terrain dir     48 1.49012e-08      1                    0.973025 1.04308e-07     48 1.86265e-09      1                     1.26468 1.49012e-08                 False
  False        5 terrain sym vs terrain dir     48 7.62939e-06      1                           0 2.28882e-05     48 6.10352e-05      1                           0 6.10352e-05                 False
  False        8      euclid vs terrain dir     48 9.31323e-10      1                     1.74419  8.3819e-09     48 5.82077e-11      1                     1.53458 5.82077e-10                 False
  False        8 terrain sym vs terrain dir     48 7.62939e-06      1                           0 2.28882e-05     48 2.98023e-08      1                    0.169026 1.78814e-07                 False
  False       12      euclid vs terrain dir     48 1.16415e-10      1                     3.80942 1.28057e-09     48 7.27596e-12      1                      2.3494 8.73115e-11                 False
  False       12 terrain sym vs terrain dir     48  3.8147e-06      1                           0 1.52588e-05     48 1.90735e-06      1                           0 7.62939e-06                 False
   True        5      euclid vs terrain dir     48 9.31323e-10      1                      1.0585  8.3819e-09     48 1.86265e-09      1                     1.35829 1.49012e-08                 False
   True        5 terrain sym vs terrain dir     48 4.76837e-07      1                           0 2.38419e-06     48 1.90735e-06      1                           0 7.62939e-06                 False
   True        8      euclid vs terrain dir     48 4.65661e-10      1                     3.04901 4.65661e-09     48 4.65661e-10      1                     2.46327 4.19095e-09                 False
   True        8 terrain sym vs terrain dir     48 1.19209e-07      1                   0.0156518 7.15256e-07     48 2.38419e-07      1                           0 1.19209e-06                 False
   True       12      euclid vs terrain dir     48 7.27596e-12      1                     4.65225 8.73115e-11     48 1.45519e-11      1                     5.96524 1.60071e-10                 False
   True       12 terrain sym vs terrain dir     48 7.62939e-06      1                           0 2.28882e-05     48  3.8147e-06      1                           0 7.62939e-06                 False

Measured experiment wall times [s]; hardware/load/workers differ, not a speed comparison
dataset   phase  wall_s  workers  resume
    old       A 9.02156        4   False
    old       B 94.6351        4   False
    old       C  2926.5        4   False
    old       D 2075.46        4   False
    old figures 19.9805        4   False
    old   total 5125.93        4   False
    new       A 4.95343        5   False
    new       B 62.3535        5   False
    new       C 1902.29        5   False
    new       D 1077.78        5   False
    new figures 13.8451        5   False
    new   total  3061.6        5   False
Directions use the sign of matched-pairs rank-biserial r; a zero paired median alone is not interpreted as equality.
Nominal scenario pairs share name/size/seed/debris; masks, retry/crop choices and sampled endpoints/waypoints can differ. This is the prescribed rerun, not fixed-coordinate causal isolation.
```


## 制約と未完了事項

- 固定件数・容量の既存テストとの矛盾を解消する変更は未適用。現状のテスト失敗を隠していない。
- Gazeboの走行は指示書の対象外のため実施していない。新worldはPNG/XMLと元標高の復元だけを確認した。
- 高さデータの刷新は実機走行の安全や物理モデルの精度を実証するものではない。
- PR作成・pushの実行結果は `DELIVERY_ja.md` を参照。

## 出典とライセンス

出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB 地面の点群（Ground）
https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb

ライセンス：CC BY 4.0 / ODbL。このフォルダのデータは、上のデータを加工して作成したものです。
元データと加工方法は変更していない `data/shizuoka_beach_las/README_ja.md` を参照。
