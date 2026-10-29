# 複数地点の地形考慮巡回：実装・検証報告

最新取得した `realtime-map`（`fc042bb`）を土台に、`codex/multi-goal-tour` で実装した。既存ファイルは変更していない。既存の追跡済み `conference/` ファイルを作業開始時の SHA-256 と照合した。

## 実装

- `conference/tapp/directional.py`：8近傍・角抜け禁止の向き付き A* / Dijkstra、親配列からの復元、登坂項付き区間積分、exact LOS によるコスト非増加の貪欲平滑化、個別区間の計画。コストはマス単位で、登坂項は `κ × 正の標高差 / RESOLUTION`。`κ = 1 / Robot().rolling_coeff` を固定しており、調整していない。
- `conference/tapp/tour.py`：到達可能で基地・他地点から5m以上離れた地点の再現可能な抽出、各始点1回の Dijkstra と各終点への平滑化による行列、ユークリッド行列、最大12地点の厳密 Held–Karp、基地へ戻る区間列。`order` は基地を先頭に1回だけ含み、`tour_legs` が帰還区間を追加する。同点は絶対差 `1e-12` 以下を浮動小数点の同点として辞書順で選ぶ。
- `conference/experiments/multi_goal_tour.py`：指定された全5地形・100/200m・シード0〜9、各12地点の先頭5/8/12地点、指定4方法を `multiprocessing.Pool` で実行。各シナリオの13地点の行列を再利用する。最初の3方法は同じ向き付き行列の保存済み区間経路を走行し、順番だけを比較する。第4方法は提案と同じ順番でκ=0の保存済み区間を走行する。全巡回を `evaluate` で評価し、全線分の接触セルを監査する。Holm補正は6比較全体に適用する。
- `conference/tests/test_tour.py`：既存A*とのκ=0一致20格子、10格子の全単純経路総当たり、全終点への Dijkstra/A* 一致、登り下りの差、既存の標本化との3,000区間の一致、平滑化の非増加性、各2〜8地点につき30非対称行列の全順列照合、辞書順の同点・到達不能・探索上限、地点抽出、砂浜3種類100mの5地点全区間の安全性と個別A*/Dijkstra計画・行列の経路およびコストの一致を確認する。全経路の総当たりは3×3を使う。全辺が正なので、全単純経路の列挙で最短路の独立した総当たり検証になる。

## 解釈上の注意・できなかったこと

指示どおり、区間積分は既存の `_line_cells(a, b)` をそのまま使い、始点から終点へ貪欲に平滑化する。個別の `plan_leg` は許可されている Dijkstra の結果を使い、行列と同じ経路になる。既存の TA* とκ=0の**格子最短コスト**が一致することは別の A* テストで確認する。平滑化後の経路頂点列について既存の A* ディスパッチャーとの同一性を主張するものではない。

κ=0の**格子辺コスト**は対称だが、方向ごとに行う貪欲平滑化は逆向きで同じ近道を選ぶ保証がなく、既存の標本化も半整数丸め境界で逆向きの標本セルが異なる場合がある。このため、指定の `terrain sym` は「κ=0で区間を計算する基準」の名前として用い、平滑化済み行列の完全な対称性は仮定しない。実測したκ=0の非対称監査表も追加した。結果を対称に見せるための平均化や、既存の標本化の変更はしていない。

同じ幾何経路を逆に走ったとき、登坂項の差は `κ(z_goal-z_start)/RESOLUTION` という端点のポテンシャルであり、閉じた巡回では総和が相殺される。したがって改善を「非対称性だけによる効果」とは解釈できない。登坂項は標高変動を避ける対称成分も含み、平滑化に伴う方向依存もある。順番が違う割合は指定どおりの列に加え、単なる巡回の逆転を同一視した割合も表示した。

コストの最適化は、事前に計算・平滑化した区間の行列に対して厳密であり、連続地形上の全経路に対する大域最適性は主張しない。`segment_cost_dir` の登坂は既存の丸め標本、`metrics.evaluate` のエネルギーは既存の補間・再標本化で評価されるため、コスト最小とエネルギー最小は一致を保証しない。エネルギーの表は指定どおり%のみで、CSVには再解析用の既存評価値を保存する。計算時間はこの環境での実測値で、Poolの並列実行と一部テストの同時実行による負荷を含む。

## 実測結果の読み取り

完走実験の経過時間は 1378.423218 秒（22.974 分）。100 シナリオ、1200 巡回、全巡回の lethal 接触セルは 0。既存の追跡済み conference ファイル 210 個は SHA-256 が一致した。

