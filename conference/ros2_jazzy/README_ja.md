# Web画面 → ROS2 Jazzy → Gazebo Harmonic

Ubuntu 24.04で、Webで計画した経路をGazeboのBUNKER模型へ送ります。WebサーバーはMacでも動き、ROSには依存しません。
この実装は実機制御・GPS・Nav2・砂の沈み込みや滑りの再現を含みません。

## この環境で確認できた範囲

公式 `osrf/ros:jazzy-desktop-full` を取得し、コンテナで `rclpy`・numpy・scipy・matplotlib・colconと
`gz sim --versions`（8.11.0）の存在を確認しました。しかし、Dockerの `vfs` ストレージ方式でコンテナを展開すると
32GBのディスクが一杯になり、継続検査用コンテナの作成が `no space left on device` で失敗しました。
**物理のあるGazebo走行、colconビルド、gz_checksはこの環境では完了していません。**
実行できなかった物理量は0で埋めず、`gz_checks/results/environment.json` に未実行として記録しています。
ROSなしのモデル・パッケージ・追従・CSV解析・API・地形の検証結果は `REPORT_ja.md` を参照してください。

## Ubuntu 24.04のセットアップ

ROS公式手順 https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html に従ってROSのaptソースを設定します。
以下は標準的な設定例です（公開されている最新の `ros2-apt-source` を使用）。

```bash
sudo apt update
sudo apt install -y locales software-properties-common curl
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
sudo add-apt-repository universe
ROS_APT_SOURCE_VERSION=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
curl -fL -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.noble_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt install -y ros-jazzy-desktop ros-jazzy-ros-gz python3-colcon-common-extensions python3-numpy python3-scipy python3-matplotlib
source /opt/ros/jazzy/setup.bash
```

GazeboはHarmonicを使います。Gazebo Classic用の研究室の起動ファイル・URDFプラグインは使用しません。

## ビルドと起動

```bash
cd <リポジトリ>/conference/ros2_jazzy
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install
source install/setup.bash
ros2 launch thesis_bunker_gz sim.launch.py map:=flat_test_100m
```

実測砂浜：

```bash
ros2 launch thesis_bunker_gz sim.launch.py map:=real_08OB87_-0206_200m_0
```

`map` は `conference/maps/<map>.npz` の拡張子なしのファイル名です。起動時に地図の基地と標高を読み、地面より0.1m浮かせて置きます。
最初の模型の向きは+xです。追従開始時の向きが異なる場合はPure Pursuitがその場で旋回します。
worldがない地図は、先に `conference/` で次のように生成します。

```bash
python3 data_prep/export_gazebo.py maps/hills_100m_100.npz gazebo_worlds/hills_100m_100
```

起動は一時worldへ模型を埋め込み、Gazebo起動サービスとの競合を避けます。元のworld・PNGは書き換えません。
地図ディレクトリを自動検出できない設置方法では、`conference_dir:=/絶対パス/conference` を渡します。
`THESIS_CONFERENCE_DIR` 環境変数でも指定できます。

## MacのWeb画面との接続

MacとUbuntuを同じネットワークに接続します。Macでは次を実行します。

```bash
cd <リポジトリ>/conference
pip install numpy scipy matplotlib pandas fastapi uvicorn httpx
python3 -m webui.server --host 0.0.0.0 --port 8080
```

Macの「システム設定 → ネットワーク → Wi-Fi → 詳細 → TCP/IP」でIPアドレスを確認します。
Ubuntuから `http://<MacのIP>:8080/api/maps` に接続できることと、MacのファイアウォールでTCP 8080を許可したことを確認します。

```bash
ros2 launch thesis_bunker_gz sim.launch.py map:=flat_test_100m webui:=http://<MacのIP>:8080
```

Webで**同じファイル地図** `flat_test_100m.npz` を選び、地点を置いて計画後に「ロボットに送る」を押します。
紫のマーカーと軌跡はロボット側から返された位置です。送信番号・走行中・完了・立ち往生などの状態を表示します。
サーバーが3秒以内に状態を受け取れなければ「ロボットとつながっていません」と表示します。
Web側は約0.3秒ごと、ROS側は0.25秒ごとにHTTPを処理します。HTTP処理はROSの別スレッドで行います。
異なる地図の指示は拒否し、`map_mismatch` を返します。サーバー再起動時は送信番号が初期化されるため、橋渡しノードも再起動します。
単一ロボット・最新の指示1件をメモリに保持する方式です。途中で別の経路を送ると、古い走行記録を `replaced` で閉じて新しい走行を始めます。

