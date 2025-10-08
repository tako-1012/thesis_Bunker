# Terrain Analyzer Module

## 概要

Terrain Analyzer Moduleは、RTAB-Mapから取得した3D点群データを処理し、地形情報を抽出するモジュールです。

## コンポーネント

### 1. TerrainAnalyzerNode
- **ファイル**: `terrain_analyzer_node.py`
- **役割**: ROS2ノードとして地形解析を統合
- **入力**: `/rtabmap/cloud_map`, `/robot_pose`
- **出力**: `/terrain/voxel_grid`, `/terrain/slope_map`, `/terrain/terrain_info`

### 2. VoxelGridProcessor
- **ファイル**: `voxel_grid_processor.py`
- **役割**: 3D点群データをボクセルグリッドに変換
- **機能**:
  - ROS PointCloud2 → numpy配列変換
  - ボクセルグリッド生成
  - ボクセル分類（空/地面/障害物/未知）

### 3. SlopeCalculator
- **ファイル**: `slope_calculator.py`
- **役割**: 地形の傾斜角度と安定性を計算
- **機能**:
  - 法線ベクトルから傾斜角度計算
  - ロボット安定性評価
  - 走行可能性判定

## 使用方法

```python
from bunker_3d_nav.terrain_analyzer import TerrainAnalyzerNode, VoxelGridProcessor, SlopeCalculator

# ノードの起動
node = TerrainAnalyzerNode()

# 個別コンポーネントの使用
processor = VoxelGridProcessor(voxel_size=0.1)
calculator = SlopeCalculator(max_slope_angle=30.0)
```

## パラメータ

| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `voxel_size` | 0.1 | ボクセルサイズ [m] |
| `ground_normal_threshold` | 80.0 | 地面判定閾値 [度] |
| `max_slope_angle` | 30.0 | 最大走行可能傾斜 [度] |
| `robot_width` | 0.6 | ロボット幅 [m] |
| `robot_length` | 0.8 | ロボット長さ [m] |
| `stability_threshold` | 20.0 | 安定性閾値 [度] |

## 出力メッセージ

### VoxelGrid3D
- `header`: ヘッダー情報
- `resolution`: ボクセルサイズ [m]
- `origin`: グリッドの原点
- `size_x/y/z`: 各方向のボクセル数
- `data`: ボクセルデータ (0:空, 1:地面, 2:障害物, 255:未知)
- `slopes`: 各地面ボクセルの傾斜角 [度]

### TerrainInfo
- `header`: ヘッダー情報
- `avg_slope`: 平均傾斜角 [度]
- `max_slope`: 最大傾斜角 [度]
- `traversable_ratio`: 走行可能領域の割合 [0-1]
- `total_voxels`: 総ボクセル数
- `ground_voxels`: 地面ボクセル数
- `obstacle_voxels`: 障害物ボクセル数

## 実装状況

- [x] ノードスケルトン実装
- [x] パラメータ管理
- [x] メッセージ定義
- [ ] 点群→ボクセル変換実装
- [ ] ボクセル分類実装
- [ ] 傾斜計算実装
- [ ] エラーハンドリング強化
