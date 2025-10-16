# A* 3D経路計画アルゴリズム設計書

## 1. アルゴリズム概要

### 1.1 A*アルゴリズムの基本原理
A*は最適経路探索アルゴリズムで、以下の評価関数を使用する：

```
f(n) = g(n) + h(n)
```

- **g(n)**: スタートノードから現在ノードnまでの実際のコスト
- **h(n)**: 現在ノードnからゴールノードまでの推定コスト（ヒューリスティック）
- **f(n)**: 総コスト（優先度キューでの比較に使用）

### 1.2 3D空間への拡張
2D A*から3Dへの拡張では以下の変更が必要：

1. **ノード表現**: `(x, y)` → `(x, y, z)`
2. **近傍探索**: 4近傍 → 26近傍（3×3×3 - 自分自身）
3. **移動コスト**: 2D距離 → 3D距離（√2, √3の考慮）
4. **ヒューリスティック**: 2Dユークリッド距離 → 3Dユークリッド距離

### 1.3 ヒューリスティック関数の選択

#### ユークリッド距離（推奨）
```python
h(n) = √((x₁-x₂)² + (y₁-y₂)² + (z₁-z₂)²)
```
- **利点**: 最適解を保証、計算が簡単
- **欠点**: 斜め移動のコストを正確に反映

#### マンハッタン距離
```python
h(n) = |x₁-x₂| + |y₁-y₂| + |z₁-z₂|
```
- **利点**: 計算が高速
- **欠点**: 3D空間では不正確、探索効率が悪い

**結論**: ユークリッド距離を採用（最適性と実装の簡潔性を両立）

## 2. データ構造設計

### 2.1 Node3Dクラス
```python
from typing import Tuple, Optional
from dataclasses import dataclass

@dataclass
class Node3D:
    """3D空間のノード"""
    
    # 位置（ボクセルグリッドのインデックス）
    position: Tuple[int, int, int]
    
    # コスト
    g_cost: float = float('inf')  # スタートからのコスト
    h_cost: float = 0.0           # ゴールまでの推定コスト
    
    # 親ノード
    parent: Optional['Node3D'] = None
    
    @property
    def f_cost(self) -> float:
        """総コスト = g + h"""
        return self.g_cost + self.h_cost
    
    def __eq__(self, other):
        """位置が同じなら同一ノード"""
        return self.position == other.position
    
    def __hash__(self):
        """ハッシュ値（dictのキーとして使用）"""
        return hash(self.position)
    
    def __lt__(self, other):
        """優先度キューでの比較（f_costで比較）"""
        return self.f_cost < other.f_cost
```

### 2.2 AStarPlanner3Dクラス
```python
import heapq
from typing import List, Tuple, Optional, Set
import numpy as np
from node_3d import Node3D

class AStarPlanner3D:
    """A* 3D経路計画"""
    
    def __init__(self, voxel_size: float = 0.1):
        self.voxel_size = voxel_size
        self.voxel_grid = None
        self.terrain_data = None
        self.cost_calculator = None
    
    def set_terrain_data(self, voxel_grid, terrain_data):
        """地形データを設定"""
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
    
    def plan_path(
        self,
        start: Tuple[float, float, float],
        goal: Tuple[float, float, float],
        smooth_path: bool = True
    ) -> Optional[List[Tuple[float, float, float]]]:
        """
        経路計画のメイン関数
        
        Args:
            start: 開始位置（ワールド座標）
            goal: 目標位置（ワールド座標）
            smooth_path: 経路平滑化の有無
        
        Returns:
            経路（ワールド座標のリスト）、失敗時はNone
        """
        # ワールド座標 → ボクセルインデックス変換
        start_idx = self._world_to_voxel(start)
        goal_idx = self._world_to_voxel(goal)
        
        # A*アルゴリズム実行
        path_indices = self._astar_search(start_idx, goal_idx)
        
        if path_indices is None:
            return None
        
        # ボクセルインデックス → ワールド座標変換
        path_world = [self._voxel_to_world(idx) for idx in path_indices]
        
        # 経路平滑化（オプション）
        if smooth_path:
            path_world = self.path_smoother.smooth_path(path_world)
        
        return path_world
```

## 3. 26近傍探索

