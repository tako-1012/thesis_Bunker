# 指示書 003：粗い地図の不確かさを、ロボットの限界で正規化した地形コストに入れる

> **状態：完了（負の結果）**（Codex が実装、Claude がレビュー済み。PR #13 で `realtime-map` に取り込み）
> 結果は `conference/results/risk_prior/` を参照。検証用シードで選ばれた λ は 0 で、5条件すべてで `coarse` より悪化した。
> 毎ステップ再計画しても悪化は残るので、原因は再計画の減少ではなく、区間ごとの平均で空間的な情報が失われたことと考える。
> 副産物として、`line_of_sight` が 0.25 マス間隔の点検査のため、マスの角をかすめるのを見落とすことがわかった。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景と目的
この研究の中心は、ロボットの限界（傾斜 25°、凸凹 0.10m）で正規化した地形コスト
`c = α·min(傾斜/θmax, 1) + β·min(凸凹/ρsat, 1)` を使う TA\* です。
指示書001では、見えない場所のコストに、粗い全体地図（`tapp/prior.py` の `coarse_prior`）から**そのまま**
計算した `c` を使いました。しかし粗い地図はブロック平均でなめらかになるので、

- 傾斜を**小さく**見積もる（急な場所を見落とす）
- 凸凹と岩はほとんど写らない

という、**向きの決まった誤差**があります。検証用シード（`range(100, 105)`）で予備的に確かめたところ、
センサーの届く距離を 5m・10m に縮め、地図を 10m・20m 間隔に粗くすると、中央値の差は小さいものの、
地形コストの平均が理想（地図をすべて知っている TA\*-S）より 4〜10% 高くなりました。
また、最悪の場合には、経路長が理想より 30% 以上長くなりました。再計画も 70回前後と多くなりました。

この指示書では、見えない場所のコストを、**粗い地図の値から推定した「本当のコストの期待値」と
「実は通れない確率」**に置き換えます。どちらも検証用の地図で較正します。
これは、TA\* の「ロボットの限界で正規化したコスト」を、不確かな地図の場合に広げるものです。

## 実装するもの

### 1. `conference/tapp/prior.py` の小さな整理（この指示書で変更を許可する）
`coarse_prior` の中の「ブロック平均 → 雑音 → 双線形補間」の部分を、新しい関数
```python
def coarse_elevation(tmap, cell_m, z_noise_m=0.0, seed=0) -> np.ndarray
```
として切り出し、`coarse_prior` はそれを呼ぶだけにする。入力の確認（`ValueError`）は `coarse_elevation` に移す。
**`coarse_prior` の出力は 1ビットも変えないこと**（下のテスト1と、既存の `tests.test_online` で確認する）。
`prior.py` のそれ以外の変更は禁止。

### 2. 新しいファイル `conference/tapp/risk_prior.py`
```python
@dataclass
class Calibration:
    cell_m: float
    edges_deg: list      # 粗い地図の傾斜の区切り [度]
    mean_cost: list      # 区間ごとの、本当の c の平均
    p_lethal: list       # 区間ごとの、本当に通れない（tmap.lethal：急斜面または岩）マスの割合
    counts: list         # 区間ごとのマス数

def calibrate(cell_m, seeds=range(100, 105), sizes=(50, 100), kinds=None) -> Calibration
def risk_prior(tmap, cell_m, calib, lam, z_noise_m=0.0, seed=0) -> PriorMap
```
- **`calibrate`**：`kinds` が None なら `tapp.terrain.TERRAIN_TYPES` のすべて。各 `build(kind, size, seed)` の地図で、
  `coarse_elevation(tm, cell_m)` から `tapp.traversability.slope_deg` で粗い地図の傾斜 ψ̂ を計算する。
  ψ̂ の区間ごとに、地図の**すべてのマス**について、本当の `tm.cost` の平均と、`tm.lethal` の割合を集計する。
  地形の種類は区別せずにまとめる（ロボットは地形の種類を知らないため）。
  - 区切り：`edges_deg = [0, 2.5, 5, ..., 25, 90]`（2.5° 刻み、25° 以上は1つの区間）。
  - マスが1つもない区間は、その区間より小さい側で一番近い、空でない区間の値を使う。それもなければ大きい側の値を使う。
  - `seeds` に `range(10)` の値が1つでも入っていたら `ValueError`（テスト用シードで較正しないため）。
