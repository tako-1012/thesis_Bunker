#!/usr/bin/env python3
"""
Debug: Verify terrain cost calculation
"""
import sys
sys.path.insert(0, '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d')
sys.path.insert(0, '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d')

import json
import numpy as np
import importlib

# Load scenario
with open('dataset3_scenarios.json') as f:
    scenario = json.load(f)[0]  # dataset3_1_1_1

print("="*60)
print("SCENARIO:", scenario['id'])
print("="*60)

# Terrain data
height_map = np.array(scenario.get('height_map'))
print(f"\n[TERRAIN DATA]")
print(f"Height map shape: {height_map.shape}")
print(f"Height range: {height_map.min():.2f} - {height_map.max():.2f}m")
print(f"Mean height: {height_map.mean():.2f}m")

# Build terrain_data
terrain_data = {'height_map': height_map}

# Coordinates
sx, sy = scenario.get('start', (0, 0))
gx, gy = scenario.get('goal', (0, 0))
start = (float(sx), float(sy), 0.0)
goal = (float(gx), float(gy), 0.0)

print(f"\n[COORDINATES]")
print(f"Start: {start}")
print(f"Goal: {goal}")

# === D*Lite Test ===
print("\n" + "="*60)
print("D*LITE TEST")
print("="*60)

try:
    # Check if terrain cost calculation exists
    from path_planner_3d.dstar_lite_3d import DStarLite3D
    
    # Create planner
    size = int(max(scenario['map_size']))
    z_layers = 8
    planner = DStarLite3D(voxel_size=1.0, grid_size=(size, size, z_layers))
    
    # Build voxel grid (properly sized)
    obs = np.array(scenario.get('obstacle_map', np.zeros((size, size))), dtype=np.uint8)
    if obs.shape != (size, size):
        obs_resized = np.zeros((size, size), dtype=np.uint8)
        obs_resized[:obs.shape[0], :obs.shape[1]] = obs
        obs = obs_resized
    voxel_grid = np.zeros((size, size, z_layers), dtype=np.float32)
    voxel_grid[:, :, 0] = obs.T
    
    # Set terrain data
    planner.set_terrain_data(voxel_grid, terrain_data)
    
    # Check if _compute_terrain_cost method exists
    if hasattr(planner, '_compute_terrain_cost'):
        print("✅ _compute_terrain_cost method exists")
        
        # Test terrain cost at a few points
        test_points = [(10, 10, 0), (50, 50, 0), (100, 100, 0)]
        for x, y, z in test_points:
            if x < size and y < size:
                try:
                    cost = planner._compute_terrain_cost((x, y, z))
                    print(f"   Terrain cost at ({x},{y},{z}): {cost:.3f}")
                except Exception as e:
                    print(f"   Error at ({x},{y},{z}): {e}")
    else:
        print("❌ _compute_terrain_cost method NOT found")
    
    # Run path planning
    result = planner.plan_path(start, goal)
    
    if result and getattr(result, 'success', False):
        path_length = getattr(result, 'path_length', 0.0)
        print(f"\n✅ D*Lite SUCCESS")
        print(f"   Path length: {path_length:.2f}m")
        print(f"   Result type: {type(result)}")
        print(f"   Result attributes: {dir(result)}")
    else:
        print(f"\n❌ D*Lite FAILED")
        
except Exception as e:
    print(f"❌ D*Lite ERROR: {e}")
    import traceback
    traceback.print_exc()

# === TA* Test ===
print("\n" + "="*60)
print("TA* TEST")
print("="*60)

try:
    from path_planner_3d.terrain_aware_astar import TerrainAwareAStar
    
    # Create planner with HIGHER terrain weight for terrain avoidance
    planner = TerrainAwareAStar(
        voxel_size=1.0,
        terrain_weight=2.0,  # 高くして地形を強く回避
        heuristic_multiplier=1.0
    )
    
    # Set terrain data
    planner.set_terrain_data(voxel_grid, terrain_data, min_bound=(0.0, 0.0, 0.0))
    
    # Check if _compute_terrain_cost exists
    if hasattr(planner, '_compute_terrain_cost'):
        print("✅ _compute_terrain_cost method exists")
        
        # Check terrain_data
        if hasattr(planner, 'terrain_data'):
            print(f"   terrain_data: {planner.terrain_data is not None}")
            if planner.terrain_data and 'height_map' in planner.terrain_data:
                hm = planner.terrain_data['height_map']
                print(f"   height_map shape: {hm.shape if hasattr(hm, 'shape') else 'N/A'}")
    else:
        print("❌ _compute_terrain_cost method NOT found")
    
    # Run path planning
    result = planner.plan_path(start, goal)
    
    stats = getattr(planner, 'last_search_stats', {})
    success = getattr(result, 'success', False) if result else False
    
    if success:
        path_length = getattr(result, 'path_length', stats.get('path_length', 0.0))
        print(f"\n✅ TA* SUCCESS")
        print(f"   Path length: {path_length:.2f}m")
        print(f"   Result type: {type(result)}")
    else:
        print(f"\n❌ TA* FAILED")
        if result:
            print(f"   Result: {result}")
        
except Exception as e:
    print(f"❌ TA* ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("COMPARISON")
print("="*60)
print("If terrain cost is working:")
print("  - Terrain cost values should be > 1.0 (not always 1.0)")
print("  - D*Lite and TA* path lengths should DIFFER")
print("  - Expected: TA* > D*Lite (terrain avoidance)")
print("="*60)
