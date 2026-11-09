# 指示書028：選択式の失敗診断と始点・終点の扱い

## 1. 実装・コミット・検証

- 作業ブランチ：`codex/028-endpoint-policy`。`realtime-map` にはマージしていない。
- 土台：`75d400a26aa7fe6d9ee29508af45e4621c7bb100`（作業開始時に取得した `realtime-map`）。
- 実装コミット：`c035820fc58531f0cc5d0f0ddd298f1cf33fa576`。最新位置の反映を補修した最終コードは `e4522fbf9c21d1b3ea10e5e072cb6ba75b88a60b`。検証記録とこの報告は、その後の文書コミットに含める。
- Gazebo、ROSノード、Dockerでの走行は実行していない。今回の結果はPythonによる計画・状態遷移・既存記録の再現である。

### 追加・変更したファイル

| ファイル | 内容 |
|---|---|
| `tapp/endpoint_policy.py` | 固定距離の解除、到達可能な代替終点、失敗分類、圧縮スナップショット、有限の再試行、区間とマスの厳密交差による長さ集計 |
| `ros2_jazzy/gz_checks/endpoint_runtime.py` | 既定では元の `LidarOnlineMission` を返すファクトリ。選択時だけ専用プランナーと非同期実行アダプターを使用 |
| `ros2_jazzy/gz_checks/lidar_checks.py` | `--endpoint-policy none\|escape`、`--diagnostics`、実験条件の記録とROS引数への受け渡し |
| `ros2_jazzy/gz_checks/lidar_planner.py` | 既定なしの追加機能の選択、実測6自由度姿勢の受け渡し |
| `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/online_planner.py` | 停止待ち・全地点判定済みの専用コマンドを経路として解釈しない |
| `ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py` | 停止待ちでは速度ゼロ・軌跡ログ保持。全地点判定後に地点別結果を保存して終了 |
| `experiments/endpoint_replay.py` | 指定された3失敗例の地図の再現。真値は計画後の監査だけで読み込む |
| `experiments/endpoint_audit.py` | 実走行の時刻付き軌跡と、実際に受け渡した解除マスクを対応付けて長さを集計 |
| `tests/test_endpoint_policy.py` | 指定1～6と、代替終点の再計画、遅延した経路の拒否、ROSコールバックの停止、長さ集計の追加検証 |
| `results/endpoint_policy/run_python_tests.py` | 全テストモジュールの実行と出力全文の保存 |
| `results/endpoint_policy/check_default_bytes.py` | 土台コミットと既定の準備出力を直接比較 |
| `results/endpoint_policy/` の残り | 検証ログ、再現の集計、準備だけのmanifest、報告 |

既存の `tapp/online_mission.py`、`lidar_runtime.py`、`fine_protocol()`、保存済みの研究結果、既存テストは変更していない。

### 実装上の決定

- 始点の解除距離は **実測位置からユークリッド距離0.5m**。丸めたマス中心から測らない。
- 終点の代替候補は **元の終点からユークリッド距離1.0m以内**。距離順・座標順で決定的に調べ、A*で到達可能な最初の候補を選ぶ。
- 点群の検出障害物、事前の障害物・水・データなし、更新DEMの生の急斜面をORしたものは解除しない。未観測の事前の生障害物も通行不可のままにする。
- コストは実際の計画用倍率（`1 + w * cost`）。解除したマスには通行可能なマスの最大値を割り当てる。
- 失敗時は速度ゼロを指示し、**シミュレーション時間で1.0秒**待つ。その後、地図を再取得して1回だけ再計画する。地図の版が進まなくても無期限には待たない。なおセンサーが途切れた場合は従来のwatchdogを優先する。
- 再試行でも失敗ならその地点を `unreachable` として次へ進む。到着は `arrived`、代替終点への到着は `nearby` として別記録する。代替終点への経路を再計画しても、この区別を失わない。
- 経路の受け渡し時にも最新の地図と位置で解除範囲を作り直し、経路と連結部分を生障害物を含む通行不可マスクで再検査する。古い地図に基づく経路は無条件では採用しない。
- `--diagnostics` は解除方針と独立して選べる。失敗時には計画に使った地図・コスト・既知/観測マスク・粗細の検出障害物・事前の生障害物・生の急斜面・姿勢・始終点・版・要求時のシミュレーション時刻を保存する。解除方針を選んだ場合は解除前の通行不可マスクも残す。
- 失敗ファイルは `diag/plan_fail_000001.npz` から連番。周期保存は最初の観測からシミュレーション時間10秒ごと、最新3ファイルだけを保持する。真偽値のマスクをpackbitsで保存し、書き込み前に5MB未満を検査する。
- `plans.csv` の `failure_class` 列は診断を選んだ場合だけ追加する。
- `endpoint_status.json` に地点別判定・再試行数・始点と終点の処理回数・解除マス数の累計を保存する。回数は検索時の適用回数であり、異なるマスの総数とは区別する。
- `endpoint_masks/` に検索時と受け渡し時の解除マスクを分けて保存する。`applied=true` は受け渡したものだけ。`endpoint_trajectory.csv` は速度を止めている間も姿勢を記録し、5MB未満のCSV部品に分割する。真値はオンライン処理へ渡さない。

