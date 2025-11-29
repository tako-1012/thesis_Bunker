# TA-A* 最適化レポート

生成日: 2025-10-28 15:20:16

## 1. Top 10 Bottlenecks

### 1. _is_valid_position in terrain_aware_astar_planner_3d.py

- Total time: 11523830.000s
- Call count: 11,523,830
- Avg per call: 1000.00ms

### 2. _calculate_slope in terrain_aware_astar_planner_3d.py

- Total time: 5890009.000s
- Call count: 5,890,009
- Avg per call: 1000.00ms

### 3. <built-in method builtins.abs> in ~

- Total time: 5451328.000s
- Call count: 5,451,328
- Avg per call: 1000.00ms

### 4. _calculate_position_risk in terrain_aware_astar_planner_3d.py

- Total time: 2284889.000s
- Call count: 2,284,889
- Avg per call: 1000.00ms

### 5. _calculate_terrain_cost in terrain_aware_astar_planner_3d.py

- Total time: 2284889.000s
- Call count: 2,284,889
- Avg per call: 1000.00ms

### 6. <built-in method builtins.id> in ~

- Total time: 815190.000s
- Call count: 815,190
- Avg per call: 1000.00ms

### 7. <built-in method _heapq.heappush> in ~

- Total time: 815184.000s
- Call count: 815,184
- Avg per call: 1000.00ms

### 8. __init__ in terrain_aware_astar_planner_3d.py

- Total time: 810458.000s
- Call count: 810,458
- Avg per call: 1000.00ms

### 9. _calculate_adaptive_heuristic in terrain_aware_astar_planner_3d.py

- Total time: 810455.000s
- Call count: 810,455
- Avg per call: 1000.00ms

### 10. <built-in method time.time> in ~

- Total time: 723646.000s
- Call count: 723,646
- Avg per call: 1000.00ms

## 2. 最適化提案

### 1. 地形評価のキャッシング

**説明**: 同じ位置の地形評価を複数回行わない

**期待効果**: 2-3x

**難易度**: 低

**優先度**: 高

### 2. ヒューリスティックの簡略化

**説明**: 複雑な地形適応ヒューリスティックを簡略版に

**期待効果**: 1.5-2x

**難易度**: 中

**優先度**: 高

### 3. 探索範囲の制限

**説明**: 26近傍から14近傍に減らす

**期待効果**: 1.3-1.5x

**難易度**: 低

**優先度**: 中

### 4. 早期終了判定

**説明**: 十分な候補が見つかったら探索を終了

**期待効果**: 1.2-1.4x

**難易度**: 中

**優先度**: 中

### 5. コスト関数の簡略化

**説明**: 詳細な地形分析を簡易版に

**期待効果**: 1.5-2x

**難易度**: 中

**優先度**: 中

