"""Offline task046 reachability, CLI, published command and Web API tests."""

from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
import numpy as np

from ros2_jazzy.gz_checks import edge_margin_checks, lidar_checks, waypoint_trial
from tapp.config import RESOLUTION, Robot
from tapp.planners import astar
from tapp.waypoint_feasibility import check_waypoints
from tests.test_rtf_option import clean_env
from webui import server


ROOT = lidar_checks.ROOT


def fixture():
    blocked = np.zeros((13, 13), bool)
    blocked[5, :] = True
    blocked[2, 2] = True
    z = np.zeros(blocked.shape)
    tm = SimpleNamespace(lethal=blocked, cost=z, elev=z, rock=np.zeros_like(blocked),
                         steep=np.zeros_like(blocked), robot=Robot())
    return dict(tmap=tm)


def archive_scenarios():
    return json.loads((lidar_checks.BASELINE/'manifest.json').read_text())['scenarios']


def trial_scenarios():
    scenarios = archive_scenarios()
    first = scenarios[0]
    first.update(start=[1, 1], points=[[2, 1], [2, 2], [6, 3], [8, 8]],
                 order=[0, 4, 2, 1, 3], stops=[[8, 8], [2, 2], [2, 1], [6, 3], [1, 1]],
                 initial_path=[[.5, .5], [4., 4.], [.5, .5]], fixed_plan_times=[])
    return scenarios


def test_geometry():
    tm = fixture()['tmap']
    start = (.5, .5)
    points = [(1., .5), (1., 1.), (3., 1.5), (4., 4.)]
    result = check_waypoints(tm.lethal, tm.cost, start, points)
    checks = result['points']
    assert [p['status'] for p in checks] == ['ok', 'blocked_cell', 'unreachable', 'unreachable']
    assert checks[1]['replacement_cell'] == [1, 2] and checks[1]['shift_m'] == .5
    assert checks[2]['replacement_cell'] == [4, 3] and checks[2]['shift_m'] == 1.
    assert checks[3]['replacement_cell'] is None and checks[3]['shift_m'] is None
    # Compare candidate ranking with independent A* searches, including ties.
    for item in checks[1:]:
        cell = np.array(item['cell'])
        candidates = sorted((int(((c-cell)**2).sum()), *c) for c in np.argwhere(~tm.lethal)
                            if ((c-cell)**2).sum() <= (1/RESOLUTION)**2)
        best = next(([int(x), int(y)] for _, x, y in candidates
                     if astar(tm.lethal, (1, 1), (x, y))['success']), None)
        assert item['replacement_cell'] == best
    # Two diagonally adjacent free squares must not connect.
    diagonal = np.ones((2, 2), bool)
    diagonal[0, 0] = diagonal[1, 1] = False
    answer = check_waypoints(diagonal, np.zeros((2, 2)), (0, 0), [(.5, .5)])
    assert answer['points'][0]['status'] == 'unreachable'
    invalid = check_waypoints(tm.lethal, tm.cost, (2.5, 1.), points)
    assert invalid['start']['status'] == 'blocked_cell'
    assert all(p['replacement_cell'] is None for p in invalid['points'])
    # Nearest distance is measured from the actual metre coordinates.
    off_grid = check_waypoints(tm.lethal, tm.cost, start, [(1.2, 1.)])['points'][0]
    assert off_grid['replacement_m'] == [1.5, 1.] and np.isclose(off_grid['shift_m'], .3)
    assert check_waypoints(tm.lethal, tm.cost, start, [(-2., 1.)])['points'][0]['reason'] == 'outside_map'
    assert substitute_all_skipped(tm)['planning_status'] == 'no_path'
    print('geometry PASS: statuses, 1 m boundary, closest A* cell/tie, no-corner-cut, off-grid and invalid start')


def substitute_all_skipped(tm):
    meta = dict(trial_scenarios()[0], points=[[8, 8]], order=[0, 1])
    result = waypoint_trial.substitute_waypoints(meta, tm)
    assert result['points'] == result['stops'] == result['initial_path'] == []
    assert result['waypoint_check']['points'][0]['action'] == 'skipped'
    return result


