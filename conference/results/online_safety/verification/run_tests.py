"""Run every Python test module in the dedicated venv, with two independent processes."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os,subprocess,sys
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
env=dict(os.environ,OPENBLAS_NUM_THREADS='1',MPLCONFIGDIR='/tmp/thesis-034-mpl',
         XDG_CACHE_HOME='/tmp/thesis-034-cache',PYTHONUNBUFFERED='1')
sources=sorted((ROOT/'tests').glob('test_*.py'))
def run(source):
    command=[sys.executable,'-m','tests.'+source.stem]
    result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    log='$ '+sys.executable+' -m tests.'+source.stem+'\n'+result.stdout+'\nexit='+str(result.returncode)+'\n'
    (OUT/(source.stem+'_log.txt')).write_text(log)
    return source.stem,result.returncode,log
results={}
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(run,source) for source in sources]):
        name,code,log=future.result();results[name]=(code,log)
        print(name+' exit='+str(code),flush=True)
        if code:print(log,flush=True)
        (OUT/'test_summary.txt').write_text('\n'.join(n+' exit='+str(v[0]) for n,v in sorted(results.items()))+'\n')
        (OUT/'all_tests_log.txt').write_text('\n'.join(v[1] for n,v in sorted(results.items())))
assert len(results)==len(sources)
sys.exit(any(code for code,log in results.values()))
