"""Freeze the legacy replay and preparation outputs before adding task028b."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
from experiments.endpoint_replay import replay
from ros2_jazzy.gz_checks.lidar_checks import prepare_cases


def main():
    subprocess.run(['git', 'diff', '--exit-code', '0009471', '--', 'conference/tapp/endpoint_policy.py',
                    'conference/ros2_jazzy/gz_checks/endpoint_runtime.py',
                    'conference/ros2_jazzy/gz_checks/lidar_checks.py',
                    'conference/experiments/endpoint_replay.py'], cwd=REPO, check=True, capture_output=True)
    destination = OUT/'legacy'
    destination.mkdir()
    (destination/'replay.json').write_text(json.dumps(replay(), ensure_ascii=False, indent=2)+'\n')
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        for key in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S'):
            os.environ.pop(key, None)
        for name, kwargs in [('coarse', {}), ('fine', dict(map_method='fine')),
                             ('escape', dict(map_method='fine', endpoint_policy='escape')),
                             ('escape_diag', dict(map_method='fine', endpoint_policy='escape', diagnostics=True))]:
            folder = Path(temporary)/name
            prepare_cases(folder, **kwargs)
            (destination/(name+'_manifest.json')).write_bytes((folder/'manifest.json').read_bytes())
    names = subprocess.check_output(['git', 'ls-files', 'conference'], cwd=REPO, text=True).splitlines()
    data = {name: hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in names}
    (OUT/'baseline_sha256.json').write_text(json.dumps(data, indent=2)+'\n')
    print('Captured legacy none/escape preparation bytes and three-case escape replay; Python only.')
    print('Original tracked conference files:', len(data))


if __name__ == '__main__':
    main()
