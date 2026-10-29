# 指示書 009：本物の砂浜（静岡県・遠州灘）で、計画・再計画・巡回を確かめる

> **状態：完了**（Codex が実装。Claude が砂浜データの誤りを直して実験をやり直した）。結果は `conference/results/real_beach/README_ja.md`。
> TA\*-S の利点は本物の砂浜でも成り立った。走りながらの再計画は、人工の砂浜より理想との差が大きかった（中央値 2.6〜19.5%）。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
指示書007で人工の砂浜を作り、008で複数地点の巡回を調べました。人工の地形だけでは「本物に合わせて作っただけ」と
言われるので、**本物の砂浜の標高データ**でも同じことを確かめます。
`conference/data/shizuoka_beach/` に、静岡県の航空レーザ測深データ（0.5m）から切り出した遠州灘の砂浜 60 か所
（200m 四方）があります。まず `conference/data/shizuoka_beach/README_ja.md` を読むこと（向き・NaN・出典・分け方）。
**このデータとそのフォルダは変更しないこと。** ネットワークからのダウンロードも不要。

**既存のファイルは変更しないこと。** すべて新しいファイルに作る。
パラメータ（`w` など）は今までの値のまま使い、調整しない。もし何か決める必要があれば、`split == "validation"` の
12 か所だけを使うこと（`test` の 48 か所の結果を見て変えないこと）。

## 実装するもの

### 1. 新しいファイル `conference/tapp/real_beach.py`
```python
def list_patches(split=None) -> list           # index.json の行（split で絞り込める）
def load_patch(name) -> np.ndarray             # elev（NaN を含む）
def build_real(name, side_m, seed, debris=False, weights=CostWeights(), robot=Robot(), max_tries=20) -> dict
```
- **切り出し**：`side_m = 200` はパッチ全体。`side_m = 100` は、海岸線に沿う向き（x）の始まりを乱数で選び
  （0〜100m）、海から陸への向き（y）は −20〜80m（配列の 60〜259 行目）とする。
- **通れない場所**：
  - データのないマス（NaN）：通れない。傾斜の計算のために、NaN は一番近いデータのあるマスの値で埋めてから
    `TraversabilityMap` を作る（`scipy.ndimage.distance_transform_edt(..., return_indices=True)` を使う）。
  - 海：標高 0m（T.P.）未満のマス。通れない。
  - これらをまとめて `TraversabilityMap(elev_filled, nodata | water | debris_rock, robot, weights)` の
    2 番目の引数に渡す（指示書007の水と同じ扱い。ロボットの半径の分だけ膨らむ）。
- **漂着物**（`debris=True` のときだけ）：流木と岩・ごみの塊を、指示書007（`tapp/beach_terrain.py`）と同じ規則で置く。
  ただし、置く帯は「標高 0.3〜2.5m（満潮線からバームの頂上の高さの範囲）に多く、それより陸側に少なく」とする。
  `beach_terrain.py` に使える関数があれば import して使う。なければ同じ規則を新しいファイルに書く（どちらにしたかを PR に書く）。
- **スタートとゴール**：`tapp.terrain.sample_start_goal` と同じく、左の帯から右の帯へ（海岸線に沿って移動する）。
  シードは `np.random.SeedSequence([seed, 4000, side_m, パッチの番号])` から作る（パッチの番号は `index.json` の順番）。
  `astar(tm.lethal, s, g)` で解けるまで作り直す（`build_natural` と同じ手順）。
- 返す辞書は `build_beach` と同じ形にする（`tmap`、`start`、`goal`、`kind`（= パッチの名前）、`side_m`、`seed`、`redraws`、
  `water`、`nodata`）。

### 2. 実験スクリプト `conference/experiments/real_beach.py`
結果は `conference/results/real_beach/` に置く。シナリオは **`test` の 48 か所 × 大きさ 100m・200m × シード 0**
（漂着物なし）と、同じものに漂着物を置いたもの（`debris=True`）。プランナーは `TA*-S exact`（`tapp.exact_planners.run_planner_exact`）を使う。

