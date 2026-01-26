"""
TA*: Terrain-Aware Adaptive Planner
地形考慮型適応的経路計画システム

Field D* Hybridをベースに、適応的選択機能を統合
"""
import numpy as np
from typing import Tuple, Dict, Optional
import time

try:
    from .field_d_star_hybrid import FieldDStarHybrid
    from .dstar_lite_3d import DStarLite3D
    from .planning_result import PlanningResult
except Exception:
    from field_d_star_hybrid import FieldDStarHybrid
    from dstar_lite_3d import DStarLite3D
    from planning_result import PlanningResult


class TAStarPlanner:
    """
    TA*: Terrain-Aware Adaptive Planner
    """

    def __init__(self, voxel_size=1.0, grid_size=(200, 200, 20)):
        self.voxel_size = voxel_size
        self.grid_size = grid_size

        # ベースプランナー（地形コスト有効）
        self.field_d = FieldDStarHybrid(voxel_size, grid_size, use_terrain_cost=True)
        self.dstar = DStarLite3D(voxel_size, grid_size)

        # 統計
        self.last_stats = {
            'selected_planner': None,
            'computation_time': 0.0,
            'path_length': 0.0
        }

    def set_terrain_data(self, voxel_grid, terrain_data=None, min_bound=None):
        """地形データを設定"""
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
        self.min_bound = min_bound

        # 各プランナーに設定
        try:
            self.field_d.set_terrain_data(voxel_grid, terrain_data, min_bound)
        except Exception:
            pass
        try:
            self.dstar.set_terrain_data(voxel_grid, terrain_data, min_bound)
        except Exception:
            pass

    def extract_features(self, voxel_grid=None) -> Dict:
        """
        環境特性を抽出
        """
        if voxel_grid is None:
            voxel_grid = getattr(self, 'voxel_grid', None)

        if voxel_grid is None:
            return {
                'map_size': max(self.grid_size),
                'obstacle_density': 0.0,
                'terrain_roughness': 0.0
            }

        # マップサイズ
        map_size = max(voxel_grid.shape)

        # 障害物密度
        obstacle_density = float(np.mean(voxel_grid > 0.5))

        # 地形粗さ（簡易版）
        terrain_roughness = 0.0
        if getattr(self, 'terrain_data', None) is not None:
            try:
                terrain_roughness = float(np.std(self.terrain_data))
            except Exception:
                terrain_roughness = 0.0

        return {
            'map_size': map_size,
            'obstacle_density': obstacle_density,
            'terrain_roughness': terrain_roughness
        }

    def select_planner(self, features: Dict, requirements: Dict) -> str:
        """
        環境特性と要件に基づいてプランナーを選択
        """
        if requirements is None:
            requirements = {}

        # 速度最優先
        if requirements.get('speed_critical', False):
            return 'dstar'

        # 地形考慮が重要かつ粗い地形
        if (requirements.get('terrain_aware', False) and 
            features.get('terrain_roughness', 0.0) > 0.5):
            return 'field_d'

        # 経路品質重視
        if requirements.get('quality_critical', True):
            return 'field_d'

        # デフォルト
        if features.get('map_size', max(self.grid_size)) < 200:
            return 'field_d'
        else:
            return 'field_d'

    def plan_path(self, start: Tuple[float, float, float], 
                  goal: Tuple[float, float, float],
                  requirements: Optional[Dict] = None,
                  **kwargs) -> PlanningResult:
        """
        適応的経路計画を実行
        """
        t0 = time.time()

        # デフォルト要件
        if requirements is None:
            requirements = {
                'speed_critical': False,
                'quality_critical': True,
                'terrain_aware': False
            }

        # 環境特性抽出
        features = self.extract_features()

        # プランナー選択
        selected = self.select_planner(features, requirements)

        # 実行
        result = None
        if selected == 'dstar':
            try:
                result = self.dstar.plan_path(start, goal, **kwargs)
                result.algorithm_name = 'TA* (D*Lite)'
            except Exception:
                result = PlanningResult(success=False, path=[], path_length=0.0, computation_time=0.0)
        else:  # 'field_d'
            try:
                result = self.field_d.plan_path(start, goal, **kwargs)
                result.algorithm_name = 'TA* (Field D*)'
            except Exception:
                result = PlanningResult(success=False, path=[], path_length=0.0, computation_time=0.0)

        # 統計更新
        self.last_stats = {
            'selected_planner': selected,
            'computation_time': time.time() - t0,
            'path_length': getattr(result, 'path_length', 0.0) if result and getattr(result, 'success', False) else 0.0,
            'features': features,
            'requirements': requirements
        }

        return result


def create_ta_star_planner(voxel_size=1.0, grid_size=(200, 200, 20)):
    """TA*プランナーを作成"""
    return TAStarPlanner(voxel_size, grid_size)
