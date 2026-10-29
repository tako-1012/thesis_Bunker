# 砂浜・丘の地形と正確な計画（タスク007）

最新取得時点の realtime-map（f8a592d）を土台に、codex/beach-terrain で実装しました。
既存ファイルは一切変更していません。全既存 conference ファイルのSHA-256を照合しました。

## 実装

- tapp/beach_terrain.py: BEACH_TYPES と generate_beach を追加しました。
  xが沿岸、yが海から陸です。砂浜は前浜・満潮線・バーム・後浜・陸端の立上がりで構成し、
  波長50m以上のフラクタル的な1次元雑音で岸位置・勾配・バーム高を変えます。
  カスプ、断続する浜崖、足跡等の微小起伏、流木、Golombek–Rapp則の小さな岩・ごみを加えます。
  water は最終標高<0、wet は 0以上かつ満潮位未満です。陸端・流木・浜崖等の診断マスクも返します。
- rolling は既存 generate_natural をそのまま呼び、標高と岩が完全一致することを検査しました。
  hills はmountainと同じフラクタル・水滴侵食・崩れを使い、中央値の正規化を9.5度としました。
  これは最初に定めた値で、検証後も変更していません。
- tapp/beach_scenario.py: build_beach を追加し、指定された2000+種類番号のSeedSequence名前空間を使います。
  TraversabilityMap(elev, rock|water, robot, weights) で水も膨張し、既存のコスト式は変更しません。
  開始・目標の候補から水・禁止セル・陸側の帯を除き、左右の帯から抽出して可解性を確認します。
- tapp/exact_planners.py: run_planner_exact を追加しました。TA*-Sの平滑化だけ正確なLOSを使い、
  その他のプランナーは既存run_plannerにそのまま委譲します。
- experiments/beach_terrain.py: 検証・テストの統計、旧/正確TA*-Sの比較、横傾き、
  A*比エネルギー、7種類のオンライン比較、対応検定、上側分位値、失敗一覧を出力します。
  エネルギーの表示表はA*に対する%のみです。再計算可能性のためCSVには元の評価量も記録しています。
- tests/test_beach_terrain.py: 決定性、断面の順序と勾配、浜崖の実測出現率、
  シナリオ、委譲したプランナーの経路一致、正確な平滑化・オンライン安全性を検査します。

## 有限地図への近似と検証の経過

前浜勾配・満潮位・バームの高さ等は指示された範囲で乱数から作ります。
バームは満潮位+0.3mより高くし、浜崖の高さも収まるよう下限を条件付けています。
沿岸方向の高さ・勾配の変動は許容範囲でクリップします。
有限の50m図面に前浜とバームを収めるため、バーム位置を陸端より海側に制限し、
満潮線までの前浜と、その上部のバーム肩を区別した折れ線断面にしました。
非常に狭い図面では前浜自体が圧縮される場合もあります。したがって全サイズで全ての典型断面値が厳密に両立するとは主張しません。
100mの検証シードについて、実測平均勾配が指定範囲（±20%）であることをテストしています。

最初の検証で、負の後浜勾配を長距離延長すると、200m図面の内陸が再び水面下になりました。
後浜が満潮位+0.15mより下がらない平坦部へ移るよう修正し、陸端の数値的な立上がりも半セル海側から始めました。
また流木は一様に選ぶ面積密度を離散本数へ丸め、100mで5〜20本の範囲を保つようにしました。
初期の実測値は validation_initial.csv とログ、修正後は validation.csv とvalidation_log.txtに保存しています。
修正は検証用シード100〜104だけで確認し、その後の生成器のASTが変わっていないことを照合しました。
テスト用シードの結果を見た再調整はしていません。

海岸の細い物体や低い段差は0.5m格子で表現しています。浜崖の物理的な断面は45度より急でも、
高さが低い場合、中央差分で得るセルの傾斜が45度に達しないことがあります。
scarp_coverage は実際の傾斜45度以上のマスが現れた沿岸行の割合であり、
要求した浜崖の長さの割合をそのまま実測値に置き換えてはいません。

