"""Same-host compatibility, strict replacement and ROS-free goal-region wiring."""

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

from results.distance_clearance.replay import install_mask
from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, lidar_runtime, safety_runtime
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.goal_region import choose_goal
from tapp.pointcloud_map_fine import PointCloudMapFine, RATIO
from tapp.traversability import inflate
from tests import test_overlap_goal as fixtures
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_waypoint_feasibility import capture_launch

BASE = 'ee501a7503074b840f95ccae516b23879ac85fdf'
ORIGINAL = (10, 10)
START = (4, 10)


def test_default_bytes(root):
    with patch.object(fixtures, 'BASE', BASE):
        _, _, old_safety, old_checks = fixtures.load_before(
            lidar_runtime, endpoint_runtime, safety_runtime, lidar_checks)
    assert capture_launch(old_checks, root/'old-default', map_method='fine') == capture_launch(
        lidar_checks, root/'new-default', map_method='fine', goal_region='none')
    ordinary = []
    for label, factory in [('old', old_safety.make_safety_lidar_runtime),
                           ('new', safety_runtime.make_safety_lidar_runtime)]:
        mapper = PointCloudMapFine(np.zeros((24, 24)))
        mapper.seen[:] = True
        runtime = fixtures.make_runtime(root/label, mapper, factory=factory)
        try:
            with patch('time.perf_counter', return_value=5.):
                command = fixtures.start_leg(runtime, START, ORIGINAL)
            ordinary.append((json.dumps(command), (runtime.plan_log.path).read_bytes()))
        finally:
            runtime.close()
        assert sorted(p.name for p in (root/label).iterdir()) == ['plans.csv']
    assert ordinary[0] == ordinary[1]
    for fixes, mode in [('none', 'centre'), ('v1', 'overlap_goal'), ('v2', 'distance')]:
        options = dict(map_method='fine', diagnostics=True, save_plan_maps=True,
                       online_fixes=fixes, obstacle_clearance=mode)
        assert capture_launch(old_checks, root/f'old-launch-{fixes}', **options) == capture_launch(
            lidar_checks, root/f'new-launch-{fixes}', goal_region='none', **options)
        args = (PointCloudMapFine, old_safety.make_safety_lidar_runtime, fixes, dict(obstacle_clearance=mode))
        old = fixtures.runtime_bytes(root/f'old-runtime-{fixes}', *args)
        now = fixtures.runtime_bytes(root/f'new-runtime-{fixes}', args[0],
                                     safety_runtime.make_safety_lidar_runtime, *args[2:])
        assert old == now
        assert all(path.name != 'goal_region.csv' for path in now[1])
    print('1 PASS: same-host pre-change versus none manifest, ROS dispatch, command and runtime log bytes')


def test_selection():
    blocked = np.ones((14, 14), bool)
    blocked[2:9, 6:8] = False
    blocked[9, 6] = False
    blocked[10, 7] = False  # Closer and free, but isolated from the start.
    original = (10, 6)
    cost, seen, steep = np.ones(blocked.shape), np.zeros_like(blocked), np.zeros_like(blocked)
    seen[8, 6] = seen[9, 6] = seen[10, 7] = True
    steep[9, 6] = True
    chosen, _ = choose_goal((2, 6), original, blocked, cost, seen, steep)
    assert chosen == (8, 6)  # Exactly one metre, nearer cell is in the steep halo.
    seen[8, 6] = False
    assert choose_goal((2, 6), original, blocked, cost, seen, steep) is None
    assert choose_goal(original, original, blocked, cost, seen, np.zeros_like(steep)) is None

    blocked[:] = False
    blocked[original] = True
    seen[:] = False
    steep[:] = False
    near, cheaper = (9, 6), (10, 7)
    seen[near] = seen[cheaper] = True
    cost[near] = 100.
    selected, _ = choose_goal((2, 6), original, blocked, cost, seen, steep)
    assert selected == cheaper  # Equal shift and a cheaper weighted route.
    print('selection PASS: nearest feasible ring, strict visibility/steep filters, blocked start and cost tie')


