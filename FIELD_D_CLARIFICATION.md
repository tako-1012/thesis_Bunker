# Field D* vs FieldD*Hybrid 整理レポート

**作成日**: 2026年1月19日  
**目的**: 論文本文とコード/データの整合性を確認

---

## 【質問1の回答】「Field D*」という名前の手法は存在するか？

### **Answer: 実装に3つ存在するが、実験データには1つだけ**

#### 実装ファイル（3つ存在）

| ファイル名 | クラス名 | 説明 |
|-----------|--------|------|
| `field_d_star.py` | `FieldDStar` | 簡易版：D*Liteをベース + 視線ショートカット |
| `field_d_star_proper.py` | `FieldDStarProper` | 完全版：エッジ上の仮想ノード + 補間 |
| `field_d_star_hybrid.py` | `FieldDStarHybrid` | ハイブリッド版：滑動ウィンドウ局所最適化 |

#### 実験データ（1つだけ）

`dataset3_8planners_results.json` に含まれるプランナー：
- D*Lite
- RRT*
- HPA*
- SAFETY
- **FieldD*Hybrid** ← **これだけが実験対象**
- TA*
- Theta*
- MPAA*

---

## 【質問2の回答】どのファイルに実装されているか？

### **Answer: 「FieldD*Hybrid」だけが実験対象**

#### マッピング表

| 実装 | クラス名 | 実験実施 | 理由 |
|-----|--------|--------|------|
| field_d_star.py | FieldDStar | ✗ NO | 実験スクリプトに含まれていない |
| field_d_star_proper.py | FieldDStarProper | ✗ NO | 実験スクリプトに含まれていない |
| field_d_star_hybrid.py | FieldDStarHybrid | ✅ YES | `run_benchmark_8planners.py` に含まれる |

#### 実験スクリプトの確認

**`run_benchmark_8planners.py` (Line 220):**
```python
planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'MPAA*']
```

**`full_benchmark_6_planners.py` (Line 317):**
```python
planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']
```

↑ 6プランナー版には Field D* 系が**一切含まれない**

---

## 【質問3の回答】本文の「Field D*」は「FieldD*Hybrid」のことか？

### **Answer: YES - 本文の「Field D*」= 「FieldD*Hybrid」**

#### 本文の記載

```
Chapter 4（提案手法）:
  4.3 TA*の提案
  4.6 Field D* Hybridの提案
  
Chapter 5（実験方法）:
  比較手法として，Regular A*，RRT*，D*Lite，Field D*を用いた。
```

#### TA*の実装コードから確認

**`ta_star.py` (Line 1-10):**
```python
"""
TA*: Terrain-Aware Adaptive Planner
地形考慮型適応的経路計画システム

Field D* Hybridをベースに、適応的選択機能を統合
"""
```

#### 結論

- ✅ 4.6で提案したのは「Field D* Hybrid」
- ✅ Chapter 5の「Field D*」は「Field D* Hybrid」の省略記載
- ✅ 他の Field D* 実装（Simple, Proper）は論文に関連しない

---

## 【質問4の回答】論文用図の手法セット

### **Answer: オプションA（5手法）が正しい**

#### 推奨セット（オプションA）

```
5手法：
  1. D*Lite              (基本・グリッドベース)
  2. RRT*                (確率ロードマップ)
  3. Regular A*          (基本グリッド型)
  4. FieldD*Hybrid       (任意角・提案の相互作用対象)
  5. TA*                 (提案手法)
```

#### タイトルの修正

```
変更前: "Computation Time Comparison (6 Planners)"
変更後: "Computation Time Comparison (5 Methods)"
```

---

## 実装と論文の対応関係

### Field D* 系の開発履歴

```
1. FieldDStar 作成
   └→ 簡易版の any-angle path planning
   
2. FieldDStarProper 作成
   └→ より完全な実装（仮想ノード対応）
   
3. FieldDStarHybrid 作成
   └→ 最終採用版（実用的で高速）
   └→ ✅ 論文で実験対象に
   └→ ✅ TA* のベースになる
```

### TA*の構成

```python
# ta_star.py より
class TAStarPlanner:
    def __init__(self):
        self.field_d = FieldDStarHybrid(...)  # ← FieldD*Hybrid をベースに
        self.dstar = DStarLite3D(...)
    
    def plan_path(self):
        # 適応的に FieldD*Hybrid と D*Lite を選択
```

---

## 論文本文の修正提案

### Chapter 5の記載を明確化

**現在（曖昧）:**
```
比較手法として，Regular A*，RRT*，D*Lite，Field D*を用いた。
```

**推奨（明確）:**
```
比較手法として，Regular A*，RRT*，D*Lite，Field D* Hybrid を用いた。
ここで Field D* Hybrid は 4.6 で提案した手法である。
```

---

## 図表の正確な手法セット確認

### 「6 Planners」図の現在の構成

```
現在の6プランナー図：
  - D*Lite
  - RRT*
  - HPA*
  - SAFETY
  - FieldD*Hybrid
  - TA*
```

**問題点**: 本文に「HPA*」「SAFETY」の記載がない

### 推奨: 5手法版への修正

```
推奨される5プランナー図：
  1. D*Lite        ✓ 本文に「D*Lite」
  2. RRT*          ✓ 本文に「RRT*」
  3. Regular A*    ✓ 本文に「Regular A*」
  4. FieldD*Hybrid ✓ 本文に「Field D*」= これ
  5. TA*           ✓ 提案手法（必須）
```

---

## 【最終判定】

| 質問 | 回答 | 確実度 |
|-----|------|--------|
| Q1: Field D*は存在するか | 実装に3つ、データに1つ | 🟢 確実 |
| Q2: どこに実装か | field_d_star_hybrid.py | 🟢 確実 |
| Q3: 本文の「Field D*」= Hybrid か | YES | 🟢 確実 |
| Q4: どの手法セット | オプションA（5手法） | 🟢 確実 |

---

## 次のステップ

### 推奨アクション

1. **図表の修正**
   - 6プランナー図 → 5プランナー図に修正
   - タイトルを「5 Methods」に変更
   - 手法セット: D*Lite, RRT*, Regular A*, FieldD*Hybrid, TA*

2. **論文本文の確認**
   - Chapter 5 の比較手法の説明を確認
   - 「Field D*」と「FieldD*Hybrid」の関係を明記

3. **スクリプトの更新**
   - 5手法版の図生成スクリプトを作成推奨
   - テンプレートは `generate_high_res_figures.py` を参考に

---

**関連ファイル**:
- 実装: `ros2/ros2_ws/src/path_planner_3d/path_planner_3d/field_d_star_*.py`
- データ: `benchmark_results/dataset3_8planners_results.json`
- スクリプト: `run_benchmark_8planners.py`, `full_benchmark_6_planners.py`
