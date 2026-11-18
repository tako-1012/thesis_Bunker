"""Task036 parity, replay, update timing and waypoint selection without ROS."""

from collections import defaultdict
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks.lidar_checks import BASELINE, prepare_cases
from tapp import local_ground
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.sensor_geometry import REAL_MOUNTS
from tests.test_prior_free import ROOT, cloud, errors, mapper_for, test_default_bytes, update
from tests.test_real_sensors import local_cloud

UNCHANGED = {'08OB86_-0205', '08OB88_-1417', '08OB88_-0167', '08OB88_00332', '08OB89_-0847'}


def baseline_module(name):
    # Keep the reference files byte-identical to 5f36770; load with the
    # original package context so their relative tapp imports resolve.
    source = ROOT/'tests/reference'/f'{name}_032.py'
    spec = importlib.util.spec_from_file_location(f'tapp.{name}_032', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def mask_differences(before, after):
    return (int(np.count_nonzero(before.fine_obstacle != after.fine_obstacle)),
            int(np.count_nonzero(before.detected_obstacle != after.detected_obstacle)))


def test_task032(reference):
    for slope in (0., 20.):
        for box in (False, True):
            for shift in (0., -.4, .4):
                old, fast = mapper_for(slope, shift), mapper_for(slope, shift)
                points = cloud(slope, box)
                with patch.object(local_ground, 'update_local', reference):
                    update(old, points)
                update(fast, points)
                assert errors(old, box) == errors(fast, box) == (0, 0)
                diff = mask_differences(old, fast)
                assert diff == (0, 0), (slope, box, shift, diff)
                print(f'032 slope={slope:g} box={box} shift={shift:g}: fine/coarse={diff}')


def test_edge_margin():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prepare_cases(root/'default', patch_count=10)
        prepare_cases(root/'zero', patch_count=10, edge_margin_m=0)
        default = (root/'default'/'manifest.json').read_bytes()
        assert default == (root/'zero'/'manifest.json').read_bytes()
        assert 'edge_margin_m' not in json.loads(default)
        cli = ROOT/'ros2_jazzy/gz_checks/lidar_checks.py'
        env = dict(os.environ, PYTHONPATH=str(ROOT))
        subprocess.run([sys.executable, str(cli), '--output', str(root/'ten'),
                        '--patch-count', '10', '--edge-margin-m', '10', '--prepare-only'],
                       check=True, env=env)
        ten = json.loads((root/'ten'/'manifest.json').read_bytes())
        assert ten['edge_margin_m'] == 10
        assert ten['waypoint_protocol'] == 'task024'

        # Docker is replaced by an argv recorder, so the launcher runs no simulator.
        docker = root/'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK036_ARGV"\n')
        docker.chmod(0o755)
        argv_path = root/'argv'
        launcher = cli.with_name('run_lidar_checks.sh')
        subprocess.run(['bash', str(launcher), str(root/'fake-run'), '--edge-margin-m', '10'],
                       check=True, env=dict(env, PATH=f'{root}:{env["PATH"]}', TASK036_ARGV=str(argv_path)))
        assert argv_path.read_bytes().split(b'\0')[-3:] == [b'--edge-margin-m', b'10', b'']

    archived = json.loads((BASELINE/'manifest.json').read_bytes())
    assert json.loads(default)['scenarios'] == archived['scenarios']
    expected = defaultdict(list)
    with (ROOT/'results/edge_margin/refresh/waypoints.csv').open(newline='') as handle:
        for row in csv.DictReader(handle):
            expected[row['patch']].append(json.loads(row['new_point']))
    unchanged = set()
    for old, new in zip(archived['scenarios'], ten['scenarios'], strict=True):
        name = new['patch']
        assert name == old['patch'] and new['start'] == old['start']
        assert new['points'] == expected[name]
        if new['points'] == old['points']:
            unchanged.add(name)
            assert new == old
        print(f'024 {name} start={new["start"]} points={new["points"]} unchanged={name in unchanged}')
    assert unchanged == UNCHANGED
    print('024 PASS: 10/10 archived waypoint lists, 5/5 unchanged scenarios, default manifest bytes and wrapper forwarding')


def synthetic_cloud(sensor):
    rng = np.random.default_rng(36)
    pose = np.array([100., 100., 0., 0., 0., 0.])
    mount = REAL_MOUNTS[sensor]
    if sensor == 'lidar':
        # 16 rings x 1800 azimuths. Spread the ground returns over the
        # useful ranges and add small range jitter within each ring.
        angle = np.tile(np.linspace(-np.pi, np.pi, 1800, endpoint=False), 16)
        distance = np.repeat(np.linspace(4.2, 22., 16), 1800) + rng.normal(0., .08, len(angle))
        x, y = distance*np.cos(angle), distance*np.sin(angle)
        z = .02*x + .01*y
        z[(x > 8.) & (x < 9.) & (abs(y) < .5)] += .4
        world = np.column_stack((x+pose[0], y+pose[1], z))
        return local_cloud(world, pose, mount), pose
    x, slope = np.meshgrid(np.linspace(1.5, 4.1, 125), np.linspace(-.8, .8, 214))
    y = x*slope
    z = np.full(x.shape, -mount.xyz[2])
    z[(x > 2.) & (x < 2.5) & (abs(y) < .25)] += .4
    return np.column_stack((x.ravel(), y.ravel(), z.ravel())), pose


def compare_updates(reference, original_mapper, label, sensor, points, pose, repeats=1):
    times = [[], []]
    differences = []
    accepted = []
    prior = np.zeros((401, 401))
    for _ in range(repeats):
        maps = [cls(prior, obstacle_reference='local') for cls in (original_mapper, PointCloudMapMulti)]
        for i, implementation in enumerate((reference, local_ground.update_local)):
            with patch.object(local_ground, 'update_local', implementation):
                result = maps[i].update(points, pose, sensor=sensor)
            times[i].append(result['update_s'])
            accepted.append(result['accepted_points'])
        differences.append(mask_differences(*maps))
        assert np.array_equal(maps[0].seen, maps[1].seen)
    assert len(set(differences)) == len(set(accepted)) == 1
    old, new = [np.percentile(values, (50, 95)) for values in times]
    print(f'{label} {sensor} {len(points)} {accepted[0]} {repeats} '
          f'{old[0]:.6f} {old[1]:.6f} {new[0]:.6f} {new[1]:.6f} '
          f'{differences[0][0]} {differences[0][1]}', flush=True)


def test_timings_and_replay(reference):
    original_mapper = baseline_module('pointcloud_map_multi').PointCloudMapMulti
    cpu = next(line.split(':', 1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
               if line.startswith('model name'))
    print('CPU', cpu, flush=True)
    print('fixture sensor input accepted repeats before_median_s before_p95_s after_median_s after_p95_s fine_diff coarse_diff',
          flush=True)
    for sensor in ('lidar', 'camera1'):
        compare_updates(reference, original_mapper, 'synthetic', sensor, *synthetic_cloud(sensor), repeats=12)
    raw = ROOT/'results/real_sensors/b0b/lidar_real_depth2/physical_1/raw/08OB86_-0205'
    for sensor, suffix in (('lidar', ''), ('camera1', '_camera1'), ('camera2', '_camera2')):
        with np.load(raw/f'first_cloud{suffix}.npz') as scan:
            compare_updates(reference, original_mapper, 'saved_b0b', sensor, scan['points'], scan['pose'])


if __name__ == '__main__':
    test_default_bytes()
    test_edge_margin()
    reference = baseline_module('local_ground').update_local
    test_task032(reference)
    test_timings_and_replay(reference)
    print('all local speed tests passed')
