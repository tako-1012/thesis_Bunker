"""Freeze pre-task029 bytes and a digest of every untouched tracked file."""

import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
from unittest.mock import patch
import numpy as np
import scipy

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
BASE = '78ff634a9c83a39e821a0fee6832517978c724b2'
EDITABLE = ['conference/tapp/pointcloud_map_fine.py', 'conference/tapp/pointcloud_map_multi.py',
            'conference/ros2_jazzy/gz_checks/lidar_map.py', 'conference/ros2_jazzy/gz_checks/lidar_checks.py',
            'conference/ros2_jazzy/gz_checks/lidar_planner.py']


def untouched_digest():
    names = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', BASE, 'conference'], cwd=REPO, text=True).splitlines()
    digest = hashlib.sha256()
    for name in names:
        if name not in EDITABLE:
            digest.update(name.encode()+b'\0'+hashlib.sha256((REPO/name).read_bytes()).digest())
    return len(names), digest.hexdigest()


def main():
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == BASE
    assert not subprocess.check_output(['git', 'diff', '--name-only'], cwd=REPO, text=True).strip()
    from tests.test_ground_estimate import legacy_output_bytes, checksum
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        root = Path(temporary)
        for key in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S'):
            os.environ.pop(key, None)
        results = dict(mapping=legacy_output_bytes(root), manifests={},
                       environment=dict(python=sys.version, numpy=np.__version__))
        for name, kwargs in [('coarse', {}), ('fine', dict(map_method='fine')),
                             ('lidar_real', dict(map_method='fine', sensors='lidar_real')),
                             ('lidar_real+depth2', dict(map_method='fine', sensors='lidar_real+depth2'))]:
            folder = root/name
            manifest = prepare_cases(folder, **kwargs)
            full = checksum((folder/'manifest.json').read_bytes())
            manifest['input_environment'] = {}
            results['manifests'][name] = dict(full_sha256=full,
                without_environment_sha256=checksum((json.dumps(manifest, ensure_ascii=False, indent=2)+'\n').encode()))
    (OUT/'legacy_bytes.json').write_text(json.dumps(results, indent=2)+'\n')
    count, digest = untouched_digest()
    protocol = dict(base=BASE, branch='codex/029-ground-estimate', client_date='2026-11-10', client_timezone='Asia/Tokyo',
                    python=sys.version, numpy=np.__version__, scipy=scipy.__version__, platform=platform.platform(),
                    baseline_conference_files=count, untouched_sha256=digest, editable_existing_files=EDITABLE,
                    original_source_sha256={name: hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in EDITABLE},
                    reference_028b_commit='ad0f0a79f25ea2ce56c081ef33b595a232ed3827',
                    ground_threshold='existing obstacle_height_m=0.3, bilinear stale prior; no new threshold',
                    history='last 64 ALL returns, filtering only for the ground median',
                    gazebo_executed=False, docker_executed=False)
    (OUT/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
    print('Captured pre-change bytes: fine and both multi-sensor modes; four default manifests.')
    print('Baseline:', BASE, 'tracked conference files:', count, 'untouched digest:', digest)


if __name__ == '__main__':
    main()
