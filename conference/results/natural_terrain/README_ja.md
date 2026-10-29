# 自然地形の生成と計画・再計画（タスク006）

最新取得時点の realtime-map（d9adad2）を土台に、codex/natural-terrain で作業しました。
**既存ファイルは1つも変更していません。** 全既存 conference ファイルのSHA-256を照合しました。

## 実装と仮定

- tapp/natural_terrain.py: generate_natural と NATURAL_TYPES、独立した fractal_surface、
  hydraulic_erosion、thermal_erosion、rock_population、spectrum_slope を追加しました。
  乱数は渡されたシードの default_rng からのみ生成します。fBmのHは0.8、beta=2H+2です。
  参照した方法は指示書に示された Huang & Turcotte (1989)、Beyer (2015)、Golombek & Rapp (1997) です。
- 水滴は双線形標高勾配、慣性、速度・水量・勾配に依存する運搬容量、堆積、半径付きの侵食、蒸発で動かします。
  バッチ内の土砂要求量はセルごとに積算し、そのセルの土量で制限します。出域・寿命終了時の土砂も戻します。
  Beyer方式をnumpyのバッチで近似したモデルで、実際の水理の時間・流量を較正したものではありません。
- 崩れは8近傍の安息角超過を同期的に低い側へ移す有限回の緩和です。
  32度・38度は移動の閾値であり、有限反復後の全方向の最大傾斜を保証する値ではありません。
- 岩は F(D)=k exp(-qD) の負の導関数を円の面積で割った個数密度から、ポアソン個数と逆CDFで直径を生成します。
  累積面積は個々の円の名目面積の和です。重なり・端での切断を含むラスターマスク面積とは区別します。
  高さは直径の半分のGaussian状のこぶで表し、サブグリッド岩は最小半セル幅でラスタライズします。
  0.4m以上の岩だけをrockに入れ、車体半径による既存の膨張はTraversabilityMapに任せます。
- rolling/mountainは1.2セル、badlandsは0.6セルの帯域制限を施したfBmを使います。
  入力fBmのスペクトル検査と、実際に平滑化・侵食した地形の前後スペクトルは区別します。
  後者がすべて同じHの純粋なべき則になるとは主張しません。
- 砂丘は風上8度・風下32度の非対称断面と、フラクタルによる尾根の曲がり、尾根高の長手方向変動、最後の崩れを使います。
- tapp/natural_scenario.py: build_natural を追加し、指定の SeedSequence 名前空間、開始・目標の抽出、
  通行可能な経路を持つまでの再作成を実装しました。terrain診断情報と生成時間も追加フィールドとして返します。
- experiments/natural_terrain.py: 指定の全統計・5プランナー・7条件を実行し、CSV、ログ、ギャラリー、
  dJ>25%ケースの図を保存します。統計検定は急斜面長、コスト、登高、エネルギー、経路長の5指標について
  paired_test と holm を使う選択とし、検定の対象をログに明記しました。
- tests/test_natural_terrain.py: 決定性、50/100/200mの形状と有限値、独立した入力fBmのスペクトル、
  岩の累積面積、シナリオの可解性、指定15軌跡の正確な安全性、実験の参照経路監査を検査します。

定数の一覧と生成器のハッシュは model_constants.json に保存しています。
重い実行依存関係は追加していません。書式整形には/tmpだけに導入したBlackを使い、ASTの一致を確認しました。

## 検証用シードだけで行った調整

最初の設定では rolling=5.5度、mountain=15度、badlands=16度で中央値を正規化しました。
直接入力した検証用シード100〜104、サイズ50/100/200mの実測値を validation_initial.csv とログに保存しています。
この時点でbadlandsの急斜面率が50m・100mで25%を超えたため、正規化の定数を16度から15度に変更しました。
また、初期砂丘の尾根高が長手方向に一定だと、検証用シナリオ dunes/50m/seed100 は20回以内で可解になりませんでした。
そのため尾根高に 0.65+0.35*(0.5+0.5*cos(...)) の長手方向変動を加え、連続した壁にならないようにしました。
変更後のbadlands・dunesの直接生成統計を validation_final.csv とログに保存しました。
ほかのパラメータは変えていません。その後は生成器・シナリオのASTが変更されていないことを照合しました。

