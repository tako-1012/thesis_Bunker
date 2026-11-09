"""Task028: fixed synthetic cases, runtime lifecycle, and three saved failures."""
from concurrent.futures import Future
from pathlib import Path
import tempfile
from unittest.mock import patch
import numpy as np
from tapp.config import RESOLUTION
from tapp.traversability import TraversabilityMap
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.collision import path_lethal_cells
from tapp.endpoint_policy import (plan_endpoint, classify_failure, raw_mask, SnapshotStore,
                                  load_snapshot, RetryState, audit_path)
from ros2_jazzy.gz_checks.endpoint_runtime import make_lidar_runtime
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission


def snapshot(n=13):
    z = np.zeros((n, n), bool)
    return dict(lethal=z.copy(), cost=np.ones((n, n)), detected=z.copy(),
                prior_raw=z.copy(), steep=z.copy(), seen=~z, pose=np.array([2., 2., 0., 0., 0., 0.]),
                start=np.array([4, 4]), goal=np.array([10, 4]), version=9, sim_time=0.)


class Immediate:
    def submit(self, f, *args):
        future = Future()
        try:
            future.set_result(f(*args))
        except Exception as exc:
            future.set_exception(exc)
        return future

    def shutdown(self, wait=True):
        pass


def environment():
    z = np.zeros((13, 13))
    mapper = PointCloudMapFine(z, z.astype(bool))
    mapper.seen[:] = True
    return dict(tmap=TraversabilityMap(z, z.astype(bool))), mapper


def test_defaults():
    with tempfile.TemporaryDirectory() as tmp:
        prior, mapper = environment()
        p = Path(tmp)
        # Default dispatch is the unchanged original class, including CSV bytes.
        a = make_lidar_runtime(prior, mapper, plan_log=p/'a.csv', executor=Immediate())
        b = LidarOnlineMission(prior, mapper, plan_log=p/'b.csv', executor=Immediate())
        assert type(a) is type(b) is LidarOnlineMission
        mission = dict(id=1, order=[0], stops_cells=[[10, 4]])
        commands = []
        for runtime in (a, b):
            runtime.start(mission)
            with patch('time.perf_counter', return_value=1.0):
                runtime.tick([2., 2.], 0.)
                command = runtime.tick([2., 2.], .1)
            assert command['path']
            commands.append(command)
            runtime.close()
        assert commands[0] == commands[1]
        assert (p/'a.csv').read_bytes() == (p/'b.csv').read_bytes()
        assert (p/'a.csv').read_bytes() == b'n_plans,reason,success,plan_time_s\n1,start_leg,True,0.0\n'
        assert not (p/'diag').exists()
    print('1 PASS: default original runtime, path and CSV bytes unchanged')


def test_start():
    s = snapshot()
    s['lethal'][3:6, 3:6] = True
    # Clear a one-cell halo, with raw corners blocking diagonal corner cuts.
    s['detected'][3, 3] = s['detected'][5, 5] = True
    s['lethal'][3, 5] = s['lethal'][5, 3] = False
    s['lethal'][4, 5] = False
    assert not plan_endpoint(s)['success']
    r = plan_endpoint(s, 'escape')
    assert r['success']
    assert not len(path_lethal_cells(r['path'], raw_mask(s)))
    assert not (r['relaxed'] & raw_mask(s)).any()
    assert np.all(r['cost'][r['relaxed']] == s['cost'][~s['lethal']].max())
    for key in ('detected', 'prior_raw', 'steep'):
        s[key][4, 4] = True
        assert not plan_endpoint(s, 'escape')['success']
        assert not plan_endpoint(s, 'escape')['relaxed'][4, 4]
        s[key][4, 4] = False
    # Metric radius is measured around the actual pose, not a rounded cell.
    s['pose'][:2] = [2.24, 2.24]
    r = plan_endpoint(s, 'escape')
    for c in np.argwhere(r['relaxed']):
        assert np.linalg.norm(c*RESOLUTION-s['pose'][:2]) <= .5+1e-12
    print('2 PASS: fixed 0.5m start escape; all three raw masks remain blocked')


def test_goal():
    s = snapshot()
    s['lethal'][10, 4] = True
    r = plan_endpoint(s, 'escape')
    assert r['success'] and r['outcome'] == 'nearby'
    assert np.linalg.norm((np.array(r['goal'])-s['goal'])*RESOLUTION) <= 1.
    assert np.linalg.norm(np.array(r['goal'])-s['goal']) == 1.
    s['detected'][10, 4] = True
    assert plan_endpoint(s, 'escape')['outcome'] == 'unreachable'
    # A nearer disconnected cell cannot win over a reachable candidate.
    s = snapshot()
    s['lethal'][10, 4] = True
    s['lethal'][9, :] = True
    s['detected'][9, :] = True
    r = plan_endpoint(s, 'escape')
    assert r['success'] and r['goal'][0] <= 8
    print('3 PASS: reachable nearest substitute <=1.0m; raw goal unreachable')