## 目標未達も含む地形統計

直接100〜104を入力した100mの浜崖検査は中央値46.5%でした。
一方、シナリオの別SeedSequenceを通した検証の100mでは28%で、下限30%に未達でした。
検証用50m beach_gentle の wet は39.73%で上限25%を超え、陸端を除く急斜面率も約1.4754%で上限1%を超えました。
テスト用でも50m beach_gentle のwetと急斜面率、200m beach_scarpの浜崖出現率が目標を外れました。
都合のよいシードの統計だけを採用していません。水割合と丘の傾斜目標は検証シナリオの中央値で範囲内でした。

検証シナリオの中央値（割合は0〜1）:

```text
                        water       wet  land_steep  scarp_coverage   slope50     steep
kind         side_m                                                                    
beach_gentle 50      0.179000  0.397300    0.014754          0.0000  3.498644  0.162300
             100     0.179450  0.115100    0.007459          0.0000  3.530285  0.185000
             200     0.179794  0.076731    0.003497          0.0000  3.359721  0.113275
beach_scarp  50      0.179500  0.099500    0.048530          0.5300  6.398543  0.185500
             100     0.179925  0.075700    0.019383          0.2800  4.764526  0.143375
             200     0.180350  0.029656    0.010768          0.3675  4.817032  0.175394
beach_steep  50      0.179700  0.069100    0.014375          0.0000  5.838146  0.170700
             100     0.180825  0.037650    0.005150          0.0000  4.946635  0.136525
             200     0.180469  0.021950    0.003627          0.0000  4.738500  0.132512
hills        50      0.000000  0.000000    0.022400          0.0000  9.495962  0.022400
             100     0.000000  0.000000    0.020175          0.0000  9.469364  0.020175
             200     0.000000  0.000000    0.023931          0.0000  9.468390  0.023931
rolling      50      0.000000  0.000000    0.000100          0.0000  5.500000  0.000100
             100     0.000000  0.000000    0.000200          0.0000  5.500000  0.000200
             200     0.000000  0.000000    0.000700          0.0000  5.500000  0.000700
```

## 計画と再計画の結果

オフライン750計画はすべて成功しました。
旧TA*-Sは150経路中2件が通行禁止マスに触れましたが、TA*-S exact は0件でした。
全体の経路長・地形コスト・横傾きの中央値は同じでしたが、修正された個別ケースでは次の差がありました。
横傾きそのものを最小化するアルゴリズムではないので、安全化しても横傾きが必ず下がるとは主張しません。

```text
 kind  side_m  seed  length_xy_old  mean_cost_old  max_roll_old  p95_roll_old  roll_frac_old  lethal_cells_old  length_xy_exact  mean_cost_exact  max_roll_exact  p95_roll_exact  roll_frac_exact  lethal_cells_exact
hills     100     8      79.823211       0.224148     14.304478      9.149927            0.0               1.0        79.674666         0.225708       14.570441        9.136566              0.0                 0.0
hills     200     7     200.145170       0.243521     12.443654      8.162392            0.0               1.0       199.945907         0.244560       14.731225        8.355002              0.0                 0.0
```

Cのoracle TA*-Sには、修論向けに新設した正確な平滑化版を使いました。
Bには論文と同じ旧TA*-SとTA*-S exactを別々に残してあります。
オンライン500走行はすべて目標に到達し、正確な接触判定で禁止マスへの接触は0件でした。
乾いた砂と濡れた砂の摩擦・沈下等の追加コストは導入せず、差は既存の傾斜・凸凹コストだけです。

## dJ>25%の図の点検

大きなdJは10走行・5ケースでした。最大dJの大きいケースから最大20ケースを選ぶ規則で、今回は全5ケースを描画・目視確認しました。
個別の数値と観察はdetour_inspection_ja.mdに記録しています。

