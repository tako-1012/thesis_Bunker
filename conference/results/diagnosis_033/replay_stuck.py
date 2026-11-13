"""Task033 A: replay the planner search and the _join check from a saved periodic snapshot.

python results/diagnosis_033/replay_stuck.py RAW_RUN_DIR [snapshot.npz]
Uses the same astar / smooth_cost_aware / _join rule as LidarOnlineMission (no code change).
"""
import sys, glob
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.planners import astar, smooth_cost_aware
from tapp.collision import line_of_sight_exact, path_lethal_cells, segment_cells, EPS


def bits(z, n):
    s = tuple(z[n+'_shape'])
    return np.unpackbits(z[n+'_bits'], count=int(np.prod(s))).reshape(s).astype(bool)


def replay(path_npz):
    z = np.load(path_npz)
    lethal, mult = bits(z, 'lethal'), z['cost']
    start, goal, pose = tuple(int(v) for v in z['start']), tuple(int(v) for v in z['goal']), z['pose']
    pos = np.asarray(pose[:2], float)/RESOLUTION
    print(f'{Path(path_npz).name} t={float(z["sim_time"]):.2f} pose_m=({pose[0]:.3f},{pose[1]:.3f}) pos_cell=({pos[0]:.3f},{pos[1]:.3f}) '
          f'start={start} goal={goal} EPS={EPS}')
    print(f'  start cell lethal={bool(lethal[start])}  3x3 lethal around start:\n{lethal[start[0]-1:start[0]+2, start[1]-1:start[1]+2].astype(int)}')
    result = astar(lethal, start, goal, mult)
    print(f'  astar success={result["success"]}')
    if not result['success']:
        return
    path, _ = smooth_cost_aware(result['path'], lethal, mult, los=line_of_sight_exact)
    path = [np.asarray(p, float) for p in path]
    print(f'  smoothed path head: {[tuple(np.round(p, 2)) for p in path[:4]]}')
    # same as OnlinePlanner._plan (initial=False): re-anchor at self.pos
    rest = path[1:]
    known_lethal = lethal
    planner_path = [pos.copy()] + rest if rest and line_of_sight_exact(known_lethal, tuple(pos), tuple(rest[0])) else [pos.copy(), np.asarray(start, float)] + rest
    # same as _join
    best = None
    for i, (a, b) in enumerate(zip(planner_path[:-1], planner_path[1:])):
        d = b-a
        t = float(np.clip(np.dot(pos-a, d)/np.dot(d, d), 0, 1)) if np.any(d) else 0.
        dist = float(np.linalg.norm(pos-(a+t*d)))
        if best is None or dist < best[0]:
            best = dist, i
    rest = planner_path[best[1]+1:]
    los = bool(rest) and line_of_sight_exact(known_lethal, tuple(pos), tuple(rest[0]))
    joined = [pos]+rest if los else [pos, np.asarray(start, float)]+rest
    hits = path_lethal_cells(joined, known_lethal)
    print(f'  _join: los_to_rest0={los} joined_head={[tuple(np.round(p, 3)) for p in joined[:3]]}')
    print(f'  _join lethal cells on joined path: {hits.tolist()}  -> {"REJECTED (returns None)" if len(hits) else "accepted"}')
    for a, b in zip(joined[:-1], joined[1:]):
        cells = segment_cells(a, b, lethal.shape)
        bad = cells[lethal[cells[:, 0], cells[:, 1]]]
        if len(bad):
            print(f'    segment {tuple(np.round(a, 3))} -> {tuple(np.round(b, 3))} touches lethal {bad.tolist()}')


if __name__ == '__main__':
    raw = Path(sys.argv[1])
    files = sys.argv[2:] or sorted(glob.glob(str(raw/'diag/periodic_*.npz')))
    for f in files:
        replay(f)