def test_substitute_replan():
    with tempfile.TemporaryDirectory() as tmp:
        prior, mapper = environment()
        mapper.lethal[10, 4] = True
        runtime = make_lidar_runtime(prior, mapper, plan_log=Path(tmp)/'plans.csv',
                                     endpoint_policy='escape', executor=Immediate())
        runtime.start(dict(id=1, order=[0], stops_cells=[[10, 4]]))
        for t in (0., .1, .2):
            runtime.tick([2., 2.], t)
        planner = runtime.state['planner']
        assert planner.endpoint_result['outcome'] == 'nearby'
        planner.since_replan = planner.replan_every_m
        for t in (.3, .4):
            runtime.tick([2., 2.], t)
        assert planner.endpoint_result['outcome'] == 'nearby'
        goal_m = np.asarray(planner.goal)*RESOLUTION
        runtime.pose[:2] = goal_m
        for t in (.5, .6, .7):
            runtime.tick(goal_m, t)
        assert runtime.finished and runtime.outcomes[0]['outcome'] == 'nearby'
        runtime.close()
    print('3b PASS: substitute remains nearby after replanning and arrival')


def test_retry_runtime():
    r = RetryState()
    assert r.failed(4.) == 'waiting'
    assert not r.ready(4.999) and r.ready(5.)
    assert r.failed(5.) == 'unreachable' and r.retries == 1
    with tempfile.TemporaryDirectory() as tmp:
        prior, mapper = environment()
        mapper.detected_obstacle[10, 4] = mapper.lethal[10, 4] = True
        runtime = make_lidar_runtime(prior, mapper, plan_log=Path(tmp)/'plans.csv',
                                     endpoint_policy='escape', diagnostics=True, executor=Immediate())
        runtime.start(dict(id=1, order=[0, 1], stops_cells=[[10, 4], [4, 10]]))
        runtime.pose = np.array([2., 2., 0., 0., 0., 0.])
        runtime.tick([2., 2.], 0.)
        for t in (.1, .5, .99):
            command = runtime.tick([2., 2.], t)
            assert command['endpoint_hold']
            assert len(runtime.state['planner'].events) == 1
        for t in (1., 1.05, 1.1, 1.15):
            command = runtime.tick([2., 2.], t)
        assert runtime.outcomes[0]['outcome'] == 'unreachable'
        assert runtime.outcomes[0]['retries'] == 1
        assert command is None or 'online_error' not in command
        assert runtime.state['leg'] == 1
        runtime.pose[:2] = [2., 5.]
        for t in (1.2, 1.25, 1.3):
            runtime.tick([2., 5.], t)
        assert runtime.finished
        assert [x['outcome'] for x in runtime.outcomes] == ['unreachable', 'arrived']
        runtime.close()
        assert len(list((Path(tmp)/'diag').glob('plan_fail_*.npz'))) == 2
    print('4 PASS: actual async runtime stops, waits 1 sim second, retries once, skips and terminates')


def test_delayed_handoff():
    with tempfile.TemporaryDirectory() as tmp:
        prior, mapper = environment()
        runtime = make_lidar_runtime(prior, mapper, plan_log=Path(tmp)/'plans.csv',
                                     endpoint_policy='escape', executor=Immediate())
        runtime.start(dict(id=1, order=[0], stops_cells=[[10, 4]]))
        runtime.tick([2., 2.], 0.)  # Worker found a path through the old map.
        mapper.lethal[7, :] = mapper.detected_obstacle[7, :] = True
        command = runtime.tick([2., 2.], .1)
        assert command['endpoint_hold'] and runtime.sent == 0
        for t in (.5, 1.09):
            assert runtime.tick([2., 2.], t)['endpoint_hold']
            assert runtime.stats['retries'] == 1
        for t in (1.1, 1.2, 1.3):
            runtime.tick([2., 2.], t)
        assert runtime.finished and runtime.outcomes[0]['outcome'] == 'unreachable'
        runtime.close()
    print('4b PASS: stale blocked handoff stops and terminates after one timed retry')


