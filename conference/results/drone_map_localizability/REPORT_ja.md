# 081 段階 B　ドローン地図と砂浜 LAS の位置の決まりやすさ

## 結果

基準は 076 のスケーリング済み情報行列の最小固有値 λmin = 1.0。
割合の分母は情報行列を得た地点。079 と同様、非収束でも情報行列が得られた地点は集計に含め、非収束数は別に示す。
弱い向きは全ての情報あり地点で数えた。X・Y・Z は弱い固有ベクトルの並進成分の主軸で、回転成分が優勢なときは回転に分類する。
広場の X・Y は局所座標の東・北で、CSV の `alongshore`・`cross_shore` は 076 の軸ラベルを引き継いでいる。

### 全地点

| 条件 | 端まで (m) | 情報あり / 地点 | 非収束 | λmin ≦ 1 | λmin 10%点 | λmin 中央値 | 弱い向き X / Y / Z / 回転 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| (a) 広場 10 cm | 全域 | 1450 / 1450 | 0 | 1450 (100.00%) | 0.281 | 0.400 | 709 / 741 / 0 / 0 |
| (b) 広場 0.5 m | 全域 | 1539 / 1539 | 0 | 1539 (100.00%) | 0.282 | 0.397 | 758 / 781 / 0 / 0 |
| (c) LAS 0.5 m | 全域 | 16340 / 16340 | 144 | 14181 (86.79%) | 0.344 | 0.516 | 11187 / 5131 / 22 / 0 |

### 地図端からの距離別

| 条件 | 端まで (m) | 情報あり / 地点 | 非収束 | λmin ≦ 1 | λmin 10%点 | λmin 中央値 | 弱い向き X / Y / Z / 回転 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| (a) 広場 10 cm | 0 ≦ d < 5 | 554 / 554 | 0 | 554 (100.00%) | 0.246 | 0.312 | 273 / 281 / 0 / 0 |
| (a) 広場 10 cm | 5 ≦ d < 10 | 500 / 500 | 0 | 500 (100.00%) | 0.363 | 0.418 | 252 / 248 / 0 / 0 |
| (a) 広場 10 cm | 10 ≦ d | 396 / 396 | 0 | 396 (100.00%) | 0.462 | 0.496 | 184 / 212 / 0 / 0 |
| (b) 広場 0.5 m | 0 ≦ d < 5 | 643 / 643 | 0 | 643 (100.00%) | 0.248 | 0.315 | 303 / 340 / 0 / 0 |
| (b) 広場 0.5 m | 5 ≦ d < 10 | 500 / 500 | 0 | 500 (100.00%) | 0.369 | 0.423 | 266 / 234 / 0 / 0 |
| (b) 広場 0.5 m | 10 ≦ d | 396 / 396 | 0 | 396 (100.00%) | 0.463 | 0.495 | 189 / 207 / 0 / 0 |
| (c) LAS 0.5 m | 0 ≦ d < 5 | 7100 / 7100 | 71 | 6243 (87.93%) | 0.290 | 0.405 | 4025 / 3053 / 22 / 0 |
| (c) LAS 0.5 m | 5 ≦ d < 10 | 5100 / 5100 | 39 | 4358 (85.45%) | 0.443 | 0.513 | 3455 / 1645 / 0 / 0 |
| (c) LAS 0.5 m | 10 ≦ d | 4140 / 4140 | 34 | 3580 (86.47%) | 0.524 | 0.560 | 3707 / 433 / 0 / 0 |

### 同じ座標で比較できる広場の地点と、砂浜別

| 条件 | 端まで (m) | 情報あり / 地点 | 非収束 | λmin ≦ 1 | λmin 10%点 | λmin 中央値 | 弱い向き X / Y / Z / 回転 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| (a) 広場 10 cm | 全域 | 1450 / 1450 | 0 | 1450 (100.00%) | 0.281 | 0.400 | 709 / 741 / 0 / 0 |
| (b) 広場 0.5 m | 全域 | 1450 / 1450 | 0 | 1450 (100.00%) | 0.288 | 0.407 | 737 / 713 / 0 / 0 |

| 条件 | 端まで (m) | 情報あり / 地点 | 非収束 | λmin ≦ 1 | λmin 10%点 | λmin 中央値 | 弱い向き X / Y / Z / 回転 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `08OB88_-1417` | 全域 | 8170 / 8170 | 137 | 6142 (75.18%) | 0.365 | 0.558 | 6031 / 2117 / 22 / 0 |
| `08OB86_-0205` | 全域 | 8170 / 8170 | 7 | 8039 (98.40%) | 0.331 | 0.485 | 5156 / 3014 / 0 / 0 |

![九工大広場の10 cm DSMにおける最小固有値](kyutech_10cm.png)

図の色は λmin。色帯の黒線が基準 1.0、背景の灰色が DSM の欠測。標本点は 1 m 格子。
並進・回転各 3 固有値、弱い固有ベクトルの 6 成分、スキャン点数と重ね合わせの状態は `points_*.csv` に収録した。
砂浜の各窓、各端距離帯、同じ座標の広場比較を含む集計は [summary.csv](summary.csv) にある。

## 読み方と限界

- **同じ広場での解像度の比較 (a)–(b)。** 両方で調べられた 1,450 地点はすべて両条件で 1.0 以下。同じ地点だけでの中央値は (a) 0.400、(b) 0.407、地点ごとの (a)−(b) の差の中央値は −0.0026。今回の平らな広場では、10 cm の細かさで基準を超える地点は増えなかった。比較には参照点群の作り方と欠測域の違いも含まれる。前処理は両方 0.25 m なので、10 cm の地形情報がすべて重ね合わせに残るとは限らない。
- **同じ 0.5 m での場所の比較 (b)–(c)。** 広場の中央値 0.397 に対し、砂浜 10 窓は 0.516。砂浜では 2,159 / 16,340 地点（13.21%）で 1.0 を超え、収束も満たしたのは 2,098 地点だった。基準以下は 1417 が 75.18%、0205 が 98.40%。079 の目印なし（各 68.88%、95.03%）と同じ順だが、079 は広い範囲の通行可能な点を 5 m おきに数えたため、今回の割合との差には切り出し・サンプリング範囲も効く。1417 の窓ごとでも 51.71%〜100% と幅がある。今回の窓の地形や欠測の違いは解像度をそろえても残る。窓が重なる場合があり、16,340 は独立な観測の数ではない。
- **地図の端。** 広場は端から 5 m 未満の中央値が両条件で約 0.31、10 m 以上では約 0.50。端では視野の一部が地図から外れ、広場の欠測も周辺部に多い。表の端距離は長方形の枠までの距離なので、実際の最寄り欠測までの距離にはならない。砂浜でも 0〜5 m の中央値は低かったが、基準以下の割合は端からの距離に対して単調には変わらなかった。
- **現地への外挿。** 076 と同じ閾値を、真の初期位置と同じ地形から作った仮のスキャンに使った。これは真値付近の局所的な観測性。実走行の積み上げ誤差、ずれた初期位置からの収束、DSM で表せない張り出しによる遮蔽、ドローンと LiDAR の時点・計測差、GNSS のない状態での絶対位置は評価していない。10 cm の実ドローン地図は広場 1 枚で、同じ砂浜を撮った地図による比較はできていない。

