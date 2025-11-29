# terrain_analyzer トラブルシューティングガイド

## 🚨 よくある問題と解決方法

### 1. メッセージインポート問題

#### 問題
```
ModuleNotFoundError: No module named 'bunker_3d_nav.msg'
```

#### 原因
- カスタムメッセージのPythonバインディングが生成されていない
- ROS2環境が正しく設定されていない
- ビルドが不完全

#### 解決方法

**方法1: 自動修復スクリプト使用**
```bash
cd ~/thesis_work/ros2/ros2_ws
./rebuild_messages.sh
```

**方法2: 手動修復**
```bash
cd ~/thesis_work/ros2/ros2_ws

# クリーンビルド
rm -rf build/ install/ log/

# 再ビルド
colcon build --packages-select bunker_3d_nav

# 環境設定
source install/setup.bash

# 確認
python3 -c "from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D; print('Success!')"
```

**方法3: 環境変数設定**
```bash
export PYTHONPATH=$PYTHONPATH:~/thesis_work/ros2/ros2_ws/install/bunker_3d_nav/lib/python3.10/site-packages
```

### 2. Rviz表示問題

#### 問題
- Rvizでマーカーが表示されない
- 点群が表示されない
- グリッドマップが表示されない

#### 原因
- トピック名の不一致
- フレーム設定の問題
- データが送信されていない

#### 解決方法

**トピック確認**
```bash
# 利用可能なトピック一覧
ros2 topic list

# 特定トピックの確認
ros2 topic echo /terrain/markers --once
ros2 topic echo /terrain/occupancy --once
ros2 topic echo /terrain/colored_cloud --once
```

**フレーム確認**
```bash
# TFフレーム確認
ros2 run tf2_tools view_frames
```

**Rviz設定確認**
- Fixed Frame: `map`
- MarkerArray Topic: `/terrain/markers`
- OccupancyGrid Topic: `/terrain/occupancy`
- PointCloud2 Topic: `/terrain/colored_cloud`

### 3. パフォーマンス問題

#### 問題
- 処理が遅い
- メモリ使用量が多い
- ノードがクラッシュする

#### 原因
- 点群データが大きすぎる
- ボクセルサイズが小さすぎる
- 可視化マーカーが多すぎる

#### 解決方法

**パラメータ調整**
```yaml
# terrain_params.yaml
terrain_analyzer:
  voxel_size: 0.2  # 0.1から0.2に変更
  max_markers: 500  # 1000から500に変更
```

**メモリ使用量監視**
```bash
# メモリ使用量確認
htop

# ROS2ノードのリソース使用量
ros2 run resource_monitor resource_monitor
```

### 4. ノード起動問題

#### 問題
- terrain_analyzer_nodeが起動しない
- エラーメッセージが表示される
- ノードがすぐに終了する

#### 原因
- 依存関係の不足
- 設定ファイルの問題
- ポートの競合

#### 解決方法

**依存関係確認**
```bash
# 必要なパッケージ確認
ros2 pkg list | grep -E "(sensor_msgs|geometry_msgs|nav_msgs|visualization_msgs)"

# 不足している場合はインストール
sudo apt install ros-humble-sensor-msgs-py
```

**ログ確認**
```bash
# 詳細ログで起動
ros2 launch bunker_3d_nav terrain_analyzer.launch.py --ros-args --log-level debug
```

**設定ファイル確認**
```bash
# 設定ファイルの構文確認
python3 -c "import yaml; yaml.safe_load(open('config/terrain_params.yaml'))"
```

### 5. データ受信問題

#### 問題
- 点群データが受信されない
- 処理が実行されない
- トピックが空

#### 原因
- 点群パブリッシャーが動作していない
- トピック名の不一致
- QoS設定の問題

#### 解決方法

**点群パブリッシャー確認**
```bash
# 点群トピックの確認
ros2 topic info /bunker/pointcloud

# 点群データの確認
ros2 topic echo /bunker/pointcloud --once
```

**テストデータ送信**
```bash
# テスト用点群データ送信
ros2 run bunker_3d_nav test_pointcloud_publisher
```

### 6. ビルド問題

#### 問題
- colcon buildが失敗する
- コンパイルエラーが発生する
- パッケージが見つからない

#### 原因
- CMakeLists.txtの設定問題
- 依存関係の不足
- パッケージ構造の問題

#### 解決方法

**CMakeLists.txt確認**
```cmake
# 必須設定
find_package(rosidl_default_generators REQUIRED)
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/TerrainInfo.msg"
  "msg/VoxelGrid3D.msg"
  DEPENDENCIES std_msgs geometry_msgs
)
ament_export_dependencies(rosidl_default_runtime)
```

**package.xml確認**
```xml
<build_depend>rosidl_default_generators</build_depend>
<exec_depend>rosidl_default_runtime</exec_depend>
<member_of_group>rosidl_interface_packages</member_of_group>
```

## 🔧 デバッグツール

### ログレベル設定
```bash
# デバッグレベルで起動
ros2 launch bunker_3d_nav terrain_analyzer.launch.py --ros-args --log-level debug
```

### トピック監視
```bash
# 全トピック監視
ros2 topic list | xargs -I {} ros2 topic echo {} --once

# 特定トピック監視
ros2 topic echo /bunker/terrain_info
```

### ノード状態確認
```bash
# ノード一覧
ros2 node list

# ノード情報
ros2 node info /terrain_analyzer
```

## 📋 チェックリスト

起動前の確認事項:
- [ ] ROS2環境が正しく設定されている
- [ ] 必要なパッケージがインストールされている
- [ ] カスタムメッセージが生成されている
- [ ] 設定ファイルが正しい
- [ ] ポートが競合していない

実行中の確認事項:
- [ ] ノードが正常に起動している
- [ ] トピックが正しく配信されている
- [ ] Rvizでデータが表示されている
- [ ] エラーログが出ていない
- [ ] パフォーマンスが許容範囲内

## 🆘 緊急時の対処法

### 完全リセット
```bash
# 全プロセス停止
pkill -f terrain_analyzer
pkill -f rviz2

# 環境リセット
cd ~/thesis_work/ros2/ros2_ws
rm -rf build/ install/ log/

# 再ビルド
colcon build --packages-select bunker_3d_nav
source install/setup.bash

# 再起動
./run_terrain_analyzer.sh
```

### ログ収集
```bash
# ログファイル作成
mkdir -p ~/thesis_work/logs
ros2 launch bunker_3d_nav terrain_analyzer.launch.py > ~/thesis_work/logs/terrain_analyzer.log 2>&1
```

## 📞 サポート

問題が解決しない場合:
1. エラーメッセージをコピー
2. ログファイルを確認
3. システム情報を収集
4. 再現手順を記録

**システム情報収集**
```bash
# ROS2バージョン
ros2 --version

# パッケージ情報
ros2 pkg list | grep bunker

# 環境変数
env | grep ROS
env | grep PYTHON
```

