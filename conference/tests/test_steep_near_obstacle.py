"""Verify the optional steep halo policy with synthetic clouds and same-host baselines."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, lidar_runtime, safety_runtime
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp import pointcloud_map_fine, pointcloud_map_multi
from tapp.online_mission import OnlinePlanner
from tapp.traversability import inflate
from tests import test_overlap_goal as reference
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission import online_safety

BASE = 'bbaa7c7a8b5f13152d66c0bf26e7552a1deaa7d2'
SHAPE = (30, 30)
SEED = (10, 10)
RELEASE = (9, 10)
BOX = [5.5, 5., 1.3]


def test_default_bytes(root):
    with patch.object(reference, 'BASE', BASE):
        fine, multi, _, _, _, safety, checks = reference.load_before(
            pointcloud_map_fine, pointcloud_map_multi, online_safety, lidar_runtime,
            endpoint_runtime, safety_runtime, lidar_checks)
    for previous, current, is_multi in (
            (fine.PointCloudMapFine, pointcloud_map_fine.PointCloudMapFine, False),
            (multi.PointCloudMapMulti, pointcloud_map_multi.PointCloudMapMulti, True)):
        elev = np.zeros((32, 32))
        for terrain in ('sensor', 'prior', 'prior_veto'):
            options = dict(obstacle_clearance='overlap', terrain_source=terrain)
            tag = f'{is_multi}-{terrain}'
            old = map_bytes(root/f'map-{tag}-old', previous(elev, **options), is_multi)
            assert old == map_bytes(root/f'map-{tag}-new', current(elev, **options), is_multi)
            assert old == map_bytes(root/f'map-{tag}-keep',
                                    current(elev, **options, steep_near_obstacle='keep'), is_multi)
    for fixes in ('none', 'v1', 'v2'):
        options = dict(map_method='fine', online_fixes=fixes, save_plan_maps=True, diagnostics=True)
        old = capture_launch(checks, root/f'{fixes}-launch-old', **options)
        assert old == capture_launch(lidar_checks, root/f'{fixes}-launch-new', **options)
        assert old == capture_launch(lidar_checks, root/f'{fixes}-launch-keep', **options, steep_near_obstacle='keep')
        assert reference.runtime_bytes(root/f'{fixes}-run-old', fine.PointCloudMapFine,
                                       safety.make_safety_lidar_runtime, fixes, {}) == reference.runtime_bytes(
            root/f'{fixes}-run-new', pointcloud_map_fine.PointCloudMapFine,
            safety_runtime.make_safety_lidar_runtime, fixes, dict(steep_near_obstacle='keep'))
    print('1 PASS: same-host implicit and explicit keep, Fine/Multi, all terrain sources, manifests, ROS args and plan logs')


def full_rebuild(mapper):
    seeds = mapper.tm.steep & ~mapper._inflated_coarse
    if mapper.terrain_source == 'prior_veto':
        seeds |= mapper._prior_steep
    return inflate(seeds, mapper.robot.footprint_radius)


def test_geometry_and_updates():
    elev = np.zeros(SHAPE)
    elev[11, 10] = elev[19, 19] = .8
    for sensors in ('legacy', 'lidar_real+depth2'):
        for clearance in ('centre', 'overlap', 'overlap_goal'):
            options = dict(map_method='fine', sensors=sensors, obstacle_clearance=clearance,
                           ground_estimate='non_obstacle')
            keep = make_pointcloud_map(elev, **options)
            mapper = make_pointcloud_map(elev, **options, steep_near_obstacle='no_inflate')
            old_halo = mapper._dilated_steep.copy()
            assert old_halo[RELEASE] and not mapper.tm.steep[RELEASE]
            with patch.object(pointcloud_map_fine, 'inflate', wraps=inflate) as stamp:
                reference.add_scan(mapper, [BOX]*3)
                stamp.assert_called_once()
                assert stamp.call_args.args[0].size < elev.size
            reference.add_scan(keep, [BOX]*3)
            assert mapper.elev.tobytes() == elev.tobytes() and mapper.tm.steep[SEED]
            assert mapper._inflated_coarse[SEED] and mapper.lethal[SEED]
            assert not mapper._inflated_coarse[RELEASE]
            assert keep.lethal[RELEASE] and not mapper.lethal[RELEASE]
            assert mapper.lethal[17, 19] and not mapper.tm.steep[17, 19]
            assert mapper._dilated_steep.tobytes() == full_rebuild(mapper).tobytes()
            assert keep.tm.steep.tobytes() == mapper.tm.steep.tobytes()
            assert keep.tm.cost.tobytes() == mapper.tm.cost.tobytes()
            assert keep._inflated_coarse.tobytes() == mapper._inflated_coarse.tobytes()
            for i, cloud in enumerate(([[9., 9.5, .5]]*3, [[.1, .1, -.9]]*3,
                                       [[8.5, 8.5, -.9], [10., 10., -.9]]), 2):
                reference.add_scan(mapper, cloud, stamp=float(i))
                assert np.array_equal(mapper._dilated_steep, full_rebuild(mapper))
                assert np.array_equal(mapper.lethal, mapper.tm.rock | mapper.tm.steep | full_rebuild(mapper))
    print('2 PASS: covered slope stays lethal, external slope keeps inflation, obstacle/height/cost bytes agree')
    print('3 PASS: obstacle-only local update and later height changes match full rebuild for Fine/Multi and all clearances')


def test_prior_and_veto(root):
    elev = np.zeros(SHAPE)
    elev[19, 19] = .8
    rock = np.zeros(SHAPE, bool)
    rock[24, 24] = True
    for terrain in ('prior', 'prior_veto'):
        mapper = make_pointcloud_map(elev, rock, map_method='fine', terrain_source=terrain,
                                     steep_near_obstacle='no_inflate', ground_estimate='non_obstacle')
        prior_halo = mapper._dilated_steep.copy()
        prior_rock = mapper._prior_rock.copy()
        reference.add_scan(mapper, [[9., 9.5, .5]]*3)
        assert np.array_equal(prior_halo, mapper._dilated_steep)
        assert np.array_equal(prior_rock, mapper._prior_rock)
    # The veto makes (10, 9) known by inflation only. After detecting a
    # different cell near its seed, the planner can observe it opening.
    inferred = (10, 9)
    reference.add_scan(mapper, [[5., 5., 0.]]*32+[[5.5, 5., .26], [4.5, 5., -.26]], stamp=2.)
    assert mapper._veto_supported[SEED] and mapper.tm.steep[SEED] and mapper.lethal[inferred]
    assert not mapper.seen[inferred]
    planner = OnlinePlanner(mapper.tm.cost, mapper.lethal, mapper.weights)
    plain_planner = OnlinePlanner(mapper.tm.cost, mapper.lethal, mapper.weights)
    args = ([2., 2.], [2., 2., 0., 0., 0., 0.], 0., inferred)
    plain = reference.make_runtime(root/'plain-veto', mapper)
    try:
        first = endpoint_runtime.capture(mapper, planner, *args, save_plan_maps=True)
        plain._observe(plain_planner)
        assert first['known'][inferred] and first['lethal'][inferred] and plain_planner.lethal[inferred]
        reference.add_scan(mapper, [[5., 5.5, .5]]*3, stamp=3.)
        later = endpoint_runtime.capture(mapper, planner, *args, save_plan_maps=True)
        plain._observe(plain_planner)
        assert plain_planner.known[inferred] and not plain_planner.lethal[inferred]
    finally:
        plain.close()
    assert not later['seen'][inferred] and later['known'][inferred] and not later['lethal'][inferred]
    assert later['veto_supported'][SEED] and later['steep'][SEED] and later['lethal'][SEED]
    assert np.array_equal(later['steep_halo'], full_rebuild(mapper))
    for fixes in ('none', 'v1', 'v2'):
        mapper = make_pointcloud_map(elev, map_method='fine', terrain_source='sensor', obstacle_clearance='overlap_goal',
                                     steep_near_obstacle='no_inflate', ground_estimate='non_obstacle')
        reference.add_scan(mapper, reference.GROUND+[reference.BOX]*3)
        rt = reference.make_runtime(root/f'combo-{fixes}', mapper, online_fixes=fixes, save_plan_maps=True)
        try:
            assert reference.start_leg(rt, reference.START, reference.GOAL_NEAR_BOX)['revision'] == 1
            record = dict(read_plans(rt.plan_maps.folder))[1]
            assert np.array_equal(record['steep_halo'], mapper._dilated_steep)
            assert mapper.lethal[reference.GOAL_NEAR_BOX] and not record['lethal'][reference.GOAL_NEAR_BOX]
        finally:
            rt.close()
    print('prior/veto PASS: prior seeds and rocks kept, former inferred halo refreshed, overlap_goal and plan maps work with none/v1/v2')


def test_wiring(root):
    options = dict(steep_near_obstacle='no_inflate', terrain_source='prior_veto', obstacle_clearance='overlap_goal',
                   save_plan_maps=True, online_fixes='v2')
    manifest, _, _, commands = capture_launch(lidar_checks, root/'launch', map_method='fine', **options)
    assert json.loads(manifest)['steep_near_obstacle'] == 'no_inflate'
    assert 'steep_near_obstacle:=no_inflate' in commands[-1]
    for factory, args in ((lidar_checks.prepare_cases, (root/'coarse',)), (make_pointcloud_map, (np.zeros(SHAPE),))):
        try:
            factory(*args, steep_near_obstacle='no_inflate')
        except ValueError as error:
            assert 'requires --map fine' in str(error)
        else:
            raise AssertionError('coarse accepted no_inflate')
    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK055_ARGV"\n')
    docker.chmod(0o755)
    args = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', TASK055_ARGV=str(args))
    subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), '--map', 'fine',
                    '--steep-near-obstacle', 'no_inflate'], check=True, env=env)
    assert args.read_bytes().split(b'\0')[-3:] == [b'--steep-near-obstacle', b'no_inflate', b'']
    print('CLI PASS: fine-only opt-in, manifest, ROS args and fake Docker forwarding')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        test_default_bytes(root)
        test_geometry_and_updates()
        test_prior_and_veto(root)
        test_wiring(root)
    print('all task055 steep-near-obstacle tests passed')
