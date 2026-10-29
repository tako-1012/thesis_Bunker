# 指示書 008：地形を考慮して、複数の地点を回る順番と経路を決める

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景と目的
海岸清掃ロボットでは、人が地図の上で選んだ**複数の地点**（ごみの場所など）を回って、スタート地点（基地）に戻ります。
地図はすでにある（すべて知っている）とします。
ふつうは、地点の間の**直線距離**で回る順番を決めます。しかし砂浜や丘では、地点の間の本当の移動コストは地形で変わります。
さらに、**登りは下りよりエネルギーを使う**ので、「A→B」と「B→A」のコストが違います（非対称）。

この指示書では、次の2つを比べます。
- **直線距離で順番を決める方法**（基準）
- **地形を考慮した、向きのあるコストで順番を決める方法**（提案）

どちらの場合も、決まった順番の各区間は、同じ地形考慮のプランナーで走ります。違いは**順番の決め方だけ**です。

**既存のファイルは変更しないこと。** すべて新しいファイルに作る。

## 向きのあるコスト
TA\* の辺のコスト `d · 0.5 · (m_u + m_v)`（`m = 1 + w·c`、マス単位）に、**登った高さの分**を足す。
```
cost(u→v) = d · 0.5 · (m_u + m_v) + κ · max(z_v − z_u, 0) / RESOLUTION
```
- `κ = 1 / robot.rolling_coeff`（今の設定では 1/0.15 ≈ 6.67）とする。
  理由：`tapp/metrics.py` のエネルギーは `m·g·(μ·L + 登った高さ)` に比例する。つまり 1m 登ることは、
  平らな所を 1/μ m 走ることと同じエネルギーになる。**この値は物理から決まるので、調整しない。**
- `κ = 0` のとき、TA\* とまったく同じになる。
- 下りは 0 として扱う（下りでエネルギーが戻るとは考えない）。
- 足す項は 0 以上なので、ユークリッド距離のヒューリスティックはそのまま許容的。

## 実装するもの

### 1. 新しいファイル `conference/tapp/directional.py`
```python
def astar_dir(blocked, elev, start, goal, mult, kappa, max_expansions=10_000_000) -> dict
def dijkstra_dir(blocked, elev, source, mult, kappa) -> (dist, parent)   # 1点から全マスへ（地点が多いときに速くするため）
def path_from_parent(parent, source, target) -> list
def segment_cost_dir(mult, elev, a, b, kappa) -> float   # 直線区間の向きのあるコスト（マス単位）
def smooth_dir(path, blocked, mult, elev, kappa) -> (path, time)
def plan_leg(sc, a, b, w=DEFAULT_W, kappa=0.0) -> dict  # 1区間の計画：astar_dir（または dijkstra_dir の結果）→ smooth_dir
```
- `astar_dir` は `tapp.planners.astar` と同じ書き方（8方向、角のすり抜け禁止、`heapq` で古い要素を無視する方式）にする。
  `kappa=0` のとき、`astar(blocked, s, g, mult)` と**同じコスト**になること（テストで確かめる）。
- `smooth_dir` は `smooth_cost_aware` と同じ考え方（貪欲に近道を試す）で、判定に `tapp.collision.line_of_sight_exact` を使う。
  近道は、`segment_cost_dir` で測った**向きのあるコストが増えない**ときだけ採用する。
  `segment_cost_dir` は、`tapp.planners.segment_cost` と同じ点の取り方で、`mult` の積分に、点の列で登った高さの合計 × κ を足す。
- `plan_leg` の戻り値：`path`（マス座標の列）、`cost_dir`（向きのあるコスト、マス単位）、`success`、`time`。

### 2. 新しいファイル `conference/tapp/tour.py`
```python
def sample_waypoints(sc, n, seed, min_sep_m=5.0) -> list          # 通れるマスからランダムに n 点
def cost_matrix(sc, points, w=DEFAULT_W, kappa=0.0) -> dict        # 向きのあるコストの行列と、各区間の経路
def euclid_matrix(points) -> np.ndarray
def solve_tour(C, start_index=0) -> (order, cost)                  # 厳密解（Held–Karp の動的計画法）。非対称な行列に対応する
def tour_legs(order) -> list                                      # 回る順の区間の一覧（最後にスタートへ戻る）
```
- **地点の選び方**：`sc["tmap"].lethal` でない（水・岩・陸側の帯を含まない）マスから、乱数（`np.random.default_rng(seed)`）で選ぶ。
  ほかの地点やスタートと `min_sep_m` 以上離れていること、スタートから `astar(tm.lethal, ...)` で行けることを確かめる。
  乱数のシードは `np.random.SeedSequence([シナリオのシード, 3000, side_m, 種類の番号])` から作る。
- **巡回**：スタート（`sc["start"]`）から出て、全地点を1回ずつ回り、スタートに戻る。
- **`cost_matrix`**：(n+1)×(n+1) の行列（0 番がスタート）。各行の始点から1回 `dijkstra_dir` を回し、各終点への
  経路を取り出して `smooth_dir` をかける（区間ごとに `astar_dir` を回すのと同じ結果になることをテストで確かめる）。
  対角は 0、行けない組は無限大。
- **`solve_tour`**：地点数 12 まで（行列の大きさ 13）は Held–Karp で厳密に解く。同じコストの順番が複数あるときは、
  辞書順で最も小さい順番を選ぶ（結果が実行ごとに変わらないようにする）。

