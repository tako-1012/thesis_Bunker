# A*（Regular A*）実装状況の完全調査レポート

**作成日**: 2026年1月19日  
**調査テーマ**: Regular A* の実装状況と論文との整合性

---

## 【質問1】A*（Regular A*）の実装ファイルは存在するか？

### **Answer: YES - 複数存在する**

#### 実装ファイル一覧

| ファイル名 | クラス名 | 形式 | 説明 |
|-----------|--------|------|------|
| `astar_3d.py` | `AStar3D` | ✅ 独立実行可能 | 基本 A* の 3D 実装 |
| `astar_planner_3d.py` | `AStarPlanner3D` | ❌ 相対インポート | コスト計算器連携版 |
| `astar_planner.py` | `AStarPlanner3D` | ❌ 相対インポート | リファクタリング版（BasePlanner3D継承） |

#### 実装の特徴

- **astar_3d.py**
  - 独立して実行可能
  - `plan_path()` メソッドを持つ
  - `set_terrain_data()` がない
  - 26-neighbor 探索対応

- **astar_planner_3d.py** / **astar_planner.py**
  - BasePlanner3D を継承
  - 相対インポートのため単独実行不可
  - ベンチマークスクリプトでは使用されていない

---

## 【質問2】Dataset3 で実験を実行できるか？

### **Answer: NO - ベンチマークスクリプトに統合されていない**

#### ベンチマークスクリプトの確認

**`run_benchmark_8planners.py` (Line 220):**
```python
planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY', 'FieldD*Hybrid', 'MPAA*']
```

**`full_benchmark_6_planners.py` (Line 317):**
```python
planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']
```

#### 実装済みのプランナー

8プランナー版：
- ✓ TA*
- ✓ Theta*
- ✓ RRT*
- ✓ D*Lite
- ✓ HPA*
- ✓ SAFETY
- ✓ FieldD*Hybrid
- ✓ MPAA*

❌ **Regular A* はない**

#### 実験実施の必要条件

Regular A* を Dataset3 で実験するには：
1. ベンチマークスクリプトに Regular A* の処理を追加
2. `plan_path()`, `set_terrain_data()` インターフェースの確保
3. 90シナリオ × 複数トライアル での実行
4. 結果データの生成

**所要時間**: 数時間～1日

---

## 【質問3】実装が必要か？本文から削除すべきか？

### **Answer: 本文から削除を推奨**

#### 理由

1. **データが存在しない**
   - `dataset3_8planners_results.json` に Regular A* のエントリーがない
   - 論文の根拠がない

2. **実装が古い（プロトタイプ）**
   - 既存の A* 実装は「過去のプロトタイプ」と見られる
   - 実際に使用されているのは地形考慮版（TA* など）

3. **本文と実験のズレ**
   - 論文では「Regular A* を比較した」と記載
   - 実際には比較していない
   - 学術的な信頼性を損なう

4. **効率性**
   - 本文修正: 5分
   - Regular A* 実装: 30分～1時間
   - Dataset3 実験: 数時間～1日

---

## 本文の比較手法との対応表

### 現在の本文

**Chapter 5:**
```
比較手法として，Regular A*，RRT*，D*Lite，Field D*を用いた．
```

### 実装・実験対象

| 手法 | 実装 | Dataset3実験 | データ | 備考 |
|------|------|----------|--------|------|
| Regular A* | ✅ あり | ❌ なし | ❌ なし | 過去のプロトタイプ |
| RRT* | ✅ あり | ✅ あり | ✅ あり | 正常 |
| D*Lite | ✅ あり | ✅ あり | ✅ あり | 正常 |
| Field D* | ✅ あり | ✅ あり | ✅ あり | FieldD*Hybrid として実装 |
| TA* | ✅ あり | ✅ あり | ✅ あり | 提案手法（別扱い） |

---

## 推奨される修正案

### 修正1: 本文の比較手法の説明を更新

**変更前:**
```
比較手法として，Regular A*，RRT*，D*Lite，Field D*を用いた．
```

**変更後（案1 - 簡潔版）:**
```
比較手法として，RRT*，D*Lite，Field D* Hybrid を用いた．
TA*は本研究で提案する手法である．
```

**変更後（案2 - 詳細版）:**
```
比較手法として，次の3つを選択した：
- D*Lite: グリッドベース動的計画法の代表
- RRT*: サンプリングベース確率的計画法の代表
- Field D* Hybrid: 任意角経路計画法の代表

TA*は本研究で提案する地形考慮型適応的経路計画手法である．
```

### 修正2: 図表の修正

**変更内容:**
- 6プランナー図 → 4プランナー図に修正
- タイトル: "Planner Performance Comparison (4 Methods)"
- 手法セット:
  1. D*Lite
  2. RRT*
  3. FieldD*Hybrid
  4. TA* (提案)

**既存ファイル:**
- ✅ `benchmark_results/dataset3_8planners_results.json` ← このまま使用可能（4手法を抽出）
- ✅ `generate_high_res_figures.py` ← このまま使用可能（4手法版へ修正）

---

## 実装が必要な場合の手順（参考）

もし Regular A* を論文に含めることが必須の場合：

### Step 1: ベンチマークスクリプト修正
```python
# run_benchmark_8planners.py に追加
elif planner_name == 'A*':
    from astar_3d import AStar3D
    planner = AStar3D(voxel_size=1.0, max_iterations=100000)
    # ただし set_terrain_data() がないため調整が必要
```

### Step 2: Dataset3 実験実行
```bash
python3 run_benchmark_8planners.py
# または新たに run_benchmark_with_astar.py を作成
```

### Step 3: 結果確認
```bash
cat benchmark_results/dataset3_*planners_summary.json | grep "A\*"
```

**所要時間:** 2-3時間

---

## 最終判定

| 質問 | 回答 | 根拠 |
|------|------|------|
| Q1: A*実装は存在するか？ | ✅ YES | astar_3d.py, astar_planner_3d.py など複数存在 |
| Q2: Dataset3で実験可能？ | ❌ NO | ベンチマークスクリプトに未統合、データなし |
| Q3: 実装が必要か？ | ❌ 不要 | 本文修正で解決可能（効率的） |

---

## 推奨アクション

### 優先度 1（推奨・最小変更）

✅ **本文から「Regular A*」を削除**

影響：
- 修正時間: 5分
- データ整合性: 完全に一致
- 論文の信頼性: 向上

### 優先度 2（スケジュール次第）

もし「比較基準として Regular A* が必要」という方針の場合：

⚠️ **Regular A* を Dataset3 で実験**

影響：
- 実装時間: 1-2時間
- 実験時間: 3-5時間
- データ整合性: 完全に一致
- 効果: 高い

### 優先度 3（非推奨）

❌ **書いたまま放置**

リスク：
- データと本文の不整合が指摘される
- 学術的な信頼性が損なわれる
- レビューで修正要求される可能性

---

## 関連ファイル

### A* 実装ファイル
- `ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py`
- `ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_planner_3d.py`
- `ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_planner.py`

### ベンチマークスクリプト
- `run_benchmark_8planners.py`
- `full_benchmark_6_planners.py`

### 実験データ
- `benchmark_results/dataset3_8planners_results.json`
- `benchmark_results/dataset3_8planners_summary.json`

### 図表生成
- `scripts/generate_paper_figures.py`
- `scripts/generate_high_res_figures.py`
