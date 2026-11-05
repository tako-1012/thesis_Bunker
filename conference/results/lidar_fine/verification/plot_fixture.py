"""Visualize the fixed synthetic test fixture, never a physical trial."""

from pathlib import Path
import sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = Path(__file__).resolve().parent.parent
ROOT = OUT.parents[1]
sys.path.insert(0, str(ROOT))
from tests.test_pointcloud_map_fine import box_cloud
from tapp.pointcloud_map import PointCloudMap, transform_points
from tapp.pointcloud_map_fine import PointCloudMapFine

cloud, pose = box_cloud(100)
world = transform_points(cloud, pose)
high = world[world[:, 2] >= .3]
fig, axes = plt.subplots(1, 2, figsize=(10, 5))
counts = []
for ax, cls, name, cmap in zip(axes, [PointCloudMap, PointCloudMapFine], ['022 coarse', '023 fine'], ['Reds', 'Blues']):
    mapper = cls(np.zeros((40, 40)))
    mapper.update(cloud, pose)
    outside = mapper.lethal.copy()
    outside[10, 10] = False
    count = int(outside.sum())
    counts.append((name, count))
    ax.imshow(np.ma.masked_where(~mapper.lethal.T, mapper.lethal.T), origin='lower',
              extent=[-.25, 19.75, -.25, 19.75], cmap=cmap, vmin=0, vmax=1, alpha=.45)
    ax.add_patch(Rectangle((4.75, 4.75), .5, .5, fill=False, edgecolor='black', lw=2, label='true box footprint'))
    ax.scatter(high[:, 0], high[:, 1], s=8, color='black', label='noisy high returns')
    ax.set(xlim=(3.7, 6.3), ylim=(3.7, 6.3), aspect='equal', xlabel='x [m]', ylabel='y [m]',
           title=name+': outside lethal = '+str(count))
    ax.set_xticks(np.arange(3.75, 6.3, .5));ax.set_yticks(np.arange(3.75, 6.3, .5))
    ax.grid(alpha=.4);ax.legend(fontsize=7)
fig.suptitle('SYNTHETIC FIXTURE ONLY: radial noise 0.02m, seed 100; no Gazebo measurements')
fig.tight_layout()
fig.savefig(OUT/'box_fixture.png', dpi=150)
plt.close(fig)
print('Synthetic fixture outside lethal cells:', counts)