def reference_module():
    reference = ROOT/'tests/reference/lidar_checks_046base.py'
    module = ModuleType('lidar_checks_046base')
    vars(module).update(vars(lidar_checks))
    exec(compile(reference.read_text(), str(reference), 'exec'), vars(module))
    return module


def capture_launch(module, output, **options):
    """Run the real runner entry with deterministic ROS callbacks and inert processes."""
    sent, commands = [], []

    class Node:
        def __init__(self, name):
            pass

        def create_subscription(self, *args):
            pass

        def destroy_node(self):
            pass

        def create_publisher(self, kind, topic, depth):
            def publish(message):
                if topic == '/mission/command':
                    sent.append(message.data.encode())
            return SimpleNamespace(publish=publish, get_subscription_count=lambda: 1)

    def spin_once(observer, **kwargs):
        observer.t = 0. if observer.t is None else observer.t+5.
        observer.pose = [.5, .5, 0., 0., 0., 0.]
        observer.perception = {'ready': True}
        observer.state = dict(mission_id=1, status='completed' if observer.recording else 'running')

    def popen(command, **kwargs):
        commands.append([arg.replace(str(output), '<output>')
                         .split('/thesis-lidar-worlds-')[0]+'/<world>/'+Path(arg).name
                         if '/thesis-lidar-worlds-' in arg else arg.replace(str(output), '<output>')
                         for arg in command])
        return SimpleNamespace(poll=lambda: None, wait=lambda **kw: 0, pid=123)

    def export(_truth, world, **kwargs):
        world.mkdir()
        (world/'world.sdf').write_text('<sdf><world><physics><real_time_factor>1</real_time_factor></physics></world></sdf>')

    stubs = {'rclpy': SimpleNamespace(init=lambda: None, shutdown=lambda: None, spin_once=spin_once),
             'rclpy.node': SimpleNamespace(Node=Node),
             'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
             'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=object),
             'rosgraph_msgs.msg': SimpleNamespace(Clock=object),
             'std_msgs.msg': SimpleNamespace(String=SimpleNamespace, Empty=object),
             'thesis_bunker_mission.transport': SimpleNamespace(pose3d=lambda p: p)}
    with ExitStack() as stack:
        stack.enter_context(patch.dict(sys.modules, stubs))
        stack.enter_context(patch.dict(os.environ, clean_env(), clear=True))
        stack.enter_context(patch.object(module.subprocess, 'check_output', return_value='fixture'))
        stack.enter_context(patch.object(module.subprocess, 'Popen', side_effect=popen))
        stack.enter_context(patch.object(module.os, 'killpg'))
        stack.enter_context(patch.object(module, 'time', SimpleNamespace(perf_counter=lambda: 10., monotonic=lambda: 0.)))
        stack.enter_context(patch.object(module, 'case_world_inputs', return_value=(fixture(), fixture())))
        stack.enter_context(patch.object(module, 'scenario_to_mapfile'))
        stack.enter_context(patch.object(module, 'export_gazebo', side_effect=export))
        stack.enter_context(patch.object(module, 'use_mesh_visual'))
        stack.enter_context(patch.object(module, 'write_terrain_obj', side_effect=lambda z, path: path))
        stack.enter_context(patch.object(waypoint_trial, 'build_real', return_value=fixture()))
        scenarios = trial_scenarios()
        module.run_checks(output, finalize_report=False, scenarios=scenarios,
                          selected_patches=[scenarios[0]['patch']], **options)
    assert len(sent) == 1
    mission = (output/'raw'/scenarios[0]['patch']/'mission.json').read_bytes()
    return (output/'manifest.json').read_bytes(), sent[0], mission, commands