- **`risk_prior`**：`coarse_elevation(tmap, cell_m, z_noise_m, seed)` から ψ̂ を計算する。
  各マスの区間 b について、次のように計算する。
  ```
  cost = clip(mean_cost[b] + lam * p_lethal[b], 0, 1)
  ```
  `lethal` は `coarse_prior(tmap, cell_m, z_noise_m, seed).lethal` とまったく同じものにする。
  `PriorMap(cost=cost, lethal=lethal, cell_m=cell_m)` を返す。
  - `lam = 0` は「期待値だけ」の版。`lam > 0` は「通れない確率の分だけ、安全側に見積もる」版。
  - `run_online` はそのまま使う（`prior_map=risk_prior(...)`）。`run_online` も `online.py` も変更しないこと。
- 較正の結果は、`conference/results/risk_prior/calibration_<cell_m>.json` に保存し、読み込む関数も用意する。
  実験スクリプトは、この JSON を毎回作り直してよい。

### 3. 実験スクリプト `conference/experiments/risk_prior.py`
`conference/experiments/online_prior.py` と同じ構成・集計の形式にする（コピーして書き換える。元は変更しない）。
共通の設定は、`planner="TA*-S"`、`w=DEFAULT_W`、`prior_lethal="soft"`、`search="astar"`（既定値）。

**比べる条件（センサーの届く距離 R、粗い地図の間隔）：**
`(15, 5)`（指示書001と同じ）、`(10, 10)`、`(10, 20)`、`(5, 10)`、`(5, 20)`。単位は m。

**手順 A：λ を決める（検証用シード `range(100, 105)` だけを使う）**
- 地図の大きさは 50m と 100m、地形は4種類すべて、上の5つの条件すべてで実験する。
- `lam ∈ {0, 0.25, 0.5, 1.0, 2.0}` について、`risk_prior` を使った再計画を実行する。
- 評価には、TA\* が最小化している量に近い値として、走った軌跡の
  `J = length_xy · (1 + w · mean_cost)`（`evaluate` の出力から計算）を使う。
  理想（`oracle TA*-S`）の J との比を `dJ = 100·(J/J_oracle − 1)` [%] とする。
- 全条件・全シナリオをまとめた dJ の中央値が一番小さい `lam` を選ぶ。同点なら、再計画の回数の中央値が
  少ない方を選ぶ。それでも同点なら、小さい方の `lam` を選ぶ。
- 選んだ値は、`conference/results/risk_prior/selected_lambda.json` に保存する。
  `lam` ごとの dJ の中央値の表は `risk_prior_lambda_log.txt` に保存する。

**手順 B：本実験（テスト用シード）**
- シードは `range(10)`、地図の大きさは 50m と 100m、地形は4種類すべて、上の5つの条件すべてで実験する。
- 各シナリオで、次の手法を比べる。

| 名前 | 設定 |
|---|---|
| `oracle TA*-S` | 地図をすべて知っている（`run_planner("TA*-S", ...)`） |
| `oracle A*` | `run_planner("A*", ...)`（エネルギーの基準） |
| `coarse` | `coarse_prior(tm, cell)`（指示書001の方法） |
| `calibrated mean` | `risk_prior(tm, cell, calib, lam=0)` |
| `risk λ*` | `risk_prior(tm, cell, calib, lam=<手順Aで選んだ値>)` |

