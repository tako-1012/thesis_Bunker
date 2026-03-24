# TA* プロファイリングボトルネック分析

## Smallシナリオ (ta_SMALL.prof)
- _terrain_aware_search: 0.147s
- _clamp_to_grid: 0.107s
- _calculate_terrain_aware_cost: 0.099s
- _calculate_risk_at: 0.065s
- _precompute_terrain_maps: 0.065s
- _calculate_local_complexity_fast: 0.059s
- _has_obstacles_in_column: 0.052s
- _calculate_obstacle_penalty: 0.050s
- _calculate_safety_penalty: 0.047s
- _get_slope_at: 0.040s

## Mediumシナリオ (ta_MEDIUM.prof)
- _terrain_aware_search: 0.312s
- _clamp_to_grid: 0.204s
- _calculate_terrain_aware_cost: 0.189s
- _calculate_risk_at: 0.162s
- is_traversable_with_limit: 0.159s
- _get_slope_at: 0.147s
- _precompute_terrain_maps: 0.078s
- _calculate_local_complexity_fast: 0.077s
- _has_obstacles_in_column: 0.014s

## Largeシナリオ (ta_LARGE.prof)
- _terrain_aware_search: 1.380s
- _clamp_to_grid: 0.753s
- is_traversable_with_limit: 0.746s
- _get_slope_at: 0.723s
- _precompute_terrain_maps: 0.672s
- _calculate_local_complexity_fast: 0.667s
- _has_obstacles_in_column: 0.451s
- _calculate_terrain_aware_cost: 0.393s
- _calculate_risk_at: 0.366s
- _calculate_obstacle_penalty: 0.196s
- _calculate_safety_penalty: 0.060s

---

## ボトルネック関数まとめ
1. _terrain_aware_search
2. _clamp_to_grid
3. _calculate_terrain_aware_cost
4. _calculate_risk_at
5. _precompute_terrain_maps
6. _calculate_local_complexity_fast
7. _has_obstacles_in_column
8. is_traversable_with_limit
9. _get_slope_at
10. _calculate_obstacle_penalty
11. _calculate_safety_penalty

## 改善優先度リスト
1. 探索コア: _terrain_aware_search
2. 地形前処理: _precompute_terrain_maps, _calculate_local_complexity_fast
3. コスト計算: _calculate_terrain_aware_cost, _calculate_risk_at, _calculate_obstacle_penalty, _calculate_safety_penalty
4. グリッド処理: _clamp_to_grid, _has_obstacles_in_column, _get_slope_at
5. 判定関数: is_traversable_with_limit

---

次フェーズでこれら関数の最適化を優先します。
