"""Refresh display-only replay labels and rerun the dependent contract test."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

VERIFY = Path(__file__).resolve().parent
ROOT = VERIFY.parents[3]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-028b-mpl',
           XDG_CACHE_HOME='/tmp/thesis-028b-cache', PYTHONUNBUFFERED='1')
protocol = json.loads((VERIFY/'protocol.json').read_text())
name = 'conference/experiments/endpoint_replay.py'
previous = protocol['source_sha256'][name]
for source, checksum in protocol['source_sha256'].items():
    if source != name:
        assert hashlib.sha256((ROOT.parent/source).read_bytes()).hexdigest() == checksum, source
protocol['source_sha256'][name] = hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest()
protocol['report_label_revision'] = dict(
    reason='Only compare_replay failure display changed to no_path; no runtime or planner change. '
           'Replay and its dependent test rerun after the complete suite.',
    previous_replay_sha256=previous,
    final_replay_sha256=protocol['source_sha256'][name])
(VERIFY/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
result = subprocess.run([sys.executable, '-m', 'experiments.endpoint_replay', '--compare',
                         '--output', 'results/endpoint_policy/b'], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
(VERIFY/'replay_console_log.txt').write_text(result.stdout)
print(result.stdout, end='', flush=True)
assert result.returncode == 0
result = subprocess.run([sys.executable, '-m', 'tests.test_endpoint_component'], cwd=ROOT, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
log = '$ python3 -m tests.test_endpoint_component\n'+result.stdout+'\nexit='+str(result.returncode)+'\n'
(VERIFY/'component_log.txt').write_text(result.stdout)
(VERIFY/'test_endpoint_component_log.txt').write_text(log)
summary, logs = [], []
for source in sorted((ROOT/'tests').glob('test_*.py')):
    log = (VERIFY/(source.stem+'_log.txt')).read_text()
    code = int(log.rstrip().rsplit('\nexit=', 1)[1])
    logs.append(log)
    summary.append(source.stem+' exit='+str(code))
(VERIFY/'all_tests_log.txt').write_text('\n'.join(logs))
(VERIFY/'test_summary.txt').write_text('\n'.join(summary)+'\n')
print(result.stdout, end='', flush=True)
print('test_endpoint_component exit='+str(result.returncode), flush=True)
sys.exit(result.returncode)