直接 generate_natural に100〜104を入力した検証では、50m砂丘の急斜面率中央値は7.14%で、目標下限8%に未達です。
一方、build_natural の独立SeedSequenceを通した検証シナリオでは50m砂丘も目標内でした。
テスト用50m砂丘では約7.26%で下限に届いていません。都合のよい結果だけを採用せず、双方を残しています。
その他の目標は、検証シナリオの中央値では範囲内でした。テスト用シードを見てから再調整していません。
検証シナリオの統計は次のとおりです（割合は0〜1）。

```text
                   slope50     steep      rock
kind     side_m                               
badlands 50      14.954967  0.231600  0.000000
         100     14.858136  0.228400  0.000000
         200     14.716853  0.213600  0.000000
boulders 50       6.257532  0.004100  0.025600
         100      6.292088  0.004175  0.026275
         200      6.261000  0.004619  0.026612
dunes    50       7.271029  0.082800  0.000000
         100      6.916236  0.097675  0.000000
         200      7.137524  0.106419  0.000000
mountain 50      14.926599  0.171100  0.000000
         100     14.813885  0.168300  0.000000
         200     14.747149  0.169319  0.000000
rolling  50       5.500000  0.000000  0.000000
         100      5.500000  0.000325  0.000000
         200      5.500000  0.000662  0.000000
```

## 結果と限界

A: 225シナリオの統計を検証用75件・テスト用150件に分けて記録しました。
生成時間は地形作成・再作成・可解性確認までを含みます。観測された最大時間は次のとおりで、指定の目安内でした。

```text
side_m
50      0.458300
100     2.105394
200    20.206249
```

B: 全750計画が成功しました。TA*-Sは平均地形コストや急斜面長をA*より下げましたが、
「急斜面を一度も通らない」は完全には成り立ちませんでした。
TA*-Sの点サンプリング評価では150件中1件（badlands/50m/seed2、steep_len約0.099579m）で急斜面露出があり、
閉じたセルの正確な接触監査では150件中48件が禁止マスに触れました。TA*の接触は0件でした。
指示どおり旧 run_planner を使っており、論文・既存の平滑化・探索は変更していません。

C: オンライン500走行は失敗例を含めて正確な接触がすべて0件でした。
coarse R5 c20 の砂丘2件（50m/seed1、100m/seed2）は too_long で失敗しました。
失敗例には目標に到達したかのようなJを埋めず、dJの中央値・分位値は計算できた成功例について報告しています。
**成功率と安全性は別に表示しています。**
また、参照のoracle TA*-Sは旧平滑化のままなので、オンライン比較対象の100参照中29件が禁止マスに触れました。
したがってdJは指示された参照に対する値であり、すべて安全な理想経路に対する損失や、情報不足だけの影響とは断定しません。

大きなdJは旧ICAROB尾根だけの現象ではありませんでしたが、今回も地形の種類への依存が強く、特に砂丘で大きくなりました。
自然地形一般への有効性や実地形との一致を、この合成地形だけで保証するものではありません。
本物のDEM、植生、土の柔らかさ、横傾き、論文の修正は対象外として実施していません。

## dJ>25%ケースの図の点検

成功例のうちdJ>25%は102走行、40シナリオでした。
全該当走行を含む40枚の個別図とギャラリーを目視確認しました。inspection_1.png〜inspection_5.png は点検用一覧です。
全ケースの対応と観察は detour_inspection_ja.md、数値一覧は以下の実験ログとonline_relative.csvにあります。

- 砂丘: 急斜面の帯に沿う長い上下移動や折り返し形状が見えます。特にdunes/100m/seed5や50m/seed6では、
  理想より複数の帯で大きな往復状の経路を取り、横断可能な場所を探して大回りしている解釈と整合します。
- 荒れ地: badlands/100m/seed1では北側を大きく回る経路、50m/seed3では起伏の周囲への回り込みが見えます。
  粗い地図に現れない禁止領域の分布を観測して進路を変える例と解釈できます。
- 山地: mountain/100m/seed5などでは谷縁・山腹の禁止領域の周囲を理想と異なる側に回り込みます。
  50m/seed6など理想と近い形の例もあるため、dJの増加を距離だけで説明せず、地形コストの差も含めて考える必要があります。

