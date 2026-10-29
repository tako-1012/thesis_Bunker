# 指示書 002：D* Lite（増分探索）による再計画の高速化

> **状態：完了**（Codex が実装、Claude がレビュー済み。PR #9 で `realtime-map` に取り込み）
> 結果は `conference/results/online_dstar/` を参照。
> 経路は A\* とすべてのシナリオで一致した（正しさの確認）。
> 50m・100m では Python のオーバーヘッドで A\* より遅いが、200m では計画時間の合計が 26〜54% 短くなった。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
`conference/tapp/online.py` の `run_online` は、再計画のたびに A\*（`tapp.planners.astar`）で
**ゼロから**経路を探し直しています。指示書001で粗い全体地図（`tapp/prior.py`）を使うと、
迷う問題は解消しましたが、再計画の回数が 19回 → 48回 に増えました
（`conference/results/online_prior/`）。

D\* Lite（Koenig & Likhachev, 2002）は、地図の変わった部分だけを計算し直す増分探索です。
再計画の計算を軽くし、200m 四方以上の地図でも実時間で動くことを示すのが、この指示書の目的です。

**注意：** D\* Lite が効くのは、見えない場所のコストが固定のとき（粗い地図、または一定値）です。
`unknown_cost="adaptive"` は、観測するたびに見えない場所全体のコストが変わるので、D\* Lite では扱わない
（指定されたらエラーにする）。

## 実装するもの

### 1. 新しいファイル `conference/tapp/dstar_lite.py`
TA\* と**まったく同じグラフ**の上で動く D\* Lite を実装する。
- 8方向の格子。斜め移動は、隣り合う2つの直交マスのどちらかが通行禁止なら不可（角のすり抜け禁止）。
- 辺のコスト：`d * 0.5 * (m_u + m_v)`（`d` は 1 か √2、`m` はマスごとの割増率 `1 + w * c`）。
  `tapp.planners.astar` の `mult` 付きの場合と同じ式。
- ヒューリスティック：現在のロボット位置とのユークリッド距離（マス単位）。割増率は 1 以上なので許容的。
- 探索はゴールから逆向き（D\* Lite の標準形）。ロボットが動いたら `k_m` を更新する（Koenig & Likhachev の最適化版）。

最低限、次のインターフェースを持つクラスにする（名前は変えてよいが、PR に書くこと）。
```python
class DStarLite:
    def __init__(self, blocked, mult, start, goal): ...   # blocked: bool 配列, mult: 実数配列
    def update_cells(self, cells, blocked, mult): ...     # 値が変わったマスの一覧と、新しい配列全体
    def move_start(self, start): ...                      # ロボットの新しい位置（マス）
    def compute(self): ...                                # 最短経路の再計算。統計（展開数・時間）を返す
    def path(self): ...                                   # 現在位置からゴールまでのマスの列（なければ None）
    @property
    def cost(self): ...                                   # 現在位置の g 値（= 最小コスト、マス単位）
```
- あるマスの `blocked` や `mult` が変わると、そのマス自身と周囲8マスから出る辺が変わる
  （斜め移動の「角のすり抜け禁止」の判定を含む）。`update_cells` では、変わったマスとその周囲8マスの
  頂点を更新すること。
- `path()` は、現在位置から「辺のコスト + 隣の g」が最小の隣へ順にたどる。同点のときの選び方は
  決まった順（`NBRS` の順）にして、結果が実行ごとに変わらないようにする。
- Python の `heapq` を使い、優先度の更新は「古い要素を無視する」方式でよい（`tapp/planners.py` と同じ流儀）。

### 2. `conference/tapp/online.py` の `run_online` を拡張
既定値では今までと**まったく同じ**動きになる、キーワード引数を追加する。
```python
search="astar"   # または "dstar_lite"
```
- `search="dstar_lite"` のとき：
  - `unknown_cost="adaptive"` かつ `prior_map is None` ならエラー（`ValueError`）。
  - 最初の計画で `DStarLite` を作る。以降、観測で計画用の地図（`planning_maps()` の
    `lethal` と `mult`）が変わったマスだけを `update_cells` に渡し、ロボットの位置を `move_start` で伝える。
  - 再計画のきっかけ（いつ計画し直すか）は、A\* の場合とまったく同じにする。
  - 経路を得た後の平滑化（TA\*-S の `smooth_cost_aware`）は、A\* の場合と同じものを使う。
  - `plan_time` には、D\* Lite の更新・再計算・経路の取り出し・平滑化の時間をすべて含める。
- A\*-HC（`planner="A*-HC"`）での D\* Lite 対応は不要（指定されたら `NotImplementedError`）。

