# API仕様書

## 目次
1. [TerrainAnalyzer](#terrainanalyzer)
2. [VoxelGridProcessor](#voxelgridprocessor)
3. [SlopeCalculator](#slopecalculator)
4. [AStar3D](#astar3d)
5. [CostFunction](#costfunction)
6. [PathSmoother](#pathsmoother)

## TerrainAnalyzer

### クラス概要
地形解析を行うROS2ノード

### コンストラクタ
```python
TerrainAnalyzerNode()
```

### メソッド

#### `pointcloud_callback(self, msg: PointCloud2) -> None`
点群データを受信して処理

**パラメータ**:
- `msg`: 点群データ（sensor_msgs/PointCloud2）

**戻り値**: None

**例**:
```python
node = TerrainAnalyzerNode()
# コールバックは自動的に呼び出される
```

## VoxelGridProcessor

### クラス概要
点群データをボクセルグリッドに変換するクラス

### コンストラクタ
```python
VoxelGridProcessor(voxel_size: float = 0.1, ground_normal_threshold: float = 80.0)
```

**パラメータ**:
- `voxel_size`: ボクセルサイズ（メートル）
- `ground_normal_threshold`: 地面判定の法線角度（度）

### メソッド

#### `process_pointcloud(self, msg: PointCloud2) -> Dict[str, Any]`
点群データを処理してボクセルグリッドを生成

**パラメータ**:
- `msg`: 点群データ（sensor_msgs/PointCloud2）

**戻り値**: 地形データ辞書
```python
{
    'voxel_grid': np.ndarray,      # ボクセルグリッド
    'classified_voxels': np.ndarray,  # 分類されたボクセル
    'normals': np.ndarray,         # 法線ベクトル
    'metadata': Dict[str, Any]     # メタデータ
}
```

**例**:
```python
processor = VoxelGridProcessor(voxel_size=0.1)
terrain_data = processor.process_pointcloud(pointcloud_msg)
voxel_grid = terrain_data['voxel_grid']
```

#### `_ros_to_numpy(self, msg: PointCloud2) -> np.ndarray`
ROS PointCloud2をnumpy配列に変換

**パラメータ**:
- `msg`: 点群データ（sensor_msgs/PointCloud2）

**戻り値**: 点群データ（numpy配列）

#### `_numpy_to_open3d(self, points: np.ndarray) -> o3d.geometry.PointCloud`
numpy配列をOpen3D点群に変換

**パラメータ**:
- `points`: 点群データ（numpy配列）

**戻り値**: Open3D点群オブジェクト

## SlopeCalculator

### クラス概要
傾斜角度と安定性を計算するクラス

### コンストラクタ
```python
SlopeCalculator(max_slope_angle: float = 30.0, stability_threshold: float = 20.0)
```

**パラメータ**:
- `max_slope_angle`: 最大傾斜角度（度）
- `stability_threshold`: 安定性閾値（度）

### メソッド

#### `calculate_slopes(self, voxel_grid: np.ndarray, normals: np.ndarray) -> Dict[str, Any]`
傾斜角度と安定性を計算

**パラメータ**:
- `voxel_grid`: ボクセルグリッド
- `normals`: 法線ベクトル

**戻り値**: 傾斜データ辞書
```python
{
    'slopes': np.ndarray,          # 傾斜角度
    'stability_map': np.ndarray,    # 安定性マップ
    'traversability_map': np.ndarray,  # 走行可能性マップ
    'statistics': Dict[str, float]  # 統計情報
}
```

**例**:
```python
calculator = SlopeCalculator(max_slope_angle=30.0)
slope_data = calculator.calculate_slopes(voxel_grid, normals)
avg_slope = slope_data['statistics']['avg_slope']
```

#### `calculate_robot_stability(self, robot_pose: np.ndarray, terrain_slopes: np.ndarray) -> Dict[str, Any]`
ロボットの安定性を計算

**パラメータ**:
- `robot_pose`: ロボットの姿勢（6次元配列）
- `terrain_slopes`: 地形の傾斜角度

**戻り値**: 安定性データ辞書
```python
{
    'roll_stability': float,       # ロール安定性
    'pitch_stability': float,      # ピッチ安定性
    'combined_stability': float,   # 複合安定性
    'is_stable': bool             # 安定性判定
}
```

## AStar3D

### クラス概要
3次元A*アルゴリズムによる経路計画クラス

### コンストラクタ
```python
AStar3D(voxel_size: float = 0.1, max_iterations: int = 10000)
```

**パラメータ**:
- `voxel_size`: ボクセルサイズ（メートル）
- `max_iterations`: 最大反復回数

### メソッド

#### `plan_path(self, start: Tuple[int, int, int], goal: Tuple[int, int, int], 
              voxel_grid: np.ndarray, cost_function: CostFunction) -> Optional[List[Tuple[int, int, int]]]`
3次元経路を計画

**パラメータ**:
- `start`: 開始位置（x, y, z）
- `goal`: 目標位置（x, y, z）
- `voxel_grid`: ボクセルグリッド
- `cost_function`: コスト関数

**戻り値**: 経路（座標のリスト）またはNone

**例**:
```python
planner = AStar3D(voxel_size=0.1)
path = planner.plan_path((0, 0, 0), (10, 10, 5), voxel_grid, cost_function)
if path:
    print(f"Path found with {len(path)} waypoints")
```

#### `_get_neighbors(self, position: Tuple[int, int, int], voxel_grid: np.ndarray) -> List[Tuple[int, int, int]]`
26近傍の位置を取得

**パラメータ**:
- `position`: 現在位置
- `voxel_grid`: ボクセルグリッド

**戻り値**: 近傍位置のリスト

#### `_heuristic(self, pos1: Tuple[int, int, int], pos2: Tuple[int, int, int]) -> float`
ヒューリスティック関数（ユークリッド距離）

**パラメータ**:
- `pos1`: 位置1
- `pos2`: 位置2

**戻り値**: ヒューリスティック値

## CostFunction

### クラス概要
経路計画のコストを計算するクラス

### コンストラクタ
```python
CostFunction(weights: Dict[str, float], safety_params: Dict[str, float])
```

**パラメータ**:
- `weights`: コスト重み辞書
- `safety_params`: 安全性パラメータ辞書

**例**:
```python
weights = {
    'distance': 1.0,
    'slope': 3.0,
    'obstacle': 5.0,
    'stability': 4.0
}
safety_params = {
    'min_obstacle_distance': 0.5,
    'max_roll_angle': 20.0,
    'max_pitch_angle': 25.0
}
cost_function = CostFunction(weights, safety_params)
```

### メソッド

#### `calculate_total_cost(self, from_pos: Tuple[float, float, float], 
                         to_pos: Tuple[float, float, float], 
                         terrain_data: Dict[str, Any]) -> float`
総コストを計算

**パラメータ**:
- `from_pos`: 開始位置
- `to_pos`: 目標位置
- `terrain_data`: 地形データ

**戻り値**: 総コスト

**例**:
```python
total_cost = cost_function.calculate_total_cost(
    (0.0, 0.0, 0.0), (1.0, 1.0, 0.1), terrain_data
)
```

#### `calculate_distance_cost(self, from_pos: Tuple[float, float, float], 
                            to_pos: Tuple[float, float, float]) -> float`
距離コストを計算

**パラメータ**:
- `from_pos`: 開始位置
- `to_pos`: 目標位置

**戻り値**: 距離コスト

#### `calculate_slope_cost(self, position: Tuple[float, float, float], 
                         terrain_data: Dict[str, Any]) -> float`
傾斜コストを計算

**パラメータ**:
- `position`: 位置
- `terrain_data`: 地形データ

**戻り値**: 傾斜コスト

#### `calculate_obstacle_cost(self, position: Tuple[float, float, float], 
                            terrain_data: Dict[str, Any]) -> float`
障害物コストを計算

**パラメータ**:
- `position`: 位置
- `terrain_data`: 地形データ

**戻り値**: 障害物コスト

#### `calculate_stability_cost(self, from_pos: Tuple[float, float, float], 
                             to_pos: Tuple[float, float, float], 
                             terrain_data: Dict[str, Any]) -> float`
安定性コストを計算

**パラメータ**:
- `from_pos`: 開始位置
- `to_pos`: 目標位置
- `terrain_data`: 地形データ

**戻り値**: 安定性コスト

## PathSmoother

### クラス概要
経路を平滑化するクラス

### コンストラクタ
```python
PathSmoother(method: str = 'cubic_spline', smoothness: float = 0.5)
```

**パラメータ**:
- `method`: 平滑化手法（'cubic_spline', 'gradient_descent'）
- `smoothness`: 平滑度（0.0-1.0）

### メソッド

#### `smooth_path(self, path: List[np.ndarray]) -> List[np.ndarray]`
経路を平滑化

**パラメータ**:
- `path`: 元の経路（numpy配列のリスト）

**戻り値**: 平滑化された経路

**例**:
```python
smoother = PathSmoother(method='cubic_spline')
smoothed_path = smoother.smooth_path(original_path)
```

#### `_cubic_spline_smoothing(self, path: List[np.ndarray]) -> List[np.ndarray]`
三次スプラインによる平滑化

**パラメータ**:
- `path`: 元の経路

**戻り値**: 平滑化された経路

#### `_gradient_descent_smoothing(self, path: List[np.ndarray]) -> List[np.ndarray]`
勾配降下法による平滑化

**パラメータ**:
- `path`: 元の経路

**戻り値**: 平滑化された経路

## 使用例

### 基本的な使用例
```python
import numpy as np
from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator
from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
from bunker_3d_nav.path_planner_3d.cost_function import CostFunction

# 地形解析
processor = VoxelGridProcessor(voxel_size=0.1)
terrain_data = processor.process_pointcloud(pointcloud_msg)

# 傾斜計算
calculator = SlopeCalculator(max_slope_angle=30.0)
slope_data = calculator.calculate_slopes(
    terrain_data['voxel_grid'], 
    terrain_data['normals']
)

# 経路計画
planner = AStar3D(voxel_size=0.1)
cost_function = CostFunction(weights, safety_params)

path = planner.plan_path(
    start=(0, 0, 0),
    goal=(10, 10, 5),
    voxel_grid=terrain_data['voxel_grid'],
    cost_function=cost_function
)

if path:
    print(f"Path found with {len(path)} waypoints")
else:
    print("No path found")
```

### パラメータの調整例
```python
# ボクセルサイズの調整
processor = VoxelGridProcessor(voxel_size=0.05)  # より細かい解像度

# 傾斜閾値の調整
calculator = SlopeCalculator(max_slope_angle=45.0)  # より緩い制約

# コスト重みの調整
weights = {
    'distance': 1.0,
    'slope': 5.0,      # 傾斜をより重視
    'obstacle': 3.0,   # 障害物を軽視
    'stability': 4.0
}
cost_function = CostFunction(weights, safety_params)
```

## エラーハンドリング

### 例外の種類
- `ValueError`: 無効なパラメータ
- `RuntimeError`: 実行時エラー
- `MemoryError`: メモリ不足
- `TimeoutError`: タイムアウト

### エラーハンドリングの例
```python
try:
    terrain_data = processor.process_pointcloud(pointcloud_msg)
except ValueError as e:
    print(f"Invalid parameter: {e}")
except RuntimeError as e:
    print(f"Runtime error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## パフォーマンス考慮事項

### メモリ使用量
- ボクセルサイズを大きくするとメモリ使用量が減少
- 不要なデータは適切に削除

### 計算時間
- ボクセルサイズを大きくすると計算時間が短縮
- 探索空間を制限すると計算時間が短縮

### 精度
- ボクセルサイズを小さくすると精度が向上
- より多くの近傍を考慮すると精度が向上