### 実行コマンド

リポジトリ直下で、次を実行した。`--prepare-only` は資料準備だけで、Gazeboを起動しない。

```bash
# 変更前に、conference/ で実行
python3 -m tests.test_planners

# 以降はリポジトリ直下
PYTHONPATH=conference python3 -m tests.test_endpoint_policy
PYTHONPATH=conference python3 conference/results/endpoint_policy/run_python_tests.py
PYTHONPATH=conference python3 conference/results/endpoint_policy/check_default_bytes.py
PYTHONPATH=conference python3 -m experiments.endpoint_replay --output conference/results/endpoint_policy
PYTHONPATH=conference python3 conference/ros2_jazzy/gz_checks/lidar_checks.py \
  --output conference/results/endpoint_policy/prepare_example \
  --patch-count 3 --map fine --endpoint-policy escape --diagnostics --prepare-only
bash -n conference/ros2_jazzy/gz_checks/run_lidar_checks.sh
git diff --check
```

既定のcoarse/fineのmanifestは土台の実装とバイト単位で一致した。実行環境を含む一致のSHA-256は `default_bytes.json` に保存した。既定のランタイムも元のクラスそのものを使用し、時計を固定したテストで経路コマンド全体とCSVのバイト列が一致した。実際の将来のGazebo走行まで、ノイズを含めた軌跡の一致を保証するものではない。

全テストと追加レビューの出力全文は、この報告末尾と `tests/` に保存する。

## 2. 保存済みの失敗の再現

保存された**最後の地図**を使う試験である。失敗瞬間の地図の再現や、新しいGazebo走行の完走を意味しない。
事前地図の生マスクは元のシナリオから再構成し、保存された `prior_rock` と膨張後の一致を検査した。事前DEMは保存された実走行の値を使い、`OnlinePlanner` の soft prior と既知マスクに従って実際の計画用地図を再構成した。

| 保存例 | `none` | `escape` | 解除マス数 | 解除マスのうち真値で通行不可 | 生障害物の解除 |
|---|---|---|---:|---:|---:|
| 研究PC `R1_05 / 08OB87_-0706` | 経路なし・始点型 | 経路なし。再試行後に `unreachable` として次地点へ | 1 | 0 | 0 |
| 研究PC 初回 `08OB87_-0706` | 経路なし・始点型 | 経路なし。再試行後に `unreachable` として次地点へ | 1 | 0 | 0 |
| クラウド `08OB88_-1417` | 経路なし・終点型 | 代替終点 `(198,151)` へ経路あり。元の終点 `(199,151)` から0.5m | 0 | 0 | 0 |

始点の2例は、実測位置から0.5m以内という固定の定義では1マスだけが解除され、経路が開かなかった。範囲を広げる調整はしていない。したがって、これらは「脱出に成功」ではなく「経路失敗1回で全走行を打ち切らず、回れない地点を明示できる」という結果である。動けないまま次の地点も回れない可能性は残る。

再現試験で返された経路に沿った解除範囲内の長さは3例とも0m、真値の通行不可マス内の長さも0mだった。最初の2例は経路が得られていないためであり、実走行で安全に脱出したことの証拠ではない。解除マスと真値の重なり0は、今回の3地図についてだけの結果である。

`replay.json` と `replay_log.txt` に、元の保存場所、分類、代替終点、解除マス数、真値との重なり、経路区間の集計を残した。次地点への移行と有限終了は同じアダプターの合成地図テストで検証した。

## 3. 研究PCで後日評価する案（今回は未実行）

