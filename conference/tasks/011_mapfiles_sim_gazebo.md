# 指示書 011：地図ファイル、経路の追従（Pure Pursuit）の模型、Gazebo 用の地形の書き出し

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
指示書010で、地図の上で地点を選び、巡回の経路を計画する Web 画面を作りました。次は、計画した経路を**ロボットに走らせる**ことです。
最終的には Ubuntu 24.04・ROS2 Jazzy・Gazebo（gz sim Harmonic）で BUNKER を走らせます（次の指示書）。
この指示書では、その前に **Mac だけ（ROS2・Gazebo なし）で確かめられる部分**を作ります。
1. **地図ファイル**：人工の地図と本物の砂浜を、1 枚ずつファイルに書き出す。Web 画面も Gazebo も、同じファイルを読み込む。
2. **経路の追従**：経路（点の列）を、ロボットの速度の指令に変える **Pure Pursuit** と、BUNKER の簡単な動きの模型（Python）。
   Web 画面で「計画した経路」と「実際に走った軌跡」を比べられるようにする。
3. **Gazebo 用の地形の書き出し**：地図ファイルから、Gazebo の world ファイル（高さ地図）を作る。

## この指示書で変更してよい既存ファイル
- `conference/tapp/mission.py`：地図ファイルを一覧に加えるため。**指示書010の地図の id とその結果は変えないこと**（`tests.test_mission` がそのまま通ること）。
- `conference/webui/` の中のファイル：地図ファイルの一覧と「走行のシミュレーション」を加えるため。
それ以外の既存ファイルは変更しない。FastAPI・uvicorn・httpx と、同梱の Leaflet は指示書010と同じく使ってよい。
`conference/tapp/` の計算部分は numpy・scipy だけにする（PNG の書き出しは matplotlib でよい）。

## 1. 地図ファイル

### 新しいファイル `conference/tapp/mapfile.py`
```python
def save_map(path, elev, *, resolution=0.5, obstacle=None, water=None, nodata=None, start_xy=None,
             name="", kind="", source="", attribution="")
def load_map_file(path, weights=CostWeights(), robot=Robot()) -> dict   # シナリオの辞書（build_beach などと同じ形）
def scenario_to_mapfile(sc, path, name, kind, source, attribution)       # 既存のシナリオから書き出す
```
- 形式は `np.savez_compressed`。中身：`elev`（float32、NaN 可）、`obstacle`・`water`・`nodata`（bool）、`resolution`、
  `start_xy`（m）、`name`・`kind`・`source`・`attribution`（文字列）、`format_version = 1`。
- 読み込みでは、NaN を一番近いデータのある値で埋めた標高から `TraversabilityMap(elev_filled, obstacle | water | nodata, robot, weights)` を作る
  （`tapp/real_beach.py` と同じ扱い）。返す辞書には `tmap`、`start`（マス）、`goal`（`None`）、`name` などを入れる。
- **元のシナリオと完全に同じ地図になること**：`scenario_to_mapfile` で書き出して `load_map_file` で読んだ `tmap.cost`・`tmap.lethal` が、
  元のシナリオと `np.array_equal` で一致すること（テストで確かめる）。そうなるように、元のシナリオの通れない場所の内訳
  （岩・漂着物、水、データなし）を正しく書き出すこと。

### 新しいスクリプト `conference/data_prep/export_maps.py` と、地図のフォルダ `conference/maps/`
次の地図を書き出す（ファイル名は `<種類>_<大きさ>m_<シード>.npz` など、わかりやすく）。
| 地図 | 中身 |
|---|---|
| `flat_test` | 平らな 100m 四方。真ん中付近に箱の形の障害物を 3 つ（動作確認用） |
| 人工の地図 | `beach_gentle`・`beach_steep`・`beach_scarp`・`rolling`・`hills`。100m と 200m、シード 100（検証用） |
| 本物の砂浜 | `conference/data/shizuoka_beach/` の `validation` 12 か所、200m（`build_real(..., 200, 0)`）。出典を `attribution` に入れる |
`conference/maps/README_ja.md` に、各地図の説明と出典を書く。フォルダ全体で 15 MB 未満にする。

### Web 画面
- `mission.list_maps()` に、`conference/maps/` にある地図ファイルを加える（id は `file/<ファイル名>`）。指示書010の id はそのまま残す。
- フォルダにファイルを置けば、サーバーを起動し直したときに一覧に出ること。

## 2. 経路の追従（Pure Pursuit）とロボットの模型

### 新しいファイル `conference/tapp/pure_pursuit.py`
```python
class PurePursuit:
    def __init__(self, path_xy, lookahead_m=1.0, v_max=1.0, w_max=1.0, goal_tol_m=0.3): ...
    def command(self, pose) -> (v, w, done)    # pose = (x, y, yaw) [m, rad]
```
- よく使われる Pure Pursuit：経路の上で、今の位置から `lookahead_m` 先の点を目標にし、曲率 `κ = 2 sin(α) / L` から角速度を決める。
- 角速度が `w_max` を超えるときは、`w = ±w_max` にして、そのぶん並進速度を下げる（急な曲がり角で外にふくらまないように）。
- 目標の向きが ±90° より大きくずれているときは、**その場で旋回**する（BUNKER はクローラー型で、その場で回れる）。
- 経路の最後の点に `goal_tol_m` 以内まで近づいたら `done = True`。

