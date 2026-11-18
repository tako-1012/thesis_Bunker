"""Hash every map array after each update; run in base and 038 worktrees and compare."""
import hashlib, json, sys
import numpy as np
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.real_beach import build_real

def h(a): return hashlib.sha256(np.ascontiguousarray(a).tobytes()+str(a.dtype).encode()+str(a.shape).encode()).hexdigest()[:16]
truth = build_real('08OB88_-0167', 200, 0, debris=True, dataset='shizuoka_beach_las')
prior_tm = build_real('08OB88_-0167', 200, 0, dataset='shizuoka_beach_las')['tmap']
elev = prior_tm.elev; rock = np.zeros(elev.shape, bool)
true_elev = truth['tmap'].elev
out = {}
for cls in (PointCloudMapFine, PointCloudMapMulti):
  for ground in ('all_returns', 'non_obstacle'):
    rng = np.random.default_rng(2026)
    m = cls(elev, rock, ground_estimate=ground)
    seq = []
    x, y = 60., 60.
    for i in range(40):
        x += rng.uniform(-1, 3); y += rng.uniform(-1, 3)
        x = float(np.clip(x, 10, 180)); y = float(np.clip(y, 10, 180))
        n = int(rng.integers(500, 6000))
        pts = rng.uniform(-12, 12, (n, 2)) + [x, y]
        idx = np.clip(np.rint(pts/0.5).astype(int), 0, np.array(true_elev.shape)-1)
        z = true_elev[idx[:, 0], idx[:, 1]] + rng.normal(0, .02, n)
        # boxes / steep spikes
        box = rng.random(n) < .08; z[box] += rng.uniform(.3, 1.2, box.sum())
        world = np.column_stack((pts, z))
        sensor = np.column_stack((world[:, 0]-x, world[:, 1]-y, world[:, 2]-0.8))
        if i % 5 == 0: sensor[:20] = np.nan
        if i % 7 == 0: sensor[20:30] = np.inf
        pose = np.array([x, y, 0., 0., 0., 0.])
        kw = dict(sensor=['lidar', 'camera1', 'camera2'][i % 3]) if cls is PointCloudMapMulti else {}
        m.update(sensor, pose, **kw)
        state = [h(getattr(m, k)) for k in ('elev', 'seen', 'lethal', 'fine_obstacle', 'fine_inflated', 'detected_obstacle')]
        state += [h(getattr(m.tm, k)) for k in ('slope', 'rough', 'cost', 'steep', 'rock', 'lethal', 'gx', 'gy')]
        seq.append(state)
    out[f'{cls.__name__}/{ground}'] = seq
json.dump(out, open(sys.argv[1], 'w'))
print('done', {k: len(v) for k, v in out.items()})
