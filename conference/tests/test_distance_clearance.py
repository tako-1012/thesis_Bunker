"""Compare clearance modes, exact geometry, local updates and ROS-free wiring."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import numpy as np
from scipy.spatial import cKDTree

from results.distance_clearance import replay
from results.overlap_goal.replay import synthetic_case, GOAL_FAR_FROM_BOX
from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, lidar_runtime, safety_runtime
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp import distance_clearance, pointcloud_map_fine, pointcloud_map_multi
from tapp.collision import line_of_sight_exact
from tapp.distance_clearance import DistanceField, SegmentClearance, obstacle_cost
from tapp.obstacle_clearance import cell_boxes, path_clearance
from tapp.planners import astar, smooth_cost_aware
from tapp.pointcloud_map_fine import FINE_RESOLUTION, PointCloudMapFine, RATIO
from tests import test_overlap_goal as reference
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission import online_safety

BASE = '2df543fd70e25fdc326e7d908e9f171091819518'


def test_legacy_bytes(root):
    with patch.object(reference, 'BASE', BASE):
        fine, multi, _, _, _, safety, checks = reference.load_before(
            pointcloud_map_fine, pointcloud_map_multi, online_safety, lidar_runtime,
            endpoint_runtime, safety_runtime, lidar_checks)
    for name in ('default', 'centre', 'overlap', 'overlap_goal'):
        clearance = {} if name == 'default' else dict(obstacle_clearance=name)
        for previous, current, is_multi in (
                (fine.PointCloudMapFine, PointCloudMapFine, False),
                (multi.PointCloudMapMulti, pointcloud_map_multi.PointCloudMapMulti, True)):
            z = np.zeros((32, 32))
            assert map_bytes(root/f'{name}-{is_multi}-old', previous(z, **clearance), is_multi) == map_bytes(
                root/f'{name}-{is_multi}-new', current(z, **clearance), is_multi)
        for fixes in ('none', 'v1', 'v2'):
            options = dict(map_method='fine', diagnostics=True, save_plan_maps=True, online_fixes=fixes, **clearance)
            tag = f'{name}-{fixes}'
            assert capture_launch(checks, root/f'{tag}-launch-old', **options) == capture_launch(
                lidar_checks, root/f'{tag}-launch-new', **options)
            assert reference.runtime_bytes(root/f'{tag}-run-old', fine.PointCloudMapFine,
                                           safety.make_safety_lidar_runtime, fixes, clearance) == reference.runtime_bytes(
                root/f'{tag}-run-new', PointCloudMapFine, safety_runtime.make_safety_lidar_runtime, fixes, clearance)
    print('1 PASS: default/centre/overlap/overlap_goal match the base on this host for maps, plans, manifests and ROS dispatch')


def test_hard_and_soft():
    shape = (24, 24)
    fine = np.zeros(tuple(n*RATIO for n in shape), bool)
    fine[::13, ::17] = True
    z = np.zeros(shape)
    centre, distance = (PointCloudMapFine(z, obstacle_clearance=mode) for mode in ('centre', 'distance'))
    for mapper in (centre, distance):
        replay.install_mask(mapper, fine)
    d = distance.distance_field.distance_m
    assert np.array_equal(centre._inflated_coarse, d <= .5)
    assert centre.lethal.tobytes() == distance.lethal.tobytes()
    seen, cost, _ = distance.planning_snapshot()
    assert not seen.any() and cost.max() > 0.  # Cost layer alone does not make cells known.
    geometry = distance.distance_field.geometry()
    lower, upper = cell_boxes(fine, .1, -.25)
    centres = np.indices(shape).transpose(1, 2, 0)*.5
    diff = np.maximum(np.maximum(lower-centres[..., None, :], centres[..., None, :]-upper), 0.)
    assert np.allclose(d, np.linalg.norm(diff, axis=-1).min(axis=-1), atol=1e-12, rtol=0.)
    a, b = (2.41, 14.71), (17.1, 12.02)
    exact = path_clearance(np.array([a, b])*.5, lower, upper)
    assert np.isclose(geometry.segment(a, b), exact, atol=1e-12, rtol=0.)
    values = [.1, .5, np.nextafter(.5, 1.), .75, 1., 1.5, np.inf]
    assert np.allclose(obstacle_cost(values), [0., 0., 1., .5625, .25, 0., 0.])
    assert np.array_equal(obstacle_cost([.75, 1.]), np.square([.75, .5]))
    assert np.isclose(obstacle_cost(1., 2.), 4/9)
    for soft in (.5, np.nan, np.inf):
        try:
            PointCloudMapFine(z, obstacle_clearance='distance', clearance_soft_m=soft)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted an invalid R_soft')
    print('2 PASS: hard mask matches centre and exact rectangle distance; quadratic band and endpoint limits')


def test_path_and_smooth():
    centre, distance = [synthetic_case(mode, GOAL_FAR_FROM_BOX) for mode in ('centre', 'distance')]
    assert centre['success'] and distance['success']
    assert distance['path_clearance_m'] > centre['path_clearance_m']
    for width in (1.2, 1.8, 2.5):
        selected = {row['mode']: row for row in replay.narrow_case(width, forced=True)}
        assert selected['distance']['route'] and not selected['distance']['goal_blocked']
        assert selected['distance']['path_m'] >= 13.
    print('3 PASS: distance increases box clearance and all three forced corridors remain passable')

    path = [(10, 15), (12, 12), (12, 8), (11, 7)]
    geometry = SegmentClearance(np.array([[4.75, 4.75]]), np.array([[4.85, 4.85]]))
    free = np.zeros((24, 24), bool)
    mult = np.ones(free.shape)
    normal, _ = smooth_cost_aware(path, free, mult, los=line_of_sight_exact)
    safe, _ = geometry.smooth(path, free, mult)
    distance_to = lambda pts: path_clearance(np.asarray(pts)*.5, geometry.lower, geometry.upper)
    assert len(normal) == 2 and distance_to(normal) < distance_to(path)
    assert distance_to(safe) >= distance_to(path)-1e-10
    for a, b in zip(safe, safe[1:]):
        assert geometry.segment(a, b) >= distance_to(path[path.index(a):path.index(b)+1])-1e-10
    print('4 PASS: cost-acceptable shortcuts cannot reduce the exact segment-to-box minimum')


def test_incremental():
    shape = (75, 65)
    grid = np.indices(shape).transpose(1, 2, 0)*.5
    field = DistanceField(shape, FINE_RESOLUTION, RATIO, 1.5)
    old_seeds = np.stack(np.meshgrid(np.arange(2, shape[0]*5, 32),
                                     np.arange(2, shape[1]*5, 32), indexing='ij'), axis=-1).reshape(-1, 2)
    added = np.array([[154, 163], [153, 166]])
    field.add(old_seeds)
    before = field.distance_m.copy()
    counts = []

    class Tree:
        def __init__(self, points):
            self.tree = cKDTree(points)

        def query(self, points):
            counts.append(points.shape[:-1])
            return self.tree.query(points)

    with patch.object(distance_clearance, 'cKDTree', Tree):
        field.add(added)
    assert counts and sum(np.prod(size) for size in counts[1:]) < np.prod(shape)
    rebuilt = DistanceField(shape, FINE_RESOLUTION, RATIO, 1.5)
    rebuilt.add(np.concatenate((old_seeds, added)))
    assert field.distance_m.tobytes() == rebuilt.distance_m.tobytes()
    assert field.cost.tobytes() == rebuilt.cost.tobytes()
    lower = added*.1-.25
    gap = np.maximum(np.maximum(lower-grid[..., None, :], grid[..., None, :]-lower-.1), 0.)
    expected = np.minimum(before, np.linalg.norm(gap, axis=-1).min(axis=-1))
    assert np.allclose(field.distance_m, expected, rtol=0., atol=1e-12)
    print('5 PASS: local queries omit distant tiles and incremental distance/cost match the full rebuild')


def test_combinations(root):
    options = dict(map_method='fine', diagnostics=True, save_plan_maps=True, pose_trace=True,
                   online_fixes='v2', terrain_source='prior_veto', tracking='corner_slow',
                   steep_near_obstacle='no_inflate', obstacle_clearance='distance', clearance_soft_m=1.7)
    manifest, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    manifest = json.loads(manifest)
    assert manifest['distance_clearance'] == dict(R_hard=.5, R_soft=1.7, w_obs=1.)
    assert manifest['pose_trace'] and manifest['save_plan_maps']
    assert {'obstacle_clearance:=distance', 'clearance_soft_m:=1.7', 'steep_near_obstacle:=no_inflate'} <= set(commands[-1])
    assert 'tracking:=corner_slow' in commands[-2] and 'pose_trace_dir:=' in ' '.join(commands[-2])

    for fixes, terrain in zip(('none', 'v1', 'v2'), ('sensor', 'prior', 'prior_veto')):
        mapper = make_pointcloud_map(np.zeros((24, 24)), map_method='fine', sensors='lidar_real+depth2',
                                     ground_estimate='non_obstacle', obstacle_clearance='distance',
                                     terrain_source=terrain, steep_near_obstacle='no_inflate')
        mapper.seen[:] = True
        reference.add_scan(mapper, reference.GROUND+[reference.BOX]*3)
        rt = reference.make_runtime(root/fixes, mapper, online_fixes=fixes, save_plan_maps=True)
        try:
            command = reference.start_leg(rt, reference.START, reference.GOAL_NEAR_BOX)
            assert command['revision'] == 1 and mapper.distance_field.cost[reference.GOAL_NEAR_BOX] > 0.
            records = dict(read_plans(rt.plan_maps.folder))
            assert records[1]['obstacle_cost'].tobytes() == mapper.distance_field.cost.tobytes()
            assert records[1]['success'] and not records[1]['lethal'][reference.GOAL_NEAR_BOX]
            planner = rt.state['planner']
            blocked, mult = planner.planning_maps()
            hard_goal = (10, 10)
            assert blocked[hard_goal] and astar(blocked, hard_goal, hard_goal, mult)['success']
            assert not planner.start_leg(hard_goal, hard_goal)['success']
        finally:
            rt.close()

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK060_ARGV"\n')
    docker.chmod(0o755)
    argv = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu', TASK060_ARGV=str(argv))
    args = ['--map', 'fine', '--obstacle-clearance', 'distance', '--clearance-soft-m', '1.7']
    subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), *args], check=True, env=env)
    assert argv.read_bytes().split(b'\0')[-7:-1] == list(map(os.fsencode, args))
    print('integration PASS: metadata, Docker/ROS options, Multi terrain/safety modes and recorded obstacle costs')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        test_legacy_bytes(root)
        test_hard_and_soft()
        test_path_and_smooth()
        test_incremental()
        test_combinations(root)
    print('all task060 distance clearance tests passed')