これらは図と評価値に基づく観察・仮説です。観測履歴や各意思決定を因果的に追跡した証明ではありません。
ローリングや岩場に大きなdJがなかったことも含め、種類間の違いを表に残しています。

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
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online && python3 -m tests.test_dstar && python3 -m tests.test_risk_prior && python3 -m tests.test_collision && python3 -m tests.test_natural_terrain
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
```

実験:

```bash
cd conference && python3 experiments/natural_terrain.py
```

正常終了しました。実験前の小規模動作確認には検証用シード100のみを使用しました。
初回集計でオンライン参照A*の接触列が未計算だったため、100参照経路を実際に再生成・再実行して補いました。
最終の実験ソースには両oracleの正確な接触監査を組み込み、統合テストも追加しました。
地形のパラメータは変更していません。生CSVを補助監査で更新した後、次のコマンドで全集計を更新しました。

```bash
python3 /tmp/natural-oracle-audit.py
cd conference && python3 experiments/natural_terrain.py --summary-only
```

補助監査は生成済みケースの参照経路だけを再計算した処理で、最終ソースを新規に実行すると同じ監査が本実験内で完結します。
計測値は以下のJSONそのままです。初回全体時間と補助監査の時間は別記し、生成やA/B/Cの合計は
並列で重なった各ワーカーの経過時間の和であって、段階ごとの壁時計時間ではありません。
図一覧の作成・目視点検とテストはこの実験時間には含めません。
MPLCONFIGDIRとXDG_CACHE_HOMEは/tmp内の書き込み可能なキャッシュを使いました。

```json
{
  "experiments_s": 601.2628937180016,
  "total_s": 604.9790589209988,
  "workers": 5,
  "generation_sum_s": 413.7216819070054,
  "statistics_sum_s": 417.122964870985,
  "offline_sum_s": 207.49360729302134,
  "online_sum_s": 2366.4638024560154,
  "additional_oracle_contact_audit_s": 10.626959832003195
}
```

## 実験が表示した集計表（更新後の表示と同一）

```text
A: terrain statistics (medians, validation and test shown separately)
                              slope50    slope90    slope99     steep      rock     rough  spectrum_before  spectrum_after  redraws  generation_time
split      kind     side_m                                                                                                                          
test       badlands 50      14.944378  32.697217  41.435521  0.239250  0.000000  0.074498        -3.885311       -3.408589      0.0         0.307708
                    100     14.797755  32.042597  41.046516  0.222400  0.000000  0.072850        -3.837456       -3.380826      0.0         1.548079
                    200     14.710801  31.453264  40.567270  0.216181  0.000000  0.072633        -3.799189       -3.419106      0.0        10.333850
           boulders 50       6.298338  12.279733  20.611325  0.003750  0.026300  0.027353        -5.048142       -3.597157      0.0         0.318750
                    100      6.262193  12.177423  20.743105  0.004275  0.026562  0.027102        -4.766515       -3.598975      0.0         1.707453
                    200      6.265383  12.110884  20.834102  0.004469  0.026378  0.027054        -4.614201       -3.630285      0.0         7.010937
           dunes    50       7.158076  22.442009  33.330065  0.072600  0.000000  0.008475        -3.756212       -3.834407      0.0         0.039187
                    100      6.883527  24.200874  34.355657  0.089512  0.000000  0.001010        -4.306321       -4.311948      0.0         0.238152
                    200      6.971619  25.035447  35.425646  0.100562  0.000000  0.000508        -4.310066       -4.319073      0.0         0.894492
           mountain 50      14.893522  28.994835  38.977593  0.182950  0.000000  0.049865        -4.997226       -3.921686      0.0         0.156663
                    100     14.817728  28.722171  38.488137  0.174162  0.000000  0.048856        -4.759805       -3.749925      0.0         0.685475
                    200     14.771558  28.502276  38.705996  0.167419  0.000000  0.048634        -4.617610       -3.726923      0.0         4.121697
           rolling  50       5.500000  10.313526  14.881005  0.000050  0.000000  0.012246        -5.026323       -4.441047      0.0         0.056527
                    100      5.500000  10.390705  14.922071  0.000325  0.000000  0.011937        -4.763606       -4.217676      0.0         0.209362
                    200      5.500000  10.339267  15.211756  0.000547  0.000000  0.011596        -4.603428       -4.138405      0.0         1.294726
