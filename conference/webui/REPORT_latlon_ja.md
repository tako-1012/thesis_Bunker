# 指示書018 実装報告

ブランチ: `codex/018-latlon`。最新 `realtime-map` の `b4c92a1` から独立して作成した。マージしない。

## 実装

- `tapp/geo.py`: GRS80・第8系の正逆変換と地図座標変換。NumPyだけを使い、国土地理院の河瀬の式（第三扁平率5次級数）を実装した。
- 出典: https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/algorithm/bl2xy/bl2xy.htm および https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/algorithm/xy2bl/xy2bl.htm 。docstringにも記載した。
- `data_prep/export_maps.py`: `export_geo_sidecars` と `--geo-only` を追加。既存NPZを再保存せず、LAS地図の横に位置情報JSONを作る。既存の通常エクスポートの呼出しは保持した。
- `maps/*.geo.json`: `origin_xy,tangent,normal,zone,resolution,offset_uv_m` と元地図・元パッチのSHA-256。今回の既存LAS地図は13枚。
- `webui/geo_api.py`: 位置情報の読込と追加の座標変換API。地図詳細には対応地図だけ `geo` を追加し、従来のフィールドは維持した。地図と位置情報のハッシュが一致しないと変換を拒否する。
- `webui/static/geo.js` と最小限の既存画面への追記: マウス/タップの緯度経度、地点一覧、JSON・lat,lngテキストの実書出しと読込。元のメートル座標、計画・シミュレーション・ロボット送信は保持した。位置情報のない地図では追加欄を表示しない。
- `tests/test_geo.py`: 原点・独立基準値・往復・半セル/中心のずれ・地図不変・Web APIを確認。
- `webui/check_latlon.py`: 実サーバーとChromiumで画面、実ダウンロード、JSON/テキスト再読込、タッチ、横はみ出し、旧地図の追加欄非表示を確認。外部リクエストとブラウザエラーはなかった。
- `README_latlon_ja.md`: 座標系・ファイル形式・API・再実行方法。

地図の最初のセル中心が(0,0)のため、200mでは(u,v)=(x-99.75,y-49.75)。画像の中心セルと海岸線の原点を混同しない。
JGD2011/JGD2024は指示どおり水平投影の式と定数を共通にした。測地系・観測時期の変位補正やWGS84への変換は行っていない。
第8系以外の換算、実機GPSの校正、Android実機や `map_point` サービスへの送信は未実施。ファイルは地図上の地点を変換した値である。

## 基準値との差（コードで計算）

```text
          X          Y      latitude     longitude      delta_lat_deg      delta_lon_deg
-146639.066 -92848.522 34.6739511947  137.48682701 -4.25145429972e-09  2.46816966865e-09
 -146574.98 -92348.545 34.6745740749 137.492275067 -4.06389943919e-09 -3.64556740351e-09
-146299.598 -89848.337 34.6772788134 137.519524976  2.36028796508e-09 -3.05306002701e-10
    -150000    -100000 34.6429835393 137.409198432  2.78198797332e-10 -4.38916458734e-10
```

指示書の1e-7度以内、原点の1e-9度以内、往復1mm以内を満たした。最大誤差を含むテスト出力全文は下に記載する。新しい経路計画実験はない。

## スクリーンショットと書出し

- [デスクトップの表示とJSON書出し](screenshots/latlon_desktop.png)
- [スマートフォン幅の表示とテキスト読込](screenshots/latlon_phone.png)
- 実際にダウンロードした `latlon_checks/waypoints_latlng.json`, `waypoints_latlng.txt` を再読込して確認した。
- スマートフォン確認はChromiumの390×844タッチ模擬で、Android実機確認ではない。
- TXTは巡回地点だけ、JSONは基地と巡回地点を含める。UIへ戻すメートル値は既存入力と同じ小数3桁。APIは倍精度を保つ。

## 環境と実行コマンド

Python `3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]`、NumPy `2.3.5`、SciPy `1.17.0`。API・全テストは `/tmp/thesis-apt-compat/bin/python`。
画面検査だけはPlaywrightが既存導入されたシステムPythonと `/usr/bin/chromium` を使用し、APIは上記venvのサーバーへ接続した。

```bash
cd conference
python3 -m tests.test_planners  # 変更前
python3 data_prep/export_maps.py --geo-only
python3 -m tests.test_geo
python3 -m webui.server --host 127.0.0.1 --port 8088
python3 -m webui.check_latlon --base-url http://127.0.0.1:8088
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_geo
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
```

## 変更前テストの出力全文
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

