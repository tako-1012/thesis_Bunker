"""Same-host default bytes, propagated uncertainty and ROS-free option wiring."""

import argparse
import ast
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, lidar_map, plan_maps, safety_runtime
from tapp import local_ground, pointcloud_map_fine, pointcloud_map_multi
from tapp.config import RESOLUTION, Robot
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.slope_uncertainty import ground_standard_errors, slope_standard_error
from tapp.traversability import inflate
from tests import test_overlap_goal as fixtures
from tests.test_ground_estimate import update_world
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch

BASE = '58379c12e30b99ad57042675a0c62abc32fd3180'
TARGET = (10, 10)
SHAPE = (24, 24)


def test_default_bytes(root):
    with patch.object(fixtures, 'BASE', BASE):
        fine, multi, local, _, _, safety, _, checks = fixtures.load_before(
            pointcloud_map_fine, pointcloud_map_multi, local_ground, plan_maps,
            endpoint_runtime, safety_runtime, lidar_map, lidar_checks)
    for settings in ({}, dict(ground_estimate='non_obstacle', ground_near_obstacle='exclude'),
                     dict(obstacle_reference='local', ground_estimate='non_obstacle')):
        for old, new, is_multi in ((fine.PointCloudMapFine, PointCloudMapFine, False),
                                   (multi.PointCloudMapMulti, PointCloudMapMulti, True)):
            tag = (settings.get('ground_near_obstacle') or settings.get('obstacle_reference') or 'base') + str(is_multi)
            prior = np.zeros(SHAPE)
            with patch.dict(sys.modules, {local.__name__: local}):
                expected = map_bytes(root/f'{tag}-old', old(prior, **settings), is_multi)
            assert expected == map_bytes(root/f'{tag}-default', new(prior, **settings), is_multi)
            assert expected == map_bytes(root/f'{tag}-none', new(prior, **settings, slope_uncertainty='none'), is_multi)
    options = dict(map_method='fine', diagnostics=True, save_plan_maps=True, pose_trace=True, online_fixes='v2')
    baseline = capture_launch(checks, root/'old', **options)
    assert baseline == capture_launch(lidar_checks, root/'default', **options)
    assert baseline == capture_launch(lidar_checks, root/'none', **options, slope_uncertainty='none')
    a = fixtures.runtime_bytes(root/'old-plan', fine.PointCloudMapFine, safety.make_safety_lidar_runtime, 'v2', {})
    b = fixtures.runtime_bytes(root/'none-plan', PointCloudMapFine, safety_runtime.make_safety_lidar_runtime,
                               'v2', {'slope_uncertainty': 'none'})
    assert a == b
    print('1 PASS: same-host old/default/none Fine and Multi map, manifest, ROS dispatch and plan bytes')


def slope_returns(angle, offsets):
    x, y = TARGET
    height = RESOLUTION*np.tan(np.deg2rad(angle))
    return [[(x+side)*RESOLUTION, y*RESOLUTION, side*height+offset]
            for side in (-1, 1) for offset in offsets]


def test_classification():
    cases = ((26., (-.1, .1), True), (30., (0.,)*12, False))
    for angle, offsets, expected_soft in cases:
        none, soft = (PointCloudMapFine(np.zeros(SHAPE), slope_uncertainty=mode)
                      for mode in ('none', 'soft'))
        for mapper in (none, soft):
            update_world(mapper, slope_returns(angle, offsets))
        np.testing.assert_allclose(soft.tm.slope[TARGET], angle, rtol=0., atol=1e-12)
        np.testing.assert_array_equal(none.elev, soft.elev)
        np.testing.assert_array_equal(none.fine_obstacle, soft.fine_obstacle)
        assert none.lethal[TARGET] and none._dilated_steep[TARGET[0], TARGET[1]+1]
        assert bool(soft.uncertain_steep[TARGET]) == expected_soft
        assert bool(soft.lethal[TARGET]) != expected_soft
        assert bool(soft._dilated_steep[TARGET[0], TARGET[1]+1]) != expected_soft
        np.testing.assert_array_equal(soft._dilated_steep, inflate(soft.tm.steep, .5))
        if expected_soft:
            assert soft.tm.cost[TARGET] == 1.
    # Replace the history with measurements of the same median. Only its
    # uncertainty changes, so slope classification and cost still must refresh.
    # Keep synthetic roughness below saturation to check the cost is restored.
    soft = PointCloudMapFine(np.zeros(SHAPE), slope_uncertainty='soft', robot=Robot(rough_sat=.2))
    update_world(soft, slope_returns(26., (-.125, .125)))
    height_before = soft.elev.copy()
    assert soft.uncertain_steep[TARGET]
    cells = np.repeat([(9, 10), (11, 10)], 64, axis=0)
    world = np.column_stack((cells*RESOLUTION, height_before[tuple(cells.T)]))
    soft._update_prior(world, cells, len(cells))
    np.testing.assert_array_equal(height_before, soft.elev)
    assert soft.lethal[TARGET] and not soft.uncertain_steep[TARGET] and soft.tm.cost[TARGET] < 1.
    print('2 PASS: 26-degree noisy slope is passable at cost 1.0; supported 30-degree slope keeps its halo')


