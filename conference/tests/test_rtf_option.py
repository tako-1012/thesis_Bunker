"""Task039 offline checks for the fine-run realtime factor and Docker forwarding."""

import ast
from contextlib import redirect_stdout
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import xml.etree.ElementTree as ET
from unittest.mock import patch

from ros2_jazzy.gz_checks import lidar_checks

ROOT = lidar_checks.ROOT
REFERENCE = ROOT/'tests/reference/rtf039_default.json'
ARCHIVE = ROOT/'results/rtf_check/hayashi_rtf1_check/rtf_1/physical_1'
LAUNCHER = Path(lidar_checks.__file__).with_name('run_lidar_checks.sh')
RTF_ENV = ('THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S', 'THESIS_FINE_PROTOCOL',
           'THESIS_ONLY_PATCH', 'LIBGL_ALWAYS_SOFTWARE')


def clean_env():
    return {key: value for key, value in os.environ.items() if key not in RTF_ENV}


def capture_default(*extra):
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True):
        output = Path(tmp)/'output'
        args = ['lidar_checks.py', '--map', 'fine', '--output', str(output), '--prepare-only', *extra]
        with patch.object(sys, 'argv', args), redirect_stdout(io.StringIO()) as console:
            lidar_checks.main()
        full = (output/'manifest.json').read_bytes()
        manifest = json.loads(full)
        environment = manifest.pop('input_environment')
        return dict(environment=environment, manifest_sha256=sha256(full).hexdigest(),
                    manifest_without_environment_sha256=sha256(
                        (json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()).hexdigest(),
                    files={f.name: sha256(f.read_bytes()).hexdigest() for f in sorted(output.iterdir())
                           if f.name != 'manifest.json'},
                    stdout_sha256=sha256(console.getvalue().encode()).hexdigest())


def test_default_bytes():
    expected = json.loads(REFERENCE.read_text())
    implicit = capture_default()
    explicit = capture_default('--real-time-factor', '0.3')
    assert implicit == explicit
    exact = implicit['environment'] == expected['environment']
    for snapshot in (implicit, expected):
        snapshot.pop('environment')
        if not exact:
            snapshot.pop('manifest_sha256')
    assert implicit == expected
    print('default 0.3 PASS: omitted/explicit match, manifest and report match pre-change hashes'
          + (' (full manifest)' if exact else ' (excluding interpreter metadata)'))


def test_overlay_settings():
    historical = json.loads((ARCHIVE/'manifest.json').read_text())
    comparable = ('map_method', 'world_max_pixels', 'lidar_spec', 'sensor_height_m',
                  'obstacle_height_m', 'obstacle_resolution_m', 'min_obstacle_points',
                  'obstacle_inflation_radius_m', 'history', 'terrain_visual',
                  'terrain_collision', 'world_input', 'real_time_factor', 'stale_timeout_s')
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True):
        root = Path(tmp)
        one = root/'one'
        with patch.object(sys, 'argv', ['lidar_checks.py', '--map', 'fine', '--prepare-only',
                                        '--output', str(one), '--real-time-factor=1.0']), \
                redirect_stdout(io.StringIO()) as console:
            lidar_checks.main()
        assert 'task023 aggregation requires 0.3x' in console.getvalue()
        assert sorted(p.name for p in one.iterdir()) == ['manifest.json']
        manifest = json.loads((one/'manifest.json').read_text())
        assert {key: manifest[key] for key in comparable} == {key: historical[key] for key in comparable}
        assert 'protocol' not in manifest
        control = lidar_checks.prepare_cases(root/'control', map_method='fine')
        assert manifest == dict(control, real_time_factor=1.)
        with patch.dict(os.environ, {'THESIS_REAL_TIME_FACTOR': '1.0'}):
            expect_invalid(root/'implicit_one', map_method='fine')
            control_over_env = lidar_checks.prepare_cases(root/'explicit', map_method='fine', real_time_factor=.3)
            assert control == control_over_env
            with patch.dict(os.environ, {'THESIS_FINE_PROTOCOL': 'rtf_check', 'THESIS_ONLY_PATCH': '08OB86_-0205'}):
                repeat = lidar_checks.prepare_cases(root/'legacy_repeat', map_method='fine')
                assert repeat['real_time_factor'] == 1.
                assert [c['patch'] for c in repeat['cases'] if c['selected']] == [
                    c['patch'] for c in historical['cases'] if c['selected']]
        with patch.dict(os.environ, {'THESIS_STALE_TIMEOUT_S': '.5'}):
            expect_invalid(root/'wrong_stale', map_method='fine', real_time_factor=1.)
        expect_invalid(root/'wrong_factor', map_method='fine', real_time_factor=.7)
        expect_invalid(root/'coarse', real_time_factor=1.)

    # Exercise the production world-setting assignment with the old audit's step.
    source = ast.parse(Path(lidar_checks.__file__).read_text())
    assignment = next(node for node in ast.walk(source) if isinstance(node, ast.Assign)
                      and ast.unparse(node.targets[0]) == "w.find('physics/real_time_factor').text")
    world = ET.fromstring('<world><physics><max_step_size>0.001</max_step_size>'
                          '<real_time_factor>0.3</real_time_factor></physics></world>')
    exec(compile(ast.Module(body=[assignment], type_ignores=[]), '<world settings>', 'exec'),
         dict(w=world, manifest=manifest, os=os))
    audit = (ARCHIVE/'world_audit.txt').read_text()
    assert float(world.findtext('physics/real_time_factor')) == 1. and '<real_time_factor>1</real_time_factor>' in audit
    assert '<max_step_size>0.001</max_step_size>' in audit and world.findtext('physics/max_step_size') == '0.001'
    assert manifest['lidar_spec']['update_hz'] == 10. and '<update_rate>10.0</update_rate>' in audit
    print('1.0 PASS: historical overlay manifest settings and world target match; stale=1.0, step=0.001, LiDAR=10Hz')
    print('validation PASS: explicit 0.3 overrides environment; legacy rtf_check still works; invalid factor, stale and coarse rejected')


