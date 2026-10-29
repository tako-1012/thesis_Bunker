# 指示書 005：粗い地図のコストに「通れない確率」を上乗せする（指示書003の作り直し）

> **状態：保留（Codex には渡していない）**
> Claude の予備実験（検証用シード）では、上乗せしても dJ はほとんど良くならなかった。
> また、悪い走行の多くは人工的な尾根のマップで起きていたため、先に自然な地形を作ることにした（指示書006）。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
指示書003では、見えない場所のコストを、粗い地図の傾斜の区間ごとの「本当のコストの平均」で**置き換え**ました。
その結果、5条件すべてで、粗い地図のコストをそのまま使う方法（`coarse`）より悪くなりました。
Claude の切り分け（検証用シード）では、毎ステップ再計画しても悪化は残りました。そこで、原因は次のことと考えています。
**区間ごとの平均に置き換えたことで、地図の細かい違い（どちらがより急か）が失われた。**

この指示書では、置き換えはしません。粗い地図のコストを**そのまま残し**、その上に「実は通れない確率」の分だけ
コストを上乗せします。
```
c_unknown = clip(c_coarse + λ · p_lethal(ψ̂), 0, 1)
```
- `c_coarse`：`coarse_prior(tm, cell).cost`（指示書001のコスト）
- `ψ̂`：粗い地図の傾斜（`slope_deg(coarse_elevation(tm, cell))`）
- `p_lethal`：指示書003で検証用シードから較正した、ψ̂ の区間ごとの「本当に通れないマスの割合」
  （`conference/results/risk_prior/calibration_<cell>.json`）

`λ = 0` のとき、`coarse` と**まったく同じ**になります。したがって、検証用シードで λ を選べば、
「今より悪くはならない（λ=0 が選ばれる）か、良くなるか」を調べる実験になります。

**今後の走りながらの実験では、指示書004の正確な判定（`exact_los=True`）を必ず使うこと。**

## 実装するもの

### 1. 新しいファイル `conference/tapp/additive_prior.py`
```python
def additive_prior(tmap, cell_m, calib, lam, z_noise_m=0.0, seed=0) -> PriorMap
```
- `base = coarse_prior(tmap, cell_m, z_noise_m, seed)`。
- `ψ̂ = slope_deg(coarse_elevation(tmap, cell_m, z_noise_m, seed))`。区間の割り当ては、`tapp/risk_prior.py` と
  まったく同じ規則にする（`risk_prior.py` の関数を import して使ってよい。`risk_prior.py` は変更しない）。
- `cost = clip(base.cost + lam * p_lethal[区間], 0, 1)`、`lethal = base.lethal`。
- `calib.cell_m != cell_m` なら `ValueError`。`lam` が有限の0以上でなければ `ValueError`。
- 較正は、`tapp.risk_prior.load_calibration` で `conference/results/risk_prior/calibration_<cell>.json` を読む。
  **較正し直さないこと。** 読み込んだものが `tapp.risk_prior.calibrate(cell_m)` の結果と一致することは、テストで確かめる。
  ファイル名は、指示書003で保存したものに合わせること（`calibration_5.json`、`calibration_10.json`、`calibration_20.json`）。

### 2. 実験スクリプト `conference/experiments/additive_prior.py`
`conference/experiments/risk_prior.py` と同じ構成・集計の形式にする（コピーして書き換える。元は変更しない）。
結果は `conference/results/additive_prior/` に置く。
共通の設定は、`planner="TA*-S"`、`w=DEFAULT_W`、`prior_lethal="soft"`、`search="astar"`、**`exact_los=True`**。
条件 (R [m], 粗い地図の間隔 [m]) は、指示書003と同じ `(15, 5)`、`(10, 10)`、`(10, 20)`、`(5, 10)`、`(5, 20)`。

**手順 A：λ を決める（検証用シード `range(100, 105)` だけを使う）**
- 地図の大きさは 50m と 100m、地形は4種類すべて、5条件すべて。
- `lam ∈ {0, 0.25, 0.5, 1.0, 2.0}`。
- 評価は、指示書003と同じ dJ（`J = length_xy·(1+w·mean_cost)`、`oracle TA*-S` との比 [%]）。
- **全条件をまとめた λ（1つ）** と、**条件ごとの λ（5つ）** の両方を選ぶ。
  選び方は指示書003と同じにする：dJ の中央値が最小のもの、同点なら再計画の回数の中央値が少ないもの、
  それでも同点なら小さい λ。
