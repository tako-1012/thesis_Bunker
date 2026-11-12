"""Record every real module exit, full output and synthetic box slopes."""

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-029-mpl',
           XDG_CACHE_HOME='/tmp/thesis-029-cache', PYTHONUNBUFFERED='1')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resume', action='store_true')
args = parser.parse_args()
protocol = json.loads((OUT/'protocol.json').read_text())
sources = protocol['editable_existing_files']+['conference/tests/test_ground_estimate.py']
hashes = {name: hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest() for name in sources}
if args.resume:
    assert hashes == protocol['source_sha256'], 'source changed since the interrupted run'
else:
    protocol['source_sha256'] = hashes
    (OUT/'protocol.json').write_text(json.dumps(protocol, ensure_ascii=False, indent=2)+'\n')
tests = sorted((ROOT/'tests').glob('test_*.py'))
logs, outcomes = [], []
if args.resume:
    for source, line in zip(tests, (OUT/'test_summary.txt').read_text().splitlines()):
        name, status = line.split(' exit=')
        assert name == source.stem
        code = int(status)
        log = (OUT/(name+'_log.txt')).read_text()
        assert log.endswith('\nexit='+str(code)+'\n')
        logs.append(log)
        outcomes.append((name, code))
    print('Resuming after', len(outcomes), 'completed modules; all real exits retained.', flush=True)
for source in tests[len(outcomes):]:
    command = [sys.executable, '-m', 'tests.'+source.stem]
    result = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = '$ python3 -m tests.'+source.stem+'\n'+result.stdout+'\nexit='+str(result.returncode)+'\n'
    (OUT/(source.stem+'_log.txt')).write_text(log)
    logs.append(log)
    outcomes.append((source.stem, result.returncode))
    (OUT/'all_tests_log.txt').write_text('\n'.join(logs))
    (OUT/'test_summary.txt').write_text('\n'.join(name+' exit='+str(code) for name, code in outcomes)+'\n')
    print(source.stem, 'exit='+str(result.returncode), flush=True)
    if result.returncode:
        print(result.stdout, end='', flush=True)

ground_output = (OUT/'test_ground_estimate_log.txt').read_text()
header = 'ground_estimate x y slope_deg steep box_lethal'
rows = [line.split() for line in ground_output.splitlines()
        if line.startswith(('all_returns ', 'non_obstacle '))]
assert len(rows) == 8, rows
with (OUT.parent/'box_slopes.csv').open('w', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow(header.split())
    writer.writerows(rows)
table = header+'\n'+'\n'.join(' '.join(row) for row in rows)+'\n'
(OUT.parent/'box_slopes_log.txt').write_text(table)
print(table, end='', flush=True)
print('Completed:', len(outcomes), 'failed:', sum(code != 0 for _, code in outcomes), flush=True)
sys.exit(any(code for _, code in outcomes))
