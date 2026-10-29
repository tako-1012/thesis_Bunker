# 指示書 004：線分の通行判定を正確にする（マスの角のかすめを見落とさない）

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
`tapp/planners.py` の `line_of_sight(blocked, a, b, step=0.25)` は、線分の上を 0.25 マスおきに点で調べています。
このため、線分が通行禁止のマスの**角をわずかにかすめる**場合を見落とします。
指示書003の実験（`conference/results/risk_prior/README_ja.md` の「安全性の制約と切り分け」）では、
オンラインの 1200 走行のうち 14 走行で、走った軌跡が通行禁止のマスに入っていました。
Claude が再現した例（クレーター・100m・シード0、R=10m、粗い地図 10m、`coarse`）では、軌跡の長さ 2 マスの線分が、
傾斜 25.7° のマス (103, 127) の角をかすめていました（マスの中を通る長さは約 0.03 マス = 1.5cm）。

この指示書の目的は次の2つです。
1. 線分が触れるマスを**すべて**調べる、正確な判定を用意する。
2. その判定を使えば、走りながらの再計画でも通行禁止のマスに一度も入らないことを確かめる。

既存の結果（論文を含む）は 1ビットも変えないこと。新しい判定は、新しい引数で選んだときだけ使う。

## 実装するもの

### 1. 新しいファイル `conference/tapp/collision.py`
```python
def segment_cells(a, b, shape) -> np.ndarray        # (k, 2) の int 配列
def line_of_sight_exact(blocked, a, b) -> bool
def path_lethal_cells(path, blocked) -> np.ndarray   # 折れ線全体で触れた通行禁止マス（重複なし、(k, 2)）
```
- 座標はマス単位で、マス (i, j) は閉じた正方形 `[i−0.5, i+0.5] × [j−0.5, j+0.5]` とする（`np.rint` の約束と同じ）。
- `segment_cells`：線分 a–b と**共通部分を持つ**すべてのマスを返す。辺や角に触れるだけのマスも含める
  （今の `line_of_sight` の ±eps の考え方と同じく、安全側にする）。地図の外のマスは除く。
  浮動小数の誤差に備えて、判定には許容誤差 `1e-9` マスを使ってよい（安全側、つまりマスを含める側に使うこと）。
- 実装の方法は自由（Amanatides–Woo の格子走査を、角を通る場合も含むように拡張したもの、
  または外接長方形の中のマスごとに線分と正方形の交差を判定する方法など）。どちらにしたかを PR に書くこと。
- `line_of_sight_exact`：`segment_cells` のどれかが `blocked` なら False。
- `path_lethal_cells`：評価用。`evaluate` は 0.1m おきの点で調べるので、これも角のかすめを見落としうる。
  そこで、軌跡（折れ線）の各線分の `segment_cells` を合わせて、`blocked` のマスを返す。

### 2. 新しい判定を選べるようにする（この指示書で、次の2ファイルの変更を許可する）
- `conference/tapp/planners.py` の `smooth_cost_aware` に、キーワード引数 `los=None` を追加する。
  None なら今までどおり `line_of_sight` を使う。関数が渡されたらそれを使う。
  `planners.py` のそれ以外の変更は禁止。
- `conference/tapp/online.py` の `run_online` に、キーワード引数 `exact_los=False` を追加する。
  True のときは、次の3か所すべてで正確な判定を使う。
  1. 平滑化：`smooth_cost_aware(..., los=line_of_sight_exact)`
  2. 再計画のつなぎ目：`line_of_sight(known & tm.lethal, pos, rest[0])` を `line_of_sight_exact` にする
  3. 再計画のきっかけ：残りの経路上で新しく見えたマスを調べるところ（今は線分あたり `ceil(L·2)` 個の点で調べている）。
     ここでは `segment_cells` で得たマスを使う。通行禁止の判定とコストの判定の両方で使うこと。
  False のときは、今までと**まったく同じ**動きにする（下のテスト3で確認する）。
  `search="dstar_lite"` のときも、`exact_los` は同じように働くようにする。

### 3. 実験スクリプト `conference/experiments/exact_los.py`
結果は `conference/results/exact_los/` に置く。

**(A) 論文の経路の点検（計算し直しはしない。既存のプランナーをそのまま実行して調べるだけ）**
- `experiments/run_all.py` の本実験（E1 main）と同じシナリオ（`build(kind, side, seed)`、地形4種類、
  大きさ 50・100・200m、シード `range(10)`）で、`run_planner("TA*", ...)` と `run_planner("TA*-S", ...)` を
  `w=DEFAULT_W` で実行する。
- 各経路について、`path_lethal_cells(path, tm.lethal)` の数と、`evaluate` の `steep_len`・`rock_hit` を記録する。
- 経路長などが `conference/results/test_results.csv` の同じ行と一致することも確認し、一致しない行の数を表示する
  （一致しない場合は、その理由を PR に書くこと）。

