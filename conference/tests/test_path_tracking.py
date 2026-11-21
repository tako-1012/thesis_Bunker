"""Task043 controller, vehicle dynamics, ROS wiring and same-host byte parity."""

from contextlib import ExitStack, contextmanager, redirect_stdout
import ast
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import numpy as np

from ros2_jazzy.gz_checks import lidar_checks
from tapp.pure_pursuit import PurePursuit
from tapp.robot_sim import simulate
from tapp.tracking import CornerSlowPursuit
from tapp.tracking_sim import lagged_velocity, simulate_tracking
from tests import test_review_fixes as ros_fixture
from tests.test_rtf_option import LAUNCHER, clean_env
from thesis_bunker_mission import online_runtime

ROOT = lidar_checks.ROOT
BASE_COMMIT = 'fa86d83aa72ad2eb086e8c1f448aa063971cfa9d'


def before_source(file):
    return subprocess.check_output(['git', 'show', f'{BASE_COMMIT}:{file.relative_to(ROOT.parent)}'],
                                   cwd=ROOT.parent)


def before_module(module):
    file = Path(module.__file__).resolve()
    old = ModuleType(module.__name__)
    old.__file__ = str(file)
    old.__package__ = module.__package__
    exec(compile(before_source(file), str(file), 'exec'), vars(old))
    return old


@contextmanager
def fixture_cohort(root, *modules):
    baseline = root/'archived_cases'
    baseline.mkdir()
    patches = [dict(name=f'fixture_{i}') for i in range(10)]
    scenarios = [dict(patch=row['name'], planning_status='success') for row in patches]
    (baseline/'manifest.json').write_text(json.dumps(dict(scenarios=scenarios)))
    with ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch.multiple(module, BASELINE=baseline, list_patches=lambda *_args, **_kw: patches))
        yield


def run_node(mode, folder, *, tracking=None):
    node = ros_fixture.follower_node(mode, folder)
    if tracking is not None:
        node.tracking = tracking
    mission = dict(id=1, map_id='fixture', path=[[0., 0.], [3., 0.], [3., 3.]],
                   revision=1, n_replans=0, leg_index=0, final_leg=True, plan_history=[])

    def send(command):
        node.on_mission(SimpleNamespace(data=json.dumps(command)))

    with patch('time.monotonic', return_value=0.):
        send(mission)
        initial = node.follower.controller
        ros_fixture.drive(node, 0., 0., 0.)
        ros_fixture.drive(node, .5, 1., .2)
        saved_log = node.log
        replacement = dict(mission, path=[[1., .2], [4., .2], [4., 3.]], replace_path=True,
                           revision=2, reason='fixture', n_replans=1, plan_time_s=.01,
                           handoff_latency_s=.02, sim_handoff_s=.05, pose_shift_m=.1)
        send(replacement)
        assert node.follower is not None and node.log is saved_log
        ros_fixture.drive(node, 1., 2., .2)
        ros_fixture.drive(node, 1.5, 3., .2, tilt=26.)
        if mode != 'none':
            assert node.last_status == 'unsafe_tilt'
        elif node.last_status != 'running':
            raise AssertionError(node.last_status)
        if tracking == 'corner_slow':
            assert isinstance(initial, CornerSlowPursuit)
            assert isinstance(node.follower.controller, CornerSlowPursuit) and node.follower.controller is not initial
        node.stop()
    files = {file.name: file.read_bytes() for file in folder.glob('*/*') if file.is_file()}
    return json.dumps((node.commands, node.states)).encode(), files


def test_legacy_bytes():
    old_checks = before_module(lidar_checks)
    old_runtime = before_module(online_runtime)
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True), \
            fixture_cohort(Path(tmp), old_checks, lidar_checks):
        root = Path(tmp)
        old_follower = root/'path_follower_before.py'
        old_follower.write_bytes(before_source(ros_fixture.FOLLOWER))
        for mode in ('none', 'v1', 'v2'):
            before, after, explicit = (root/f'{mode}-{part}' for part in ('before', 'after', 'explicit'))
            kwargs = dict(map_method='fine', online_fixes=mode)
            old_checks.prepare_cases(before, **kwargs)
            lidar_checks.prepare_cases(after, **kwargs)
            lidar_checks.prepare_cases(explicit, tracking='default', **kwargs)
            assert len({(folder/'manifest.json').read_bytes() for folder in (before, after, explicit)}) == 1
            with patch.object(ros_fixture, 'FOLLOWER', old_follower), \
                    patch.object(online_runtime, 'replace_running_path', old_runtime.replace_running_path):
                expected = run_node(mode, before/'logs')
            assert expected == run_node(mode, after/'logs') == run_node(mode, explicit/'logs', tracking='default')
    print('1 PASS: before/current same-host manifest, ROS states, commands, trajectory, replan and stop bytes for none/v1/v2')


