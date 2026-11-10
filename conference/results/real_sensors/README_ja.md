# 指示書027 段階A：実機センサーの実装・Python確認

Gazeboは未実行。段階Bの走行・性能・実機との一致は、この結果から主張しない。

## 明示的な選択

引数なしは従来どおり。実機センサーを使う場合だけ `--map fine --sensors lidar_real` または
`--map fine --sensors lidar_real+depth2` を渡す。Dockerラッパーは既存の引数転送を使う。

準備だけ（ROS2・Gazebo不要、保存先は毎回新しくする）：

```bash
cd conference
python3 ros2_jazzy/gz_checks/lidar_checks.py --prepare-only \
  --output /tmp/task027-real-sensors-prepare --map fine --sensors lidar_real+depth2
```

研究PCで後日、段階Bの実施指示が出たときの引数の例（今回未実行）：

```bash
bash ros2_jazzy/gz_checks/run_lidar_checks.sh results/<新しい保存先> \
  --patch-count 3 --map fine --sensors lidar_real+depth2
```

`fine_protocol()` の既定は0.3倍・途切れ1秒のまま。026の作業ブランチは取り込んでおらず、
そのブランチの `THESIS_FINE_PROTOCOL` / `THESIS_ONLY_PATCH` を上書き・削除していない。
本ブランチにはその機能はないため、後日併用する場合は別途統合確認が必要。
新しいセンサー構成の走行は022/023と条件が違うので、既存の比較集計へ混ぜない。
段階B用の `real_sensors_report.py` は今回の範囲外。生データ・manifestの保存経路を用意した。

## 座標・地図・センサー別の記録

- `SensorMount.xyz` は模型原点からの位置。SDFへは `base_link` の高さ0.35mを引いて記述する。
  `make_model(lidar=True, lidar_xyz=(x,y,z), lidar_rpy=(roll,pitch,yaw))` で任意の取り付けを指定できる。
- プリセット `sensor_preset='real_bunker'` は実機のLiDAR位置・最短0.9mを固定する。
  `depth_cameras=True` を併用したときだけ左右のD455仮定モデルを付ける。
- Gazebo Sensors 8のDepthCameraSensor・Ogre2の点群生成ソースに合わせ、点群の軸は
  x前・y左・z上として扱う。`gz_frame_id` は `camera1` / `camera2` に固定。
  ROS optical座標の外部実機点群をこのまま入力してはいけない。
- 212×120で縦58°・横87°を両立するため、SDFのlens/intrinsicsに別々のfx/fyを入れる。
  近クリップは軸方向、遠クリップはOgre2の点群シェーダーに合わせ放射距離で判定する。
- 点群ごとに、センサー取り付け変換と、その点群時刻に補間したground_truth姿勢を適用する。
- 地図は `PointCloudMapFine` を再利用。登録済みworld点群を仮想センサー経由で渡し、
  0.5m高さ格子・直近64点・0.1m障害物格子・0.3m/3点・0.5mの1回膨張を維持する。
  元の `pointcloud_map.py` / `pointcloud_map_fine.py` は無変更。
- 3センサーを別々の最大1件キューで受け、古い時刻から処理する。同じ共有地図に入れ、
  どれかのセンサーが届かない状態を別センサーで隠さないよう、全選択センサーの鮮度を確認する。
- `map_updates.csv` にセンサー名、`sensor_status_multi.json` にセンサー別受信・処理・破棄数・最終時刻を保存。
  各センサーの最初の点群とハッシュも保存する。
- `pointcloud_map.npz.sensors.json` は点群数・高い点数・細格子の初回検出数と、初回検出時の
  センサー、寄与したセンサー別の点数、sim時刻、ロボットからの水平距離を保存する。
  「物体の個数」ではなく「細格子の個数」。複数センサーの2点＋1点でも同じ3点基準を満たす。

## 死角の表と図

- `coverage.csv` / `coverage_ja.md`：高さ4種×構成3種×方向6種、72行。距離刻み0.01m。
- `coverage.png`：高さ別の平面図（x前・y左）。青は実機LiDAR、橙はカメラが補う部分。
- `coverage_log.txt`：正面の表（スクリプトの出力そのまま）。
- 距離はセンサーからではなく**模型原点から**。LiDARは後方0.24mなので、高さ0.3mの物の正面の
  最短水平距離は約3.87m（LiDARからは約4.11m）。カメラ2台込みは約1.38m。
  カメラの前方0.40mの取り付け・外向きyaw・最短距離・左右位置も含める。
- 既存資料の「約0.8m」はカメラ位置から・中心視野等の簡略化による値。本表は同一の模型原点と
  実際の左右位置で計算するため、そのまま比較しない。
- 高さ0.3m物体は16本の離散LiDARビーム間にも小さな死角が生じる。
  資料の「4.1〜11.4mは連続」を前提にせず、宣言された16本・±15°から直接計算した。
- 幾何学的可視性だけの表。遮蔽、ノイズ、画素命中、物体幅、姿勢変動、3点以上の観測条件は含まない。
  0.1m/0.2mが見えても、既存の0.3mしきい値で障害物になることは保証しない。

## Python検証

```bash
cd conference
python3 -m tests.test_real_sensors
python3 -m experiments.sensor_coverage --output results/real_sensors
```

全テストの出力全文と終了コードは `tests/`。実行の詳細は `REPORT_ja.md`。

## 実動作で後日確認すること

深度カメラのSDF読込・点群の軸とクリップ・ROS橋渡しは公式ソースから実装したが、Gazeboでは未確認。
最初は既知の箱・平面でフレーム、位置、点群、3センサーの鮮度、負荷を短時間確認する必要がある。
カメラ2台による更新頻度・CPU/GPU負荷や完走率の改善は未測定。
実機D455の特性の再現、遮蔽の再現性、ノイズのシード固定、現実の検出性能も未確認。

参照した一次資料：
- https://github.com/gazebosim/gz-sensors/blob/gz-sensors8/src/DepthCameraSensor.cc
- https://github.com/gazebosim/gz-sensors/blob/gz-sensors8/src/CameraSensor.cc
- https://github.com/gazebosim/gz-rendering/blob/gz-rendering8/ogre2/src/media/materials/programs/GLSL/depth_camera_fs.glsl
- https://github.com/gazebosim/gz-rendering/blob/gz-rendering8/ogre2/src/media/materials/programs/GLSL/depth_camera_final_fs.glsl
- https://github.com/gazebosim/sdformat/blob/sdf14/sdf/1.10/camera.sdf
