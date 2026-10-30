# 指示書 010：地図の上で地点を選び、巡回の経路を計画する Web 画面（ROS2 なしで動く版）

> **状態：完了**（PR #34）。起動のしかたは `conference/webui/README_ja.md`。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
海岸清掃ロボットでは、人が地図の上でごみの場所などを選び、ロボットがそれを回ります。
研究室には Android のアプリ（地図をタップして目的地を1つ置くだけ）がありますが、Android の端末が手元にないので、
**iPad やパソコンのブラウザから使える Web 画面**を作ります。
この指示書では、**ROS2 や Unity がなくても動く部分**（画面と計画のサーバー）だけを作ります。
ロボットに経路を送る部分（ROS2・Unity）は、次の指示書で行います。

計画には、これまでに作ったものをそのまま使います：
- 回る順番：`tapp/tour.py` の `cost_matrix`・`solve_tour`（指示書008）
- 区間の経路：TA\*-S exact と同じ考え方の `tapp/directional.py`（`kappa=0` で TA\*-S と同じコスト）
- 地図：人工の砂浜（`tapp/beach_scenario.build_beach`）、本物の砂浜（`tapp/real_beach.build_real`）

## この指示書だけの例外
- **FastAPI と uvicorn を使ってよい**（研究室の Android 用サーバーと同じ）。テストには FastAPI の `TestClient`（httpx）を使ってよい。
  `pip install fastapi uvicorn httpx` を README に書くこと。`conference/tapp/` の計算部分は今までどおり numpy・scipy だけにする。
- 画面の地図には **Leaflet 1.9.4**（BSD-2-Clause）を使う。**インターネットにつながらない現場でも動くように、
  `conference/webui/static/vendor/leaflet/` にファイルを置く**（CDN から読み込まない）。ライセンスの文書も一緒に置くこと。
- 既存のファイルは変更しないこと。

## 実装するもの

### 1. 新しいファイル `conference/tapp/mission.py`（計算部分。Web には依存しない）
```python
def list_maps() -> list                      # 選べる地図の一覧（id、表示名、大きさ）
def load_map(map_id) -> dict                 # シナリオの辞書（build_beach / build_real の結果）＋ id
def render_map_png(sc) -> bytes              # 地図の画像（下記）
def plan_mission(sc, start_xy, points_xy, method="terrain", w=DEFAULT_W) -> dict
```
- **地図の一覧**：
  - 人工の砂浜：`beach_gentle`・`beach_steep`・`beach_scarp`・`rolling`・`hills`、200m、シード 100（検証用）
  - 本物の砂浜：`validation` の 12 か所、200m
  - id は `synthetic/<種類>/200/100`、`real/<パッチ名>/200` の形にする。
  - 作ったシナリオは、同じ id ならキャッシュして使い回す。
- **座標**：画面とのやり取りは**メートル単位**の (x, y)。x は海岸線に沿う向き、y は海から陸への向き（`README_ja.md` と同じ）。
  マスへの変換は `round(x / 0.5)`。地図の外は拒否する。
- **地図の画像**：陰影図の上に、傾斜の色（25° 以上を赤）、水（青）、データなし（灰色）、通れない場所（赤の半透明）を重ねた PNG。
  1 マス = 1 画素。matplotlib で作ってよい。
- **`plan_mission`**：
  - 入力の地点を検査する：地図の外、通れないマスの上、スタートから行けない地点は、`rejected` に理由をつけて返し、残りで計画する。
  - 点の数は 1〜12 個（13 個以上は `ValueError`）。
  - `method="terrain"`：`cost_matrix(..., kappa=1/robot.rolling_coeff)` で向きのあるコストの行列を作り、`solve_tour` で順番を決める（指示書008の `terrain dir`）。
  - `method="euclid"`：直線距離の行列で順番を決め、区間は同じ `kappa` のプランナーで走る（指示書008の `euclid`）。
  - 戻り値：順番（入力の番号）、巡回全体の経路（メートル単位の点の列）、区間ごとの経路と長さ、
    巡回全体の `tapp.metrics.evaluate` の主な値（長さ、登った高さ、地形コストの平均、急斜面の長さ、横傾きの 95% 値、エネルギーは A\* に対する % ではなく**このままの値**で可）、
    `path_lethal_cells` の数（0 になるはず）、計算時間（行列・順番の解）、`rejected`。

