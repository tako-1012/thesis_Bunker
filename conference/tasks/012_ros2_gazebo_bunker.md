# 指示書 012：ROS2 Jazzy ＋ Gazebo（gz sim Harmonic）で BUNKER を走らせる（Web 画面 → ROS2 → Gazebo）

> **状態：完了**（Codex が実装。Gazebo での確認は Codex の環境では容量不足でできなかったため、Claude が Docker で実行した。
> その前に、位置の出力名の誤り（`PosePublisher` は `<topic>` を無視する）を Claude が直した）。
> 結果は `conference/ros2_jazzy/gz_checks/results/claude_docker_run/README_ja.md`。平地・本物の砂浜とも巡回を完走し、通れない場所への接触は 0。
> 本物の砂浜の標高データが 0.1m 刻みの段々になっていることが見つかった（未対応）。

最初に、リポジトリ直下の `AGENTS.md` を読むこと。土台にするブランチは `realtime-map`（最新を取得すること）。
報告・PR の説明・コミットメッセージは日本語で書くこと。

## 背景
指示書010・011で、Web 画面で地点を選んで巡回の経路を計画し、Python の簡単な模型で走らせ、Gazebo 用の地形を書き出しました。
この指示書では、**Ubuntu 24.04・ROS2 Jazzy・Gazebo Harmonic** で、物理のある BUNKER を、書き出した地形の上で走らせます。
流れは次のとおりです。
1. Mac（または Ubuntu）で Web 画面を開き、地図・地点を選んで経路を計画し、「ロボットに送る」を押す。
2. Ubuntu の ROS2 のノードが Web 画面のサーバーから経路を受け取り、Pure Pursuit（`tapp/pure_pursuit.py`）で `/cmd_vel` を出す。
3. Gazebo の BUNKER が地形の上を走り、位置・姿勢が Web 画面に戻ってきて、地図の上に表示される。走った記録は CSV に残る。

## わかっていること（Claude が確かめた）
- `apt` で `packages.ros.org` から入れることは、クラウドの環境ではできなかった（証明書の名前が合わない）。
  **Docker の公式イメージ `osrf/ros:jazzy-desktop-full` なら、ROS2 Jazzy・Gazebo Harmonic・ros_gz がそろって動く**
  （クラウドで `dockerd` を起動して使えた。画面なしの `gz sim -s -r`）。
- 指示書011の `gazebo_worlds/` の 2 つの world は、どちらも読み込めて動く。
- **ただし、地形の当たり判定がずれている。** `<heightmap>` の `<pos>` は見た目には効くが、当たり判定（DART の ODE の高さ地図）では無視され、
  当たり判定の地形が原点を中心に置かれる。そのため、地図の大部分では物が地形をすり抜けて落ちる。
  **`<pos>` を `0 0 0` にして、同じずらし（x, y, z）を地形のモデルの `<pose>` に移すと直る。** 直したあと、本物の砂浜
  （`real_08OB87_-0206`）の 6 か所に球を落とすと、止まった高さは地図の標高と 0〜0.2m で合った（差は斜面を転がった分）。
  x と y の入れ替わりや反転もなかった。→ 下の「変更してよい既存ファイル」で直すこと。

**ROS2 と Gazebo は、Docker のイメージで動かして確かめること。** あなたの環境で Docker が使えない場合は、
- ROS2・Gazebo がなくても確かめられる部分（Web 画面とのやり取り、経路の追従の中身、記録の解析、SDF の形）は、テストで確かめる。
- ROS2・Gazebo で動かす部分は、Ubuntu 24.04 での手順と、確かめることの一覧を README に書く。実際に動かすのは利用者（修士の学生）が行う。
Docker が使えない場合でも、下の「Gazebo で確かめるスクリプト」は書くこと。Claude が Docker で走らせて確かめる。
動かせなかったことは報告にそのまま書く（動かしたふりをしないこと）。

## 守ること
- `ros2/`（研究室のリポジトリから来たもの）は変更しない。研究室のリポジトリ（`hayashilab/bunker_ros2` など）には何も書き込まない。
- 研究室の BUNKER のメッシュ（STL）は**このリポジトリにコピーしない**（研究室のリポジトリのライセンスが書かれていないため）。
  見た目に使いたいときは、利用者の手元にある研究室のリポジトリの場所を起動の引数で渡して読み込む（下記）。渡さなければ箱の見た目で動くこと。