### 3. 実験スクリプト `conference/experiments/online_dstar.py`
`conference/experiments/online_prior.py` と同じ構成・集計の形式にする（コピーして書き換える。元は変更しない）。
テスト用シード：50m と 100m は `range(10)`、200m は `range(5)`（時間の都合）。地形は4種類すべて。
センサーの届く距離 15m、`w=DEFAULT_W`、プランナー `"TA*-S"`、粗い地図は `coarse_prior(tm, 5.0)`、`prior_lethal="soft"`。

| 名前 | 設定 |
|---|---|
| `oracle TA*-S` | 地図をすべて知っている（`run_planner("TA*-S", ...)`） |
| `oracle A*` | `run_planner("A*", ...)`（エネルギーの基準） |
| `A* prior5` | `search="astar"`（= 指示書001の `online prior5 soft`） |
| `D*Lite prior5` | `search="dstar_lite"`、再計画のきっかけは A\* と同じ |
| `A* prior5 every-step` | `search="astar"`、`replan_every_m=1.0`（毎ステップ計画し直す）※50m と 100m のみ |
| `D*Lite prior5 every-step` | `search="dstar_lite"`、`replan_every_m=1.0` |

結果は `conference/results/online_dstar/online_dstar.csv` に保存する。
表示して `online_dstar_log.txt` にも保存する集計表：
- 全体の中央値：`online_prior.py` と同じ列（成功率、急斜面を通った割合、理想比の経路長とエネルギー、
  A\* 比のエネルギー、傾斜の95%値、再計画の回数、計画時間、計画時間の最大値）
- **マップの大きさ別の計算時間**：1回あたりの計画時間の中央値、1回の計画時間の最大値、1回の走行全体の
  計画時間の合計の中央値
- 同じシナリオでの `A* prior5` と `D*Lite prior5` の**経路長の差**（中央値と最大値）

並列化には `multiprocessing.Pool` を使う。計算時間を比べるので、手法ごとの計算時間の測り方は揃えること。

## テスト：新しいファイル `conference/tests/test_dstar.py`（`python3 -m tests.test_dstar` で実行）
1. **静的な一致**：`tests/test_planners.py` と同じようなランダムな格子（大きさ25、障害物の割合20%、
   割増率 1〜6）20通りで、`DStarLite` の `cost` が `astar(blocked, s, g, mult)` の最小コストと一致する
   （誤差 1e-9。`astar` の `cost` は m 単位なので、マス単位に直して比べること）。到達不能なら両方が失敗すること。
2. **動的な一致**：ランダムな格子で、「ランダムなマスのコストや通行禁止を変える → ロボットを経路上で数歩
   進める → `compute`」を20回くり返す。毎回、`cost` が、その時点の地図と現在位置から
   ゼロから計算した `astar` の最小コストと一致すること（誤差 1e-9）。これを複数のシードで行う。
3. **回帰テスト**：`search` を指定しない（= `"astar"`）場合、指示書001の結果と一致すること。
   - `build("ridge", 100, 7)`、`coarse_prior(tm, 5.0)`、`prior_lethal="soft"`：
     `length_xy` = 95.218208（誤差 1e-6）、`n_plans` = 67
   - `build("hills", 100, 2)`、`coarse_prior(tm, 5.0)`、`prior_lethal="hard"`：
     `length_xy` = 85.493375（誤差 1e-6）、`n_plans` = 60
4. **安全性**：`search="dstar_lite"`（通常と every-step の両方）で、尾根とクレーター・50m・シード0〜4のとき、
   走った軌跡が実際に通れない場所に入らないこと（`steep_len == 0` かつ `rock_hit` が False）。
5. **エラー処理**：`search="dstar_lite"` で `unknown_cost="adaptive"`（粗い地図なし）を指定したら
   `ValueError` になること。

既存のテスト（`tests.test_planners`、`tests.test_online`）もすべて通ること。

## 完了の条件
- `python3 -m tests.test_planners`、`python3 -m tests.test_online`、`python3 -m tests.test_dstar` が通る。
- `python3 experiments/online_dstar.py` が最後まで動き、CSV とログができている。
- 変更禁止のファイル（`AGENTS.md` を参照）が変わっていない。変更してよいのは `conference/tapp/online.py` だけ
  （新しいファイルの追加は可）。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- D\* Lite が **A\* より速くならなかった場合も、そのまま報告する**こと。数値を良く見せるために
  条件を変えたり、テスト用シードで調整したりしないこと。
- `A* prior5` と `D*Lite prior5` で経路が違った場合、その理由（同じコストの経路が複数あるときの選び方の違い、など）
  を、わかる範囲で書くこと。

## 対象外
遮蔽（丘の裏が見えないこと）の考慮、論文の変更、横傾きを考慮した版（`tapp/aniso.py`）への D\* Lite の対応。
