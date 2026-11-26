"""Check task070 radii, plan-local endpoint exceptions and same-host default bytes."""

import argparse
import ast
import csv
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from results.distance_clearance import replay as boxes
from ros2_jazzy.gz_checks import (
    distance_runtime, endpoint_runtime, lidar_checks, lidar_map, lidar_runtime, overlap_goal, plan_maps, safety_runtime,
)
from tapp import pointcloud_map_fine, pointcloud_map_multi
from tapp.config import RESOLUTION
from tapp.pointcloud_map_fine import RATIO, PointCloudMapFine
from tapp.tracking_margin import TrackingClearance, distance_cost, radius_map
from tests import test_overlap_goal as fixtures
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission import online_runtime, online_safety

BASE = '9eee50fed7e2104fc189531d7d6f1db4cb832a7b'
START, GOAL = (6, 10), (12, 10)
SHAPE = (24, 24)


def test_default(root):
    modules = (pointcloud_map_fine, pointcloud_map_multi, plan_maps, overlap_goal, distance_runtime,
               online_runtime, online_safety, lidar_runtime, endpoint_runtime, safety_runtime, lidar_map, lidar_checks)
    with patch.object(fixtures, 'BASE', BASE):
        old = {module.__name__: prior for module, prior in zip(modules, fixtures.load_before(*modules))}
    for clearance in ({}, dict(obstacle_clearance='distance', steep_clearance='distance')):
        tag = str(bool(clearance))
        for module, name, multi in [(pointcloud_map_fine, 'PointCloudMapFine', False),
                                    (pointcloud_map_multi, 'PointCloudMapMulti', True)]:
            old_cls, cls = (getattr(source, name) for source in (old[module.__name__], module))
            z = np.zeros(SHAPE)
            before = map_bytes(root/f'{tag}-{multi}-before', old_cls(z, **clearance), multi)
            assert before == map_bytes(root/f'{tag}-{multi}-after', cls(z, **clearance), multi)
            assert before == map_bytes(root/f'{tag}-{multi}-none', cls(z, **clearance, tracking_margin='none'), multi)
        options = dict(map_method='fine', diagnostics=True, save_plan_maps=True, online_fixes='v2', **clearance)
        expected = capture_launch(old[lidar_checks.__name__], root/f'{tag}-launch-before', **options)
        assert expected == capture_launch(lidar_checks, root/f'{tag}-launch-after', **options)
        assert expected == capture_launch(lidar_checks, root/f'{tag}-launch-none', tracking_margin='none', **options)
        with patch.dict(sys.modules, {distance_runtime.__name__: old[distance_runtime.__name__]}):
            expected_run = fixtures.runtime_bytes(root/f'{tag}-rt-before',
                old[pointcloud_map_fine.__name__].PointCloudMapFine, old[safety_runtime.__name__].make_safety_lidar_runtime,
                'v2', clearance)
        assert expected_run == fixtures.runtime_bytes(root/f'{tag}-rt-none', PointCloudMapFine,
            safety_runtime.make_safety_lidar_runtime, 'v2', dict(clearance, tracking_margin='none'))
    print('1 PASS: default and explicit none match the pre-change map, manifest, ROS commands and plan bytes')


def test_radii_and_costs():
    distances = np.array([.499, .5, .7739, .774, 1., 1.5, np.inf])
    grid = np.repeat(distances[None, :], 3, axis=0)
    fixed = TrackingClearance('fixed', np.zeros_like(grid), {'obstacle': grid})
    blocked, mult, labels, _, _ = fixed.project(np.zeros_like(grid, bool), np.ones_like(grid),
                                               None, None, 1.)
    np.testing.assert_array_equal(blocked[0], [True, True, True, False, False, False, False])
    assert labels == '' and mult[0, 3] == 2. and mult[0, 5] == 1.
    assert np.isclose(mult[0, 4]-1., ((1.5-1.)/(1.5-.774))**2)
    np.testing.assert_array_equal(distance_cost(np.array([.5, 1.5]), .5), [1., 0.])
    print('2 PASS: fixed band .5–.774 m; cost 1 at .774 m and 0 at 1.5 m')

    np.testing.assert_array_equal(radius_map('slope', np.array([[9., 10., 11., 35.]])),
                                  [[.774, 1.114, 1.114, 1.114]])
    elevation = np.broadcast_to(np.arange(SHAPE[0])[:, None]*RESOLUTION*np.tan(np.deg2rad(11.)), SHAPE).copy()
    mapper = PointCloudMapFine(elevation, terrain_source='prior', steep_clearance='distance', tracking_margin='slope')
    np.testing.assert_array_equal(mapper.tracking_clearance_snapshot().radius, 1.114)
    print('3 PASS: slope radius .774 m below 10°, 1.114 m from 10° upward; mapper planning slope used')


