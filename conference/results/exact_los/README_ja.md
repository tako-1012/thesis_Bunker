# 正確な線分通行判定（タスク004）

最新取得時点の realtime-map（63b28a8）を土台に、指定の codex/exact-los で実装しました。

## 実装

- tapp/collision.py: segment_cells、line_of_sight_exact、path_lethal_cells を追加しました。
  各行の閉じた帯で線分をスラブクリッピングし、その区間が触れる列のマスを列挙する方式です。
  一様な点サンプリングや外接長方形全体の総当たりには依存せず、辺・角への接触も含めます。
  正方形を各軸に1e-9セルだけ拡張して、安全側の許容誤差を適用します。
  マスは地図内だけを返し、軌跡全体の通行禁止マスは重複を除いて返します。
- tapp/planners.py: 許可された smooth_cost_aware の los=None 引数と判定の差し替えだけを変更しました。
  None は従来の line_of_sight を使います。ほかの探索やコスト積分は変更していません。
- tapp/online.py: exact_los=False を追加しました。True の場合だけ、平滑化、再計画のつなぎ目、
  新しく見えた残経路セルの通行禁止・コスト両方の検査に正確な判定を使います。
  A* と D* Lite のどちらでも有効です。既定の分岐は従来の判定を維持します。
- tests/test_collision.py: 独立した分離軸の定理による20×20全マスの基準と2000線分を比較しました。
  中心・辺・角の端点、長さゼロ、逆順、地図外、重複除去、指定の角かすめ例、回帰、安全性を検査します。
- experiments/exact_los.py: 論文経路の監査とオンライン比較を multiprocessing.Pool で実行し、
  CSV・ログ・保存済み結果との不一致行・実行時間を新しい結果フォルダだけに保存します。

既存ファイルの変更は許可された planners.py と online.py だけです。
全既存 conference ファイルのSHA-256を照合し、ほかのソース・論文・既存結果に変更がないことを確認しました。
新しい依存関係は追加していません。テスト用シードで判定の許容誤差や設定を調整していません。

## 結果と制約

(A) TA*は120経路中0件、TA*-Sは120経路中6件が閉じた通行禁止マスに触れました。
その6件はすべて点サンプリングの評価では露出が見えませんでした。論文は変更していません。
該当ケースは次のとおりです。

```text
   kind  side_m  seed planner  lethal_cells
craters     100     0   TA*-S             1
  rocky      50     0   TA*-S             1
  rocky      50     3   TA*-S             2
  rocky     200     1   TA*-S             1
  rocky     200     6   TA*-S             2
  rocky     200     8   TA*-S             1
```

(B) 旧判定の400走行中14件が接触し、正確判定の400走行では接触0件でした。
全走行が目標に到達しました。正確判定で残った接触例はありません。
既存の論文結果・タスク003のcoarse結果との不一致はどちらも0行でした。
比較した評価値には経路長、3D長、エネルギー、平均コスト、急斜面長、岩接触、傾斜95%値を含み、
オンラインでは再計画回数も比較しています。数値の比較は絶対許容誤差1e-9で、計時は除きます。

次は条件ごとの中央値と、計画時間の中央値同士の変化率です。
短くなった条件も、長くなった条件も、そのまま示します。
dJは多くの条件でわずかに増え、R=5m・cell=20mでは減りました。再計画回数も表のとおり変わりました。

```text
              dJ_old  plans_old  time_old  dJ_exact  plans_exact  time_exact  time_change_pct
R_m cell_m                                                                                   
5   10      7.136692       63.5  2.071598  7.243856         64.5    1.935636        -6.563138
    20      9.307821       72.5  1.864565  9.196318         72.0    1.825377        -2.101755
10  10      3.342535       59.0  1.800411  3.444945         60.0    1.838675         2.125294
    20      4.744195       65.5  1.837842  4.794876         66.0    1.852687         0.807736
15  5       1.497122       48.0  2.181050  1.499733         49.0    2.295193         5.233423
```

計画時間は既存 run_online の plan_time（探索・更新・経路抽出・平滑化）の定義です。
再計画トリガーのセル列挙、センサー処理、実行軌跡の監査は含めていません。
そのため、この値から制御ループ全体の実時間性や速度向上を断定していません。
実験は5並列で行い、時間差には実行時の揺らぎと経路の変化も含まれます。

今回の安全性確認は指定された地図とシード、および閉じたセルの点ロボットモデルに対する結果です。
ロボットの足跡を追加した判定、コスト積分、evaluate、Theta*、論文の変更は行っていません。
本実験前の並列化の小規模動作確認には検証用シード100を使い、その結果は本実験に含めていません。

## 実行コマンドと出力全文

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
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online && python3 -m tests.test_dstar && python3 -m tests.test_risk_prior && python3 -m tests.test_collision
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
```

実験:

```bash
cd conference && python3 experiments/exact_los.py
```

正常終了しました。実験全体の実測時間は 577.003 秒です。
この時間には、以下の報告用再集計・ファイル照合は含めません。

```json
{
  "total_s": 577.0028929479995,
  "workers": 5,
  "python": "3.12.14"
}
```

## 実験が表示した集計表（そのまま）

```text
A: unchanged paper planners
         paths  success  touching_paths  sampled_exposure
planner                                                  
TA*        120      1.0               0                 0
TA*-S      120      1.0               6                 0

A: saved-result mismatches (absolute tolerance 1e-9; timing excluded): 0

B: online replanning
                      success  touching_runs  sampled_exposure  dJ_median        dJ90  plans  plan_time
R_m cell_m exact_los                                                                                   
5   10     False          1.0              4                 2   7.136692   77.086729   63.5   2.071598
           True           1.0              0                 0   7.243856   55.675435   64.5   1.935636
    20     False          1.0              2                 1   9.307821  100.590234   72.5   1.864565
           True           1.0              0                 0   9.196318  100.990954   72.0   1.825377
10  10     False          1.0              4                 1   3.342535   25.303457   59.0   1.800411
           True           1.0              0                 0   3.444945   25.252449   60.0   1.838675
    20     False          1.0              2                 0   4.744195   57.084070   65.5   1.837842
           True           1.0              0                 0   4.794876   57.185062   66.0   1.852687
15  5      False          1.0              2                 0   1.497122    5.704775   48.0   2.181050
           True           1.0              0                 0   1.499733    5.869762   49.0   2.295193

B: saved coarse mismatches (absolute tolerance 1e-9; timing excluded): 0

B: trajectories touching lethal cells:
 R_m  cell_m    kind  side_m  seed  exact_los  lethal_cells
  10      10 craters     100     0      False             1
   5      10 craters     100     7      False             2
  10      20   hills      50     1      False             1
  15       5   hills     100     9      False             1
   5      20   ridge     100     3      False             1
   5      10   rocky      50     6      False             1
   5      20   rocky      50     7      False             2
  10      10   rocky     100     0      False             2
  15       5   rocky     100     0      False             2
   5      10   rocky     100     3      False             3
  10      10   rocky     100     4      False             1
  10      10   rocky     100     5      False             1
  10      20   rocky     100     6      False             2
   5      10   rocky     100     7      False             1

failures: {}
```
