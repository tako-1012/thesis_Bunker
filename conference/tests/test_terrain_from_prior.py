"""Task047 same-host default bytes, fixed planning terrain, and archived replay."""

import argparse
from contextlib import redirect_stdout
import ast
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from results.terrain_from_prior import replay
from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from tapp import pointcloud_map, pointcloud_map_fine, pointcloud_map_multi
from tapp.online_mission import OnlinePlanner
from tapp.online_safety import make_follower
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tests.test_ground_estimate import BOX_CELL, box_world, update_world
from tests.test_real_sensors import local_cloud
from tests.test_rtf_option import LAUNCHER
from tests.test_waypoint_feasibility import capture_launch

ROOT = lidar_checks.ROOT
BASE = 'd0ff2afa003cf757c52c82c9b48752dc373e3d28'


def before_module(module):
    file = Path(module.__file__)
    source = subprocess.check_output(['git', 'show', f'{BASE}:{file.relative_to(ROOT.parent)}'],
                                     cwd=ROOT.parent)
    old = ModuleType(module.__name__)
    old.__file__, old.__package__ = str(file), module.__package__
    exec(compile(source, str(file), 'exec'), vars(old))
    return old


def map_bytes(root, mapper, multi=False):
    root.mkdir()
    with patch('time.perf_counter', return_value=1.):
        if multi:
            pose = np.array([2., 5., 0., 0., 0., 0.])
            updates = [mapper.update(local_cloud(box_world(), pose, mount), pose, sensor=name, stamp=float(i))
                       for i, (name, mount) in enumerate(mapper.mounts.items(), 1)]
        else:
            updates = [update_world(mapper, points) for points in (
                box_world(), [[5., 5., .1]]*7+[[5., 5., .55]]*70, [[8., 5., -.1]], np.empty((0, 3)))]
    mapper.save(root/'map.npz')
    logs = {path.name: path.read_bytes() for path in root.iterdir()}
    arrays = tuple(v.tobytes() for v in (*mapper.planning_snapshot(), mapper.elev, mapper.tm.slope, mapper.tm.rough))
    return json.dumps(updates).encode(), logs, arrays


def test_default_bytes(root):
    old_base = before_module(pointcloud_map)
    with patch.dict(sys.modules, {pointcloud_map.__name__: old_base}):
        old_fine = before_module(pointcloud_map_fine)
    with patch.dict(sys.modules, {pointcloud_map_fine.__name__: old_fine}):
        old_multi = before_module(pointcloud_map_multi)
    z = np.zeros((32, 32))
    for previous, current, multi in ((old_fine.PointCloudMapFine, PointCloudMapFine, False),
                                     (old_multi.PointCloudMapMulti, PointCloudMapMulti, True)):
        expected = map_bytes(root/f'map-{multi}-before', previous(z), multi)
        assert expected == map_bytes(root/f'map-{multi}-after', current(z), multi)
        assert expected == map_bytes(root/f'map-{multi}-explicit', current(z, terrain_source='sensor'), multi)
    old_checks = before_module(lidar_checks)
    for mode in ('none', 'v1', 'v2'):
        kwargs = dict(map_method='fine', online_fixes=mode, obstacle_clearance='centre', tracking='default')
        expected = capture_launch(old_checks, root/f'{mode}-before', **kwargs)
        assert expected == capture_launch(lidar_checks, root/f'{mode}-after', **kwargs)
        assert expected == capture_launch(lidar_checks, root/f'{mode}-explicit', terrain_source='sensor', **kwargs)
    print('1 PASS: same-host before/after NPZ, update results, multi-sensor sidecars, snapshots and none/v1/v2 dispatch bytes')


