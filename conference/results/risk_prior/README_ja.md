# 不確かな粗地図に対する較正済み地形コスト

`realtime-map` の最新取得時点（`8396981`）を土台に、指定の `codex/risk-prior` で実装しました。
既存ファイルの変更は、指示書で許可された `conference/tapp/prior.py` の関数切り出しだけです。
`online.py`、探索・評価・地形生成・設定、論文、既存結果は変更していません。

## 実装

- `tapp/prior.py`: ブロック平均・雑音・双線形補間と入力検証を `coarse_elevation` に切り出しました。
  `coarse_prior` はその戻り値を使って、従来どおり TraversabilityMap を作ります。
  変更前に保存した全16条件の cost/lethal と、変更後の配列のバイト列が完全一致しました。
  本実験の基準条件でも、既存結果の全80ケースについて経路長・エネルギー・平均コスト・再計画回数・安全性指標が完全一致しました。
- `tapp/risk_prior.py`: `Calibration`、`calibrate`、`risk_prior`、
  `save_calibration`、`load_calibration` を追加しました。
  検証用地図の全マスを地形種別によらず集計し、指定された傾斜区間で真の平均コストと通行不可確率を推定します。
  空区間は指定された近い非空区間の値を引き継ぎ、counts 自体は変更しません。
  seeds にテスト用の0〜9が含まれる較正は、地図を作る前に ValueError にします。
- `experiments/risk_prior.py`: 較正、検証用シードだけでのλ選択、本実験、中央値・上側分位・地形別集計、
  対応のある両側Wilcoxon検定、比較ごと5条件のHolm補正を実装しました。
  `experiments.analyze` の `paired_test` と `holm` をimportして使用し、元のファイルは変更していません。
  `run_online` は既存のまま、TA*-S・既定のA*探索・soft priorで呼び出します。
- `tests/test_risk_prior.py`: 整理後の一致、全マスの集計、較正の決定性とJSON往復、
  テスト用シードの拒否、空区間と境界、期待コスト・λ単調性・クリップ・雑音・lethalの一致、
  指定された地形・シード・センサー距離での安全性を検査します。

較正は検証用シードだけで行い、λも同じ検証用シードの実行結果だけで選択しました。
較正JSONと選択JSONのハッシュを本実験中に記録し、終了後に変更がないことを照合しました。
本実験の結果を見た後に、λ候補、傾斜区間、パラメータを変更していません。
同じ入力になる calibrated mean と risk λ* も、それぞれ実際にプランナーを実行しました。
本実行前の並列化・選択・統計処理の小規模確認にも検証用シード100を使い、
その出力は本実験の結果に含めていません。

## 結果

選ばれたλは **0** でした。したがって今回の risk λ* は、通行不可確率の上乗せを行わない期待値のみの版です。
**risk λ* は、全5条件のうち5条件で coarse よりdJ中央値が悪化し、改善しませんでした。**
再計画回数と計画時間は減りましたが、目的関数の改善には結びついていません。
次は本実験CSVから再集計した条件別の中央値です。

```text
             coarse_dJ  coarse_plans  coarse_plan_time    risk_dJ  risk_plans  risk_plan_time
R_m  cell_m                                                                                  
15.0 5.0      1.497122          48.0          1.882018   1.734707        15.0        0.935004
10.0 10.0     3.342535          59.0          1.801513   6.514097        19.0        0.984045
     20.0     4.744195          65.5          2.195245   8.663069        23.0        1.528701
5.0  10.0     7.136692          63.5          2.066896  15.010684        25.0        1.149973
     20.0     9.307821          72.5          1.985560  19.333615        26.0        1.245345
```

検証用CSVは1200行、本実験CSVは2000行です。
要求された条件・地形・サイズ・シード・手法の網羅、一意性、全件の目標到達、
保存ログと表示内容の一致を確認しました。
なお、目標到達の成功と安全性は別です。下記の露出例を成功率に隠さず報告します。

