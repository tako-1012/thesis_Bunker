#!/usr/bin/env python3
"""Single-case debug script for AHA*."""
import sys
import os
import logging
import time
import json
from typing import Dict, Optional

# Add workspace path_planner_3d package to sys.path
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if workspace_root not in sys.path:
    sys.path.insert(0, workspace_root)

import numpy as np
from path_planner_3d.anytime_hierarchical_astar import AnytimeHierarchicalAStar
from path_planner_3d.cost_function import CostFunction
from path_planner_3d.config import PlannerConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def generate_terrain(size: int) -> Dict:
    """Generate simple terrain for testing."""
    grid_size = size
    heights = np.random.rand(grid_size, grid_size) * 2.0
    obstacles = np.random.rand(grid_size, grid_size) < 0.1
    
    return {
        'grid_size': grid_size,
        'resolution': 1.0,
        'origin': [0.0, 0.0, 0.0],
        'heights': heights,
        'obstacles': obstacles,
    }


def run_single_debug():
    """Run single AHA* test case with debug logging."""
    logger.info("=" * 60)
    logger.info("AHA* SINGLE-CASE DEBUG")
    logger.info("=" * 60)
    
    # Generate small terrain
    size = 20
    terrain = generate_terrain(size)
    logger.info(f"Generated terrain: {size}x{size}, resolution={terrain['resolution']}")
    
    # Create planner config
    config = PlannerConfig(
        map_bounds=([0.0, 0.0, 0.0], [float(size), float(size), 3.0]),
        voxel_size=1.0,
        max_slope_deg=45.0,
        timeout=30.0,
    )
    
    cost_fn_obj = CostFunction(
        weights={
            'distance': 1.0,
            'slope': 2.0,
            'obstacle': 10.0,
            'stability': 1.0,
        },
        safety_params={
            'min_obstacle_distance': 1.0,
            'max_slope': 45.0,
            'min_stability': 0.3,
        }
    )
    
    def terrain_cost_fn(from_pos, to_pos, terrain_data):
        return cost_fn_obj.calculate_total_cost(from_pos, to_pos, terrain_data)
    
    # Create AHA* planner with debug-friendly parameters
    planner = AnytimeHierarchicalAStar(
        config=config,
        coarse_factor=2,  # Reduced for debugging
        initial_epsilon=1.5,  # Lower epsilon
        epsilon_decay=0.9,
        terrain_cost_fn=terrain_cost_fn,
    )
    
    # Define simple start/goal
    start = [1.0, 1.0, terrain['heights'][1, 1]]
    goal = [float(size - 2), float(size - 2), terrain['heights'][size - 2, size - 2]]
    
    logger.info(f"Start: {start}")
    logger.info(f"Goal: {goal}")
    logger.info(f"Distance: {np.linalg.norm(np.array(goal) - np.array(start)):.2f}")
    
    # Run planner with short timeout for debugging
    timeout = 5.0
    logger.info(f"Running AHA* with timeout={timeout}s...")
    logger.info("-" * 60)
    
    start_time = time.time()
    result = planner.plan_path(start, goal, terrain_data=terrain, timeout=timeout)
    elapsed = time.time() - start_time
    
    logger.info("-" * 60)
    logger.info("RESULT:")
    logger.info(f"  success: {result.success}")
    logger.info(f"  computation_time: {result.computation_time:.3f}s")
    logger.info(f"  path_length: {result.path_length:.2f}")
    logger.info(f"  nodes_explored: {result.nodes_explored}")
    logger.info(f"  path points: {len(result.path)}")
    if result.error_message:
        logger.error(f"  error: {result.error_message}")
    logger.info("=" * 60)
    
    return result


if __name__ == '__main__':
    result = run_single_debug()
    sys.exit(0 if result.success else 1)