**(B) 走りながらの再計画**
- 指示書003と同じ5条件（R, 粗い地図の間隔）=`(15,5)`、`(10,10)`、`(10,20)`、`(5,10)`、`(5,20)`。
  地形4種類、大きさ 50・100m、シード `range(10)`、`planner="TA*-S"`、`w=DEFAULT_W`、`coarse_prior(tm, cell)`、
  `prior_lethal="soft"`。
- 各シナリオで `exact_los=False` と `exact_los=True` の両方を実行する。
- 記録するもの：成功したか、`path_lethal_cells(traj, tm.lethal)` の数、`steep_len`、`rock_hit`、
  dJ（指示書003と同じ定義 `J = length_xy·(1+w·mean_cost)`、理想 `oracle TA*-S` との比 [%]）、再計画の回数、計画時間。
- `exact_los=False` の結果は、指示書003の `risk_prior.csv` の `coarse` の行と一致するはず。一致しない行の数を表示する。

表示して `exact_los_log.txt` にも保存する集計表：
- (A)：プランナーごとに、通行禁止のマスに触れた経路の数（`path_lethal_cells` が1つ以上）と、`steep_len > 0` または
  `rock_hit` の経路の数
- (B)：条件ごと・`exact_los` ごとに、成功率、通行禁止のマスに触れた走行の数、`steep_len > 0` または `rock_hit` の走行の数、
  dJ の中央値と 90% 値、再計画の回数の中央値、計画時間の中央値
- (B)：触れた走行の一覧（条件、地形、大きさ、シード、`exact_los`、触れたマスの数）

並列化には `multiprocessing.Pool` を使う。

## テスト：新しいファイル `conference/tests/test_collision.py`（`python3 -m tests.test_collision` で実行）
1. **`segment_cells` の正しさ**：シードを固定した乱数で作った 2000 本の線分（端点は 20×20 の格子の中、
   一部は端点がマスの中心・辺・角にちょうど乗るようにする）について、`segment_cells` の結果が、
   総当たりの基準（20×20 のすべてのマスについて、線分と閉じた正方形が交わるかを、分離軸の定理で判定する）と一致すること。
   長さ 0 の線分（a = b）も含めること。
2. **見落としの再現と修正**：角をわずかにかすめる線分で、`line_of_sight` は True、`line_of_sight_exact` は False になること。
   背景の例をずらした次の座標を使うこと：6×6 の格子で通行禁止のマスは (3, 2) だけ、
   a = (1.19286796, 1.77048902)、b = (3.15312682, 1.37377099)
   （線分がマス (3, 2) に入る部分の長さは約 0.03 マス。Claude が確認済み：`line_of_sight` は True、
   `step=0.001` にすると False）。
3. **回帰テスト**：`exact_los` を指定しない場合、指示書001・002・003のテストの値と一致すること。
   - `build("ridge", 100, 7)`、`coarse_prior(tm, 5.0)`、`prior_lethal="soft"`：`length_xy` = 95.218208（誤差 1e-6）、`n_plans` = 67
   - `build("craters", 100, 0)`、R=10m、`coarse_prior(tm, 10.0)`、soft：`steep_len` = 0.0997987（誤差 1e-6）。
     これは、今の判定で見落としが起きることを記録するテストである。
   - 論文の平滑化：`build("hills", 100, 0)` で `run_planner("TA*-S", ...)` の経路が、`los` を指定しない場合と
     `los=line_of_sight` を渡した場合でまったく同じになること。
4. **安全性**：`exact_los=True` で、`build("craters", 100, 0)`・R=10m・`coarse_prior(tm, 10.0)`・soft の走行が、
   `path_lethal_cells(traj, tm.lethal)` で 0 個になること。また、尾根とクレーター・50m・シード0〜4、
   R=5m と 15m、`search="astar"` と `"dstar_lite"` でも 0 個になること。
5. 既存のテスト（`tests.test_planners`、`tests.test_online`、`tests.test_dstar`、`tests.test_risk_prior`）がすべて通ること。

## 完了の条件
- 5つのテストファイルがすべて通る。
- `python3 experiments/exact_los.py` が最後まで動き、CSV とログができている。
- 変更してよい既存ファイルは、`conference/tapp/planners.py`（`smooth_cost_aware` の `los` 引数だけ）と
  `conference/tapp/online.py`（`exact_los` 引数だけ）。それ以外の既存ファイルは変更しない。新しいファイルの追加は可。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- (A) で、論文の TA\* と TA\*-S の経路に、通行禁止のマスに触れたものがあったかどうか。**あった場合も、そのまま報告する**こと
  （論文は変更しない。Claude が判断する）。
- (B) で、`exact_los=True` にしても通行禁止のマスに触れた走行が残った場合、その例と、わかる範囲での理由。
- `exact_los=True` にしたことによる計画時間の増え方と、dJ・再計画の回数の変化。

## 対象外
`lazy_theta`（Theta\*）と `tapp/terrain_baselines.py` の判定の変更、`segment_cost`（コストの積分）の変更、
`evaluate` の変更、ロボットの大きさ（足跡）を考えた判定、論文の変更。
