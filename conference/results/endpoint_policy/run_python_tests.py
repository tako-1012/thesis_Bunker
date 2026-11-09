"""Run every Python test module, preserve complete output and nonzero exits."""
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent/'tests'
OUT.mkdir(exist_ok=True)
rows = []
for test in sorted((ROOT/'tests').glob('test_*.py')):
    module = 'tests.'+test.stem
    began = time.monotonic()
    try:
        result = subprocess.run([sys.executable, '-m', module], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as exc:
        output, code = (exc.stdout or b'')+b'\nTIMEOUT 300 seconds\n', 124
    (OUT/(test.stem+'.txt')).write_bytes(output)
    rows.append(dict(module=module, exit=code, seconds=round(time.monotonic()-began, 3)))
    (OUT/'status.json').write_text(json.dumps(rows, indent=2)+'\n')
    print(module, 'exit='+str(code), flush=True)
sys.exit(any(row['exit'] for row in rows))
