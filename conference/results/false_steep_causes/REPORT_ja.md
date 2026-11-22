# 053 保存記録で調べた偽の急斜面

基点は作業開始時の `realtime-map` の `662c3cf83b052fd091a9064b479c7938c10b6d8c`。作業ブランチは `codex/053-false-steep-causes`。分類条件は実データの集計前に `6d2679e` で固定した。実装・テスト・集計結果は `b22ebd5451a29e5a6c140704cfbbebef281eac84` に収録した。この報告は後続コミットに収録する。 [集計前の定義](PROTOCOL_ja.md)

047・048の14件で、終了時に観測済みだった陸上の偽急斜面は2,040マス。うち1,633マス（80.05%）は、検出障害物の0.5 m膨張の範囲内またはその縁から0.5 m以内にあった。0167の第5地点を塞いだセルは4件すべてで同じだった。失敗時に真値20.87°を25.28～26.82°と推定し、最寄りの検出障害物の膨張まで9.34 mあった。 [型の集計](types.csv) · [目標周辺のセル別記録](goal_cells.csv)

## 入力と変更ファイル

- `replay.py` を追加。047・048の14件を再計算し、条件と入力がそろう追加走行を系列・センサー構成別に集計した。評価用NPZの事前・真値地図の署名をmanifestと照合し、最終通行不可マスクも保存値と一致することを確認した。初回の点数は既存マッパーを通した最大64点/セルの保持履歴から求めた。 [047の入力一覧](../terrain_from_prior/runs.csv) · [048の報告](../stale_prior_risk/REPORT_ja.md)
- `inventory.csv`、`runs.csv`、`features.csv`、`types.csv`、`overlaps.csv`、`goal_cells.csv`、`replay_log.txt` を追加。採否、走行・段階別の数、特徴の分位点、型の件数と割合、型の組み合わせ、0167のセル別記録、実行出力を保存した。
- `conference/tests/test_false_steep_causes.py` を追加。人工地図で判定と特徴を検証し、コミット済みの走行から表を作成しながら、入力が欠けた件の理由が表示されることを確認した。 `PROTOCOL_ja.md` と本報告も同じ結果フォルダに追加した。

入力候補116件のうち80件を使用した。14件の主対象はすべて使用できた。除外36件の内訳は、035の失敗時地図のみ6件、037の8件と039の7件（終了時地図・初回点群が未収録）、細格子障害物を持たない022の粗格子10件、初回点群だけの5件（030の2件、023の途中記録1件、RTF確認の2件）。評価用地図には022の保存済み標高を使い、海・欠測は200 mのLAS元DEMから求めた。 [採否と理由](inventory.csv)

## 主対象14件の集計

25°超を急斜面とし、膨張前の推定傾斜と評価用標高の傾斜をマスごとに比較した。終了時に観測済みだった608,700マスのうち、海38,552マスと欠測97マスを外した570,051マスが陸上の分母。初回LiDARの観測マス18,533はすべて陸上だった。047の5,803は通行不可の判定と膨張、評価用の不可マスクを使った023の指標。053の表は傾斜値の判定そのものを比較している。 [走行別の数](runs.csv) · [047の指標](../terrain_from_prior/map_errors.csv)

| 段階 | 偽の急斜面 | 正しい急斜面 | 正しい非急斜面 | 見落とした急斜面 |
|---|---:|---:|---:|---:|
| 初回LiDAR | 209 | 973 | 17,265 | 86 |
| 終了時 | 2,040 | 5,562 | 561,544 | 905 |

### 型の該当数と割合

| 型 | 初回の偽急斜面 | 終了時の偽急斜面 | 終了時の正しい急斜面 | 終了時の正しい非急斜面 |
|---|---:|---:|---:|---:|
| 箱付近 | 50（23.92%） | 1,633（80.05%） | 24（0.43%） | 28,793（5.13%） |
| 初回の点が少ない | 32（15.31%） | 206（10.10%） | 232（4.17%） | 11,823（2.11%） |
| 真値が20～25° | 21（10.05%） | 368（18.04%） | 0（0%） | 2,217（0.39%） |
| 真の高さのばらつきが大きい | 20（9.57%） | 372（18.24%） | 5,562（100%） | 2,154（0.38%） |
| 海・欠測の近く | 0（0%） | 1（0.05%） | 4（0.07%） | 3,458（0.62%） |