- 較正には、手順Aと同じ検証用シードの `Calibration` を使う。テスト用シードで較正し直さないこと。

結果は `conference/results/risk_prior/risk_prior.csv` に保存する。
表示して `risk_prior_log.txt` にも保存する集計表は次のとおり。
- 条件ごと・手法ごとの中央値：成功率、急斜面を通った割合、dJ、理想比の経路長（dL）とエネルギー（dE）、
  A\* 比のエネルギー、傾斜の95%値、再計画の回数、計画時間
- 条件ごと・手法ごとの**悪い側の値**：dJ と dL の 90% 値と最大値
- 条件ごと・地形別の dJ の中央値
- **統計**：条件ごとに、`coarse` と `risk λ*` の dJ について、同じシナリオどうしで対応のある Wilcoxon 検定を行う
  （`scipy.stats.wilcoxon`、両側）。5つの条件の p 値には Holm の補正をかける。
  効果量として、順位双列相関 r も表示する。`conference/experiments/analyze.py` の `holm` と `paired_test` を
  import して使うこと（`analyze.py` は変更しない）。
  `calibrated mean` と `coarse` についても同じように検定する。
- 失敗の一覧とその理由

並列化には `multiprocessing.Pool` を使う。

## テスト：新しいファイル `conference/tests/test_risk_prior.py`（`python3 -m tests.test_risk_prior` で実行）
1. **整理の確認**：4種類の地形、50m、シード0で、`cell_m ∈ {5.0, 10.0}`、`z_noise_m ∈ {0, 0.5}` のすべてについて、
   `coarse_elevation` から作った `TraversabilityMap`（岩はすべて False）の `cost` と `lethal` が、
   `coarse_prior` の出力と `np.array_equal` で一致すること。
2. **較正の確認**：
   - `counts` の合計が、使った地図のマス数の合計と等しいこと。
   - `p_lethal` が [0, 1] に入っていること。
   - 同じ引数で2回呼ぶと、まったく同じ結果になること。
   - JSON に保存して読み込んでも同じになること。
   - `seeds` に 0 を含めると `ValueError` になること。
   （テストの時間を短くするため、地図を `sizes=(50,)`、`kinds=("hills",)` などに絞ってよい）
3. **コストの確認**：`lam=0` のときの `cost` が、区間ごとの `mean_cost` と一致すること。
   `lam` を大きくすると、どのマスでも `cost` が減らないこと。値が [0, 1] に入っていること。
   `lethal` が `coarse_prior` の `lethal` と一致すること。
4. **安全性**：`risk_prior` を使った `run_online`（`lam=0` と `lam=1.0`、R=5m と 15m）で、尾根とクレーター・50m・
   シード0〜4のとき、走った軌跡が実際に通れない場所に入らないこと（`steep_len == 0` かつ `rock_hit` が False）。

既存のテスト（`tests.test_planners`、`tests.test_online`、`tests.test_dstar`）もすべて通ること。

## 完了の条件
- 4つのテストファイルがすべて通る。
- `python3 experiments/risk_prior.py` が最後まで動き、CSV・JSON・ログができている。
- 変更してよいのは `conference/tapp/prior.py`（1節の整理だけ）。それ以外の既存ファイルは変更しない。
  新しいファイルの追加は可。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- **`risk λ*` が `coarse` より良くならなかった条件も、そのまま報告する**こと。
  λ や区間の区切りを、テスト用シードの結果を見てから変えないこと。
- 手順Aで選ばれた λ と、`lam` ごとの dJ の表。
- 較正の表（区間ごとの `mean_cost`、`p_lethal`、`counts`）。5m・10m・20m のそれぞれについて書く。
- 実行にかかった時間。

## 対象外
遮蔽（丘の裏が見えないこと）の考慮、D\* Lite での実験（`search="dstar_lite"` は使わない）、
地形の種類ごとの較正、論文の変更、横傾きを考慮した版（`tapp/aniso.py`）。