def test_standard_errors():
    # Sample std([1, 3]) is sqrt(2), so standard error is exactly 1.
    error = ground_standard_errors(np.array([1., 3., 2.]), np.array([0, 0, 1]), np.array([2, 1, 0]))
    np.testing.assert_array_equal(error, [1., .15, .15])
    sigma = np.zeros((5, 5))
    sigma[1, 2], sigma[3, 2], sigma[2, 1], sigma[2, 3] = .1, .2, .3, .4
    sigma[0, 0], sigma[0, 1], sigma[1, 0] = .1, .2, .3
    gx, gy = np.full_like(sigma, .3), np.full_like(sigma, .4)
    result = slope_standard_error(gx, gy, sigma)
    np.testing.assert_allclose(result[2, 2], np.sqrt((.6**2)*(.1**2+.2**2)+(.8**2)*(.3**2+.4**2)))
    corner = np.sqrt((.6*.3)**2+(.8*.2)**2+(-(.6+.8)*.1)**2)/RESOLUTION
    np.testing.assert_allclose(result[0, 0], corner)

    mapper = PointCloudMapFine(np.zeros(SHAPE), ground_estimate='non_obstacle', slope_uncertainty='soft')
    # An accepted height equal to the prior still has measurement error.
    update_world(mapper, [[5., 5., 0.], [5.5, 5., .6]])
    assert mapper.sigma_h[10, 10] == .15
    assert mapper.seen[11, 10] and mapper.sigma_h[11, 10] == 0. and mapper.elev[11, 10] == 0.
    assert mapper.sigma_h[15, 15] == 0.

    excluded = PointCloudMapFine(np.zeros(SHAPE), ground_estimate='non_obstacle',
                                 ground_near_obstacle='exclude', slope_uncertainty='soft')
    update_world(excluded, [[5.10, 5.20, .10], [5.10, 5.20, .20]])
    np.testing.assert_allclose(excluded.sigma_h[TARGET], .05)
    previous = excluded.elev[TARGET]
    update_world(excluded, [[5.30, 5.20, .6]]*3)
    assert excluded.elev[TARGET] == previous and excluded.sigma_h[TARGET] == .15
    assert excluded.sigma_h[11, 10] == 0.

    # Local ground uses the same eligible returns and preserves the prior
    # where it has neither a median nor an identified plane.
    local = PointCloudMapFine(np.zeros(SHAPE), obstacle_reference='local', slope_uncertainty='soft')
    update_world(local, [[5.1, 5.1, .1], [5.2, 5.1, .1], [5.1, 5.2, .1]])
    np.testing.assert_allclose(local.elev[TARGET], .1)
    assert local.sigma_h[TARGET] == 0. and local.sigma_h[11, 10] == 0.
    print('3 PASS: sample and slope errors, shared corner, prior/single/held fallbacks and local ground')