def test_false_slope_and_obstacles(root):
    z = np.zeros((32, 32))
    goal = (12, 10)  # two coarse cells from the box, outside its obstacle halo
    for clearance in ('centre', 'overlap'):
        old = PointCloudMapFine(z, obstacle_clearance=clearance)
        fixed = PointCloudMapFine(z, obstacle_clearance=clearance, terrain_source='prior')
        update_world(old, box_world())
        with patch.object(fixed, '_update_roughness', side_effect=AssertionError('prior recomputed roughness')), \
                patch.object(pointcloud_map_fine, 'inflate', side_effect=AssertionError('prior reinflated slopes')):
            update_world(fixed, box_world())
        assert old.lethal[goal] and old._dilated_steep[goal] and not old._inflated_coarse[goal]
        assert not fixed.lethal[goal] and fixed.lethal[BOX_CELL]
        assert old.elev.tobytes() == fixed.elev.tobytes() and np.isclose(fixed.elev[BOX_CELL], .55)
        assert np.array_equal(fixed.tm.elev, z) and not fixed.tm.cost.any() and old.tm.cost.any()
    fixed.save(root/'prior.npz')
    with np.load(root/'prior.npz', allow_pickle=False) as arrays:
        assert arrays['elev'][BOX_CELL] == fixed.elev[BOX_CELL] and not arrays['terrain_steep'].any()
    print('2 PASS: apparent steepness blocks the goal only with sensor terrain, with the same sensor elevation and box evidence')

    z[18:] = .7
    true_steep = (18, 14)
    pose = np.array([2., 5., 0., 0., 0., 0.])
    xy = np.arange(3.5, 6.6, .2)
    ground = [[x, y, 0.] for x in xy for y in xy]
    world = np.asarray(ground+[[5., 5., .55]]*3)
    for cls in (PointCloudMapFine, PointCloudMapMulti):
        for obstacle_ref in ('prior', 'local'):
            options = dict(obstacle_reference=obstacle_ref, obstacle_clearance='overlap')
            old, fixed = (cls(z, terrain_source=source, **options) for source in ('sensor', 'prior'))
            for mapper in (old, fixed):
                if cls is PointCloudMapMulti:
                    mapper.update(local_cloud(world, pose, mapper.mounts['lidar']), pose)
                else:
                    update_world(mapper, world)
            assert fixed.detected_obstacle[BOX_CELL] and fixed.lethal[BOX_CELL]
            assert old.fine_inflated.tobytes() == fixed.fine_inflated.tobytes()
            assert fixed.tm.steep[true_steep] and fixed.lethal[true_steep] and not fixed.seen[true_steep]
            planner = OnlinePlanner(fixed.tm.cost, fixed.lethal, fixed.weights)
            planner.observe(*fixed.planning_snapshot())
            assert planner.planning_maps()[0][true_steep]
    for mode in ('v1', 'v2'):
        follower = make_follower([[0., 0.], [3., 0.]], online_fixes=mode)
        assert follower.step(1., [0., 0., 0., np.deg2rad(26.), 0., 0.]) == (0., 0., True)
        assert follower.status == 'unsafe_tilt'
    print('3 PASS: Fine/Multi × prior/local with overlap retains box and unobserved true steep hazards; v1/v2 tilt stop intact')


def test_wiring(root):
    manifest, _, _, commands = capture_launch(lidar_checks, root/'prior-run', map_method='fine',
                                              terrain_source='prior', obstacle_reference='local',
                                              obstacle_clearance='overlap', online_fixes='v2', tracking='corner_slow')
    assert json.loads(manifest)['terrain_source'] == 'prior'
    assert 'terrain_source:=prior' in commands[-1] and 'terrain_source:=prior' not in commands[-2]
    assert {'online_fixes:=v2', 'obstacle_reference:=local', 'obstacle_clearance:=overlap'} <= set(commands[-1])
    assert 'tracking:=corner_slow' in commands[-2]
    assert make_pointcloud_map(np.zeros((10, 10)), map_method='fine', sensors='lidar_real',
                               terrain_source='prior').terrain_source == 'prior'
    for invalid in ('bad', 'prior'):
        try:
            make_pointcloud_map(np.zeros((10, 10)), terrain_source=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(f'accepted coarse terrain source {invalid}')
    source = ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    code = next(n for n in ast.parse(source.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = []
    stub = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kw: calls.append(kw), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kw: (calls.append(kw) or stub))
    exec(compile(ast.Module(body=[code], type_ignores=[]), str(source), 'exec'), scope)
    scope['main'](['--terrain-source', 'prior', '--ros-args', '-p', 'map_method:=fine'])
    assert calls == [dict(args=['--ros-args', '-p', 'map_method:=fine']), dict(terrain_source='prior')]
    fake = root/'docker'
    fake.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    fake.chmod(0o755)
    passed = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapper'), '--map', 'fine',
                                      '--terrain-source', 'prior'], env=dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}'))
    assert passed.split(b'\0')[-5:] == [b'--map', b'fine', b'--terrain-source', b'prior', b'']
    print('configuration PASS: manifest, production command, direct planner CLI, real-sensor factory and fake Docker')


def test_replay(root):
    with redirect_stdout(io.StringIO()) as output:
        replay.main(root/'replay')
    rows = replay.read_csv(root/'replay/runs.csv')
    assert len(rows) == 35
    groups = {source: [r for r in rows if r['map_source'] == source]
              for source in ('final', 'failure_snapshot', 'missing')}
    assert [len(rows) for rows in groups.values()] == [14, 6, 15]
    assert sum(r['recovered'] == 'True' for r in groups['final']) == 9
    assert sum(r['recovered'] == 'True' for r in groups['failure_snapshot']) == 3
    assert all(r['prior_route'] == '' and r['reason'] for r in groups['missing'])
    assert len(replay.read_csv(root/'replay/goals.csv')) == 5
    assert 'map_errors' in output.getvalue()
    print('4 PASS: all 35 failures classified; 9/14 recovered on final maps, 3/6 on failure snapshots, 15 without either')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        test_default_bytes(root)
        test_false_slope_and_obstacles(root)
        test_wiring(root)
        test_replay(root)
    print('all task047 terrain-source tests passed')