- 車体の大きさなどの値は、出典を README に書く（`tapp/config.py` の `Robot`、研究室の URDF の関節の位置、AgileX の公開されている仕様）。
  出典のない値（摩擦係数など）は「仮定」と書く。走らせた結果を見て値を合わせ込まないこと。

## この指示書で変更してよい既存ファイル
- `conference/webui/` の中のファイル：「ロボットに送る」とロボットの位置の表示のため。**指示書010・011の API とその結果は変えないこと**（`tests.test_mission`・`tests.test_mapfiles_sim` がそのまま通ること）。
- `conference/data_prep/export_gazebo.py` と `conference/gazebo_worlds/`：
  (1) 上の当たり判定のずれを直す（`<heightmap>` の `<pos>` は `0 0 0`、ずらしは地形のモデルの `<pose>`。見た目と当たり判定の両方）。
  (2) world に IMU などのセンサーの system（`gz-sim-sensors-system`、`gz-sim-imu-system`）を加える。
  直したら `conference/gazebo_worlds/` を作り直すこと（高さ画像・障害物の箱は変わらないこと）。
  `tests.test_mapfiles_sim` が `<pos>` の値を確かめている場合は、**同じ意味（地形の範囲が地図と合う）を、モデルの `<pose>` を足して確かめる形**に直してよい
  （確かめる中身を弱めないこと。直した場所と理由を報告に書く）。
それ以外の既存ファイルは変更しない。

## 1. BUNKER の Gazebo 用モデル：`conference/ros2_jazzy/src/thesis_bunker_gz/models/bunker/model.sdf`
研究室の URDF（`bunker_description/urdf/bunker.xacro`）は Gazebo Classic 用で、`base_link` の質量が 0.0001kg、
車輪の関節が動かない設定で、`libgazebo_ros_planar_move.so`（地形を無視して平面を滑らせる）で動かしています。
**地形の上で物理を確かめるには使えないので、新しく SDF で作る。**
- 車体：箱。大きさは AgileX の公開仕様（1023 × 778 × 410 mm 程度。出典を書く）。質量は `Robot.mass_kg`（150kg）。慣性は箱の式で計算する。
- クローラー：左右それぞれ、前後に並べた車輪（球または円柱、4〜6 個）で近似し、`gz::sim::systems::DiffDrive` で左右の車輪をまとめて回す。
  左右のクローラーの中心の間隔は研究室の URDF の車輪の関節の位置（y = ±0.3495m）から取る。
  その場で旋回できるように、車輪の横向きの摩擦（`mu2` と `fdir1`）を小さくしてよい（値は仮定と書く）。
  `gz::sim::systems::TrackedVehicle` を使う方法もあるが、この指示書では DiffDrive の方を作り、どちらにしたかと理由を報告に書く。
- センサー：IMU（傾きの記録のため）。LiDAR・カメラはこの指示書では付けない。
- 位置：`gz::sim::systems::PosePublisher`（または `OdometryPublisher`）で、**world 座標の本当の位置**を出す。
  シミュレーションでは、追従にこの本当の位置を使う（実機では GPS などが必要になるが、それは対象外）。
- 見た目：起動の引数 `lab_mesh_dir`（研究室の `bunker_description/meshes` の場所）が与えられたときだけ、`BUNKER.STL` を見た目に使う。
  与えられないときは箱を見た目にする。

## 2. ROS2 のパッケージ：`conference/ros2_jazzy/src/`
`colcon build` で作れる ament_python のパッケージにする。
| パッケージ | 中身 |
|---|---|
| `thesis_bunker_gz` | 上のモデル、起動ファイル `sim.launch.py`、`ros_gz_bridge` の設定 |
| `thesis_bunker_mission` | 経路の追従のノード `path_follower`、Web 画面との橋渡しのノード `webui_bridge` |

### `sim.launch.py`
```bash
ros2 launch thesis_bunker_gz sim.launch.py map:=flat_test_100m [lab_mesh_dir:=...] [webui:=http://<Mac の IP>:8080]
```
- `conference/gazebo_worlds/<地図>/world.sdf` を `gz sim` で開き、BUNKER を地図ファイルの `start_xy` に置く。
  高さは、地図の標高（`tapp.mapfile.load_map_file`）から決め、少し浮かせて置く。
