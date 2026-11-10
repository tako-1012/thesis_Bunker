"""Task027 visibility of vertical point-columns: no occlusion/noise/pixel guarantee.

Distances are horizontal metres from model origin; azimuth 0 is forward.
LiDAR has 16 discrete elevations and continuous azimuth (width unspecified).
"""

import argparse
import csv
import json
from pathlib import Path
import numpy as np
from tapp.sensor_geometry import REAL_MOUNTS, DepthCameraSpec

MODES = ('legacy_lidar', 'lidar_real', 'lidar_real+depth2')
HEIGHTS = (.1, .2, .3, .5)
DIRECTIONS = (0, 45, -45, 90, -90, 180)


def visible(x, y, height, mode):
    if mode not in MODES or not np.isfinite(height) or height <= 0:
        raise ValueError('unknown mode or invalid height')
    x, y = np.broadcast_arrays(np.asarray(x, float), np.asarray(y, float))
    real = mode != 'legacy_lidar'
    sx, sy, sz = REAL_MOUNTS['lidar'].xyz if real else (0., 0., .8)
    radius = np.hypot(x-sx, y-sy)
    hits = np.zeros(x.shape, bool)
    for elevation in np.deg2rad(np.linspace(-15, 15, 16)):
        z = sz+radius*np.tan(elevation)
        distance = radius/np.cos(elevation)
        hits |= (z >= 0.) & (z <= height) & (distance >= (.9 if real else .1)) & (distance < 29.995)
    if mode == 'lidar_real+depth2':
        spec = DepthCameraSpec()
        for name in ('camera1', 'camera2'):
            camera = REAL_MOUNTS[name]
            dx, dy = x-camera.xyz[0], y-camera.xyz[1]
            yaw = camera.rpy[2]
            forward, left = dx*np.cos(yaw)+dy*np.sin(yaw), -dx*np.sin(yaw)+dy*np.cos(yaw)
            low = np.maximum(-camera.xyz[2], -forward*np.tan(np.deg2rad(spec.vertical_fov_deg/2)))
            high = np.minimum(height-camera.xyz[2], forward*np.tan(np.deg2rad(spec.vertical_fov_deg/2)))
            closest_z = np.clip(0., low, np.maximum(low, high))
            hits |= ((forward >= spec.min_range_m) & (low <= high)
                     & (np.abs(left) <= forward*np.tan(np.deg2rad(spec.horizontal_fov_deg/2)))
                     & (np.sqrt(forward**2+left**2+closest_z**2) < spec.max_range_m))
    return hits


def intervals(mask, distances):
    ids = np.flatnonzero(mask)
    if not len(ids):
        return []
    groups = np.split(ids, np.flatnonzero(np.diff(ids) > 1)+1)
    return [[round(float(distances[g[0]]), 2), round(float(distances[g[-1]]), 2)] for g in groups]


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    distances = np.arange(.01, 30.0001, .01)
    rows = []
    for height in HEIGHTS:
        for mode in MODES:
            for direction in DIRECTIONS:
                angle = np.deg2rad(direction)
                ranges = intervals(visible(distances*np.cos(angle), distances*np.sin(angle), height, mode), distances)
                row = dict(height_m=height, sensors=mode, direction_deg=direction,
                           first_visible_m=ranges[0][0] if ranges else '', visible_intervals_m=json.dumps(ranges, separators=(',', ':')))
                row.update({f'at_{d}m': bool(visible(d*np.cos(angle), d*np.sin(angle), height, mode)) for d in (1,2,3,4,5,6)})
                rows.append(row)
    with (output/'coverage.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    lines = ['# センサーの幾何学的な死角（Gazebo未実行）', '',
             '距離は模型原点からの水平距離。0°は前、+90°は左。距離刻み0.01mの近似表。',
             '地面から指定高さまでの垂直な点状物を対象とする。LiDARは16本の縦ビーム、方位は連続と仮定。',
             'カメラは連続視野の幾何学。画素での命中・遮蔽・ノイズ・姿勢変動・判定に必要な3点は含まない。',
             '幾何学的に見えても障害物検出を保証しない（既存の高さしきい値は0.3m）。', '',
             '| 高さ m | センサー | 方向 ° | 最初に見える距離 m | 見える区間 m |', '|---|---|---|---|---|']
    for r in rows:
        lines.append(f"| {r['height_m']} | {r['sensors']} | {r['direction_deg']} | {r['first_visible_m']} | {r['visible_intervals_m']} |")
    (output/'coverage_ja.md').write_text('\n'.join(lines)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap, BoundaryNorm
    from matplotlib.patches import Patch
    fig, axes = plt.subplots(2,2,figsize=(11,10))
    coord = np.linspace(-8,8,321); x,y = np.meshgrid(coord,coord)
    cmap = ListedColormap(['#eeeeee','#999999','#0072b2','#e69f00'])
    for ax,h in zip(axes.flat,HEIGHTS):
        legacy,lidar,combined = [visible(x,y,h,mode) for mode in MODES]
        category = np.where(combined & ~lidar,3,np.where(lidar,2,np.where(legacy,1,0)))
        ax.imshow(category,extent=[-8,8,-8,8],origin='lower',cmap=cmap,norm=BoundaryNorm([-.5,.5,1.5,2.5,3.5],4))
        ax.plot(0,0,'k+',markersize=9)
        ax.set(title=f'Object height {h:.1f} m',xlabel='Forward x (m)',ylabel='Left y (m)')
    fig.legend(handles=[Patch(color=c,label=t) for c,t in zip(cmap.colors,['Blind','Legacy only','Real LiDAR','Added by cameras'])],loc='lower center',ncol=4)
    fig.tight_layout(rect=(0,.04,1,1)); fig.savefig(output/'coverage.png',dpi=140); plt.close(fig)
    print('height_m | sensors | front_first_visible_m | front_visible_intervals_m')
    for r in rows:
        if r['direction_deg']==0:
            print(f"{r['height_m']} | {r['sensors']} | {r['first_visible_m']} | {r['visible_intervals_m']}")
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=Path('results/real_sensors'))
    generate(p.parse_args().output)


if __name__=='__main__':
    main()
