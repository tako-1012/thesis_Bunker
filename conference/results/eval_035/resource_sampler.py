#!/usr/bin/env python3
"""Host resource sampler (stdlib, /proc + nvidia-smi); stops when a given file exists."""
import csv, os, subprocess, sys, time
from pathlib import Path
out, stop, period = Path(sys.argv[1]), Path(sys.argv[2]), float(sys.argv[3]) if len(sys.argv) > 3 else 5.
HZ = os.sysconf('SC_CLK_TCK')
def cpus():
    r = {}
    for line in open('/proc/stat'):
        p = line.split()
        if p[0].startswith('cpu') and p[0] != 'cpu':
            v = list(map(int, p[1:9]))
            r[p[0]] = (sum(v), v[3]+v[4])
    return r
def procs():
    r = {}
    for pid in filter(str.isdigit, os.listdir('/proc')):
        try:
            s = open(f'/proc/{pid}/stat').read()
        except OSError:
            continue
        c = s[s.index('(')+1:s.rindex(')')]
        f = s[s.rindex(')')+2:].split()
        r[pid] = (c, int(f[11])+int(f[12]))
    return r
def mem():
    m = {l.split(':')[0]: int(l.split()[1]) for l in open('/proc/meminfo')}
    return (m['MemTotal']-m['MemAvailable'])/1048576
def gpu():
    try:
        return subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,power.draw,temperature.gpu',
                                        '--format=csv,noheader,nounits'], text=True, timeout=5).strip().replace(' ', '')
    except Exception as exc:
        return 'error,error,error,'+type(exc).__name__
new = not out.exists()
with out.open('a', newline='') as f:
    w = csv.writer(f)
    if new:
        w.writerow(['wall', 'cpu_avg_pct', 'cpu_max_core_pct', 'mem_used_gib', 'gpu_util_pct', 'gpu_mem_mib', 'gpu_power_w', 'gpu_temp_c', 'top_procs_pct'])
    c0, p0, t0 = cpus(), procs(), time.time()
    while not stop.exists():
        time.sleep(period)
        c1, p1, t1 = cpus(), procs(), time.time()
        u = [100*(1-(c1[k][1]-c0[k][1])/max(1, c1[k][0]-c0[k][0])) for k in c1]
        by = {}
        for pid, (name, tick) in p1.items():
            if pid in p0:
                by[name] = by.get(name, 0)+tick-p0[pid][1]
        top = sorted(by.items(), key=lambda kv: -kv[1])[:6]
        text = ' '.join(f'{n.replace(" ", "_")}={100*v/HZ/(t1-t0):.0f}' for n, v in top if v)
        w.writerow([time.strftime('%FT%T%z'), f'{sum(u)/len(u):.1f}', f'{max(u):.1f}', f'{mem():.2f}', *gpu().split(','), text])
        f.flush()
        c0, p0, t0 = c1, p1, t1