def test_wiring(root):
    options = dict(map_method='fine', slope_uncertainty='soft', ground_estimate='non_obstacle',
                   ground_near_obstacle='exclude', obstacle_clearance='distance', online_fixes='v2',
                   pose_trace=True, save_plan_maps=True)
    raw_manifest, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    manifest = json.loads(raw_manifest)
    assert manifest['slope_uncertainty'] == 'soft' and manifest['slope_uncertainty_lower_z'] == 1.645
    assert manifest['slope_uncertainty_single_height_error_m'] == .15
    assert {'slope_uncertainty:=soft', 'save_plan_maps:=true', 'obstacle_clearance:=distance',
            'ground_near_obstacle:=exclude'} <= set(commands[-1])
    assert any(arg.startswith('pose_trace_dir:=') for arg in commands[-1])
    mapper_keys = ('map_method', 'slope_uncertainty', 'ground_estimate', 'ground_near_obstacle', 'obstacle_clearance')
    mapper = lidar_map.make_pointcloud_map(np.zeros(SHAPE), **{k: options[k] for k in mapper_keys})
    # The new fine obstacle excludes one of the two low returns. Only the
    # remaining adopted return contributes to the measurement uncertainty.
    update_world(mapper, [[5., 5., -.05], [5.2, 5., .2]]+[[5.3, 5., .6]]*3)
    np.testing.assert_allclose(mapper.elev[TARGET], -.05)
    assert mapper.sigma_h[TARGET] == .15
    runtime = fixtures.make_runtime(root/'recorded', mapper, save_plan_maps=True, online_fixes='v2')
    try:
        command = fixtures.start_leg(runtime, (6, 10), (6, 14))
        assert command['revision'] == 1
        saved = dict(plan_maps.read_plans(runtime.plan_maps.folder))[1]
        np.testing.assert_array_equal(saved['sigma_h'], mapper.sigma_h)
        np.testing.assert_array_equal(saved['uncertain_steep'], mapper.uncertain_steep)
    finally:
        runtime.close()
    mapper.save(root/'final.npz')
    with np.load(root/'final.npz') as data:
        np.testing.assert_array_equal(data['sigma_h'], mapper.sigma_h)
        np.testing.assert_array_equal(data['uncertain_steep'], mapper.uncertain_steep)
    for settings in (dict(map_method='coarse'), dict(map_method='fine', terrain_source='prior'),
                     dict(map_method='fine', terrain_source='prior_veto')):
        for configure in (lambda: lidar_checks.prepare_cases(root/'invalid', slope_uncertainty='soft', **settings),
                          lambda: lidar_map.make_pointcloud_map(np.zeros(SHAPE), slope_uncertainty='soft', **settings)):
            try:
                configure()
            except ValueError as exc:
                assert 'requires --map fine and --terrain-source sensor' in str(exc)
            else:
                raise AssertionError('incompatible mode was accepted')

    path = lidar_checks.ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    main = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    calls = []
    stub = SimpleNamespace(close=lambda: None, destroy_node=lambda: None)
    ros = SimpleNamespace(init=lambda **kw: calls.append(kw), spin=lambda node: None, ok=lambda: False)
    scope = dict(argparse=argparse, sys=sys, rclpy=ros, GROUND_ESTIMATES=('all_returns', 'non_obstacle'),
                 LidarPlannerNode=lambda **kw: (calls.append(kw) or stub))
    exec(compile(ast.Module(body=[main], type_ignores=[]), str(path), 'exec'), scope)
    scope['main'](['--slope-uncertainty', 'soft', '--ros-args', '-p', 'map_method:=fine'])
    assert calls == [dict(args=['--ros-args', '-p', 'map_method:=fine']), dict(slope_uncertainty='soft')]

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\n')
    docker.chmod(0o755)
    flags = ['--map', 'fine', '--slope-uncertainty', 'soft']
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu')
    output = subprocess.check_output(['bash', str(LAUNCHER), str(root/'wrapper'), *flags], env=env)
    assert output.split(b'\0')[-5:-1] == list(map(os.fsencode, flags))
    print('wiring PASS: manifest, ROS CLI, shell forwarding, independent obstacle clearance and plan fields')


if __name__ == '__main__':
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_default_bytes(root)
        test_classification()
        test_standard_errors()
        test_wiring(root)
    print('all task066 slope uncertainty tests passed')
