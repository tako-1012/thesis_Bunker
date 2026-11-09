"""How close each run of 08OB87_-0706 passed the driftwood next to the no_path point (read-only).

Prints, per run: closest approach to the no_path end point and to the rock cell, whether the no_path robot
cell is blocked in that run's final map, and how many distinct cells of the track are blocked in that final map.
The final map is the end-of-run state, not the state when the robot passed, so the last two are indicators only.

Usage (from conference/): python3 results/rtf_check/divergence/rock_approach.py > results/rtf_check/divergence/rock_approach.csv"""
import csv, sys
from pathlib import Path
import numpy as np
RES, P = .5, '08OB87_-0706'
C = Path('results/rtf_check')
NO_PATH_XY, CELL, ROCK = np.array([76.9, 71.01]), (154, 142), np.array([77., 71.75])
runs = {'first_0.3': C/'hayashi_first_gazebo_check/physical_3/raw'/P, 'cloud_0.3': Path('results/lidar_fine/physical_10/raw')/P}
for r in sorted((C/'hayashi_rtf_repeat').glob('rtf_*')):
    runs[r.name] = r/'physical_1/raw'/P
for r in sorted((C/'divergence').glob('R[12]_*')):
    runs[r.name] = r/'physical_1/raw'/P
w = csv.writer(sys.stdout)
w.writerow(['run', 'min_to_no_path_m', 'min_to_rock_m', 'cell_154_142_blocked', 'blocked_of_9', 'track_cells', 'track_cells_blocked_final'])
for name, raw in runs.items():
    if not (raw/'pointcloud_map.npz').exists() or not (raw/'trajectory.csv').exists():
        w.writerow([name] + ['']*6); continue
    t = np.array([[float(r['x']), float(r['y'])] for r in csv.DictReader((raw/'trajectory.csv').open())])
    m = np.load(raw/'pointcloud_map.npz'); b = m['seen'] & m['lethal']
    cells = {tuple(c) for c in np.round(t/RES).astype(int)}
    i, j = CELL
    w.writerow([name, round(float(np.hypot(*(t-NO_PATH_XY).T).min()), 2), round(float(np.hypot(*(t-ROCK).T).min()), 2), int(b[CELL]),
                int(b[i-1:i+2, j-1:j+2].sum()), len(cells), sum(int(b[c]) for c in cells)])