### 3. 実験スクリプト `conference/experiments/multi_goal_tour.py`
結果は `conference/results/multi_goal_tour/` に置く。

**シナリオ**：`tapp.beach_scenario.build_beach`、5種類すべて（`beach_gentle`、`beach_steep`、`beach_scarp`、`rolling`、`hills`）、
大きさ 100m と 200m、テスト用シード `range(10)`。各シナリオで 12 点を選び、その最初の 5 点・8 点・12 点の3通りで実験する。
`w = DEFAULT_W`。

**比べる順番の決め方**（区間の走り方は、どれも `plan_leg(..., kappa=κ_run)` で同じにする）

| 名前 | 順番を決める行列 | 区間を走るプランナー |
|---|---|---|
| `euclid` | 直線距離 | κ_run = 1/μ |
| `terrain sym` | κ = 0 の向きのあるコスト（= TA\* のコスト。対称） | κ_run = 1/μ |
| `terrain dir` | κ = 1/μ の向きのあるコスト（非対称）＝**提案** | κ_run = 1/μ |
| `terrain dir / TA*-S legs` | κ = 1/μ で順番を決め、区間は κ_run = 0（TA\*-S exact と同じ） | κ_run = 0 |

**評価**：決めた順番で、区間の経路をつないだ巡回全体について、`tapp.metrics.evaluate` で次を測る。
- 向きのあるコストの合計（κ = 1/μ で測る。「この巡回にかかる地形とエネルギーのコスト」）
- エネルギー（`terrain dir` に対する %。kJ の値は表に出さない）、経路長、登った高さ、横傾き（`p95_roll`）、急斜面を通った長さ
- 計算時間：行列を作る時間、順番を解く時間
- `terrain dir` と比べた、各方法の向きのあるコストの差 [%]

**表示して `multi_goal_tour_log.txt` に保存する集計表**
- 地点数ごと・方法ごとの中央値と 90% 値（`terrain dir` に対するコストとエネルギーの差 [%]、経路長、登った高さ）
- 地形の種類ごと・地点数ごとの、`euclid` に対する `terrain dir` のコストの差の中央値
- **順番が変わった割合**：`euclid` と `terrain dir` の順番が違ったシナリオの割合。`terrain sym` と `terrain dir` の順番が違ったシナリオの割合
- **非対称の大きさ**：行列の各組の `|C_ij − C_ji| / (C_ij + C_ji)` の中央値と 90% 値（地形の種類ごと）
- 統計：地点数ごとに、`euclid` 対 `terrain dir`、`terrain sym` 対 `terrain dir` の向きのあるコストについて、
  対応のある両側 Wilcoxon 検定（`experiments/analyze.py` の `paired_test` と `holm`。Holm の補正は表全体でかける）
- 計算時間（行列、順番の解）の中央値と最大値
- 1つのシナリオ（`beach_steep`・200m・シード 0・12 点）について、`euclid` と `terrain dir` の巡回を地図に重ねた図
  `tour_example.png`（背景は傾斜と水・通れない場所。地点に番号を振る）

並列化には `multiprocessing.Pool` を使う。

## テスト：新しいファイル `conference/tests/test_tour.py`（`python3 -m tests.test_tour` で実行）
1. **κ=0 の一致**：`tests/test_planners.py` と同じようなランダムな格子 20 通りで、`astar_dir(..., kappa=0)` のコストが
   `astar(blocked, s, g, mult)` のコストと一致すること（`astar` は m 単位なので換算する。誤差 1e-9）。
2. **向きのあるコストの正しさ**：小さな格子（例 6×6）で、すべての経路を調べる総当たりと、`astar_dir` の最小コストが
   一致すること（κ > 0、標高はランダム、10 通り）。`dijkstra_dir` の距離が、各終点への `astar_dir` のコストと一致すること。
3. **非対称**：一様な斜面（標高 = x 方向に一定の勾配）で、上り方向の区間のコストが下り方向より `κ × 高さの差 / RESOLUTION`
   だけ大きいこと（誤差 1e-9）。
4. **Held–Karp**：地点数 2〜8 のランダムな非対称行列 30 通りで、`solve_tour` の結果が、全順列の総当たりと同じコストになること。
   同点の扱いが決まっていること（同じ入力で2回解くと同じ順番）。
5. **地点の選び方**：選んだ地点が通れるマスにあり、互いに `min_sep_m` 以上離れ、スタートから行けること。同じシードで同じ地点になること。
6. **安全性**：`plan_leg` の経路が、`path_lethal_cells(path, tm.lethal)` で 0 個であること（砂浜3種類・100m・シード 0・5 点の全区間）。
7. 既存のテストがすべて通ること。

## 完了の条件
- すべてのテストが通る。
- `python3 experiments/multi_goal_tour.py` が最後まで動き、CSV・ログ・図ができている。
- 既存のファイルは1つも変更しない。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- `terrain dir` が `euclid` や `terrain sym` より良くならなかった場合も、そのまま書く。
- 順番が変わった割合と、非対称の大きさ（地形の種類ごと）。平らな地形では差が小さいはずなので、その確認も書く。
- 計算時間（とくに 200m・12 点の行列を作る時間）。
- 実験にかかった時間。

## 対象外
走りながら順番を組み直すこと、潮の満ち引き、乾いた砂と濡れた砂のコストの違い、13 点以上の近似解法、論文の変更。
これらは次の指示書以降で行う。