def test_diagnostics():
    s = snapshot()
    s['lethal'][10, 4] = True
    assert classify_failure(s) == 'goal_cell'
    s['lethal'][10, 4] = False
    s['lethal'][4, 4] = True
    assert classify_failure(s) == 'start_cell'
    s['lethal'][:] = False
    assert classify_failure(s) == 'corridor'
    s['goal'] = [100, 4]
    assert classify_failure(s) == 'other'
    with tempfile.TemporaryDirectory() as tmp:
        store = SnapshotStore(tmp)
        p = store.save(s, failure=True)
        restored = load_snapshot(p)
        assert all(np.array_equal(s[k], restored[k]) for k in s)
        for t in (0., 9., 10., 20., 30., 40.):
            s['sim_time'] = t
            store.tick(s)
        assert len(list(Path(tmp).glob('periodic_*.npz'))) == 3
        assert p.exists() and all(f.stat().st_size < 5_000_000 for f in Path(tmp).glob('*.npz'))
    with tempfile.TemporaryDirectory() as tmp:
        prior, mapper = environment()
        mapper.lethal[10, 4] = True
        runtime = make_lidar_runtime(prior, mapper, plan_log=Path(tmp)/'plans.csv',
                                     diagnostics=True, executor=Immediate())
        runtime.start(dict(id=1, order=[0], stops_cells=[[10, 4]]))
        runtime.tick([2., 2.], 12.)
        mapper.lethal[:] = False  # A later update must not alter the failure snapshot.
        runtime.tick([2., 2.], 12.1)
        runtime.close()
        failure = load_snapshot(next((Path(tmp)/'diag').glob('plan_fail_*.npz')))
        assert failure['lethal'][10, 4] and failure['sim_time'] == 12.
        assert 'goal_cell' in (Path(tmp)/'plans.csv').read_text()
    relaxed = np.zeros((4, 4), bool)
    relaxed[1, 1] = True
    audit = audit_path([[0., .5], [1., .5]], relaxed, relaxed)
    assert abs(audit['relaxed_length_m']-.5) < 1e-12
    assert audit['truth_lethal_length_m'] == audit['relaxed_length_m']
    print('5 PASS: exact failed map, classifications, 10s snapshots/newest 3, offline exact lengths')


def test_audit_and_transport():
    import ast
    import json
    from types import SimpleNamespace
    from experiments.endpoint_audit import audit_run
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder/'endpoint_masks').mkdir()
        mask = np.zeros((4, 4), bool)
        mask[1, 1] = True
        np.savez_compressed(folder/'endpoint_masks/000001.npz', applied=True,
                            sim_time=.25, relaxed_bits=np.packbits(mask), relaxed_shape=mask.shape)
        (folder/'endpoint_trajectory.csv').write_text('sim_time,x,y,z,roll,pitch,yaw\n0,0,0.5,0,0,0,0\n1,1,0.5,0,0,0,0\n')
        result = audit_run(folder, mask)
        assert abs(result['relaxed_length_m']-.5) < 1e-12
        assert result['truth_lethal_length_m'] == result['relaxed_length_m']
    # Exercise the actual ROS callback body without importing ROS or Gazebo.
    path = Path(__file__).resolve().parents[1]/'ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'on_mission')
    namespace = dict(json=json, Twist=lambda: 'zero_velocity')
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
    messages, stopped = [], []
    fake = SimpleNamespace(map_id='test', online=True, follower=object(), mission_id=1,
                           log=SimpleNamespace(mission={}), cmd=SimpleNamespace(publish=messages.append),
                           stop=stopped.append)
    original_log = fake.log
    namespace['on_mission'](fake, SimpleNamespace(data=json.dumps(dict(map_id='test', id=1, endpoint_hold=True))))
    assert fake.follower is None and fake.log is original_log and messages == ['zero_velocity']
    namespace['on_mission'](fake, SimpleNamespace(data=json.dumps(dict(map_id='test', id=1,
                          endpoint_finished=True, endpoint_outcomes=[dict(outcome='nearby')]))))
    assert stopped == ['completed'] and fake.log.mission['endpoint_outcomes'][0]['outcome'] == 'nearby'
    print('5b PASS: time-aligned actual-travel audit; ROS callback holds zero velocity and retains run log')


def test_saved_failures():
    from experiments.endpoint_replay import replay
    rows = replay()
    assert len(rows) == 3
    assert all(r['none'] == 'no_path' and r['raw_cells_cleared'] == 0 for r in rows)
    assert all(r['escape'] in ('path', 'unreachable_after_retry_then_next_stop') for r in rows)
    for row in rows:
        print('6 replay:', row)
    print('6 PASS: three saved failures reproduced without changing fixed constants')


if __name__ == '__main__':
    for test in (test_defaults, test_start, test_goal, test_substitute_replan, test_retry_runtime, test_delayed_handoff, test_diagnostics, test_audit_and_transport, test_saved_failures):
        test()
    print('Task028 endpoint policy tests passed; full existing suite is run separately (requirement 7).')