### 3.1 近傍定義
3D空間での近傍は以下の通り：

- **6近傍**: 直交方向のみ（±x, ±y, ±z）
- **18近傍**: 6近傍 + 面方向の斜め（12方向）
- **26近傍**: 18近傍 + 空間対角線（8方向）

**採用**: 26近傍（最適解を保証）

### 3.2 移動コスト
```python
def _calculate_move_cost(self, from_pos, to_pos):
    """移動コスト計算"""
    dx = abs(from_pos[0] - to_pos[0])
    dy = abs(from_pos[1] - to_pos[1])
    dz = abs(from_pos[2] - to_pos[2])
    
    # 移動タイプ判定
    if dx + dy + dz == 1:
        # 直交移動（6近傍）
        return self.voxel_size
    elif dx + dy + dz == 2 and (dx == 0 or dy == 0 or dz == 0):
        # 面方向斜め移動（12近傍）
        return self.voxel_size * np.sqrt(2)
    else:
        # 空間対角線移動（8近傍）
        return self.voxel_size * np.sqrt(3)
```

### 3.3 障害物チェック
```python
def _is_traversable(self, pos: Tuple[int, int, int]) -> bool:
    """走行可能チェック"""
    # グリッド範囲内チェック
    if not self._is_in_grid(pos):
        return False
    
    # ボクセルタイプチェック
    voxel_type = self.voxel_grid.get_voxel_type(pos)
    if voxel_type == VoxelType.OBSTACLE:
        return False
    
    # 傾斜チェック
    slope = self.terrain_data.get_slope(pos)
    if slope > self.max_slope_angle:
        return False
    
    return True
```

## 4. コスト関数設計

### 4.1 統合コスト関数
```python
total_cost = (
    base_cost +           # 基本移動コスト
    slope_cost +          # 傾斜ペナルティ
    obstacle_cost +       # 障害物回避コスト
    risk_cost +           # 転倒リスクコスト
    smoothness_cost       # 経路平滑化コスト
)
```

### 4.2 各コストの詳細

#### 基本移動コスト
```python
def _base_cost(self, from_pos, to_pos):
    """基本移動コスト（距離ベース）"""
    dx = from_pos[0] - to_pos[0]
    dy = from_pos[1] - to_pos[1]
    dz = from_pos[2] - to_pos[2]
    return np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
```

#### 傾斜コスト
```python
def _slope_cost(self, slope_deg: float) -> float:
    """傾斜コスト（指数関数的に増加）"""
    if slope_deg < 15.0:
        return 0.0
    elif slope_deg < 25.0:
        return (slope_deg - 15.0) / 10.0  # 0-1
    elif slope_deg < 35.0:
        return 1.0 + (slope_deg - 25.0) / 5.0  # 1-3
    else:
        return 1000.0  # 実質走行不可
```

#### 障害物回避コスト
```python
def _obstacle_cost(self, distance_to_obstacle: float) -> float:
    """障害物近接コスト"""
    safety_margin = 0.5  # [m]
    if distance_to_obstacle < safety_margin:
        return 1000.0
    else:
        return 1.0 / distance_to_obstacle
```

#### 転倒リスクコスト
```python
def _risk_cost(self, roll: float, pitch: float) -> float:
    """転倒リスクコスト"""
    risk = max(abs(roll), abs(pitch))
    threshold = 20.0  # [度]
    
    if risk > threshold:
        return 10.0 * risk
    else:
        return risk
```

#### 平滑化コスト
```python
def _smoothness_cost(self, turn_angle: float) -> float:
    """急旋回ペナルティ"""
    return abs(turn_angle) * 0.1
```

### 4.3 重み付けパラメータ
```yaml
weights:
  distance: 1.0      # 基本距離
  slope: 3.0         # 傾斜を重視
  obstacle: 5.0      # 障害物回避を最重視
  risk: 4.0          # 転倒リスクを重視
  smoothness: 1.0    # 平滑化
```

## 5. 経路平滑化アルゴリズム

