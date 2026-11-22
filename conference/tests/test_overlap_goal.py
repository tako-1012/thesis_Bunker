"""Task052 opt-in clearance, same-host byte comparisons and synthetic legs."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
from unittest.mock import patch

import numpy as np

from results.overlap_goal.replay import BOX, START, GOAL_NEAR_BOX, GOAL_FAR_FROM_BOX, archived_goals, synthetic_case
from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, lidar_runtime, safety_runtime
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp import pointcloud_map_fine, pointcloud_map_multi
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.traversability import TraversabilityMap
from tests.test_endpoint_policy import Immediate
from tests.test_ground_estimate import update_world
from tests.test_real_sensors import local_cloud
from tests.test_review_fixes import SCENARIO
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission import online_safety

BASE = '662c3cf83b052fd091a9064b479c7938c10b6d8c'
ROOT = lidar_checks.ROOT
NEARBY = (9, 10)  # Centre blocked by BOX.
OUTSIDE = (6, 14)
GROUND = [[x*.5, y*.5, 0.] for x in range(8, 13) for y in range(8, 13) if (x, y) != GOAL_NEAR_BOX]


def load_before(*modules):
    old = {}
    for current in modules:
        path = Path(current.__file__).relative_to(ROOT.parent)
        source = subprocess.check_output(['git', 'show', f'{BASE}:{path}'], cwd=ROOT.parent)
        module = ModuleType(current.__name__)
        module.__file__, module.__package__ = current.__file__, current.__package__
        with patch.dict(sys.modules, old):
            exec(compile(source, module.__file__, 'exec'), vars(module))
        old[module.__name__] = module
    return [old[m.__name__] for m in modules]


def add_scan(mapper, world, stamp=1.):
    if isinstance(mapper, pointcloud_map_multi.PointCloudMapMulti):
        pose = np.array([2., 5., 0., 0., 0., 0.])
        mapper.update(local_cloud(world, pose, mapper.mounts['lidar']), pose, sensor='lidar', stamp=stamp)
    else:
        update_world(mapper, world)


def make_runtime(folder, mapper, *, factory=safety_runtime.make_safety_lidar_runtime, **options):
    folder.mkdir()
    tm = TraversabilityMap(mapper.prior, mapper.raw_obstacle)
    return factory(dict(tmap=tm), mapper, plan_log=folder/'plans.csv', executor=Immediate(), **options)


def start_leg(runtime, start, *goals):
    runtime.start(dict(SCENARIO, start_cells=list(start), stops_cells=[list(g) for g in goals]))
    position = np.asarray(start)*RESOLUTION
    assert runtime.tick(position, 1.) is None
    return runtime.tick(position, 2.)


def runtime_bytes(folder, cls, factory, online_fixes, clearance):
    mapper = cls(np.zeros((24, 24)), ground_estimate='non_obstacle', **clearance)
    mapper.seen[:] = True
    add_scan(mapper, GROUND+[BOX]*3)
    runtime = make_runtime(folder, mapper, factory=factory, online_fixes=online_fixes,
                           diagnostics=True, save_plan_maps=True, record_clearance=True)
    try:
        with patch('time.perf_counter', return_value=5.):
            command = start_leg(runtime, START, GOAL_FAR_FROM_BOX)
            assert command['revision'] == 1
    finally:
        runtime.close()
    return json.dumps(command).encode(), {p.relative_to(folder): p.read_bytes()
                                          for p in folder.rglob('*') if p.is_file()}


def test_default_bytes(root):
    fine, multi, _, _, _, safety, checks = load_before(
        pointcloud_map_fine, pointcloud_map_multi, online_safety, lidar_runtime,
        endpoint_runtime, safety_runtime, lidar_checks)
    for mode, clearance in [('default', {}), ('centre', dict(obstacle_clearance='centre')),
                            ('overlap', dict(obstacle_clearance='overlap'))]:
        for previous, current, is_multi in (
                (fine.PointCloudMapFine, pointcloud_map_fine.PointCloudMapFine, False),
                (multi.PointCloudMapMulti, pointcloud_map_multi.PointCloudMapMulti, True)):
            elev = np.zeros((32, 32))
            assert map_bytes(root/f'{mode}-{is_multi}-old', previous(elev, **clearance), is_multi) == map_bytes(
                root/f'{mode}-{is_multi}-new', current(elev, **clearance), is_multi)
        for fixes in ('none', 'v1', 'v2'):
            tag = f'{mode}-{fixes}'
            options = dict(map_method='fine', online_fixes=fixes, diagnostics=True, save_plan_maps=True, **clearance)
            assert capture_launch(checks, root/f'{tag}-launch-old', **options) == capture_launch(
                lidar_checks, root/f'{tag}-launch-new', **options)
            assert runtime_bytes(root/f'{tag}-run-old', fine.PointCloudMapFine,
                                 safety.make_safety_lidar_runtime, fixes, clearance) == runtime_bytes(
                root/f'{tag}-run-new', pointcloud_map_fine.PointCloudMapFine,
                safety_runtime.make_safety_lidar_runtime, fixes, clearance)
    print('1 PASS: same-host default, explicit centre and overlap bytes for Fine/Multi, none/v1/v2,'
          ' manifest, ROS launch, paths, diagnostics and plan maps')


def test_goal_obstacle_only(root):
    for terrain in ('sensor', 'prior', 'prior_veto'):
        for sensors in ('legacy', 'lidar_real+depth2'):
            tag = f'{terrain}-{sensors}'
            mapper = make_pointcloud_map(np.zeros((24, 24)), map_method='fine', terrain_source=terrain,
                                         sensors=sensors, obstacle_clearance='overlap_goal',
                                         ground_estimate='non_obstacle')
            # The goal is in inferred overlap coverage only.
            add_scan(mapper, GROUND+[BOX]*3)
            assert mapper.fine_obstacle.sum() == 1 and mapper.lethal[GOAL_NEAR_BOX]
            assert not mapper.seen[GOAL_NEAR_BOX]
            fixes = {'sensor': 'none', 'prior': 'v1', 'prior_veto': 'v2'}[terrain]
            rt = make_runtime(root/tag, mapper, online_fixes=fixes,
                              diagnostics=True, save_plan_maps=True)
            try:
                command = start_leg(rt, START, GOAL_NEAR_BOX)
                assert command['revision'] == 1 and command['path'][-1] == [4.5, 5.5]
                first = dict(read_plans(rt.plan_maps.folder))[1]
                assert first['known'][GOAL_NEAR_BOX] and not first['seen'][GOAL_NEAR_BOX]
                assert not first['lethal'][GOAL_NEAR_BOX] and not first['obstacle_halo'][GOAL_NEAR_BOX]
                assert ('veto_supported' in first) == (terrain == 'prior_veto')
                assert first['lethal'][NEARBY] and first['obstacle_halo'][NEARBY]
                planner = rt.state['planner']
                assert np.argwhere(first['lethal'] ^ (planner.known & planner.lethal)).tolist() == [list(GOAL_NEAR_BOX)]
                assert mapper.lethal[GOAL_NEAR_BOX] and planner.lethal[GOAL_NEAR_BOX]
            finally:
                rt.close()

    for cause in ('centre', 'prior_rock', 'steep_halo'):
        elev = np.zeros((24, 24))
        rock = np.zeros(elev.shape, bool)
        goal = NEARBY if cause == 'centre' else GOAL_NEAR_BOX
        if cause == 'prior_rock':
            rock[goal] = True
        if cause == 'steep_halo':
            elev[:, 13:] = 1.
        mapper = pointcloud_map_fine.PointCloudMapFine(
            elev, rock, terrain_source='prior', obstacle_clearance='overlap_goal', ground_estimate='non_obstacle')
        add_scan(mapper, GROUND+[BOX]*3)
        assert mapper._inflated_coarse[goal]
        if cause == 'prior_rock':
            assert mapper._prior_rock[goal]
        if cause == 'steep_halo':
            assert mapper._dilated_steep[goal] and not mapper.tm.steep[goal]
        rt = make_runtime(root/cause, mapper, diagnostics=True, save_plan_maps=True)
        try:
            command = start_leg(rt, OUTSIDE, goal)
            assert command['online_error'] == 'start_leg'
            record = dict(read_plans(rt.plan_maps.folder))[1]
            assert record['lethal'][goal] and record['failure_class'] == 'goal_cell'
            assert bool(record['obstacle_halo'][goal]) == (cause == 'centre')
        finally:
            rt.close()
    print('2 PASS: overlap-only goal opens even if unseen; centre halo, prior rock and steep halo still block;'
          ' Fine/Multi and sensor/prior/prior_veto')


def test_next_goal_and_replan(root):
    for fixes in ('none', 'v1', 'v2'):
        for arrived_inside_old_cell in (False, True):
            mapper = pointcloud_map_fine.PointCloudMapFine(
                np.zeros((24, 24)), obstacle_clearance='overlap_goal', ground_estimate='non_obstacle')
            add_scan(mapper, GROUND+[BOX]*3)
            rt = make_runtime(root/f'{fixes}-{arrived_inside_old_cell}', mapper, online_fixes=fixes,
                              save_plan_maps=True)
            try:
                command = start_leg(rt, START, GOAL_NEAR_BOX, GOAL_FAR_FROM_BOX)
                assert command['revision'] == 1
                arrival = np.asarray(GOAL_NEAR_BOX)*RESOLUTION + [0., 0. if arrived_inside_old_cell else .28]
                rt.tick(arrival, 3.)
                next_leg = rt.tick(arrival, 4.)
                records = dict(read_plans(rt.plan_maps.folder))
                first, second = records[1], records[2]
                assert not first['lethal'][GOAL_NEAR_BOX] and second['lethal'][GOAL_NEAR_BOX]
                assert second['obstacle_halo'][GOAL_NEAR_BOX] and second['lethal'][NEARBY]
                assert tuple(second['goal']) == GOAL_FAR_FROM_BOX
                hits = path_lethal_cells(second['path_cells'], second['lethal'])
                if arrived_inside_old_cell:
                    assert hits.tolist() == [list(GOAL_NEAR_BOX)]
                else:
                    assert not len(hits)
                if arrived_inside_old_cell and fixes == 'none':
                    assert next_leg is None  # Legacy handoff still rejects a blocked start.
                else:
                    assert next_leg['reason'] == 'next_leg'  # v1/v2 exempt the actual start at handoff.
            finally:
                rt.close()
    for fixes in ('v1', 'v2'):
        mapper = pointcloud_map_fine.PointCloudMapFine(
            np.zeros((24, 24)), obstacle_clearance='overlap_goal', ground_estimate='non_obstacle')
        add_scan(mapper, GROUND+[BOX]*3)
        rt = make_runtime(root/f'replan-{fixes}', mapper, online_fixes=fixes, save_plan_maps=True)
        try:
            assert start_leg(rt, START, GOAL_NEAR_BOX)['revision'] == 1
            # The overlap halo already covered the goal. New fine evidence
            # reaches its centre, so the latest view invalidates the old path.
            add_scan(mapper, GROUND+[[4.41, 5.11, .4]]*3, stamp=2.)
            position = np.asarray(START)*RESOLUTION
            rt.tick(position, 3.)
            failure = rt.tick(position, 4.)
            if failure is None:
                failure = rt.tick(position, 5.)
            assert failure['online_error'] == 'lethal_changed'
            records = dict(read_plans(rt.plan_maps.folder))
            assert not records[1]['lethal'][GOAL_NEAR_BOX] and records[2]['lethal'][GOAL_NEAR_BOX]
        finally:
            rt.close()
    print('3 PASS: intermediate and former goals retain overlap, old start handoff rules apply,'
          ' latest centre blockage triggers v1/v2 replanning')


def test_wiring_and_synthetic(root):
    options = dict(map_method='fine', obstacle_clearance='overlap_goal', online_fixes='v2',
                   terrain_source='prior_veto', tracking='corner_slow', save_plan_maps=True)
    manifest, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    assert json.loads(manifest)['obstacle_clearance'] == 'overlap_goal'
    assert 'obstacle_clearance:=overlap_goal' in commands[-1]
    assert 'tracking:=corner_slow' in commands[-2] and 'save_plan_maps:=true' in commands[-1]
    for configure, args in [(lidar_checks.prepare_cases, (root/'coarse',)),
                            (make_pointcloud_map, (np.zeros((12, 12)),))]:
        try:
            configure(*args, obstacle_clearance='overlap_goal', map_method='coarse')
        except ValueError as exc:
            assert str(exc) == 'overlap_goal obstacle clearance requires --map fine'
        else:
            raise AssertionError('coarse map accepted overlap_goal')
    wrapper = root/'docker'
    wrapper.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK052_ARGV"\n')
    wrapper.chmod(0o755)
    argv = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', TASK052_ARGV=str(argv))
    subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), '--map', 'fine',
                    '--obstacle-clearance', 'overlap_goal'], check=True, env=env)
    assert argv.read_bytes().split(b'\0')[-3:] == [b'--obstacle-clearance', b'overlap_goal', b'']

    centre, overlap, goal = (synthetic_case(mode, GOAL_NEAR_BOX)
                             for mode in pointcloud_map_fine.OBSTACLE_CLEARANCES)
    assert centre['success'] and not overlap['success'] and goal['success']
    assert goal['path_clearance_m'] >= .5
    centre, overlap, goal = (synthetic_case(mode, GOAL_FAR_FROM_BOX)
                             for mode in pointcloud_map_fine.OBSTACLE_CLEARANCES)
    assert centre['path_clearance_m'] < .5 <= overlap['path_clearance_m']
    assert overlap['path_cells'] == goal['path_cells']
    archived = list(archived_goals(ROOT/'results/eval_044/no_path_evidence.csv'))
    assert len(archived) == 12 and all(row['overlap_goal_open'] for row in archived)
    print('4 PASS: manifest, ROS and mocked Docker forwarding, fine-only validation, both synthetic paths and 12 archived goals')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        test_default_bytes(root)
        test_goal_obstacle_only(root)
        test_next_goal_and_replan(root)
        test_wiring_and_synthetic(root)
    print('all task052 overlap goal tests passed')