## 安全性の制約と切り分け

指定の安全性テストは通りましたが、本実験のオンライン1200走行のうち14行で、
評価上の急斜面への露出または岩への接触がありました。
内訳は coarse が4行、calibrated mean が5行、
risk λ* が5行です。同一λによる重複した手法の走行も行数に含みます。
したがって全条件の安全性を保証する結果ではありません。

```text
 R_m  cell_m    kind  side_m  seed         variant  steep_len  rock_hit
15.0     5.0   rocky     100     7 calibrated mean   0.000000      True
15.0     5.0   rocky     100     7         risk λ*   0.000000      True
10.0    10.0   hills     100     2 calibrated mean   0.099824     False
10.0    10.0   hills     100     2         risk λ*   0.099824     False
10.0    10.0   hills     100     3 calibrated mean   0.099861     False
10.0    10.0   hills     100     3         risk λ*   0.099861     False
10.0    10.0 craters     100     0          coarse   0.099799     False
 5.0    10.0   hills     100     3 calibrated mean   0.099762     False
 5.0    10.0   hills     100     3         risk λ*   0.099762     False
 5.0    10.0   rocky      50     6          coarse   0.000000      True
 5.0    10.0   rocky     100     7          coarse   0.000000      True
 5.0    20.0   hills      50     4 calibrated mean   0.099679     False
 5.0    20.0   hills      50     4         risk λ*   0.099679     False
 5.0    20.0   rocky      50     7          coarse   0.000000      True
```

代表3例を再実行して、真の lethal マスク上で区間ごとに既存の line_of_sight を検査しました。
標準間隔0.25セルでは受理され、細かい0.01セルでは拒否される区間が、それぞれ見つかりました。
coarse の例では、整理前の prior.py をGitの土台コミットから読み込んでも
配列と実行軌跡の全座標が一致し、同じ露出を再現しました。
これは少なくとも既存のサンプリングによる衝突判定にも見落としがある証拠です。
全露出例の原因をこの3例だけで断定してはいません。
指示書の変更禁止に従い、online.py や planners.py は修正していません。修復は別の作業が必要です。

診断の実行結果（実験本体の計時には含めていません）:

```text
{'kind': 'craters', 'side_m': 100, 'seed': 0, 'R_m': 10.0, 'cell_m': 10.0, 'method': 'coarse', 'steep_len': 0.0997987193600691, 'rock_hit': False, 'segments_accepted_at_default_step_but_rejected_at_0_01_cells': 1}
Original pre-refactor coarse_prior reproduces the exact same exposed trajectory.
{'kind': 'rocky', 'side_m': 100, 'seed': 7, 'R_m': 15.0, 'cell_m': 5.0, 'method': 'risk', 'steep_len': 0.0, 'rock_hit': True, 'segments_accepted_at_default_step_but_rejected_at_0_01_cells': 1}
{'kind': 'hills', 'side_m': 50, 'seed': 4, 'R_m': 5.0, 'cell_m': 20.0, 'method': 'risk', 'steep_len': 0.09967899892736333, 'rock_hit': False, 'segments_accepted_at_default_step_but_rejected_at_0_01_cells': 1}
```

20mの較正表では15度以上の区間にサンプルがなく、指示どおり下側の非空区間を引き継いでいます。
これらの区間が観測データで直接較正されたとは主張しません。
今回の集計だけから、目的関数が悪化した原因や、実機での有効性は断定していません。

## 実行コマンドとテスト出力全文

変更前:

```bash
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online && python3 -m tests.test_dstar
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
```

変更後:

```bash
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online && python3 -m tests.test_dstar && python3 -m tests.test_risk_prior
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
```

実験:

```bash
cd conference && python3 experiments/risk_prior.py
```

実行時は Matplotlib の読み取り専用ホームへのキャッシュ作成を避けるため、
MPLCONFIGDIR=/tmp/risk-prior-mpl、XDG_CACHE_HOME=/tmp/risk-prior-cache を指定しました。
新しい依存関係は追加していません。