### 5.1 Cubic Spline補間
```python
from scipy.interpolate import CubicSpline

def smooth_path(self, path):
    """Cubic spline補間による平滑化"""
    if len(path) < 3:
        return path
    
    # パラメータt（経路長に沿ったパラメータ）
    t = self._calculate_path_parameter(path)
    
    # Cubic spline補間
    cs_x = CubicSpline(t, path[:, 0])
    cs_y = CubicSpline(t, path[:, 1])
    cs_z = CubicSpline(t, path[:, 2])
    
    # 補間
    t_new = np.linspace(t[0], t[-1], self.num_points)
    x_new = cs_x(t_new)
    y_new = cs_y(t_new)
    z_new = cs_z(t_new)
    
    return np.column_stack([x_new, y_new, z_new])
```

### 5.2 勾配降下法による最適化
```python
def optimize_path_gradient_descent(self, path, iterations=100):
    """勾配降下法による経路最適化"""
    optimized_path = path.copy()
    
    for i in range(iterations):
        gradient = self._calculate_gradient(optimized_path)
        optimized_path -= self.learning_rate * gradient
        
        # 制約チェック
        optimized_path = self._apply_constraints(optimized_path)
    
    return optimized_path
```

### 5.3 制約条件
```python
def _check_constraints(self, path):
    """制約チェック"""
    # 最大傾斜チェック
    slopes = self._calculate_slopes(path)
    if np.max(slopes) > self.max_slope_deg:
        return False
    
    # 最小曲率半径チェック
    curvatures = self._calculate_curvatures(path)
    if np.min(curvatures) < self.min_curve_radius:
        return False
    
    return True
```

## 6. パフォーマンス最適化

### 6.1 ヒープの効率的実装
```python
import heapq

# 優先度キュー（ヒープ）の使用
open_list = []
heapq.heappush(open_list, start_node)

# ノードの重複チェック用辞書
all_nodes = {start: start_node}
```

### 6.2 探索空間の制限
```python
def _limit_search_space(self, start, goal):
    """探索空間を制限（バウンディングボックス）"""
    margin = 50  # ボクセル単位
    min_x = min(start[0], goal[0]) - margin
    max_x = max(start[0], goal[0]) + margin
    min_y = min(start[1], goal[1]) - margin
    max_y = max(start[1], goal[1]) + margin
    min_z = min(start[2], goal[2]) - margin
    max_z = max(start[2], goal[2]) + margin
    
    return (min_x, max_x, min_y, max_y, min_z, max_z)
```

### 6.3 早期終了条件
```python
def _should_terminate(self, current, goal, iterations):
    """早期終了条件"""
    # ゴール到達
    if current.position == goal:
        return True
    
    # 最大反復回数
    if iterations > self.max_iterations:
        return True
    
    # オープンリストが空
    if not self.open_list:
        return True
    
    return False
```

## 7. 実装の優先順位

### Phase 1: 基本実装（Day 9）
1. Node3Dクラス実装
2. AStarPlanner3D基本構造
3. 26近傍探索
4. 基本的なヒューリスティック

### Phase 2: コスト関数統合（Day 10）
1. CostCalculatorクラス実装
2. 傾斜コスト統合
3. 障害物コスト統合
4. 転倒リスクコスト統合

### Phase 3: 経路平滑化（Day 11）
1. PathSmootherクラス実装
2. Cubic spline補間
3. 制約チェック
4. A*への統合

### Phase 4: 最適化・統合（Day 12）
1. パフォーマンス最適化
2. Unity統合
3. テスト・デバッグ
4. ドキュメント整備

## 8. 推定所要時間

- **Day 9**: 6-8時間（基本実装）
- **Day 10**: 6-8時間（コスト関数）
- **Day 11**: 4-6時間（平滑化）
- **Day 12**: 4-6時間（統合・テスト）

**合計**: 20-28時間

## 9. 成功指標

### 機能面
- [ ] 3D空間での経路探索が正常動作
- [ ] 傾斜を考慮した経路生成
- [ ] 障害物回避機能
- [ ] 経路平滑化機能

### 性能面
- [ ] 計算時間: 10秒以内（100×100×10グリッド）
- [ ] メモリ使用量: 500MB以内
- [ ] 経路品質: 傾斜30度以下、障害物0.5m以上離隔

### 統合面
- [ ] ROS2ノードとして動作
- [ ] Unity連携機能
- [ ] Rviz可視化対応

---

**作成日**: 2025-10-11  
**更新日**: 2025-10-11  
**作成者**: AI研究アシスタント