def test_default_and_dispatch(root):
    before = reference_module()
    # The 024 builder records run_fixed_mission wall time in fixed_plan_times.
    # Feed both versions one freshly built cohort so clock noise cannot alter bytes.
    with patch.dict(os.environ, clean_env(), clear=True):
        margin_cohort = edge_margin_checks.build_cohort()
    for mode, options in [('coarse', {}), ('fine', {'map_method': 'fine'}),
                          ('024', {'map_method': 'fine', 'edge_margin_m': 10})]:
        with patch.dict(os.environ, clean_env(), clear=True), \
                patch.object(edge_margin_checks, 'build_cohort', return_value=margin_cohort):
            baseline = root/f'{mode}-baseline'
            current = root/f'{mode}-none'
            before.prepare_cases(baseline, **options)
            lidar_checks.prepare_cases(current, waypoint_check='none', **options)
            assert (baseline/'manifest.json').read_bytes() == (current/'manifest.json').read_bytes()
    baseline = capture_launch(before, root/'old-run')
    assert capture_launch(lidar_checks, root/'new-run') == baseline
    assert capture_launch(lidar_checks, root/'none-run', waypoint_check='none') == baseline
    print('none PASS: three same-environment manifests, and command/mission bytes at a mocked live dispatch')

    manifest, payload, _, _ = capture_launch(lidar_checks, root/'substitute-run', waypoint_check='substitute')
    data, mission = json.loads(manifest), json.loads(payload)
    scenario = data['scenarios'][0]
    assert data['waypoint_check'] == 'substitute' and data['waypoint_check_radius_m'] == 1.
    assert [p['action'] for p in scenario['waypoint_check']['points']] == ['kept', 'substituted', 'substituted', 'skipped']
    assert scenario['points'] == [[2, 1], [1, 2], [4, 3]]
    assert mission['stops_cells'] == [[1, 2], [2, 1], [4, 3], [1, 1]]
    assert mission['order'] == [0, 2, 1, 3]
    assert mission['path'] == scenario['initial_path']
    assert np.array_equal(mission['points'], np.asarray(scenario['points'])*RESOLUTION)
    print('substitute PASS: replanned closed tour, skips and stable order in manifest and published command')


def test_cli_and_web(root):
    output = root/'cli'
    env = {**clean_env(), 'THESIS_FINE_PROTOCOL': 'rtf_check', 'THESIS_ONLY_PATCH': '08OB88_-0167'}
    subprocess.run([sys.executable, lidar_checks.__file__, '--map', 'fine', '--prepare-only',
                    '--waypoint-check', 'substitute', '--output', str(output)],
                   check=True, env=env, cwd=ROOT)
    manifest = json.loads((output/'manifest.json').read_bytes())
    selected = next(meta for meta in manifest['scenarios'] if meta['patch'] == '08OB88_-0167')
    assert selected['waypoint_check']['points'] and not (output/'raw').exists()
    try:
        lidar_checks.prepare_cases(root/'conflict', map_method='fine', endpoint_policy='escape_component',
                                   waypoint_check='substitute')
    except ValueError as error:
        assert 'endpoint-policy none' in str(error)
    else:
        raise AssertionError('substitute was combined with 028b')

    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK046_DOCKER_ARGS"\n')
    docker.chmod(0o755)
    args = root/'args'
    subprocess.run(['bash', str(Path(lidar_checks.__file__).with_name('run_lidar_checks.sh')),
                    str(root/'wrapper'), '--waypoint-check', 'substitute'], check=True,
                   env={**env, 'PATH': f'{root}:{os.environ["PATH"]}', 'TASK046_DOCKER_ARGS': str(args)})
    assert args.read_bytes().split(b'\0')[-3:] == [b'--waypoint-check', b'substitute', b'']
    with TestClient(server.app) as client, patch.object(server, 'load_map', return_value=fixture()):
        response = client.post('/api/waypoint-check',
                               json=dict(map_id='fixture', start=[.5, .5], points=[[1., 1.], [4., 4.]]))
        assert response.status_code == 200, response.text
        points = response.json()['points']
        assert points[0]['status'] == 'blocked_cell' and points[0]['replacement_m'] == [.5, 1.]
        assert points[1]['status'] == 'unreachable' and points[1]['replacement_m'] is None
    print('CLI/wrapper/API PASS: prepare-only, 028b conflict, forwarding and read-only preview')


if __name__ == '__main__':
    test_geometry()
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_default_and_dispatch(root)
        test_cli_and_web(root)
    print('all waypoint feasibility tests passed')
