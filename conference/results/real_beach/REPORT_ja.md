# 実測砂浜での計画・再計画・巡回：実装・検証報告

最新取得した `realtime-map`（`2ff60d8`）を土台に、`codex/real-beach` で実装した。変更は新しいファイルへの追加だけであり、既存のコード、結果、`conference/data/` は変更していない。

## 実装

- `conference/tapp/real_beach.py`：`list_patches`、`load_patch`、`build_real` と最近傍補完。NaNを含む読み込み結果を保持し、計画用には `distance_transform_edt(..., return_indices=True)` で補完する。元データなし、水域、漂着物をまとめて `TraversabilityMap` の障害物引数へ渡し、既存のロボット半径で膨張する。
- 100mの切り出しは海岸線方向の開始セルを0〜200から選び、海から陸への軸は `[60:260]`。200mでは全体を使う。シードは指定の `SeedSequence([seed, 4000, side_m, パッチ番号])` を根に、再試行番号を `spawn_key` に入れ、切り出し・漂着物・端点に3つの子系列を割り当てる。漂着物の有無によって切り出し用乱数の消費が変わらない。再試行で切り出しや端点が変わる場合は、CSVに再試行回数と切り出し原点を保存する。
- 漂着物は007の流木配置を単独で再利用できる関数がなかったため、新しいファイルに同じ密度・長さ・厚さ・角度の規則で記述した。岩の直径分布には既存の `rock_population` をimportして使う。中心は85%を標高0.3〜2.5m、残りを2.5m超の陸から選び、該当帯がない場合だけ有効な陸全体へ戻す。流木と大きな岩のマスク、007と同じ岩のGaussian標高盛り上がりを、元の有効な陸の範囲だけに制限する。これらは実測された漂着物ではなく仮想的な追加障害物であり、元の標高とマスクを別に保持する。
- `conference/experiments/real_beach.py`：指定された(A)〜(D)を `multiprocessing.Pool` で実行する。Aは実測60パッチと人工3種類×検証シード5個。B/Cはテスト48パッチ×100/200m×漂着物なし/あり。Dは200mの96シナリオで5/8/12地点、指定の3方法を比較する。パラメータの調整はしていない。
- Bは007と同じ5プランナーを使い、既存のTA*-Sとexact版を両方残す。Cは007と同じ7条件、同じ `coarse_prior`、`unknown_cost="adaptive"`、`prior_lethal="soft"`、`exact_los=True` を使う。Dは既存の008の地点抽出・行列・Held–Karpを再利用し、方法間で物理κの区間経路を共有して順番だけを比較する。
- 長い実験を途中から再開できるよう、コードのSHA-256に対応する `/tmp/real-beach-cache/` へケース単位の結果を保存する。通常実行は全ケースを計算し直し、`--resume` を明示した場合だけ保存済み結果を読む。図のための軌跡もここに置く。保存CSVとログは新しい `conference/results/real_beach/` だけへ書く。
- `conference/tests/test_real_beach.py`：全データの読み込み・分割・向き、最近傍補完、指定された最初の5テストパッチの100/200m切り出し・再現性・障害物・到達可能性、漂着物、exact計画と粗い事前地図を使うオンライン走行の安全性を確認する。漂着物なし/ありの両方を検査する。

## 元データの向き条件の不一致（未解決）

指定の向き検査を緩めずに実行すると、配布データのうち2パッチが条件を満たさない。`08OC92_-1251`（validation）は平均断面のy=0〜50mに海面を超える位置がなく、`08PD13_00846`（test）はy=−50m側の平均標高が海面以上になる。数値と失敗のトレースはテスト出力全文に記載する。データの修正、パッチの除外、検査の緩和はしていない。ほかの検査を継続するため、各テストグループを実行して失敗を集約し、失敗が1つでもあれば終了コード1を返す。

このため、指示書の「すべてのテストが通る」という完了条件は達成していない。入力データの変更は禁止されているので、この不一致の解決には元データまたは要求条件についての判断が必要になる。実験は指定の全パッチを含めて実施する。

図の座標軸は切り出し範囲の左下を基準にした距離であり、T.P.の高さや元の平面直角座標を示す軸ではない。水域は青、データなしは紫、通行不可領域は灰色で重ねる。

## 測定の定義と解釈上の限界

Aの陸は元データが有限で標高0m以上のセル、前浜はそのうち0〜2mのセルとする。前浜勾配は陸向き軸の標高勾配の中央値。陸幅は各沿岸方向位置について、最初の有効な陸セルから、通行可能な陸を経て最初に現れる通行不可セルまたはデータなしセルまでを測り、その中央値を取る。通れる陸がない断面は幅0、陸自体がない断面は除外する。海岸線や陸端がパッチ外の場合は、この有限範囲内での幅になる。最近傍補完は傾斜・roughの境界付近に影響しうる。スペクトルは既存の `spectrum_slope` と同じ動径平均法を補完後の200mパッチ全体へ使うため、水域、断面の大きな勾配、欠測補完も含む。陸だけの微細な粗さの独立測定と解釈しない。

Aの人工値と実測の10〜90%範囲の比較は、3種類それぞれの検証シード5個の中央値を、全60実測パッチの分位点と比べる記述的な比較である。validationとtestの実測中央値も分けて表示する。この比較結果を見て人工地形やパラメータを調整していない。

Dの行列時間は基地を含む13点分であり、5/8/12地点の先頭部分に再利用する。ユークリッド行列の時間は順番を決める行列の構築時間で、共通の物理κ区間を作る時間を含まない。物理κ行列の構築時間はterrain dirの欄で確認できる。κ=0でも方向ごとの貪欲平滑化・既存の丸め標本化により行列が完全には対称にならないため、008と同じく監査値を示す。閉じた巡回では端点標高のポテンシャルが相殺されるので、改善を非対称性だけの効果とは呼ばない。

実測地形の漂着物なし/ありでは、障害物による再抽出や到達可能性の違いにより、端点・切り出し・巡回地点が異なる場合がある。方法間では同一シナリオ・区間経路を共有するが、漂着物の有無の差を同一経路への障害物だけの因果効果と解釈しない。人工との比較はBを100/200m、Cを100m、Dを200mの砂浜3種類に限定し、異なる地形分布の記述的な比較として示す。

## 出典（データREADMEからそのまま転載）

- 出典：静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）
  https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
- ライセンス：CC BY 4.0 / ODbL。**このフォルダのデータは、上のデータを加工して作成したものです**
  （論文や発表で使うときは、この出典を書くこと）。
- 元データの座標：日本測地系2024・平面直角座標系第8系、高さは東京湾平均海面（T.P.）。


## 実測結果と人工地形との比較

全ケースの計算は終了した。Aは75ケース、Bは960経路、Cは1344条件、Dは864巡回と7488組の地点間コスト。既存の追跡済みconferenceファイル289個はSHA-256が一致した。

Aで人工地形の中央値が実測の10〜90%範囲から外れた項目は次のとおり。数値は下の集計表にそのまま掲載する。

- beach_gentle：slope90, steep_land, lethal_land。
- beach_scarp：slope90, slope99, steep_land, land_width_m, lethal_land。
- beach_steep：slope90, steep_land, foreshore_gradient, land_width_m, lethal_land。

Bの傾向比較（各シナリオのTA*-S exact / A* - 1 の中央値[%]。人工は007の100/200m砂浜3種類に限定）：

- 漂着物なし・地形コストJ：実測-27.1717%、人工-15.6183%。増減の符号は同じ。
- 漂着物なし・登った高さ：実測-59.4397%、人工-29.8211%。増減の符号は同じ。
- 漂着物なし・エネルギー：実測-3.05301%、人工-6.10245%。増減の符号は同じ。
- 漂着物なし・経路長：実測1.90573%、人工-2.59091%。増減の符号は異なる。
- 漂着物なし・TA*-S：探索失敗0/96、lethalに接触した経路4/96。
- 漂着物なし・TA*-S exact：探索失敗0/96、lethalに接触した経路0/96。
- 漂着物あり・地形コストJ：実測-25.7576%、人工-15.6183%。増減の符号は同じ。
- 漂着物あり・登った高さ：実測-50.9409%、人工-29.8211%。増減の符号は同じ。
- 漂着物あり・エネルギー：実測-3.95924%、人工-6.10245%。増減の符号は同じ。
- 漂着物あり・経路長：実測2.83857%、人工-2.59091%。増減の符号は異なる。
- 漂着物あり・TA*-S：探索失敗0/96、lethalに接触した経路16/96。
- 漂着物あり・TA*-S exact：探索失敗0/96、lethalに接触した経路0/96。

Cの人工との比較は同じ100mだけで行う。以下はdJの中央値[%]であり、人工は007の砂浜3種類。200mの結果は比較対象がない追加実験として表に分けて示す。

