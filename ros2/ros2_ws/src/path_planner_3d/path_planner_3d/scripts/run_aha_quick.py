#!/usr/bin/env python3
"""Quick runner to execute AnytimeHierarchicalAStar by loading files directly.

This avoids package-relative import issues when running as a standalone script.
"""
import importlib
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(__file__))

def main():
    # Ensure the parent of the package directory is on sys.path so
    # package imports inside the library work as intended.
    pkg_parent = os.path.dirname(ROOT)
    if pkg_parent not in sys.path:
        sys.path.insert(0, pkg_parent)

    pkg_name = os.path.basename(ROOT)
    cfg_mod = importlib.import_module(f"{pkg_name}.config")
    aha_mod = importlib.import_module(f"{pkg_name}.anytime_hierarchical_astar")

    PlannerConfig = getattr(cfg_mod, 'PlannerConfig')
    AnytimeHierarchicalAStar = getattr(aha_mod, 'AnytimeHierarchicalAStar')

    cfg = PlannerConfig(map_bounds=([-5, -5, 0], [5, 5, 2]), voxel_size=0.5, timeout=30)
    planner = AnytimeHierarchicalAStar(cfg, coarse_factor=2, initial_epsilon=2.0, epsilon_decay=0.5)

    start = [-4.0, -4.0, 0.0]
    goal = [4.0, 4.0, 0.0]

    t0 = time.time()
    result = planner.plan_path(start, goal)
    elapsed = time.time() - t0

    print('Success:', result.success)
    print('Path length:', result.path_length)
    print('Nodes explored:', result.nodes_explored)
    print('Elapsed:', elapsed)
    if result.path:
        print('First point:', result.path[0])
        print('Last point:', result.path[-1])

if __name__ == '__main__':
    main()
