"""
ARA* (Anytime Repairing A*) 3D経路計画
TA*やWeighted A*の地形ヒューリスティックを活用し、εスケジューリングで高速→最適化を両立
"""
import numpy as np
import time
import logging
from typing import Tuple, List, Optional

try:
    from .planning_result import PlanningResult
except ImportError:
    from planning_result import PlanningResult

from weighted_astar_planner_3d import WeightedAStarPlanner3D

logger = logging.getLogger(__name__)

class ARAStarPlanner3D:
    """ARA* (Anytime Repairing A*) 3D経路計画"""
    def __init__(self, grid_size=(100, 100, 30), voxel_size=0.1, max_slope=30.0,
                 epsilon_schedule=[3.0, 2.0, 1.5, 1.2, 1.0], map_bounds=None, timeout=30.0):
        self.grid_size = grid_size
        self.voxel_size = voxel_size
        self.max_slope = max_slope
        self.epsilon_schedule = epsilon_schedule
        self.map_bounds = map_bounds
        self.timeout = timeout

    def plan_path(self, start, goal, terrain_data=None, timeout=None):
        """
        εを段階的に減少させて再探索し、任意時点で最良解を返す
        """
        start_time = time.time()
        best_result = None
        best_cost = float('inf')
        timeout = timeout or self.timeout
        for eps in self.epsilon_schedule:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                logger.warning(f"ARA*: Timeout after {elapsed:.2f}s, returning best found path.")
                break
            logger.info(f"ARA*: Searching with epsilon={eps}")
            planner = WeightedAStarPlanner3D(
                grid_size=self.grid_size,
                voxel_size=self.voxel_size,
                max_slope=self.max_slope,
                epsilon=eps,
                map_bounds=self.map_bounds
            )
            result = planner.plan_path(start, goal, terrain_data, timeout=timeout-elapsed)
            if result and getattr(result, 'success', True) and result.path:
                cost = getattr(result, 'path_length', len(result.path))
                if cost < best_cost:
                    best_result = result
                    best_cost = cost
                if eps == 1.0:
                    logger.info("ARA*: Found optimal path (epsilon=1.0)")
                    break
        if best_result:
            logger.info(f"ARA*: Returning best path (cost={best_cost:.2f})")
            return best_result
        logger.warning("ARA*: No path found in any epsilon schedule")
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=0,
            error_message="ARA* failed",
            algorithm_name="ARA*"
        )
