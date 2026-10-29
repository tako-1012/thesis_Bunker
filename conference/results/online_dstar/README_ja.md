# D* Lite による粗い事前地図付きオンライン再計画

最新の `realtime-map`（土台: `76c7888`）から実装しました。変更した既存ファイルは
`conference/tapp/online.py` だけです。既存の全 conference ファイルの SHA-256 を照合し、
このファイル以外に変更がないことを確認しました。保護されたソース、論文、既存結果は変更していません。

## 実装

- `tapp/dstar_lite.py` の `DStarLite`: ゴールから逆向きに探索する D* Lite。
  TA* と同じ辺コスト、8近傍、角抜け禁止、移動時の `k_m` 更新を使います。
  コスト増加・減少、障害物の追加・除去に対応し、変わったマスと周囲8マスを更新します。
  優先度キューは heapq と古い要素の無視で管理し、経路抽出の同点は NBRS 順で決めます。
  インターフェースは指示書どおり `update_cells`、`move_start`、`compute`、
  `path`、`cost` です。`cost` はマス単位です。
- `tapp/online.py`: `search="astar"` を既定値とし、`search="dstar_lite"` を追加。
  再計画のきっかけ、平滑化、現在のセル中心を経由する接続処理は共通です。
  粗地図なしの adaptive は ValueError、A*-HC は NotImplementedError です。
- 公平な計時と既存動作の維持のため、追加引数 `record_plan_times=False` を設けました。
  既定値では既存 A* の返却フィールドと計時範囲を保ち、True のときだけ
  `plan_times` に各呼び出しの実測値を返します。
- `experiments/online_dstar.py`: 指定された全地形、サイズ、シード、手法を
  multiprocessing.Pool で実行し、CSV と表示結果と同一のログを保存します。
- `tests/test_dstar.py`: 静的・動的な最小コストの一致、角抜け禁止、コスト減少、
  到達不能と再開通、移動・同点処理、タスク001の回帰、安全性、エラー処理、
  計時記録の整合性を検査します。

## 計時と結果の解釈

オンラインの A* と D* Lite は、計画用配列を作った直後から、経路抽出・平滑化が終わるまでの
同じ区間を測定しています。D* Lite の初期化、変化したセルの検出・更新、再計算も含めます。
センサー処理、共通の計画用配列の作成、軌跡の実行は両方とも含めません。
実験CSVの plan_time と max_plan_time は、この共通区間の実測値の合計と最大値です。
各呼び出しの値を JSON の plan_times 列にも保存し、1回あたりの中央値は
合計時間を回数で割った推定値ではなく、全呼び出しの実測値から計算します。
既定の4プロセスで計測しました（実行環境の利用可能CPUは5）。
Python 3.12.14、NumPy 2.3.5、SciPy 1.17.0、pandas 2.2.3 を使用しています。

**全体では D* Lite は A* より速くなりませんでした。**
通常再計画の合計計画時間の中央値は、A* の 2.229 秒に対して D* Lite は 3.843 秒です。
一方、200m の通常再計画では、A* の 23.690956 秒に対して D* Lite は 16.321694 秒で、
この条件では時間短縮を確認しました。50m と100mでは通常・毎ステップとも合計時間の中央値が増えています。
結果を見て条件やパラメータを変更していません。

通常再計画の全100組と、同じサイズで比較できる毎ステップ再計画の80組について、
CSVの経路長の差の最大絶対値はどちらも0.0m、再計画回数の差があった組も0件でした。
したがって今回、比較可能な組での経路長の違いは観測していません。
全軌跡の座標列を保存して照合したわけではないので、座標列そのものの完全一致までは主張しません。
一般には逆向き探索・同点選択・平滑化を通じて経路や後続の観測範囲が変わり得ます。

200m の D* Lite 通常再計画での1回の最大時間は 2.153783 秒でした。
本実験はシミュレーションであり、実機の周期・走行速度に対する実時間性は未検証です。
また A* 毎ステップ再計画は指示どおり200mでは実行していないため、その条件との比較はできません。
全体集計の毎ステップ手法間では対象サイズが異なるため、性能比較にはサイズ別の表を使ってください。
oracle A* は急斜面を禁止しないエネルギー参照です。安全性は制約付きのオンライン手法で評価しています。

実験完了後に580行・100シナリオ・指定手法の網羅と一意性、全件成功、
全オンライン実行での急斜面・岩への接触なし、計時記録の件数・合計・最大値、
表示ログとの一致、各ファイルが5MB未満であることを確認しました。

## 実行コマンドとテスト出力全文

変更前:

```bash
cd conference && python3 -m tests.test_planners && python3 -m tests.test_online
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
```

変更後（指定の3テスト）:

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

実験:

```bash
cd conference && python3 experiments/online_dstar.py
```

最後まで正常終了しました。テスト用シードでのパラメータ調整はしていません。
本実験前のCSV・集計処理の確認には検証用シード100を使い、その出力は本実験の結果には含めていません。

## 実験が表示した集計表（そのまま）

```text
                          succ  steep_exposed  dL_oracle  dE_oracle   dE_A   cost  slope95  plans  plan_time  max_plan
variant                                                                                                               
oracle A*                  1.0           0.73     -3.146      7.485  0.000  0.298   25.234    1.0      0.023     0.323
oracle TA*-S               1.0           0.00      0.000      0.000 -6.964  0.160    9.439    1.0      0.146     1.998
A* prior5                  1.0           0.00     -0.405     -0.245 -7.019  0.167    9.558   58.0      2.229     2.191
D*Lite prior5              1.0           0.00     -0.405     -0.245 -7.019  0.167    9.558   58.0      3.843     2.154
A* prior5 every-step       1.0           0.00     -0.631     -0.497 -7.995  0.170    9.776   76.0      1.906     0.885
D*Lite prior5 every-step   1.0           0.00     -0.552     -0.417 -6.973  0.167    9.641   83.0      4.565     1.913

per size (planning times [s], median over individual calls):
                                 call_median_s  call_max_s  total_median_s
variant                  side_m                                           
oracle A*                50           0.010264    0.019271        0.010264
                         100          0.033127    0.282853        0.033127
                         200          0.134137    0.323359        0.134137
oracle TA*-S             50           0.083880    0.163166        0.083880
                         100          0.177814    0.515262        0.177814
                         200          0.729563    1.997819        0.729563
A* prior5                50           0.023836    0.139460        0.643419
                         100          0.039172    0.539408        2.849275
                         200          0.137487    2.191117       23.690956
D*Lite prior5            50           0.076301    0.230582        1.838923
                         100          0.067823    0.545084        4.466410
                         200          0.104709    2.153783       16.321694
A* prior5 every-step     50           0.016638    0.135393        0.880487
                         100          0.033275    0.885229        3.664887
                         200               NaN         NaN             NaN
D*Lite prior5 every-step 50           0.060730    0.446186        2.424687
                         100          0.057371    0.535991        5.205266
                         200          0.094362    1.913122       18.655943

paired path length difference (D*Lite prior5 - A* prior5 [m]):
        pairs  dL_median_m  abs_dL_median_m  abs_dL_max_m
side_m                                                   
all       100          0.0              0.0           0.0
50         40          0.0              0.0           0.0
100        40          0.0              0.0           0.0
200        20          0.0              0.0           0.0

A* prior5 every-step is not run at 200 m (NaN above).

failures: {}
```

