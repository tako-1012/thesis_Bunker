"""Capture all Python tests for the corrected task028b contract, no Gazebo."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REPO = ROOT.parent
def git(*args):
    return subprocess.check_output(['git', *args], cwd=REPO, text=True).strip()

sources = ['conference/tapp/endpoint_policy.py', 'conference/tests/test_endpoint_component.py']
base = git('rev-parse', 'HEAD')
protocol = dict(merge_commit=base, realtime_map=git('rev-parse', 'origin/realtime-map'),
                date='2026-11-11', timezone='Asia/Tokyo', python=sys.version,
                source_sha256={p: hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in sources},
                gazebo_executed=False)
digest = hashlib.sha256()
for name in git('ls-tree', '-r', '--name-only', base, 'conference').splitlines():
    if name not in sources and name != 'conference/results/endpoint_policy/b/REPORT_ja.md':
        digest.update(name.encode()+b'\0'+hashlib.sha256((REPO/name).read_bytes()).digest())
protocol['untouched_sha256'] = digest.hexdigest()
(OUT/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-finish-mpl',
           XDG_CACHE_HOME='/tmp/thesis-finish-cache', PYTHONUNBUFFERED='1')
logs, summary = [], []
for source in sorted((ROOT/'tests').glob('test_*.py')):
    command = [sys.executable, '-m', 'tests.'+source.stem]
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = '$ python3 -m tests.'+source.stem+'\n'+result.stdout+'\nexit='+str(result.returncode)+'\n'
    (OUT/(source.stem+'_log.txt')).write_text(log)
    logs.append(log)
    summary.append(source.stem+' exit='+str(result.returncode))
    (OUT/'all_tests_log.txt').write_text('\n'.join(logs))
    (OUT/'test_summary.txt').write_text('\n'.join(summary)+'\n')
    print(summary[-1], flush=True)
    if result.returncode:
        print(result.stdout, flush=True)
sys.exit(any(not row.endswith('exit=0') for row in summary))