### 2. 新しいファイル `conference/webui/server.py`（FastAPI）
| エンドポイント | 中身 |
|---|---|
| `GET /` | 画面（`static/index.html`） |
| `GET /api/maps` | 地図の一覧 |
| `GET /api/maps/{map_id}` | 地図の情報（大きさ [m]、解像度、スタートの位置） |
| `GET /api/maps/{map_id}/image.png` | 地図の画像 |
| `POST /api/plan` | `{map_id, start, points, method}` → `plan_mission` の結果（JSON） |

- 起動：`cd conference && python3 -m webui.server --host 0.0.0.0 --port 8080`。iPad からは `http://<パソコンの IP>:8080` で開ける。
- 計画は時間がかかる（200m・12 点で数十秒）ので、別のスレッドで計算して、画面を止めない。
  計算中に次の計画の依頼が来たら、前の計画を待たせずにエラー（HTTP 409）を返す（単純な方でよい）。

### 3. 新しいファイル `conference/webui/static/index.html`、`app.js`、`style.css`
- Leaflet の `L.CRS.Simple` で、地図の画像を**メートル単位**で表示する（拡大・縮小・移動ができる）。
- **地点の操作**：
  - 地図をタップ（クリック）すると地点が追加される。番号つきのマーカーにする。
  - マーカーはドラッグで動かせる。マーカーをタップすると、削除のボタンが出る。
  - スタート（基地）は別の形のマーカーで、ドラッグで動かせる。
  - **座標を直接入力する欄**もつける（`x, y` を 1 行に 1 点。貼り付けで一度に入力できる）。
  - 地点のリストを JSON で保存・読み込みできる（ブラウザのダウンロード・ファイル選択でよい）。
- **計画**：「順番の決め方」（地形を考慮 / 直線距離）を選んで「経路を計画」ボタン → 計算中の表示 → 経路を地図に描き、
  回る順番の番号をマーカーに表示する。結果の表（全体の長さ、登った高さ、地形コスト、急斜面の長さ、横傾き、計算時間、
  受け付けなかった地点と理由）を出す。
- 「両方を比べる」ボタン：2つの決め方で計画し、経路を色分けして重ね、表を並べる。
- 「再生」ボタン：ロボットのマーカーが経路に沿って動く（画面の中だけのアニメーション。速さは 1.388 m/s ＝ Android アプリと同じ 5 km/h）。
- **iPad の Safari で使えること**：タップで操作できる大きさのボタン（44px 以上）、縦横どちらの向きでも崩れない画面。
- 表示する文字は日本語にする。

### 4. README `conference/webui/README_ja.md`
起動のしかた、iPad からの開き方（同じネットワークにつなぐ、パソコンの IP の調べ方）、画面の使い方、
地図の出典（本物の砂浜を表示するときの静岡県のデータの出典）を書く。画面の下にも出典を表示すること。

## テスト：新しいファイル `conference/tests/test_mission.py`（`python3 -m tests.test_mission` で実行）
1. **地図**：`list_maps()` に人工 5 種類と本物 12 か所が入っていること。`render_map_png` が PNG（先頭が `\x89PNG`）で、
   大きさが地図のマス数と同じであること。
2. **計画の一致**：`plan_mission(method="terrain")` の順番と全体のコストが、同じ地点で `cost_matrix`・`solve_tour` を直接呼んだ結果と一致すること
   （人工の砂浜 1 枚、5 点）。`method="euclid"` の順番が、直線距離で `solve_tour` した結果と一致すること。
3. **地点の検査**：地図の外、水の上、通れない場所の地点が `rejected` に入り、残りの地点で計画されること。13 点で `ValueError`。
4. **安全性**：返ってきた巡回の経路の `path_lethal_cells` が 0 であること（人工 3 種類・本物 2 か所、ランダムな 5 点。シードは固定）。
5. **API**：`TestClient` で、`GET /api/maps`、`GET /api/maps/{id}`、`GET /api/maps/{id}/image.png`、`POST /api/plan` が正しく動くこと。
   不正な `map_id` で 404、地点 0 個で 422 になること。
6. 既存のテストがすべて通ること。

## 完了の条件
- すべてのテストが通る。
- `python3 -m webui.server` で起動し、ブラウザで地図の表示・地点の追加・計画・比較・再生ができる。
  **画面のスクリーンショット**（パソコンの幅と iPad の幅の2つ。ヘッドレスのブラウザで撮ってよい）を
  `conference/webui/screenshots/` に置き、PR に貼ること。
- 既存のファイルは1つも変更しない。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 対象外
ROS2・Unity・実機への経路の送信、GPS（緯度・経度）の地図、航空写真の背景、ログイン、複数人での同時利用。これらは次の指示書以降で行う。