def add_evidence(mapper, endpoints, offset):
    fine = mapper.fine_obstacle.copy()
    for x, y in endpoints:
        fine[x*RATIO+RATIO//2, y*RATIO+RATIO//2+offset] = True
    # Only add new cells to the incremental field.
    boxes.install_mask(mapper, fine & ~mapper.fine_obstacle)
    mapper.version += 1


def margin_mapper():
    mapper = PointCloudMapFine(np.zeros(SHAPE), obstacle_clearance='distance', tracking_margin='fixed')
    mapper.seen[:] = True
    return mapper


def test_endpoints(root):
    mapper = margin_mapper()
    add_evidence(mapper, [START, GOAL], offset=6)  # Each endpoint is .55 m from a detected square.
    runtime = fixtures.make_runtime(root/'endpoints', mapper, online_fixes='v2', diagnostics=True, save_plan_maps=True)
    try:
        command = fixtures.start_leg(runtime, START, GOAL)
        assert command['revision'] == 1
        assert command['plan_history'][0]['tracking_margin_relaxed'] == 'start|goal'
        plans = list(csv.DictReader(runtime.plan_log.path.open()))
        assert plans[0]['tracking_margin_relaxed'] == 'start|goal'
        plan = dict(plan_maps.read_plans(runtime.plan_maps.folder))[1]
        assert str(plan['tracking_margin_relaxed']) == 'start|goal'
        assert str(plan['tracking_margin_relaxed_layers']) == 'obstacle'
        np.testing.assert_array_equal(plan['tracking_hard_radius_m'], np.full(SHAPE, .774))
        assert not plan['lethal'][START] and not plan['lethal'][GOAL]
        assert np.isclose(plan['obstacle_cost'][START], .95**2)
        assert not mapper.lethal[START] and not mapper.lethal[GOAL]
        clearance = mapper.tracking_clearance_snapshot()
        assert clearance.protected(())[START] and clearance.protected(())[GOAL]
        follower_log = SimpleNamespace(folder=root/'follower', mission={}, _save=lambda: None)
        follower_log.folder.mkdir()
        online_runtime.record_plan_history(follower_log, command)
    finally:
        runtime.close()

    # Entering one layer's added band cannot unblock the other layer along the route.
    distance = np.full((5, 5), np.inf)
    other = distance.copy()
    distance[1, 1], other[2, 2], other[3, 3] = .60, .60, .49
    clearance = TrackingClearance('fixed', np.zeros_like(distance), {'obstacle': distance, 'steep': other})
    blocked, mult, role, layers, _ = clearance.project(np.zeros_like(distance, bool), np.ones_like(distance),
                                                     (1, 1), (4, 4), 1.)
    assert role == 'start' and layers == {'obstacle'}
    assert not blocked[1, 1] and np.isclose(mult[1, 1], 1.+.9**2)
    assert blocked[2, 2] and blocked[3, 3]

    for name, endpoint in [('start', START), ('goal', GOAL)]:
        close = margin_mapper()
        add_evidence(close, [endpoint], offset=5)
        runtime = fixtures.make_runtime(root/f'blocked-{name}', close, online_fixes='v2')
        try:
            command = fixtures.start_leg(runtime, START, GOAL)
            assert command['online_error'] == 'start_leg'
            event = command['plan_history'][0]
            assert not event['success'] and event['tracking_margin_relaxed'] == ''
        finally:
            runtime.close()

    for fixes in ('none', 'v2'):
        close = margin_mapper()
        add_evidence(close, [START], offset=6)
        runtime = fixtures.make_runtime(root/f'delayed-{fixes}', close, online_fixes=fixes)
        try:
            runtime.start(dict(fixtures.SCENARIO, start_cells=list(START), stops_cells=[list(GOAL)]))
            position = np.asarray(START)*RESOLUTION
            assert runtime.tick(position, 1.) is None
            add_evidence(close, [START], offset=5)
            assert runtime.tick(position, 2.) is None and runtime.sent == 0
        finally:
            runtime.close()
    mapper = margin_mapper()
    runtime = fixtures.make_runtime(root/'blocked-during-leg', mapper, online_fixes='v2')
    try:
        assert fixtures.start_leg(runtime, START, GOAL)['revision'] == 1
        position = np.asarray(START)*RESOLUTION
        add_evidence(mapper, [(9, 10)], offset=6)
        assert not mapper.lethal[9, 10]
        assert runtime.tick(position, 3.) is None
        replanned = runtime.tick(position, 4.)
        assert replanned['revision'] == 2 and replanned['reason'] == 'tracking_margin_blocked'
    finally:
        runtime.close()
    print('4 PASS: start and goal exceptions recorded, hard band restored between plans, <0.5 m and stale handoff rejected')


def test_wiring(root):
    options = dict(map_method='fine', obstacle_clearance='distance', steep_clearance='distance',
                   tracking_margin='slope', save_plan_maps=True)
    result, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    manifest = json.loads(result)
    assert manifest['tracking_margin'] == 'slope'
    assert manifest['tracking_margin_settings']['distance_layers'] == ['obstacle', 'steep']
    assert manifest['tracking_margin_settings']['high_slope_hard_m'] == 1.114
    assert {'tracking_margin:=slope', 'obstacle_clearance:=distance', 'steep_clearance:=distance',
            'save_plan_maps:=true'} <= set(commands[-1])
    for settings, message in (({}, 'requires --obstacle-clearance distance or --steep-clearance distance'),
                              (dict(obstacle_clearance='distance', clearance_soft_m=1.6), 'fixes --clearance-soft-m at 1.5')):
        folder = root/'invalid'
        for configure in (lambda: lidar_checks.prepare_cases(folder, map_method='fine', tracking_margin='fixed', **settings),
                          lambda: lidar_map.make_pointcloud_map(np.zeros(SHAPE), map_method='fine',
                                                               tracking_margin='fixed', **settings)):
            try:
                configure()
            except ValueError as exc:
                assert message in str(exc)
            else:
                raise AssertionError('invalid settings accepted')
            assert not folder.exists()
    for settings in (dict(steep_clearance='distance'), dict(obstacle_clearance='distance')):
        assert lidar_map.make_pointcloud_map(np.zeros(SHAPE), map_method='fine',
                                             tracking_margin='fixed', **settings).tracking_margin == 'fixed'

    path = lidar_checks.ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    main = next(node for node in ast.parse(path.read_text()).body if isinstance(node, ast.FunctionDef) and node.name == 'main')
    calls = []
    stub = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kw: calls.append(kw), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kw: (calls.append(kw) or stub))
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'), scope)
    scope['main'](['--tracking-margin', 'fixed', '--ros-args', '-p', 'map_method:=fine'])
    assert calls == [dict(args=['--ros-args', '-p', 'map_method:=fine']), dict(tracking_margin='fixed')]

    fake = root/'docker'
    fake.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    fake.chmod(0o755)
    flags = ['--map', 'fine', '--steep-clearance', 'distance', '--tracking-margin', 'fixed']
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu')
    output = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapped'), *flags], env=env)
    assert output.split(b'\0')[-len(flags)-1:-1] == list(map(os.fsencode, flags))
    print('5 PASS: start-up validation, one or both distance layers, manifest, ROS CLI and shell forwarding')


if __name__ == '__main__':
    with TemporaryDirectory() as folder:
        root = Path(folder)
        test_default(root)
        test_radii_and_costs()
        test_endpoints(root)
        test_wiring(root)
    print('all task070 tracking margin tests passed')
