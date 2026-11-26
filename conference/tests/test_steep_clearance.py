"""Exercise steep distance, local updates, legacy bytes and ROS-free wiring."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch

import numpy as np

from results.distance_clearance import replay as boxes
from results.steep_clearance import replay
from ros2_jazzy.gz_checks import distance_runtime, endpoint_runtime, lidar_checks, lidar_runtime, safety_runtime
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp import distance_clearance, pointcloud_map_fine, pointcloud_map_multi
from tapp.collision import line_of_sight_exact
from tapp.config import RESOLUTION
from tapp.distance_clearance import CombinedClearance, SegmentClearance, obstacle_cost
from tapp.obstacle_clearance import path_clearance
from tapp.online_mission import OnlinePlanner
from tapp.planners import smooth_cost_aware
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.steep_clearance import SteepDistanceField
from tests import test_overlap_goal as reference
from tests.test_ground_estimate import update_world
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_terrain_from_prior import map_bytes
from tests.test_waypoint_feasibility import capture_launch
from thesis_bunker_mission import online_safety

BASE = '58379c12e30b99ad57042675a0c62abc32fd3180'


def test_legacy_bytes(root):
    with patch.object(reference, 'BASE', BASE):
        old_clearance, fine, multi, _, _, _, safety, search, checks = reference.load_before(
            distance_clearance, pointcloud_map_fine, pointcloud_map_multi, online_safety, lidar_runtime,
            endpoint_runtime, safety_runtime, distance_runtime, lidar_checks)
    for mode in ('centre', 'distance'):
        clearance = dict(obstacle_clearance=mode)
        z = np.zeros((32, 32))
        for previous, current, is_multi in (
                (fine.PointCloudMapFine, PointCloudMapFine, False),
                (multi.PointCloudMapMulti, pointcloud_map_multi.PointCloudMapMulti, True)):
            tag = f'{mode}-{is_multi}'
            expected = map_bytes(root/f'{tag}-old', previous(z, **clearance), is_multi)
            assert expected == map_bytes(root/f'{tag}-new', current(z, **clearance), is_multi)
            assert expected == map_bytes(root/f'{tag}-explicit',
                                         current(z, **clearance, steep_clearance='centre'), is_multi)
        for fixes in ('none', 'v1', 'v2'):
            options = dict(map_method='fine', diagnostics=True, save_plan_maps=True, online_fixes=fixes, **clearance)
            tag = f'{mode}-{fixes}'
            expected = capture_launch(checks, root/f'{tag}-launch-old', **options)
            assert expected == capture_launch(lidar_checks, root/f'{tag}-launch-new', **options)
            assert expected == capture_launch(lidar_checks, root/f'{tag}-launch-centre', **options, steep_clearance='centre')
            with patch.dict('sys.modules', {search.__name__: search, old_clearance.__name__: old_clearance}):
                expected = reference.runtime_bytes(root/f'{tag}-rt-old', fine.PointCloudMapFine,
                                                   safety.make_safety_lidar_runtime, fixes, clearance)
            assert expected == reference.runtime_bytes(
                root/f'{tag}-rt-new', PointCloudMapFine, safety_runtime.make_safety_lidar_runtime,
                fixes, dict(clearance, steep_clearance='centre'))
    print('1 PASS: identical same-host Fine/Multi, map, manifest, mission, diagnostics and runtime bytes for centre')


def oracle(steep):
    cells = np.argwhere(steep)
    if not len(cells):
        return np.full(steep.shape, np.inf)
    centres = np.indices(steep.shape).transpose(1, 2, 0)
    offsets = np.maximum(np.abs(centres[:, :, None]-cells)-.5, 0.)*RESOLUTION
    return np.hypot(offsets[..., 0], offsets[..., 1]).min(axis=2)


def test_masks_and_cost():
    steep = np.zeros((24, 24), bool)
    steep[10, 10] = True
    prior = PointCloudMapFine(np.zeros(steep.shape)).tm
    entries = {}
    for obstacle in ('centre', 'distance'):
        for slope in ('centre', 'distance'):
            mapper = PointCloudMapFine(prior.elev, obstacle_clearance=obstacle, steep_clearance=slope)
            # Include a band query that has an observed obstacle cost and
            # another that stays unknown while the steep layer contributes.
            mapper.seen[:13, :] = True
            replay.install_steep(mapper, steep)
            fine = np.zeros(mapper.fine_shape, bool)
            fine[56, 52] = True
            boxes.install_mask(mapper, fine)
            runtime = lidar_runtime.LidarOnlineMission(dict(tmap=prior), mapper)
            try:
                planner = runtime._new_planner(OnlinePlanner, ((1, 1),))
                runtime._observe(planner)
                lethal, multiplier = planner.planning_maps()
                entries[obstacle, slope] = (mapper, planner, lethal, multiplier)
            finally:
                runtime.close()
    mapper, planner, _, multiplier = entries['distance', 'distance']
    field = mapper.steep_distance_field
    np.testing.assert_allclose(field.distance_m, oracle(steep), atol=1e-12, rtol=0.)
    np.testing.assert_array_equal(obstacle_cost([.5, .75, 1., 1.5]), [0., .5625, .25, 0.])
    assert obstacle_cost([np.nextafter(.5, 1.)])[0] > .999999
    assert field.cost[13, 10] > 0. and not planner.known[13, 10]
    assert (mapper.distance_field.cost*field.cost*planner.known > 0.).any()
    for obstacle in ('centre', 'distance'):
        _, _, base_hard, base_mult = entries[obstacle, 'centre']
        _, _, opt_hard, opt_mult = entries[obstacle, 'distance']
        assert opt_hard.tobytes() == base_hard.tobytes()
        np.testing.assert_array_equal(opt_mult, base_mult+planner.w*field.cost)
    np.testing.assert_allclose(multiplier, entries['centre', 'centre'][3]
                               + planner.w*(field.cost+mapper.distance_field.cost*planner.known), atol=1e-14, rtol=0.)
    # Test the diagonal of the steep-only hard stencil, outside any box check.
    assert not entries['centre', 'distance'][2][9, 9] and field.distance_m[9, 9] < .5
    print('2 PASS: unchanged hard stencil, exact square distances and quadratic soft costs add to obstacle costs')


def test_paths():
    centre, distance = replay.replay_synthetic()
    assert centre['route'] and distance['route'] and distance['min_steep_m'] > centre['min_steep_m']
    for gap in (1.2, 1.8, 2.5):
        for row in replay.replay_synthetic(gap, forced=True):
            assert row['route'] and not row['goal_blocked']
    print('3 PASS: route moves farther from slopes and all three forced gaps remain reachable')


def test_shortcuts_and_updates():
    path = [(10, 15), (12, 12), (12, 8), (11, 7)]
    steep = SegmentClearance(np.array([[4.75, 4.75]]), np.array([[5.25, 5.25]]))
    # A second layer intersects the original route. Comparing one global
    # minimum instead of each layer would allow the unsafe steep shortcut.
    box = SegmentClearance(np.array([[5.95, 5.95]]), np.array([[6.05, 6.05]]))
    layer = CombinedClearance(box, steep)
    free = np.zeros((24, 24), bool)
    mult = np.ones(free.shape)
    normal, _ = smooth_cost_aware(path, free, mult, los=line_of_sight_exact)
    safe, _ = layer.smooth(path, free, mult)
    near = lambda points: path_clearance(np.asarray(points)*.5, steep.lower, steep.upper)
    assert len(normal) == 2 and near(normal) < near(path)
    for a, b in zip(safe, safe[1:]):
        assert steep.segment(a, b) >= near(path[path.index(a):path.index(b)+1])-1e-10
    assert not layer.preserves(path[0], path[1], path[2])

    mask = np.zeros((67, 71), bool)
    mask[2::8, 3::9] = True
    field = SteepDistanceField(mask)
    geometry = field.geometry()
    previous = geometry.lower.copy()
    mask[10, 12] = False
    mask[17, 13] = True
    with patch.object(field, '_update_tiles', wraps=field._update_tiles) as update:
        field.refresh(mask)
    affected = update.call_args.args[1]
    assert 0 < len(affected) < 25
    rebuilt = SteepDistanceField(mask)
    assert field.distance_m.tobytes() == rebuilt.distance_m.tobytes()
    assert field.cost.tobytes() == rebuilt.cost.tobytes()
    np.testing.assert_allclose(field.distance_m, oracle(mask), atol=1e-12, rtol=0.)
    assert np.array_equal(geometry.lower, previous) and field.geometry() is not geometry
    field.refresh(np.zeros_like(mask))
    assert np.isinf(field.distance_m).all() and not field.cost.any()
    for terrain in ('sensor', 'prior', 'prior_veto'):
        z = np.zeros((28, 28))
        mapper = PointCloudMapFine(z, samples_per_cell=3, terrain_source=terrain,
                                   steep_clearance='distance')
        update_world(mapper, [[5., 5., .62]]*2)
        update_world(mapper, [[4.5, 5., 0.]]*2)  # marks an adjacent veto cell supported
        assert bool(mapper.tm.steep.any()) == (terrain != 'prior')
        assert not mapper.fine_obstacle.any()
        np.testing.assert_allclose(mapper.steep_distance_field.distance_m, oracle(mapper.tm.steep), atol=1e-12, rtol=0.)
        update_world(mapper, [[5., 5., 0.]]*3)
        assert np.isinf(mapper.steep_distance_field.distance_m).all()
    print('4 PASS: no clearance-reducing shortcuts; local add/remove and all terrain sources match rebuild')


def test_configuration(root):
    options = dict(map_method='fine', obstacle_clearance='distance', steep_clearance='distance',
                   ground_estimate='non_obstacle', ground_near_obstacle='exclude', terrain_source='prior',
                   steep_near_obstacle='no_inflate', diagnostics=True, save_plan_maps=True,
                   pose_trace=True, online_fixes='v2', sensors='lidar_real+depth2')
    raw, _, _, commands = capture_launch(lidar_checks, root/'launch', **options)
    manifest = json.loads(raw)
    assert manifest['steep_clearance'] == 'distance'
    assert manifest['steep_distance_clearance'] == dict(R_hard=.5, R_soft=1.5, w=1.)
    assert {'steep_clearance:=distance', 'ground_near_obstacle:=exclude',
            'terrain_source:=prior', 'obstacle_clearance:=distance'} <= set(commands[-1])
    assert manifest['pose_trace'] and manifest['save_plan_maps']
    mapper_args = {key: value for key, value in options.items()
                   if key not in ('diagnostics', 'save_plan_maps', 'pose_trace', 'online_fixes')}
    mapper = make_pointcloud_map(np.zeros((24, 24)), **mapper_args)
    mapper.seen[:] = True
    steep = np.zeros(mapper.elev.shape, bool)
    steep[12, 9] = True
    replay.install_steep(mapper, steep)
    reference.add_scan(mapper, reference.GROUND+[reference.BOX]*3)
    runtime = reference.make_runtime(root/'runtime', mapper, online_fixes='v2', save_plan_maps=True)
    try:
        command = reference.start_leg(runtime, reference.START, reference.GOAL_FAR_FROM_BOX)
        assert command['revision'] == 1
        saved = dict(read_plans(runtime.plan_maps.folder))[1]
        assert saved['obstacle_cost'].tobytes() == mapper.distance_field.cost.tobytes()
        assert saved['steep_cost'].tobytes() == mapper.steep_distance_field.cost.tobytes()
        assert saved['success']
    finally:
        runtime.close()
    with np.testing.assert_raises_regex(ValueError, 'requires --map fine'):
        make_pointcloud_map(np.zeros((24, 24)), steep_clearance='distance')
    with np.testing.assert_raises_regex(ValueError, 'requires --map fine'):
        lidar_checks.prepare_cases(root/'coarse', steep_clearance='distance')

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" > "$TASK065_ARGV"\n')
    docker.chmod(0o755)
    argv = root/'argv'
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', THESIS_RENDER='cpu', TASK065_ARGV=str(argv))
    args = ['--map', 'fine', '--steep-clearance', 'distance']
    subprocess.run(['bash', str(LAUNCHER), str(root/'wrapped'), *args], check=True, env=env)
    assert argv.read_bytes().split(b'\0')[-len(args)-1:-1] == list(map(os.fsencode, args))
    print('integration PASS: CLI, manifest, ROS and fake Docker, Multi and both saved soft layers')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp)
        test_legacy_bytes(scratch)
        test_masks_and_cost()
        test_paths()
        test_shortcuts_and_updates()
        test_configuration(scratch)
    print('all task065 steep clearance tests passed')