停止はGazebo起動ターミナルのCtrl+C、または次のROSトピックを使用します。

```bash
ros2 topic pub --once /mission/stop std_msgs/msg/Empty '{}'
```

## ROSの接続と記録

- `/cmd_vel`：ROS → Gazebo、`geometry_msgs/Twist`。DiffDriveへ接続。
- `/clock`：Gazebo → ROS、シミュレーション時刻。両ノードは `use_sim_time=true`。
- `/ground_truth`：Gazebo → ROS、`geometry_msgs/PoseArray`。模型だけのPosePublisherを使い、親がworldのモデルの位置・姿勢を取得します。
  車輪の積算オドメトリ `/wheel_odom` は追従には使いません。
- `/imu`：Gazebo → ROS、`sensor_msgs/Imu`。ノイズモデルは追加していません。
- `/mission/command`：JSONの `std_msgs/String`。経路と番号・地図・先読み・地点を1メッセージで渡し、別トピック間のメタデータ到着順の競合を避けます。
  `/mission/path` には同じ経路を `nav_msgs/Path` でも配信します。
- `/mission/state`：JSONの状態。完了・立ち往生を保持して橋渡しノードが確実に受け取れるようにします。

`path_follower` は `tapp.follower.MissionFollower` を呼び、既存の `PurePursuit` をそのまま使います。
速度上限1.0m/s、角速度上限1.0rad/s、到達距離0.3m、制御周期0.05秒、既定の先読み1.0mです。
立ち往生の閾値 `stall_timeout_s` は既定10秒。0.1m進むか、旋回指令時に0.1rad向きが変わると時計を更新します。
これは仮定の監視値で、走行結果を見て調整していません。位置受信が壁時計で1秒止まった場合も停止します。

走行ごとに `~/thesis_runs/<Asia_Tokyoの日時>_<地図>/` に保存します。
`trajectory.csv` は `t,x,y,z,roll,pitch,yaw,v,w`（秒・m・rad）で、roll・pitchはIMU、yawと位置はworldの真値です。
IMU受信前だけworld姿勢のroll・pitchを使います。`mission.json` に地図ID・地点・経路・制御設定・終了状態を保存します。
`run_root` ノード引数で記録先を変えられます。

```bash
cd <リポジトリ>/conference
python3 experiments/gz_run_report.py ~/thesis_runs/<走行フォルダ>
```

`report/` にJSON、CSV、地図上の経路・軌跡、roll／pitch時系列、表示表を保存します。
同じ開始姿勢・経路で運動学模型も実行します。実際の姿勢95%値は時間サンプル、地図の予測値は既存evaluateと同じ0.1m弧長サンプルです。
比較する分布の重みが異なる点に注意してください。地図からのpitchも既存evaluateの方向勾配と同じ式で95%値を求めます。

## 物理模型の値と出典

| 値 | 出典または仮定 |
|---|---|
| 車体箱1.023×0.778×0.410m | 指示書012が引用するAgileX公開寸法の近似。https://global.agilex.ai/products/bunker |
| 車体質量150kg | `tapp/config.py` の `Robot.mass_kg`。慣性は一様な箱の式m(a²+b²)/12 |
| クローラー中心y=±0.3495m、間隔0.699m | 指示書012に記載された研究室URDF `bunker_description/urdf/bunker.xacro` の車輪関節位置。https://github.com/hayashilab/bunker_ros2 |
| 左右4輪ずつ、半径0.12m、幅0.08m、各1kg | 近似の仮定。輪の慣性は円柱の式。模型全質量は車体と車輪の合計で、150kgの実機質量を厳密に再現するものではない |
| 車輪x=−0.36,−0.12,0.12,0.36m、車輪中心z=0.12m、車体中心z=0.35m | 配置の仮定。車体箱は公開外形を箱として用い、車輪との合成外形まで実機寸法と一致するとはしていない |
| 摩擦mu=1.0、mu2=0.1、fdir1=(1,0,0)、関節減衰0.05 | 仮定。転がる方向を保ち、横方向は滑りやすくして旋回可能にする。結果による合わせ込みなし |
| 外部STLのscale=0.001 | 研究室メッシュをmm単位と仮定する見た目のみの設定。衝突は常に箱。未検証 |
| IMU 50Hz・位置20Hz・制御20Hz、理想的な関節速度駆動 | 通信・計算の仮定。実機のセンサー周期やモーターの最大トルクを再現する設定ではない |

