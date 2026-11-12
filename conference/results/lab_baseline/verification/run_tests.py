"""Full Python test output in the dedicated task031 venv."""
from pathlib import Path
import os,subprocess,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
env = dict(os.environ, OPENBLAS_NUM_THREADS='1', MPLCONFIGDIR='/tmp/thesis-031-mpl',
           XDG_CACHE_HOME='/tmp/thesis-031-cache', PYTHONUNBUFFERED='1')
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