**(A) 本物と人工の比較**（地形の自然さの確認）
本物の砂浜（`validation` と `test` の両方）と、指示書007の人工の砂浜（`beach_gentle`、`beach_steep`、`beach_scarp`、200m、
検証用シード `range(100, 105)`）について、次の値を並べて表示する。
- 陸（データがあり、標高 0m 以上）の傾斜の 50・90・99% 値、25°を超える割合
- 前浜の勾配（標高 0〜2m のマスの、陸への向きの勾配の中央値）
- 陸の幅（海岸線から、通れない帯またはデータのない所まで）
- 凸凹（`rough`）の中央値、動径平均したパワースペクトルの傾き
- 通れない場所の割合（海・データなしを除く）
人工の砂浜の値が、本物の 10〜90% の範囲から外れている項目を、表の下に一覧で表示する。

**(B) 地図をすべて知っている場合の計画**：指示書007の (B) と同じプランナー・同じ集計（横傾きを含む。エネルギーは A\* 比の % だけ）。
漂着物なし・ありを分けて表示する。

**(C) 走りながらの再計画**：指示書007の (C) と同じ7条件・同じ集計（`exact_los=True`。粗い地図は `coarse_prior` で、本物の地形を
ブロック平均したもの）。漂着物なし・ありを分けて表示する。dJ が 25% を超えた走行の一覧と、最大 10 件の図。

**(D) 複数地点の巡回**：指示書008の実験を、本物の砂浜（200m、漂着物なし・あり）で行う。地点数 5・8・12、方法は
`euclid`、`terrain sym`、`terrain dir`（008 と同じ定義・同じ評価）。地点のシードは
`np.random.SeedSequence([0, 3000, 200, パッチの番号])` から作る。

表示した集計表を `real_beach_log.txt` に保存する。並列化には `multiprocessing.Pool` を使う。

## テスト：新しいファイル `conference/tests/test_real_beach.py`（`python3 -m tests.test_real_beach` で実行）
1. **データの読み込み**：60 か所すべてが読め、大きさが 400×400、`validation` が 12 か所・`test` が 48 か所であること。
2. **向き**：各パッチで、x に沿って平均した断面の標高が、y = −50m 側（海）で 0 未満、y = 0〜50m のどこかで 0 を超えること。
3. **シナリオ**：`build_real` が、`test` の最初の 5 か所・100m と 200m で解ける地図を返すこと。スタートとゴールが通れる場所にあり、
   海・データなしのマスが `lethal` に含まれること。同じ引数で2回作ると同じ地図・同じスタートとゴールになること。
4. **漂着物**：`debris=True` で、漂着物のマスが標高 0m 以上の陸にだけあり、`debris=False` のときより `lethal` が増えること。
5. **安全性**：`run_planner_exact("TA*-S", ...)` の経路と、`exact_los=True` の `run_online`（`coarse R5 c10`）の軌跡が、
   `test` の最初の 5 か所・100m で `path_lethal_cells(..., tm.lethal)` が 0 個であること。
6. 既存のテストがすべて通ること。

## 完了の条件
- すべてのテストが通る。
- `python3 experiments/real_beach.py` が最後まで動き、CSV・ログ・図ができている。
- 既存のファイルと `conference/data/` は1つも変更しない。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- (A) で、人工の砂浜が本物から外れていた項目（そのまま書く）。
- (B)〜(D) で、人工の砂浜（指示書007・008）の結果と比べて、同じ傾向だったか、違ったか。
- 論文や発表で使うときの出典の書き方（`README_ja.md` の出典をそのまま使う）。
- 各実験にかかった時間。

## 対象外
本物の 5m・10m 標高データ（国土地理院）を粗い地図に使うこと、濡れた砂と乾いた砂、潮の満ち引き、論文の変更。
