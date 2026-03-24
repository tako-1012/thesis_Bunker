#!/usr/bin/env python3
import os
import json
import numpy as np
from importlib import util

base = os.path.join(os.path.dirname(__file__), '..')
npz_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_data.npz')
meta_path = os.path.join(base, 'terrain_test_scenarios', 'hill_detour_meta.json')

print('Loading', npz_path)
data = np.load(npz_path)
with open(meta_path,'r') as f:
    meta = json.load(f)

elev = data['elevation']
height_map = np.max(elev, axis=2)
print('height_map shape', height_map.shape)

# load planners
repo_root = base
ta_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/terrain_aware_astar.py')
astar_path = os.path.join(repo_root, 'ros2/ros2_ws/src/path_planner_3d/path_planner_3d/astar_3d.py')

spec = util.spec_from_file_location('ta', ta_path)
mod = util.module_from_spec(spec)
spec.loader.exec_module(mod)
TerrainAwareAStar = mod.TerrainAwareAStar

spec2 = util.spec_from_file_location('astar', astar_path)
mod2 = util.module_from_spec(spec2)
spec2.loader.exec_module(mod2)
AStar3D = mod2.AStar3D

grid_size = tuple(meta['grid_size'])
voxel_size = float(meta['voxel_size'])
start = tuple(meta['start'])
goal = tuple(meta['goal'])

# run planners
print('Running TA* and A*')
ta = TerrainAwareAStar(voxel_size=voxel_size, grid_size=grid_size)
ta.set_terrain_data(data['voxel_grid'], {'elevation': elev, 'roughness': data['roughness'], 'density': data['density']})
ta_res = ta.plan_path(start, goal)
if isinstance(ta_res, dict):
    ta_path_world = np.array(ta_res.get('path',[]))
else:
    ta_path_world = np.array(getattr(ta_res, 'path', []))

# Regular A*
astar = AStar3D(voxel_size=voxel_size, max_iterations=200000)
# compute voxel start/goal
half_x = (grid_size[0] * voxel_size) / 2.0
half_y = (grid_size[1] * voxel_size) / 2.0
min_bound = np.array([-half_x, -half_y, 0.0])

s_vox = tuple(np.round((np.array(start)-min_bound)/voxel_size).astype(int))
g_vox = tuple(np.round((np.array(goal)-min_bound)/voxel_size).astype(int))

astar_res = astar.plan_path(s_vox, g_vox, data['voxel_grid'], cost_function=None)
if isinstance(astar_res, dict):
    a_path_vox = astar_res.get('path', [])
else:
    a_path_vox = getattr(astar_res, 'path', [])
reg_path_world = [tuple(min_bound + (np.array(p)+0.5)*voxel_size) for p in a_path_vox]
reg_path_world = np.array(reg_path_world)

print('TA path points', ta_path_world.shape)
print('Reg path points', reg_path_world.shape)

# sample heights with correct shift: world coords are centered around 0, map extent 0-100 corresponds to +50 shift
nx, ny = height_map.shape

def sample_heights_world(path):
    hs = []
    for p in path:
        xw, yw = p[0], p[1]
        # shift by +50
        xi = int(round((xw+50.0)/100.0*(nx-1)))
        yi = int(round((yw+50.0)/100.0*(ny-1)))
        xi = max(0, min(nx-1, xi))
        yi = max(0, min(ny-1, yi))
        hs.append(float(height_map[xi, yi]))
    return hs

ta_h = sample_heights_world(ta_path_world)
reg_h = sample_heights_world(reg_path_world)
print('TA max height', max(ta_h) if ta_h else None)
print('Reg max height', max(reg_h) if reg_h else None)
print('Height diff reg-ta', (max(reg_h)-max(ta_h)) if ta_h and reg_h else None)