- `ros_gz_bridge` で `/cmd_vel`（ROS → Gazebo）、`/clock`・本当の位置・`/imu`（Gazebo → ROS）をつなぐ。
- `path_follower` と `webui_bridge` も起動する（`webui` を渡さなければ `webui_bridge` は起動しない）。
- `world.sdf` が `conference/gazebo_worlds/` にない地図は、`data_prep/export_gazebo.py` で作るように README に書く。

### 経路の追従の中身（ROS に依存しない）：新しいファイル `conference/tapp/follower.py`
```python
class MissionFollower:
    def __init__(self, path_xy, lookahead_m=1.0, v_max=1.0, w_max=1.0, goal_tol_m=0.3): ...
    def step(self, t, pose) -> (v, w, done)   # pose = (x, y, yaw)
    def log_row(self, t, pose3d, imu_rpy, v, w) -> dict
```
- 中身は `tapp.pure_pursuit.PurePursuit` をそのまま使う（作り直さない）。止まっている・進まない状態が一定時間続いたら「立ち往生」として止まる
  （時間の閾値は引数にして、README に書く）。
- `path_follower` ノードは、このクラスを呼ぶだけの薄いものにする（ROS なしでテストできるように）。

### 走った記録
- `path_follower` は、1 回の走行ごとに `~/thesis_runs/<日時>_<地図>/` に `trajectory.csv`（時刻、x、y、z、roll、pitch、yaw、v、w）と
  `mission.json`（地図、地点、計画した経路、Pure Pursuit の設定）を書く。
- 新しいスクリプト `conference/experiments/gz_run_report.py <記録のフォルダ>`：計画した経路との横方向のずれ（平均・最大）、所要時間、
  完走したか、軌跡が通れない場所に触れたマスの数（`tapp.collision.path_lethal_cells`）、**実際の roll・pitch の 95% 値と、
  地図から計算した値（`tapp.metrics.evaluate` と同じ計算）の比較**、図（地図の上の計画と軌跡、時刻ごとの roll・pitch）を出す。
  同じ記録で `tapp.robot_sim.simulate`（指示書011の簡単な模型）も走らせて、並べて表示する。

## 3. Web 画面との橋渡し
Web 画面のサーバーは **ROS2 に依存させない**（Mac で ROS2 なしに動くこと）。ロボットの側から Web 画面のサーバーに取りに行く形にする。
| エンドポイント | 中身 |
|---|---|
| `POST /api/robot/mission` | 画面の「ロボットに送る」：`{map_id, path, lookahead_m}` を、送った番号つきで保存する |
| `GET /api/robot/mission?after=<番号>` | ロボットの側が新しい経路を取りに来る（なければ 204） |
| `POST /api/robot/state` | ロボットの側が、位置・姿勢・状態（走行中・完了・立ち往生）を送る |
| `GET /api/robot/state` | 画面が、ロボットの位置を取りに来る（1 秒に数回） |
- `webui_bridge` ノードは、標準ライブラリ（`urllib`）だけで上の API を使う。新しい経路が来たら `path_follower` に渡す
  （ROS のトピック `nav_msgs/Path` でよい）。地図が今の Gazebo の地図と違うときは受け付けず、状態でそう返す。
- 画面：計画の結果が出たあと「ロボットに送る」ボタン。ロボットの位置を地図の上に別の形のマーカーで出し、走った軌跡を線で残す。
  ロボットから一定時間連絡がないときは「ロボットとつながっていません」と出す。
- ロボットはいつも 1 台だけとする（ログインや複数台は対象外）。

## テスト：新しいファイル `conference/tests/test_ros2_gz.py`（`python3 -m tests.test_ros2_gz`。ROS2・Gazebo なしで動くこと）
1. **モデル**：`model.sdf` が XML として読め、車体の質量が `Robot.mass_kg`、左右のクローラーの間隔が 0.699m、DiffDrive の
   `left_joint`・`right_joint` が実在する関節を指し、IMU と本当の位置を出す system があること。`lab_mesh_dir` なしで STL を参照しないこと。
2. **パッケージ**：両方のパッケージの `package.xml`・`setup.py` が読め、起動ファイルとノードの入口が書かれていること。
   リポジトリの中に `.STL` が増えていないこと。