## 計算方法

- (a) は段階 A の `z_median` を局所 10 cm セルの中心に置き、5 cm 点群の全 649,172 点を重ね合わせに入力した。DSM は 385 × 426 マスで、18,190 マスが欠測。隣接格子は 079 と同じ対角線の三角形で結び、欠測頂点を含む面と外周のセル中心より外に光線を返す面を作らなかった。
- (b) は同一原点の 5 × 5 完全ブロックで有効値の中央値を取った。全欠測ブロックは欠測のまま。北端の余った 10 cm 1 行を外したため、範囲は 38.5 × 42.5 m（77 × 85 マス）。(b) と (c) の参照点群は 075・079 と同じ 0.1 m 間隔で三角面の高さを採った。
- (c) は元の `shizuoka_beach_las` から、全 76 × 86 マスが有限かつ標高 0 m 以上の範囲を列挙した。砂浜ごとに `default_rng(0)` で左下セルを重複なしに 5 個選んだ。窓は重なり得る。漂着物や目印は加えなかった。
- (a)〜(c) の三角面は 079 に合わせて頂点の標高を小数第 4 位までに丸めた。評価点は左下から (0.75 m, 0.75 m) を起点とする 1 m 格子で、欠測位置は除いた。0.75 m は 0.1 m と 0.5 m の両方でセル中心に乗る位相。端までの距離は長方形のセル境界までの最短水平距離で算出した。
- 車体は水平・+X 向き。079 の `REAL_MOUNTS['lidar']` と `LidarSpec`（16 × 1,800 光線、垂直 ±15°、0.9–30 m、距離雑音の標準偏差 0.02 m）を使用した。広場の同一座標、砂浜の重複窓の同一座標では同じ乱数列を使った。
- 076 の GICP は真の LiDAR 姿勢で初期化した。全条件とも既存の `MapRegistration` により 0.25 m ボクセルで前処理し、同じ情報計算と閾値を使った。生の参照点数は [metadata.json](metadata.json) に記録した。

### 砂浜の切り出し座標

元の LAS 200 m 正方形のローカル軸で示す。左下は切り出すセルの外端。

| 砂浜 | 窓 | 左下 X (m) | 左下 Y (m) | 対応 CSV |
| --- | ---: | ---: | ---: | --- |
| `08OB88_-1417` | 1 | 100.0 | 72.0 | [位置と固有値](points_c_08OB88_-1417_1.csv) |
| `08OB88_-1417` | 2 | 80.5 | 81.0 | [位置と固有値](points_c_08OB88_-1417_2.csv) |
| `08OB88_-1417` | 3 | 45.0 | 68.0 | [位置と固有値](points_c_08OB88_-1417_3.csv) |
| `08OB88_-1417` | 4 | 50.5 | 84.0 | [位置と固有値](points_c_08OB88_-1417_4.csv) |
| `08OB88_-1417` | 5 | 136.0 | 78.5 | [位置と固有値](points_c_08OB88_-1417_5.csv) |
| `08OB86_-0205` | 1 | 97.0 | 85.5 | [位置と固有値](points_c_08OB86_-0205_1.csv) |
| `08OB86_-0205` | 2 | 75.5 | 66.0 | [位置と固有値](points_c_08OB86_-0205_2.csv) |
| `08OB86_-0205` | 3 | 39.0 | 95.5 | [位置と固有値](points_c_08OB86_-0205_3.csv) |
| `08OB86_-0205` | 4 | 45.0 | 51.5 | [位置と固有値](points_c_08OB86_-0205_4.csv) |
| `08OB86_-0205` | 5 | 137.0 | 72.5 | [位置と固有値](points_c_08OB86_-0205_5.csv) |

## コミットとファイル

- 元の `realtime-map` は `2b3f04ef24dc91e6902c3ee8203c4c0c6be6dfec`。
- 実装・テストのコミットは `f76de94ddfae7cee4ec9e8323f2c450a4b02032d`。ブランチは `codex/081-drone-map-localizability`。結果と報告を後続コミットに収録した。
- 追加したコードは `conference/experiments/drone_map_rays.py`（可変間隔の三角面と最初の交点）、`conference/experiments/drone_map_localizability.py`（実験・集計・描画）、`conference/tests/test_drone_map_localizability.py`。
- 本フォルダーに `REPORT_ja.md`、`summary.csv`、`metadata.json`、`points_*.csv` 12 本、`kyutech_10cm.png`、`experiment_log.txt` を追加した。
- 既存ファイルの差分はゼロ。079 のコード・結果と 076 のコード、段階 A のデータをベースと比較し、同一バイトを確認した。

## 実行環境とコマンド

クラウドの AMD EPYC 9V45、CPU 割当 2、Python 3.12.14。NumPy 2.3.5、SciPy 1.17.0、Matplotlib 3.10.8、KISS-ICP 1.3.0、small_gicp 1.0.1。
既存の標準 venv と、`requirements_localization.txt` の版を入れた専用 venv を使った。専用 venv に `requirements-venv.txt` の依存を追加した。
Gazebo や研究 PC での計算はこの実験に含まない。

```bash
git fetch origin realtime-map
git merge-base --is-ancestor 2b3f04e FETCH_HEAD
git switch -c codex/081-drone-map-localizability FETCH_HEAD
cd conference
export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/081-mpl XDG_CACHE_HOME=/tmp/081-cache
mkdir -p /tmp/081-logs
/tmp/thesis036-venv/bin/python -u -m tests.test_planners > /tmp/081-logs/before.txt 2>&1
/tmp/thesis076-venv/bin/python -m pip install -r requirements-venv.txt
/tmp/thesis076-venv/bin/python -m experiments.drone_map_localizability --out /tmp/081-experiment --workers 2
# 各モジュールの正確なコマンドは下の全文ログ行に記録
# 標準 venv 60 本を -P 3、位置推定用 venv の 4 本を -P 2
cmp /tmp/081-logs/before.txt <(tail -n +2 /tmp/081-logs/tests.test_planners.txt | head -n -2)
/tmp/thesis036-venv/bin/python -u -m tests.test_drone_map_localizability
git diff --check
```

[実験の標準出力全文・実時間](experiment_log.txt)

## 確認とテスト出力全文

全 64 モジュールが exit=0。変更前・後の `test_planners` の出力は同一バイト。
位置推定ライブラリありの実行で 10 cm 平面は λmin 0.501216、凹凸ありは 15.950748。
ライブラリなしの実行では、この GICP テストだけが SKIP と表示された。

<details>
<summary>Python とパッケージの版</summary>

