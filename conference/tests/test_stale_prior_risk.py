"""Task048 compatibility, support threshold, existing hazards and CLI wiring."""

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from tapp import pointcloud_map_fine, pointcloud_map_multi
from tapp.online_mission import OnlinePlanner
from tapp.pointcloud_map_fine import PointCloudMapFine, TERRAIN_SOURCES
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tests.test_rtf_option import LAUNCHER
from tests.test_real_sensors import local_cloud
from tests.test_terrain_from_prior import map_bytes, update_world
from tests.test_waypoint_feasibility import capture_launch

ROOT = lidar_checks.ROOT
BASE = '247c465328435c53df6d131cff51568901877047'


def before_module(module):
    file = Path(module.__file__)
    code = subprocess.check_output(['git', 'show', f'{BASE}:{file.relative_to(ROOT.parent)}'], cwd=ROOT.parent)
    old = ModuleType(module.__name__)
    old.__file__, old.__package__ = str(file), module.__package__
    exec(compile(code, str(file), 'exec'), vars(old))
    return old


def test_bytes(root):
    old_fine = before_module(pointcloud_map_fine)
    with patch.dict(sys.modules, {pointcloud_map_fine.__name__: old_fine}):
        old_multi = before_module(pointcloud_map_multi)
    for before, after, multi in ((old_fine.PointCloudMapFine, PointCloudMapFine, False),
                                 (old_multi.PointCloudMapMulti, PointCloudMapMulti, True)):
        for source in ('sensor', 'prior'):
            z = np.zeros((32, 32))
            z[22:] = .8
            options = {} if source == 'sensor' else dict(terrain_source=source)
            name = f'{multi}-{source}'
            expected = map_bytes(root/f'{name}-before', before(z, **options), multi)
            assert map_bytes(root/f'{name}-after', after(z, **options), multi) == expected
            if source == 'sensor':
                assert map_bytes(root/f'{name}-explicit', after(z, terrain_source=source), multi) == expected

    old_checks = before_module(lidar_checks)
    for mode in ('sensor', 'prior'):
        for fixes in ('none', 'v2'):
            kw = dict(map_method='fine', terrain_source=mode, online_fixes=fixes)
            name = f'run-{mode}-{fixes}'
            old = capture_launch(old_checks, root/f'{name}-before', **kw)
            assert capture_launch(lidar_checks, root/f'{name}-after', **kw) == old
    print('1 PASS: sensor and prior NPZ, snapshot, multi-sensor sidecar and mocked runner bytes match same-host base')


def blocked_for_planner(mapper):
    planner = OnlinePlanner(mapper.tm.cost, mapper.lethal, mapper.weights)
    planner.observe(*mapper.planning_snapshot())
    return planner.planning_maps()[0]


def test_support(root):
    base = np.zeros((32, 32))
    cell, neighbour = (10, 10), (9, 10)
    for cap in (63, 64):
        old, veto = (PointCloudMapFine(base, terrain_source=mode, samples_per_cell=cap)
                     for mode in ('prior', 'prior_veto'))
        world = [[5., 5., 0.]]*31+[[5.5, 5., -.8]]
        for mapper in (old, veto):
            update_world(mapper, world)
        assert not veto._veto_supported[cell] and not veto.tm.steep[cell]
        assert np.array_equal(blocked_for_planner(veto), blocked_for_planner(old))
        assert veto.elev[10, 10] == 0.
        # Repeating the same elevation changes only the retained sample count.
        for mapper in (old, veto):
            update_world(mapper, [[5., 5., 0.]])
        assert veto._veto_supported[cell] and veto.tm.steep[cell] and not old.tm.steep[cell]
        blocked = blocked_for_planner(veto)
        assert blocked[cell] and blocked[neighbour] and not veto.seen[neighbour]
        assert np.array_equal(veto.tm.cost, old.tm.cost)
        veto.save(root/f'veto-{cap}.npz')
        with np.load(root/f'veto-{cap}.npz', allow_pickle=False) as data:
            assert data['veto_supported'][cell] and data['terrain_steep'][cell]
        # New sensor heights may clear the veto as the retained history fills.
        update_world(veto, [[5.5, 5., 0.]]*cap)
        assert not veto.tm.steep[cell] and not blocked_for_planner(veto)[cell]
    print('2 PASS: cutoff at 32 of 63/64; unchanged height crossing triggers veto, 0.5m halo, subsequent clearing')


def test_prior_steep():
    base = np.zeros((32, 32))
    base[12:] = .8
    for mode in TERRAIN_SOURCES:
        mapper = PointCloudMapFine(base, terrain_source=mode)
        # Register the same true shape so the legacy sensor height fusion also retains the slope.
        update_world(mapper, [[5.5, 5., 0.]]*32+[[6., 5., .8]]*32)
        assert mapper.tm.steep[11, 10] and blocked_for_planner(mapper)[11, 10]
        if mode != 'sensor':
            # An unobserved prior steep cell remains barred in both prior modes.
            assert not mapper.seen[12, 20] and blocked_for_planner(mapper)[12, 20]
    print('3 PASS: unchanged real prior slopes in all three modes; both prior modes also forbid unobserved steep cells')


def test_wiring(root):
    manifest, _, _, commands = capture_launch(lidar_checks, root/'veto-run', map_method='fine',
                                              terrain_source='prior_veto', online_fixes='v2')
    config = json.loads(manifest)
    assert config['terrain_source'] == 'prior_veto' and 'ceil' in config['terrain_veto_support']
    assert 'terrain_source:=prior_veto' in commands[-1] and 'terrain_source:=prior_veto' not in commands[-2]
    mapper = make_pointcloud_map(np.zeros((10, 10)), map_method='fine', sensors='lidar_real',
                                 terrain_source='prior_veto', obstacle_reference='local', obstacle_clearance='overlap')
    assert isinstance(mapper, PointCloudMapMulti) and mapper.terrain_source == 'prior_veto'
    pose = np.array([.5, 2., 0., 0., 0., 0.])
    ground = [[2., 2., 0.]]*32 + [[x, y, 0.] for x in (1.5, 2.5) for y in (1.5, 2.5)]
    mapper.update(local_cloud(ground, pose, mapper.mounts['lidar']), pose)
    assert mapper._veto_supported[4, 4] and not mapper.tm.steep[4, 4]
    try:
        make_pointcloud_map(np.zeros((10, 10)), terrain_source='prior_veto')
    except ValueError as exc:
        assert 'fine' in str(exc)
    else:
        raise AssertionError('accepted prior_veto in the coarse mapper')
    planner = ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    main = next(n for n in ast.parse(planner.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = []
    stub = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kw: calls.append(kw), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kw: (calls.append(kw) or stub))
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(planner), 'exec'), scope)
    scope['main'](['--terrain-source', 'prior_veto', '--ros-args', '-p', 'map_method:=fine'])
    assert calls == [dict(args=['--ros-args', '-p', 'map_method:=fine']), dict(terrain_source='prior_veto')]
    fake = root/'docker'
    fake.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    fake.chmod(0o755)
    argv = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapper'),
                                    '--map', 'fine', '--terrain-source', 'prior_veto'],
                                   env=dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}'))
    assert argv.split(b'\0')[-3:] == [b'--terrain-source', b'prior_veto', b'']
    print('configuration PASS: manifest, ROS argument, planner CLI, Multi local/overlap, fine-only validation and fake Docker')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        test_bytes(root)
        test_support(root)
        test_prior_steep()
        test_wiring(root)
    print('all task048 stale-prior-risk tests passed')
