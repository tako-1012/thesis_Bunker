# 実験環境・パラメータ設定

**作成日**: 2026年1月29日  
**目的**: 実験の完全な再現性を保証するための完全な記録

---

## 1. 計算環境

| 項目 | 仕様 | 確認方法 |
|------|------|---------|
| OS | Ubuntu 20.04 LTS / 22.04 LTS | `lsb_release -a` |
| カーネル | Linux 5.15以上 | `uname -r` |
| ROS | ROS 2 Humble (humble) | `ros2 --version` |
| Python | 3.10以上 | `python3 --version` |
| CMake | 3.16以上 | `cmake --version` |
| Unity | 2021.3 LTS 以上 | Unity Hub |

### CPUスペック（重要：パフォーマンスに直結）

```bash
# CPU情報取得
lscpu | grep "Model name"
lscpu | grep "CPU max MHz"
lscpu | grep "Cores\|Threads"

# メモリ情報取得
free -h
```

**記入欄**:
- CPU モデル: ________________________
- 最大周波数: ________________________
- コア数: ________________________
- メモリ: ________________________

### 必要な依存パッケージ

```bash
# Python依存パッケージ
pip install numpy scipy pandas scikit-learn matplotlib

# ROS2依存パッケージ
sudo apt install ros-humble-geometry2 ros-humble-nav2-core

# ベンチマークツール
pip install cProfile pytest
```

---

## 2. アルゴリズムパラメータ

### 2.1 TA* (Terrain-Aware Adaptive A*)

**実装ファイル**: `terrain_aware_astar.py`

| パラメータ名 | 値 | データ型 | 範囲 | 説明 |
|-------------|-----|--------|------|------|
| `terrain_weight` | 0.3 | float | [0.0, 1.0] | 地形コスト重み（0=地形無視、1.0=完全反映） |
| `heuristic_multiplier` | 1.5 | float | [1.0, 2.0] | ヒューリスティック倍率（許容性を保証） |
| `prune_distance_factor` | 2.0 | float | [1.5, 3.0] | プルーニング距離係数（迂回経路許容度） |
| `cost_limit_factor` | 3.0 | float | [2.0, 4.0] | コスト上限係数（過高コスト排除） |
| `voxel_size` | 0.5 | float | [0.1, 1.0] | ボクセルサイズ (m) |
| `grid_size` | (200, 200, 20) | tuple | - | グリッドサイズ (x, y, z) |
| `max_iterations` | 500000 | int | [10000, 1000000] | 最大探索ノード数 |
| `timeout` | 300.0 | float | [60.0, 600.0] | タイムアウト (秒) |

**ソースコード抽出**:
```bash
grep -n "terrain_weight\|heuristic_multiplier\|prune_distance" \
  ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py | head -20
```

### 2.2 RRT* (Rapid-exploring Random Tree*)

**実装ファイル**: `rrt_star.py`

| パラメータ名 | 値 | データ型 | 説明 |
|-------------|-----|--------|------|
| `max_iterations` | 10000 | int | 最大反復回数 |
| `step_size` | 1.0 | float | ステップサイズ (m) |
| `goal_sample_rate` | 0.1 | float | ゴールサンプリング率（10%確率でゴール向け） |
| `search_radius` | 5.0 | float | 再配線探索半径 (m) |
| `timeout` | 300.0 | float | タイムアウト (秒) |

### 2.3 SAFETY_FIRST

**実装ファイル**: `safety_first.py`

| パラメータ名 | 値 | データ型 | 説明 |
|-------------|-----|--------|------|
| `safety_threshold` | 0.8 | float | 安全性閾値（0.8=ロボット半径の0.8m内） |
| `max_slope` | 30.0 | float | 最大登坂角 (度) |
| `min_clearance` | 0.3 | float | 最小クリアランス (m) |
| `timeout` | 300.0 | float | タイムアウト (秒) |

### 2.4 HPA* (Hierarchical Pathfinding A*)

**実装ファイル**: `hpa_star.py`

| パラメータ名 | 値 | データ型 | 説明 |
|-------------|-----|--------|------|
| `cluster_size` | 10 | int | クラスタサイズ（グリッド単位） |
| `abstraction_level` | 2 | int | 抽象化レベル数 |
| `inter_cluster_range` | 2 | int | クラスタ間接続範囲 |
| `timeout` | 300.0 | float | タイムアウト (秒) |

### 2.5 D* Lite