### 新しいファイル `conference/tapp/robot_sim.py`
```python
def simulate(sc, path_xy, start_pose, dt=0.05, max_time_s=None, controller_kwargs=None) -> dict
```
- 動きの模型：その場で旋回できる車両の運動学（`x += v cos(yaw) dt`、`y += v sin(yaw) dt`、`yaw += w dt`）。滑りや傾斜による減速は**入れない**
  （単純な方を選ぶ。次の指示書の Gazebo で物理を確かめる）。
- 最初の向きは、経路の最初の区間の向きにする。
- 返す値：走った軌跡（時刻つき）、かかった時間、経路からのずれ（横方向の距離）の平均と最大、
  **軌跡が通れない場所に触れたマスの数**（`tapp.collision.path_lethal_cells`）、完走したかどうか。

### Web 画面に「走行のシミュレーション」を加える
- `POST /api/simulate`：`{map_id, path, lookahead_m}` → `simulate` の結果。
- 計画の結果が出たあと、「走行をシミュレーション」ボタンで、**実際に走った軌跡**を計画した経路と別の色で重ね、
  所要時間・経路からのずれ・通れない場所への接触を表に出す。「再生」は、走った軌跡を時刻どおりに動かす。
- 先読みの距離（`lookahead_m`）を画面で変えられるようにする（0.5〜3.0m、初期値 1.0m）。

## 3. Gazebo 用の地形の書き出し

### 新しいスクリプト `conference/data_prep/export_gazebo.py`
```bash
python3 data_prep/export_gazebo.py maps/<地図>.npz <出力フォルダ>
```
- 出力：Gazebo（gz sim Harmonic）の world ファイル（SDF、`<heightmap>` を使う）、高さ地図の画像（16 bit のグレースケール PNG）、説明の README。
- 高さ地図の画像は、Gazebo の決まりに合わせて**正方形で、一辺が 2^n + 1 画素**にする（例：400 マス → 513 画素に双線形補間）。
  `<size>` には地図の実際の大きさ（m）と高さの幅を入れる。NaN は一番近い値で埋める。
- 水は、高さ 0m の青い平面（見た目だけ）として置く。障害物（岩・漂着物・箱）は、マスのまとまりごとに箱として置く（衝突あり）。
- world には、太陽の光と、地面の物理（摩擦）を入れる。座標の原点と向きは、地図ファイルの (x, y) と同じにする（README に書く）。
- **Gazebo はこの環境では動かせないので**、ファイルの形が正しいことだけをテストで確かめる（下記）。
  Ubuntu で `gz sim <world ファイル>` で開くための手順を README に書く。

## テスト：新しいファイル `conference/tests/test_mapfiles_sim.py`
1. **地図ファイル**：人工の砂浜 3 種類（200m）と本物の砂浜 2 か所で、`scenario_to_mapfile` → `load_map_file` の `tmap.cost`・`tmap.lethal`・`start` が
   元と完全に一致すること。`conference/maps/` のすべてのファイルが読み込めること。
2. **Pure Pursuit**：まっすぐな経路と、90° に曲がる経路で、完走し、経路からのずれの最大が、まっすぐなら 0.05m 以内、
   曲がり角では `lookahead_m` 以内であること。逆向きから始めると、その場で旋回してから進むこと。
3. **巡回の走行**：`flat_test` と人工の砂浜 1 枚で、`plan_mission`（5 点）の経路を `simulate` で走らせると完走すること。
   通れない場所に触れたマスの数を記録して表示する（0 でなくても失敗にはしない。報告に書く）。
4. **Gazebo の書き出し**：`flat_test` と本物の砂浜 1 か所で、出力の PNG が正方形・2^n+1 画素・16 bit であること、
   world ファイルが XML として読めて `<heightmap>` の `<size>` が地図の大きさと合うこと、
   PNG から戻した高さが元の標高と、補間の誤差の範囲（最大 0.1m 程度）で一致すること。
5. **API**：`POST /api/simulate` が動くこと。`file/...` の地図で `GET /api/maps`・`POST /api/plan` が動くこと。
6. 既存のテスト（`tests.test_mission` を含む）がすべて通ること。

## 完了の条件
- すべてのテストが通る。
- Web 画面で、地図ファイルの地図を選び、計画 → 走行のシミュレーション → 再生ができる。スクリーンショットを PR に貼ること。
- `conference/maps/` に地図ファイルがあり、そのうち `flat_test` と本物の砂浜 1 か所の Gazebo 用の world を `conference/gazebo_worlds/` に置く（5 MB 未満）。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- 巡回の走行で、通れない場所に触れたことがあったか。あった場合は、その場所と理由（Pure Pursuit が角を内側にショートカットした、など）。
- Gazebo の書き出しで、決まり（2^n+1 画素など）に合わせるために行った処理と、標高の誤差。

## 対象外
ROS2 のノード、Gazebo での実際の走行、BUNKER の 3D モデル、GPS（緯度・経度）、実機。これらは次の指示書で行う。
