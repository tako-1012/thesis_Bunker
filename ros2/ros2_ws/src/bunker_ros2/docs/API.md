# API Documentation

## Path Planners

### BasePlanner3D

基底クラス。全てのプランナーが継承します。

```python
class BasePlanner3D(ABC):
    def __init__(self, config: PlannerConfig)
    
    @abstractmethod
    def plan_path(self, start, goal, terrain_data, timeout) -> PlanningResult
```

### AStarPlanner3D

A*アルゴリズム実装。

```python
planner = AStarPlanner3D(config)
result = planner.plan_path(start=[0,0,0], goal=[10,10,0])
```

### TerrainAwareAStarPlanner3D

提案手法: Terrain-Aware A*

```python
planner = TerrainAwareAStarPlanner3D(config)
result = planner.plan_path(start, goal, terrain_data)
```

## Configuration

### PlannerConfig

```python
config = PlannerConfig(
    map_bounds=([-25,-25,0], [25,25,5]),
    voxel_size=0.2,
    max_slope_deg=30.0
)

# または事前定義
config = PlannerConfig.small_scale()
config = PlannerConfig.medium_scale()
config = PlannerConfig.large_scale()
```

### ExperimentConfig

```python
config = ExperimentConfig(
    num_scenarios=10,
    random_seed=42,
    scenario_timeout=300
)
```

## Experiments

### TerrainExperiment

```python
experiment = TerrainExperiment(
    terrain_type="flat_agricultural_field",
    num_scenarios=10,
    output_dir="../results"
)
experiment.run_experiment()
```

## Analysis

### Visualizer

```python
viz = Visualizer(output_dir='../results/figures')
viz.plot_terrain_success_rates(data)
viz.plot_scalability(data)
viz.generate_all_figures(phase2_data, phase3_data, phase4_data)
```

### LaTeXGenerator

```python
latex = LaTeXGenerator(output_dir='../results/tables')
latex.generate_terrain_results_table(data)
latex.generate_all_tables(phase2_data, phase4_data)
```

## Utilities

### Logger

```python
from utils.logger import setup_logger

logger = setup_logger('my_module', level=logging.INFO)
logger.info("Message")
```

### Timer

```python
from utils.timer import Timer

with Timer("My Operation"):
    # 処理
    pass
```

### FileManager

```python
from utils.file_manager import FileManager

FileManager.save_json(data, 'result.json')
data = FileManager.load_json('result.json')
```