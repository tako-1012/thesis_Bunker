"""Tasks 045/056 rendering, byte parity and offline comparison without Docker or ROS/GPU."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
from unittest.mock import patch

import numpy as np

from results.gpu_rendering import cloud_pair
from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.gpu_rendering import save_renderer
from tests.test_rtf_option import LAUNCHER, clean_env
from tests.test_waypoint_feasibility import capture_launch

ROOT = lidar_checks.ROOT
BASE = 'a04805767d4259f0d7f40f17288f2eb8a1facb55'
BASE_056 = '9014c19ec3ec8598bf0824674316842e46e88ae2'
EGL_ENV = '__EGL_VENDOR_LIBRARY_FILENAMES'
EGL_VENDOR_FILE = '/usr/share/glvnd/egl_vendor.d/10_nvidia.json'
ARCHIVE = ROOT/'results/gpu_check_054'


def before_bytes(path, base=BASE):
    return subprocess.check_output(['git', 'show', f'{base}:{path.relative_to(ROOT.parent)}'],
                                   cwd=ROOT.parent)


def before_checks(base=BASE):
    file = Path(lidar_checks.__file__)
    module = ModuleType(lidar_checks.__name__)
    module.__file__ = str(file)
    module.__package__ = lidar_checks.__package__
    exec(compile(before_bytes(file, base), str(file), 'exec'), vars(module))
    return module


def capture_argv(root, script, mode=None, status=0, args=()):
    docker = root/'docker'
    docker.write_text('#!/bin/bash\nprintf "%s\\0" "$@" >"$TASK045_ARGS"\nexit "$TASK045_STATUS"\n')
    docker.chmod(0o755)
    arg_file = root/'argv'
    arg_file.unlink(missing_ok=True)
    env = dict(clean_env(), PATH=f'{root}:{os.environ["PATH"]}', TASK045_ARGS=str(arg_file),
               TASK045_STATUS=str(status), THESIS_FINE_PROTOCOL='rtf_check',
               THESIS_ONLY_PATCH='08OB88_-1417', THESIS_SOFTWARE_RENDERING='1', LIBGL_ALWAYS_SOFTWARE='1',
               **{EGL_ENV: '/host/ignore-this.json'})
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
        old, previous, new = scripts/'old.sh', scripts/'previous.sh', scripts/'new.sh'
        old.write_bytes(before_bytes(LAUNCHER))
        previous.write_bytes(before_bytes(LAUNCHER, BASE_056))
        new.write_bytes(LAUNCHER.read_bytes())
        fine_args = ('--map', 'fine', '--real-time-factor', '1.0')
        for args in ((), fine_args):
            expected, before = capture_argv(root, old, args=args)
            assert before.returncode == 0
            recent, before = capture_argv(root, previous, args=args)
            assert before.returncode == 0 and recent == expected
            for mode in (None, 'cpu'):
                actual, result = capture_argv(root, new, mode, args=args)
                assert result.returncode == 0 and expected == actual
        # Use the actual shell checks with a fixture file in place of the host path.
        vendor = root/'vendor definitions/10_nvidia.json'
        assert EGL_VENDOR_FILE in LAUNCHER.read_text()
        new.write_text(LAUNCHER.read_text().replace(EGL_VENDOR_FILE, shlex.quote(str(vendor))))
        missing, stopped = capture_argv(root, new, 'gpu', args=fine_args)
        assert missing is None and stopped.returncode == 2
        assert b'readable NVIDIA EGL vendor file' in stopped.stderr and os.fsencode(vendor) in stopped.stderr
        vendor.parent.mkdir()
        vendor.write_text('{"file_format_version":"1.0.0","ICD":{"library_path":"libEGL_nvidia.so.0"}}\n')
        actual, result = capture_argv(root, new, 'gpu', args=fine_args)
        assert result.returncode == 0
        argv = actual.decode().split('\0')[:-1]
        assert argv[argv.index('--gpus')+1] == 'all'
        assert 'THESIS_RENDER=gpu' in argv and 'NVIDIA_DRIVER_CAPABILITIES=all' in argv
        assert not any(arg.startswith('LIBGL_ALWAYS_SOFTWARE=') for arg in argv)
        assert 'unset LIBGL_ALWAYS_SOFTWARE DISPLAY WAYLAND_DISPLAY\n' in argv[argv.index('-lc')+1]
        assert tuple(argv[-4:]) == fine_args
        mounts = [value for flag, value in zip(argv, argv[1:]) if flag == '-v']
        assert f'{vendor}:{vendor}:ro' in mounts
        assert f'{EGL_ENV}={vendor}' in argv and f'{EGL_ENV}=/host/ignore-this.json' not in argv
        _, failed = capture_argv(root, new, 'gpu', status=125)
        assert failed.returncode == 125 and b'NVIDIA Container Toolkit' in failed.stderr
        missing, invalid = capture_argv(root, new, 'bad')
        assert missing is None and invalid.returncode == 2
    print('Docker PASS: implicit/explicit CPU argv and env byte-identical to 045 and 056 bases; '
          'GPU mounts read-only vendor, forces EGL selection, rejects missing file before Docker, preserves toolkit errors')


def test_manifest():
    old = before_checks()
    previous = before_checks(BASE_056)
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {}, clear=True):
        root = Path(tmp)
        profiles = [('coarse', {}), ('fine', {}), ('fine', dict(THESIS_FINE_PROTOCOL='rtf_check',
                                                                THESIS_ONLY_PATCH='08OB88_-1417', LIBGL_ALWAYS_SOFTWARE='1'))]
        for i, (method, env) in enumerate(profiles):
            with patch.dict(os.environ, env, clear=True):
                before = root/f'before{i}'
                old.prepare_cases(before, map_method=method)
                expected = (before/'manifest.json').read_bytes()
                recent = root/f'recent{i}'
                previous.prepare_cases(recent, map_method=method)
                assert (recent/'manifest.json').read_bytes() == expected
                for label, mode in (('implicit', {}), ('explicit', {'THESIS_RENDER': 'cpu'})):
                    output = root/f'{label}{i}'
                    with patch.dict(os.environ, mode):
                        lidar_checks.prepare_cases(output, map_method=method)
                    assert (output/'manifest.json').read_bytes() == expected
        profile = dict(THESIS_FINE_PROTOCOL='rtf_check', THESIS_ONLY_PATCH='08OB88_-1417')
        options = dict(map_method='fine', real_time_factor=1., sensors='lidar_real+depth2')
        with patch.dict(os.environ, profile):
            old.prepare_cases(root/'cpu', **options)
        with patch.dict(os.environ, dict(profile, THESIS_RENDER='gpu', **{EGL_ENV: EGL_VENDOR_FILE})):
            lidar_checks.prepare_cases(root/'gpu', **options)
        cpu = json.loads((root/'cpu/manifest.json').read_bytes())
        gpu = json.loads((root/'gpu/manifest.json').read_bytes())
        assert gpu.pop('rendering') == dict(mode='gpu', engine='ogre2', backend='EGL', egl_vendor_file=EGL_VENDOR_FILE)
        assert gpu == cpu
        with patch.dict(os.environ, dict(profile, THESIS_RENDER='cpu', **{EGL_ENV: '/ignored.json'})):
            assert capture_launch(previous, root/'live-before', **options) == capture_launch(
                lidar_checks, root/'live-after', **options)
    print('manifest PASS: CPU preparation and final mocked dispatch byte parity; GPU records passed EGL vendor only')


def test_renderer_and_clouds():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        home = root/'server'
        ogre = home/'.gz/rendering/ogre2.log'
        raw = root/'raw'
        raw.mkdir()
        unverified = dict(gl_vendor=None, gl_renderer=None, gpu_rendered=None)
        assert save_renderer(home, raw) == dict(renderer=None, ogre_log=None, **unverified)
        ogre.parent.mkdir(parents=True)
        ogre.write_text('12:34:56: RenderSystem Name: OpenGL 3+\n'
                        '12:34:56: GPU Vendor: nvidia\n'
                        '12:34:56: Device Name: NVIDIA GeForce RTX 5060 Laptop GPU\n')
        assert save_renderer(home, raw) == dict(renderer='NVIDIA GeForce RTX 5060 Laptop GPU',
                                               ogre_log='ogre2.log', **unverified)
        assert (raw/'ogre2.log').read_bytes() == ogre.read_bytes()
        ogre.write_text('12:34:56: GL_RENDERER = llvmpipe (LLVM 20)\n')
        assert save_renderer(home, raw)['renderer'] == 'llvmpipe (LLVM 20)'
        shutil.copyfile(ARCHIVE/'gpu/ogre2_live.log', ogre)
        mesa = save_renderer(home, raw)
        assert mesa['gl_vendor'] == 'Mesa' and mesa['gpu_rendered'] is False
        assert mesa['gl_renderer'] == mesa['renderer'] == 'llvmpipe (LLVM 20.1.2, 256 bits)'
        with ogre.open('a') as stream:
            stream.write('12:35:00: GL_VENDOR = NVIDIA Corporation\n')
        assert save_renderer(home, raw)['gpu_rendered'] is None  # Second context is partial.
        with ogre.open('a') as stream:
            stream.write('12:35:00: GL_RENDERER = GeForce RTX 5060 Laptop GPU/PCIe/SSE2\n')
        nvidia = save_renderer(home, raw)
        assert nvidia['gl_vendor'] == 'NVIDIA Corporation' and nvidia['gpu_rendered'] is True
        assert nvidia['gl_renderer'] == 'GeForce RTX 5060 Laptop GPU/PCIe/SSE2'

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
    print('renderer/cloud PASS: 054 Mesa/llvmpipe, sample NVIDIA and partial contexts; '
          'earliest pre-motion common stamp and matched pose range statistics')


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
        incomplete = root/'gpu/physical_1/clouds'
        incomplete.mkdir()
        (incomplete/'poses.npz').write_bytes(b'PK\x03\x04')
        with redirect_stdout(io.StringIO()) as output:
            assert cloud_pair.compare(root) == 2
        summary = json.loads(output.getvalue())
        assert summary['gpu_over_cpu_rtf'] == 2.
        assert all(c['status'] == 'pose_record_error' for c in summary['clouds'].values())
    print('summary PASS: valid renderer/RTF/GPU usage kept when a cloud pair is unavailable')


def test_gpu_manifest_checkpoint():
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'THESIS_RENDER': 'gpu', EGL_ENV: EGL_VENDOR_FILE}):
        root = Path(tmp)
        checkpoints = []

        def fake_renderer(home, raw):
            checkpoints.append(json.loads((root/'manifest.json').read_text()))
            ogre = home/'.gz/rendering/ogre2.log'
            ogre.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ARCHIVE/'gpu/ogre2_live.log', ogre)
            return save_renderer(home, raw)

        with patch.object(lidar_checks, 'save_renderer', side_effect=fake_renderer):
            manifest, _, _, commands = capture_launch(lidar_checks, root, map_method='fine')
        case, = [row for row in json.loads(manifest)['cases'] if row['selected']]
        assert '--render-engine' in commands[0] and case['rendering']['gpu_rendered'] is False
        first, second = checkpoints
        assert first['execution'] == second['execution'] == 'started'
        assert first['rendering']['egl_vendor_file'] == EGL_VENDOR_FILE
        for recorded in checkpoints:
            selected, = [row for row in recorded['cases'] if row['selected']]
            assert selected['run_folder'] == case['run_folder']
        selected, = [row for row in second['cases'] if row['selected']]
        assert selected['rendering']['gl_vendor'] == 'Mesa' and selected['rendering']['gpu_rendered'] is False
    print('GPU checkpoint PASS: run folder and Ogre2 verdict remain in the manifest before normal teardown')


def test_stopped_summary():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        gpu, cpu = (root/mode/'physical_1' for mode in ('gpu', 'cpu'))
        gpu.mkdir(parents=True)
        raw = cpu/'raw'
        raw.mkdir(parents=True)
        archived = json.loads((ARCHIVE/'gpu/manifest.json').read_text())
        selected, = [row for row in archived['cases'] if row['selected']]
        assert archived['execution'] == 'started' and selected['run_folder'] is None
        cpu_case = dict(selected=True, patch=selected['patch'], run_folder='raw', termination='completed')
        (cpu/'manifest.json').write_text(json.dumps(dict(real_time_factor=1., sensors='lidar_real+depth2',
            execution='finished', cases=[cpu_case], software_rendering='1')))
        (raw/'mission.json').write_text(json.dumps(dict(started_t=5., finished_t=15., wall_elapsed_s=20.)))

        def summarize():
            summary = root/'summary.json'
            with summary.open('w') as output:
                result = subprocess.run([sys.executable, cloud_pair.__file__, 'compare', str(root)], stdout=output)
            assert result.returncode == 2
            data = json.loads(summary.read_text())
            assert data['trials']['cpu']['measured_rtf'] == .5
            assert data['gpu_over_cpu_rtf'] is None and not data['nvidia_renderer_confirmed']
            assert all(c['status'] == 'no_paired_trial' for c in data['clouds'].values())
            trial = data['trials']['gpu']
            assert trial['patch'] == selected['patch'] and trial['execution'] == 'started'
            assert trial['sim_s'] is trial['wall_s'] is trial['measured_rtf'] is None
            return trial

        (gpu/'manifest.json').write_text(json.dumps(archived))
        assert 'run_folder was not recorded (execution=started)' in summarize()['error']
        shutil.copyfile(ARCHIVE/'gpu/stopped.txt', gpu.parent/'stopped.txt')
        assert 'selected Ogre2 renderer is llvmpipe' in summarize()['stop_reason']
        selected.update(run_folder='raw', rendering=dict(renderer='llvmpipe', gl_vendor='Mesa',
                                                            gl_renderer='llvmpipe', gpu_rendered=False))
        (gpu/'manifest.json').write_text(json.dumps(archived))
        (gpu/'raw').mkdir()
        (gpu/'raw/mission.json').write_text('{"status":"running","started_t":5}')
        trial = summarize()
        assert trial['gpu_rendered'] is False and trial['gl_vendor'] == 'Mesa'
        assert 'mission timing is incomplete (status=running)' in trial['error']
        (gpu.parent/'exit.txt').write_text('143\n')
        assert 'trial stopped with exit code 143' in summarize()['error']
    print('partial summary PASS: 054 GPU manifest without run_folder, interrupted mission and signal exit keep CPU fields')


if __name__ == '__main__':
    test_docker_arguments()
    test_manifest()
    test_renderer_and_clouds()
    test_summary()
    test_gpu_manifest_checkpoint()
    test_stopped_summary()
    print('all task045/056 GPU rendering tests passed')
