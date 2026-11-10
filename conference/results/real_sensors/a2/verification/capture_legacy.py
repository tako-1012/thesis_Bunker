"""Freeze pre-A2 SDF/spec/wrapper bytes using Python and a fake Docker only."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'ros2_jazzy/src/thesis_bunker_gz'))
from tapp.sensor_geometry import DepthCameraSpec
from thesis_bunker_gz.model import make_model

BASE = '0009471'


def main():
    paths = ['conference/tapp/sensor_geometry.py',
             'conference/ros2_jazzy/src/thesis_bunker_gz/thesis_bunker_gz/depth_camera.py',
             'conference/ros2_jazzy/gz_checks/run_lidar_checks.sh']
    subprocess.run(['git', 'diff', '--exit-code', BASE, '--', *paths], cwd=REPO, check=True, capture_output=True)
    destination = OUT/'legacy'
    destination.mkdir()  # Never overwrite the captured pre-change fixtures.
    for name, kwargs in [('default.sdf', {}), ('lidar.sdf', dict(lidar=True)),
                         ('real_lidar.sdf', dict(sensor_preset='real_bunker')),
                         ('depth2.sdf', dict(sensor_preset='real_bunker', depth_cameras=True))]:
        make_model(destination/name, **kwargs)
    (destination/'depth_camera_spec.json').write_text(json.dumps(asdict(DepthCameraSpec()), sort_keys=True, indent=2)+'\n')
    captures = {}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        fake = root/'docker'
        fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["TASK027A2_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n')
        fake.chmod(0o755)
        env = dict(os.environ, PATH=str(root)+os.pathsep+os.environ['PATH'], TASK027A2_ARGS=str(root/'args.json'))
        for name in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S',
                     'THESIS_ROS_IMAGE', 'THESIS_ROS_DOMAIN_ID', 'THESIS_SOFTWARE_RENDERING'):
            env.pop(name, None)
        for name, extra in [('default', []), ('fine', ['--map', 'fine', '--sensors', 'lidar_real+depth2'])]:
            output = root/name
            subprocess.run(['bash', str(ROOT/'ros2_jazzy/gz_checks/run_lidar_checks.sh'), str(output), *extra],
                           env=env, check=True, capture_output=True)
            args = json.loads((root/'args.json').read_text())
            normalized = [arg.replace(str(ROOT), '<CONFERENCE>').replace(str(output), '<OUTPUT>') for arg in args]
            normalized = ['THESIS_OUTPUT_UID=<UID>' if arg.startswith('THESIS_OUTPUT_UID=') else
                          'THESIS_OUTPUT_GID=<GID>' if arg.startswith('THESIS_OUTPUT_GID=') else arg for arg in normalized]
            captures[name] = normalized
    (destination/'wrapper_args.json').write_text(json.dumps(captures, ensure_ascii=False, indent=2)+'\n')
    names = subprocess.check_output(['git', 'ls-files', 'conference'], cwd=REPO, text=True).splitlines()
    checksums = {name: hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in names}
    (OUT/'baseline_sha256.json').write_text(json.dumps(checksums, indent=2)+'\n')
    print('Captured unchanged baseline SDF/spec and default/fine Docker argv; fake Docker only.')
    print('Original tracked conference files:', len(checksums))


if __name__ == '__main__':
    main()
