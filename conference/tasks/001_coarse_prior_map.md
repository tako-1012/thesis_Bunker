# 指示書 001：粗い全体地図を使った、走りながらの再計画

> **状態：完了**（Codex が実装、Claude がレビュー済み。PR #4 で `realtime-map` に取り込み）
> 結果は `conference/results/online_prior/` を参照。
> 尾根で抜け道を探して迷う問題がほぼ解消した（経路長の理想比：+19.4% → −0.2%）。
> 一方で、再計画の回数は 19回 → 48回 に増えた。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`。

## 背景
`conference/tapp/online.py` は、ロボットがセンサーの届く範囲の地形しか知らない状態で、
走りながら経路を計画し直すシミュレーションです。見えていない場所には、一定のコスト、
または「適応的」なコスト（それまでに見た地形の平均）を使っています。
結果（`conference/results/online/`）から、次の弱点がわかっています。
尾根のマップでは抜け道が見えず、大きく回り道してしまう
（例：尾根・100m・シード7で、地図をすべて知っていれば95mのところを216m走る）。

実際には、**粗い全体地図**（国の測量や衛星による5mや10m間隔の標高データなど）が手に入ることが多いです。
この指示書の目的は、その粗い地図を見えない場所の推定に使い、近くはセンサーの詳しい情報で上書きすることです。

## 実装するもの

### 1. 新しいファイル `conference/tapp/prior.py`
```python
def coarse_prior(tmap, cell_m, z_noise_m=0.0, seed=0) -> PriorMap
```
- 正しい標高 `tmap.elev`（解像度 `tapp.config.RESOLUTION` = 0.5m）を、`cell_m`（5.0m か 10.0m）ごとの
  **ブロック平均**で粗くする。ブロックの大きさは round(cell_m / 0.5) マス。端の半端なブロックも平均する。
  その後、**双線形補間**で元の0.5m間隔（`tmap.elev` と同じ大きさ）に戻す。
- `z_noise_m` が指定されたら、**粗い**マスごとに独立なガウス雑音を足してから補間する
  （乱数は `np.random.default_rng(seed)`）。
- 岩は粗い地図には写らない（小さすぎるため）。
- 戻した標高から、`tapp/traversability.py` とまったく同じ式で、傾斜・凸凹・コストを計算する
  （岩をすべて False にして `TraversabilityMap` を使い、`tmap` と同じ `robot`・`weights` を渡す）。
- `PriorMap`：`cost`（実数の配列）、`lethal`（粗い地図で傾斜が限界を超える場所の真偽配列）、
  `cell_m` を持つ小さな dataclass。

### 2. `conference/tapp/online.py` の `run_online` を拡張
既定値では今までと**まったく同じ**動きになる、2つのキーワード引数を追加する。
```python
prior_map=None, prior_lethal="soft"
```
- `prior_map is None` のとき：今までと同じ動き（下の回帰テストで確認）。
- それ以外のとき：見えていない場所には、一定値や適応的な値の代わりに `prior_map.cost` を使う。
  このとき `unknown_cost` は無視する。
- `prior_lethal`：
  - `"hard"`：粗い地図で通れない（`prior_map.lethal`）見えていない場所を、通行禁止として扱う
  - `"soft"`：通行禁止にはせず、コストを 1.0（最大値）にする
  - `"ignore"`：`prior_map.cost` だけを使う
- 再計画のきっかけ：残りの経路上で新しく見えたマスが、次のどれかに当てはまったら再計画する。
  - 実際に通れない
  - 実際のコストが、そのマスに**想定していたコスト**（粗い地図のコスト、soft なら 1.0）より 0.05 以上高い
  - hard モードで「通れない」と想定していたマスが、実は通れた（近道が開く可能性があるため）
- 再計画のつなぎ目の修正（現在いるマスの中心を経由する）はそのまま残す。
- 戻り値では、今と同じく `n_plans`、`plan_time`、`max_plan_time` も返す。

### 3. 実験スクリプト `conference/experiments/online_prior.py`
`conference/experiments/online_replanning.py` と同じ構成・同じ集計の形式にする
（コピーして書き換える。元のファイルは変更しない）。
テスト用シード `range(10)`、地形 `tapp.terrain.TERRAIN_TYPES`、マップの大きさ (50, 100)。
センサーの届く距離 15m、`w=DEFAULT_W`、プランナー `"TA*-S"`。比べる条件：

| 名前 | 設定 |
|---|---|
| `oracle TA*-S` | 地図をすべて知っている（`run_planner("TA*-S", ...)`） |
| `oracle A*` | `run_planner("A*", ...)`（エネルギーの基準） |
| `online adaptive` | `unknown_cost="adaptive"`（これまでの最良、粗い地図なし） |
| `online prior5 soft` | `coarse_prior(tm, 5.0)`、`prior_lethal="soft"` |
| `online prior5 hard` | `coarse_prior(tm, 5.0)`、`prior_lethal="hard"` |
| `online prior10 soft` | `coarse_prior(tm, 10.0)`、`prior_lethal="soft"` |
| `online prior5 soft noisy` | `coarse_prior(tm, 5.0, z_noise_m=0.5, seed=<シナリオのシード>)`、soft |

結果は `conference/results/online_prior/online_prior.csv` に保存する。
`online_replanning.py` と同じ集計表を表示し、`online_prior_log.txt` にも保存する。
- 全体の中央値：成功率、急斜面を通った割合、理想（oracle TA\*-S）比の経路長とエネルギー、
  A\* 比のエネルギー、傾斜の95%値、再計画の回数、計画時間、計画時間の最大値
- マップの大きさ別
- **地形別**（理想比の経路長）
- 失敗の一覧とその理由

並列化には `multiprocessing.Pool` を使う。

### 4. 図 `conference/experiments/demo_online_prior.py`
`demo_online.py` をコピーし、尾根・100m・シード7について次の4つを表示する。
地図をすべて知っている場合、`online adaptive`、`online prior5 soft`、`online prior10 soft`。
保存先は `conference/results/online_prior/demo_online_prior_ridge_7.png`（`paper/` の下には置かない）。

## テスト：新しいファイル `conference/tests/test_online.py`（`python3 -m tests.test_online` で実行）
1. **回帰テスト**：`build("ridge", 100, 0)` と `build("ridge", 100, 7)` で、
   `run_online(..., planner="TA*-S", unknown_cost="adaptive", sense_radius_m=15.0, w=8.0)`
   （`prior_map=None`）を実行したとき、`evaluate(traj)["length_xy"]` が
   154.688509 と 215.530174（誤差 1e-6 以内）、`n_plans` が 81 と 103 になること。
2. **正しい地図を与えた場合**：正しい `tmap.cost`・`tmap.lethal` から直接作った `PriorMap`
   （`coarse_prior` は使わない）を `prior_lethal="hard"` で渡したとき、
   走った距離が `run_planner("TA*-S", ...)` の 2% 以内になること
   （地形4種類それぞれ1シナリオ、50m、シード0）。
3. **粗い地図の確認**：`coarse_prior(tm, 5.0)` の出力が `tm.elev` と同じ大きさであること。
   `cell_m=0.5` のとき、粗い地図のコストが、岩なしで計算した `tm.cost` と一致すること（誤差 1e-9 以内）。
4. **安全性**：3節のすべての条件について、尾根とクレーター・50m・シード0〜4で、
   走った軌跡が実際に通れない場所に入らないこと
   （`evaluate(...)["steep_len"] == 0` かつ `rock_hit` が False）。

## 完了の条件
- `python3 -m tests.test_planners` と `python3 -m tests.test_online` が通る。
- `python3 experiments/online_prior.py` が最後まで動き、CSV・ログ・図ができている。
- 変更禁止のファイル（`AGENTS.md` を参照）が変わっていない。
  `git diff --stat realtime-map` に出るのは、新しいファイルと `conference/tapp/online.py` だけ。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告がついている。

## 対象外
D\* Lite などの増分探索、遮蔽（丘の裏が見えないこと）の考慮、論文の変更。