3. **追従の中身**：`MissionFollower` を、指示書011の `tapp.robot_sim` と同じ運動学の模型で回したとき、`tapp.robot_sim.simulate` と同じ軌跡になること
   （同じ `PurePursuit` を使っているため）。動かない姿勢を入れ続けると「立ち往生」になること。
4. **記録の解析**：`gz_run_report.py` を、`tapp.robot_sim.simulate` の結果から作った記録で走らせて、横方向のずれ・通れない場所への接触が
   `simulate` の値と一致すること。
5. **API**：`TestClient` で、送る → 取りに来る（番号つき、2 回目は 204）→ 状態を送る → 状態を取る、が動くこと。不正な地図・空の経路は 422。
6. **world**：作り直した `gazebo_worlds/` の world に IMU などの system があり、地形・障害物が前と同じであること。
7. 既存のテストがすべて通ること。

## 4. Gazebo で確かめるスクリプト：`conference/ros2_jazzy/gz_checks/`
Docker のイメージ `osrf/ros:jazzy-desktop-full` の中で、画面なし（`gz sim -s -r`）で走らせるスクリプト。1 つのコマンドで全部走り、結果を JSON に書く。
`run_gz_checks.sh`（Docker を呼ぶ側）と、イメージの中で動く Python を分けること。
1. **地形**：`gazebo_worlds/` のすべての world で、地図の陸の 20 か所（シード固定）に球を落とし、止まった高さと地図の標高の差（球を斜面で転がさないように、
   摩擦を大きくし、転がり止めを入れてよい）。差の最大を出す。
2. **BUNKER を置く**：`flat_test` と本物の砂浜 1 か所で、スタートに置いて 5 秒待ち、沈んだり跳ねたりせず、地面の上で止まっていること。
3. **前進・旋回**：`flat_test` で `/cmd_vel` に前進 0.5m/s を 10 秒、その場旋回 0.5rad/s を 10 秒送り、進んだ距離・回った角度と指令の比。
4. **経路の追従**：`flat_test` と本物の砂浜 1 か所で、`plan_mission`（5 点、シード固定）の経路を `path_follower` で走らせ、
   `gz_run_report.py` の結果（完走、横方向のずれ、接触、roll・pitch）を出す。
閾値は決めない（初めて測る値なので、結果をそのまま報告に書く）。ただし、球のすり抜け・BUNKER の落下は失敗とする。

## 5. README：`conference/ros2_jazzy/README_ja.md`
- Ubuntu 24.04 に ROS2 Jazzy と Gazebo Harmonic（`ros-jazzy-ros-gz`）を入れる手順、`colcon build`、起動のしかた。
- Mac で Web 画面を起動し、Ubuntu から `webui:=http://<Mac の IP>:8080` でつなぐ手順（同じネットワーク、ファイアウォール）。
- **利用者が確かめることの一覧**（チェックリスト）：Gazebo が開く、BUNKER が地形の上に置かれる、`/cmd_vel` で前進・その場旋回ができる、
  画面から送った経路を走る、画面にロボットが表示される、記録が残り `gz_run_report.py` が動く。うまくいかないときに見るところ。
- 値の出典と仮定の一覧。

## 完了の条件
- すべてのテストが通る。
- `conference/ros2_jazzy/` に 2 つのパッケージと README がある。
- Web 画面に「ロボットに送る」とロボットの位置の表示がある（ロボットの代わりに、テスト用の小さなスクリプトで `POST /api/robot/state` を送って、
  表示されるスクリーンショットを PR に貼る）。
- `gz_checks` を Docker で走らせた結果（JSON）を `conference/ros2_jazzy/gz_checks/results/` に置く。走らせられなかった場合はそう書く。
- `realtime-map` に向けた PR があり、`AGENTS.md` に書いた形式の報告（日本語）がついている。

## 結果の報告で必ず書くこと
- 車体・クローラー・摩擦の値と出典（仮定のものは仮定と）。
- DiffDrive にした理由と、その場旋回がうまくいくと考える理由（または心配な点）。
- Docker で ROS2・Gazebo を動かせたか。`gz_checks` の結果（地形の高さの差、前進・旋回の比、追従の結果）。

## 対象外
実機、GPS（緯度・経度）、LiDAR・カメラ、地図の作り直し（走りながらの再計画は次以降）、Nav2、研究室のリポジトリの Jazzy への移植（後回し）、砂の物理（沈み込み・滑り）。