- 漂着物なし・coarse R10 c10：実測4.73732%、人工6.59482%（実測の中央値が小さい）。
- 漂着物なし・coarse R15 c5：実測1.58031%、人工2.80683%（実測の中央値が小さい）。
- 漂着物なし・coarse R5 c10：実測11.0889%、人工7.78997%（実測の中央値が大きい）。
- 漂着物なし・coarse R5 c20：実測12.7281%、人工10.264%（実測の中央値が大きい）。
- 漂着物なし・online adaptive R15：実測8.67164%、人工6.14845%（実測の中央値が大きい）。
- 漂着物あり・coarse R10 c10：実測5.01755%、人工6.59482%（実測の中央値が小さい）。
- 漂着物あり・coarse R15 c5：実測1.99946%、人工2.80683%（実測の中央値が小さい）。
- 漂着物あり・coarse R5 c10：実測10.6484%、人工7.78997%（実測の中央値が大きい）。
- 漂着物あり・coarse R5 c20：実測11.9727%、人工10.264%（実測の中央値が大きい）。
- 漂着物あり・online adaptive R15：実測7.735%、人工6.14845%（実測の中央値が大きい）。
- C・漂着物なし・100m：オンライン失敗0/240、lethal接触0/240、dJ>25%は14/240。
- C・漂着物なし・200m：オンライン失敗0/240、lethal接触0/240、dJ>25%は55/240。
- C・漂着物あり・100m：オンライン失敗0/240、lethal接触0/240、dJ>25%は8/240。
- C・漂着物あり・200m：オンライン失敗0/240、lethal接触0/240、dJ>25%は40/240。

### 図から確認できる大きなdJのケース

`detour_01.png`（08PD03_-0005）では、実行軌跡が濃い急斜面帯に沿って海側へ大きく回り込み、折り返す部分が見える。`detour_04.png`（08OC96_-1412）でも、急斜面帯の付近で横方向へ進んで戻る軌跡がある。`detour_08.png`（08OC96_-0662）では、細い急斜面帯と追加障害物の周辺でoracleとは異なる経路を取っている。これらの図は移動距離の増加と整合する。

一方、`detour_10.png`（08OC97_-1678）はdJ=90.9986%に対してdL=-1.00907%であり、距離増加が主な説明にならない。実行軌跡はoracleより海側の傾斜帯に寄っている。経路上のmean_costもoracleの0.0348364から0.183397へ増えており、同程度の距離でも高コストの部分を通ることでJが増えた例である。

以上は保存された最終軌跡と地図からの観察であり、どの観測が個々の再計画を発火させたかという因果関係まで特定するものではない。


Dで探索・地点抽出・巡回が成功しなかった条件は0/864。失敗がある場合は集計表の一覧に掲載する。

Dの傾向比較：順番を決める基準以外の区間経路は同じ。提案のコスト差は terrain dir / euclid - 1 の中央値[%]。人工は008の200m砂浜3種類のみ。

- 漂着物なし・5地点：提案のコスト差は実測-0.0894205%、人工0%。傾向は人工では中央値が同点だったが、実測では低下した。 順番が変わった割合はeuclid対提案60.4167%、κ=0基準対提案33.3333%。
  euclidよりコストが改善しなかったケース（同点を含む）は19/48、エネルギーが増えたケースは18/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は32/48、エネルギーが増えたケースは11/48。
- 漂着物なし・8地点：提案のコスト差は実測-0.204345%、人工-0.0425097%。傾向は同じ。 順番が変わった割合はeuclid対提案81.25%、κ=0基準対提案50%。
  euclidよりコストが改善しなかったケース（同点を含む）は9/48、エネルギーが増えたケースは25/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は24/48、エネルギーが増えたケースは18/48。
- 漂着物なし・12地点：提案のコスト差は実測-0.802793%、人工-0.008622%。傾向は同じ。 順番が変わった割合はeuclid対提案87.5%、κ=0基準対提案54.1667%。
  euclidよりコストが改善しなかったケース（同点を含む）は6/48、エネルギーが増えたケースは21/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は22/48、エネルギーが増えたケースは18/48。
- 漂着物あり・5地点：提案のコスト差は実測-0.0457011%、人工0%。傾向は人工では中央値が同点だったが、実測では低下した。 順番が変わった割合はeuclid対提案54.1667%、κ=0基準対提案43.75%。
  euclidよりコストが改善しなかったケース（同点を含む）は22/48、エネルギーが増えたケースは14/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は27/48、エネルギーが増えたケースは13/48。
- 漂着物あり・8地点：提案のコスト差は実測-0.196597%、人工-0.0425097%。傾向は同じ。 順番が変わった割合はeuclid対提案75%、κ=0基準対提案43.75%。
  euclidよりコストが改善しなかったケース（同点を含む）は12/48、エネルギーが増えたケースは15/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は27/48、エネルギーが増えたケースは12/48。
- 漂着物あり・12地点：提案のコスト差は実測-0.226357%、人工-0.008622%。傾向は同じ。 順番が変わった割合はeuclid対提案68.75%、κ=0基準対提案43.75%。
  euclidよりコストが改善しなかったケース（同点を含む）は15/48、エネルギーが増えたケースは19/48。
  terrain symよりコストが改善しなかったケース（同点を含む）は27/48、エネルギーが増えたケースは16/48。
- 漂着物なしの非対称比率：中央値0.0346938、90%値0.0737371。κ=0監査値は中央値0.00112929、90%値0.0033659。パッチ別の値は表とCSVに掲載する。
- 漂着物ありの非対称比率：中央値0.0294119、90%値0.0679953。κ=0監査値は中央値0.00121653、90%値0.00327694。パッチ別の値は表とCSVに掲載する。

## 実験時間

- A：7.571607秒（0.126分）。
- B：103.873857秒（1.731分）。
- C：2195.572278秒（36.593分）。
- D：1664.994212秒（27.750分）。
- figures：10.595783秒（0.177分）。
- 合計：3982.970246秒（66.383分）、Poolワーカー5。計算時間にはこの環境での並列実行の負荷を含む。

## 実行コマンドとテスト出力全文

変更前：
```bash
cd conference
python3 -m tests.test_planners
```
```text
all planner tests passed
roll-aware tests passed
```

変更後（失敗があっても全モジュールを実行し、各終了コードを記録）：
```bash
cd conference
export MPLCONFIGDIR=/tmp/real-test-mpl XDG_CACHE_HOME=/tmp/real-test-cache OPENBLAS_NUM_THREADS=1
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_natural_terrain
python3 -m tests.test_online
python3 -m tests.test_planners
python3 -m tests.test_real_beach
python3 -m tests.test_risk_prior
python3 -m tests.test_tour
```
```text
$ python3 -m tests.test_beach_terrain
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
exit_code = 0
$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
exit_code = 0
$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
exit_code = 0
$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
exit_code = 0
$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
exit_code = 0
$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed
exit_code = 0
$ python3 -m tests.test_real_beach
all 60 patches loaded: shapes, 12/48 split, nearest-data fill passed
Traceback (most recent call last):
  File "/workspace/thesis_Bunker/conference/tests/test_real_beach.py", line 145, in <module>
    check()
  File "/workspace/thesis_Bunker/conference/tests/test_real_beach.py", line 58, in test_orientation
    not violations
AssertionError: supplied data violate requested orientation (name, sea-side mean, max mean in y=0..50m): [('08OC92_-1251', -2.7546429443359375, -0.7416749572753907), ('08PD13_00846', 0.234796142578125, 1.5667951965332032)]
08OB86_00292: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_01763: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB87_-0986: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_00916: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB88_-0083: 100/200m crops, deterministic clean/debris scenarios, reachability and forbidden masks passed
08OB86_00292: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_01763: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB87_-0986: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_00916: exact offline and coarse R5 c10 online safety passed, clean/debris
08OB88_-0083: exact offline and coarse R5 c10 online safety passed, clean/debris
real-beach test groups failed: 1
exit_code = 1
$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
exit_code = 0
$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed
exit_code = 0
Failed modules: ['tests.test_real_beach']
```

## 実験コマンドと表示した集計表全文

```bash
cd conference
MPLCONFIGDIR=/tmp/real-mpl XDG_CACHE_HOME=/tmp/real-cache OPENBLAS_NUM_THREADS=1 python3 experiments/real_beach.py
MPLCONFIGDIR=/tmp/real-mpl XDG_CACHE_HOME=/tmp/real-cache OPENBLAS_NUM_THREADS=1 python3 experiments/real_beach.py --summary-only
```

後者は保存済みの実行結果から集計表だけを生成する。Bのエネルギー検定も007と同じA*比の%を入力に使い、向きの監査とパッチ別のD集計を追加した。プランナーの実行結果を保存したoffline・online・tours・pair_costs等のCSVを再計算・補填していない。以下は最終的にスクリプトが表示した全文。

