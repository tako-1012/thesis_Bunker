# 3D Path Planning for UGV in Unstructured Terrain

不整地環境における無人地上車両（UGV）のための3D経路計画研究

## 概要

本研究では、Terrain-Aware A*（TA-A*）という新しい経路計画アルゴリズムを提案し、不整地環境での性能を実証します。

## 主要な成果

- **5つのアルゴリズム実装**: Dijkstra, A*, Weighted A*, RRT*, TA-A* (提案手法)
- **5つの代表的地形での評価**: 平坦地から極端地形まで
- **スケーラビリティ検証**: 20m×20mから100m×100mまで
- **論文用図表生成**: 高品質なグラフとLaTeXテーブル

## ディレクトリ構造

```
thesis_work/
├── ros2/ros2_ws/src/bunker_ros2/
│   ├── path_planner_3d/           # アルゴリズム実装
│   ├── experiments/               # 実験管理
│   ├── analysis/                  # 分析・可視化
│   ├── terrain/                   # 地形管理
│   ├── utils/                     # ユーティリティ
│   └── tests/                     # テストコード
└── results/                       # 実験結果
    ├── figures/                   # 論文用図表
    └── tables/                    # LaTeXテーブル
```

## インストール

```bash
# ROS2環境のセットアップ
cd ~/thesis_work/ros2/ros2_ws
colcon build

# Pythonパッケージ
pip install numpy matplotlib scipy
```

## 使用方法

### 簡単な経路計画

```python
from path_planner_3d.astar_planner import AStarPlanner3D
from path_planner_3d.config import PlannerConfig

# 設定
config = PlannerConfig.medium_scale()
planner = AStarPlanner3D(config)

# 経路計画
start = [0, 0, 0.2]
goal = [20, 20, 0.2]
result = planner.plan_path(start, goal)

if result.success:
    print(f"経路長: {result.path_length:.2f}m")
    print(f"計算時間: {result.computation_time:.2f}s")
```

### 実験の実行

```python
from experiments.terrain_experiment import TerrainExperiment

# 実験実行
experiment = TerrainExperiment(
    terrain_type="flat_agricultural_field",
    num_scenarios=10,
    output_dir="../results"
)
experiment.run_experiment()
```

### 結果の可視化

```python
from analysis.visualizer import Visualizer
from analysis.latex_generator import LaTeXGenerator
from utils.file_manager import FileManager

# データ読み込み
phase2_data = FileManager.load_json('../results/efficient_terrain_results.json')
phase4_data = FileManager.load_json('../results/phase4_scalability_results.json')

# 可視化
viz = Visualizer()
viz.generate_all_figures(phase2_data, [], phase4_data)

# LaTeX生成
latex = LaTeXGenerator()
latex.generate_all_tables(phase2_data, phase4_data)
```

### テスト

```bash
# 全テスト実行
python -m unittest discover tests/

# 特定のテスト
python -m unittest tests.test_planners
```

## 主要な実験結果

### Phase 2: 代表的地形実験

- Flat Agricultural Field: 全アルゴリズム 80-100%
- Gentle Hills: A*/Weighted A* 100%, TA-A* 60%
- その他の地形でも包括的評価完了

### Phase 4: スケーラビリティ検証

- Small (20m): A*/Weighted A* 100%
- Medium (50m): 全アルゴリズム 88-100%
- Large (100m): 全アルゴリズム 100%

## 論文

研究成果は学会発表レベルの論文としてまとめられています。

## ライセンス

MIT License

## 著者

[あなたの名前]

## 謝辞

本研究は[指導教員名]教授の指導の下で行われました。