終了時の偽急斜面のうち、初回に3×3の近傍へ1点以上入ったのは413/2,040マス（20.25%）。この413マスでは206マス（49.88%）が1～8点だった。正しい急斜面では232/2,428（9.56%）、正しい非急斜面では11,823/44,315（26.68%）。終了時に差分の計算に使ったセルの一部が未観測だった割合は、偽急斜面で447/2,040（21.91%）、正しい急斜面で373/5,562（6.71%）、正しい非急斜面で44,217/561,544（7.87%）。初回の偽急斜面では197/209（94.26%）だった。 [型と観測状況](types.csv)

### 型の重なり

終了時の偽急斜面2,040マスについて、列挙した型だけに該当する場合の数を示す。初回は該当なし107、箱付近だけ50、初回の点が少ないだけ31、点が少なく真値が境目1、真値が境目かつ高低差あり20だった。 [全段階・全分類の組み合わせ](overlaps.csv)

| 終了時に該当した型の組み合わせ | マス数 | 割合 |
|---|---:|---:|
| 箱付近だけ | 1,445 | 70.83% |
| 真値が境目＋高低差 | 313 | 15.34% |
| 箱付近＋初回の点が少ない | 170 | 8.33% |
| 初回の点が少ない＋真値が境目＋高低差 | 33 | 1.62% |
| 該当なし | 33 | 1.62% |
| 高低差だけ | 23 | 1.13% |
| 箱付近＋真値が境目 | 13 | 0.64% |
| 真値が境目だけ | 3 | 0.15% |
| 箱付近＋真値が境目＋高低差 | 3 | 0.15% |
| 箱付近＋初回の点が少ない＋真値が境目 | 2 | 0.10% |
| 初回の点が少ない＋真値が境目 | 1 | 0.05% |
| 海・欠測の近くだけ | 1 | 0.05% |

### 特徴の比較

初回LiDARで偽急斜面になったマスの保持点数の中央値は、中央4点、周囲8セル19点、中央を含む3×3全体27点。正しい急斜面は5/11/16点、正しい非急斜面は7/26/34点だった。初回の偽急斜面の水平距離11.51 m・絶対方位49.57°・入射角5.84°に対し、正しい急斜面は22.85 m・92.60°・22.65°、正しい非急斜面は11.28 m・90.00°・7.00°。偽急斜面の入射角の10～90%点は1.48～15.19°で、正しい非急斜面の2.58～13.70°と重なった。 [特徴の10・50・90%点と有効数](features.csv)

| 終了時の指標の中央値 | 偽の急斜面 | 正しい急斜面 | 正しい非急斜面 |
|---|---:|---:|---:|
| 検出障害物まで m | 0.28 | 12.90 | 6.46 |
| 検出障害物の膨張まで m | 0.00 | 12.36 | 5.91 |
| 真値の傾斜 ° | 5.77 | 33.02 | 3.38 |
| 推定の傾斜 ° | 28.31 | 31.27 | 3.37 |
| 3×3標高の標準偏差 m、真値／推定 | 0.052／0.203 | 0.267／0.251 | 0.027／0.026 |
| 海まで m | 41.67 | 90.50 | 61.50 |
| 欠測まで m | 50.00 | 7.50 | 54.39 |
| 初回の水平距離 m | 61.14 | 48.43 | 78.45 |
| 初回の絶対方位 ° | 21.28 | 32.39 | 19.50 |
| 初回の入射角 ° | 2.63 | 15.84 | 1.43 |

終了時の初回幾何の中央値にはLiDAR最大距離30 mの外が含まれる。終了時の偽急斜面の1,627マス（79.75%）では初回の3×3の点が0だった。最後にそのセルの標高を更新したときの距離、方位、点数は記録されていない。海・欠測も含む観測済み格子では偽急斜面に相当する傾斜の食い違いが3,577マスあり、陸上から外した分は1,537マス（海1,536、欠測1）だった。陸上の海・欠測付近で1マスという結果は、この分を含まない。 [走行別の数](runs.csv)

