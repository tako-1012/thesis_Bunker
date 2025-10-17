# A* 3D Path Planner

3D空間でのA*経路計画アルゴリズム実装

## クイックスタート

### 全テスト実行（推奨）
```bash
cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/path_planner_3d
./run_all_tests.sh
```

### クイックテスト（基本テストのみ）
```bash
./quick_test.sh
```

### 個別テスト実行
```bash
# Node3Dテスト
python3 test_node_3d.py

# A*基本テスト
python3 test_astar_basic.py

# 可視化テスト
python3 visualize_path.py

# パフォーマンステスト
python3 performance_test.py

# エッジケーステスト
python3 edge_case_test.py
```

## テスト内容

1. **Node3Dテスト**: データ構造の基本動作
2. **A*基本テスト**: 経路探索の基本機能
3. **インタラクティブテスト**: 様々な距離での動作確認
4. **可視化テスト**: 経路の可視化（PNG生成）
5. **パフォーマンステスト**: 計算速度の測定
6. **エッジケーステスト**: 境界条件の確認

## 生成されるファイル

- `astar_path_3d.png`: 3D経路の可視化
- `astar_path_2d.png`: 2D経路の可視化（上面図）

## 主要クラス

- `Node3D`: 3D空間のノード
- `AStarPlanner3D`: A*経路計画アルゴリズム

## 使用方法

### 基本的な使用方法
```python
from astar_planner_3d import AStarPlanner3D

# プランナー作成
planner = AStarPlanner3D(
    voxel_size=0.1,
    grid_size=(100, 100, 10),
    min_bound=(-5.0, -5.0, 0.0)
)

# 経路計画
start = (0.0, 0.0, 0.5)
goal = (3.0, 3.0, 1.0)
path = planner.plan_path(start, goal)

if path is not None:
    print(f"経路が見つかりました: {len(path)}点")
    stats = planner.get_search_stats()
    print(f"探索ノード数: {stats['nodes_explored']}")
    print(f"計算時間: {stats['computation_time']:.4f}秒")
else:
    print("経路が見つかりませんでした")
```

## パラメータ

### AStarPlanner3D
- `voxel_size`: ボクセルサイズ（メートル）
- `grid_size`: グリッドサイズ（x, y, z）
- `min_bound`: グリッドの最小境界（ワールド座標）

## アルゴリズム特徴

- **26近傍探索**: 3D空間での効率的な探索
- **ユークリッド距離ヒューリスティック**: 最適解を保証
- **優先度キュー**: 効率的なノード管理
- **座標変換**: ワールド座標とボクセル座標の双方向変換

## パフォーマンス

- **計算時間**: 通常0.001-0.01秒
- **メモリ使用量**: 500MB以内
- **探索効率**: 高効率なA*アルゴリズム

## テスト結果例

```
=== test_planner_creation ===
✅ プランナー作成テスト成功

=== test_coordinate_conversion ===
  ワールド座標 (0.0, 0.0, 1.0) → ボクセル (50, 50, 10)
  ボクセル (50, 50, 10) → ワールド座標 (0.05, 0.05, 1.05)
✅ 座標変換テスト成功

=== test_neighbors ===
  位置 (50, 50, 5) の近傍数: 26
  位置 (0, 0, 0) の近傍数: 7
✅ 近傍取得テスト成功

=== test_simple_path ===
  経路長: 11点
  開始点: (0.05, 0.05, 0.55)
  目標点: (1.05, 1.05, 0.55)
  探索ノード数: 11
  計算時間: 0.0030秒
✅ 簡単な経路探索テスト成功

✅ 全てのA*基本テストが成功しました！
```

## 重要な注意事項

### グリッド範囲と座標の関係

グリッドの設定例:
- voxel_size: 0.1m
- grid_size: (100, 100, 30)
- min_bound: (-5.0, -5.0, 0.0)

この場合の実際の範囲:
- X: -5.0m ~ +4.9m（ボクセル0-99）
- Y: -5.0m ~ +4.9m（ボクセル0-99）
- Z: 0.0m ~ +2.9m（ボクセル0-29）

**重要**: 最大境界は`min_bound + grid_size * voxel_size - voxel_size`

経路計画時は、座標が範囲内にあることを確認してください：
```python
# OK: 範囲内
planner.plan_path((0.0, 0.0, 0.5), (4.9, 4.9, 2.9))

# NG: 最大境界ちょうどは範囲外
planner.plan_path((0.0, 0.0, 0.5), (5.0, 5.0, 3.0))
```

### グリッド範囲の確認方法
```python
planner = AStarPlanner3D(
    voxel_size=0.1,
    grid_size=(100, 100, 30),
    min_bound=(-5.0, -5.0, 0.0)
)

# 最大境界を計算
max_bound = (
    planner.min_bound[0] + (planner.grid_size[0] - 1) * planner.voxel_size,
    planner.min_bound[1] + (planner.grid_size[1] - 1) * planner.voxel_size,
    planner.min_bound[2] + (planner.grid_size[2] - 1) * planner.voxel_size
)

print(f"有効範囲: {planner.min_bound} ~ {max_bound}")
```

## 今後の拡張予定

- **コスト関数統合**: 傾斜、障害物、転倒リスクを考慮
- **経路平滑化**: Cubic spline補間
- **ROS2統合**: ノードとしての実装
- **Unity連携**: シミュレーション環境との統合