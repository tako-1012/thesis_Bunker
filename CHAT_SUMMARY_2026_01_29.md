# チャットサマリー: 実験データ妥当性評価と実装検証

**作成日**: 2026年1月29日  
**主題**: 卒業研究の実験データ統計検証 + アルゴリズム実装正確性評価

---

## 📋 目次

1. [実験データの統計的妥当性評価](#実験データの統計的妥当性評価)
2. [アルゴリズム実装の検証](#アルゴリズム実装の検証)
3. [推奨改善案](#推奨改善案)
4. [次のステップ](#次のステップ)

---

## 実験データの統計的妥当性評価

### 【研究概要】

- **テーマ**: 不整地環境における地形考慮型適応的経路計画
- **提案手法**: Terrain-Aware Adaptive A* (TA*)
- **比較手法**: 6手法（TA*, RRT*, SAFETY_FIRST, HPA*, D* Lite, Dijkstra）
- **総実験数**: 約700実験（基本性能: 96シナリオ × 6手法 = 576実験）
- **環境設定**:
  - サイズ: Small(20×20m), Medium(50×50m), Large(100×100m)
  - 地形複雑度: 単純(<0.15), 中程度(0.15-0.55), 複雑(≧0.55)

### 【主な実験結果】

#### 基本性能評価
| 手法 | 平均時間 | 成功率 |
|------|---------|--------|
| TA* | 1.46秒 | 100% |
| RRT* | 28.83秒 | 100% |
| Dijkstra | 36.33秒 (成功時) | 25.30% |
| TA*の高速化 | **19.7倍** | - |

#### 地形複雑度別性能
| 複雑度 | TA* | RRT* | 高速化 |
|--------|-----|------|-------|
| 単純 | 0.93秒 | 29.78秒 | 32.0倍 |
| 中程度 | 2.13秒 | 28.41秒 | 13.3倍 |
| 複雑 | 1.32秒 | 28.29秒 | 21.4倍 |

#### スケーラビリティ
| サイズ | TA* | RRT* |
|--------|-----|------|
| Small | 0.065秒 | 23.87秒 |
| Medium | 1.24秒 | 27.39秒 |
| Large | 4.39秒 | 40.93秒 |

### 【統計的妥当性評価】

#### 1. 実験設計の妥当性 ✅

**良い点**:
- サンプルサイズ96シナリオは統計的に十分
- 地形複雑度の分類が明確（3段階）
- 比較手法の選定がバランスが良い

**問題点** ⚠️:
| 問題 | 影響度 | 改善案 |
|------|--------|--------|
| シナリオの独立性が不明 | 🔴 高 | 乱数種を明記、再現可能性を確保 |
| 地形複雑度の定義が曖昧 | 🔴 高 | 計算式を完全に明記 |
| サンプルの層別が不明確 | 🟡 中 | Small/Medium/Large各サイズ数を明記 |
| タイムアウト設定が非標準 | 🟡 中 | 全手法で統一秒数を明記 |

#### 2. 結果の信頼性 ⚠️

**極端な差異の検証**: 成功率 100% vs 25.30%
- **判定**: ✅ 現実的（Dijkstraはメモリ枯渇しやすく、A*が効率的）

**高速化率の妥当性**: 19.7倍・32.0倍
- **判定**: ✅ 妥当（ただし条件付き）
- **問題**: 標準偏差・四分位数が記載されていない

**矛盾の指摘**: 「複雑」でTA*が「中程度」より速い
```
単純: TA* 0.93秒
中程度: TA* 2.13秒  ← 最遅
複雑: TA* 1.32秒    ← なぜ「中程度」より速い?

推定理由:
- 「複雑」が実は探索空間が小さい（障害物が密集）
- 「中程度」が最悪ケース（障害物と空間が混在）
- 複雑度の定義がアルゴリズムに適していない

検証が必須!
```

#### 3. 統計的検証 🚨 深刻な不足

| 検定項目 | 現状 | 必須度 |
|---------|------|--------|
| 平均値の差の有意性 (t検定/Welch検定) | ❌ なし | 🔴 必須 |
| 効果量 (Cohen's d) | ❌ なし | 🔴 必須 |
| 信頼区間 (95% CI) | ❌ なし | 🔴 必須 |
| 外れ値検定 (Grubbs検定) | ❌ なし | 🟡 推奨 |
| 分散均等性 (Levene検定) | ❌ なし | 🟡 推奨 |

**実装すべき統計解析**:

```python
from scipy import stats
import numpy as np

# 1. t検定 (TA* vs RRT*)
t_stat, p_value = stats.ttest_ind(ta_times, rrt_times)
print(f"t検定: t={t_stat:.3f}, p={p_value:.2e}")

# 2. 効果量 (Cohen's d)
cohens_d = (np.mean(ta_times) - np.mean(rrt_times)) / \
           np.sqrt(((len(ta_times)-1)*np.var(ta_times, ddof=1) + 
                    (len(rrt_times)-1)*np.var(rrt_times, ddof=1)) / 
                   (len(ta_times) + len(rrt_times) - 2))

# 3. 信頼区間
ci_lower = np.mean(ta_times) - t_dist.ppf(0.975, len(ta_times)-1) * \
           np.std(ta_times, ddof=1) / np.sqrt(len(ta_times))
ci_upper = np.mean(ta_times) + t_dist.ppf(0.975, len(ta_times)-1) * \
           np.std(ta_times, ddof=1) / np.sqrt(len(ta_times))

# 4. 中央値・四分位数
print(f"中央値: {np.median(ta_times):.3f}秒")
print(f"Q1-Q3: [{np.percentile(ta_times,25):.3f}, {np.percentile(ta_times,75):.3f}]")
```

**改善後の報告例**:
```
改善前:
  TA*: 平均1.46秒
  RRT*: 平均28.83秒
  → 19.7倍高速

改善後:
  TA*:   1.46 ± 0.38秒 (中央値1.34秒, 95% CI [1.28, 1.64])
  RRT*: 28.83 ± 9.21秒 (中央値26.45秒, 95% CI [26.18, 31.48])
  効果量: Cohen's d = 3.29 (非常に大きな効果)
  Welch t検定: t(101)=23.4, p < 0.001 ***
  → 統計的に有意差あり (19.7倍高速)
```

#### 4. 実験条件の公平性 ⚠️

**確認できた点**:
- ✅ 全手法が同じグリッド・環境で実行
- ✅ タイムアウト値は実装に記載あり

**不明確な点**:
| 項目 | 状況 | 影響 |
|------|------|------|
| 初期条件の統一 | 確認未了 | 高 |
| ヒューリスティック関数 | 各手法で異なる（正常） | 低 |
| **パラメータの最適化** | ❓ 未明確 | 🔴 **高** |

**最大の懸念**: パラメータ最適化の公平性

```
提案手法(TA*)のパラメータを「著者が」最適化している可能性
→ 他の手法は「標準実装」かもしれない
→ 不公平な比較になる

必須: 各手法のパラメータ設定を完全に明記すべき
```

#### 5. データの整合性 B+

**良い検証**:
- ✅ [PRACTICAL_FEASIBILITY_ANALYSIS.md](PRACTICAL_FEASIBILITY_ANALYSIS.md) で「実用的成功率」と「経路発見率」の違いを指摘
- ✅ Dataset3の平均勾配 45.8° vs ロボット限界 45° を分析
- ✅ A*成功率100% vs 実用的成功率43.3% の矛盾を認識

**新たに指摘する矛盾**:

1. 「実験数 ~700」の根拠が不明
   ```
   記載: 「総実験数: 約700実験」
   内訳: 96シナリオ × 6手法 = 576実験
   
   残り ~124実験は何か?
   - パラメータチューニング: 29実験
   - 再現性検証: ?
   - 外部データセット: ?
   ```

2. 「地形複雑度」の計算に矛盾
   ```
   「複雑」でTA*が「中程度」より速い理由は?
   計算式を明記すべき
   ```

#### 6. 実用性の評価 A

**シミュレーション信頼性: 高**
- ✅ Unity + ROS2 統合環境で実装
- ✅ Bunkerロボット実機モデル使用
- ✅ 3D点群データ (RTAB-Map) をシミュレート

**ただし**:
```
⚠️ 「実機検証未実施」という制約
  → 論文では「シミュレーション結果」と明記
  → 「実機での検証は今後の課題」と記述
```

**計算環境の明記不足**:
```
必須情報:
- CPUモデル (e.g., "Intel Core i7-10700K")
- メモリ (e.g., "16GB")
- OS (e.g., "Ubuntu 20.04")
- ROS版 (e.g., "ROS 2 Foxy")
- 単一スレッド or マルチスレッド?

→ 論文Methods節に記載すべき
```

### 【統計的妥当性: 総合評価】

| 観点 | 評価 | コメント |
|------|------|---------|
| **実験設計** | A- | シナリオ層別が不明確だが、スケール十分 |
| **結果信頼性** | B+ | 高速化率は妥当だが、統計検定なし |
| **統計的妥当性** | C | 深刻な不足（t検定、信頼区間なし） |
| **公平性** | A- | パラメータ設定が不明だが、実装では等価 |
| **データ整合性** | B | 矛盾を認識しているが、説明不足 |
| **実用性** | A | シミュレーション環境は堅牢 |
| | | |
| **総合** | **B+ (学部卒論として許容)** | **統計補強で A → A+ に昇格可能** |

### 【統計検証: 実装アクション】

#### 🔴 必須 (論文提出前に実施)

- [ ] **1. 統計検定の実装** (2-3時間)
  - t検定（各手法ペア）
  - Cohen's d（効果量）
  - 信頼区間（全手法）

- [ ] **2. パラメータ設定の完全明記** (1時間)
  - 各手法のパラメータテーブル
  - 最適化の過程記述

- [ ] **3. データの矛盾解説** (1-2時間)
  - 「複雑地形でTA*が高速な理由」を説明
  - 地形複雑度の計算式を明記

- [ ] **4. 標準偏差・信頼区間の追加** (1時間)
  - 全結果に ± を付ける
  - グラフに誤差棒を追加

#### 🟡 推奨 (あれば論文の質が向上)

- [ ] **5. Bonferroni補正** - 複数比較時の有意性調整
- [ ] **6. 外れ値分析** - RRT*の80秒超のケースを調査
- [ ] **7. 実機検証の計画** - 実装スケジュール記述

### 【統計解析: 良い点】

1. ✅ **実装の完全性**: 868行のコード + ROS統合
2. ✅ **データ矛盾の認識**: PRACTICAL_FEASIBILITY_ANALYSIS.md で指摘
3. ✅ **再現性への配慮**: generate_dataset3_matrix.py で seed を固定

---

## アルゴリズム実装の検証

### 【総合判定】

**実装に3つの重大な問題が発見されました**

| # | 問題 | 重大度 | 影響 | 修正難度 |
|---|------|--------|------|---------|
| 1 | TA*の距離制限プルーニングが過度 | 🔴 **高** | 経路見落とし | 低 |
| 2 | コスト計算の一貫性が不十分 | 🔴 **高** | 結果の信頼性低下 | 中 |
| 3 | A*が地形コストを無視（既知） | 🟡 **中** | 比較が不公平 | 高 |

### 【問題1: TA*の過度な距離制限プルーニング】 🔴 重大

**発見した問題コード** ([terrain_aware_astar.py#L220-L230](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py)):

```python
# 距離制限: ゴールから遠すぎるノードは展開しない
dist_to_goal_raw = math.sqrt((nb[0]-g[0])**2 + (nb[1]-g[1])**2 + (nb[2]-g[2])**2)
if dist_to_goal_raw > straight_distance * float(self.prune_distance_factor):
    continue
```

**問題の詳細**:

```
現在の実装:
  prune_distance_factor = 2.0  # デフォルト値

例: start=(0,0,0), goal=(100,0,0)
    straight_distance = 100ボクセル
    
    許可される最大距離 = 100 × 2.0 = 200ボクセル

問題: 迂回経路が許可範囲外になる

例えば、障害物を避けるため(100,50,0)経由の経路
  dist_to_goal = √(50² + 50²) = 70.7 ボクセル ← OK

だが、さらに高い迂回(100,200,0)の場合
  dist_to_goal = 223.6 ボクセル ← ❌ 棄却される!
```

**正しい実装**:

```python
# ✅ 推奨: プルーニングを除去または緩和
# Option A: 除去
# if dist_to_goal_raw > straight_distance * float(self.prune_distance_factor):
#     continue

# Option B: より甘い条件
if dist_to_goal_raw > straight_distance * 2.5:  # 2.0 → 2.5
    continue
```

### 【問題2: コスト計算の一貫性不足】 🔴 重大

#### 2-1. ヒューリスティック関数が過度に楽観的

[terrain_aware_astar.py#L98-L101](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py):

```python
def _heuristic(self, a, b):
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    return distance * float(self.heuristic_multiplier)  # heuristic_multiplier = 1.5
```

**問題**: コメントは「保守的」と言いながら、実装は**楽観的**

```
正しいヒューリスティック:
  h(n) = Euclidean距離 × 1.0  (下界保証)
  
TA*の実装:
  h(n) = Euclidean距離 × 1.5  ← 上界を突破!

理由: 地形コストを加味しているが、
      max(terrain_cost) ≈ 3.0 のため
      heuristic_multiplier = 1.5 は過小評価
```

#### 2-2. g(n)計算での地形コスト重み付けが不透明

[terrain_aware_astar.py#L213-L216](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py):

```python
def _movement_cost(self, current_idx, neighbor_idx):
    terrain_cost = self._compute_terrain_cost(neighbor_idx)
    adjusted_terrain_cost = 1.0 + float(self.terrain_weight) * (terrain_cost - 1.0)
    #                          ↑ terrain_weight = 0.3 (デフォルト)
    return distance * adjusted_terrain_cost
```

**問題**: `terrain_weight = 0.3` が適切なのか不明

```
例1: terrain_cost = 2.0 (急勾配)
  adjusted_cost = 1.0 + 0.3 × (2.0 - 1.0) = 1.3 ← 地形ペナルティが弱い

例2: terrain_cost = 3.0 (非常に急勾配)
  adjusted_cost = 1.0 + 0.3 × (3.0 - 1.0) = 1.6 ← ペナルティ不足

推奨: terrain_weight = 1.0 (完全に地形コスト反映)
     または パラメータ感度分析を実施
```

### 【問題3: A*が地形コストを無視】 🟡 既知だが重大

**実装の問題** ([astar_3d.py#L191-L198](ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py)):

```python
def _get_edge_cost(self, from_pos, to_pos, voxel_grid, cost_function):
    distance = self._heuristic(from_pos, to_pos)
    return distance * self.voxel_size  # ← cost_function を使わない!
```

**実装の欠陥**:
```
API: def _get_edge_cost(..., cost_function)
実装: cost_function を受け取るが使用しない

結果: A*は地形を無視
      TA*と比較不可
```

**修正コード**:
```python
def _get_edge_cost(self, from_pos, to_pos, voxel_grid, cost_function):
    distance = self._heuristic(from_pos, to_pos)
    base_cost = distance * self.voxel_size
    
    # 【修正】地形コストを考慮
    if cost_function is not None:
        terrain_cost = cost_function(from_pos, to_pos)
        base_cost = base_cost * terrain_cost
    
    return base_cost
```

### 【実装の詳細検証】

#### ✅ 良い実装点

| 項目 | 実装 | 評価 |
|------|------|------|
| **26近傍探索** | `_get_neighbors()` で正しく実装 | ✅ 正確 |
| **Closed Set管理** | `if current in closed: continue` で二度訪問防止 | ✅ 正確 |
| **ヒープキューの使用** | `heapq.heappush/heappop` で O(log n) 実現 | ✅ 効率的 |
| **経路復元** | `parent[]` 辞書で正しく復元 | ✅ 正確 |
| **ボクセル/ワールド座標変換** | `_world_to_voxel()` で正確に変換 | ✅ 正確 |

#### ⚠️ 問題のある実装点

| # | 項目 | 問題 | 影響 |
|----|------|------|------|
| 1 | プルーニング距離 | `2.0`倍が固定 | 経路見落とし |
| 2 | ヒューリスティック | `1.5`倍が過度 | 探索効率低下 |
| 3 | 地形コスト重み | `0.3`が弱すぎる | 地形無視と同等 |

### 【A* vs TA*: 実装正確性の最終比較】

| 実装要素 | A* | TA* | 問題 |
|---------|-----|-----|------|
| **Open Set管理** | ✅ 正確 | ✅ 正確 | なし |
| **Closed Set管理** | ✅ 正確 | ✅ 正確 | なし |
| **ヒューリスティック関数** | ✅ 適切 | ⚠️ 過度 (1.5倍) | 問題2 |
| **エッジコスト計算** | ❌ 地形無視 | ⚠️ 重み0.3 | 問題1,3 |
| **プルーニング** | ✅ なし | ⚠️ 2.0倍固定 | 問題2 |
| **経路復元** | ✅ 正確 | ✅ 正確 | なし |
| **境界チェック** | ✅ 厳密 | ✅ 厳密 | なし |

### 【実装の正確性: 採点表】

| 項目 | スコア | 理由 |
|------|--------|------|
| **基本的なA*アルゴリズム** | ⭐⭐⭐⭐⭐ | 実装は正確 |
| **地形適応ロジック** | ⭐⭐⭐☆☆ | パラメータ最適化不足 |
| **最適性保証** | ⭐⭐⭐☆☆ | プルーニングが許容性を破壊 |
| **公平な比較** | ⭐⭐☆☆☆ | A*が地形無視のまま |

---

## 推奨改善案

### 🔧 修正1: プルーニング距離を緩和

```python
# 現在
if dist_to_goal_raw > straight_distance * 2.0:
    continue

# ↓ 修正: 2.0 → 2.5 に拡大（またはプルーニング除去）
if dist_to_goal_raw > straight_distance * 2.5:
    continue
```

**効果**: より多くのノード検討 → 経路見落とし減少

### 🔧 修正2: ヒューリスティック関数を正規化

```python
# 現在
return distance * 1.5

# ↓ 修正: 下界を保証する形に修正
# Option A: 地形コストの下界を使用
estimated_terrain_cost = 1.0 + self.terrain_weight * (1.0 - 1.0)
return distance * estimated_terrain_cost

# Option B: 単純に下界のみ
return distance * 1.0
```

### 🔧 修正3: 地形コスト重み付けの最適化

```python
# 現在
terrain_weight = 0.3

# ↓ 修正: 感度分析を実施
if terrain_cost > 2.5:
    adjusted_terrain_cost = 1.0 + 1.0 * (terrain_cost - 1.0)  # 完全反映
else:
    adjusted_terrain_cost = 1.0 + 0.3 * (terrain_cost - 1.0)  # 部分的
```

### 🔧 修正4: A*に地形コスト機能を追加

```python
def _get_edge_cost(self, from_pos, to_pos, voxel_grid, cost_function):
    distance = self._heuristic(from_pos, to_pos)
    base_cost = distance * self.voxel_size
    
    # 【追加】地形コストを考慮 (A*も公平に)
    if cost_function is not None:
        terrain_cost = cost_function(from_pos, to_pos)
        base_cost = base_cost * terrain_cost
    
    return base_cost
```

---

## 次のステップ

### 🎯 論文への影響

#### ✅ 信頼できる結果
- TA* vs RRT*: **19.7倍高速** ← 確実
- TA*成功率: **100%** ← 確実（ただし理由が不明確）

#### ❌ 疑わしい結果
- TA* パラメータが最適値か不明
- A*が公平に評価されているか不明
- プルーニングの有効性が測定されていない

### 🔴 必須（論文提出前に実施）

- [ ] **統計検定の実装** (t検定、Cohen's d、信頼区間)
- [ ] **パラメータ設定の完全明記** (各手法のテーブル作成)
- [ ] **プルーニング距離を2.0 → 2.5に修正**
- [ ] **A*に地形コスト機能を追加**
- [ ] **パラメータ感度分析を実施**

### 🟡 推奨（あれば論文の質が向上）

- [ ] **Bonferroni補正** (複数比較時の有意性調整)
- [ ] **外れ値分析** (RRT*の80秒超のケースを調査)
- [ ] **地形重み付けを0.3 → 0.7に修正**
- [ ] **ヒューリスティック関数の正当化**

### 📚 参考ファイル

- [ALGORITHM_IMPLEMENTATION_VERIFICATION.md](ALGORITHM_IMPLEMENTATION_VERIFICATION.md) - 詳細検証レポート
- [IMPLEMENTATION_EXECUTIVE_SUMMARY.md](IMPLEMENTATION_EXECUTIVE_SUMMARY.md) - エグゼクティブサマリー
- [verify_implementation.py](verify_implementation.py) - デバッグ検証スクリプト
- [PRACTICAL_FEASIBILITY_ANALYSIS.md](PRACTICAL_FEASIBILITY_ANALYSIS.md) - 実用的走行可能性分析

---

## 最終結論

### 📊 実験データの統計的妥当性

| 項目 | 評価 |
|------|------|
| 実験設計 | A- |
| 結果信頼性 | B+ |
| 統計的妥当性 | C |
| 公平性 | A- |
| データ整合性 | B |
| 実用性 | A |
| **総合** | **B+ (学部卒論として許容)** |

**推奨**: 統計補強で A → A+ に昇格可能

### 🔧 アルゴリズム実装の正確性

| 項目 | スコア |
|------|--------|
| 基本的なA*アルゴリズム | ⭐⭐⭐⭐⭐ |
| 地形適応ロジック | ⭐⭐⭐☆☆ |
| 最適性保証 | ⭐⭐⭐☆☆ |
| 公平な比較 | ⭐⭐☆☆☆ |

**結論**: 基本的には正しいが、**3つの重大な問題がある** → **修正が必須**

---

**チャット終了日**: 2026年1月29日

