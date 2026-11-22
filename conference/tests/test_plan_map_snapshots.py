"""Check plan-map recording and offline attribution without ROS or Gazebo."""

import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType
from unittest.mock import patch

import numpy as np

from experiments import plan_map_inspect
from ros2_jazzy.gz_checks import endpoint_runtime, lidar_checks, safety_runtime
from ros2_jazzy.gz_checks.plan_maps import PlanMapStore, read_plans
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.traversability import TraversabilityMap
from tests.test_endpoint_policy import Immediate
from tests.test_ground_estimate import update_world
from tests.test_review_fixes import SCENARIO
from tests.test_waypoint_feasibility import capture_launch

ROOT = lidar_checks.ROOT
BASE = 'cb6bdf406d5ec36b56f918e900d6f401ee25c584'


def before_module(module):
    file = Path(module.__file__)
    source = subprocess.check_output(['git', 'show', f'{BASE}:{file.relative_to(ROOT.parent)}'],
                                     cwd=ROOT.parent)
    old = ModuleType(module.__name__)
    old.__file__, old.__package__ = str(file), module.__package__
    exec(compile(source, str(file), 'exec'), vars(old))
    return old


def run_fixture(folder, make_runtime, *, recording=False, diagnostics=True):
    prior_z = np.zeros((24, 24))
    rock = np.zeros(prior_z.shape, bool)
    mapper = PointCloudMapFine(prior_z, rock, terrain_source='prior_veto')
    mapper.seen[:] = True
    folder.mkdir()
    runtime = make_runtime(dict(tmap=TraversabilityMap(prior_z, rock)), mapper,
                           online_fixes='v2', diagnostics=diagnostics, plan_log=folder/'plans.csv',
                           executor=Immediate(), **(dict(save_plan_maps=True) if recording else {}))
    with patch('time.perf_counter', return_value=5.):
        runtime.start(SCENARIO.copy())
        assert runtime.tick([2., 2.], 1.) is None
        first = runtime.tick([2., 2.], 2.)
        update_world(mapper, [[9., 2., .55]]*32)
        runtime.tick([2., 2.], 3.)
        failure = runtime.tick([2., 2.], 4.)
        runtime.close()
    assert first['revision'] == 1 and failure['online_error'] == 'lethal_changed'
    return first, failure


def test_default_and_wiring(root):
    old_checks = before_module(lidar_checks)
    for mode in ('none', 'v1', 'v2'):
        options = dict(map_method='fine', online_fixes=mode, diagnostics=True)
        assert capture_launch(old_checks, root/f'{mode}-old', **options) == capture_launch(
            lidar_checks, root/f'{mode}-new', **options)
    old_endpoint = before_module(endpoint_runtime)
    with patch.dict(sys.modules, {endpoint_runtime.__name__: old_endpoint}):
        old_safety = before_module(safety_runtime)
    old, new = root/'runtime-old', root/'runtime-new'
    first = run_fixture(old, old_safety.make_safety_lidar_runtime)
    assert run_fixture(new, safety_runtime.make_safety_lidar_runtime) == first
    files = lambda p: {x.relative_to(p): x.read_bytes() for x in p.rglob('*') if x.is_file()}
    assert files(old) == files(new)
    manifest, _, _, commands = capture_launch(lidar_checks, root/'opt-in', map_method='fine',
                                              terrain_source='prior_veto', save_plan_maps=True)
    assert json.loads(manifest)['save_plan_maps'] and 'save_plan_maps:=true' in commands[-1]
    print('1 PASS: same-host default manifest, missions, commands, plan CSV and diagnostic NPZ bytes; opt-in forwarding')


def test_live_search_records(root):
    raw = root/'live'
    commands = run_fixture(raw, safety_runtime.make_safety_lidar_runtime, recording=True, diagnostics=False)
    assert commands == run_fixture(root/'no-recording', safety_runtime.make_safety_lidar_runtime, diagnostics=False)
    first, _ = commands
    folder = raw/'plan_maps'
    records = dict(read_plans(folder))
    assert list(records) == [1, 2]
    assert not records[1]['lethal'].any()
    goal = tuple(records[2]['goal'])
    assert records[2]['lethal'][goal] and records[2]['veto_supported'][goal]
    assert records[2]['failure_class'] == 'goal_cell'
    with np.load(folder/'applied_000001.npz') as data:
        assert data['sim_time'] == 2 and data['revision'] == 1
        assert np.array_equal(data['path_m'], first['path'])
    with np.load(folder/'applied_000002.npz') as data:
        assert data['failed'] and data['sim_time'] == 4