def expect_invalid(output, **options):
    try:
        lidar_checks.prepare_cases(output, **options)
    except ValueError:
        return
    raise AssertionError(f'unexpected acceptance: {options}')


def test_live_entry_without_simulator():
    # Run the setup and finalization paths with zero selected cases. All ROS
    # calls and the Gazebo version probe are inert.
    stubs = {'rclpy': SimpleNamespace(init=lambda: None, shutdown=lambda: None),
             'rclpy.node': SimpleNamespace(Node=object),
             'rclpy.qos': SimpleNamespace(qos_profile_sensor_data=None),
             'geometry_msgs.msg': SimpleNamespace(PoseArray=object, Twist=object),
             'rosgraph_msgs.msg': SimpleNamespace(Clock=object),
             'std_msgs.msg': SimpleNamespace(String=object, Empty=object)}
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, clean_env(), clear=True), \
            patch.dict(sys.modules, stubs), patch.object(lidar_checks.subprocess, 'check_output', return_value='fixture'), \
            redirect_stdout(io.StringIO()) as console:
        output = Path(tmp)
        lidar_checks.run_checks(output, map_method='fine', real_time_factor=1., selected_patches=[])
        manifest = json.loads((output/'manifest.json').read_text())
        assert manifest['real_time_factor'] == 1. and manifest['execution'] == 'finished'
        assert 'task023 aggregation requires 0.3x' in console.getvalue()
        assert sorted(p.name for p in output.iterdir()) == ['manifest.json']
    print('run finalization PASS: explicit 1.0 preserves manifest and skips incompatible task023 summary')



def test_wrapper():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docker = root/'docker'
        docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK039_DOCKER_ARGS"\n')
        docker.chmod(0o755)
        argv_file = root/'argv'
        env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', TASK039_DOCKER_ARGS=str(argv_file))
        for flag in ((), ('--real-time-factor', '1.0'), ('--real-time-factor=0.3',)):
            subprocess.run(['bash', str(LAUNCHER), str(root/'output'), '--map', 'fine', *flag], check=True, env=env)
            argv = argv_file.read_bytes().decode().rstrip('\0').split('\0')
            assert argv[argv.index('bash', argv.index('-lc')+1)+1:] == ['--map', 'fine', *flag]
            assert 'THESIS_REAL_TIME_FACTOR=0.3' in argv
            assert 'THESIS_STALE_TIMEOUT_S=1.0' in argv
            if not flag:
                baseline = argv
            else:
                assert argv[:-len(flag)] == baseline
    print('wrapper PASS: split and equals options forward unchanged, with identical Docker setup')


if __name__ == '__main__':
    test_default_bytes()
    test_overlay_settings()
    test_wrapper()
    test_live_entry_without_simulator()
    print('all task039 RTF option tests passed')