### 追加走行

| 終了時の記録系列 | 件数 | 陸上の観測済みマス | 偽急斜面 | 箱付近の割合 |
|---|---:|---:|---:|---:|
| 030の残り | 29 | 1,668,138 | 10,715 | 14.47% |
| 023のfine系列 | 13 | 554,722 | 3,313 | 73.59% |
| 実機構成LiDARの予備記録 | 1 | 32,856 | 150 | 97.33% |
| 実機構成LiDAR＋カメラ2台の予備記録 | 2 | 68,923 | 326 | 95.40% |
| RTF確認系列 | 21 | 1,240,250 | 5,580 | 94.48% |

030の追加29件にはC2が15件あり、追加分の偽急斜面の8,870マスを占めた。主対象14件は030の `goal_cell` から選ばれており、別系列や条件に80.05%を適用する根拠はない。カメラを含む走行の初回は、保存されたLiDARを単独で再処理した。 [追加走行の指標](runs.csv) · [030の条件](../eval_ground_endpoint/REPORT_ja.md)

## 0167 第5地点 (137, 294)

初回LiDARでは、4件とも目標への水平距離が58.67 mで、周囲2.0 mに点が入らなかった。失敗時、目標セルの真値は10.79°で、推定は7.02～11.99°だった。0.5 m隣の (137, 293) だけが目標を急斜面の膨張で塞いでいた。この隣接セルの真の傾斜は20.87°、3×3真値標高の標準偏差は0.220 m。すべての差分セルがこの時点で観測済みだった。初回の点は0で、実際に急斜面が作られたときの点の数は不明。海まで96.0 m、欠測まで2.69 m、検出障害物の膨張まで9.34 mだった。 [セルごとの高さ・斜度・観測有無](goal_cells.csv)

| 030の走行 | 塞いだ隣接セルの失敗時傾斜 | 終了時傾斜 | 周囲2 mの観測済み偽急斜面、失敗時／終了時 |
|---|---:|---:|---:|
| C0 r2 | 26.82° | 27.01° | 3／3 |
| C1 r1 | 26.11° | 26.76° | 2／2 |
| C1 r2 | 26.31° | 26.35° | 3／4 |
| C1 r3 | 25.28° | 25.28° | 3／4 |

隣接セル (137, 293) の傾斜を決めた主な差分はy方向だった。(137, 292) と (137, 294) の1 m間の標高差は真値0.380 m、失敗時の推定0.466～0.506 m。その低い側の (137, 292) が真値より0.150～0.185 m低く推定され、y方向の傾斜が過大になった。

047で数えた同地点の `goal_cell` 19件のうち、上表は終了時地図と初回点群の両方がある4件。035の3件は失敗時地図だけがあり、残り12件は格子が未収録だった。030では別条件のC2に転倒3件の記録もある。 [047の地点別出典](../terrain_from_prior/goals.csv) · [030の転倒記録](../eval_ground_endpoint/REPORT_ja.md)

## センサー側で減らす案と見落としの危険

| 型 | 減らす案 | 本当の急斜面を見落とす危険 |
|---|---|---|
| 箱付近 | 高さの層が分かれる場合は上層の点を地面の推定から外し、下層に地面の支持がある場合に限って傾斜を再計算する。障害物の検出と余白は保つ。 | 崖の上端や新しい砂の盛り上がりを箱の上層として外す可能性。下層が見えない場合は地面の傾斜を未確定とする。 |
| 点が少ない | 傾斜差分の両端に十分な点がそろうまで保留し、別の姿勢から観測を追加する。 | 急斜面は遮蔽や浅い入射で点が集まりにくい。保留中のセルを通行可として扱うと見落としにつながる。 |
| 境目の傾斜 | 25°付近で測定誤差が閾値をまたぐ場合に、別方向の点群で傾斜の符号と大きさを確認する。 | 本当に25°を少し超える斜面の検出が遅れる。再観測前に通行可へ変更すると進入する可能性がある。 |
| 高低差 | 単一のセル中央値に頼らず、局所面の残差と斜面の連続性を確認し、段差・崖を別に扱う。 | 広い窓で平滑化すると狭い実斜面が消える。正しく検出した急斜面の全5,562マスが今回の高低差条件を満たす。 |
| 海・欠測付近 | 欠測をまたぐ差分は保留し、同じ陸側の観測から傾斜を確認する。 | 海岸の段差や欠測の向こう側の実斜面が保留になる。海・不明領域と隣接する斜面の通行可否は別に考える必要がある。 |

