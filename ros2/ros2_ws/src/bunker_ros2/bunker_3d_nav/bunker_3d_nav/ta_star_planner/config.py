"""
設定管理

マジックナンバーを全て排除し、設定を一元管理
"""
from dataclasses import dataclass
from typing import Tuple, Optional

@dataclass
class PlannerConfig:
    """プランナー設定"""
    
    # マップ設定
    map_bounds: Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    voxel_size: float = 0.2
    
    # 制約
    max_slope_deg: float = 30.0
    max_velocity: float = 1.0
    
    # タイムアウト（Noneなら自動設定）
    timeout: Optional[float] = None
    
    @classmethod
    def small_scale(cls) -> 'PlannerConfig':
        """小規模マップ設定"""
        return cls(
            map_bounds=([-10, -10, 0], [10, 10, 3]),
            voxel_size=0.1,
            timeout=600
        )
    
    @classmethod
    def medium_scale(cls) -> 'PlannerConfig':
        """中規模マップ設定"""
        return cls(
            map_bounds=([-25, -25, 0], [25, 25, 5]),
            voxel_size=0.2,
            timeout=1800
        )
    
    @classmethod
    def large_scale(cls) -> 'PlannerConfig':
        """大規模マップ設定"""
        return cls(
            map_bounds=([-50, -50, 0], [50, 50, 8]),
            voxel_size=0.5,
            timeout=3600
        )

@dataclass
class ExperimentConfig:
    """実験設定"""
    
    # シナリオ設定
    num_scenarios: int = 10
    random_seed: int = 42
    
    # タイムアウト
    scenario_timeout: float = 300  # 5分
    
    # 並列実行
    use_parallel: bool = False
    num_workers: int = 4
    
    # 出力設定
    save_intermediate: bool = True
    output_dir: str = '../results'

@dataclass
class TerrainConfig:
    """地形設定"""
    
    # 地形タイプ
    terrain_type: str = 'flat'
    
    # 地形パラメータ
    max_slope: float = 30.0
    obstacle_density: float = 0.1
    
    # サイズ
    map_size: float = 50.0
    resolution: float = 0.5
    
    # 生成パラメータ
    random_seed: int = 42



