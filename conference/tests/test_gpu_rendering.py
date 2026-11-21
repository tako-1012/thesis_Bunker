"""Task045 byte parity and opt-in arguments, with no Docker daemon or ROS/GPU."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import ModuleType
from unittest.mock import patch

import numpy as np

from results.gpu_rendering import cloud_pair
from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.gpu_rendering import save_renderer
from tests.test_rtf_option import LAUNCHER, clean_env

ROOT = lidar_checks.ROOT
BASE = 'a04805767d4259f0d7f40f17288f2eb8a1facb55'


def before_bytes(path):
    return subprocess.check_output(['git', 'show', f'{BASE}:{path.relative_to(ROOT.parent)}'],
                                   cwd=ROOT.parent)


def before_checks():
    file = Path(lidar_checks.__file__)
    module = ModuleType(lidar_checks.__name__)
    module.__file__ = str(file)
    module.__package__ = lidar_checks.__package__
    exec(compile(before_bytes(file), str(file), 'exec'), vars(module))
    return module


def capture_argv(root, script, mode=None, status=0, args=()):
    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK045_ARGS"\nexit "$TASK045_STATUS"\n')
    docker.chmod(0o755)
    arg_file = root/'argv'
    arg_file.unlink(missing_ok=True)
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', TASK045_ARGS=str(arg_file),
               TASK045_STATUS=str(status), THESIS_FINE_PROTOCOL='rtf_check',
               THESIS_ONLY_PATCH='08OB88_-1417', THESIS_SOFTWARE_RENDERING='1', LIBGL_ALWAYS_SOFTWARE='1')
    env.pop('THESIS_RENDER', None)
    if mode is not None:
        env['THESIS_RENDER'] = mode
    command = ['bash', str(script), str(root/'out'), *args]
    result = subprocess.run(command, env=env, capture_output=True)
    return arg_file.read_bytes() if arg_file.exists() else None, result


def test_docker_arguments():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        scripts = root/'conference/ros2_jazzy/gz_checks'
        scripts.mkdir(parents=True)
        old, new = scripts/'old.sh', scripts/'new.sh'
        old.write_bytes(before_bytes(LAUNCHER))
        new.write_bytes(LAUNCHER.read_bytes())
        fine_args = ('--map', 'fine', '--real-time-factor', '1.0')
        for args in ((), fine_args):
            expected, before = capture_argv(root, old, args=args)
            assert before.returncode == 0
            for mode in (None, 'cpu'):
                actual, result = capture_argv(root, new, mode, args=args)
                assert result.returncode == 0 and expected == actual
        actual, result = capture_argv(root, new, 'gpu', args=fine_args)
        assert result.returncode == 0
        argv = actual.decode().split('\0')[:-1]
        assert argv[argv.index('--gpus')+1] == 'all'
        assert 'THESIS_RENDER=gpu' in argv and 'NVIDIA_DRIVER_CAPABILITIES=all' in argv
        assert not any(arg.startswith('LIBGL_ALWAYS_SOFTWARE=') for arg in argv)
        assert 'unset LIBGL_ALWAYS_SOFTWARE DISPLAY WAYLAND_DISPLAY\n' in argv[argv.index('-lc')+1]
        assert tuple(argv[-4:]) == fine_args
        _, failed = capture_argv(root, new, 'gpu', status=125)
        assert failed.returncode == 125 and b'NVIDIA Container Toolkit' in failed.stderr
        missing, invalid = capture_argv(root, new, 'bad')
        assert missing is None and invalid.returncode == 2
    print('Docker PASS: absent/explicit cpu byte-identical to base; gpu forwarding, toolkit error and invalid selection')


def test_manifest():
    old = before_checks()
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
        root = Path(tmp)
        profiles = [('coarse', {}), ('fine', {}), ('fine', dict(THESIS_FINE_PROTOCOL='rtf_check',
                                                                THESIS_ONLY_PATCH='08OB88_-1417', LIBGL_ALWAYS_SOFTWARE='1'))]
        for i, (method, env) in enumerate(profiles):
            with patch.dict(os.environ, env, clear=True):
                before = root/f'before{i}'
                old.prepare_cases(before, map_method=method)
                expected = (before/'manifest.json').read_bytes()
                for label, mode in (('implicit', {}), ('explicit', {'THESIS_RENDER': 'cpu'})):
                    output = root/f'{label}{i}'
                    with patch.dict(os.environ, mode):
                        lidar_checks.prepare_cases(output, map_method=method)
                    assert (output/'manifest.json').read_bytes() == expected
        profile = dict(THESIS_FINE_PROTOCOL='rtf_check', THESIS_ONLY_PATCH='08OB88_-1417')
        options = dict(map_method='fine', real_time_factor=1., sensors='lidar_real+depth2')
        with patch.dict(os.environ, profile):
            old.prepare_cases(root/'cpu', **options)
        with patch.dict(os.environ, dict(profile, THESIS_RENDER='gpu')):
            lidar_checks.prepare_cases(root/'gpu', **options)
        cpu = json.loads((root/'cpu/manifest.json').read_bytes())
        gpu = json.loads((root/'gpu/manifest.json').read_bytes())
        assert gpu.pop('rendering') == dict(mode='gpu', engine='ogre2', backend='EGL')
        assert gpu == cpu
    print('manifest PASS: cpu byte parity, also with historical protocol; gpu records mode without changing other fields')


def test_renderer_and_clouds():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home = root/'server'
        ogre = home/'.gz/rendering/ogre2.log'
        raw = root/'raw'
        raw.mkdir()
        assert save_renderer(home, raw) == dict(renderer=None, ogre_log=None)
        ogre.parent.mkdir(parents=True)
        ogre.write_text('12:34:56: RenderSystem Name: OpenGL 3+\n'
                        '12:34:56: GPU Vendor: nvidia\n'
                        '12:34:56: Device Name: NVIDIA GeForce RTX 5060 Laptop GPU\n')
        assert save_renderer(home, raw) == dict(renderer='NVIDIA GeForce RTX 5060 Laptop GPU', ogre_log='ogre2.log')
        assert (raw/'ogre2.log').read_bytes() == ogre.read_bytes()
        ogre.write_text('12:34:56: GL_RENDERER = llvmpipe (LLVM 20)\n')
        assert save_renderer(home, raw)['renderer'] == 'llvmpipe (LLVM 20)'

        folders = raw/'cpu', raw/'gpu'
        a = np.array([[[1., 0., 0.], [2., 0., 0.]], [[3., 0., 0.], [np.inf, 0., 0.]]])
        b = np.array([[[2., 0., 0.], [1., 0., 0.]], [[np.inf, 0., 0.], [4., 0., 0.]]])
        first, second = 100_000_000, 200_000_000
        for folder, xyz in zip(folders, (a, b), strict=True):
            folder.mkdir()
            for stamp in (first, second):
                np.savez(folder/f'lidar-{stamp}.npz', xyz=xyz, frame='fixture')
        pose = np.array([0., 0., 0., 0., 0., 0., 1.])
        shifted = pose+np.array([.002, 0., 0., 0., 0., 0., 0.])
        poses = [{first: pose, second: pose}, {first: shifted, second: pose}]
        result = cloud_pair.compare_sensor('lidar', folders, (second+1, second+1), poses)
        assert result['stamp_ns'] == second and result['status'] == 'compared'
        assert result['cpu_finite'] == result['gpu_finite'] == 3
        assert result['paired_finite'] == 2 and result['cpu_only'] == result['gpu_only'] == 1
        assert result['abs_range_difference_m'] == dict(median=1., p95=1., max=1.)
        assert result['range_gpu_minus_cpu_m']['median'] == 0.
        assert cloud_pair.compare_sensor('lidar', folders, (second, second+1), poses)['status'].startswith('no_common')
    print('renderer/cloud PASS: actual Ogre device extraction and fallback; earliest pre-motion common stamp and matched pose range statistics')


def test_summary():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for mode, seconds in (('cpu', 20.), ('gpu', 10.)):
            folder = root/mode
            physical = folder/'physical_1'
            raw = physical/'raw'
            raw.mkdir(parents=True)
            case = dict(selected=True, patch='fixture', run_folder='raw', termination='completed')
            manifest = dict(real_time_factor=1., sensors='lidar_real+depth2', execution='finished',
                            cases=[case], software_rendering='1' if mode == 'cpu' else None)
            if mode == 'gpu':
                manifest['rendering'] = dict(mode='gpu')
                case['rendering'] = dict(renderer='NVIDIA fixture')
            (physical/'manifest.json').write_text(json.dumps(manifest))
            (raw/'mission.json').write_text(json.dumps(dict(started_t=5., finished_t=15., wall_elapsed_s=seconds)))
            (folder/'gpu_usage.csv').write_text('2026/11/21 12:00:00, 0, device, 5, 0\n')
        with redirect_stdout(io.StringIO()) as output:
            assert cloud_pair.compare(root) == 2
        summary = json.loads(output.getvalue())
        assert summary['gpu_over_cpu_rtf'] == 2. and summary['nvidia_renderer_confirmed']
        assert summary['trials']['gpu']['wall_run_gpu_usage']['0 device']['max_pct'] == 5.
        assert summary['clouds']['camera1']['status'] == 'no_common_pre_mission_stamp_and_pose'
    print('summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable')


if __name__ == '__main__':
    test_docker_arguments()
    test_manifest()
    test_renderer_and_clouds()
    test_summary()
    print('all task045 GPU rendering tests passed')
