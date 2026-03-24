# 【調査完了】D*LiteとTA*が同じ経路長になる理由

## 問題概要

D*LiteとTA*が全シナリオで完全に同じ経路長（例：124.98m）を出力していた。

## 原因究明結果

### 原因1: TA*の地形データキー不一致

**問題**: TA*の実装では `terrain_data['elevation']` を探していたが、Dataset3には `terrain_data['height_map']` しかない。

**コード（修正前）**:
```python
def _compute_slope_cost(self, idx):
    if self.terrain_data is None or 'elevation' not in self.terrain_data:
        return 1.0  # ← 常に1.0を返す！
```

**結果**: TA*の地形コストが機能していない

### 原因2: D*Liteが地形コストを未使用

**問題**: D*Liteの移動コスト計算が `g = current.g_cost + 1.0` で固定値のみ使用。

**コード（修正前）**:
```python
def _dstar_lite_on_grid(self, start, goal):
    # ...
    for neighbor in self._get_neighbors(current.position):
        g = current.g_cost + 1.0  # ← 常に1.0の移動コスト！
```

**結果**: D*Liteも地形コストが機能していない

### 原因3: 経路長計算における地形コスト未適用

**重要な発見**: 仮にD*LiteとTA*が異なる経路を見つけても、ベンチマークで報告される「経路長」はユークリッド距離（地形コスト未適用）のため、見た目には差がない。

FieldD*Hybridが115.52m（7.5%短い）なのは、**地形コストが高い領域を避ける=より直線的な経路=ユークリッド距離が短い** という理由。

## 実装修正

### 修正1: TA*のキーを'height_map'に対応

```python
def _compute_slope_cost(self, idx):
    if self.terrain_data is None:
        return 1.0
    # Support both 'elevation' and 'height_map' keys
    elevation = None
    if 'elevation' in self.terrain_data:
        elevation = self.terrain_data['elevation']
    elif 'height_map' in self.terrain_data:
        elevation = self.terrain_data['height_map']  # ← 追加
    else:
        return 1.0
```

### 修正2: D*Liteに地形コスト計算を追加

```python
def _dstar_lite_on_grid(self, start, goal):
    # ...
    for neighbor in self._get_neighbors(current.position):
        move_cost = self._compute_movement_cost(current.position, neighbor)  # ← 追加
        g = current.g_cost + move_cost  # ← move_costを使用

def _compute_movement_cost(self, current_pos, neighbor_pos):
    """移動コストを計算（Euclidean距離 × 地形コスト）"""
    distance = np.sqrt(...)  # Euclidean
    terrain_cost = self._compute_terrain_cost(neighbor_pos)  # terrain_cost
    return distance * terrain_cost
```

## 地形データの特性

Dataset3の地形は非常に険しい：

| 地点 | 高さ | 最大勾配 | 勾配（度） | 地形コスト |
|------|------|---------|-----------|-----------|
| (50, 50) | 2.47m | 2.821m | 70.5° | 3.00 |
| (75, 75) | 1.85m | 5.224m | 79.2° | 3.00 |
| (100, 100) | 4.82m | 4.010m | 76.0° | 3.00 |

→ フラクタルノイズの勾配が極めて大きく、全域でコスト最大値（3.0）に達している

## 修正後の予想される変化

修正後にベンチマークを再実行すると：

1. **D*Lite**: 経路が変わる可能性（現在の経路は最短距離ベース）
2. **TA***: `terrain_weight=0.3`を適用した経路が計算される
3. **経路長の差**: FieldD*Hybridとの差がさらに明確になる（より短い経路）

## ファイル修正箇所

- `/path_planner_3d/path_planner_3d/terrain_aware_astar.py` - `_compute_slope_cost`関数
- `/path_planner_3d/path_planner_3d/dstar_lite_3d.py` - `_dstar_lite_on_grid`関数 + `_compute_movement_cost`追加

## 次のステップ

1. ✅ TA*を修正（'elevation' → 'height_map'対応）
2. ✅ D*Liteを修正（地形コスト計算を追加）
3. ⏳ ベンチマークを再実行
4. ⏳ FieldD*との経路長差を検証
5. ⏳ 実コストベースの比較レポートを生成

---

**報告日**: 2026年1月27日
**調査者**: GitHub Copilot