全実験の実測時間は **927.328秒** です。
内訳と実行環境は、実験スクリプトが測定して保存した次のJSONのとおりです。
この時間には後処理の照合と安全性診断は含めません。

```json
{
  "calibration_s": 3.3574239919998945,
  "validation_s": 254.1758812979997,
  "test_s": 669.6089338830006,
  "total_s": 927.328054775,
  "workers": 5,
  "python": "3.12.14",
  "numpy": "2.3.5",
  "pandas": "2.2.3"
}
```

## λ選択表（表示したまま）

```text
lambda selection (validation seeds only; unrounded medians determine rank):
 lam  succ  runs  computed_dJ  dJ_median  plans_median
0.00   1.0   200          200   5.985445          18.0
0.25   1.0   200          200   6.087428          17.0
0.50   1.0   200          200   6.282060          16.0
1.00   1.0   200          200   6.005402          15.0
2.00   1.0   200          200   6.215938          13.0

selected lambda: 0

failures: {}
```

## 較正表（表示したまま）

各 cell_m について mean_cost、p_lethal、counts の全区間を示します。
元の精度の値は calibration_5.json、calibration_10.json、calibration_20.json に保存しています。

```text
calibration: cell_m=5
 lower_deg  upper_deg  mean_cost  p_lethal  counts
       0.0        2.5   0.221843  0.013332  294403
       2.5        5.0   0.245193  0.014487  335752
       5.0        7.5   0.283999  0.022119  134588
       7.5       10.0   0.325450  0.040384   68245
      10.0       12.5   0.372452  0.059138   52690
      12.5       15.0   0.424115  0.109169   38051
      15.0       17.5   0.479378  0.239672   24279
      17.5       20.0   0.521467  0.430250   16344
      20.0       22.5   0.551857  0.602143   10637
      22.5       25.0   0.570594  0.736109    6749
      25.0       90.0   0.590115  0.913098   18262

calibration: cell_m=10
 lower_deg  upper_deg  mean_cost  p_lethal  counts
       0.0        2.5   0.247136  0.021615  456990
       2.5        5.0   0.272610  0.044436  284074
       5.0        7.5   0.327140  0.092473  112033
       7.5       10.0   0.360509  0.117072   70888
      10.0       12.5   0.399283  0.212279   40409
      12.5       15.0   0.441343  0.302170   18430
      15.0       17.5   0.428959  0.362021    8947
      17.5       20.0   0.442757  0.433018    4658
      20.0       22.5   0.470475  0.554961    3175
      22.5       25.0   0.613343  0.905660     318
      25.0       90.0   0.591866  1.000000      78

calibration: cell_m=20
 lower_deg  upper_deg  mean_cost  p_lethal  counts
       0.0        2.5   0.280444  0.063394  697544
       2.5        5.0   0.284532  0.071194  205412
       5.0        7.5   0.309063  0.038888   85270
       7.5       10.0   0.338364  0.026973   10010
      10.0       12.5   0.390835  0.154073    1694
      12.5       15.0   0.272322  0.000000      70
      15.0       17.5   0.272322  0.000000       0
      17.5       20.0   0.272322  0.000000       0
      20.0       22.5   0.272322  0.000000       0
      22.5       25.0   0.272322  0.000000       0
      25.0       90.0   0.272322  0.000000       0

```

## 本実験の集計表（表示したまま）

r と差の符号は「最初の手法 − coarse」です。dJが低い方がよいため、負のrが最初の手法に有利です。
Holm補正は risk λ* 対 coarse の5条件と、calibrated mean 対 coarse の5条件を別々に行っています。
表示値の丸めを検定やλ選択には使っていません。