```text
$ /tmp/thesis076-venv/bin/python -VV
Python 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
$ /tmp/thesis076-venv/bin/python -m pip check
No broken requirements found.
$ /tmp/thesis076-venv/bin/python -m pip freeze
annotated-doc==0.0.7
annotated-types==0.8.0
anyio==4.16.0
certifi==2026.11.20
click==8.5.1
contourpy==1.4.0
cycler==0.12.1
fastapi==0.141.1
fonttools==4.69.1
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
kiss-icp==1.3.0
kiwisolver==1.5.1
markdown-it-py==4.3.0
matplotlib==3.10.8
mdurl==0.1.2
natsort==8.4.0
numpy==2.3.5
packaging==26.4
pandas==2.2.3
pillow==13.0.0
pydantic==2.13.4
pydantic-settings==2.16.3
pydantic_core==2.46.4
Pygments==2.21.0
pyparsing==3.3.3
pyquaternion==0.9.9
python-dateutil==4.0.0
python-dotenv==1.2.4
pytz==2026.6
rich==15.0.0
scipy==1.17.0
shellingham==1.5.4
small_gicp==1.0.1
starlette==1.6.0
tqdm==4.70.1
typer==0.29.3
typing-inspection==0.4.5
typing_extensions==4.16.0
tzdata==2026.6
uvicorn==0.52.1
$ /tmp/thesis036-venv/bin/python -VV
Python 3.12.14 (main, Aug 25 2026, 14:00:49) [Clang 22.1.3 ]
$ /tmp/thesis036-venv/bin/python -m pip check
No broken requirements found.
$ /tmp/thesis036-venv/bin/python -m pip freeze
annotated-doc==0.0.6
annotated-types==0.8.0
anyio==4.16.0
certifi==2026.10.23
click==8.5.1
contourpy==1.4.0
cycler==0.12.1
fastapi==0.141.1
fonttools==4.68.0
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.20
kiwisolver==1.5.1
matplotlib==3.10.8
numpy==2.3.5
packaging==26.3
pandas==2.2.3
pillow==13.0.0
pydantic==2.13.4
pydantic_core==2.46.4
pyparsing==3.3.3
python-dateutil==4.0.0
pytz==2026.6
scipy==1.17.0
starlette==1.6.0
typing-inspection==0.4.5
typing_extensions==4.16.0
tzdata==2026.6
uvicorn==0.52.1
```

</details>

<details>
<summary>成果物の再集計チェック</summary>

```text
Independent triangle/barycentric oracle: 1440 channels and 30% missing vertices match at 0.1 m
verified 12 scenes, 19,329 rows and all summary strata from point CSV
1450 paired Kyutech sites; 0 a-only / 89 b-only
a 0.2040421006 0.5181402509 8010.5
b 0.2054404502 0.5148732818 8229.0
079 and 076 paths and ODM inputs byte-identical to base; each generated artifact below 5 MB
PNG SHA-256 06faf0b2bcb6c2585990987943291bc05468a69a9413301a7be041d0dc0ff7cc
```

</details>

<details>
<summary>変更前の test_planners とライブラリなしの新規テスト</summary>

```text
$ /tmp/thesis036-venv/bin/python -u -m tests.test_planners
all planner tests passed
roll-aware tests passed

$ /tmp/thesis036-venv/bin/python -u -m tests.test_drone_map_localizability
1 PASS: variable grid agrees with 079 at 0.5 m, including entry from outside
2 PASS: no hits in holes or outside; finite triangles past holes remain visible
3 SKIP: KISS-ICP と small_gicp が必要です。python -m pip install -r requirements_localization.txt を実行してください。 (No module named 'kiss_icp')
4 PASS: medians of finite 5 × 5 blocks, all-empty stays empty, incomplete block omitted
crop PASS: five deterministic distinct land-only origins
all drone map localizability tests passed (optional backend skip shown above if absent)
```

</details>

<details>
<summary>全 64 モジュールの標準出力と標準エラー</summary>