validation badlands 50      14.954967  32.344352  42.472801  0.231600  0.000000  0.072130        -3.871835       -3.477215      0.0         0.168577
                    100     14.858136  32.049993  41.070604  0.228400  0.000000  0.072744        -3.838878       -3.398537      0.0         0.843961
                    200     14.716853  31.387681  40.606519  0.213600  0.000000  0.072901        -3.790549       -3.367131      0.0        11.559994
           boulders 50       6.257532  12.258338  20.174898  0.004100  0.025600  0.026689        -4.998390       -3.651300      0.0         0.409930
                    100      6.292088  12.247605  20.820711  0.004175  0.026275  0.027249        -4.762224       -3.612709      0.0         1.749628
                    200      6.261000  12.146690  21.004381  0.004619  0.026612  0.027123        -4.616332       -3.614261      0.0         7.258851
           dunes    50       7.271029  22.979935  33.439996  0.082800  0.000000  0.009493        -3.679300       -3.736825      0.0         0.092158
                    100      6.916236  24.827957  34.430567  0.097675  0.000000  0.001020        -4.287439       -4.292860      0.0         0.152173
                    200      7.137524  25.491360  35.900883  0.106419  0.000000  0.000503        -4.226417       -4.233765      0.0         0.596881
           mountain 50      14.926599  28.725334  39.485487  0.171100  0.000000  0.048867        -5.021963       -3.856682      0.0         0.086019
                    100     14.813885  28.397835  38.756432  0.168300  0.000000  0.048660        -4.769423       -3.786750      0.0         0.390194
                    200     14.747149  28.563058  38.404562  0.169319  0.000000  0.048801        -4.606228       -3.736639      0.0         5.014884
           rolling  50       5.500000  10.110343  14.201984  0.000000  0.000000  0.011591        -5.052641       -4.415295      0.0         0.029848
                    100      5.500000  10.394052  14.891869  0.000325  0.000000  0.011860        -4.762347       -4.223025      0.0         0.259692
                    200      5.500000  10.308863  15.117935  0.000662  0.000000  0.011460        -4.595289       -4.107541      0.0         1.298321

B: offline planner medians
         success   exposed  steep_len      cost     climb     energy     length      time
planner                                                                                  
A*           1.0  0.626667   4.769403  0.285228  5.853107  28.603986  82.866997  0.037166
A*-HC        1.0  0.000000   0.000000  0.294326  5.656280  29.404507  90.945489  0.056580
TA*          1.0  0.000000   0.000000  0.199827  4.653084  29.159444  97.042081  0.276771
TA*-S        1.0  0.006667   0.000000  0.211265  4.420860  27.888083  92.398413  0.334611
Theta*       1.0  0.626667   3.884984  0.289538  5.419069  27.138931  78.045519  0.076752

B: TA* / TA*-S paths touching lethal cells
planner
TA*       0
TA*-S    48

B: TA*-S minus A*, two-sided Wilcoxon; Holm over five metrics
   metric   n           p         r      delta      p_holm
steep_len 150 3.80973e-17        -1    -4.7694 7.61946e-17
mean_cost 150 2.34631e-26 -0.999823 -0.0845545 1.17315e-25
    climb 150 4.92884e-23 -0.930243   -0.98064 1.97154e-22
energy_kj 150   0.0016368 -0.296424  -0.626189   0.0016368
length_xy 150 5.31121e-19  0.838234    4.78737 1.59336e-18

C: online medians
                     success  exposed         dJ        dL        dE      dE_A    slope95  plans  plan_time  touching
variant                                                                                                              
oracle A*               1.00     0.60  19.374033 -3.731910  2.746564  0.000000  27.106428    1.0   0.020776        60
oracle TA*-S            1.00     0.01   0.000000  0.000000  0.000000 -2.672758  18.538030    1.0   0.158729        29
online adaptive R15     1.00     0.00   2.602251  0.095703  0.413235 -2.994031  17.965134   25.0   1.604211         0
coarse R15 c5           1.00     0.00   2.279866  0.510538  0.747727 -2.687817  18.498261   50.5   2.422175         0
coarse R10 c10          1.00     0.00   5.479351  3.352174  3.596374 -0.626018  17.406590   64.5   2.314517         0
coarse R5 c10           1.00     0.00   8.800258  3.460605  4.190686  1.548366  13.440243   75.5   2.790058         0
coarse R5 c20           0.98     0.00  12.487560  4.565641  5.895011  2.279935  13.440243   80.5   2.855537         0

C: upper tails [%]
                           dJ90       dJmax        dL90       dLmax
variant                                                            
oracle A*             39.655140   56.893502    0.877709    5.493442
oracle TA*-S           0.000000    0.000000    0.000000    0.000000
online adaptive R15   28.434403  162.749998   17.224727  168.077127
coarse R15 c5         12.178552  161.136230   11.740711  167.008653
coarse R10 c10        55.140680  183.279489   57.610405  203.854694
coarse R5 c10        126.073047  301.447289  137.017124  390.673012
coarse R5 c20        160.730669  353.814707  182.107894  439.970600

