from pathlib import Path
import subprocess,sys,json,time
root=Path(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
results=[]
for test in sorted((root/'tests').glob('test_*.py')):
    start=time.monotonic()
    try:
        r=subprocess.run([sys.executable,'-m','tests.'+test.stem],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=240)
        code,log=r.returncode,r.stdout
    except subprocess.TimeoutExpired as e:
        code,log=124,(e.stdout or b'').decode() if isinstance(e.stdout,bytes) else (e.stdout or '')
    (out/(test.stem+'.txt')).write_text(log)
    results.append(dict(module='tests.'+test.stem,exit=code,seconds=round(time.monotonic()-start,2)))
    (out/'status.json').write_text(json.dumps(results,indent=2)+'\n')
    print(test.stem,code,flush=True)
sys.exit(any(r['exit'] for r in results))