```text

$ /tmp/thesis036-venv/bin/python -u -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_common_eval
beach beach centre n=1 no_path=1
1 runs -> /tmp/tmp65duf2dx/output
synthetic: geometry, revision boundaries, stops, timing, gzip, omissions and overwrite protection passed
030 08OB87_-0706 C0 n=3 completed=3
030 08OB87_-0706 C1 n=3 completed=3
030 08OB87_-0706 C2 n=3 completed=3
030 08OB88_-0167 C0 n=3 no_path=3
030 08OB88_-0167 C1 n=3 no_path=3
030 08OB88_-0167 C2 n=3 rollover=3
030 08OB88_-1417 C0 n=3 no_path=3
030 08OB88_-1417 C1 n=3 completed=3
030 08OB88_-1417 C2 n=3 completed=3
030 08OB89_-0347 C0 n=3 no_path=3
030 08OB89_-0347 C1 n=3 no_path=3
030 08OB89_-0347 C2 n=3 partial=3
030 08OB89_-0847 C0 n=3 no_path=3
030 08OB89_-0847 C1 n=3 completed=1 stuck=2
030 08OB89_-0847 C2 n=3 completed=2 partial=1
45 runs -> /tmp/tmp65duf2dx/030
030 compared per-field counts: {'exit_code': 45, 'outcome': 45, 'status': 45, 'recorded_status': 45, 'goals_reached': 45, 'returned_to_start': 45, 'truth_lethal_len_m': 45, 'truth_lethal_entries': 45, 'debris_len_m': 45, 'debris_entries': 45, 'lethal_cells': 45, 'debris_cells': 45, 'rolled_over': 45, 'deviation_mean_m': 45, 'deviation_max_m': 45, 'n_plans': 45, 'failed_plans': 45, 'fail_goal_cell': 45, 'fail_start_cell': 45, 'fail_start_steep': 45, 'map_fp_cells': 43, 'map_fn_cells': 43, 'map_fp_steep_cells': 43, 'map_fp_obstacle_only_cells': 43, 'detector_fp_cells': 43, 'detector_fn_cells': 43, 'map_updates': 45, 'map_update_s_p95': 45, 'stops_unreachable': 15, 'relaxed_len_m': 15, 'relaxed_truth_lethal_len_m': 15, 'rollover_t_s': 3}
035 08OB86_-0205 S1 n=1 completed=1
035 08OB86_-0205 S2 n=1 other_error=1
035 08OB87_-0706 P1 n=3 completed=3
035 08OB88_-0167 P1 n=3 no_path=3
035 08OB88_-1417 P1 n=3 completed=3
035 08OB89_-0347 P1 n=3 no_path=3
035 08OB89_-0847 P1 n=3 completed=3
17 runs -> /tmp/tmp65duf2dx/035
035 compared per-field counts: {'exit_code': 17, 'outcome': 17, 'status': 17, 'n_plans': 16, 'n_replans': 16, 'failed_plans': 16, 'fail_goal_cell': 16, 'ev_off_path': 16, 'ev_unsafe_tilt': 16, 'ev_safety_replanned': 16, 'map_updates': 16, 'map_update_s_median': 16, 'map_update_s_p95': 16, 'map_update_s_max': 16, 'queue_drops': 16} plus 6 sensor rows
037 08OB86_-0205 L n=3 unknown=3
037 08OB86_-0205 LC n=3 unknown=3
037 08OB88_-0167 L n=3 unknown=3
037 08OB88_-0167 LC n=3 unknown=3
037 08OB88_-1417 L n=3 unknown=3
037 08OB88_-1417 LC n=3 unknown=3
037 08OB88_00332 L n=3 unknown=3
037 08OB88_00332 LC n=3 unknown=3
037 08OB89_-0847 L n=3 unknown=3
037 08OB89_-0847 LC n=3 unknown=3
30 runs -> /tmp/tmp65duf2dx/037
037 matched 30 metadata/exit records; absent raw outcome, geometry, events and updates stayed blank
all common evaluation tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_distance_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: default/centre/overlap/overlap_goal match the base on this host for maps, plans, manifests and ROS dispatch
2 PASS: hard mask matches centre and exact rectangle distance; quadratic band and endpoint limits
3 PASS: distance increases box clearance and all three forced corridors remain passable
4 PASS: cost-acceptable shortcuts cannot reduce the exact segment-to-box minimum
5 PASS: local queries omit distant tiles and incremental distance/cost match the full rebuild
08OB86_00294 completed
integration PASS: metadata, Docker/ROS options, Multi terrain/safety modes and recorded obstacle costs
all task060 distance clearance tests passed

exit=0

$ /tmp/thesis076-venv/bin/python -u -m tests.test_drone_map_localizability
1 PASS: variable grid agrees with 079 at 0.5 m, including entry from outside
2 PASS: no hits in holes or outside; finite triangles past holes remain visible
3 PASS: plane at 0.1 m, minimum eigenvalue 0.501216, status=weak_information
3 PASS: rough at 0.1 m, minimum eigenvalue 15.950748, status=accepted
4 PASS: medians of finite 5 × 5 blocks, all-empty stays empty, incomplete block omitted
crop PASS: five deterministic distinct land-only origins
all drone map localizability tests passed (optional backend skip shown above if absent)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_edge_margin
sampling: all ten frozen default/zero-margin outputs byte-identical; 12-point draws meet 10m, 5m separation and reachability
sampling boundaries: inclusive margin, no start snapping, invalid margins and zero goals passed
cohort: independently recomputed the five changed beaches; all other metadata exactly equals task021; archived world-height bytes retained
synthetic start fixture: an insufficient start margin excludes the tour before sampling or planning, without moving it
report: 40 rows mix untouched cached rows with synthetic reruns; incomplete outcomes stay unknown; descriptive pairs, no energy/tests of significance
real adapter preparation: partial controls and both selected LiDAR cohorts accept exactly the same new metadata without ROS
dispatch fixtures: only changed eligible beaches reach the old runners; identical tour/world inputs, matched LiDAR conditions and no legacy finalizer
Docker fixture: normal read-only-source wrapper forwards fixed 0.3x/1s and refuses an existing manifest
all edge-margin tests passed (ROS2/Gazebo not required; fixture records are not experimental data)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_component
component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected
component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed
legacy bytes: only two corrected start_steep labels differ in replay; all other fields and four preparation variants unchanged
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'policy': 'escape_component', 'none': 'no_path', 'result': 'no_path', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
028b saved replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'policy': 'escape_component', 'none': 'no_path', 'result': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'raw_path_cells': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
saved component contract: both start_steep cases clear ZERO cells, protect all raw masks, retry once and advance to the next stop
all task028b component tests passed (Python only; Gazebo not run)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_endpoint_policy
1 PASS: default original runtime, path and CSV bytes unchanged
2 PASS: fixed 0.5m start escape; all three raw masks remain blocked
3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable
3b PASS: substitute remains nearby after replanning and arrival
4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates
4b PASS: stale blocked handoff stops and terminates after one timed retry
5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths
5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log
6 replay: {'case': 'results/rtf_check/divergence/R1_05/physical_1/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/rtf_check/hayashi_first_gazebo_check/physical_3/raw/08OB87_-0706', 'failure_class': 'start_steep', 'none': 'no_path', 'escape': 'unreachable_after_retry_then_next_stop', 'goal': [347, 145], 'outcome': 'unreachable', 'relaxed_cells': 1, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 replay: {'case': 'results/lidar_fine/physical_10/raw/08OB88_-1417', 'failure_class': 'goal_cell', 'none': 'no_path', 'escape': 'path', 'goal': [198, 151], 'outcome': 'nearby', 'relaxed_cells': 0, 'relaxed_truth_lethal_cells': 0, 'raw_cells_cleared': 0, 'relaxed_length_m': 0.0, 'truth_lethal_length_m': 0.0, 'cells': []}
6 PASS: three saved failures reproduced without changing fixed constants
Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_false_steep_causes
1 PASS: geometry, exact slope labels, box halo, point counts, missing stencil, relief, sea/nodata and view angles
2 PASS: committed final/first/failure data produce CSVs and a missing run is explicitly skipped
all task053 false-steep-cause tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_false_steep_inspect
1 PASS: actual lethal and steep layers, true halo and independent obstacles; first/middle/last/max
2 PASS: signed high/low endpoint errors and central/edge stencil, with optional point counts
3 PASS: fine-cell centres, inclusive 0.2 and 0.5 m, empty and absent obstacle maps
4 PASS: missing records have explicit skip reasons; independent final evidence and optional counts retained
all task069 false-steep inspection tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_footprint
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_geo
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_goal_region
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host pre-change versus none manifest, ROS dispatch, command and runtime log bytes
selection PASS: nearest feasible ring, strict visibility/steep filters, blocked start and cost tie
2 PASS: box halo unmodified; centre/overlap_goal/distance, v1/v2, plan snapshots and no reachable candidate
3 PASS: steep halo, restore before arrival, stale substitution rejected by the preserved safety handoff
08OB86_00294 completed
configuration PASS: manifest, ROS options, direct CLI, Docker forwarding and incompatible mode
all task063 goal-region tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gpu_rendering
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
Docker PASS: implicit/explicit CPU argv and env byte-identical to 045 and 056 bases; GPU mounts read-only vendor, forces EGL selection, rejects missing file before Docker, preserves toolkit errors
08OB86_00294 completed
08OB86_00294 completed
manifest PASS: CPU preparation and final mocked dispatch byte parity; GPU records passed EGL vendor only
renderer/cloud PASS: 054 Mesa/llvmpipe, sample NVIDIA and partial contexts; earliest pre-motion common stamp and matched pose range statistics
summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable
08OB86_00294 completed
GPU checkpoint PASS: run folder and Ogre2 verdict remain in the manifest before normal teardown
partial summary PASS: 054 GPU manifest without run_folder, interrupted mission and signal exit keep CPU fields
all task045/056 GPU rendering tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ground_estimate
1 PASS: implicit/explicit all_returns match pre-change update JSON, snapshots, histories, NPZ and multi-sensor sidecar bytes
2 PASS: 0.55m box creates false steep neighbours only with all_returns; box detection/inflation and all evidence unchanged
ground_estimate x y slope_deg steep box_lethal
all_returns 9 10 28.810793742973065 True True
all_returns 11 10 28.810793742973065 True True
all_returns 10 9 28.810793742973065 True True
all_returns 10 11 28.810793742973065 True True
non_obstacle 9 10 0.0 False True
non_obstacle 11 10 0.0 False True
non_obstacle 10 9 0.0 False True
non_obstacle 10 11 0.0 False True
3 PASS: all-excluded cells retain prior height and seen status; last-64 ALL returns displace older ground, then ground observations resume
4 PASS: sub-0.3m terrain changes retained; bilinear prior and the unchanged >=0.3m obstacle boundary used
5 PASS: LiDAR+two cameras share unchanged 2+1 detection evidence, source attribution and filtering; ground-only median removes false steep cells
configuration PASS: byte-identical default manifests; opt-in factory, CLI, ROS parameter and actual node constructor propagation; invalid/coarse combinations rejected
all ground-estimate tests passed; requirement 6 is verified by running every conference/tests module separately (Python only)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ground_near_obstacle
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/implicit/explicit keep map, sensor, plan, ROS and manifest bytes
2 PASS: low box wall induces a false steep cell only in keep; same detections, halo and coverage
3 PASS: the true ramp remains steep and detection is identical for prior and local reference
4 PASS: zero returns preserves prior/previous height; 0.2m boundary; dirty history agrees with full rebuild
08OB86_00294 completed
integration PASS: Fine/Multi, manifest, ROS and Docker args, distance/no_inflate/pose trace/plan maps, prior height only
all task062 ground-near-obstacle tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_lab_geometry
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_landmark_world
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host previous/default bytes for full mocked output trees, launch and dispatch
2 PASS: 161 landmarks over 10045 m², density, seed, nested positions and gaps
3 PASS: serialized prior blocks landmarks, evaluation counts debris but excludes known landmarks
4 PASS: terrain triangles and both static surfaces agree with XYZ within 5e-05 m
5 PASS: 0.500712 mm maximum Euclidean error, exceptions and empty scan preserved
capture PASS: original ROS topics/stamps, endian/row padding, cutoff and strict byte cap
08OB86_00294 completed
dispatch PASS: world, reference, manifest and separate truth-only recorder alongside pose error
all landmark world tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_lidar_figures
T4: 24 rows
T5: 38 rows
T6: 20 rows
T7: 12 rows
F8–F11, T4–T7, numbers_lidar.tex and sources.json: /tmp/tmppkq2a8ec/archive
archive PASS: all figures/tables, macros recalculated from source CSVs and exact input hashes
missing/044 PASS: remaining outputs and missing-input message; common schema extends the figures
output guard PASS: existing results, pillar-one output and paper paths rejected
050 PASS: completion and both T5 scopes are recalculated from the committed CSV
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/eval_ground_endpoint/runs.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/eval_035/runs.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/real_sensors_compare/runs.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/rtf_compare/stage_b/common_eval/runs.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/eval_064/common_eval_all/runs.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/waypoint_feasibility/goal_cell.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/terrain_from_prior/goals.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/map_speed/timing.csv
Skipped missing results file: /tmp/tmppkq2a8ec/terrain/results/rtf_compare/stage_b/sensor_updates.csv
T4: 10 rows
T5: 15 rows
T6: 4 rows
T7: 0 rows
F8–F11, T4–T7, numbers_lidar.tex and sources.json: /tmp/tmppkq2a8ec/terrain/out
057 PASS: missing input is reported and an added CSV updates F10, the tables and input hashes
legacy PASS: same-environment 030–044 tables, F9 statistics and all prior numeric macros match
064 PASS: 180 committed runs, six GPU cohorts and T4–T6/count macros match the CSV
T7 PASS: exactly 4 comparisons × 3 measures, two-sided Fisher and within-measure Holm p values
pre-068 PASS: T4–T6 rows for 030–057, old macros and F8–F10 match same-host baseline bytes
all LiDAR figure tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_local_speed
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmp6_2relkq/ten
024 08OB86_00294 start=[52, 195] points=[[309, 113], [273, 232], [104, 176], [46, 121], [250, 270]] unchanged=False
024 08OB86_-0205 start=[49, 270] points=[[114, 102], [114, 214], [42, 179], [135, 255], [93, 197]] unchanged=True
024 08OB87_-0706 start=[50, 200] points=[[89, 197], [263, 259], [59, 119], [347, 145], [39, 236]] unchanged=False
024 08OB88_-1417 start=[70, 169] points=[[337, 140], [313, 165], [199, 151], [264, 194], [203, 229]] unchanged=True
024 08OB88_-0167 start=[38, 231] points=[[137, 294], [249, 150], [202, 281], [31, 208], [348, 149]] unchanged=True
024 08OB88_00332 start=[45, 228] points=[[142, 207], [38, 131], [203, 180], [136, 171], [70, 116]] unchanged=True
024 08OB88_01832 start=[36, 214] points=[[223, 254], [335, 247], [159, 229], [264, 180], [133, 240]] unchanged=False
024 08OB89_00152 start=[48, 341] points=[[296, 173], [183, 372], [207, 192], [328, 186], [193, 222]] unchanged=False
024 08OB89_-0347 start=[55, 326] points=[[294, 224], [164, 169], [213, 144], [195, 352], [264, 374]] unchanged=False
024 08OB89_-0847 start=[70, 146] points=[[269, 98], [75, 211], [227, 332], [281, 117], [350, 279]] unchanged=True
024 PASS: 10/10 archived waypoint lists, 5/5 unchanged scenarios, default manifest bytes and wrapper forwarding
032 slope=0 box=False shift=0: fine/coarse=(0, 0)
032 slope=0 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0: fine/coarse=(0, 0)
032 slope=0 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=0 box=True shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0: fine/coarse=(0, 0)
032 slope=20 box=False shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=False shift=0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0: fine/coarse=(0, 0)
032 slope=20 box=True shift=-0.4: fine/coarse=(0, 0)
032 slope=20 box=True shift=0.4: fine/coarse=(0, 0)
CPU AMD EPYC 9V45 96-Core Processor
fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff
synthetic lidar 28800 28800 12 3.458343 3.603756 0.114587 0.165671 0 0
synthetic camera1 26750 26750 12 4.930158 5.886793 0.014257 0.056259 0 0
saved_b0b lidar 28800 11741 1 1.503161 1.503161 0.033533 0.033533 1 1
saved_b0b camera1 26750 9604 1 2.202313 2.202313 0.027928 0.027928 0 0
saved_b0b camera2 26750 9242 1 1.976616 1.976616 0.024764 0.024764 0 0
all local speed tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_localizability_map
test_alongshore_gaps_ignore_duplicate_cross_shore_positions (__main__.LocalizabilityTests.test_alongshore_gaps_ignore_duplicate_cross_shore_positions) ... ok
test_extruded_shoreline_leaves_alongshore_ambiguous (__main__.LocalizabilityTests.test_extruded_shoreline_leaves_alongshore_ambiguous) ... ok
test_hessian_includes_mixed_derivatives_in_physical_units (__main__.LocalizabilityTests.test_hessian_includes_mixed_derivatives_in_physical_units) ... ok
test_matching_ignores_samples_shifted_outside_the_patch (__main__.LocalizabilityTests.test_matching_ignores_samples_shifted_outside_the_patch) ... ok
test_off_centre_cone_is_determined (__main__.LocalizabilityTests.test_off_centre_cone_is_determined) ... ok
test_repeated_hill_has_second_minimum (__main__.LocalizabilityTests.test_repeated_hill_has_second_minimum) ... ok
test_uniform_source_height_offset_does_not_change_result (__main__.LocalizabilityTests.test_uniform_source_height_offset_does_not_change_result) ... ok
test_visibility_agrees_with_existing_ray_model_at_edges (__main__.LocalizabilityTests.test_visibility_agrees_with_existing_ray_model_at_edges) ... ok

----------------------------------------------------------------------
Ran 8 tests in 0.583s

OK

exit=0

$ /tmp/thesis076-venv/bin/python -u -m tests.test_localizability_scan
1 PASS: 16 × 1800 rays, ±15°, mount, 0.9–30 m span, 0.02 m radial noise and box/cylinder shadows
1 PASS: first mesh hit agrees with independent triangle oracle, including outside origin and multiple surfaces
2 PASS: plane λmin=0.501997, weak=cross_shore, status=weak_information
2 PASS: landmarks λmin=36.257700, weak=alongshore, status=accepted
3 PASS: 078 prepare-only inputs, 19 placements and full reference XYZ match the 075 world builder
route PASS: exact end retained; a missing sample breaks weak intervals
all localizability scan tests passed (optional backend skip shown above if absent)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_map_speed
byte-identical replay against the pre-038 implementation: 88 update states; states differing from the hashes stored on the recording machine: 0

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_mapfiles_sim
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_obstacle_clearance
1 PASS: centre default/explicit, prior/local, fine/multi; maps match the pre-041 implementation on this machine (recorded hashes also match); manifest, ROS-mocked commands and existing none/v1/v2 files match baseline
2 mode min_path_clearance_m lethal_cells path_grid
centre 0.477533728 4 [(10, 15), (11, 7)]
overlap 1.123456796 12 [(10, 15), (12, 10), (12, 8), (11, 7)]
3 PASS: full recompute after 20 updates across prior/local and fine/multi, plus dense/sparse edge cases
3 planning PASS: inferred overlap halo blocks unseen cells in normal and diagnostic planner snapshots
4 B PASS: periodic observed data incl. empty map, exact trajectory-to-box distance, CSV parts and truth-mask fallback
4 C1-C3 PASS: missing plan_history, shared path_distance (300 decisions, 23 rounding cases), class default
4 C4 and routing PASS: env-selected 1.0 honoured, overlap manifest, ROS command and wrapper
4 ROS constructor PASS: v2 runtime, overlap mapper and diagnostics selected together
all task041 obstacle clearance tests passed

exit=0

$ /tmp/thesis076-venv/bin/python -u -m tests.test_offline_localization
test_packed_recording_decodes_range_interpolates_pose_and_keeps_ns (__main__.OfflineInputTests.test_packed_recording_decodes_range_interpolates_pose_and_keeps_ns) ... ok
test_weakest_direction_is_reported_in_world_axes (__main__.OfflineInputTests.test_weakest_direction_is_reported_in_world_axes) ... ok
test_combined_corrects_at_odometry_multiples_in_landmark_scene (__main__.OfflineLocalizationTests.test_combined_corrects_at_odometry_multiples_in_landmark_scene) ... ok
test_combined_rejects_low_information_even_when_registration_converges (__main__.OfflineLocalizationTests.test_combined_rejects_low_information_even_when_registration_converges) ... ok
test_flat_plane_has_weak_translation_parallel_to_surface (__main__.OfflineLocalizationTests.test_flat_plane_has_weak_translation_parallel_to_surface) ... ok
test_kiss_icp_tracks_relative_motion_and_keeps_fixed_initial_offset (__main__.OfflineLocalizationTests.test_kiss_icp_tracks_relative_motion_and_keeps_fixed_initial_offset) ... ok
test_scan_to_map_recovers_position_and_yaw_from_initial_offset (__main__.OfflineLocalizationTests.test_scan_to_map_recovers_position_and_yaw_from_initial_offset) ... ok

----------------------------------------------------------------------
Ran 7 tests in 20.677s

OK

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_mission
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_online_safety
1 PASS: implicit/explicit none match pre-change runtime command JSON, plans/diagnostic bytes, follower trajectory/mission bytes and manifests
2 PASS: LiDAR and perfect-radius joins exempt only the start cell; later lethal cells remain rejected
3 PASS: actual stuck_0847_C1_r2_t1345 fixture search and handoff
online_fixes search_success handoff path_points outside_start_lethal_cells start_lethal
none True False 0 0 True
v1 True True 5 0 True
4 PASS: consecutive join rejection terminates at exactly 10 simulation seconds; acceptance resets the interval
5 PASS: known free-to-lethal on remaining path triggers lethal_changed only in v1; off-path changes do not replan; pending changes reset on planning
6 PASS: +/-26deg roll/pitch and 0.8m deviation stop; 24/25deg and 0.7/0.75m do not; zero linear and angular speed
safety recovery PASS: stop invalidates old work, replans from measured position, accepts replacement, ignores stale status and ends on no-path
ROS adapter PASS: real callbacks publish zero/status, preserve the open run, relay the stop and resume on a replanned path
diagnostics/concurrency PASS: v1 records diagnostics without 028b relaxation; busy pre-stop work cannot hand off and recovery uses the latest pose
configuration PASS: v1 manifest/CLI and both ROS parameter commands; 028b unchanged and excluded from v1
all online-safety tests passed; requirement 7 is checked by the complete conference/tests run

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_overlap_goal
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default, explicit centre and overlap bytes for Fine/Multi, none/v1/v2, manifest, ROS launch, paths, diagnostics and plan maps
2 PASS: overlap-only goal opens even if unseen; centre halo, prior rock and steep halo still block; Fine/Multi and sensor/prior/prior_veto
3 PASS: intermediate and former goals retain overlap, old start handoff rules apply, latest centre blockage triggers v1/v2 replanning
08OB86_00294 completed
4 PASS: manifest, ROS and mocked Docker forwarding, fine-only validation, both synthetic paths and 12 archived goals
all task052 overlap goal tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_path_tracking
1 PASS: before/current same-host manifest, ROS states, commands, trajectory, replan and stop bytes for none/v1/v2
2 PASS: straight speed, 2m corner window, 60-degree 0.5 m/s cap and strict 45-degree spin
3 PASS: 0.3 s rise/decay, 80% steady turn response, no-lag trace equals robot_sim
wiring PASS: opt-in initial/replacement paths with none/v1/v2, manifest, ROS args and Docker stub
all task043 tracking tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_plan_map_snapshots
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, missions, commands, plan CSV and diagnostic NPZ bytes; opt-in forwarding
Plan map recording stopped at 4.5 sim s: storage limit
2 PASS: exact search maps, signed-zero/delta cost, paths, prior_veto mask, handoff association and byte cap
approach: 1 rows
goal_cell: 1 rows
skipped: 0 rows
/tmp/tmpro68rdzi/absent [approach and goal_cell] skipped: no saved search maps; cannot inspect box detection or first goal block
3 PASS: interpolated closest approach uses the last handed-off plan; first blocked goal and missing-record handling
all task051 plan map snapshot tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map
flat fixture: median height, zero slope/cost, exact hit-only mask, unknown cells and immutable prior passed
box fixtures: prior-relative clusters, exact TraversabilityMap features, steep inflation and bounded unknown halo passed
registration: model/sensor offset, roll/pitch/yaw convention and stamped SO(3) interpolation passed
PointCloud2 layouts: endian, point/row padding, truncation, nonfinite/range/bounds filtering passed
model: default SDF bytes unchanged; 16 x 2deg channels, 360deg/10Hz/30m and configurable assumed mount/noise passed
LiDAR runtime: worker and delayed handoff use hit-only clouds; truth maps and virtual_sense are unavailable
/workspace/thesis_Bunker/conference/experiments/gz_lidar_report.py:159: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
quality fixtures: unique hit-cell errors, measured map times, unchanged task021 controls and unknown LiDAR outcomes passed
all pointcloud map tests passed (synthetic fixtures only; no Gazebo measurements)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pointcloud_map_fine
flat: no obstacles; only hit cells become known
noisy box fixture (seed, coarse outside lethal, fine outside lethal): [(100, 12, 8), (101, 11, 8), (102, 12, 8), (103, 12, 8), (104, 12, 8)]
box retained; 0.5m heights/cost/seen bytes and steep inflation unchanged
one dilation: exhaustive centre-to-square distance, repeated/additive seeds, centre radius bound, packed save passed
centre clearance: 0.1m side spill leaves the next coarse centre free; all <=0.5m centres blocked
boundaries: all 25 subcell phases, four map corners and diagonal square-edge clearance passed
legacy: default/explicit coarse use the unchanged class; full controlled-clock update and NPZ bytes identical
selection: legacy manifest bytes identical; fine preserves exact task022 cohort, mesh/0.3x/1s protocol
Docker wrapper fixture: coarse defaults preserved; both fine flag spellings forward the fixed run settings
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
map audit fixtures: final-lethal versus raw-detector errors distinguished; four methods retain cached values and missing fine outcomes
all fine-grid pointcloud tests passed (synthetic fixtures only, no Gazebo results)

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pose_error
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/default/none manifest, commands, run files and follower bytes
2 PASS (legacy): oblique coast, yaw, same stamped pose for cloud registration, planning, control and arrival
2 PASS (lidar_real+depth2): oblique coast, yaw, same stamped pose for cloud registration, planning, control and arrival
drift L=  1 m theory=0.010000 sample_xy=0.009762,0.009542
drift L= 10 m theory=0.031623 sample_xy=0.030688,0.031450
drift L=100 m theory=0.100000 sample_xy=0.098146,0.096925
3 PASS: 1,000 drift walks, ±10% sample standard-deviation limit, mission start and no yaw drift
4 PASS: eval_runs measures truth clearance, rollover and endpoint-mask travel without estimated fallback
08OB86_00294 completed
Task072 preparation only; Gazebo not executed: /tmp/tmpb_lpola5/prepared
wiring PASS: selected patch axes and seed, shared topic, CLI parameters and shell forwarding
all task072 pose-error tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_pose_trace
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host default manifest, run files, ROS arguments, commands, timeout boundary and control bytes for none/v1/v2
2 PASS: shared upstream, follower receipt, follower processing, missing data, stamp fallback and CPU evidence
Task058 preparation only; Gazebo not executed: /tmp/tmp1z0sx7vd/prepared
08OB86_00294 completed
3 PASS: CLI/manifest, ROS trace destinations, fake Docker, bounded CSV rollover and CPU sample
all task058 pose trace tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_prior_free
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
2-4 PASS: flat/20deg plane and 0.4m boxes, with exact and +/-0.4m shifted priors
slope_deg box prior_shift_m reference false_positive_cells missed_cells
0.0 False 0.0 prior 0 0
0.0 False 0.0 local 0 0
0.0 False -0.4 prior 81 0
0.0 False -0.4 local 0 0
0.0 False 0.4 prior 0 0
0.0 False 0.4 local 0 0
0.0 True 0.0 prior 0 0
0.0 True 0.0 local 0 0
0.0 True -0.4 prior 80 0
0.0 True -0.4 local 0 0
0.0 True 0.4 prior 0 1
0.0 True 0.4 local 0 0
20.0 False 0.0 prior 0 0
20.0 False 0.0 local 0 0
20.0 False -0.4 prior 81 0
20.0 False -0.4 local 0 0
20.0 False 0.4 prior 0 0
20.0 False 0.4 local 0 0
20.0 True 0.0 prior 0 0
20.0 True 0.0 local 0 0
20.0 True -0.4 prior 80 0
20.0 True -0.4 local 0 0
20.0 True 0.4 prior 0 1
20.0 True 0.4 local 0 0
local support PASS: fewer than 3/collinear minima remain unclassified; both real sensor modes fuse sensor-only evidence and attribution
5 PASS: true world box tops equal component maximum; lower edges/footprints/collision-visual sizes and truth NPZ unchanged
6 PASS: SeedSequence reproducibility, distinct patch seeds, preserved sea/nodata, flat none and immutable input arrays
configuration PASS: factory/CLI/manifest/ROS command forwarding; invalid coarse/local rejected; Gazebo not started
all prior-free tests passed; requirement 7 is checked by the separate complete test-module run

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_beach_las
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
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_real_sensors
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

$ /tmp/thesis076-venv/bin/python -u -m tests.test_recording_bridge
test_localization_cli_runs_all_three_methods_on_native_chunks (__main__.RecordingBridgeLocalizationTests.test_localization_cli_runs_all_three_methods_on_native_chunks) ... ok
test_manifest_for_another_case_cannot_supply_mount (__main__.RecordingBridgeTests.test_manifest_for_another_case_cannot_supply_mount) ... ok
test_manifest_uses_model_origin_and_full_orientation (__main__.RecordingBridgeTests.test_manifest_uses_model_origin_and_full_orientation) ... ok
test_missing_mount_and_foreign_reference_fail (__main__.RecordingBridgeTests.test_missing_mount_and_foreign_reference_fail) ... ok
test_native_rows_and_decoded_lidar_match_writer (__main__.RecordingBridgeTests.test_native_rows_and_decoded_lidar_match_writer) ... ok
test_sdf_composes_lidar_and_parent_link_poses (__main__.RecordingBridgeTests.test_sdf_composes_lidar_and_parent_link_poses) ... ok
test_truth_alias_described_in_review (__main__.RecordingBridgeTests.test_truth_alias_described_in_review) ... ok

----------------------------------------------------------------------
Ran 7 tests in 13.360s

OK

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_review_fixes
1 PASS: none/v1 commands, ROS follower state and log bytes unchanged; full manifest hashes 8/8
A1 v1 second tilt after 9s: replanned
A1 v2 second tilt after 9s: terminal unsafe_tilt
A1 v2 second tilt after 10s: terminal unsafe_tilt
A1 v2 second tilt after 10.1s: replanned
A2 v1 duplicate segment, 0.8m: running
A2 v2 duplicate segment, 0.8m: off_path
A3 v1 near passed segment and 0.8m from remaining route: running
A3 v2 near passed segment and 0.8m from remaining route: off_path
B6 PASS: the box is detected with support 0.70m from its centre
B9 PASS: dense/cKDTree agree on 298 heights, including unknown support
B8 5f36770 local_ground_032.py SHA-256 5a57c07f09d31e0fcf7508de6ddc28e05253cca13939eeda767ffca2ef7491f5
B8 5f36770 pointcloud_map_multi_032.py SHA-256 710d81185c5a945e9c89d1d679414c6846832f779edbc6a9e9065823ba67dc96
v2 configuration PASS: manifest, CLI, both ROS parameters and async factory
B10 PASS: fine world input NPZ, world SDF and heightmap match byte for byte; coarse matching remains explicit
Task036 task023 aggregation skipped: the waypoint cohort differs from the cached task022 controls. Manifest and available raw results: /tmp/tmpz7_23dw2/edge
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpz7_23dw2/coarse
Task036 task023 aggregation skipped: opt-in conditions require separate evaluation from task023. Manifest and available raw results: /tmp/tmpz7_23dw2/opt-in
B11 PASS: standard aggregation selected only for a comparable fine cohort
B7 controlled scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 0
6 0 0 0
7 0 0 0
8 0 0 0
9 0 0 0
10 0 0 0
11 0 0 0
B7 review scan fine_diff coarse_diff lethal_diff
0 0 0 0
1 0 0 0
2 0 0 0
3 0 0 0
4 0 0 0
5 0 0 2
6 2 2 1
7 4 2 0
8 8 2 0
9 10 3 5
10 13 3 0
11 11 2 0
all task040 review-fix tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_ros2_gz
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_rtf_option
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
/workspace/thesis_Bunker/conference/experiments/lidar_fine_report.py:168: FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation.
  data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
default 0.3 PASS: omitted/explicit match, manifest and report match pre-change hashes (full manifest)
1.0 PASS: historical overlay manifest settings and world target match; stale=1.0, step=0.001, LiDAR=10Hz
validation PASS: explicit 0.3 overrides environment; legacy rtf_check still works; invalid factor, stale and coarse rejected
wrapper PASS: split and equals options forward unchanged, with identical Docker setup
run finalization PASS: explicit 1.0 preserves manifest and skips incompatible task023 summary
all task039 RTF option tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_slope_uncertainty
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host old/default/none Fine and Multi map, manifest, ROS dispatch and plan bytes
2 PASS: 26-degree noisy slope is passable at cost 1.0; supported 30-degree slope keeps its halo
3 PASS: sample and slope errors, shared corner, prior/single/held fallbacks and local ground
08OB86_00294 completed
wiring PASS: manifest, ROS CLI, shell forwarding, independent obstacle clearance and plan fields
all task066 slope uncertainty tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_stale_prior_risk
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: sensor and prior NPZ, snapshot, multi-sensor sidecar and mocked runner bytes match same-host base
2 PASS: cutoff at 32 of 63/64; unchanged height crossing triggers veto, 0.5m halo, subsequent clearing
3 PASS: unchanged real prior slopes in all three modes; both prior modes also forbid unobserved steep cells
08OB86_00294 completed
configuration PASS: manifest, ROS argument, planner CLI, Multi local/overlap, fine-only validation and fake Docker
all task048 stale-prior-risk tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_clearance
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre
2 PASS: unchanged hard stencil, exact square distances and quadratic soft costs add to obstacle costs
3 PASS: route moves farther from slopes and all three forced gaps remain reachable
4 PASS: no clearance-reducing shortcuts; local add/remove and all terrain sources match rebuild
08OB86_00294 completed
integration PASS: CLI, manifest, ROS and fake Docker, Multi and both saved soft layers
all task065 steep clearance tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_steep_near_obstacle
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host implicit and explicit keep, Fine/Multi, all terrain sources, manifests, ROS args and plan logs
2 PASS: covered slope stays lethal, external slope keeps inflation, obstacle/height/cost bytes agree
3 PASS: obstacle-only local update and later height changes match full rebuild for Fine/Multi and all clearances
prior/veto PASS: prior seeds and rocks kept, former inferred halo refreshed, overlap_goal and plan maps work with none/v1/v2
08OB86_00294 completed
CLI PASS: fine-only opt-in, manifest, ROS args and fake Docker forwarding
all task055 steep-near-obstacle tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_terrain_from_prior
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
1 PASS: same-host before/after NPZ, update results, multi-sensor sidecars, snapshots and none/v1/v2 dispatch bytes
2 PASS: apparent steepness blocks the goal only with sensor terrain, with the same sensor elevation and box evidence
3 PASS: Fine/Multi × prior/local with overlap retains box and unobserved true steep hazards; v1/v2 tilt stop intact
08OB86_00294 completed
configuration PASS: manifest, production command, direct planner CLI, real-sensor factory and fake Docker
4 PASS: all 35 failures classified; 9/14 recovered on final maps, 3/6 on failure snapshots, 15 without either
all task047 terrain-source tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_thesis_figures

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

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tour_human_order
test_numerical_difference_rejects_the_replay (__main__.ArchivedTourTests.test_numerical_difference_rejects_the_replay) ... ok
test_recomputed_matrices_reproduce_all_five_archived_methods (__main__.ArchivedTourTests.test_recomputed_matrices_reproduce_all_five_archived_methods) ... ok
test_clusters_are_chosen_from_the_preceding_center_and_stay_together (__main__.HumanOrderTests.test_clusters_are_chosen_from_the_preceding_center_and_stay_together) ... ok
test_nearest_within_cluster_enters_from_last_waypoint (__main__.HumanOrderTests.test_nearest_within_cluster_enters_from_last_waypoint) ... ok

----------------------------------------------------------------------
Ran 4 tests in 30.524s

OK

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tour_real_beach
test_all_orders_use_same_008_legs_and_match_brute_force (__main__.TourRealBeachTests.test_all_orders_use_same_008_legs_and_match_brute_force) ... ok
test_clustered_goals_are_deterministic_separated_and_reachable (__main__.TourRealBeachTests.test_clustered_goals_are_deterministic_separated_and_reachable) ... ok
test_time_accounts_for_overlapping_corner_lookahead (__main__.TourRealBeachTests.test_time_accounts_for_overlapping_corner_lookahead) ... ok
test_time_matches_straight_and_right_angle_controller_speeds (__main__.TourRealBeachTests.test_time_matches_straight_and_right_angle_controller_speeds) ... ok

----------------------------------------------------------------------
Ran 4 tests in 0.913s

OK

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_tracking_error
1 PASS: full-path distance, Menger curvature, slope, motion direction and command bins
2 PASS: pre-path samples, same-time revisions, causal switches and task042 percentile parity
approaches PASS: interpolated strict clearance and same-box attribution
3 PASS: committed archive tables, explicit skipped input and published event-evidence coverage
all task061 tracking-error tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0

$ /tmp/thesis036-venv/bin/python -u -m tests.test_waypoint_feasibility
/tmp/thesis036-venv/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
geometry PASS: statuses, 1 m boundary, closest A* cell/tie, no-corner-cut, off-grid and invalid start
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
none PASS: three same-environment manifests, and command/mission bytes at a mocked live dispatch
08OB86_00294 completed
substitute PASS: replanned closed tour, skips and stable order in manifest and published command
Task046 preparation only; Gazebo not executed: /tmp/tmp69j2ze4r/cli
CLI/wrapper/API PASS: prepare-only, 028b conflict, forwarding and read-only preview
all waypoint feasibility tests passed

exit=0

```

</details>