5地点：提案のコスト差の中央値は euclid 比 -0.0683934%、terrain sym 比 0%。改善しなかった件数（差の絶対値1e-9以下の同点を含む）はそれぞれ 45/100、52/100。エネルギーが euclid より増えたケースは 34/100、terrain sym より増えたケースは 30/100。

同じ提案順序のκ=0区間に対して、提案の物理κ区間の実測コストが小さいケースは 100/100、逆に大きいケースは 0/100。

8地点：提案のコスト差の中央値は euclid 比 -0.0760716%、terrain sym 比 -0.00881593%。改善しなかった件数（差の絶対値1e-9以下の同点を含む）はそれぞれ 40/100、49/100。エネルギーが euclid より増えたケースは 30/100、terrain sym より増えたケースは 23/100。

同じ提案順序のκ=0区間に対して、提案の物理κ区間の実測コストが小さいケースは 99/100、逆に大きいケースは 1/100。

12地点：提案のコスト差の中央値は euclid 比 -0.0402532%、terrain sym 比 -0.00558394%。改善しなかった件数（差の絶対値1e-9以下の同点を含む）はそれぞれ 40/100、49/100。エネルギーが euclid より増えたケースは 28/100、terrain sym より増えたケースは 23/100。

同じ提案順序のκ=0区間に対して、提案の物理κ区間の実測コストが小さいケースは 100/100、逆に大きいケースは 0/100。

非対称の比率 beach_gentle：中央値 0.0141717、90%値 0.0461061。κ=0平滑化行列の同じ比率は中央値 0.0012178、90%値 0.00361925、最大 0.0125764。

非対称の比率 beach_scarp：中央値 0.0145391、90%値 0.0377016。κ=0平滑化行列の同じ比率は中央値 0.00125578、90%値 0.00367369、最大 0.0138251。

非対称の比率 beach_steep：中央値 0.0127149、90%値 0.0393145。κ=0平滑化行列の同じ比率は中央値 0.00120719、90%値 0.00363397、最大 0.0124562。

非対称の比率 hills：中央値 0.0253877、90%値 0.0665779。κ=0平滑化行列の同じ比率は中央値 0.00118922、90%値 0.00358815、最大 0.0185848。

非対称の比率 rolling：中央値 0.0188748、90%値 0.0544984。κ=0平滑化行列の同じ比率は中央値 0.00097343、90%値 0.00302485、最大 0.0193987。

緩い砂浜の非対称中央値は 0.0141717。全5種類の中央値のうち小さい順で 2/5 位だった。完全な平地のシナリオは指定の5種類には含まれておらず、平地でのゼロ性を実験結果として推定・補填していない。

200m・12地点（基地を含め13点）のκ=0行列構築は、中央値 44.747168 秒、最大 98.091464 秒。小さい地点数でもこの同じ行列を再利用するため、5地点専用の独立した構築時間ではない。

200m・12地点（基地を含め13点）の物理κ行列構築は、中央値 46.633040 秒、最大 100.691044 秒。小さい地点数でもこの同じ行列を再利用するため、5地点専用の独立した構築時間ではない。


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

変更後（各コマンドの終了コード0を確認）：
```bash
cd conference
export MPLCONFIGDIR=/tmp/tour-test-mpl XDG_CACHE_HOME=/tmp/tour-test-cache OPENBLAS_NUM_THREADS=1
python3 -m tests.test_beach_terrain
python3 -m tests.test_collision
python3 -m tests.test_dstar
python3 -m tests.test_natural_terrain
python3 -m tests.test_online
python3 -m tests.test_planners
python3 -m tests.test_risk_prior
python3 -m tests.test_tour
# 個別A*との経路照合を追加後
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
$ python3 -m tests.test_collision
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
$ python3 -m tests.test_dstar
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
$ python3 -m tests.test_natural_terrain
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
$ python3 -m tests.test_online
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
$ python3 -m tests.test_planners
all planner tests passed
roll-aware tests passed
$ python3 -m tests.test_risk_prior
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
$ python3 -m tests.test_tour
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual planning (kappa=0 and physical)
all multi-goal tour tests passed
$ python3 -m tests.test_tour # expanded individual A*/Dijkstra path equivalence checks
kappa=0 agrees with legacy A* (20 random 25x25 grids)
directed A*/Dijkstra agree with all-simple-path exhaustive oracle (10 grids); unreachable/corners/budget passed
uphill/downhill identity, segment units and nonincreasing exact smoothing passed
Held-Karp matches all permutations (30 asymmetric matrices at each of 2..8 destinations); ties/closure passed
beach_gentle: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_steep: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
beach_scarp: reproducible reachable separated waypoints; all directed legs safe; matrix agrees with individual A*/Dijkstra planning (kappa=0 and physical)
all multi-goal tour tests passed
```