**実装ファイル**: `dstar_lite.py`

| パラメータ名 | 値 | データ型 | 説明 |
|-------------|-----|--------|------|
| `heuristic_weight` | 1.0 | float | ヒューリスティック重み |
| `replanning_threshold` | 0.5 | float | 再計画トリガー閾値 |
| `timeout` | 300.0 | float | タイムアウト (秒) |

### 2.6 Dijkstra

**実装ファイル**: `dijkstra.py`

| パラメータ名 | 値 | データ型 | 説明 |
|-------------|-----|--------|------|
| `timeout` | 300.0 | float | タイムアウト (秒) |
| `use_distance_heuristic` | False | bool | 距離ヒューリスティック使用（Dijkstraなので通常False） |

---

## 3. 地形複雑度の定義

### 3.1 複雑度計算式

```
terrain_complexity = 
  w_slope × slope_complexity + 
  w_obstacle × obstacle_complexity + 
  w_roughness × roughness_complexity

ここで、
  w_slope = 0.4      (傾斜重み)
  w_obstacle = 0.4   (障害物重み)
  w_roughness = 0.2  (粗さ重み)
```

### 3.2 各項目の詳細

**傾斜複雑度（slope_complexity）**:
```
if max_slope < 15°:
    slope_complexity = 0.1
elif max_slope < 30°:
    slope_complexity = 0.4
elif max_slope < 45°:
    slope_complexity = 0.7
else:
    slope_complexity = 1.0
```

**障害物複雑度（obstacle_complexity）**:
```
obstacle_ratio = occupied_cells / total_cells

if obstacle_ratio < 0.2:
    obstacle_complexity = 0.1
elif obstacle_ratio < 0.4:
    obstacle_complexity = 0.4
elif obstacle_ratio < 0.6:
    obstacle_complexity = 0.7
else:
    obstacle_complexity = 1.0
```

**粗さ複雑度（roughness_complexity）**:
```
roughness = std_dev(height_map) / mean(height_map)

if roughness < 0.1:
    roughness_complexity = 0.1
elif roughness < 0.3:
    roughness_complexity = 0.4
elif roughness < 0.5:
    roughness_complexity = 0.7
else:
    roughness_complexity = 1.0
```

### 3.3 複雑度の分類

| 分類 | 複雑度範囲 | 説明 | シナリオ数 |
|------|-----------|------|----------|
| 単純 (Simple) | < 0.15 | 平坦、障害物少ない | 32 |
| 中程度 (Medium) | 0.15 - 0.55 | 緩い勾配、中程度の障害物 | 32 |
| 複雑 (Complex) | ≥ 0.55 | 急勾配、障害物密集 | 32 |

---

## 4. シナリオ設定

### 4.1 環境サイズ

| サイズ名 | 実世界サイズ | グリッド解像度 | グリッドサイズ | シナリオ数 | 用途 |
|---------|-----------|-----------|-----------|----------|------|
| Small | 20m × 20m | 0.5m/grid | 40 × 40 | 30 | 屋内環境 |
| Medium | 50m × 50m | 0.5m/grid | 100 × 100 | 48 | 一般的な屋外 |
| Large | 100m × 100m | 0.5m/grid | 200 × 200 | 18 | 大規模野外 |

### 4.2 地形複雑度分布

| 複雑度 | Small | Medium | Large | 合計 |
|--------|-------|--------|-------|------|
| 単純 | 10 | 16 | 6 | 32 |
| 中程度 | 10 | 16 | 6 | 32 |
| 複雑 | 10 | 16 | 6 | 32 |
| 合計 | 30 | 48 | 18 | 96 |

### 4.3 シナリオ生成パラメータ

```python
# ベースとなる乱数シード
SEED_DATASET1 = 42
SEED_DATASET2 = 123  
SEED_DATASET3 = 456

# シナリオごとの固定シード
seed_scenario = base_seed + scenario_index

# 生成手順
1. seed_scenarioで乱数生成器を初期化
2. 障害物ランダム配置（複雑度に基づいて密度決定）
3. 地形高さマップ生成（勾配範囲を複雑度で制御）
4. スタート/ゴール地点をランダム選定
5. A*で接続性確認（経路が存在することを保証）
```

---

## 5. タイムアウト設定

### 5.1 タイムアウト値

**全手法共通**: `timeout = 300.0秒`

### 5.2 タイムアウト判定