指示書に従いDiffDriveを採用しました。左右の複数のrevolute関節をまとめて駆動でき、TrackedVehicleより単純だからです。
その場旋回は左右を逆転させ、横方向の小さい摩擦でスキッド旋回する想定です。
実際の旋回比・横滑り・斜面での安定性は未測定で、クローラーそのものを忠実に再現するものではありません。

研究室メッシュはコピーしません。手元のファイルを見た目だけに使う場合：

```bash
ros2 launch thesis_bunker_gz sim.launch.py map:=flat_test_100m lab_mesh_dir:=/手元の/bunker_description/meshes
```

指定しない場合はSTLを参照せず箱だけで動きます。既存の `ros2/` や研究室のリポジトリへは書き込みません。

## 一括Gazebo検査

Dockerの公式イメージを使い、1コマンドでビルド・画面なしの検査・JSON出力を行います。
`vfs` のDockerではイメージ展開が大きくなるため、今回は容量不足でした。十分な空き容量のあるUbuntuのDockerで実行してください。

```bash
cd <リポジトリ>/conference
./ros2_jazzy/gz_checks/run_gz_checks.sh
```

出力先は `ros2_jazzy/gz_checks/results/`、引数で別ディレクトリにも変更できます。
ソースはread-onlyでマウントし、ビルドはコンテナの `/tmp`、出力だけを別の書込み可能なマウントへ置きます。
`THESIS_ROS_IMAGE`、`THESIS_ROS_DOMAIN_ID` でイメージ・ROSドメインを変更できます。
CPU上での検査ではworldの一時コピーだけをreal_time_factor=5にします。物理刻み0.001秒と車両パラメータは変更しません。

検査内容：全worldで固定シード100の陸20地点に垂直ガイド付きの半径0.05mの球を落とす、
基地で待機、0.5m/s×10秒の前進、0.5rad/s×10秒の旋回、5地点の巡回と記録解析。
精度や速度比に合格閾値は設けません。真値と地図の差、ドリフト、比、完走、接触、姿勢をそのままJSONへ記録します。
すり抜け／落下は地図標高より1m以上低下した場合として失敗にします。通信が来ない場合は実行エラーとして記録し、数値を作りません。

## 利用者が確かめる一覧

- [ ] `colcon build` が成功し、`ros2 pkg executables thesis_bunker_mission` に2ノードが出る。
- [ ] Gazeboが開き、地形の見た目と衝突が一致する。BUNKERが基地の地面に落ち着く。
- [ ] `/clock`・`/ground_truth`・`/imu` が流れ、world座標が地図のメートル座標と一致する。
- [ ] `/cmd_vel` で前進とその場旋回ができる。前進・旋回の実測比を保存する。
- [ ] MacのWebで同じファイル地図を選択し、送信番号付き経路を受信して走行する。
- [ ] 紫の位置・軌跡・状態がWebに表示され、通信断で未接続表示になる。
- [ ] `trajectory.csv`・`mission.json` が残り、`gz_run_report.py` で表と図を生成できる。
- [ ] `run_gz_checks.sh` の `results.json` を読み、落下・立ち往生・接触・姿勢と未完走を確認する。

接続しない場合はMacのIP／TCP 8080、地図IDの一致、`ROS_DOMAIN_ID`、`use_sim_time` を確認します。
模型が落ちる場合は生成済みworldのheightmap.posが0で、平行移動がterrainモデルのposeにあることを確認します。
位置が届かない場合は `ros2 topic echo /ground_truth` とGazebo／bridgeログ、IMUが届かない場合はworldのSensors／Imu systemを確認します。
