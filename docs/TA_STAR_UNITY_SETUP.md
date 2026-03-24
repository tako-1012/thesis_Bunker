# TA* Unity 可視化システム セットアップガイド

## 概要

本システムは、Terrain-Aware A* (TA*)経路計画アルゴリズムをROS2で実装し、Unity Editorでリアルタイム可視化するためのデモシステムです。

## システム構成

```
┌─────────────────────────┐
│  Terrain Analyzer Node  │ ← 地形データ処理（オプション）
│  (点群 → ボクセル変換)    │
└────────┬────────────────┘
         │ /bunker/voxel_grid
         │ /bunker/terrain_info
         ↓
┌─────────────────────────┐
│  TA* Planner Node       │ ← 経路計画コア
│  (TerrainAwareAStar)    │
└────────┬────────────────┘
         │ /path_3d (Path)
         ↓
┌─────────────────────────┐
│ Unity Visualization     │ ← ROS2 ↔ Unity ブリッジ
│ Node (TCP Socket)       │
└────────┬────────────────┘
         │ TCP 11000
         ↓
┌─────────────────────────┐
│   Unity Editor          │ ← 3D可視化
│   (PathPlanningVis)     │
└─────────────────────────┘
```

## 必要環境

- **OS**: Ubuntu 22.04 (推奨)
- **ROS2**: Humble Hawksbill
- **Python**: 3.10+
- **Unity**: 2021.3 LTS 以上
- **その他**: numpy, open3d (オプション)

## インストール手順

### 1. ROS2ワークスペースのビルド

```bash
cd ~/thesis_work/ros2/ros2_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select bunker_3d_nav
source install/setup.bash
```

### 2. 依存パッケージの確認

```bash
# 必要に応じてインストール
pip3 install numpy
```

### 3. Unity プロジェクトの準備

Unity Hubから以下のプロジェクトを開く:
```
~/thesis_work/unity/PathPlanningVisualization
```

## 起動方法

### オプション1: 統合スクリプトで起動（推奨）

```bash
cd ~/thesis_work
./scripts/launch_ta_star_demo.sh
```

オプション:
- `--no-unity`: Unity Editorを自動起動しない
- `--with-rviz`: RVizを起動する

### オプション2: 手動起動

#### ターミナル1: TA* Planner Node

```bash
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash
ros2 run bunker_3d_nav ta_star_planner_node.py
```

#### ターミナル2: Unity Visualization Bridge

```bash
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash
ros2 run bunker_3d_nav unity_visualization_node.py
```

#### ターミナル3: Unity Editor

```bash
~/thesis_work/scripts/launch_unity_visualization.sh
```

Unity起動後、Playボタンを押す。

## 動作確認

### クイックテスト

```bash
# ターミナル1: TA*システム起動
cd ~/thesis_work/ros2/ros2_ws
source install/setup.bash
ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py

# ターミナル2: テストスクリプト実行
cd ~/thesis_work
python3 scripts/test_ta_star.py
```

成功すると以下のようなメッセージが表示される:
```
✅ Path received with XX waypoints
✅ Test PASSED: Path planning successful!
```

### 手動で目標位置を送信

```bash
# 現在位置を送信
ros2 topic pub -1 /current_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: "map"}, pose: {position: {x: 0.0, y: 0.0, z: 0.5}}}'

# 目標位置を送信
ros2 topic pub -1 /goal_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: "map"}, pose: {position: {x: 5.0, y: 5.0, z: 0.5}}}'
```

### 経路を確認

```bash
# 経路トピックをエコー
ros2 topic echo /path_3d

# 経路の統計情報
ros2 topic hz /path_3d
```

## トラブルシューティング

### 1. ビルドエラー

```bash
# クリーンビルド
cd ~/thesis_work/ros2/ros2_ws
rm -rf build install log
colcon build --symlink-install
```

### 2. ノードが起動しない

```bash
# ROS2環境の確認
echo $ROS_DISTRO
ros2 pkg list | grep bunker

# ノードリストの確認
ros2 run bunker_3d_nav ta_star_planner_node.py --help
```

### 3. Unity接続エラー

- Unity Editorが起動しているか確認
- Playモードになっているか確認
- ファイアウォールでポート11000が開いているか確認

### 4. 経路が表示されない

```bash
# トピック確認
ros2 topic list | grep path
ros2 topic info /path_3d

# ログ確認
ros2 node info /ta_star_planner
```

## パラメータ調整

### launch ファイルで調整

`ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/launch/ta_star_unity_demo.launch.py`

主要パラメータ:
- `voxel_size`: ボクセルサイズ (default: 0.2m)
- `grid_size_x/y/z`: グリッドサイズ (default: 200×200×50)
- `planning_interval`: 経路再計画間隔 (default: 2.0秒)
- `terrain_analysis_radius`: 地形分析半径 (default: 5)

### 実行時にパラメータ指定

```bash
ros2 launch bunker_3d_nav ta_star_unity_demo.launch.py \
  voxel_size:=0.1 \
  grid_size_x:=300 \
  planning_interval:=1.0
```

## 開発メモ

### 現在の実装状況

- ✅ TA* コアアルゴリズム実装
- ✅ ROS2ノード化
- ✅ Unity ブリッジ実装
- ✅ 統合launchファイル
- ✅ ダミー地形データ対応
- ⏳ 実地形データ統合 (terrain_analyzer連携)
- ⏳ RViz可視化

### 次のステップ

1. 実地形データ（rtabmap点群）の統合
2. 複数シナリオの自動実行
3. パフォーマンス計測・ログ記録
4. Unity側のUI改善

## 関連ファイル

- **TA*実装**: `ros2/ros2_ws/src/bunker_ros2/path_planner_3d/terrain_aware_astar_advanced.py`
- **プランナーノード**: `ros2/ros2_ws/src/bunker_ros2/path_planner_3d/ta_star_planner_node.py`
- **Unity bridge**: `ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/bunker_3d_nav/scripts/unity_visualization_node.py`
- **Launch file**: `ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/launch/ta_star_unity_demo.launch.py`
- **統合スクリプト**: `scripts/launch_ta_star_demo.sh`

## ライセンス

MIT License

## 問い合わせ

hayashi@example.com
