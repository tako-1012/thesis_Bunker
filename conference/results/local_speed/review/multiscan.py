"""Compare 032 local (base) vs 036 local over a moving sequence of synthetic LiDAR scans."""
import sys, numpy as np
from unittest.mock import patch
from tests.test_local_speed import baseline_module, synthetic_cloud, mask_differences
from tapp import local_ground
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.sensor_geometry import REAL_MOUNTS
from tests.test_real_sensors import local_cloud
ref = baseline_module('local_ground').update_local
Old = baseline_module('pointcloud_map_multi').PointCloudMapMulti
rng = np.random.default_rng(7)
prior = np.zeros((401, 401))
# terrain: gentle slope + bumps + 6 boxes 0.4m
def ground(x, y): return .03*x + .02*y + .15*np.sin(x/3)*np.cos(y/4)
boxes = [(110,100),(118,103),(126,97),(134,101),(142,99),(150,104)]
maps = [Old(prior, obstacle_reference='local'), PointCloudMapMulti(prior, obstacle_reference='local')]
mount = REAL_MOUNTS['lidar']
for k in range(12):
    px = 100 + 4*k
    pose = np.array([px, 100., 0., 0., 0., 0.])
    angle = np.tile(np.linspace(-np.pi, np.pi, 1800, endpoint=False), 16)
    d = np.repeat(np.linspace(4.2, 22., 16), 1800) + rng.normal(0, .08, len(angle))
    x, y = px + d*np.cos(angle), 100 + d*np.sin(angle)
    z = ground(x, y)
    for bx, by in boxes:
        z[(abs(x-bx) < .5) & (abs(y-by) < .5)] += .4
    pts = local_cloud(np.column_stack((x, y, z)), pose, mount)
    for m, impl in zip(maps, (ref, local_ground.update_local)):
        with patch.object(local_ground, 'update_local', impl):
            m.update(pts, pose, sensor='lidar')
    print(k, 'fine/coarse diff', mask_differences(*maps), 'elev max abs diff', float(np.nanmax(np.abs(maps[0].elev-maps[1].elev))), flush=True)
old, new = maps
d = np.abs(old.elev-new.elev)
print('coarse cells |elev diff|>0.05:', int((d > .05).sum()), ' lethal diff:', int((old.lethal != new.lethal).sum()))
for i in np.argwhere(d > .05)[:8]:
    c = tuple(i); print('  cell', c, 'xy', (c[0]*.5, c[1]*.5), 'old', round(float(old.elev[c]),3), 'new', round(float(new.elev[c]),3), 'truth', round(float(ground(c[0]*.5, c[1]*.5)),3))
fs = old.fine_shape
ii = np.argwhere(old.fine_obstacle != new.fine_obstacle)
def inbox(f):
    x = f[0]*.1 - .25 + .05; y = f[1]*.1 - .25 + .05
    return any(abs(x-bx) < .6 and abs(y-by) < .6 for bx, by in boxes)
print('fine diffs: only-old', [(tuple(f), inbox(f)) for f in ii if old.fine_obstacle[tuple(f)]][:15])
print('fine diffs: only-new', [(tuple(f), inbox(f)) for f in ii if new.fine_obstacle[tuple(f)]][:15])