```text
per condition and variant (medians; relative metrics [%]):
                             succ  steep_exposed      dJ     dL     dE   dE_A   cost  slope95  plans  plan_time
R_m  cell_m variant                                                                                            
15.0 5.0    oracle A*         1.0          0.712  29.540 -3.208  7.955  0.000  0.313   25.234    1.0      0.018
            oracle TA*-S      1.0          0.000   0.000  0.000  0.000 -7.369  0.160    9.556    1.0      0.157
            coarse            1.0          0.000   1.497 -0.469 -0.414 -7.637  0.169    9.759   48.0      1.882
            calibrated mean   1.0          0.000   1.735 -0.680 -0.208 -6.986  0.179   10.488   15.0      0.921
            risk λ*           1.0          0.000   1.735 -0.680 -0.208 -6.986  0.179   10.488   15.0      0.935
10.0 10.0   oracle A*         1.0          0.712  29.540 -3.208  7.955  0.000  0.313   25.234    1.0      0.019
            oracle TA*-S      1.0          0.000   0.000  0.000  0.000 -7.369  0.160    9.556    1.0      0.150
            coarse            1.0          0.012   3.343  0.665  0.958 -5.590  0.180    9.956   59.0      1.802
            calibrated mean   1.0          0.025   6.514 -1.121  0.075 -7.041  0.198   11.626   19.0      0.976
            risk λ*           1.0          0.025   6.514 -1.121  0.075 -7.041  0.198   11.626   19.0      0.984
     20.0   oracle A*         1.0          0.712  29.540 -3.208  7.955  0.000  0.313   25.234    1.0      0.026
            oracle TA*-S      1.0          0.000   0.000  0.000  0.000 -7.369  0.160    9.556    1.0      0.159
            coarse            1.0          0.000   4.744  0.440  0.715 -3.826  0.182   10.107   65.5      2.195
            calibrated mean   1.0          0.000   8.663 -0.731  0.448 -6.109  0.201   11.531   23.0      1.503
            risk λ*           1.0          0.000   8.663 -0.731  0.448 -6.109  0.201   11.531   23.0      1.529
5.0  10.0   oracle A*         1.0          0.712  29.540 -3.208  7.955  0.000  0.313   25.234    1.0      0.017
            oracle TA*-S      1.0          0.000   0.000  0.000  0.000 -7.369  0.160    9.556    1.0      0.152
            coarse            1.0          0.000   7.137  0.978  2.071 -2.806  0.191   10.160   63.5      2.067
            calibrated mean   1.0          0.012  15.011 -1.531  1.190 -5.255  0.224   14.103   25.0      1.201
            risk λ*           1.0          0.012  15.011 -1.531  1.190 -5.255  0.224   14.103   25.0      1.150
     20.0   oracle A*         1.0          0.712  29.540 -3.208  7.955  0.000  0.313   25.234    1.0      0.018
            oracle TA*-S      1.0          0.000   0.000  0.000  0.000 -7.369  0.160    9.556    1.0      0.161
            coarse            1.0          0.000   9.308  1.181  3.048 -2.617  0.197   11.140   72.5      1.986
            calibrated mean   1.0          0.012  19.334 -1.630  1.291 -5.308  0.242   14.363   26.0      1.192
            risk λ*           1.0          0.012  19.334 -1.630  1.291 -5.308  0.242   14.363   26.0      1.245

upper tails (90th percentile and maximum [%]):
                                dJ90   dJ_max    dL90   dL_max
R_m  cell_m variant                                           
15.0 5.0    oracle A*         73.114  139.686   3.105    5.859
            oracle TA*-S       0.000    0.000   0.000    0.000
            coarse             5.705   71.658   4.427   65.823
            calibrated mean   15.779   81.053   4.077   77.122
            risk λ*           15.779   81.053   4.077   77.122
10.0 10.0   oracle A*         73.114  139.686   3.105    5.859
            oracle TA*-S       0.000    0.000   0.000    0.000
            coarse            25.303  101.836  20.186  100.479
            calibrated mean   55.793  107.478  58.763  101.639
            risk λ*           55.793  107.478  58.763  101.639
     20.0   oracle A*         73.114  139.686   3.105    5.859
            oracle TA*-S       0.000    0.000   0.000    0.000
            coarse            57.084  102.654  55.056  102.680
            calibrated mean   74.763  242.877  66.808  219.702
            risk λ*           74.763  242.877  66.808  219.702
5.0  10.0   oracle A*         73.114  139.686   3.105    5.859
            oracle TA*-S       0.000    0.000   0.000    0.000
            coarse            77.087  153.928  63.175  115.267
            calibrated mean  100.680  312.040  81.285  239.840
            risk λ*          100.680  312.040  81.285  239.840
     20.0   oracle A*         73.114  139.686   3.105    5.859
            oracle TA*-S       0.000    0.000   0.000    0.000
            coarse           100.590  291.784  87.459  253.543
            calibrated mean  116.991  320.017  86.638  240.926
            risk λ*          116.991  320.017  86.638  240.926

per condition and terrain (median dJ [%]):
kind                         craters   hills    ridge   rocky
R_m  cell_m variant                                          
15.0 5.0    oracle A*         65.412  17.954   30.431  38.626
            oracle TA*-S       0.000   0.000    0.000   0.000
            coarse             1.628   0.952    1.520   1.988
            calibrated mean    1.269   0.939    2.787   2.869
            risk λ*            1.269   0.939    2.787   2.869
10.0 10.0   oracle A*         65.412  17.954   30.431  38.626
            oracle TA*-S       0.000   0.000    0.000   0.000
            coarse             2.919   2.959    3.487   4.246
            calibrated mean    6.897   4.076   19.804   6.241
            risk λ*            6.897   4.076   19.804   6.241
     20.0   oracle A*         65.412  17.954   30.431  38.626
            oracle TA*-S       0.000   0.000    0.000   0.000
            coarse             3.223   3.984   32.781   6.162
            calibrated mean    7.694   6.711   57.277   8.067
            risk λ*            7.694   6.711   57.277   8.067
5.0  10.0   oracle A*         65.412  17.954   30.431  38.626
            oracle TA*-S       0.000   0.000    0.000   0.000
            coarse             5.265   6.259   10.901  10.505
            calibrated mean   12.041   9.555   79.918  17.951
            risk λ*           12.041   9.555   79.918  17.951
     20.0   oracle A*         65.412  17.954   30.431  38.626
            oracle TA*-S       0.000   0.000    0.000   0.000
            coarse             6.631   8.820   78.747  15.464
            calibrated mean   16.413  12.817  104.452  20.663
            risk λ*           16.413  12.817  104.452  20.663

paired two-sided Wilcoxon tests (Holm across five conditions per comparison):
negative r favours the first method (lower dJ)
 R_m  cell_m               comparison  n  dJ_diff_median        r           p      p_holm
  15       5         risk λ* - coarse 80        0.338367 0.282716   0.0280419   0.0280419
  10      10         risk λ* - coarse 80         1.78364 0.545062 2.28428e-05 9.13712e-05
  10      20         risk λ* - coarse 80         2.01054 0.400617  0.00185328  0.00370655
   5      10         risk λ* - coarse 80         4.77013 0.621605 1.36628e-06 6.83141e-06
   5      20         risk λ* - coarse 80         4.94072 0.524691 4.56511e-05 0.000136953
  15       5 calibrated mean - coarse 80        0.338367 0.282716   0.0280419   0.0280419
  10      10 calibrated mean - coarse 80         1.78364 0.545062 2.28428e-05 9.13712e-05
  10      20 calibrated mean - coarse 80         2.01054 0.400617  0.00185328  0.00370655
   5      10 calibrated mean - coarse 80         4.77013 0.621605 1.36628e-06 6.83141e-06
   5      20 calibrated mean - coarse 80         4.94072 0.524691 4.56511e-05 0.000136953

failures: {}
```