- 選んだ値を `selected_lambda.json` に保存する。`lam` ごとの dJ の中央値の表を、全体と条件ごとの両方について
  `additive_prior_lambda_log.txt` に保存する。

**手順 B：本実験（テスト用シード）**
- シードは `range(10)`、大きさは 50m と 100m、地形は4種類すべて、5条件すべて。

| 名前 | 設定 |
|---|---|
| `oracle TA*-S` | `run_planner("TA*-S", ...)` |
| `oracle A*` | `run_planner("A*", ...)` |
| `coarse` | `coarse_prior(tm, cell)` |
| `additive λ*` | `additive_prior(..., lam=<全条件をまとめて選んだ λ>)` |
| `additive λ*_cond` | `additive_prior(..., lam=<その条件で選んだ λ>)` |

- λ が 0 に選ばれた場合も、その手法を実際に実行すること（結果は `coarse` と同じになるはず。一致を確認して表示する）。

結果は `additive_prior.csv` に保存する。表示して `additive_prior_log.txt` にも保存する集計表は、指示書003の
`risk_prior_log.txt` と同じ構成にする。
- 条件ごと・手法ごとの中央値
- 悪い側の値（dJ と dL の 90% 値と最大値）
- 条件ごと・地形別の dJ の中央値
- 統計：条件ごとに、`additive λ*` − `coarse` と `additive λ*_cond` − `coarse` の dJ について、
  対応のある両側 Wilcoxon 検定（`experiments/analyze.py` の `paired_test` と `holm` を使う）。
  Holm の補正は、比較ごとに5条件で行う。差がすべて 0 の場合は検定できないので、「差なし」と表示する。
- 安全性：通行禁止のマスに触れた走行の数（`tapp.collision.path_lethal_cells(traj, tm.lethal)` が1つ以上）。
  手法ごと・条件ごとに表示する。
- 失敗の一覧とその理由

並列化には `multiprocessing.Pool` を使う。

## テスト：新しいファイル `conference/tests/test_additive_prior.py`（`python3 -m tests.test_additive_prior` で実行）
1. **λ=0 の一致**：4種類の地形、50m、シード0、`cell_m ∈ {5, 10, 20}`、`z_noise_m ∈ {0, 0.5}` で、
   `additive_prior(..., lam=0)` の `cost` と `lethal` が、`coarse_prior` の出力と `np.array_equal` で一致すること。
2. **上乗せの確認**：`lam` を大きくすると、どのマスでも `cost` が減らないこと。値が [0, 1] に入っていること。
   `cost − coarse_prior.cost` が、クリップされないマスで `lam · p_lethal[区間]` と一致すること（誤差 1e-12）。
3. **較正ファイルの確認**：`cell_m ∈ {5, 10, 20}` のそれぞれについて、`load_calibration` で読んだものが
   `calibrate(cell_m)` の結果と一致すること（`mean_cost` と `p_lethal` は誤差 1e-12、`counts` と `edges_deg` は完全一致）。
4. **エラー処理**：`cell_m` が較正と合わない場合、`lam` が負・NaN・無限大の場合に `ValueError` になること。
5. **安全性**：`exact_los=True` で、`additive_prior`（`lam=0` と `lam=1.0`）を使った `run_online` が、尾根と岩場・50m・
   シード0〜4、R=5m と 15m、`cell_m = 10` のとき、`path_lethal_cells(traj, tm.lethal)` で 0 個になること。
6. 既存のテスト（`tests.test_planners`、`test_online`、`test_dstar`、`test_risk_prior`、`test_collision`）がすべて通ること。

## 完了の条件
- 6つのテストファイルがすべて通る。
- `python3 experiments/additive_prior.py` が最後まで動き、CSV・JSON・ログができている。
- 既存のファイルは**1つも変更しない**（新しいファイルの追加だけ）。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- 手順Aで選ばれた λ（全体と条件ごと）と、`lam` ごとの dJ の表。
- **`additive` が `coarse` より良くならなかった条件も、そのまま報告する**こと。
  λ の候補や区間を、テスト用シードの結果を見てから変えないこと。
- 再計画の回数と計画時間の変化。
- 実行にかかった時間。

## 対象外
較正のやり直しや区間の変更、凸凹（粗さ）や岩の確率を別に推定すること、遮蔽、D\* Lite での実験、論文の変更。
