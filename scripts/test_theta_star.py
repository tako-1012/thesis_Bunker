#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d'))
import numpy as np
from theta_star import ThetaStar

def run_theta(scenario):
    if scenario == 'SMALL':
        grid_size=(50,50,10)
        start=(0,0,0.2)
        goal=(40,40,0.2)
    elif scenario=='MEDIUM':
        grid_size=(100,100,20)
        start=(0,0,0.2)
        goal=(80,80,0.2)
    else:
        grid_size=(200,200,50)
        start=(0,0,0.2)
        goal=(180,180,0.2)
    terrain = np.zeros(grid_size)
    planner = ThetaStar(voxel_size=0.2, grid_size=grid_size)
    planner.set_terrain_data(terrain)
    path = planner.plan_path(start, goal)
    print(scenario, 'path_len', len(path) if path else None)

if __name__ == '__main__':
    for s in ['SMALL','MEDIUM','LARGE']:
        run_theta(s)
