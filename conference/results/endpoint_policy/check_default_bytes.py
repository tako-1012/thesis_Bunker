"""Compare legacy default preparation bytes with the exact task028 base commit."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
BASE = '75d400a26aa7fe6d9ee29508af45e4621c7bb100'
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/'ros2_jazzy/gz_checks/lidar_checks.py'
old = subprocess.check_output(['git', 'show', BASE+':conference/ros2_jazzy/gz_checks/lidar_checks.py'], cwd=ROOT)
namespace = dict(__name__='task028_baseline', __file__=str(SOURCE))
exec(compile(old, str(SOURCE), 'exec'), namespace)
from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
rows = []
for method in ('coarse', 'fine'):
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        namespace['prepare_cases'](folder, map_method=method)
        before = (folder/'manifest.json').read_bytes()
        (folder/'manifest.json').unlink()
        prepare_cases(folder, map_method=method)
        after = (folder/'manifest.json').read_bytes()
        assert before == after
        rows.append(dict(map=method, equal=True, bytes=len(after), sha256=hashlib.sha256(after).hexdigest()))
content = json.dumps(dict(base=BASE, default_manifest=rows), indent=2)+'\n'
(Path(__file__).parent/'default_bytes.json').write_text(content)
print(content, end='')