029の合成点群テストでは、地面の推定から高い点を外すと、箱に隣接する4セルが28.81°から0°になり、箱の通行不可は維持された。今回の保存記録には終了時の点群履歴がなく、同じ走行での効果は再計算していない。 [029のテスト](../ground_estimate/REPORT_ja.md)

## 確認できなかったこと

検出マスクは箱以外も含むため、近接だけで点の混入を確定できない。0167では境目の真の斜面と標高推定誤差の組合せを再現できた。元の点の内訳、遮蔽、入射方向、姿勢のずれなど、標高誤差の発生過程は初回以降の点群・姿勢履歴がないため切り分けられなかった。海では評価に使われた標高より実際の水面が観測された可能性があり、欠測の傾斜値は補間に依存する。スクリプトの見落とし数は膨張前の傾斜判定であり、通行止めの見落とし数とは異なる。センサー側の案の改善量・見落とし・走行安全性は未検証。クラウドで保存記録とPythonを使い、Gazeboと研究PCでの実行は行っていない。

## 実行コマンド

クラウドにあった `/tmp/venv038`（Python 3.12.14）を使用した。`pip freeze` で `conference/requirements-venv.txt` の9パッケージの版が一致することを確認した。変更前と変更後にプランナーテストを実行した。既存モジュールの実行を開始したあと、新規モジュールを個別に実行した。

~~~bash
git fetch origin realtime-map
git rev-parse FETCH_HEAD
git switch -c codex/053-false-steep-causes FETCH_HEAD
/tmp/venv038/bin/python --version
/tmp/venv038/bin/python -m pip freeze
mkdir -p /tmp/053-tests
cd conference
OPENBLAS_NUM_THREADS=1 /tmp/venv038/bin/python -m tests.test_planners \
  > /tmp/053-tests/before-planners.log 2>&1