def record_fixture():
    shape = (13, 13)
    masks = {k: np.zeros(shape, bool) for k in ('lethal', 'seen', 'known', 'detected', 'obstacle_halo',
                                              'prior_raw', 'prior_inflated', 'steep', 'steep_halo')}
    return dict(masks, cost=np.arange(169, dtype=float).reshape(shape), pose=[1., 1., 0., 0., 0., 0.],
                resolution_m=.5, start=[2, 2], goal=[10, 9], version=2, sim_time=0.)


def test_codec_and_inspector(root):
    raw = root/'record'
    store = PlanMapStore(raw/'plan_maps')
    record = record_fixture()
    record['detected'][4, 3] = record['obstacle_halo'][4, 3] = record['lethal'][4, 3] = True
    record['cost'][0, 0] = -0.
    search = dict(path=[[0., 2.], [8., 2.]], success=True, reason='start_leg')
    assert store.search(record, search, '') == 1
    store.application(1, dict(path=[[0., 1.], [4., 1.]], revision=1), 1.)
    record['sim_time'] = 1.2
    record['cost'][0, 0] = np.nextafter(1., 2.)
    record['lethal'][10, 9] = record['obstacle_halo'][10, 9] = True
    assert store.search(record, search, '') == 2
    store.application(2, dict(path=[[0., 0.], [4., 0.]], revision=2), 2.)
    record['sim_time'] = 4.5
    record['obstacle_halo'][10, 9] = False
    record['steep_halo'][10, 9] = True
    assert store.search(record, dict(path=[], success=False, reason='distance'), 'goal_cell') == 3
    store.application(3, dict(online_error='distance'), 5.)
    records = dict(read_plans(store.folder))
    assert records[1]['cost'].view(np.uint64)[0, 0] == np.float64(-0.).view(np.uint64)
    assert records[3]['cost'].tobytes() == record['cost'].tobytes()
    assert np.array_equal(records[3]['lethal'], record['lethal']) and records[3]['unknown'].all()
    assert np.array_equal(records[1]['path_cells'], search['path'])
    tiny = PlanMapStore(root/'tiny', limit=4500)
    assert tiny.search(record, search, '') is None and (tiny.folder/'incomplete.json').is_file()
    assert sum(p.stat().st_size for p in tiny.folder.iterdir()) < 4500
    print('2 PASS: exact search maps, signed-zero/delta cost, paths, prior_veto mask, handoff association and byte cap')

    (raw/'trajectory.csv').write_text('t,x,y\n0,0,1\n4,4,1\n')
    (raw/'debris_footprints.csv').write_text('xmin,ymin,xmax,ymax\n1.6,1.3,2.3,1.8\n')
    (raw/'mission.json').write_text('{"status":"no_path"}')
    with (raw/'path_revisions.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(('t', 'path'))
        writer.writerow((1.1, json.dumps([[0., 1.], [4., 1.]])))
        writer.writerow((2.1, json.dumps([[0., 0.], [4., 0.]])))
    out = root/'inspection'
    plan_map_inspect.main([str(raw), '--out', str(out)])
    with (out/'approach.csv').open() as stream:
        box, = csv.DictReader(stream)
    with (out/'goal_cell.csv').open() as stream:
        goal, = csv.DictReader(stream)
    assert box['plan'] == '1' and np.isclose(float(box['time']), 1.6)
    assert box['path_time_basis'] == 'follower_revision'
    assert np.isclose(float(box['distance_m']), .3) and box['box_detected_cells'] == '1'
    assert box['nearby_blocked_halo_cells'] == '1' and box['path_halo_cells'] == '0'
    assert goal['first_blocked_plan'] == '2' and goal['first_blocked_cause'] == 'detected_obstacle_inflation'
    assert goal['failure_plan'] == '3' and goal['failure_cause'] == 'steep_inflation'
    missing = []
    plan_map_inspect.inspect(root/'absent', [], [], missing)
    assert missing and 'no saved search maps' in missing[0]['reason']
    print('3 PASS: interpolated closest approach uses the last handed-off plan; first blocked goal and missing-record handling')


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        test_default_and_wiring(root)
        test_live_search_records(root)
        test_codec_and_inspector(root)
    print('all task051 plan map snapshot tests passed')