C: per terrain median dJ [%]
kind                  badlands   boulders       dunes   mountain    rolling
variant                                                                    
oracle A*            33.437684  17.600430   -7.060871  26.180384  19.850486
oracle TA*-S          0.000000   0.000000    0.000000   0.000000   0.000000
online adaptive R15   2.895960   1.268513    7.309197   3.136056   4.126213
coarse R15 c5         2.355441   1.587743    8.041937   3.026946   1.836675
coarse R10 c10        9.360626   3.069055   54.203570   6.734307   3.232660
coarse R5 c10        17.104272   4.054538  151.018021  12.080353   5.138154
coarse R5 c20        24.496264   5.155716  187.861570  17.358470   7.566085

C: dJ > 25% trajectories (figures: detour_<kind>_<side_m>_<seed>.png)
    kind  side_m  seed             variant         dJ         dL  n_plans
badlands      50     3       coarse R5 c20 109.147423  96.262939       72
badlands      50     6       coarse R5 c20  38.562073  65.790594       73
badlands      50     7      coarse R10 c10  34.080522  52.553346       58
badlands      50     8      coarse R10 c10  32.690736  30.300930       72
badlands      50     8       coarse R5 c20  36.361811  35.363968       81
badlands      50     9       coarse R15 c5  31.183239  35.889836       37
badlands      50     9       coarse R5 c10  52.023358  21.399880       51
badlands      50     9       coarse R5 c20  61.641528  41.251565       58
badlands      50     9 online adaptive R15  34.032337  17.205437       23
badlands     100     0       coarse R5 c10  29.411574   6.146089       86
badlands     100     0       coarse R5 c20  90.641780  84.668955      152
badlands     100     1      coarse R10 c10  54.490105  50.772254      143
badlands     100     1       coarse R15 c5  34.674742  33.067590      118
badlands     100     1       coarse R5 c10  42.697940  47.224827      161
badlands     100     1       coarse R5 c20 122.206540  92.552704      189
badlands     100     1 online adaptive R15  63.005927  32.123230       86
badlands     100     2       coarse R5 c10  32.536309  25.942371      141
badlands     100     2       coarse R5 c20  66.722284  51.327761      163
badlands     100     3      coarse R10 c10  25.916920   7.053424      103
badlands     100     3       coarse R5 c20  36.644110  20.770492      128
badlands     100     4      coarse R10 c10  35.348953  39.848386       86
badlands     100     4       coarse R5 c10  32.935565  29.312999       93
badlands     100     4 online adaptive R15  39.725636  36.233438       59
badlands     100     5       coarse R5 c10  41.577499  55.073305      133
badlands     100     5       coarse R5 c20  27.553737  46.524026      125
badlands     100     6       coarse R5 c10  46.321645  30.772106      102
badlands     100     6       coarse R5 c20  40.837083  27.299298      102
   dunes      50     0       coarse R5 c10  89.735793 101.783353      161
   dunes      50     0       coarse R5 c20  65.956515  72.070777      153
   dunes      50     1       coarse R5 c10 217.175787 273.198636      155
   dunes      50     2       coarse R5 c10 219.432834 267.518626      156
   dunes      50     2       coarse R5 c20 226.540035 278.522100      162
   dunes      50     3       coarse R5 c10  82.176222  90.587641      110
   dunes      50     3       coarse R5 c20  83.645162  94.408931      112
   dunes      50     4       coarse R5 c10 186.958610 252.841618      133
   dunes      50     4       coarse R5 c20 186.539133 251.659103      132
   dunes      50     5      coarse R10 c10 100.468561 105.451282       60
   dunes      50     5       coarse R5 c10 205.112157 253.506624      143
   dunes      50     5       coarse R5 c20 208.160574 256.376199      144
   dunes      50     6      coarse R10 c10  74.090482  93.225074       60
   dunes      50     6       coarse R5 c10 301.447289 390.673012      161
   dunes      50     6       coarse R5 c20 353.814707 439.970600      172
   dunes      50     7      coarse R10 c10  56.075576  57.314950       72
   dunes      50     7       coarse R15 c5  38.041204  27.519949       46
   dunes      50     7       coarse R5 c10  97.201323 111.528689      107
   dunes      50     7       coarse R5 c20  87.166742 101.802620      103
   dunes      50     7 online adaptive R15  27.812410  22.450270       27
   dunes      50     8      coarse R10 c10  40.127220  37.410327      103
   dunes      50     8       coarse R5 c10  75.090171  73.933406      149
   dunes      50     8       coarse R5 c20  88.610097  91.269191      163
   dunes      50     9      coarse R10 c10  84.932975 105.289805       95
   dunes      50     9       coarse R15 c5  45.126453  55.717958       54
   dunes      50     9       coarse R5 c10 210.343235 253.719291      178
   dunes      50     9       coarse R5 c20 213.862438 257.581092      184
   dunes      50     9 online adaptive R15  43.799338  56.631221       47
   dunes     100     0      coarse R10 c10  52.331563  60.269503       92
   dunes     100     0       coarse R5 c10 224.034268 251.804021      213
   dunes     100     0       coarse R5 c20 223.495838 256.006710      260
   dunes     100     1       coarse R5 c10  98.939714 115.050320      244
   dunes     100     1       coarse R5 c20 112.579181 129.583885      275
   dunes     100     2      coarse R10 c10 103.767817 118.046688      228
   dunes     100     2       coarse R15 c5  62.906006  71.339681      119
   dunes     100     2       coarse R5 c10 110.659520 125.039830      266
   dunes     100     2 online adaptive R15  62.496808  70.164067      123
   dunes     100     3      coarse R10 c10  25.503364  25.763544      209
   dunes     100     3       coarse R5 c10  37.212538  35.310464      242
   dunes     100     3       coarse R5 c20  83.923127  82.306203      338
   dunes     100     4      coarse R10 c10  79.513484  90.397587      179
   dunes     100     4       coarse R5 c10 102.048893 116.585555      215
   dunes     100     4       coarse R5 c20 149.669899 168.052913      298
   dunes     100     5      coarse R10 c10 183.279489 188.412072      244
   dunes     100     5       coarse R15 c5 161.136230 167.008653      186
   dunes     100     5       coarse R5 c10 213.075799 212.300387      303
   dunes     100     5       coarse R5 c20 216.560577 216.846593      409
   dunes     100     5 online adaptive R15 162.749998 168.077127      173
   dunes     100     6      coarse R10 c10 102.998552 111.027280      223
   dunes     100     6       coarse R15 c5 123.122064 142.998627      169
   dunes     100     6       coarse R5 c10 119.836804 129.505770      262
   dunes     100     6       coarse R5 c20 226.783204 254.683980      408
   dunes     100     6 online adaptive R15 135.363033 155.174256      168
   dunes     100     7      coarse R10 c10  67.894835  89.801138      157
   dunes     100     7       coarse R5 c10 183.734834 232.293844      292
   dunes     100     7       coarse R5 c20 266.714654 326.742252      405
   dunes     100     8      coarse R10 c10 167.861798 203.854694      263
   dunes     100     8       coarse R15 c5  89.209525  96.869819      144
   dunes     100     8       coarse R5 c10 182.199239 204.619304      285
   dunes     100     8       coarse R5 c20 189.184007 214.902849      306
   dunes     100     8 online adaptive R15  72.873054  75.784481      114
   dunes     100     9      coarse R10 c10  37.065085  33.960690      260
   dunes     100     9       coarse R5 c10  73.177553  69.586309      323
   dunes     100     9       coarse R5 c20  75.454859  74.408826      342
mountain      50     2       coarse R5 c10  38.898757  25.751437       67
mountain      50     2       coarse R5 c20  49.010814  35.046278       73
mountain      50     3       coarse R5 c10  43.557861  43.821127       68
mountain      50     6 online adaptive R15  43.315374  17.398332       30
mountain     100     0       coarse R5 c20  28.071765  26.552358      129
mountain     100     2       coarse R5 c20  40.751365  35.120277      105
mountain     100     5      coarse R10 c10  55.036803  36.587927      137
mountain     100     5 online adaptive R15  44.081766  16.607550       65
mountain     100     6       coarse R5 c10  31.427689  15.624369      115
mountain     100     6       coarse R5 c20  30.362546  18.909692      120
mountain     100     7       coarse R5 c20  46.421398  36.878716       93

failures:
 kind  side_m  seed       variant   reason
dunes      50     1 coarse R5 c20 too_long
dunes     100     2 coarse R5 c20 too_long
```
