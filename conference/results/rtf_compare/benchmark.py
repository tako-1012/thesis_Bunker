"""Time a sustained synthetic three-sensor run using one production fine map."""

import argparse
import csv
from pathlib import Path

import numpy as np

from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from tapp.config import RESOLUTION
from tapp.sensor_geometry import DepthCameraSpec, REAL_MOUNTS, transform_sensor_points

SENSORS = ('lidar', 'camera1', 'camera2')
SEED = 103
FRAMES = 120


def ground(x, y, *, shift=0.):
    """A gently rolling beach with a steeper bank displaced in the prior."""
    bank_y = 101.8 + .7*np.sin((x-85.)/4.) + shift
    return .02*(x-90.) + .01*(y-100.) + .55*(1.+np.tanh((y-bank_y)/.55))


def footprints():
    """Use the point counts and ground-return patterns of the 038 workloads."""
    theta = np.tile(np.linspace(-np.pi, np.pi, 1800, endpoint=False), 16)
    radius = np.repeat(np.linspace(4.2, 22., 16), 1800)
    lidar = np.column_stack((radius*np.cos(theta), radius*np.sin(theta), np.zeros(len(theta))))
    spec = DepthCameraSpec()
    x, slope = np.meshgrid(np.linspace(1.5, 4.1, spec.height), np.linspace(-.8, .8, spec.width))
    camera = np.column_stack((x.ravel(), (x*slope).ravel(), np.zeros(x.size)))
    return {'lidar': lidar, 'camera1': camera, 'camera2': camera}


def make_scan(sensor, xy_grid, pose, rng):
    local = xy_grid.copy()
    if sensor == 'lidar':
        local[:, :2] += rng.normal(0., .04, local[:, :2].shape)
    mount = REAL_MOUNTS[sensor]
    world = transform_sensor_points(local, pose, mount)
    x, y = world[:, 0], world[:, 1]
    surface = ground(x, y)
    for bx, by in ((93., 99.), (99., 102.)):
        surface[(abs(x-bx) < .5) & (abs(y-by) < .5)] += .4
    noise = .02 if sensor == 'lidar' else .01
    local[:, 2] = surface-world[:, 2]+rng.normal(0., noise, len(local))
    return local


def run():
    rng = np.random.default_rng(SEED)
    x, y = np.indices((400, 400))*RESOLUTION
    mapper = make_pointcloud_map(ground(x, y, shift=-1.2), map_method='fine',
                                 sensors='lidar_real+depth2', ground_estimate='non_obstacle')
    templates = footprints()
    previous_steep = mapper.tm.steep.copy()
    records = []
    for frame in range(FRAMES):
        for sensor, offset in zip(SENSORS, (0., .025, .05), strict=True):
            stamp = frame/10 + offset
            x = 90.+stamp
            y = 99.7+.2*np.sin(stamp)
            pose = np.array([x, y, float(ground(x, y)), 0., 0., 0.])
            cloud = make_scan(sensor, templates[sensor], pose, rng)
            result = mapper.update(cloud, pose, sensor=sensor, stamp=stamp)
            steep = mapper.tm.steep
            records.append(dict(frame=frame, stamp_sim_s=stamp, sensor=sensor, x_m=x, y_m=y,
                                input_points=len(cloud), accepted_points=result['accepted_points'],
                                observed_cells=result['observed_cells'], update_s=result['update_s'],
                                steep_added=int(np.count_nonzero(steep & ~previous_steep)),
                                steep_removed=int(np.count_nonzero(previous_steep & ~steep))))
            previous_steep = steep.copy()
    return records


def summarize(records):
    cpu = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
               if line.startswith('model name'))
    print(f'CPU: {cpu}')
    print(f'seed={SEED} frames={FRAMES} updates={len(records)} map=400x400 ground=non_obstacle reference=prior')
    print('sensor updates points accepted_min accepted_max median_ms p95_ms max_ms steep_changed added removed')
    for sensor in SENSORS:
        rows = [row for row in records if row['sensor'] == sensor]
        times = np.array([row['update_s']*1_000 for row in rows])
        accepted = [row['accepted_points'] for row in rows]
        added = sum(row['steep_added'] for row in rows)
        removed = sum(row['steep_removed'] for row in rows)
        changed = sum(1 for row in rows if row['steep_added'] or row['steep_removed'])
        print(sensor, len(rows), rows[0]['input_points'], min(accepted), max(accepted),
              *(f'{value:.3f}' for value in (*np.percentile(times, (50, 95)), times.max())),
              changed, added, removed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', required=True, type=Path)
    args = parser.parse_args()
    records = run()
    with args.csv.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(records)
    summarize(records)


if __name__ == '__main__':
    main()
