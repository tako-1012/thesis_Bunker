"""
Compatibility wrapper for terrain_aware_astar_advanced.
Use TerrainAwareAStar from path_planner_3d so legacy imports continue to work.
"""
from enum import Enum

try:
    from path_planner_3d.terrain_aware_astar import TerrainAwareAStar
except Exception:  # pragma: no cover - fallback when PYTHONPATH differs
    from ..path_planner_3d.terrain_aware_astar import TerrainAwareAStar  # type: ignore


class TerrainType(str, Enum):
    FLAT = "FLAT"
    GENTLE_SLOPE = "GENTLE_SLOPE"
    STEEP_SLOPE = "STEEP_SLOPE"
    OBSTACLE_DENSE = "OBSTACLE_DENSE"
    ROUGH = "ROUGH"
    UNKNOWN = "UNKNOWN"


TERRAIN_STRATEGIES = {}

__all__ = ["TerrainAwareAStar", "TerrainType", "TERRAIN_STRATEGIES"]