$ python3 -m tests.test_geo
/tmp/thesis-apt-compat/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

## ブラウザ検査の出力全文
```text
desktop: geographic cursor, lat/lng list, actual JSON/text downloads and both import round trips passed
phone 390x844: touch coordinate display, lat/lng text file import and no horizontal overflow passed (Chromium emulation)
unreferenced map: geographic tools hidden; no browser errors or external requests
```

## 保全・提出・レビュー依頼

変更した既存ファイルは指示書が許可したエクスポーターとWebの5ファイルだけ。他の既存管理対象ファイル、全NPZ、元データ、実験結果、world、論文、プランナーはSHA-256が一致した。既存テストの変更・弱体化はない。
PR APIが `Forbidden` となるため、作成できない場合もこの報告を作業ブランチに保存してpushする。マージしない。
Claudeには原点/画像中心/半セルの扱い、水平測地系の解釈、Android側が読むファイル形式を確認してほしい。

## 変更・追加ファイル一覧

- `conference/data_prep/export_maps.py`
- `conference/maps/real_las_08OB87_-0206_200m_0.geo.json`
- `conference/maps/real_las_08OB87_-0206_200m_0_debris.geo.json`
- `conference/maps/real_las_08OB88_01332_200m_0.geo.json`
- `conference/maps/real_las_08OB89_-1597_200m_0.geo.json`
- `conference/maps/real_las_08OC90_00270_200m_0.geo.json`
- `conference/maps/real_las_08OC91_00811_200m_0.geo.json`
- `conference/maps/real_las_08OC93_-1519_200m_0.geo.json`
- `conference/maps/real_las_08OC95_-0321_200m_0.geo.json`
- `conference/maps/real_las_08OC96_-0676_200m_0.geo.json`
- `conference/maps/real_las_08OC97_-0077_200m_0.geo.json`
- `conference/maps/real_las_08OC98_-1101_200m_0.geo.json`
- `conference/maps/real_las_08OC98_01898_200m_0.geo.json`
- `conference/maps/real_las_08OC99_00983_200m_0.geo.json`
- `conference/tapp/geo.py`
- `conference/tests/test_geo.py`
- `conference/webui/README_latlon_ja.md`
- `conference/webui/REPORT_latlon_ja.md`
- `conference/webui/check_latlon.py`
- `conference/webui/geo_api.py`
- `conference/webui/latlon_checks/browser_console_log.txt`
- `conference/webui/latlon_checks/browser_log.txt`
- `conference/webui/latlon_checks/export_geo_log.txt`
- `conference/webui/latlon_checks/reference_comparison.csv`
- `conference/webui/latlon_checks/server_log.txt`
- `conference/webui/latlon_checks/verification/all_tests_log.txt`
- `conference/webui/latlon_checks/verification/planners_before_log.txt`
- `conference/webui/latlon_checks/verification/preservation_audit.json`
- `conference/webui/latlon_checks/verification/test_beach_terrain_log.txt`
- `conference/webui/latlon_checks/verification/test_collision_log.txt`
- `conference/webui/latlon_checks/verification/test_dstar_log.txt`
- `conference/webui/latlon_checks/verification/test_geo_log.txt`
- `conference/webui/latlon_checks/verification/test_mapfiles_sim_log.txt`
- `conference/webui/latlon_checks/verification/test_mission_log.txt`
- `conference/webui/latlon_checks/verification/test_natural_terrain_log.txt`
- `conference/webui/latlon_checks/verification/test_online_log.txt`
- `conference/webui/latlon_checks/verification/test_online_mission_log.txt`
- `conference/webui/latlon_checks/verification/test_planners_log.txt`
- `conference/webui/latlon_checks/verification/test_real_beach_las_log.txt`
- `conference/webui/latlon_checks/verification/test_real_beach_log.txt`
- `conference/webui/latlon_checks/verification/test_risk_prior_log.txt`
- `conference/webui/latlon_checks/verification/test_ros2_gz_log.txt`
- `conference/webui/latlon_checks/verification/test_summary.txt`
- `conference/webui/latlon_checks/verification/test_tour_log.txt`
- `conference/webui/latlon_checks/waypoints_latlng.json`
- `conference/webui/latlon_checks/waypoints_latlng.txt`
- `conference/webui/screenshots/latlon_desktop.png`
- `conference/webui/screenshots/latlon_phone.png`
- `conference/webui/server.py`
- `conference/webui/static/app.js`
- `conference/webui/static/geo.js`
- `conference/webui/static/index.html`
- `conference/webui/static/style.css`
