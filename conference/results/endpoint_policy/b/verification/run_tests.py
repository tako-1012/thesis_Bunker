"""Capture every test module's full output and retain each real exit status."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-028b-mpl',
           XDG_CACHE_HOME='/tmp/thesis-028b-cache', PYTHONUNBUFFERED='1')
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--resume', action='store_true', help='retain completed logs after an interrupted runner')
args = parser.parse_args()
sources = sorted((ROOT/'tests').glob('test_*.py'))
logs, outcomes = [], []
if args.resume:
    protocol = json.loads((OUT/'protocol.json').read_text())
    for name, checksum in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest() == checksum, name
    for source, line in zip(sources, (OUT/'test_summary.txt').read_text().splitlines(), strict=False):
        name, status = line.split(' exit=')
        assert name == source.stem, (name, source)
        code = int(status)
        log = (OUT/(name+'_log.txt')).read_text()
        assert log.startswith('$ python3 -m tests.'+name+'\n') and log.endswith('\nexit='+str(code)+'\n')
        logs.append(log)
        outcomes.append((name, code))
    print('Resuming after', len(outcomes), 'completed modules; previous nonzero statuses retained.', flush=True)
for source in sources[len(outcomes):]:
    name = source.stem
    result = subprocess.run([sys.executable, '-m', 'tests.'+name], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = '$ python3 -m tests.'+name+'\n'+result.stdout+'\nexit='+str(result.returncode)+'\n'
    (OUT/(name+'_log.txt')).write_text(log)
    logs.append(log)
    outcomes.append((name, result.returncode))
    (OUT/'all_tests_log.txt').write_text('\n'.join(logs))
    (OUT/'test_summary.txt').write_text('\n'.join(n+' exit='+str(c) for n, c in outcomes)+'\n')
    print(name, 'exit='+str(result.returncode), flush=True)
    if result.returncode:
        print(result.stdout[-6000:], flush=True)
        # Collect remaining independent modules; preserve this nonzero exit.
sys.exit(any(code for _, code in outcomes))