- beach_scarp/50m/seed2: 理想は早い段階で海側へ移る一方、オンラインは浜崖の陸側を進み、右端近くを大きく回り込む形でした。
- beach_scarp/50m/seed4: 理想は陸側、オンラインは浜崖の海側を通り、違う側から禁止領域を避けています。
- beach_scarp/50m/seed6 と100m/seed9: 理想より陸側を通る経路が目立ちます。距離差よりdJ差が大きいので、
  地形コスト差も寄与しており、大回りだけが全原因ではありません。
- hills/50m/seed3: 理想は谷の北側を通り、オンラインは南側の谷へ回り込む形です。

これらは図と評価量に基づく観察・仮説で、観測履歴を使った意思決定の因果的な証明ではありません。
実在の日本の海岸データによる較正、砂の支持力、潮の時間変化、動く人、複数地点巡回、論文の修正は実施していません。

## 実行コマンドとテスト出力全文

変更前:

```bash
cd conference && python3 -m tests.test_planners
```

```text
all planner tests passed
roll-aware tests passed
```

変更後:

```bash
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online && python3 -m tests.test_dstar && python3 -m tests.test_risk_prior && python3 -m tests.test_collision && python3 -m tests.test_natural_terrain && python3 -m tests.test_beach_terrain
```

```text
all planner tests passed
roll-aware tests passed
regression passed (ridge/100 m, seeds 0 and 7)
perfect prior passed (all terrain kinds/50 m/seed 0)
coarse prior passed (shape, no rocks, partial blocks, noise, robot/weights, edges)
prior policies passed (hard/soft/ignore, sensing overrides, cell-specific triggers)
safety passed (60 trajectories: five online variants and constrained oracle)
all online tests passed
static agreement passed (20 random grids, tolerance 1e-9)
dynamic agreement passed (5 seeds x 20 updates, tolerance 1e-9)
corner constraints, cost decreases, unreachable/reopened routes and ties passed
task 001 regression passed (ridge soft and hills hard, search omitted)
D* Lite safety passed (20 trajectories, normal and every-step replanning)
error handling and fixed/adaptive-with-map prior handling passed
all D* Lite tests passed
coarse elevation/refactor passed (16 terrain/cell/noise combinations)
calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)
empty-bin fallback and boundary assignment passed
risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)
risk-prior safety passed (40 trajectories, 40 successful; 20 m cells, R=5/15 m, lambda=0/1)
all risk-prior tests passed
segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)
corner-grazing reproduction and exact rejection passed
legacy online and smoothing regressions passed
exact online safety passed (41 trajectories, A* and D* Lite)
all collision tests passed
natural generation determinism, distinct seeds, shape and finite values passed
pre-erosion radial spectrum passed: [-3.5227452123825955, -3.4854938900090673, -3.5147015961346426, -3.469782545726739, -3.4636674128050786]
rock area law: 0.4 0.02703765778384137 0.02660688949938067
rock area law: 0.6 0.014010959187524073 0.013724330217025335
rock area law: 1.0 0.003425544099666588 0.003651617375374042
natural scenarios and exact online safety passed (15 trajectories)
experiment oracle contact audit passed (both reference planners)
all natural-terrain tests passed
beach determinism, shapes, finite values, water/wet and unchanged rolling passed
averaged sea/wet/dry/inland profiles and foreshore slopes passed (validation seeds)
scarp 45-degree coverage passed: [np.float64(0.465), np.float64(0.615), np.float64(0.0), np.float64(0.16), np.float64(0.555)]
beach scenarios, delegated planner equality and exact smoothing passed (15 scenarios)
exact beach online safety passed (9 trajectories)
all beach-terrain tests passed
```

実験:

```bash
cd conference && python3 experiments/beach_terrain.py
```

正常終了しました。実験前の動作確認には検証用シード100のみを使い、その結果を本実験に混ぜていません。
MPLCONFIGDIR と XDG_CACHE_HOME は/tmp内に指定し、実行依存ライブラリは追加していません。
以下は実測時間です。generation/statistics/offline/onlineのsumは並列ワーカーの経過時間の和であり、
段階の壁時計時間ではありません。図の目視確認・報告書作成・テスト時間は含めません。

