# 指示書 017：「見えない陰」を入れたセンサーの模擬で、走りながらの再計画を確かめ直す

> **状態：未着手**。最初に `AGENTS.md` と `conference/tasks/BATCH_RULES_ja.md` を読むこと。ブランチは `codex/017-visibility`。

## 背景
これまで、センサーは「ロボットのまわり半径 R の地形が、すべて誤差なく見える」とみなしてきた（`tapp/online_mission.virtual_sense`）。
実際の LiDAR では、砂丘や漂着物の**陰になった場所は見えない**。修論の限界として必ず聞かれるので、陰を入れた模擬で結果が変わるかを確かめる。

## 作るもの
新しいファイル `conference/tapp/visibility.py`：
```python
def visible_cells(elev, pos_cell, radius_m, sensor_height_m=0.8) -> np.ndarray   # bool、見えるマス
def virtual_sense_los(truth_tm, pos_cell, radius_m, sensor_height_m=0.8) -> (mask, cost, lethal)   # virtual_sense と同じ形
```
- 見える条件：ロボットの位置の地面から `sensor_height_m` 上にあるセンサーから、マスの地面（中心）への線分が、途中の地形より上を通ること
  （途中のマスの標高と比べる。マスは `tapp.collision.segment_cells` と同じ考え方で拾ってよい）。半径 R の外は見えない。
- 漂着物（`rock`）は、標高に高さを足して扱う。`build_real` の漂着物に高さの情報がなければ、仮定の高さ（例：0.3m）を使い、仮定と書く。
- `sensor_height_m = 0.8` は仮定（BUNKER の上にセンサーを載せた高さの目安）。0.5・0.8・1.2m を比べる。
- **見えないマスは「まだ知らない」扱い**（事前の地図か、平均のコストを使う。`OnlinePlanner` の今の扱いのまま）。

## 実験：`conference/experiments/online_visibility.py`（結果は `conference/results/online_visibility/`）
- 指示書014と同じシナリオ（点群の砂浜の `test` 48 か所、200m、5 点）。事前の地図は `coarse c10` と `stale`、半径 10m。
- センサー：今の「半径 R がすべて見える」と、陰あり（高さ 0.5・0.8・1.2m）。
- 集計（指示書014と同じ形）：完走、`too_long`、通れない場所に触れた走行の数、dJ、計画し直した回数、計画時間。
  さらに、1 回の観測で見えたマスの割合（半径の中のうち、見えた割合）の中央値。
- **大事なのは**：陰があっても、通れない場所に触れないか（触れたら、どこで、なぜか）。dJ がどれだけ悪くなるか。

## テスト：`conference/tests/test_visibility.py`
1. 平らな地形では、半径の中のマスがすべて見える。
2. 高い壁の向こうのマスは見えず、手前は見える（人工の小さな地形で作ってよい）。
3. センサーを高くすると、見えるマスが減らない（同じ地形・同じ位置で）。
4. `virtual_sense_los` の戻り値の形が `virtual_sense` と同じ。

## 報告：`conference/results/online_visibility/REPORT_ja.md`
集計表。陰ありで通れない場所に触れた場合は、その例の図と理由。「半径 R がすべて見える」との違いを、修論の限界の節で使える形で短くまとめる。