export OPENBLAS_NUM_THREADS=1 MPLCONFIGDIR=/tmp/053-mpl XDG_CACHE_HOME=/tmp/053-cache
find tests -maxdepth 1 -name 'test_*.py' -print0 | sort -z |
  xargs -0 -n1 -P4 sh -c '
    name=${1##*/}
    name=tests.${name%.py}
    /tmp/venv038/bin/python -u -m "$name" >"/tmp/053-tests/$name.log" 2>&1
    printf "%s\n" "$?" >"/tmp/053-tests/$name.status"
  ' _
/tmp/venv038/bin/python -u -m tests.test_false_steep_causes \
  > /tmp/053-tests/tests.test_false_steep_causes.log 2>&1
printf '%s\n' "$?" > /tmp/053-tests/tests.test_false_steep_causes.status

export PYTHONPATH=.
mkdir -p /tmp/053-final-replay /tmp/053-repro-replay
/tmp/venv038/bin/python -u results/false_steep_causes/replay.py --out /tmp/053-final-replay \
  > /tmp/053-final-replay/replay_log.txt
/tmp/venv038/bin/python -u results/false_steep_causes/replay.py --out /tmp/053-repro-replay \
  > /tmp/053-repro-replay/replay_log.txt
diff -r /tmp/053-final-replay /tmp/053-repro-replay
cp /tmp/053-final-replay/{features.csv,goal_cells.csv,inventory.csv,overlaps.csv,replay_log.txt,runs.csv,types.csv} \
  results/false_steep_causes/
cd ..
git diff --check 662c3cf..HEAD
git diff --name-status 662c3cf..HEAD
git push -u origin codex/053-false-steep-causes
git ls-remote --heads origin refs/heads/codex/053-false-steep-causes
~~~

分類条件のコミット後、`--out /tmp/053-first-replay` で集計し、出力を確認した。続けて `--out results/false_steep_causes` で目標周辺の標高列を加えた。最終版では海・欠測に相当する件数の内訳も追加し、上記の別フォルダへの2回の集計で検証した。 [再集計の標準出力全文](replay_log.txt)

### 追加テストの初回実行

人工地図の地点 (3, 3) は欠測からちょうど1.0 mだった。初回テストでは範囲外と誤って期待していたため、条件どおり範囲内を期待するよう修正した。後続の試行では書き込み可能なキャッシュ先を指定した。

~~~bash
cd conference
OPENBLAS_NUM_THREADS=1 /tmp/venv038/bin/python -u -m tests.test_false_steep_causes
~~~

~~~text
mkdir -p failed for path /home/agent/.config/matplotlib: [Errno 30] Read-only file system: '/home/agent/.config/matplotlib'
Matplotlib created a temporary cache directory at /tmp/matplotlib-hfh2yxr2 because there was an issue with the default path (/home/agent/.config/matplotlib); it is highly recommended to set the MPLCONFIGDIR environment variable to a writable directory, in particular to speed up the import of Matplotlib and to better support multiprocessing.
Fontconfig error: No writable cache directories
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/workspace/thesis_Bunker/conference/tests/test_false_steep_causes.py", line 96, in <module>
    test_features()
  File "/workspace/thesis_Bunker/conference/tests/test_false_steep_causes.py", line 55, in test_features
    assert types['sea_or_nodata_near'][cell] and not types['sea_or_nodata_near'][3, 3]
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError
~~~

### レコードと集計表の照合結果

2回の独立した出力先のCSV6点と実行ログは、`diff -r` で全ファイルがバイト単位で一致した。CSVから直接数え直し、観測マスの分類、型の単独件数と組み合わせ、0167の同一セルによる4件の閉塞を照合した。

~~~text
CSV audit PASS: record coverage, partitioned counts, type intersections and four goal blockers agree
~~~

### 変更前のプランナーテスト出力全文

~~~~text
all planner tests passed
roll-aware tests passed
~~~~

### 変更後の全テスト出力全文

既存44本と追加1本の計45モジュールがすべて終了コード0。プランナーテストは変更前と同じ出力だった。

<details>
<summary>45モジュールの標準出力・標準エラー</summary>

~~~~text
$ /tmp/venv038/bin/python -u -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_common_eval
beach beach centre n=1 no_path=1
1 runs -> /tmp/tmpwi9ys2pi/output
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
45 runs -> /tmp/tmpwi9ys2pi/030
030 compared per-field counts: {'exit_code': 45, 'outcome': 45, 'status': 45, 'recorded_status': 45, 'goals_reached': 45, 'returned_to_start': 45, 'truth_lethal_len_m': 45, 'truth_lethal_entries': 45, 'debris_len_m': 45, 'debris_entries': 45, 'lethal_cells': 45, 'debris_cells': 45, 'rolled_over': 45, 'deviation_mean_m': 45, 'deviation_max_m': 45, 'n_plans': 45, 'failed_plans': 45, 'fail_goal_cell': 45, 'fail_start_cell': 45, 'fail_start_steep': 45, 'map_fp_cells': 43, 'map_fn_cells': 43, 'map_fp_steep_cells': 43, 'map_fp_obstacle_only_cells': 43, 'detector_fp_cells': 43, 'detector_fn_cells': 43, 'map_updates': 45, 'map_update_s_p95': 45, 'stops_unreachable': 15, 'relaxed_len_m': 15, 'relaxed_truth_lethal_len_m': 15, 'rollover_t_s': 3}
035 08OB86_-0205 S1 n=1 completed=1
035 08OB86_-0205 S2 n=1 other_error=1
035 08OB87_-0706 P1 n=3 completed=3
035 08OB88_-0167 P1 n=3 no_path=3
035 08OB88_-1417 P1 n=3 completed=3
035 08OB89_-0347 P1 n=3 no_path=3
035 08OB89_-0847 P1 n=3 completed=3
17 runs -> /tmp/tmpwi9ys2pi/035
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
30 runs -> /tmp/tmpwi9ys2pi/037
037 matched 30 metadata/exit records; absent raw outcome, geometry, events and updates stayed blank
all common evaluation tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_edge_margin
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

$ /tmp/venv038/bin/python -u -m tests.test_endpoint_component
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

$ /tmp/venv038/bin/python -u -m tests.test_endpoint_policy
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

$ /tmp/venv038/bin/python -u -m tests.test_false_steep_causes
1 PASS: geometry, exact slope labels, box halo, point counts, missing stencil, relief, sea/nodata and view angles
2 PASS: committed final/first/failure data produce CSVs and a missing run is explicitly skipped
all task053 false-steep-cause tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_footprint
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

$ /tmp/venv038/bin/python -u -m tests.test_geo
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_gpu_rendering
Docker PASS: absent/explicit cpu byte-identical to base; gpu forwarding, toolkit error and invalid selection
manifest PASS: cpu byte parity, also with historical protocol; gpu records mode without changing other fields
renderer/cloud PASS: actual Ogre device extraction and fallback; earliest pre-motion common stamp and matched pose range statistics
summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable
all task045 GPU rendering tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_ground_estimate
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

$ /tmp/venv038/bin/python -u -m tests.test_gz_compare
comparison scenarios: first six LAS test patches, clean 200m seed0; both methods match direct start/goal/path calls
unavailable-world fixture: all scenarios retained, one export attempt per beach, no invented physical measurements
worlds: all six LAS maps reconstructed from decoded PNGs within 0.1m; default exports unchanged by explicit legacy limit; invalid limits rejected
comparison report: 6x2 kinematic fixtures agree with analyze_run; paired medians, immutable raw logs and excluded columns passed
fixture values are simulated test data, not Gazebo measurements
all Gazebo comparison tests passed (ROS2/Gazebo not required)

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_gz_online_batch
scenarios: first ten LAS test beaches; truth/prior arrays, seed-selected five points, task014 order and inflated plans agree with direct calls
runtime: unchanged async worker uses the predeparture order; opt-in masks and blocked endpoints verified
synthetic fixtures only: completion/stuck/rollover/timeout, five-target prefix, contact, active-path deviation, planning times and immutable originals passed
raw CSV parts: strict file limit, repeated headers, exact numeric strings and complete record order passed
unrun report: twenty scenarios retained, unknown physical outcomes stay blank, no energy/map/world artifacts and overwrite refused
synthetic paired counts: incomplete tours excluded from paired medians; each outcome retains the actual-recording denominator
all Gazebo online batch tests passed (ROS2/Gazebo not required; fixture measurements are not experimental data)

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_lab_geometry
1 PASS: flat terrain and physical 5/12/22/30deg planes match independent eight-neighbour formula; all six cost stages and uint8 truncation
2 PASS: <=3 valid neighbours and absent centres stay unknown; fourth valid neighbour enables cost
3 PASS: pinned Jazzy setCostmap integer conversion, 253/254 blockage and allowed unknown=253
4 PASS: no raw obstacle contact/corner cuts; blocked starts and disconnected goals rejected; independent Dijkstra optimum; one 0.35m square-distance inflation
5 PASS: task013 A*/TA*-S all non-energy path metrics and scenario identifiers match clean/debris, 100/200m; times independently remeasured
all lab-geometry tests passed; requirement 6 is checked by the full conference/tests suite

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_lidar_figures
T4: 12 rows
T5: 14 rows
T6: 14 rows
F8, F9, T4–T6, numbers_lidar.tex and sources.json: /tmp/tmpri_walvg/archive
archive PASS: all figures/tables, macros recalculated from source CSVs and exact input hashes
missing/044 PASS: remaining outputs and missing-input message; common schema extends the figures
output guard PASS: existing results, pillar-one output and paper paths rejected
all LiDAR figure tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_local_speed
1 PASS: pre-change map NPZ/snapshot/history/sidecar, world and manifest SHA-256 match; explicit prior matches implicit default
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpzms_u0kx/ten
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
CPU AMD EPYC 9V74 80-Core Processor
fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff
synthetic lidar 28800 28800 12 12.150142 16.101823 0.368565 0.523212 0 0
synthetic camera1 26750 26750 12 16.580757 20.355122 0.079888 0.115017 0 0
saved_b0b lidar 28800 11741 1 2.453366 2.453366 0.077043 0.077043 1 1
saved_b0b camera1 26750 9604 1 3.402250 3.402250 0.065276 0.065276 0 0
saved_b0b camera2 26750 9242 1 5.472414 5.472414 0.033884 0.033884 0 0
all local speed tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_map_speed
byte-identical replay against the pre-038 implementation: 88 update states; states differing from the hashes stored on the recording machine: 0

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_mapfiles_sim
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_mission
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_obstacle_clearance
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

$ /tmp/venv038/bin/python -u -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_online_deadend
safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed
08OB86_00294: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB86_-0205: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OB87_-0706: disabled trajectory/count parity and A/B/A+B stale five-point contacts=0
08OC99_01733 stale R10: validation-frozen B completed without contact
all online dead-end tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_online_mission
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_online_safety
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

$ /tmp/venv038/bin/python -u -m tests.test_path_tracking
1 PASS: before/current same-host manifest, ROS states, commands, trajectory, replan and stop bytes for none/v1/v2
2 PASS: straight speed, 2m corner window, 60-degree 0.5 m/s cap and strict 45-degree spin
3 PASS: 0.3 s rise/decay, 80% steady turn response, no-lag trace equals robot_sim
wiring PASS: opt-in initial/replacement paths with none/v1/v2, manifest, ROS args and Docker stub
all task043 tracking tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_plan_map_snapshots
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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
/tmp/tmpx2dosw51/absent [approach and goal_cell] skipped: no saved search maps; cannot inspect box detection or first goal block
3 PASS: interpolated closest approach uses the last handed-off plan; first blocked goal and missing-record handling
all task051 plan map snapshot tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_planners
all planner tests passed
roll-aware tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_pointcloud_map
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

$ /tmp/venv038/bin/python -u -m tests.test_pointcloud_map_fine
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

$ /tmp/venv038/bin/python -u -m tests.test_prior_free
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

$ /tmp/venv038/bin/python -u -m tests.test_real_beach
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

$ /tmp/venv038/bin/python -u -m tests.test_real_beach_las
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
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
mapfiles: all 12 LAS validation files match build_real exactly and retain Ground attribution
comparison: identity joins reject missing/duplicate cases; 16-bit PNG filters preserve standard-decoded height samples
all real-beach LAS tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_real_sensors
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

$ /tmp/venv038/bin/python -u -m tests.test_review_fixes
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
Task036 task023 aggregation skipped: the waypoint cohort differs from the cached task022 controls. Manifest and available raw results: /tmp/tmpa9g2maj2/edge
Task036 task023 aggregation skipped: the task023 report requires --map fine. Manifest and available raw results: /tmp/tmpa9g2maj2/coarse
Task036 task023 aggregation skipped: opt-in conditions require separate evaluation from task023. Manifest and available raw results: /tmp/tmpa9g2maj2/opt-in
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

$ /tmp/venv038/bin/python -u -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_ros2_gz
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_rtf_option
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

$ /tmp/venv038/bin/python -u -m tests.test_stale_prior_risk
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_terrain_from_prior
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
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

$ /tmp/venv038/bin/python -u -m tests.test_thesis_figures

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

$ /tmp/venv038/bin/python -u -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_visibility
visibility: all cells in the physical radius visible on flat terrain, including clipped edges
visibility: front and wall top visible, cells behind the wall occluded
visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell
sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed
control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit
all visibility tests passed

exit=0

$ /tmp/venv038/bin/python -u -m tests.test_waypoint_feasibility
/tmp/venv038/lib/python3.12/site-packages/fastapi/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
geometry PASS: statuses, 1 m boundary, closest A* cell/tie, no-corner-cut, off-grid and invalid start
08OB86_00294 completed
08OB86_00294 completed
08OB86_00294 completed
none PASS: three same-environment manifests, and command/mission bytes at a mocked live dispatch
08OB86_00294 completed
substitute PASS: replanned closed tour, skips and stable order in manifest and published command
Task046 preparation only; Gazebo not executed: /tmp/tmpudv8b2xh/cli
CLI/wrapper/API PASS: prepare-only, 028b conflict, forwarding and read-only preview
all waypoint feasibility tests passed

exit=0

~~~~

</details>
