"""Capture every test module's full output; stop on failure without changing tests."""

import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-024-mpl',
           XDG_CACHE_HOME='/tmp/thesis-024-cache', PYTHONUNBUFFERED='1')
logs, outcomes = [], []
for source in sorted((ROOT/'tests').glob('test_*.py')):
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
        break
sys.exit(any(code for _, code in outcomes))
