import numpy as np
from dstar_lite_planner import DStarLitePlanner

# 非常にシンプルな地形でテスト
cost_map = np.ones((100, 100), dtype=np.float32) * 0.1  # ほぼ全て通行可能

start = np.array([1.0, 1.0, 0.0])
goal = np.array([8.0, 8.0, 0.0])
bounds = ((-1.0, 10.0), (-1.0, 10.0), (0.0, 2.0))

planner = DStarLitePlanner(
    start=start, goal=goal, bounds=bounds,
    terrain_cost_map=cost_map, resolution=0.1
)

print("D* Lite simple test...")
import time
start_time = time.time()
path = planner.plan()
elapsed = time.time() - start_time

if path:
    print(f"\u2713 SUCCESS in {elapsed:.2f}s")
    print(f"  Waypoints: {len(path)}")
    total_dist = sum(np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1))
    print(f"  Distance: {total_dist:.2f}m")
else:
    print(f"\u2717 FAILED after {elapsed:.2f}s")
