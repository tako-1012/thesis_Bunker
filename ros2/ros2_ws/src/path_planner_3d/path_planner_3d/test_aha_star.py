"""
Minimal sanity check for AnytimeHierarchicalAStar.
Run with: python3 test_aha_star.py
"""
import time

try:
    from .config import PlannerConfig
    from .anytime_hierarchical_astar import AnytimeHierarchicalAStar
except ImportError:  # pragma: no cover
    from config import PlannerConfig
    from anytime_hierarchical_astar import AnytimeHierarchicalAStar


def run_demo():
    cfg = PlannerConfig(map_bounds=([-5, -5, 0], [5, 5, 2]), voxel_size=0.5, timeout=60)
    planner = AnytimeHierarchicalAStar(cfg, coarse_factor=2, initial_epsilon=2.0, epsilon_decay=0.5)
    start = [-4.0, -4.0, 0.0]
    goal = [4.0, 4.0, 0.0]

    t0 = time.time()
    result = planner.plan_path(start, goal)
    elapsed = time.time() - t0

    print("Success:", result.success)
    print("Path length:", result.path_length)
    print("Nodes explored:", result.nodes_explored)
    print("Elapsed:", elapsed)
    if result.path:
        print("First point:", result.path[0])
        print("Last point:", result.path[-1])

    assert result.path_length >= 0.0
    if result.success:
        assert len(result.path) >= 2


if __name__ == "__main__":
    run_demo()
