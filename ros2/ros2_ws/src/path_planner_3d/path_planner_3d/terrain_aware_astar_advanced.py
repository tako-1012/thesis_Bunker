"""
Compatibility wrapper for terrain_aware_astar_advanced.
Redirects to TerrainAwareAStar (terrain_aware_astar) to preserve legacy imports
while using the thesis-correct implementation.
"""
from enum import Enum

try:
    from .terrain_aware_astar import TerrainAwareAStar
except Exception:  # pragma: no cover - fallback for direct import
    from terrain_aware_astar import TerrainAwareAStar


class TerrainType(str, Enum):
    FLAT = "FLAT"
    GENTLE_SLOPE = "GENTLE_SLOPE"
    STEEP_SLOPE = "STEEP_SLOPE"
    OBSTACLE_DENSE = "OBSTACLE_DENSE"
    ROUGH = "ROUGH"
    UNKNOWN = "UNKNOWN"


# Placeholder strategy map for compatibility; real logic lives in TerrainAwareAStar
TERRAIN_STRATEGIES = {}

__all__ = ["TerrainAwareAStar", "TerrainType", "TERRAIN_STRATEGIES"]
