"""Exercise the opt-in ground median, local updates and ROS-free compatibility."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import lidar_checks, safety_runtime
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp import local_ground, pointcloud_map_fine, pointcloud_map_multi
from tapp.config import RESOLUTION
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from tapp.traversability import TraversabilityMap, inflate
from tests import test_overlap_goal as reference
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch

BASE = 'ee501a7503074b840f95ccae516b23879ac85fdf'
SHAPE = (28, 28)
BOX = [5.30, 5., .75]
DIRTY = (10, 10)


def make(mode, prior, **options):
    return PointCloudMapFine(prior, ground_estimate='non_obstacle', ground_near_obstacle=mode, **options)


def legacy_bytes(root):
    with patch.object(reference, 'BASE', BASE):
        fine, multi, local, checks = reference.load_before(
            pointcloud_map_fine, pointcloud_map_multi, local_ground, lidar_checks)
    for estimate in ('all_returns', 'non_obstacle'):
        for obstacle_ref in ('prior', 'local'):
            options = dict(ground_estimate=estimate, obstacle_reference=obstacle_ref)
            tag = f'{estimate}-{obstacle_ref}'
            for old, new, is_multi in ((fine.PointCloudMapFine, PointCloudMapFine, False),
                                       (multi.PointCloudMapMulti, PointCloudMapMulti, True)):
                z = np.zeros(SHAPE)
                prefix = f'{tag}-{is_multi}'
                with patch.dict(sys.modules, {local.__name__: local}):
                    expected = map_bytes(root/f'{prefix}-old', old(z, **options), is_multi)
                assert expected == map_bytes(root/f'{prefix}-new', new(z, **options), is_multi)
                assert expected == map_bytes(root/f'{prefix}-keep',
                                             new(z, **options, ground_near_obstacle='keep'), is_multi)
    for fixes in ('none', 'v1', 'v2'):
        options = dict(map_method='fine', ground_estimate='non_obstacle', online_fixes=fixes,
                       save_plan_maps=True, diagnostics=True, pose_trace=True)
        expected = capture_launch(checks, root/f'{fixes}-old', **options)
        assert expected == capture_launch(lidar_checks, root/f'{fixes}-new', **options)
        assert expected == capture_launch(lidar_checks, root/f'{fixes}-keep',
                                          **options, ground_near_obstacle='keep')
        assert reference.runtime_bytes(root/f'{fixes}-plan-old', fine.PointCloudMapFine,
                                       safety_runtime.make_safety_lidar_runtime, fixes, {}) == reference.runtime_bytes(
            root/f'{fixes}-plan-new', PointCloudMapFine, safety_runtime.make_safety_lidar_runtime,
            fixes, dict(ground_near_obstacle='keep'))
    print('1 PASS: same-host old/implicit/explicit keep map, sensor, plan, ROS and manifest bytes')


def flat_box():
    # The actual ground is flat. A uniform +0.22m prior offset makes the
    # lower (0.50m high) wall returns survive the existing 0.3m test alone.
    prior = np.full(SHAPE, .22)
    world = [[x*.5, y*.5, 0.] for x in range(8, 15) for y in range(8, 14)]
    world += [[5.10, 5., .50]]*7+[BOX]*3
    keep, exclude = (make(mode, prior) for mode in ('keep', 'exclude'))
    for mapper in (keep, exclude):
        reference.add_scan(mapper, world)
    assert keep.tm.steep[9, 10] and not exclude.tm.steep.any()
    assert keep.elev[DIRTY] == .50 and exclude.elev[DIRTY] == 0.
    assert np.array_equal(keep.fine_obstacle, exclude.fine_obstacle)
    assert np.array_equal(keep.fine_inflated, exclude.fine_inflated)
    assert np.array_equal(keep.seen, exclude.seen)
    assert keep.fine_obstacle.sum() == 1 and exclude.lethal[11, 10]
    print('2 PASS: low box wall induces a false steep cell only in keep; same detections, halo and coverage')


def true_slope():
    gradient = np.tan(np.deg2rad(30.))
    prior = np.broadcast_to(np.arange(SHAPE[0])[:, None]*RESOLUTION*gradient, SHAPE).copy()
    ground = [[x*.5, y*.5, prior[x, y]] for x in range(5, 16) for y in range(7, 14)]
    box = [[5.30, 5., 5.30*gradient+.55]]*3
    for ref in ('prior', 'local'):
        # Denser returns provide non-collinear 032 support around the box.
        support = ground+[[x, y, x*gradient] for x in np.arange(4.6, 5.81, .1)
                          for y in np.arange(4.5, 5.61, .1)]
        keep, exclude = (make(mode, prior, obstacle_reference=ref) for mode in ('keep', 'exclude'))
        for mapper in (keep, exclude):
            reference.add_scan(mapper, support+box)
        assert keep.fine_obstacle.sum() == 1
        assert np.array_equal(keep.fine_obstacle, exclude.fine_obstacle)
        assert np.array_equal(keep.fine_inflated, exclude.fine_inflated)
        assert exclude.tm.steep[5:10, 7:14].all()
        assert np.array_equal(keep.tm.steep, exclude.tm.steep)
    print('3 PASS: the true ramp remains steep and detection is identical for prior and local reference')


def incremental():
    mapper = make('exclude', np.zeros(SHAPE))
    newest = [5.30, 5.20, .6]
    untouched = (5, 5)
    fallback = (10, 11)
    reference.add_scan(mapper, [[4.8, 5.2, 0.]]+[[5.10, 5.2, .26]]*5+
                       [[5.20, 5.30, .17]]*4+[[2.5, 2.5, .1]])
    before = mapper.elev.copy()
    assert before[DIRTY] > .25 and before[fallback] > .16
    with patch.object(mapper, '_publish', wraps=mapper._publish) as publish:
        reference.add_scan(mapper, [newest]*3)
    updated, _ = publish.call_args.args
    observed = publish.call_args.kwargs['observed']
    assert np.ravel_multi_index(DIRTY, SHAPE) in updated and np.ravel_multi_index(DIRTY, SHAPE) not in observed
    assert np.ravel_multi_index(untouched, SHAPE) not in updated
    assert mapper.elev[DIRTY] == 0.
    assert mapper.elev[fallback] == before[fallback] and mapper.elev[11, 10] == mapper.prior[11, 10]
    obstacle = np.argwhere(mapper.fine_obstacle)
    assert len(obstacle) == 1
    i, j = obstacle[0]
    assert mapper._ground_excluded[i-2, j] and not mapper._ground_excluded[i-2, j-1]

    expected = before.copy()
    for cell, values in mapper.samples.items():
        xy = np.column_stack(np.unravel_index(mapper._fine_ids[cell], mapper.fine_shape))
        d2 = ((xy[:, None]-obstacle)**2).sum(axis=2)
        good = (d2 > 4).all(axis=1) & (values[:, 1] < mapper.obstacle_height_m)
        if good.any():
            expected.flat[cell] = np.median(values[good, 0])
    np.testing.assert_array_equal(mapper.elev, expected)
    tm = TraversabilityMap(expected, mapper.raw_obstacle, mapper.robot, mapper.weights)
    np.testing.assert_array_equal(mapper.tm.steep, tm.steep)
    np.testing.assert_allclose(mapper.tm.rough, tm.rough, atol=1e-9, rtol=0.)
    np.testing.assert_allclose(mapper.tm.cost, tm.cost, atol=1e-9, rtol=0.)
    np.testing.assert_array_equal(mapper.lethal, tm.rock | mapper._inflated_coarse | inflate(tm.steep, .5))
    print('4 PASS: zero returns preserves prior/previous height; 0.2m boundary; dirty history agrees with full rebuild')


def integration(root):
    options = dict(map_method='fine', ground_estimate='non_obstacle', ground_near_obstacle='exclude',
                   terrain_source='prior', obstacle_clearance='distance', steep_near_obstacle='no_inflate',
                   pose_trace=True, save_plan_maps=True, sensors='lidar_real+depth2', online_fixes='v2')
    raw_manifest, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    manifest = json.loads(raw_manifest)
    assert manifest['ground_near_obstacle'] == 'exclude' and manifest['ground_exclusion_radius_m'] == .2
    assert manifest['ground_near_obstacle_effect'] == 'recorded sensor elevation only'
    assert manifest['save_plan_maps'] and manifest['pose_trace']
    assert {'ground_near_obstacle:=exclude', 'obstacle_clearance:=distance', 'steep_near_obstacle:=no_inflate'} <= set(commands[-1])
    assert any('pose_trace_dir:=' in arg for arg in commands[-1])
    params = {key: options[key] for key in ('map_method', 'ground_estimate', 'ground_near_obstacle',
                                           'obstacle_clearance', 'steep_near_obstacle', 'sensors')}
    prior = np.full(SHAPE, .22)
    ground = [[x*.5, y*.5, 0.] for x in range(8, 13) for y in range(8, 12)]
    world = ground+[[5.10, 5., .50]]*7+[BOX]*3
    mappers = [make_pointcloud_map(prior, **params, terrain_source=terrain) for terrain in ('sensor', 'prior')]
    for mapper in mappers:
        mapper.seen[:] = True
        reference.add_scan(mapper, world)
        assert mapper.fine_obstacle.sum() == 1 and mapper.elev[DIRTY] == 0.
        runtime = reference.make_runtime(root/mapper.terrain_source, mapper, online_fixes='v2', save_plan_maps=True)
        try:
            command = reference.start_leg(runtime, reference.START, reference.GOAL_FAR_FROM_BOX)
            assert command['revision'] == 1
            saved = dict(read_plans(runtime.plan_maps.folder))[1]
            assert saved['success'] and 'obstacle_cost' in saved
        finally:
            runtime.close()
    assert np.array_equal(mappers[1].tm.elev, prior) and not np.array_equal(mappers[1].elev, prior)

    for invalid in (dict(map_method='coarse', ground_estimate='non_obstacle'),
                    dict(map_method='fine', ground_estimate='all_returns')):
        with np.testing.assert_raises_regex(ValueError, '--ground-estimate non_obstacle'):
            make_pointcloud_map(prior, **invalid, ground_near_obstacle='exclude')
        with np.testing.assert_raises_regex(ValueError, '--ground-estimate non_obstacle'):
            lidar_checks.prepare_cases(root/'invalid', **invalid, ground_near_obstacle='exclude')

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK062_ARGV"\n')
    docker.chmod(0o755)
    argv = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu', TASK062_ARGV=str(argv))
    for policy in (['--ground-near-obstacle', 'exclude'], ['--ground-near-obstacle=exclude']):
        args = ['--map', 'fine', '--ground-estimate', 'non_obstacle', *policy]
        subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), *args], check=True, env=env)
        assert argv.read_bytes().split(b'\0')[-len(args)-1:-1] == list(map(os.fsencode, args))
    print('integration PASS: Fine/Multi, manifest, ROS and Docker args, distance/no_inflate/pose trace/plan maps, prior height only')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        legacy_bytes(root)
        flat_box()
        true_slope()
        incremental()
        integration(root)
    print('all task062 ground-near-obstacle tests passed')