まず別の作業ツリーでこのブランチを取得し、既存の実験が動いていないこと、Dockerとセンサー通信が使えることを確認する。保存先は毎回新しくする。以下は**後日の評価用**であり、今回走らせたコマンドではない。

```bash
# リポジトリ直下・研究PC上で、tmux内から1回ずつ
THESIS_ROS_DOMAIN_ID=175 bash conference/ros2_jazzy/gz_checks/run_lidar_checks.sh \
  "$PWD/conference/results/endpoint_policy/eval_none_01" \
  --patch-count 3 --map fine --endpoint-policy none --diagnostics

THESIS_ROS_DOMAIN_ID=175 bash conference/ros2_jazzy/gz_checks/run_lidar_checks.sh \
  "$PWD/conference/results/endpoint_policy/eval_escape_01" \
  --patch-count 3 --map fine --endpoint-policy escape --diagnostics
```

- **第1段階案：** 先頭3地点を各方針5回ずつ、none→escape→none→escapeと交互に実行する。同時にGazeboを走らせない。
- **第2段階案：** 停止・保存・終了が正しく動くことを確認した後、10地点を各方針3回ずつ実行し、`08OB88_-1417` も含める。これは追加評価なので、研究担当の判断と別の実行依頼が必要。
- どちらも描画方式、目標倍率0.3、途切れ基準1.0秒、センサーの設定とノイズ、既存の障害物判定、元の地点順を揃える。診断の負荷も両条件に同じように掛ける。GPU・1.0倍・実機センサー変更は混ぜない。
- 比較項目：`arrived` / `nearby` / `unreachable` の地点数、全地点が判定されるまでの時間、失敗型、再試行回数、解除回数とマス数、実際に解除領域を通った長さ、そのうち真値で通行不可だった長さ、センサー途切れ・衝突・停止・時間切れ。
- `completed` は「全地点が到着または回れないと判定された」こと。全地点に到着できたという成功率には置き換えず、地点別結果を必ず併記する。
- 新しい条件では旧task023集計を呼ばない。`endpoint_status.json` と新しい監査結果で評価する。
- 実行後、escapeの各 `raw/<patch>/` に対して次の監査を行う。真値を渡すのはこのオフライン集計だけ。

```bash
cd conference
python3 -m experiments.endpoint_audit \
  results/endpoint_policy/eval_escape_01/raw/08OB87_-0706 \
  --truth results/endpoint_policy/eval_escape_01/raw/08OB87_-0706/evaluation_reference.npz
```

## 4. できなかったこと・限界

- Gazebo・Docker・実機での評価は未実施。ROSの実通信、停止までの物理的遅れ、長時間安定性、処理負荷と点群の取りこぼしは未検証。
- 保存済みの地図は走行終了時のもの。失敗瞬間や塞がった順序は復元できない。新しい診断は次の走行から有効になる。
- 始点型の2例は固定の0.5m範囲では脱出できない。この実装だけで経路問題を解消したとは言えない。
- 生の検出障害物はセンサーによる推定であり、真値そのものではない。膨張だけのマスを解除してもロボットの余裕が減るため、真値との照合と物理走行での評価が必要。
- 待機は1秒で打ち切って最新地図を取得するため、版が進まない場合も同じ地図で再試行する。新しいセンサー情報が必ず増えるとは保証しない。
- 通れる範囲が限定的なとき、全地点を `unreachable` と判定して終了する可能性がある。これは走行成功とは別に扱う。
- 再現試験の長さは計画経路上の値。実際に通った長さは、後日のGazebo軌跡と受け渡したマスクから `endpoint_audit.py` で計算する。

## 検証の出力全文

全25テストモジュールが終了コード0。全体実行後に追加した位置反映の補修についても、影響する `tests.test_endpoint_policy` を再実行し、終了コード0を確認した。

### 変更前の必須テスト

```text
all planner tests passed
roll-aware tests passed
```

### 全モジュールの実行結果