```text

A: supplied patches violating the requested mean-profile orientation (data unchanged)
        kind      split  sea_side_mean  front_profile_max
08OC92_-1251 validation       -2.75464          -0.741675
08PD13_00846       test       0.234796             1.5668

A: terrain statistics; medians over patches / artificial validation seeds
   source        group  slope50  slope90  slope99  steep_land  foreshore_gradient  land_width_m     rough  spectrum  lethal_land
     real         test  4.21039  10.1345  26.7953   0.0123618           0.0584174           102 0.0194237  -2.92683    0.0197579
     real   validation  3.95746   7.9584  20.1577  0.00500379           0.0489808           105 0.0183222  -2.91872    0.0134526
synthetic beach_gentle  3.52068   39.953  42.1333    0.138051           0.0432445          89.5 0.0193392  -2.93473     0.153638
synthetic  beach_scarp  3.87395  40.2853  42.7474    0.213943           0.0716077            16 0.0191346  -2.93929     0.229267
synthetic  beach_steep  3.88004  40.0925  42.2108    0.161693         0.000726161            29 0.0202472  -2.93737      0.17253

A: real-patch 10th/90th percentiles (all 60; descriptive, never used for tuning)
 quantile  slope50  slope90  slope99  steep_land  foreshore_gradient  land_width_m     rough  spectrum  lethal_land
      0.1  2.75287  6.79212  12.5004 0.000232859           0.0244064         45.05 0.0172014  -2.96355   0.00572208
      0.9  5.67988  19.1509  42.4572   0.0699469           0.0950714           151 0.0213053  -2.89536    0.0821946

A: artificial medians outside real 10..90% range
        kind             metric  synthetic_median    real_p10  real_p90
beach_gentle            slope90            39.953     6.79212   19.1509
beach_gentle         steep_land          0.138051 0.000232859 0.0699469
beach_gentle        lethal_land          0.153638  0.00572208 0.0821946
 beach_scarp            slope90           40.2853     6.79212   19.1509
 beach_scarp            slope99           42.7474     12.5004   42.4572
 beach_scarp         steep_land          0.213943 0.000232859 0.0699469
 beach_scarp       land_width_m                16       45.05       151
 beach_scarp        lethal_land          0.229267  0.00572208 0.0821946
 beach_steep            slope90           40.0925     6.79212   19.1509
 beach_steep         steep_land          0.161693 0.000232859 0.0699469
 beach_steep foreshore_gradient       0.000726161   0.0244064 0.0950714
 beach_steep       land_width_m                29       45.05       151
 beach_steep        lethal_land           0.17253  0.00572208 0.0821946

B: offline medians; energy only relative to A* [%]
 debris     planner  success  exposed  steep_len      cost    climb  energy_vs_A_pct  max_roll  p95_roll  roll_frac  length      time  touching
  False          A*        1   0.1875          0  0.164897  1.76472                0   10.5816   6.02599          0 120.556 0.0551539        18
  False       A*-HC        1        0          0  0.164897  1.76941                0   10.5816   6.08273          0 120.556  0.055915         0
  False         TA*        1        0          0 0.0691427 0.734457          0.19991   5.47814   2.76153          0 130.544  0.177591         0
  False       TA*-S        1        0          0 0.0770972 0.797206         -3.05301   6.16171   3.47634          0 125.772  0.503605         4
  False TA*-S exact        1        0          0 0.0770972 0.791136         -3.05301   6.16171   3.47634          0 125.772  0.495863         0
   True          A*        1 0.166667          0  0.189168  2.37331                0    11.652     6.815          0 120.575 0.0468328        16
   True       A*-HC        1        0          0  0.189157  2.37331                0    11.652   6.94237          0 120.575 0.0412018         0
   True         TA*        1        0          0 0.0873301  1.20275       -0.0283113   5.76131   3.31619          0 132.476  0.181269         0
   True       TA*-S        1        0          0  0.096429  1.21047         -3.99422   7.09029    4.0925          0 126.026  0.411443        16
   True TA*-S exact        1        0          0 0.0964437  1.21946         -3.95924   7.09029    4.0925          0 126.026  0.408033         0

B: paired two-sided Wilcoxon; Holm over ten tests
 debris          metric  n           p         r      delta      p_holm
  False       steep_len 96 7.62939e-06        -1          0 1.52588e-05
  False       mean_cost 96 1.78129e-17        -1 -0.0821114 1.78129e-16
  False           climb 96 1.78129e-17        -1   -1.01222 1.78129e-16
  False energy_vs_A_pct 96 5.98185e-08 -0.637027   -3.05301 2.39274e-07
  False       length_xy 96 1.95605e-06  0.559278    2.04497 5.86815e-06
   True       steep_len 96 3.05176e-05        -1          0 3.05176e-05
   True       mean_cost 96 1.78129e-17        -1    -0.0857 1.78129e-16
   True           climb 96 1.78129e-17        -1   -1.06424 1.78129e-16
   True energy_vs_A_pct 96 5.59754e-10 -0.728952   -3.95924 3.35852e-09
   True       length_xy 96  9.6216e-09  0.674399    2.93833  4.8108e-08

B: failures
Empty DataFrame
Columns: [kind, side_m, seed, debris, planner, reason]
Index: []

C: online medians and tails; dJ/dL/dE relative to exact oracle [%]
 debris             variant  success  exposed      dJ        dL         dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax     dL90   dLmax
  False      coarse R10 c10        1        0 6.12509 -0.778863 -0.0191441 -3.80268  6.35951     70    6.26492         0 21.3586 77.5942   4.7186 74.7113
  False       coarse R15 c5        1        0 2.73964 -0.432384   -0.21245 -3.08922  6.18321     65    6.02757         0 12.1449 188.325  2.57933   127.2
  False       coarse R5 c10        1        0 13.9149  -1.33531   0.374137 -3.19087  6.61184     78    6.13617         0 35.4668 103.945  4.74039 84.7788
  False       coarse R5 c20        1        0 17.5601  -2.17879  -0.358631  -4.1695   6.9356   80.5    6.65093         0 48.9955 97.5188  3.87675 87.5103
  False online adaptive R15        1        0 11.0538  -2.79064    -1.2285 -5.07991  6.60647   35.5    3.86786         0 30.7984 181.201 0.720601 85.9032
  False           oracle A*        1   0.1875 37.3097  -1.87006    3.14958        0  7.28106      1  0.0551539        18 58.8283  135.15  2.34686 4.14957
  False        oracle TA*-S        1        0       0         0          0 -3.05301  5.86993      1   0.495863         0       0       0        0       0
   True      coarse R10 c10        1        0 6.99788 -0.818629   0.162121 -3.61059  6.47148   84.5    7.16678         0 16.6554 95.2111  4.76809 73.0879
   True       coarse R15 c5        1        0 2.79388 -0.176721     0.0391 -2.89357  6.30339     77    6.94809         0 10.4814 178.528   6.2965 136.046
   True       coarse R5 c10        1        0 12.3597  -1.47832    0.43578 -3.72664  6.92055   86.5       7.29         0 22.9542 102.451  4.90089 81.7473
   True       coarse R5 c20        1        0 16.4335  -2.48683  -0.423323 -3.97981  7.39165   92.5    6.53338         0 41.8108 95.4595  5.91437 83.2404
   True online adaptive R15        1        0 11.5606  -3.15172  -0.960535 -5.13305  7.20614   34.5    4.17202         0 24.8284 61.7993 0.279374 62.5024
   True           oracle A*        1 0.166667  34.694  -2.76008    4.12248        0  8.44622      1  0.0468328        16 54.0672 111.069  1.84025 4.57115
   True        oracle TA*-S        1        0       0         0          0 -3.95924  6.27231      1   0.408033         0       0       0        0       0

C: per patch median dJ [%], debris=False
        kind  coarse R10 c10  coarse R15 c5  coarse R5 c10  coarse R5 c20  online adaptive R15  oracle A*  oracle TA*-S
08OB86_00292         4.35187         6.0957        16.6245         16.623              20.5995    33.2489             0
08OB87_-0986         2.62905        3.08505        11.9148         28.233              18.3131    49.1291             0
08OB87_01763         10.9506        1.74613        14.4856        15.2413               12.914     30.948             0
08OB88_-0083         7.00155        2.50757        21.8758        24.6392              13.2003    46.9131             0
08OB88_-1083         5.97607       0.693483        12.0947        23.2288              16.3189    44.8443             0
08OB88_00916         7.53508        3.47959        14.1918        13.4906              18.7029    34.6637             0
08OB89_-1151         6.65185        8.28418        10.8637        43.3615              12.3574    54.6621             0
08OB89_00598         3.87674        3.67133         11.431        13.0496              13.9833    18.5826             0
08OB89_01348         2.89151         2.4308        11.3914        16.0817              20.4505    47.8331             0
08OB89_02098         19.7658        1.21797        17.3117        31.6925              4.51399    53.2716             0
08OC80_-0586         9.29631        9.13084        16.1044        20.0903              19.4928    33.3407             0
08OC80_00163         8.76281        5.74078        10.5771        8.29937              12.8302    31.4713             0
08OC80_00913         6.42984         3.1111        10.3443        10.9484               7.6138    37.4373             0
08OC91_-0682         4.66127        1.89889        8.44869        15.8446              7.05119    42.6563             0
08OC91_-1932         12.7004        9.31502        20.6829        19.4704              13.3536    41.0854             0
08OC91_00067         8.00757        5.32569        10.9223        29.6382              12.7684    27.8535             0
08OC91_00817         6.74054        5.66401        7.84227        14.2849               10.167    39.1565             0
08OC91_01567         10.4199        2.29676        12.8665        16.0552               14.443    29.7467             0
08OC92_00998         6.42826         3.6083        10.2265        14.9573              24.2131    46.5052             0
08OC93_-1189          9.1914        4.96196         13.871        15.4431              11.3551    28.3258             0
08OC93_00060         1.46373       0.356961        20.2158        37.0511              6.05256    52.1777             0
08OC93_01310         4.71291        1.32968        13.6321        18.3066              22.2676    42.0077             0
08OC94_-1354         12.5096        8.79854        15.4878        15.8944              17.3578       25.1             0
08OC94_00145         7.52677        2.38676        11.8675        12.3143              10.2277    33.6319             0
08OC94_00895         5.97678        4.23981        12.4274        7.76185              15.0553    37.0016             0
08OC95_-0392         7.60508        3.75126         12.634         24.907              15.6017    35.0388             0
08OC95_-1142         16.2301        7.35229        18.6949        10.7547              15.3233    42.2147             0
08OC95_-1892         5.36844        5.14502        8.84075        19.0349              7.87577    38.4491             0
08OC95_00857         9.03293        11.1166         15.879        15.0387              10.7418    20.3146             0
08OC96_-0662         49.8174        27.1239          40.89        51.3936              50.0754    27.3904             0
08OC96_-1412         39.0911           32.6        65.8414        67.9479              53.3376    40.9852             0
08OC96_-2162         8.61567        0.13496        38.2179        43.8841              8.59351    28.7581             0
08OC96_01587         3.79062        2.04074         6.2401         24.365              17.9234    55.3448             0
08OC97_-0178         1.91198       0.935276        12.4527        43.5294              24.1173    24.9344             0
08OC97_-0928         8.14735        1.20328        9.49299        11.1738              16.7983    38.2818             0
08OC97_-1678         7.28135        8.27004        53.4328        14.1332              11.8269    72.2998             0
08OC97_01071         8.88799        8.00369         17.512        30.0654               17.326    44.6058             0
08OC98_-0281         12.0245        5.17653        16.4778        18.8437              14.3301    26.6377             0
08OC98_-1531         6.87186        1.91494        15.2897        12.6193              8.32875    43.1556             0
08OC98_00468         2.02526        1.05212        4.11057        9.29084              1.69941    30.0026             0
08OC98_01218         5.38481        3.98768        10.9183        12.7769              6.71145     33.581             0
08OC98_01968         12.5303        1.36881        21.3503        26.8576               28.491    38.3183             0
08OC99_-0768          14.839        3.51634        24.7974        28.6659              18.0784    53.7537             0
08OC99_00231         9.20186        5.70037        34.5455        43.6244              9.04269    44.4934             0
08OC99_00981         5.12095        3.20274        14.9427        24.0478              25.2018    40.6672             0
08OC99_01731         14.7151        9.67163        35.2254           37.4              7.14459    53.8804             0
08PD03_-0005         12.0245         94.614        23.4582        25.8815              91.0977     22.291             0
08PD13_00846          36.976        2.66535        43.2303          45.68              9.89169    93.9615             0

C: per patch median dJ [%], debris=True
        kind  coarse R10 c10  coarse R15 c5  coarse R5 c10  coarse R5 c20  online adaptive R15  oracle A*  oracle TA*-S
08OB86_00292         8.00183        1.83052        15.3774        17.5994              15.4432    35.0084             0
08OB87_-0986         4.76774        1.92983        10.0777        22.2993              20.8427    43.6105             0
08OB87_01763         8.30318        2.18308        11.9302        15.7177              11.8407    24.2611             0
08OB88_-0083         10.1224        4.24195        15.1537        26.0429              11.5803    36.4078             0
08OB88_-1083         5.76542        4.07333        9.87364        19.7623              17.0606    50.5819             0
08OB88_00916         8.11854        3.87849        13.0484        17.5525              18.1032    34.2326             0
08OB89_-1151         7.21748        8.69744        11.4976         43.747              9.47242    53.1288             0
08OB89_00598         4.34852        3.95997        9.87083         11.223              13.7894     24.417             0
08OB89_01348         3.29654        2.54071        15.4016        18.6306              16.4371    46.5875             0
08OB89_02098         5.49535        8.59422        4.47437        12.4783               6.7741    53.1102             0
08OC80_-0586         6.44029        3.82928        15.2466        18.0877               20.809     37.618             0
08OC80_00163         9.59713        6.01021        13.7704        13.3581              11.0386    49.5895             0
08OC80_00913         8.94637        6.33003        10.7404        11.6615              6.61911    34.5398             0
08OC91_-0682         5.70511        1.60569        8.34127        9.18016              4.76425    42.0797             0
08OC91_-1932         10.7515        11.5744        17.8702        23.7402              12.4937    33.1041             0
08OC91_00067         7.71741        6.86831        13.4947        33.5196              12.1666    32.5573             0
08OC91_00817         5.16234        1.63147        13.2496        14.9569              11.8922    35.2359             0
08OC91_01567         13.4607        3.00041        11.4821        13.6691               13.907    28.0418             0
08OC92_00998         10.0831        2.04471        15.1971        18.4634              16.6066    41.4048             0
08OC93_-1189         8.97648        6.30647        13.5384        12.8563              9.05953    25.5416             0
08OC93_00060         4.75533        3.50144        8.44244        19.0025              20.1943    36.7383             0
08OC93_01310          4.9016        1.09495        13.6627        14.8172              25.8818    47.0501             0
08OC94_-1354         8.09506        6.07102        12.2366        10.7865               9.9489    24.3036             0
08OC94_00145         5.99379        1.88994         9.9093        14.1938              10.3805     28.514             0
08OC94_00895         5.63483         4.9281        15.3662        9.05681              15.7364    43.1012             0
08OC95_-0392         7.98338         6.1205        14.4312        23.5984              18.5257    37.1943             0
08OC95_-1142         8.23191        3.80042        15.1557        11.4331               14.493    45.0714             0
08OC95_-1892         7.54711        4.49337         8.4844        12.6137              6.47351    35.6467             0
08OC95_00857         5.86671        9.17364        15.4646        22.9959               14.432    41.5766             0
08OC96_-0662         54.0711        27.2084        38.2171        54.5301              32.6009    30.9462             0
08OC96_-1412         43.0395        36.7345        64.3801        66.2779              51.3648    40.7528             0
08OC96_-2162         14.9136        1.62348        18.8987        25.3657              5.10061    18.1158             0
08OC96_01587         5.03564        1.84602        6.65918        23.4077              16.6086    58.5546             0
08OC97_-0178         2.27521        1.81398         8.7221        35.5412                16.19    21.0003             0
08OC97_-0928         14.4829        3.87425        14.3447        13.0479               20.224    40.4191             0
08OC97_-1678         6.60737        3.91097        8.24126        8.97094              4.43541    26.9808             0
08OC97_01071         2.89845       0.994719        10.6079        24.2477              13.9719     41.603             0
08OC98_-0281         13.8178        4.72544        16.3246        17.7477              13.3416    26.8631             0
08OC98_-1531         8.59026        2.81243        11.3979        11.5166              7.56249    34.4349             0
08OC98_00468         2.96208        1.26352        5.92504        10.5781             0.490994    30.3455             0
08OC98_01218          5.8138        3.99179        13.8561        12.9887              8.18403    33.6239             0
08OC98_01968         2.26939       0.268462        5.79935        18.4468              17.2622    31.6032             0
08OC99_-0768          14.728        3.10744        24.3166        26.0999              12.7483    41.8127             0
08OC99_00231         7.39832        3.34677         32.969        41.9871              8.11398    36.2566             0
08OC99_00981          8.5016        3.29505        15.9388        10.4263              1.54733    13.2758             0
08OC99_01731         15.6098        10.4927        33.8267        32.6767              6.81701    50.6746             0
08PD03_-0005         15.2491        90.1765        18.8604        23.2052              14.3892    21.5009             0
08PD13_00846         32.5916        4.49139        37.8896        41.1301              10.6783    79.7453             0

C: all dJ > 25% trajectories (largest ten plotted)
        kind  side_m  seed  debris             variant      dJ        dL  n_plans
08PD03_-0005     200     0   False       coarse R15 c5 188.325     127.2      279
08PD03_-0005     200     0   False online adaptive R15 181.201   85.9032      193
08PD03_-0005     200     0    True       coarse R15 c5 178.528   136.046      305
08OC96_-1412     100     0   False       coarse R5 c10 103.945   84.7788      140
08OC96_-1412     100     0    True       coarse R5 c10 102.451   81.7473      143
08OC96_-1412     100     0   False       coarse R5 c20 97.5188   87.5103      143
08OC96_-1412     100     0    True       coarse R5 c20 95.4595   83.2404      150
08OC96_-0662     200     0    True      coarse R10 c10 95.2111   73.0879      270
08OC96_-0662     200     0    True       coarse R5 c20 93.6686   30.3411      261
08OC97_-1678     200     0   False       coarse R5 c10 90.9986  -1.00907      135
08OC96_-0662     200     0   False online adaptive R15 85.1058   45.2793      147
08PD13_00846     200     0   False       coarse R5 c20 81.2685   8.53203      165
08OC96_-0662     200     0   False       coarse R5 c20 79.5043   33.9921      241
08OC96_-1412     100     0    True      coarse R10 c10 78.1477   69.8937      128
08OC96_-0662     200     0   False      coarse R10 c10 77.5942   71.2998      244
08PD13_00846     200     0   False       coarse R5 c10 76.1483   8.60175      157
08OC96_-2162     200     0   False       coarse R5 c20 75.3232   3.03225      141
08OC96_-1412     100     0   False      coarse R10 c10 71.8113   74.7113      129
08PD13_00846     200     0   False      coarse R10 c10 69.1138   6.74002      146
08OC99_00231     100     0   False       coarse R5 c20 68.6886   22.3756       95
08OC99_00231     100     0    True       coarse R5 c20 65.7007    21.659       93
08PD13_00846     200     0    True       coarse R5 c20  65.017   7.24329      170
08OC97_-0178     200     0   False       coarse R5 c20 64.7664   1.39633      158
08OC96_-2162     200     0   False       coarse R5 c10 62.8594   2.60961      143
08OC99_01731     200     0   False       coarse R5 c20 61.9118   42.4357      186
08OC96_-1412     100     0    True online adaptive R15 61.7993   62.5024       72
08OC96_-1412     100     0   False       coarse R15 c5   60.69     74.33      109
08OC96_-1412     100     0    True       coarse R15 c5 59.8205   70.9426      109
08OC96_-1412     100     0   False online adaptive R15 59.6282   70.9917       69
08PD13_00846     200     0    True       coarse R5 c10 58.9216   7.57523      169
08OC96_-0662     200     0    True       coarse R5 c10 58.8538   35.9752      232
08OC91_00067     200     0    True       coarse R5 c20 58.3668   8.29763      167
08OC97_-0178     200     0    True       coarse R5 c20 57.4547   6.36867      161
08OC96_-0662     200     0   False       coarse R5 c10 56.8524   38.9773      212
08OC99_01731     200     0   False       coarse R5 c10 55.7252   38.9981      193
08OC99_01731     200     0    True       coarse R5 c10 55.5688   37.6299      195
08OC96_-0662     200     0    True online adaptive R15 55.2908   11.9849      107
08OC93_00060     100     0   False       coarse R5 c20 54.1563   3.17364       68
08OC91_00067     200     0   False       coarse R5 c20 54.0992   10.1356      164
08OC96_-0662     200     0    True       coarse R15 c5 53.9641   36.5403      220
08PD13_00846     200     0    True      coarse R10 c10 53.8599   6.01337      159
08OC98_01968     200     0   False online adaptive R15 53.2912  -9.83662       34
08OC99_01731     200     0    True       coarse R5 c20 53.0873   36.4666      184
08OC96_-0662     200     0   False       coarse R15 c5 53.0602   38.6931      190
08OB89_-1151     100     0   False       coarse R5 c20 52.9953  -1.21004       64
08OB89_-1151     100     0    True       coarse R5 c20  52.984 -0.624158       69
08OC99_00231     100     0   False       coarse R5 c10 49.7278   12.3555       87
08OC99_00231     100     0    True       coarse R5 c10  49.193   11.0909       87
08OC96_-1412     200     0   False online adaptive R15  47.047   4.47373       62
08OC99_00981     200     0   False online adaptive R15 46.8698  -11.1258       77
08OC96_01587     200     0   False       coarse R5 c20 44.9957   -5.2132      126
08PD03_-0005     200     0   False       coarse R5 c20  43.778   2.81864      156
08OC99_00981     200     0   False       coarse R5 c20 43.5564  -10.7253      158
08OC96_01587     200     0    True       coarse R5 c20 43.0228  -2.77277      130
08OB88_-0083     200     0    True       coarse R5 c20 42.5452   -2.6143      160
08OB88_-0083     200     0   False       coarse R5 c20 42.4108  -7.02055      114
08OC98_01968     200     0   False       coarse R5 c20  42.232  -8.70279      143
08OB89_02098     200     0   False       coarse R5 c20 41.5621   17.9259      114
08OC96_-2162     200     0    True       coarse R5 c20 41.0764   2.52167      148
08OC96_-1412     200     0    True online adaptive R15 40.9303   2.36595       59
08OC99_-0768     200     0   False       coarse R5 c20  40.288  -2.80686      140
08OC93_01310     200     0    True online adaptive R15 39.2132  0.196057       51
08OC98_01968     200     0   False       coarse R5 c10 38.9655  -6.90838      157
08OC96_-1412     200     0   False       coarse R5 c20  38.377    2.7196      139
08OC96_-1412     200     0    True       coarse R5 c20 37.0963   1.37461      142
08PD03_-0005     200     0    True       coarse R5 c20  36.732   5.46006      167
08OC95_-0392     200     0   False       coarse R5 c20 36.6315 -0.991216       86
08OB88_-0083     200     0   False       coarse R5 c10 36.1481  -5.74185      113
08PD03_-0005     200     0   False       coarse R5 c10 35.5442   10.1221      159
08OC99_-0768     200     0   False       coarse R5 c10 35.3895  -3.31224      125
08OC96_01587     200     0   False online adaptive R15 34.5793  -6.39374       78
08OB89_-1151     200     0    True       coarse R5 c20 34.5101  -12.8307      110
08OB88_-1083     200     0   False       coarse R5 c20 34.4459  -2.49042      106
08OC95_-0392     200     0    True       coarse R5 c20 34.1782  -1.38242       89
08OB89_-1151     200     0   False       coarse R5 c20 33.7276  -11.5764      108
08OC96_01587     200     0    True online adaptive R15 32.2866  -4.90932       80
08OB86_00292     200     0   False online adaptive R15 32.0591   -5.7258       58
08OB87_-0986     100     0   False       coarse R5 c20 31.9486    -1.927       59
08OC94_-1354     200     0   False online adaptive R15 31.8824  -4.96279       70
08OC97_01071     200     0   False       coarse R5 c20 31.8097  -3.00693      117
08OC93_01310     200     0   False online adaptive R15 30.8944   -3.8192       24
08OB89_02098     200     0   False       coarse R5 c10 30.7198   9.68667      100
08OB89_01348     200     0   False online adaptive R15 30.7024  -7.45013       28
08OC99_-0768     200     0    True       coarse R5 c10 30.6949  -4.22925      147
08PD03_-0005     200     0    True       coarse R5 c10 30.6743   5.19063      167
08OC98_01968     200     0    True online adaptive R15 30.5219  -7.96861       44
08OC99_-0768     200     0    True       coarse R5 c20 30.2686  -4.68198      153
08OB87_-0986     200     0   False online adaptive R15 29.7519  -5.60092       62
08OC97_01071     200     0    True       coarse R5 c20 29.4696  -1.11157      120
08OB89_01348     200     0    True       coarse R5 c20 29.2938  -6.29136      117
08OB88_00916     200     0   False online adaptive R15 29.1899  -23.0875       20
08OC92_00998     200     0    True       coarse R5 c20 29.0592  -11.1234      131
08OB87_-0986     200     0    True       coarse R5 c20 29.0218  -6.99512      134
08OB87_-0986     200     0    True online adaptive R15 28.9942   -7.6564       65
08OC95_00857     200     0    True       coarse R5 c20 28.7356  -9.15239      144
08OC92_00998     100     0   False online adaptive R15 28.7216  0.138801       18
08OB89_02098     200     0   False      coarse R10 c10    28.6   10.4271       97
08OC97_-0178     200     0   False online adaptive R15  28.591  -4.61597       37
08OB88_00916     200     0    True online adaptive R15 28.4208  -5.71878       24
08OC97_01071     100     0   False       coarse R5 c20 28.3211  -2.20073       77
08OC80_-0586     200     0   False online adaptive R15 28.2999   -5.8013       40
08OB88_-1083     200     0    True       coarse R5 c20 27.8452   -1.6301      105
08OC96_-1412     200     0   False       coarse R5 c10 27.7379   4.31678      149
08OC95_-1142     200     0   False      coarse R10 c10 27.5257   3.84475      111
08OC94_-1354     200     0   False       coarse R5 c20 27.4779  -2.04992      142
08OC95_-1892     100     0   False       coarse R5 c20 27.2276  -1.92623       59
08OC99_-0768     200     0   False online adaptive R15 27.1263  -3.93477       56
08PD03_-0005     200     0    True online adaptive R15 26.7844   9.65037      100
08OC96_-1412     200     0    True       coarse R5 c10 26.3096   3.55301      150
08OC91_-1932     100     0   False       coarse R5 c20 26.2677  -12.6056       55
08OC99_01731     200     0    True      coarse R10 c10 26.1764   28.8332      182
08OC98_01968     200     0    True       coarse R5 c20 25.9792  -3.67064      154
08OC99_01731     200     0   False      coarse R10 c10 25.7655   29.2249      169
08OB89_01348     200     0   False       coarse R5 c20 25.6713  -6.36356      105
08OC94_-1354     200     0   False       coarse R5 c10 25.4115  -4.48592      142
08OC92_00998     200     0   False       coarse R5 c20 25.1457  -7.98336      121
08OB89_01348     200     0    True online adaptive R15 25.0396  -7.66009       34

C: failures
Empty DataFrame
Columns: [kind, side_m, seed, debris, variant, reason]
Index: []

D: tour metrics; relative cost and energy vs terrain dir [%]
 debris  n_goals      method  success  cost_rel_pct_median  cost_rel_pct_p90  energy_rel_pct_median  energy_rel_pct_p90  length_xy_median  length_xy_p90  climb_median  climb_p90  p95_roll_median  p95_roll_p90  steep_len_median  steep_len_p90
  False        5      euclid        1            0.0895024           1.85738                      0            0.382988           444.136         554.69       7.31058    11.0257          4.61738       6.37563                 0              0
  False        5 terrain dir        1                    0                 0                      0                   0           443.991        553.256       7.14801     10.918          4.55043       6.33725                 0              0
  False        5 terrain sym        1                    0          0.162003                      0            0.011172           444.541        552.958       7.14801    10.9103          4.56063       6.35274                 0              0
  False        8      euclid        1             0.204771            4.0888             -0.0318687             2.78131           517.203        610.862       8.88188    12.6702          4.85989       7.23013                 0              0
  False        8 terrain dir        1                    0                 0                      0                   0           518.529        620.913       8.51024     12.444          4.77367       6.98181                 0              0
  False        8 terrain sym        1           0.00563437          0.319597                      0           0.0234443           517.711         610.91       8.53606     12.444          4.90717       6.93856                 0              0
  False       12      euclid        1             0.809331            7.7539                      0             2.45681           575.576         699.38       10.4657     16.491           5.4289       7.21382                 0              0
  False       12 terrain dir        1                    0                 0                      0                   0           579.186        716.407       10.2196    14.7783          5.11799       6.67974                 0              0
  False       12 terrain sym        1           0.00719785          0.200474                      0            0.147169           579.659        697.997       10.1974    14.7783          5.07524       6.81804                 0              0
   True        5      euclid        1            0.0457225           2.74833                      0            0.716849           442.037        573.897       7.42867    14.3836          5.00882       8.07695                 0              0
   True        5 terrain dir        1                    0                 0                      0                   0           445.459        575.319        7.3838    14.2547          5.03199       8.07695                 0              0
   True        5 terrain sym        1                    0          0.188204                      0            0.081642           445.459        574.033        7.3838    14.2547          5.12329       8.19924                 0              0
   True        8      euclid        1             0.196984           1.95499                      0             1.14808           499.637        646.148       9.56856    18.4671          5.23992       8.19071                 0              0
   True        8 terrain dir        1                    0                 0                      0                   0           500.004        627.293       9.36244    16.9862          5.26133       7.53945                 0              0
   True        8 terrain sym        1                    0          0.188488                      0           0.0447747           500.234        627.738       9.35654    16.9469           5.2802       7.53945                 0              0
   True       12      euclid        1             0.226871            4.3584                      0             1.29756           574.328        697.954       10.9084    19.6353           5.4753       7.80386                 0              0
   True       12 terrain dir        1                    0                 0                      0                   0           572.118        711.495       10.6874    18.8563          5.36344       7.46778                 0              0
   True       12 terrain sym        1                    0          0.271687                      0           0.0108602           571.504        691.734       10.9191    18.8916          5.34495       7.31854                 0              0

D: per-patch directed cost relative to Euclidean ordering [%]
        kind  n_goals   clean_pct   debris_pct
08OB86_00292        5   -0.173514            0
08OB86_00292        8           0    -0.771063
08OB86_00292       12  -0.0575559     -1.95858
08OB87_-0986        5   -0.176569     -2.30367
08OB87_-0986        8    -1.90053            0
08OB87_-0986       12    -1.19606            0
08OB87_01763        5   -0.134907            0
08OB87_01763        8    -0.85372            0
08OB87_01763       12    -3.76893            0
08OB88_-0083        5    -1.55157            0
08OB88_-0083        8    -3.14975            0
08OB88_-0083       12    -5.56104    -0.317631
08OB88_-1083        5   -0.129906       -2.611
08OB88_-1083        8     -5.1282     -23.2133
08OB88_-1083       12     -20.302     -21.0714
08OB88_00916        5  -0.0179724    -0.950501
08OB88_00916        8    -9.03581      -1.0813
08OB88_00916       12    -12.6267     -5.41956
08OB89_-1151        5           0            0
08OB89_-1151        8   -0.170043     -2.15296
08OB89_-1151       12 -0.00586873     -1.93941
08OB89_00598        5           0      -0.1475
08OB89_00598        8    -2.82296     -2.64304
08OB89_00598       12    -1.60365     -2.38663
08OB89_01348        5   -0.115455            0
08OB89_01348        8   -0.177416    -0.392763
08OB89_01348       12   -0.154513  -0.00352413
08OB89_02098        5 -0.00735991            0
08OB89_02098        8   -0.933467   -0.0233383
08OB89_02098       12    -1.77542 -0.000791827
08OC80_-0586        5           0   -0.0976689
08OC80_-0586        8           0            0
08OC80_-0586       12    -3.16886    -0.295293
08OC80_00163        5   -0.130219    -0.225277
08OC80_00163        8    -2.92358     -1.69655
08OC80_00163       12           0   -0.0178414
08OC80_00913        5  -0.0213155    -0.175967
08OC80_00913        8    -2.56442    -0.202251
08OC80_00913       12           0            0
08OC91_-0682        5           0     -2.87918
08OC91_-0682        8   -0.231274     -1.63849
08OC91_-0682       12  -0.0277923     -1.27484
08OC91_-1932        5    -4.94166     -4.06474
08OC91_-1932        8   -0.343472    -0.630347
08OC91_-1932       12   -0.220785    -0.499606
08OC91_00067        5    -1.21867   -0.0573618
08OC91_00067        8    -1.88695    -0.212706
08OC91_00067       12           0    -0.345466
08OC91_00817        5           0            0
08OC91_00817        8           0            0
08OC91_00817       12 -0.00852589            0
08OC91_01567        5     -1.7048            0
08OC91_01567        8           0    -0.210084
08OC91_01567       12  -0.0748399    -0.589164
08OC92_00998        5  -0.0536632            0
08OC92_00998        8    -1.48615     -0.17658
08OC92_00998       12    -4.52096            0
08OC93_-1189        5   -0.225663            0
08OC93_-1189        8   -0.302888    -0.180687
08OC93_-1189       12    -1.67215     -0.21827
08OC93_00060        5           0   -0.0184692
08OC93_00060        8  -0.0621422    -0.124262
08OC93_00060       12   -0.359551            0
08OC93_01310        5   -0.916774            0
08OC93_01310        8   -0.300131            0
08OC93_01310       12    -2.46476     -2.83953
08OC94_-1354        5    -0.14414    -0.317191
08OC94_-1354        8    -0.11513    -0.181742
08OC94_-1354       12   -0.392337            0
08OC94_00145        5           0            0
08OC94_00145        8   -0.103055    -0.151582
08OC94_00145       12    -1.00061     -5.69753
08OC94_00895        5           0            0
08OC94_00895        8   -0.170932    -0.521022
08OC94_00895       12   -0.210279    -0.163099
08OC95_-0392        5           0            0
08OC95_-0392        8           0    -0.233712
08OC95_-0392       12           0    -0.234445
08OC95_-1142        5   -0.256833    -0.192122
08OC95_-1142        8   -0.162726            0
08OC95_-1142       12    -2.61664     -2.14404
08OC95_-1892        5           0   -0.0527181
08OC95_-1892        8           0            0
08OC95_-1892       12   -0.739674      -2.3774
08OC95_00857        5   -0.150236            0
08OC95_00857        8    -11.4786      -14.272
08OC95_00857       12    -14.5606     -3.63353
08OC96_-0662        5    -3.66804    -0.038684
08OC96_-0662        8    -3.40456    -0.414641
08OC96_-0662       12    -2.60345     -1.20597
08OC96_-1412        5   -0.718714    -0.889514
08OC96_-1412        8    -1.53862   -0.0160198
08OC96_-1412       12    -1.74277     -2.21648
08OC96_-2162        5   -0.102931      -2.8172
08OC96_-2162        8           0            0
08OC96_-2162       12     -0.2286            0
08OC96_01587        5           0    -0.341566
08OC96_01587        8    -6.71612    -0.187047
08OC96_01587       12    -1.77696            0
08OC97_-0178        5           0            0
08OC97_-0178        8   -0.563064            0
08OC97_-0178       12   -0.225695     -6.17236
08OC97_-0928        5  -0.0759097    -0.290183
08OC97_-0928        8  -0.0672142    -0.227804
08OC97_-0928       12   -0.239078            0
08OC97_-1678        5     -2.2716    -0.346818
08OC97_-1678        8    -5.60537    -0.157576
08OC97_-1678       12    -3.33979    -0.238365
08OC97_01071        5   -0.147587    -0.244718
08OC97_01071        8   -0.137288     -1.81624
08OC97_01071       12    -10.7991     -1.87337
08OC98_-0281        5           0            0
08OC98_-0281        8   -0.151073            0
08OC98_-0281       12   -0.110934            0
08OC98_-1531        5           0            0
08OC98_-1531        8    -0.16874            0
08OC98_-1531       12  -0.0589847   -0.0530856
08OC98_00468        5           0            0
08OC98_00468        8  -0.0352392     -1.57322
08OC98_00468       12   -0.865911    -0.473083
08OC98_01218        5           0     -3.45459
08OC98_01218        8  -0.0613244     -1.77738
08OC98_01218       12  -0.0108872   -0.0297482
08OC98_01968        5           0            0
08OC98_01968        8   -0.123365   -0.0440313
08OC98_01968       12   -0.107606            0
08OC99_-0768        5   -0.185031            0
08OC99_-0768        8  -0.0700449    -0.341812
08OC99_-0768       12           0   -0.0144786
08OC99_00231        5    -0.85333    -0.202948
08OC99_00231        8           0    -0.190943
08OC99_00231       12    -1.24965            0
08OC99_00981        5           0     -2.61367
08OC99_00981        8   -0.589161     -1.02521
08OC99_00981       12    -4.46814     -8.61137
08OC99_01731        5    -4.67766     -1.70172
08OC99_01731        8    -1.74734    -0.043571
08OC99_01731       12    -13.1119            0
08PD03_-0005        5           0     -4.33981
08PD03_-0005        8           0     -16.9212
08PD03_-0005       12           0            0
08PD13_00846        5    -2.09938            0
08PD13_00846        8    -2.71785    -0.333431
08PD13_00846       12     -4.0424   -0.0259739

D: per-patch asymmetry |Cij-Cji|/(Cij+Cji)
        kind  debris     median       p90
08OB86_00292   False  0.0399051 0.0704568
08OB86_00292    True  0.0391419 0.0690123
08OB87_-0986   False  0.0361942 0.0697447
08OB87_-0986    True  0.0351065 0.0716093
08OB87_01763   False  0.0414415 0.0559969
08OB87_01763    True  0.0252444 0.0491967
08OB88_-0083   False   0.052798 0.0835427
08OB88_-0083    True  0.0432648 0.0753197
08OB88_-1083   False  0.0428156 0.0700437
08OB88_-1083    True  0.0466868 0.0735816
08OB88_00916   False  0.0413519 0.0792154
08OB88_00916    True  0.0376248 0.0711012
08OB89_-1151   False  0.0423856 0.0656608
08OB89_-1151    True   0.036234 0.0591381
08OB89_00598   False  0.0276603 0.0604539
08OB89_00598    True  0.0174613 0.0573437
08OB89_01348   False  0.0214055 0.0504203
08OB89_01348    True  0.0179048 0.0446456
08OB89_02098   False  0.0280611 0.0563497
08OB89_02098    True   0.029542 0.0503828
08OC80_-0586   False  0.0299858 0.0490138
08OC80_-0586    True  0.0286838 0.0430488
08OC80_00163   False  0.0255267 0.0661161
08OC80_00163    True  0.0293946 0.0500918
08OC80_00913   False  0.0213929 0.0470882
08OC80_00913    True  0.0170935 0.0433389
08OC91_-0682   False  0.0282461  0.070457
08OC91_-0682    True  0.0366843  0.060708
08OC91_-1932   False  0.0407786 0.0623092
08OC91_-1932    True  0.0238648 0.0602673
08OC91_00067   False  0.0406394 0.0747511
08OC91_00067    True  0.0404989 0.0771767
08OC91_00817   False  0.0343971 0.0703023
08OC91_00817    True   0.025467 0.0440692
08OC91_01567   False  0.0439323 0.0827438
08OC91_01567    True  0.0298833 0.0755558
08OC92_00998   False  0.0244389 0.0513358
08OC92_00998    True  0.0201116 0.0375053
08OC93_-1189   False  0.0144538 0.0347556
08OC93_-1189    True 0.00960727 0.0259021
08OC93_00060   False  0.0289626 0.0559562
08OC93_00060    True  0.0262188 0.0531978
08OC93_01310   False   0.039136 0.0796547
08OC93_01310    True  0.0507202 0.0798951
08OC94_-1354   False  0.0508315 0.0828919
08OC94_-1354    True  0.0250624 0.0659362
08OC94_00145   False  0.0355007 0.0558934
08OC94_00145    True  0.0306455 0.0866538
08OC94_00895   False  0.0223051 0.0564485
08OC94_00895    True  0.0153794 0.0441425
08OC95_-0392   False  0.0297509 0.0609906
08OC95_-0392    True  0.0344338 0.0592162
08OC95_-1142   False  0.0328109 0.0566679
08OC95_-1142    True  0.0181591 0.0401138
08OC95_-1892   False  0.0370911 0.0632501
08OC95_-1892    True  0.0271761 0.0419388
08OC95_00857   False  0.0621728 0.0963313
08OC95_00857    True   0.051867 0.0781143
08OC96_-0662   False  0.0174935 0.0632027
08OC96_-0662    True  0.0398395 0.0675569
08OC96_-1412   False   0.059636 0.0951684
08OC96_-1412    True  0.0579377 0.0985158
08OC96_-2162   False  0.0351755  0.073827
08OC96_-2162    True  0.0182887 0.0512482
08OC96_01587   False  0.0253071  0.071856
08OC96_01587    True  0.0158079 0.0426329
08OC97_-0178   False   0.046276  0.064484
08OC97_-0178    True  0.0418338 0.0575143
08OC97_-0928   False  0.0327198 0.0595022
08OC97_-0928    True  0.0377415 0.0528164
08OC97_-1678   False  0.0315205 0.0685713
08OC97_-1678    True  0.0327537 0.0663133
08OC97_01071   False   0.054341 0.0818153
08OC97_01071    True  0.0518809 0.0845653
08OC98_-0281   False  0.0638638 0.0912914
08OC98_-0281    True  0.0256421 0.0662779
08OC98_-1531   False  0.0393423 0.0727704
08OC98_-1531    True  0.0261633 0.0662109
08OC98_00468   False  0.0208738 0.0383837
08OC98_00468    True  0.0274652 0.0497081
08OC98_01218   False  0.0562658 0.0842769
08OC98_01218    True  0.0343615 0.0756781
08OC98_01968   False  0.0500154 0.0944902
08OC98_01968    True  0.0498503 0.0971934
08OC99_-0768   False  0.0349683 0.0622353
08OC99_-0768    True  0.0360202 0.0731131
08OC99_00231   False  0.0453588 0.0903464
08OC99_00231    True  0.0454173 0.0968241
08OC99_00981   False  0.0544567 0.0921005
08OC99_00981    True  0.0544648 0.0917196
08OC99_01731   False  0.0466253 0.0907955
08OC99_01731    True   0.039244 0.0648541
08PD03_-0005   False 0.00727212  0.023068
08PD03_-0005    True  0.0088517 0.0230226
08PD13_00846   False  0.0209143 0.0500373
08PD13_00846    True  0.0290948 0.0581155

D: terrain dir relative to euclid ordering [%]
 debris  n_goals  dir_vs_euclid_pct_median
  False        5                -0.0894205
  False        8                 -0.204345
  False       12                 -0.802793
   True        5                -0.0457011
   True        8                 -0.196597
   True       12                 -0.226357

D: changed orders [%]
 debris  n_goals  euclid_vs_dir_pct  sym_vs_dir_pct
  False        5            60.4167         33.3333
  False        8              81.25              50
  False       12               87.5         54.1667
   True        5            54.1667           43.75
   True        8                 75           43.75
   True       12              68.75           43.75

D: pair-matrix asymmetry; zero-kappa audit included
 debris  pairs    median       p90  zero_kappa_median  zero_kappa_p90
  False   3744 0.0346938 0.0737371         0.00112929       0.0033659
   True   3744 0.0294119 0.0679953         0.00121653      0.00327694

D: paired two-sided Wilcoxon; Holm over all twelve comparisons
 debris  n_goals                 comparison  n           p  r  median_cost_difference      p_holm
  False        5      euclid vs terrain dir 48 3.72529e-09  1                 1.43242 2.98023e-08
  False        5 terrain sym vs terrain dir 48 3.05176e-05  1                       0 3.05176e-05
  False        8      euclid vs terrain dir 48 3.63798e-12  1                 4.49381 4.00178e-11
  False        8 terrain sym vs terrain dir 48 1.19209e-07  1                 0.11558 5.96046e-07
  False       12      euclid vs terrain dir 48 4.54747e-13  1                 16.9943 5.45697e-12
  False       12 terrain sym vs terrain dir 48 2.98023e-08  1                0.159125 2.08616e-07
   True        5      euclid vs terrain dir 48 2.98023e-08  1                0.841234 2.08616e-07
   True        5 terrain sym vs terrain dir 48 9.53674e-07  1                       0  3.8147e-06
   True        8      euclid vs terrain dir 48 2.91038e-11  1                 4.55478 2.91038e-10
   True        8 terrain sym vs terrain dir 48 9.53674e-07  1                       0  3.8147e-06
   True       12      euclid vs terrain dir 48 2.32831e-10  1                 5.14253 2.09548e-09
   True       12 terrain sym vs terrain dir 48 9.53674e-07  1                       0  3.8147e-06

D: matrix / Held-Karp time [s]; full 13-point matrices reused by all prefixes
 debris  n_goals      method  matrix_median  matrix_max  solve_median   solve_max
  False        5      euclid    0.000118823  0.00525873   0.000410628  0.00124118
  False        5 terrain dir        47.1957     82.6925   0.000340076  0.00045676
  False        5 terrain sym        45.3652     76.9288   0.000351295    0.018741
  False        8      euclid    0.000118823  0.00525873    0.00661933   0.0272225
  False        8 terrain dir        47.1957     82.6925    0.00593634   0.0285428
  False        8 terrain sym        45.3652     76.9288    0.00596253   0.0228715
  False       12      euclid    0.000118823  0.00525873       0.28005    0.863867
  False       12 terrain dir        47.1957     82.6925      0.268425     0.77889
  False       12 terrain sym        45.3652     76.9288      0.274244       0.828
   True        5      euclid    0.000127325 0.000509274   0.000425643  0.00104058
   True        5 terrain dir        35.0583     63.9055   0.000340508 0.000461292
   True        5 terrain sym         34.797     58.4928   0.000348925 0.000598243
   True        8      euclid    0.000127325 0.000509274     0.0062838   0.0259742
   True        8 terrain dir        35.0583     63.9055    0.00589119   0.0254407
   True        8 terrain sym         34.797     58.4928    0.00594224    0.028385
   True       12      euclid    0.000127325 0.000509274      0.271418    0.994424
   True       12 terrain dir        35.0583     63.9055      0.269346    0.734017
   True       12 terrain sym         34.797     58.4928      0.256899    0.550317

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
 debris             variant  success  exposed      dJ        dL         dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax     dL90   dLmax
  False      coarse R10 c10        1        0 4.73732  -1.85644  -0.944532 -3.07583  6.17469   54.5    2.88041         0 13.5794 71.8113  2.34258 74.7113
  False       coarse R15 c5        1        0 1.58031 -0.475676  -0.355848 -2.12301   5.9641     49    2.96776         0 12.4485   60.69  1.98713   74.33
  False       coarse R5 c10        1        0 11.0889  -1.53271  -0.384442 -2.83054  6.48053   58.5    2.77742         0 21.8259 103.945  4.32761 84.7788
  False       coarse R5 c20        1        0 12.7281  -2.37789  -0.704036 -3.26837  6.50644     61    2.95504         0 29.4094 97.5188  3.74441 87.5103
  False online adaptive R15        1        0 8.67164   -2.7077   -1.61895 -4.58008  6.33267     26     1.8628         0 16.5766 59.6282  0.47838 70.9917
  False           oracle A*        1   0.0625  30.913  -1.75646    1.32936        0  7.05017      1  0.0337117         3 52.7878 67.9138  2.16857 4.14957
  False        oracle TA*-S        1        0       0         0          0 -1.31164  5.85177      1    0.35319         0       0       0        0       0
   True      coarse R10 c10        1        0 5.01755  -1.22896  -0.134608 -3.68108  6.30129   61.5    2.81391         0 12.4401 78.1477  3.87636 69.8937
   True       coarse R15 c5        1        0 1.99946 -0.331006 0.00904054 -1.81766   6.0367     57    2.98787         0 7.79473 59.8205  3.94396 70.9426
   True       coarse R5 c10        1        0 10.6484  -1.56987  -0.155672 -3.32404  6.53632     67     2.8691         0 17.0745 102.451  3.86592 81.7473
   True       coarse R5 c20        1        0 11.9727  -3.04763   -1.02212 -3.97981  6.86934     67    2.83825         0 21.4505 95.4595  3.08351 83.2404
   True online adaptive R15        1        0   7.735  -3.00735   -1.25534 -4.40269  6.44167     27    1.85717         0 16.2242 61.7993 0.633518 62.5024
   True           oracle A*        1   0.0625 29.1722  -2.10231    2.99342        0   7.8188      1  0.0232637         3 46.0814 65.1659   1.7939 4.57115
   True        oracle TA*-S        1        0       0         0          0 -2.90642  5.98945      1   0.209745         0       0       0        0       0

C: real 200m subset (additional experiment)
 debris             variant  success  exposed      dJ         dL        dE     dE_A  slope95  plans  plan_time  touching    dJ90   dJmax     dL90   dLmax
  False      coarse R10 c10        1        0 7.41614  -0.293031  0.569472 -4.12043  6.53159  105.5     14.194         0 23.4493 77.5942  6.21392 71.2998
  False       coarse R15 c5        1        0 2.97849 -0.0615244  0.238156 -4.20802  6.54374     91    12.5901         0 11.0496 188.325  4.99325   127.2
  False       coarse R5 c10        1        0 18.2522   -1.21783  0.574954 -3.74771  7.35501  113.5    14.9096         0 43.9934 90.9986  5.60227 38.9981
  False       coarse R5 c20        1        0 22.8191   -2.00727  0.304528 -4.48649  7.59558  121.5    14.5296         0  56.443 81.2685  4.68218 42.4357
  False online adaptive R15        1        0 19.7332   -3.65652 -0.815005  -5.4662  7.37899     46    11.6142         0 38.2665 181.201 0.723606 85.9032
  False           oracle A*        1   0.3125  44.201   -1.97016   4.73181        0  8.83524      1   0.098091        15 68.5827  135.15  2.37265 3.87724
  False        oracle TA*-S        1        0       0          0         0 -4.51729  6.09524      1    0.76035         0       0       0        0       0
   True      coarse R10 c10        1        0 9.02879  0.0053343   1.28192 -3.48461  6.94286  120.5    20.6245         0 18.6761 95.2111  5.37433 73.0879
   True       coarse R15 c5        1        0    4.18  -0.119815  0.297198  -4.1241  6.70173    115    21.1664         0 11.6938 178.528  7.02235 136.046
   True       coarse R5 c10        1        0 15.9397   -1.04472  0.661298 -4.22691  7.30585    130    21.7807         0  27.619 58.9216  4.98601 37.6299
   True       coarse R5 c20        1        0 21.0543   -2.25583  0.524139 -4.37478  8.07237  133.5    19.9004         0 46.0421 93.6686  6.38715 36.4666
   True online adaptive R15        1        0 17.7899      -3.27 -0.710954 -5.83562  7.68038     50    13.6115         0 29.4525 55.2908 0.218378 11.9849
   True           oracle A*        1 0.270833 39.0119   -2.91685   5.53265        0  9.64662      1   0.101606        13 66.3419 111.069  1.96872  3.2981
   True        oracle TA*-S        1        0       0          0         0  -5.2426   6.5622      1    0.78161         0       0       0        0       0

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
      A      7.57161
      B      103.874
      C      2195.57
      D      1664.99
figures      10.5958
Total wall time [s]: 3982.970246; workers=5; resume=False
Source: 静岡県「VIRTUAL SHIZUOKA 静岡県 中西部沿岸 点群データ」ALB グリッドデータ（0.5m）
https://www.geospatial.jp/ckan/dataset/shizuoka-2025-pointcloud-alb
ライセンス：CC BY 4.0 / ODbL。このフォルダのデータは、上のデータを加工して作成したものです。
Caveats: nearest-data fill affects spectra; zero-kappa greedy smoothing need not be symmetric; closed-tour endpoint elevation potentials cancel.
```