```json
{
  "experiments_s": 308.5087509969999,
  "total_s": 312.47037981299945,
  "workers": 5,
  "generation_sum_s": 169.14308025400533,
  "statistics_sum_s": 173.13423830498505,
  "offline_sum_s": 274.36240242599524,
  "online_sum_s": 1088.686882964008
}
```

## 実験スクリプトが表示した全集計表（そのまま）

```text
A: terrain statistics (medians, validation and test shown separately)
                                   water       wet  landward  driftwood  scarp_coverage  land_steep   slope50    slope90    slope99     steep      rock     rough  spectrum_before  spectrum_after  redraws  generation_time
split      kind         side_m                                                                                                                                                                                              
test       beach_gentle 50      0.179400  0.255900   0.14000   0.001400          0.0000    0.014695  3.905293  39.842280  42.610616  0.150000  0.001700  0.014895        -2.876166       -2.954389      0.0         0.066269
                        100     0.179525  0.163138   0.13750   0.001250          0.0000    0.007135  3.428998  39.311941  42.209402  0.142375  0.001712  0.016731        -2.978402       -3.028430      0.0         0.250729
                        200     0.179684  0.074825   0.14375   0.001372          0.0000    0.003663  3.447258  39.601268  42.523967  0.146263  0.002356  0.018654        -2.927599       -2.941757      0.0         1.702792
           beach_scarp  50      0.179550  0.130450   0.16000   0.000700          0.4900    0.040797  6.566525  40.163994  43.892016  0.189850  0.002200  0.020404        -2.900205       -2.951563      0.0         0.086726
                        100     0.180150  0.065387   0.15000   0.001462          0.6050    0.019730  4.859224  39.589790  42.654491  0.164388  0.002000  0.017082        -2.936547       -3.006093      0.0         0.294711
                        200     0.180575  0.026450   0.13750   0.001569          0.0400    0.009796  4.756258  39.568161  42.641389  0.144656  0.002000  0.018741        -2.931254       -2.942111      0.0         1.069733
           beach_steep  50      0.179800  0.091250   0.15000   0.001000          0.0000    0.014808  6.941045  39.380096  42.224461  0.160000  0.001150  0.017648        -2.884935       -2.949993      0.0         0.063439
                        100     0.180050  0.052912   0.14500   0.001488          0.0000    0.007026  5.762511  39.415082  42.294316  0.150375  0.001850  0.019373        -2.970063       -3.020949      0.0         0.277310
                        200     0.180675  0.022875   0.16125   0.001206          0.0000    0.003733  4.708876  39.867511  42.277504  0.173644  0.002075  0.018192        -2.938172       -2.941450      0.0         1.173069
           hills        50      0.000000  0.000000   0.00000   0.000000          0.0000    0.024250  9.498420  19.059649  28.328278  0.024250  0.000000  0.030069        -5.077484       -3.816923      0.0         0.150923
                        100     0.000000  0.000000   0.00000   0.000000          0.0000    0.023838  9.480432  19.145928  28.137075  0.023838  0.000000  0.028950        -4.783210       -3.789022      0.0         0.632782
                        200     0.000000  0.000000   0.00000   0.000000          0.0000    0.024322  9.465232  18.968066  28.169594  0.024322  0.000000  0.029098        -4.617177       -3.735488      0.0         3.932763
           rolling      50      0.000000  0.000000   0.00000   0.000000          0.0000    0.000100  5.500000  10.259622  14.594873  0.000100  0.000000  0.012104        -5.037976       -4.438006      0.0         0.069703
                        100     0.000000  0.000000   0.00000   0.000000          0.0000    0.000288  5.500000  10.323956  15.045250  0.000288  0.000000  0.011938        -4.770848       -4.241949      0.0         0.215081
                        200     0.000000  0.000000   0.00000   0.000000          0.0000    0.000556  5.500000  10.369043  15.195606  0.000556  0.000000  0.011576        -4.615132       -4.140560      0.0         1.109191
validation beach_gentle 50      0.179000  0.397300   0.15000   0.001900          0.0000    0.014754  3.498644  39.190006  41.163671  0.162300  0.002100  0.011089        -2.860497       -2.951643      0.0         0.032781
                        100     0.179450  0.115100   0.18000   0.001850          0.0000    0.007459  3.530285  40.167358  42.072860  0.185000  0.002025  0.017337        -2.967942       -3.029717      0.0         0.183540
                        200     0.179794  0.076731   0.11250   0.001350          0.0000    0.003497  3.359721  38.592010  41.983524  0.113275  0.001412  0.017381        -2.921782       -2.934733      0.0         0.888639
           beach_scarp  50      0.179500  0.099500   0.16000   0.001300          0.5300    0.048530  6.398543  39.144981  46.575398  0.185500  0.002100  0.015975        -2.915590       -2.967888      0.0         0.056463
                        100     0.179925  0.075700   0.13000   0.001875          0.2800    0.019383  4.764526  39.883090  42.620998  0.143375  0.001900  0.015081        -2.944788       -3.003553      0.0         0.231681
                        200     0.180350  0.029656   0.17000   0.001625          0.3675    0.010768  4.817032  39.903333  42.547382  0.175394  0.001944  0.017885        -2.929480       -2.939287      0.0         1.045275
           beach_steep  50      0.179700  0.069100   0.16000   0.001000          0.0000    0.014375  5.838146  39.716416  41.892793  0.170700  0.001800  0.014492        -2.888309       -2.951875      0.0         0.114935
                        100     0.180825  0.037650   0.13500   0.001275          0.0000    0.005150  4.946635  39.877416  42.021958  0.136525  0.001825  0.014542        -2.979128       -3.016378      0.0         0.165752
                        200     0.180469  0.021950   0.13000   0.001412          0.0000    0.003627  4.738500  39.559207  42.062685  0.132512  0.001938  0.018775        -2.933746       -2.937375      0.0         1.651572
           hills        50      0.000000  0.000000   0.00000   0.000000          0.0000    0.022400  9.495962  19.511059  27.194191  0.022400  0.000000  0.029849        -4.955367       -3.832889      0.0         0.151739
                        100     0.000000  0.000000   0.00000   0.000000          0.0000    0.020175  9.469364  18.384157  27.597357  0.020175  0.000000  0.028846        -4.718502       -3.729350      0.0         0.655263
                        200     0.000000  0.000000   0.00000   0.000000          0.0000    0.023931  9.468390  18.834970  28.328883  0.023931  0.000000  0.029018        -4.616487       -3.699264      0.0         4.679240
           rolling      50      0.000000  0.000000   0.00000   0.000000          0.0000    0.000100  5.500000  10.260376  14.781823  0.000100  0.000000  0.012498        -5.043889       -4.483769      0.0         0.046629
                        100     0.000000  0.000000   0.00000   0.000000          0.0000    0.000200  5.500000  10.221291  14.654026  0.000200  0.000000  0.011703        -4.747368       -4.197564      0.0         0.160102
                        200     0.000000  0.000000   0.00000   0.000000          0.0000    0.000700  5.500000  10.272093  15.149416  0.000700  0.000000  0.011416        -4.603741       -4.081560      0.0         1.320850

B: offline planner medians
             success  exposed  steep_len      cost     climb  energy_vs_A_pct   max_roll  p95_roll  roll_frac     length      time
planner                                                                                                                           
A*               1.0     0.24        0.0  0.190731  2.604656         0.000000  11.273761  7.641940        0.0  83.269484  0.048305
A*-HC            1.0     0.00        0.0  0.190731  2.594269         0.000000  11.213038  7.592498        0.0  84.195156  0.053462
TA*              1.0     0.00        0.0  0.128885  1.917558        -0.949608   6.747517  4.107431        0.0  86.274656  0.206713
TA*-S            1.0     0.00        0.0  0.140910  1.819883        -5.945662   7.279387  4.717955        0.0  82.478459  0.304330
TA*-S exact      1.0     0.00        0.0  0.140910  1.819883        -5.945662   7.279387  4.717955        0.0  82.478459  0.324228

B: TA* / TA*-S paths touching lethal cells
planner
TA*            0
TA*-S          2
TA*-S exact    0

B: TA*-S exact minus A*, two-sided Wilcoxon; Holm over five metrics
    metric   n           p         r      delta      p_holm
 steep_len 150 2.91038e-11        -1          0 5.82077e-11
 mean_cost 150 2.29961e-26        -1 -0.0457125  1.1498e-25
     climb 150 2.49213e-26 -0.999294  -0.598388  1.1498e-25
energy_rel 150 3.20083e-23 -0.934305   -5.94566 9.60249e-23
 length_xy 150   0.0198405 -0.219249  -0.862597   0.0198405

C: online medians
                     success  exposed         dJ        dL        dE      dE_A    slope95  plans  plan_time  touching
variant                                                                                                              
oracle A*                1.0     0.23  19.751882  1.684752  6.212686  0.000000  10.552096    1.0   0.027547        23
oracle TA*-S             1.0     0.00   0.000000  0.000000  0.000000 -5.849255   8.006759    1.0   0.170160         0
online adaptive R15      1.0     0.00   3.987416 -1.123476 -0.272938 -5.800661   8.414518   13.0   0.853940         0
coarse R15 c5            1.0     0.00   1.694878 -0.383033 -0.256990 -5.834577   8.004177   34.5   1.695251         0
coarse R10 c10           1.0     0.00   4.491727 -0.279692  0.311785 -5.129966   7.967976   43.0   1.536507         0
coarse R5 c10            1.0     0.00   7.757823 -0.503327  0.253814 -4.547059   8.607230   53.5   1.431153         0
coarse R5 c20            1.0     0.00   9.059590 -0.034366  1.236338 -3.947927   9.214740   46.0   1.343950         0

C: upper tails [%]
                          dJ90      dJmax      dL90      dLmax
variant                                                       
oracle A*            36.125263  69.296397  5.233974   7.407333
oracle TA*-S          0.000000   0.000000  0.000000   0.000000
online adaptive R15   9.229721  19.119464  0.749099   9.046572
coarse R15 c5         5.860787  29.058034  4.599941  39.318365
coarse R10 c10        7.951677  29.372925  6.145927  39.933463
coarse R5 c10        15.878072  45.803802  9.606503  39.797541
coarse R5 c20        16.248463  48.078251  7.875542  29.933135

C: per terrain median dJ [%]
kind                 beach_gentle  beach_scarp  beach_steep      hills    rolling
variant                                                                          
oracle A*               17.978271    20.415797    15.192240  33.485909  22.859127
oracle TA*-S             0.000000     0.000000     0.000000   0.000000   0.000000
online adaptive R15      3.986991     4.314552     4.867331   3.123697   3.180486
coarse R15 c5            1.393619     2.700566     3.476465   1.684372   1.338921
coarse R10 c10           3.910866     5.737060     4.127251   4.396195   4.314962
coarse R5 c10            7.567896     6.909440     6.885021   8.306757   8.510479
coarse R5 c20            9.170098     8.903149     8.886472  10.006951   8.526672

C: dJ > 25% trajectories (figures: detour_<kind>_<side_m>_<seed>.png)
       kind  side_m  seed        variant        dJ        dL  n_plans
beach_scarp      50     2 coarse R10 c10 29.372925 39.933463       43
beach_scarp      50     2  coarse R15 c5 29.058034 39.318365       34
beach_scarp      50     2  coarse R5 c10 29.833849 39.797541       52
beach_scarp      50     4  coarse R5 c20 36.856014 18.443976       41
beach_scarp      50     6  coarse R5 c10 45.544353 10.343723       55
beach_scarp      50     6  coarse R5 c20 48.078251 10.092280       44
beach_scarp     100     9 coarse R10 c10 28.363019 17.383050       91
beach_scarp     100     9  coarse R5 c10 45.803802 27.317890       99
beach_scarp     100     9  coarse R5 c20 47.306513 29.933135      102
      hills      50     3  coarse R5 c10 44.204486 22.219435       49

failures:
Empty DataFrame
Columns: [kind, side_m, seed, variant, reason]
Index: []
```