## 実験コマンドと表示した集計表全文
```bash
cd conference
MPLCONFIGDIR=/tmp/tour-mpl XDG_CACHE_HOME=/tmp/tour-cache OPENBLAS_NUM_THREADS=1 python3 experiments/multi_goal_tour.py
```
```text
kappa = 6.66666666667; w = 8; workers = 5; scenarios = 100; tours = 1200
Experiment wall time [s]: 1378.423218
Matrix times are for 13 points, reused by the 5/8/12-goal prefixes; solve times exclude matrix construction.
Relative values are 100*(method/terrain dir - 1); energy is displayed only as percent.

Tour metrics (length/climb/steep length [m], roll [deg])
 n_goals                   method  cost_rel_pct_median  cost_rel_pct_p90  energy_rel_pct_median  energy_rel_pct_p90  length_xy_median  length_xy_p90  climb_median  climb_p90  p95_roll_median  p95_roll_p90  steep_len_median  steep_len_p90
       5                   euclid            0.0684402          0.429191                      0            0.211462           314.229        515.871       7.33954    17.3169          5.23688       8.87573                 0              0
       5              terrain sym                    0          0.219941                      0            0.139872           314.531        515.871        7.3036    17.2684          4.98369       8.79998                 0              0
       5              terrain dir                    0                 0                      0                   0           314.704        515.871       7.29104    17.2905          4.86454       8.98689                 0              0
       5 terrain dir / TA*-S legs             0.823955           1.27077              0.0145032            0.775731           315.249        514.148       7.56591    17.8078          4.85868       9.02488                 0              0
       8                   euclid            0.0761296          0.451523                      0             0.37942           361.184        580.082       8.74648    20.3883          5.17342       9.36752                 0              0
       8              terrain sym            0.0088169          0.245283                      0            0.244651           360.856        580.466       8.69279    19.9907          5.02553        9.3469                 0              0
       8              terrain dir                    0                 0                      0                   0           360.549        580.432       8.69279     19.821          5.01997        9.6005                 0              0
       8 terrain dir / TA*-S legs             0.769831            1.1764              0.0244865             0.51348            356.78         578.28       9.03429    20.9657          5.05605       8.93866                 0              0
      12                   euclid            0.0402697          0.705719                      0            0.302296           432.291         697.85       10.0099    23.9555          5.65728       9.78761                 0              0
      12              terrain sym           0.00558429          0.184897                      0             0.21379           432.223        699.543        9.9791    23.9044          5.56069       9.79344                 0              0
      12              terrain dir                    0                 0                      0                   0            434.96        699.483       10.0028    23.8999          5.62574       9.74519                 0              0
      12 terrain dir / TA*-S legs             0.780073           1.08633                0.10429            0.652549           431.621        694.873       10.3428    24.5161          5.53544       9.46311                 0              0

Directed cost relative to Euclidean ordering [%]
        kind  n_goals  dir_vs_euclid_cost_pct_median
beach_gentle        5                     -0.0214107
 beach_steep        5                    -0.00816771
 beach_scarp        5                     -0.0393066
     rolling        5                       -0.11537
       hills        5                      -0.106308
beach_gentle        8                      -0.152963
 beach_steep        8                              0
 beach_scarp        8                     -0.0353961
     rolling        8                      -0.127691
       hills        8                      -0.142638
beach_gentle       12                     -0.0368465
 beach_steep       12                     -0.0230749
 beach_scarp       12                              0
     rolling       12                     -0.0782947
       hills       12                      -0.140357

Changed orders [%]; cycle columns identify a tour with its reversal
        kind  n_goals  euclid_vs_dir_pct  sym_vs_dir_pct  euclid_vs_dir_cycle_pct  sym_vs_dir_cycle_pct
beach_gentle        5                 50              35                       10                     5
 beach_steep        5                 50              65                        5                     0
 beach_scarp        5                 50              35                       30                     0
     rolling        5                 60              40                       20                    10
       hills        5                 65              65                       25                    10
beach_gentle        8                 75              35                       20                     5
 beach_steep        8                 30              30                       10                     5
 beach_scarp        8                 50              75                       20                     0
     rolling        8                 65              35                       25                    10
       hills        8                 80              80                       40                    20
beach_gentle       12                 60              45                       20                    10
 beach_steep       12                 55              55                       10                    15
 beach_scarp       12                 45              40                       25                     0
     rolling       12                 70              55                       30                     5
       hills       12                 70              60                       40                    10

Changed orders overall [%]
 n_goals  euclid_vs_dir_pct  sym_vs_dir_pct
       5                 55              48
       8                 60              51
      12                 60              51

Pair-matrix asymmetry |Cij-Cji|/(Cij+Cji)
        kind  pairs    median       p90
beach_gentle   1560 0.0141717 0.0461061
 beach_scarp   1560 0.0145391 0.0377016
 beach_steep   1560 0.0127149 0.0393145
       hills   1560 0.0253877 0.0665779
     rolling   1560 0.0188748 0.0544984

Zero-kappa smoothing/sampling asymmetry audit
        kind     median        p90   maximum
beach_gentle  0.0012178 0.00361925 0.0125764
 beach_scarp 0.00125578 0.00367369 0.0138251
 beach_steep 0.00120719 0.00363397 0.0124562
       hills 0.00118922 0.00358815 0.0185848
     rolling 0.00097343 0.00302485 0.0193987

Paired two-sided Wilcoxon; Holm correction over all six comparisons
 n_goals                 comparison   n           p  r  median_cost_difference      p_holm
       5      euclid vs terrain dir 100 1.10762e-10  1                  0.9414 3.32285e-10
       5 terrain sym vs terrain dir 100 7.10543e-15  1                       0 4.26326e-14
       8      euclid vs terrain dir 100 1.62956e-11  1                 1.51878 8.14778e-11
       8 terrain sym vs terrain dir 100 5.14528e-10  1                0.179425 1.02906e-09
      12      euclid vs terrain dir 100 1.62956e-11  1                 1.01233 8.14778e-11
      12 terrain sym vs terrain dir 100 5.14528e-10  1               0.0753459 1.02906e-09

Matrix computation time [s] (200 m / 12 goals included)
 side_m      method  matrix_13points_median_s  matrix_13points_max_s
    100      euclid               6.02285e-05            0.000421828
    100 terrain sym                   14.0266                 28.867
    100 terrain dir                   16.4988                 30.995
    200      euclid                8.7223e-05            0.000350946
    200 terrain sym                   44.7472                98.0915
    200 terrain dir                    46.633                100.691

Held-Karp solve time [s]
 side_m  n_goals      method    median_s       max_s
    100        5      euclid 0.000378891   0.0187466
    100        5 terrain dir 0.000319599  0.00441277
    100        5 terrain sym 0.000323445  0.00044827
    100        8      euclid  0.00644176   0.0373088
    100        8 terrain dir   0.0058996   0.0419506
    100        8 terrain sym  0.00596189   0.0287056
    100       12      euclid    0.283692    0.600991
    100       12 terrain dir    0.277459     1.40082
    100       12 terrain sym    0.278047    0.627254
    200        5      euclid 0.000390249   0.0047276
    200        5 terrain dir   0.0003176 0.000444293
    200        5 terrain sym 0.000321041 0.000469355
    200        8      euclid  0.00663605    0.103213
    200        8 terrain dir  0.00588801   0.0322524
    200        8 terrain sym  0.00587297    0.028394
    200       12      euclid    0.277423     1.10085
    200       12 terrain dir    0.264283    0.596771
    200       12 terrain sym    0.264095    0.784475

Safety: maximum lethal cells per complete tour = 0
Closed-tour endpoint elevation potentials cancel: improvements cannot be attributed solely to matrix asymmetry.
```


## 追加したファイル

- `conference/tapp/directional.py`

- `conference/tapp/tour.py`

- `conference/experiments/multi_goal_tour.py`

- `conference/tests/test_tour.py`

- `conference/results/multi_goal_tour/metadata.json`

- `conference/results/multi_goal_tour/multi_goal_tour_log.txt`

- `conference/results/multi_goal_tour/pair_costs.csv`

- `conference/results/multi_goal_tour/paired_tests.csv`

- `conference/results/multi_goal_tour/run_progress_log.txt`

- `conference/results/multi_goal_tour/scenario_times.csv`

- `conference/results/multi_goal_tour/tests_log.txt`

- `conference/results/multi_goal_tour/tour_example.png`

- `conference/results/multi_goal_tour/tours.csv`

- `conference/results/multi_goal_tour/REPORT_ja.md`


`tour_example.png` は指定の beach_steep・200m・シード0・12地点の図。CSVには個々の巡回順序と地点、評価値、行列・探索の実測時間、および各対の実測コストを保存した。