def test_corner_speed():
    straight = [[0., 0.], [6., 0.]]
    assert CornerSlowPursuit(straight).command([1., 0., 0.]) == PurePursuit(straight).command([1., 0., 0.])
    corner = [[0., 0.], [3., 0.], [4.5, 1.5*math.sqrt(3)]]
    ctl = CornerSlowPursuit(corner)
    assert ctl.command([.5, 0., 0.]) == (1., 0., False)
    speed, omega, done = ctl.command([1.5, 0., 0.])
    assert math.isclose(speed, .5, abs_tol=1e-14) and omega == 0. and not done
    for degrees in (44., 45.):
        assert CornerSlowPursuit(straight).command([1., 0., math.radians(degrees)])[0] > 0
    assert CornerSlowPursuit(straight).command([1., 0., math.radians(45.1)]) == (0., -1., False)
    assert CornerSlowPursuit(straight).command([1., 0., math.radians(-60.)]) == (0., 1., False)
    assert PurePursuit(straight).command([1., 0., math.radians(60.)])[0] > 0
    print('2 PASS: straight speed, 2m corner window, 60-degree 0.5 m/s cap and strict 45-degree spin')


def test_models():
    dt = .05
    v = w = 0.
    for _ in range(6):
        v, w = lagged_velocity(v, w, 1., 1., dt)
    assert np.allclose((v, w), np.array([1., .8])*(1-math.exp(-1)), atol=1e-14, rtol=0.)
    decay = lagged_velocity(v, w, 0., 0., .3)
    assert np.allclose(decay, np.array([v, w])*math.exp(-1), atol=1e-14, rtol=0.)
    for _ in range(300):
        v, w = lagged_velocity(v, w, 1., 1., dt)
    assert np.allclose((v, w), (1., .8), atol=1e-14, rtol=0.)
    path = [[3., 3.], [6., 3.], [6., 6.]]
    pose = [3., 3., 0.]
    sc = dict(tmap=SimpleNamespace(lethal=np.zeros((20, 20), bool), shape=(20, 20)))
    baseline = simulate(sc, path, pose)
    reproduced = simulate_tracking(path, pose)
    assert all(reproduced[key] == baseline[key] for key in reproduced)
    delayed = simulate_tracking(path, pose, lagged=True)
    assert delayed['completed'] and delayed['trajectory'][1][1]-pose[0] < dt
    print('3 PASS: 0.3 s rise/decay, 80% steady turn response, no-lag trace equals robot_sim')


def test_opt_in_wiring():
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True), \
            fixture_cohort(Path(tmp), lidar_checks):
        root = Path(tmp)
        for mode in ('none', 'v1', 'v2'):
            run_node(mode, root/mode, tracking='corner_slow')
        out = root/'prepare'
        with patch.object(sys, 'argv', ['lidar_checks.py', '--map', 'fine', '--prepare-only',
                                        '--online-fixes', 'v2', '--tracking', 'corner_slow', '--output', str(out)]), \
                redirect_stdout(io.StringIO()):
            lidar_checks.main()
        manifest = json.loads((out/'manifest.json').read_text())
        assert manifest['tracking'] == 'corner_slow' and manifest['online_fixes'] == 'v2'
        assert manifest['tracking_settings'] == dict(corner_lookahead_m=2., min_speed_fraction=.3,
                                                     spin_heading_error_deg=45.)
        source = ast.parse(Path(lidar_checks.__file__).read_text())
        branch = next(node for node in ast.walk(source) if isinstance(node, ast.If)
                      and 'tracking' in ast.unparse(node.test)
                      and any('commands' in ast.unparse(statement) for statement in node.body))
        commands = [['follower'], ['planner']]
        exec(compile(ast.Module(body=[branch], type_ignores=[]), '<ROS command>', 'exec'),
             dict(commands=commands, manifest=manifest))
        assert commands == [['follower', '-p', 'tracking:=corner_slow'], ['planner']]
        docker = root/'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK043_ARGV"\n')
        docker.chmod(0o755)
        argv = root/'argv'
        env = dict(os.environ, PATH=f'{root}:{os.environ["PATH"]}', TASK043_ARGV=str(argv))
        subprocess.run(['bash', str(LAUNCHER), str(root/'wrapper'), '--map', 'fine',
                        '--tracking', 'corner_slow'], check=True, env=env)
        assert argv.read_bytes().split(b'\0')[-3:] == [b'--tracking', b'corner_slow', b'']
    print('wiring PASS: opt-in initial/replacement paths with none/v1/v2, manifest, ROS args and Docker stub')


if __name__ == '__main__':
    test_legacy_bytes()
    test_corner_speed()
    test_models()
    test_opt_in_wiring()
    print('all task043 tracking tests passed')
