# Path Planner 3D Module

## 概要

Path Planner 3D Moduleは、3次元地形情報を基に最適な経路を計画するモジュールです。A*アルゴリズムを使用し、傾斜、障害物、安定性を考慮した経路を生成します。

## コンポーネント

### 1. PathPlanner3DNode
- **ファイル**: `path_planner_node.py`
- **役割**: ROS2ノードとして経路計画を統合
- **入力**: `/terrain/voxel_grid`, `/goal_pose`, `/current_pose`
- **出力**: `/path_3d`, `/path_cost`, `/path_visualization`

### 2. AStar3D
- **ファイル**: `astar_3d.py`
- **役割**: 3次元A*アルゴリズムによる経路計画
- **機能**:
  - 26近傍探索
  - ヒューリスティック計算
  - 優先度キュー管理

### 3. CostFunction
- **ファイル**: `cost_function.py`
- **役割**: 経路コストの計算
- **機能**:
  - 距離コスト計算
  - 傾斜コスト計算
  - 障害物近接コスト計算
  - 安定性コスト計算

### 4. PathSmoother
- **ファイル**: `path_smoother.py`
- **役割**: 生成された経路の平滑化
- **機能**:
  - 三次スプライン補間
  - 勾配降下法最適化
  - 単純平均化

## 使用方法

```python
from bunker_3d_nav.path_planner_3d import PathPlanner3DNode, AStar3D, CostFunction, PathSmoother

# ノードの起動
node = PathPlanner3DNode()

# 個別コンポーネントの使用
astar = AStar3D(voxel_size=0.1, max_iterations=10000)
cost_func = CostFunction(weights, safety_params)
smoother = PathSmoother(method='cubic_spline')
```

## パラメータ

### 経路計画パラメータ
| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `max_iterations` | 10000 | A*最大反復回数 |
| `planning_timeout` | 10.0 | 計画タイムアウト [秒] |
| `voxel_size` | 0.1 | ボクセルサイズ [m] |

### コスト関数重み
| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `weight_distance` | 1.0 | 距離重み |
| `weight_slope` | 3.0 | 傾斜重み |
| `weight_obstacle` | 5.0 | 障害物重み |
| `weight_stability` | 4.0 | 安定性重み |

### 安全パラメータ
| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `min_obstacle_distance` | 0.5 | 最小障害物距離 [m] |
| `max_roll_angle` | 20.0 | 最大ロール角 [度] |
| `max_pitch_angle` | 25.0 | 最大ピッチ角 [度] |

### 経路平滑化パラメータ
| パラメータ | デフォルト値 | 説明 |
|-----------|-------------|------|
| `smoothing_method` | 'cubic_spline' | 平滑化手法 |
| `smoothness_factor` | 0.5 | 平滑化係数 [0-1] |

## 出力メッセージ

### Path (nav_msgs/Path)
- `header`: ヘッダー情報
- `poses`: 経路点のリスト (PoseStamped)

### PathCost (bunker_3d_nav/PathCost)
- `header`: ヘッダー情報
- `total_cost`: 総コスト
- `distance_cost`: 距離コスト
- `slope_cost`: 傾斜コスト
- `obstacle_cost`: 障害物近接コスト
- `stability_cost`: 安定性コスト
- `path_length`: 経路長 [m]
- `max_slope`: 経路上の最大傾斜 [度]
- `avg_slope`: 経路上の平均傾斜 [度]

## アルゴリズム詳細

### A* 3Dアルゴリズム
1. **初期化**: スタート位置をオープンセットに追加
2. **探索**: 26近傍のボクセルを探索
3. **コスト計算**: f(n) = g(n) + h(n)
   - g(n): スタートから現在位置までのコスト
   - h(n): 現在位置からゴールまでのヒューリスティック
4. **最適化**: 最小f(n)のノードを選択
5. **終了条件**: ゴール到達またはタイムアウト

### コスト関数
```python
total_cost = w1 * distance_cost +
             w2 * slope_cost +
             w3 * obstacle_cost +
             w4 * stability_cost
```

### 経路平滑化
- **Cubic Spline**: 三次スプライン補間による平滑化
- **Gradient Descent**: 勾配降下法による最適化
- **Simple Averaging**: 移動平均による平滑化

## 実装状況

- [x] ノードスケルトン実装
- [x] A*アルゴリズム構造
- [x] コスト関数構造
- [x] 経路平滑化構造
- [x] パラメータ管理
- [ ] A*アルゴリズム実装
- [ ] コスト計算実装
- [ ] 経路平滑化実装
- [ ] パフォーマンス最適化