```python
if time.time() - start_time > timeout:
    return {
        'success': False,
        'nodes_explored': nodes_count,
        'computation_time': timeout,
        'reason': 'timeout'
    }
```

---

## 6. 成功判定基準

### 6.1 成功条件（全て満たす必要がある）

```
✅ success = True ←以下を全て満たす:

1. タイムアウト内に終了
   time_elapsed ≤ timeout (300秒)

2. 経路を発見
   path_length > 0 AND path_points ≥ 2

3. 障害物回避
   全経路点がvoxel_grid[x,y,z] < threshold

4. 長さ妥当性
   path_length < euclidean_distance × 10

5. ロボット物理制約
   max_slope ≤ robot.max_slope (30°以下)
```

### 6.2 失敗原因

```
❌ success = False ←以下のいずれかの場合:

1. タイムアウト
   time_elapsed > 300秒

2. 経路未発見
   nodes_explored ≥ max_iterations (500,000)

3. 無効な経路
   path_length = 0 OR path_pointsが不正

4. 物理制約違反
   max_slope > 30°
```

---

## 7. 実行環境チェックリスト

### セットアップ時確認事項

- [ ] Ubuntu 20.04 LTS以上がインストールされている
- [ ] ROS 2 Humbleがインストールされている
- [ ] Python 3.10以上がインストールされている
- [ ] 必要なPythonパッケージがインストール済み
  ```bash
  pip list | grep numpy scipy pandas
  ```
- [ ] ワークスペースがビルド済み
  ```bash
  cd ros2/ros2_ws
  colcon build
  ```
- [ ] 環境変数が設定済み
  ```bash
  source install/setup.bash
  ```

### 実験前確認事項

- [ ] ベンチマークデータが整備されている
- [ ] タイムアウト値が全手法で統一されている
- [ ] 乱数シードが記録されている
- [ ] 結果出力ディレクトリが存在する
- [ ] 計算環境情報が記録されている

---

## 8. 再現性保証

### 8.1 完全再現のための手順

```bash
# 1. リポジトリのクローン
git clone <repo_url>
cd thesis_work

# 2. 環境変数設定
export SEED_DATASET3=456
export TIMEOUT=300
export MAX_ITERATIONS=500000

# 3. ベンチマーク実行
cd ros2/ros2_ws
source install/setup.bash
ros2 run path_planner_3d benchmark_full.py

# 4. 統計分析
cd ../../
python3 statistical_analysis.py

# 5. レポート生成
# → statistical_report.md が生成される
```

### 8.2 バージョン情報

**ソフトウェアバージョン**:
```bash
# 記録方法
ros2 --version > version_info.txt
python3 --version >> version_info.txt
pip list >> version_info.txt
```

---

## 9. パラメータ感度分析

### 9.1 パラメータ変更履歴

| 日付 | パラメータ | 変更前 | 変更後 | 理由 |
|------|-----------|--------|--------|------|
| 2026-01-29 | terrain_weight | - | 0.3 | 基準値設定 |
| 2026-01-29 | heuristic_multiplier | - | 1.5 | 最適化 |

### 9.2 感度分析の実施予定

```python
# パラメータ組み合わせテスト
parameter_ranges = {
    'terrain_weight': [0.1, 0.3, 0.5, 0.7, 1.0],
    'heuristic_multiplier': [1.0, 1.2, 1.5, 1.8, 2.0],
    'prune_distance_factor': [1.5, 2.0, 2.5, 3.0]
}

# テスト数: 5 × 5 × 4 = 100通り
# 各テスト: 96シナリオ × 1回 = 96実行
# 総実行数: 9,600実行
```

---

## 10. 参考資料

### 実装ファイル
- `terrain_aware_astar.py` - TA*実装
- `astar_3d.py` - A*実装
- `statistical_analysis.py` - 統計分析

### 論文・文献
- Hart et al. (1968) - A*の原論文
- Koenig & Likhachev (2002) - D* Lite
- Dolgov et al. (2010) - Hybrid A*

### 関連ドキュメント
- [PRACTICAL_FEASIBILITY_ANALYSIS.md](PRACTICAL_FEASIBILITY_ANALYSIS.md)
- [TA_STAR_REPORT.md](TA_STAR_REPORT.md)
- [CHAT_SUMMARY_2026_01_29.md](CHAT_SUMMARY_2026_01_29.md)

---

**作成者**: AI Assistant  
**最終更新**: 2026年1月29日

