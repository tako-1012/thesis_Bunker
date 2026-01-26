#!/usr/bin/env python3
"""Test WeightedAStar directly without AHA* wrapper."""
import sys
import os
import logging

workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import numpy as np
from path_planner_3d.weighted_astar import WeightedAStar
from path_planner_3d.cost_function import CostFunction
from path_planner_3d.config import PlannerConfig

logging.basicConfig(level=logging.INFO, format='%(name)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Simple terrain
size = 20
terrain = {
    'grid_size': size,
    'resolution': 1.0,
    'origin': [0.0, 0.0, 0.0],
    'heights': np.ones((size, size)) * 1.0,  # Flat at z=1.0
    'obstacles': np.zeros((size, size), dtype=bool),  # No obstacles
}

config = PlannerConfig(
    map_bounds=([0.0, 0.0, 0.0], [float(size), float(size), 3.0]),
    voxel_size=1.0,
    max_slope_deg=45.0,
)

cost_fn_obj = CostFunction(
    weights={'distance': 1.0, 'slope': 0.1, 'obstacle': 10.0, 'stability': 0.1},
    safety_params={'min_obstacle_distance': 1.0, 'max_slope': 45.0, 'min_stability': 0.1}
)

def terrain_cost_fn(from_pos, to_pos, terrain_data):
    return cost_fn_obj.calculate_total_cost(from_pos, to_pos, terrain_data)

planner = WeightedAStar(config=config, epsilon=1.0, terrain_cost_fn=terrain_cost_fn)

# Adjacent cells at same Z
start = [1.0, 1.0, 1.0]
goal = [2.0, 2.0, 1.0]

logger.info(f"Testing: {start} -> {goal}")
result = planner.plan_path(start, goal, terrain_data=terrain, timeout=10.0)

logger.info(f"Result: success={result.success}, nodes={result.nodes_explored}, path_len={len(result.path)}")
if result.success:
    logger.info(f"Path: {result.path}")
else:
    logger.error(f"Failed: {result.error_message}")

sys.exit(0 if result.success else 1)
