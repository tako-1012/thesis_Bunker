"""Run all conference test modules and retain their complete unedited output."""

import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-021-mpl',
           XDG_CACHE_HOME='/tmp/thesis-021-cache', PYTHONUNBUFFERED='1')
full, outcomes = [], []
for path in sorted((ROOT / 'tests').glob('test_*.py')):
    module = path.stem
    command = [sys.executable, '-m', 'tests.' + module]
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = '$ python3 -m tests.' + module + '\n' + result.stdout + '\nexit=' + str(result.returncode) + '\n'
    (OUT / (module + '_log.txt')).write_text(log)
    full.append(log)
    outcomes.append((module, result.returncode))
    (OUT / 'all_tests_log.txt').write_text('\n'.join(full))
    (OUT / 'test_summary.txt').write_text('\n'.join(name+' exit='+str(code) for name, code in outcomes)+'\n')
    print(module, 'exit=' + str(result.returncode), flush=True)
    if result.returncode:
        print(result.stdout[-6000:], flush=True)
        break
sys.exit(any(code for _, code in outcomes))