## 追加したファイル

- `conference/tapp/real_beach.py`
- `conference/experiments/real_beach.py`
- `conference/tests/test_real_beach.py`
- `conference/results/real_beach/artificial_outside.csv`
- `conference/results/real_beach/detour_01.png`
- `conference/results/real_beach/detour_02.png`
- `conference/results/real_beach/detour_03.png`
- `conference/results/real_beach/detour_04.png`
- `conference/results/real_beach/detour_05.png`
- `conference/results/real_beach/detour_06.png`
- `conference/results/real_beach/detour_07.png`
- `conference/results/real_beach/detour_08.png`
- `conference/results/real_beach/detour_09.png`
- `conference/results/real_beach/detour_10.png`
- `conference/results/real_beach/detours.csv`
- `conference/results/real_beach/metadata.json`
- `conference/results/real_beach/offline.csv`
- `conference/results/real_beach/offline_tests.csv`
- `conference/results/real_beach/online.csv`
- `conference/results/real_beach/orientation_violations.csv`
- `conference/results/real_beach/pair_costs.csv`
- `conference/results/real_beach/patch_asymmetry.csv`
- `conference/results/real_beach/real_beach_log.txt`
- `conference/results/real_beach/run_progress_log.txt`
- `conference/results/real_beach/runtime.json`
- `conference/results/real_beach/statistics.csv`
- `conference/results/real_beach/tests_log.txt`
- `conference/results/real_beach/tour_example_debris_0.png`
- `conference/results/real_beach/tour_example_debris_1.png`
- `conference/results/real_beach/tour_patch_summary.csv`
- `conference/results/real_beach/tour_tests.csv`
- `conference/results/real_beach/tours.csv`
- `conference/results/real_beach/REPORT_ja.md`