def box_mapper(mode, terrain):
    mapper = PointCloudMapFine(np.zeros((24, 24)), obstacle_clearance=mode, terrain_source=terrain)
    mapper.seen[:] = True
    fine = np.zeros(mapper.fine_shape, bool)
    fine[tuple(np.asarray(ORIGINAL)*RATIO+RATIO//2)] = True
    install_mask(mapper, fine)
    return mapper


def test_box_and_no_path(root):
    for mode, terrain, fixes in [('centre', 'sensor', 'none'), ('overlap_goal', 'prior', 'v1'),
                                 ('distance', 'prior_veto', 'v2')]:
        mapper = box_mapper(mode, terrain)
        before = mapper.lethal.tobytes()
        runtime = fixtures.make_runtime(root/mode, mapper, goal_region='ring', online_fixes=fixes, save_plan_maps=True)
        try:
            command = fixtures.start_leg(runtime, START, ORIGINAL)
            assert command['revision'] == 1
            goal = tuple(np.rint(np.asarray(command['path'][-1])/RESOLUTION).astype(int))
            blocked = mapper.lethal
            assert blocked[ORIGINAL] and not blocked[goal] and goal != ORIGINAL and mapper.seen[goal]
            assert np.linalg.norm(np.subtract(goal, ORIGINAL))*RESOLUTION <= 1.
            assert not len(path_lethal_cells(np.asarray(command['path'])/RESOLUTION, blocked))
            assert blocked.tobytes() == before
            record = dict(read_plans(runtime.plan_maps.folder))[1]
            assert record['lethal'].tobytes() == before
            assert record['original_goal'].tolist() == list(ORIGINAL) and record['goal'].tolist() == list(goal)
            with np.load(runtime.plan_maps.folder/'applied_000001.npz', allow_pickle=False) as applied:
                assert applied['revision'] == 1
            assert not command['final_leg']
            arrival = command['path'][-1]
            runtime.tick(arrival, 3.)
            completion = runtime.tick(arrival, 4.)
            assert completion['endpoint_finished'] and completion['endpoint_outcomes'][0]['outcome'] == 'nearby'
        finally:
            runtime.close()

    mapper = box_mapper('centre', 'sensor')
    mapper.seen[:] = False
    mapper.seen[ORIGINAL] = True
    runtime = fixtures.make_runtime(root/'missing', mapper, goal_region='ring', diagnostics=True)
    try:
        command = fixtures.start_leg(runtime, START, ORIGINAL)
        assert command['online_error'] == 'start_leg'
        assert 'goal_cell' in (runtime.folder/'plans.csv').read_text()
        assert not list(csv.DictReader(runtime.goal_log.path.open()))
    finally:
        runtime.close()

    mapper = PointCloudMapFine(np.zeros((24, 24)), obstacle_clearance='overlap_goal',
                               ground_estimate='non_obstacle')
    mapper.seen[:] = True
    fixtures.add_scan(mapper, fixtures.GROUND+[fixtures.BOX]*3)
    target = fixtures.GOAL_NEAR_BOX
    assert mapper.lethal[target]
    runtime = fixtures.make_runtime(root/'centre-exception', mapper, goal_region='ring')
    try:
        command = fixtures.start_leg(runtime, fixtures.START, target)
        assert command['path'][-1] == (np.asarray(target)*RESOLUTION).tolist()
        assert mapper.lethal[target] and not list(csv.DictReader(runtime.goal_log.path.open()))
    finally:
        runtime.close()
    print('2 PASS: box halo unmodified; centre/overlap_goal/distance, v1/v2, plan snapshots and no reachable candidate')


def set_steep(mapper, cell=None):
    mapper.tm.steep.fill(False)
    if cell is not None:
        mapper.tm.steep[cell] = True
    mapper._dilated_steep = inflate(mapper.tm.steep, mapper.robot.footprint_radius)
    mapper.lethal = mapper.tm.rock | mapper._dilated_steep
    mapper.version += 1


def test_restore_and_stale_handoff(root):
    mapper = PointCloudMapFine(np.zeros((24, 24)))
    mapper.seen[:] = True
    set_steep(mapper, ORIGINAL)
    runtime = fixtures.make_runtime(root/'restore', mapper, goal_region='ring', online_fixes='v2')
    try:
        first = fixtures.start_leg(runtime, START, ORIGINAL)
        alt = first['path'][-1]
        assert alt != (np.asarray(ORIGINAL)*RESOLUTION).tolist()
        assert not mapper._dilated_steep[tuple(np.rint(np.asarray(alt)/RESOLUTION).astype(int))]
        set_steep(mapper)
        runtime.tick(alt, 3.)
        restored = runtime.tick(alt, 4.)
        assert restored['path'][-1] == (np.asarray(ORIGINAL)*RESOLUTION).tolist()
        assert restored['reason'] == 'goal_region_restore' and restored['final_leg'] and not runtime.finished
        original_m = restored['path'][-1]
        runtime.tick(original_m, 5.)
        assert runtime.tick(original_m, 6.) is None and runtime.finished
        events = list(csv.DictReader(runtime.goal_log.path.open()))
        assert [row['event'] for row in events] == ['substitute', 'restore']
        assert 'steep_halo' in events[0]['reason'] and events[1]['shift_m'] == '0.0'
    finally:
        runtime.close()

    mapper = box_mapper('centre', 'sensor')
    runtime = fixtures.make_runtime(root/'blocked-handoff-start', mapper, goal_region='ring', online_fixes='v2')
    try:
        runtime.start(dict(fixtures.SCENARIO, stops_cells=[list(ORIGINAL)]))
        position = np.asarray(START)*RESOLUTION
        assert runtime.tick(position, 1.) is None
        mapper.lethal[START] = True
        assert runtime.tick(position, 2.) is None
        assert runtime.sent == 0 and mapper.lethal[START]
    finally:
        runtime.close()

    mapper = PointCloudMapFine(np.zeros((24, 24)))
    mapper.seen[:] = True
    set_steep(mapper, ORIGINAL)
    runtime = fixtures.make_runtime(root/'delayed', mapper, goal_region='ring', online_fixes='v2')
    try:
        runtime.start(dict(fixtures.SCENARIO, stops_cells=[list(ORIGINAL)]))
        position = np.asarray(START)*RESOLUTION
        runtime.tick(position, 1.)
        set_steep(mapper)  # Pending replacement was made against a blocked original.
        assert runtime.tick(position, 2.) is None
        assert runtime.sent == 0
        assert [event['event'] for event in runtime.safety_events] == ['join_rejected']
        assert runtime.tick(position, 3.)['path'][-1] == (np.asarray(ORIGINAL)*RESOLUTION).tolist()
        assert not list(csv.DictReader(runtime.goal_log.path.open()))
    finally:
        runtime.close()
    print('3 PASS: steep halo, restore before arrival, stale substitution rejected by the preserved safety handoff')


def test_configuration(root):
    options = dict(map_method='fine', goal_region='ring', pose_trace=True, save_plan_maps=True,
                   terrain_source='prior', obstacle_clearance='distance', online_fixes='v2')
    manifest, _, _, commands = capture_launch(lidar_checks, root/'ring-launch', **options)
    assert json.loads(manifest)['goal_region'] == 'ring'
    assert json.loads(manifest)['goal_region_radius_m'] == 1.
    assert {'goal_region:=ring', 'save_plan_maps:=true', 'terrain_source:=prior', 'obstacle_clearance:=distance'} <= set(commands[-1])
    assert 'pose_trace_dir:=' in ' '.join(commands[-1])
    for configure in (
        lambda: lidar_checks.prepare_cases(root/'conflict', goal_region='ring', endpoint_policy='escape'),
        lambda: fixtures.make_runtime(root/'conflict-runtime', box_mapper('centre','sensor'),
                                      goal_region='ring', endpoint_policy='escape'),
    ):
        try:
            configure()
        except ValueError as exc:
            assert '--endpoint-policy none' in str(exc)
        else:
            raise AssertionError('incompatible endpoint policy accepted')

    path = lidar_checks.ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    main = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = []
    stub = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kw: calls.append(kw), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kw: (calls.append(kw) or stub))
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'), scope)
    scope['main'](['--goal-region', 'ring', '--ros-args', '-p', 'map_method:=fine'])
    assert calls == [dict(args=['--ros-args', '-p', 'map_method:=fine']), dict(goal_region='ring')]
    fake = root/'docker'
    fake.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    fake.chmod(0o755)
    flags = ['--map', 'fine', '--goal-region', 'ring']
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu')
    output = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapped'), *flags], env=env)
    assert output.split(b'\0')[-5:-1] == list(map(os.fsencode, flags))
    print('configuration PASS: manifest, ROS options, direct CLI, Docker forwarding and incompatible mode')


if __name__ == '__main__':
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        test_default_bytes(folder)
        test_selection()
        test_box_and_no_path(folder)
        test_restore_and_stale_handoff(folder)
        test_configuration(folder)
    print('all task063 goal-region tests passed')