```text
tests.test_beach_terrain exit=0
tests.test_collision exit=0
tests.test_dstar exit=0
tests.test_endpoint_policy exit=0
tests.test_footprint exit=0
tests.test_geo exit=0
tests.test_gz_compare exit=0
tests.test_gz_online_batch exit=0
tests.test_mapfiles_sim exit=0
tests.test_mission exit=0
tests.test_natural_terrain exit=0
tests.test_online exit=0
tests.test_online_deadend exit=0
tests.test_online_mission exit=0
tests.test_planners exit=0
tests.test_pointcloud_map exit=0
tests.test_pointcloud_map_fine exit=0
tests.test_real_beach exit=0
tests.test_real_beach_las exit=0
tests.test_real_sensors exit=0
tests.test_risk_prior exit=0
tests.test_ros2_gz exit=0
tests.test_thesis_figures exit=0
tests.test_tour exit=0
tests.test_visibility exit=0
```

### tests.test_beach_terrain（出力全文）

```text
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
```

### tests.test_collision（出力全文）

```text
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
```

### tests.test_dstar（出力全文）

```text
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
```

### tests.test_endpoint_policy（出力全文）

```text
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_cell', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_cell', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).
```

### tests.test_footprint（出力全文）

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

### tests.test_geo（出力全文）

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

### tests.test_gz_compare（出力全文）

```text
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)
```

### tests.test_gz_online_batch（出力全文）

```text
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)
```

### tests.test_mapfiles_sim（出力全文）

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

### tests.test_mission（出力全文）

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

### tests.test_natural_terrain（出力全文）

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

### tests.test_online（出力全文）

```text
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
```

### tests.test_online_deadend（出力全文）

```text
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed
```

### tests.test_online_mission（出力全文）

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

### tests.test_planners（出力全文）

```text
all planner tests passed
roll-aware tests passed
```

### tests.test_pointcloud_map（出力全文）

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

### tests.test_pointcloud_map_fine（出力全文）

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

### tests.test_real_beach（出力全文）

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

### tests.test_real_beach_las（出力全文）

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

### tests.test_real_sensors（出力全文）

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

### tests.test_risk_prior（出力全文）

```text
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
```

### tests.test_ros2_gz（出力全文）

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

### tests.test_thesis_figures（出力全文）

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

### tests.test_tour（出力全文）

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

### tests.test_visibility（出力全文）

```text
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed
```

### 最終コードでの追加テスト再実行（出力全文）

```text
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
```

### 既定の出力比較（出力全文）

```text
{
  "base": "75d400a26aa7fe6d9ee29508af45e4621c7bb100",
  "default_manifest": [
    {
      "map": "coarse",
      "equal": true,
      "bytes": 34416,
      "sha256": "b32d9a39293eb1017f64a4c40d429b6f0676a0a33b8d3b5af1b1508b8fea6561"
    },
    {
      "map": "fine",
      "equal": true,
      "bytes": 35009,
      "sha256": "b533efba56749c4e0f7ae348f042e8797445e54d92d4ec7ec50dcd4b62730dc1"
    }
  ]
}
```

### 保存済み失敗例の集計（出力全文）

```text
[
  {
    "case": "results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706",
    "failure_class": "start_cell",
    "none": "no_path",
    "escape": "unreachable_after_retry_then_next_stop",
    "goal": [
      347,
      145
    ],
    "outcome": "unreachable",
    "relaxed_cells": 1,
    "relaxed_truth_lethal_cells": 0,
    "raw_cells_cleared": 0,
    "relaxed_length_m": 0.0,
    "truth_lethal_length_m": 0.0,
    "cells": []
  },
  {
    "case": "results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706",
    "failure_class": "start_cell",
    "none": "no_path",
    "escape": "unreachable_after_retry_then_next_stop",
    "goal": [
      347,
      145
    ],
    "outcome": "unreachable",
    "relaxed_cells": 1,
    "relaxed_truth_lethal_cells": 0,
    "raw_cells_cleared": 0,
    "relaxed_length_m": 0.0,
    "truth_lethal_length_m": 0.0,
    "cells": []
  },
  {
    "case": "results/lidar_fine/physical_10/raw/08OB88_-1417",
    "failure_class": "goal_cell",
    "none": "no_path",
    "escape": "path",
    "goal": [
      198,
      151
    ],
    "outcome": "nearby",
    "relaxed_cells": 0,
    "relaxed_truth_lethal_cells": 0,
    "raw_cells_cleared": 0,
    "relaxed_length_m": 0.0,
    "truth_lethal_length_m": 0.0,
    "cells": []
  }
]
```

### 資料準備だけの実行（出力全文）

```text
Task028 preparation only; Gazebo not executed: conference/results/endpoint_policy/prepare_example
```
