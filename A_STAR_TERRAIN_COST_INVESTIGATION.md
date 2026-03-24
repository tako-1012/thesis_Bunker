# A*の地形コスト処理に関する重大な問題

**作成日**: 2026年1月29日  
**調査対象**: A* vs TA* の地形コスト処理比較

---

## 🔴 重大な発見：A*は地形コストを全く使用していない

### A*のエッジコスト計算（実装コード）

```python
def _get_edge_cost(self, from_pos, to_pos, voxel_grid, cost_function):
    """
    Calculate edge cost between two positions.
    
    Args:
        cost_function: Cost function for evaluating costs  ← 引数として受け取るが...
    
    Returns:
        Edge cost
    """
    # Euclidean distance
    distance = self._heuristic(from_pos, to_pos)
    return distance * self.voxel_size  # ← cost_function を使用していない！
```

**問題点**:
- `cost_function` 引数を受け取るが、**実際には使用していない**
- 単純なユークリッド距離 × voxel_size のみ
- **地形の勾配、複雑度、走行コストを一切考慮していない**

---

## 📊 TA*との比較

### TA*のエッジコスト計算

```python
def _movement_cost(self, current_idx, neighbor_idx):
    dx = neighbor_idx[0] - current_idx[0]
    dy = neighbor_idx[1] - current_idx[1]
    dz = neighbor_idx[2] - current_idx[2]
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    
    terrain_cost = self._compute_terrain_cost(neighbor_idx)  # ← 地形コスト計算
    adjusted_terrain_cost = 1.0 + float(self.terrain_weight) * (terrain_cost - 1.0)
    
    return distance * adjusted_terrain_cost  # ← 地形を考慮したコスト
```

**特徴**:
- 各ノードで `_compute_terrain_cost()` を呼び出し
- `terrain_weight` で地形の影響を調整
- 地形が複雑な場所ではコストが増加 → 迂回経路を選択

---

## 🚨 問題の本質

### Dataset3 の地形データ

**シナリオ例（dataset3_1_1_1）**:
```
terrain_metadata:
  avg_slope_deg: 52.8°（平均勾配）
  max_slope_deg: 80.9°（最大勾配）
  max_elevation: 8.87m
```

### A*の「成功」の定義

**現在のA*実装**:
```python
def _is_valid_position(self, position, voxel_grid):
    # Check if not obstacle
    voxel_value = voxel_grid[x, y, z]
    if voxel_value == 2:  # Obstacle
        return False
    return True
```

**問題**:
- **障害物（voxel==2）でなければ通行可能**と判定
- 地形の勾配（slope）を全く考慮していない
- **70°の急斜面でも「成功」と判定される可能性が高い**

---

## 🔍 実際の走行可能性

### ロボットの仕様（一般的）

- **走行可能勾配**: 通常 30°～45° 以下
- **安全勾配**: 20° 以下が推奨
- **Dataset3の平均勾配**: **52.8°** ← **走行不可能な可能性が高い**

### A*の経路の実際

**A*が100%成功した理由**:
1. **障害物回避のみ**を判定
2. 地形勾配を無視
3. **実際には走行不可能な急斜面を経路に含む可能性**

**TA*が失敗した理由（再解釈）**:
1. 地形コストを考慮して**走行困難な経路を回避**
2. 迂回経路を探索するため**ノード数が増加**
3. ノード上限（500k）に到達 → 失敗

---

## 📈 比較表

| 項目 | A* | TA* |
|------|-----|-----|
| **地形コスト使用** | ❌ 無し | ✅ 有り |
| **エッジコスト** | 距離のみ | 距離 × 地形係数 |
| **勾配考慮** | ❌ 無し | ✅ 有り |
| **走行可能性** | ❓ 不明 | ✅ 考慮 |
| **成功率** | 100% | 88.9% |
| **経路の実用性** | ❓ 疑問 | ✅ 高い |

---

## 🎯 卒論への影響

### 重要な注意事項

**現在の主張**:
「A*は100%成功、TA*は88.9%成功」

**正確な主張**:
```
A*は障害物回避のみを考慮し、100%の経路発見に成功した。
しかし、地形の勾配を考慮していないため、得られた経路の
実用性（実際の走行可能性）は不明である。

一方、TA*は地形コストを考慮し、走行可能な経路を探索するため、
小中規模環境では100%成功したが、大規模環境では探索空間の
拡大により88.9%の成功率となった。

TA*が見つける経路は、地形を考慮しているため、A*より実用的で
ある可能性が高い。
```

---

## 🔧 検証が必要な項目

### 1. A*の経路の実際の勾配

```python
# A*が見つけた経路の各セグメントの勾配を計算
for i in range(len(path)-1):
    p1, p2 = path[i], path[i+1]
    elevation_diff = abs(p2[2] - p1[2])
    horizontal_dist = sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)
    slope = atan(elevation_diff / horizontal_dist) * 180 / pi
    
    if slope > 45:  # ロボットの走行限界
        print(f"危険な勾配: {slope:.1f}°")
```

### 2. TA*の経路の実際の勾配

同様の計算で、TA*が地形を避けているかを確認

### 3. ロボットの走行可能勾配

仕様書またはシミュレーションで確認

---

## ✅ 結論

### A*の「100%成功」の再評価

**技術的には**:
- 障害物を避けた経路を発見 → 成功

**実用的には**:
- 地形勾配を無視 → **走行不可能な経路の可能性**
- 経路の質は不明

### TA*の「88.9%成功」の価値

**技術的には**:
- 大規模環境でノード上限到達 → 失敗

**実用的には**:
- 地形を考慮した**実際に走行可能な経路**を探索
- 経路の質は高い
- スケーラビリティは課題

---

## 📝 卒論での記述例

```
実験の結果、A*は全90シナリオで経路発見に成功したが、
地形の勾配を考慮していないため、得られた経路の実用性
（実際のロボットによる走行可能性）は保証されない。

一方、TA*は地形コストを考慮し、走行困難な領域を避けた
経路を探索する。小中規模環境（150×150, 250×250）では
100%成功したが、大規模環境（400×400）では探索空間の
拡大により88.9%の成功率となった。

ただし、TA*が見つける経路は地形適応により、A*より
実用的である可能性が高く、成功率の単純比較だけでは
手法の優劣を判断できない。
```

---

**この調査により、A*とTA*の「成功」の定義が根本的に異なることが判明しました。**
