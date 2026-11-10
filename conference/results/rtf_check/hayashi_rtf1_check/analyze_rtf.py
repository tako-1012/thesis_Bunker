#!/usr/bin/env python3
"""Same-basis comparison of target RTF runs. Each metric names its clock: wall or sim."""
import csv, json, statistics as st, sys
from pathlib import Path
def pct(v, q):
    v = sorted(v)
    return v[min(len(v)-1, int(q*len(v)))] if v else None
def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None
def one(run):
    out = run/'physical_1'
    m = json.loads((out/'manifest.json').read_text())
    case = next(c for c in m['cases'] if c.get('selected'))
    raw = out/case['run_folder']
    mission = json.loads((raw/'mission.json').read_text())
    sim_s = mission['finished_t']-mission['started_t']; wall_s = mission['wall_elapsed_s']
    rtf = sim_s/wall_s
    r = dict(run=run.name, termination=case.get('termination'), target_rtf=m['real_time_factor'],
             mission_sim_s=sim_s, mission_wall_s=wall_s, measured_rtf_mission=rtf)
    u = list(csv.DictReader((raw/'map_updates.csv').open()))
    t0, t1 = mission['started_t'], mission['finished_t']
    u = [x for x in u if t0 <= float(x['stamp']) <= t1]
    st_ = [float(x['stamp']) for x in u]; gaps = [b-a for a, b in zip(st_, st_[1:])]
    us = [float(x['update_s']) for x in u if num(x['update_s']) is not None]
    r.update(map_updates=len(u), map_rate_sim_hz=(len(u)-1)/(st_[-1]-st_[0]), map_rate_wall_hz=(len(u)-1)/(st_[-1]-st_[0])*rtf,
             stamp_gap_sim_median_s=st.median(gaps), stamp_gap_sim_p95_s=pct(gaps, .95), stamp_gap_sim_max_s=max(gaps),
             gap_over_0p15_sim_share=sum(g > .15 for g in gaps)/len(gaps),
             map_errors=sum(x['status'] != 'ok' for x in u), queue_drops_final=int(u[-1]['queue_drops'] or 0),
             update_wall_median_s=st.median(us), update_wall_p95_s=pct(us, .95), update_wall_max_s=max(us),
             update_share_of_scan_period_median=st.median(us)/(.1/rtf), update_over_scan_period_wall_share=sum(x > .1/rtf for x in us)/len(us))
    try:
        s = json.loads((raw/'sensor_status.json').read_text())
        r.update(received_clouds=s.get('received_clouds'), received_rate_sim_hz=s.get('received_clouds')/(mission['finished_t']), sensor_error=s.get('error'))
    except (OSError, TypeError, ValueError):
        pass
    p = list(csv.DictReader((out/'probe.csv').open()))
    moving = [x for x in p if x['status'] == 'running' and num(x['sim_t']) is not None]
    if len(moving) > 2:
        wall = [float(x['wall_s']) for x in moving]; sim = [float(x['sim_t']) for x in moving]
        w30 = [(sim[i]-sim[i-30])/(wall[i]-wall[i-30]) for i in range(30, len(sim))]
        ages = [num(x['cloud_age_sim_s']) for x in moving if num(x['cloud_age_sim_s']) is not None]
        recv = [num(x['received_clouds']) for x in moving if num(x['received_clouds']) is not None]
        r.update(measured_rtf_probe=(sim[-1]-sim[0])/(wall[-1]-wall[0]), rtf_30wall_min=min(w30) if w30 else None,
                 rtf_30wall_p05=pct(w30, .05) if w30 else None,
                 cloud_age_sim_median_s=st.median(ages), cloud_age_sim_p95_s=pct(ages, .95), cloud_age_sim_max_s=max(ages),
                 cloud_age_in_wall_max_s=max(ages)/rtf,
                 received_rate_probe_sim_hz=(recv[-1]-recv[0])/(sim[-1]-sim[0]),
                 received_rate_probe_wall_hz=(recv[-1]-recv[0])/(wall[-1]-wall[0]),
                 cmd_gap_max_wall_s=max(num(x['cmd_gap_max_wall_s']) or 0 for x in moving),
                 cmd_gap_max_sim_s=max(num(x['cmd_gap_max_sim_s']) or 0 for x in moving),
                 cmd_rate_wall_hz=sum(int(x['cmd_count']) for x in moving)/(wall[-1]-wall[0]),
                 cmd_rate_sim_hz=sum(int(x['cmd_count']) for x in moving)/(sim[-1]-sim[0]),
                 sensor_errors_seen=sorted({x['sensor_error'] for x in moving if x['sensor_error'] not in ('', 'None')}))
    try:
        rp = list(csv.DictReader((raw/'replans.csv').open()))
    except OSError:
        rp = []
    if rp:
        h = [float(x['handoff_latency_s']) for x in rp if num(x.get('handoff_latency_s')) is not None]
        hs = [float(x['sim_handoff_s']) for x in rp if num(x.get('sim_handoff_s')) is not None]
        pt = [float(x['plan_time_s']) for x in rp if num(x.get('plan_time_s')) is not None]
        r.update(replans=len(rp), plan_wall_median_s=st.median(pt), plan_wall_max_s=max(pt))
        if h:
            r.update(handoff_wall_median_s=st.median(h), handoff_wall_p95_s=pct(h, .95), handoff_wall_max_s=max(h))
        if hs:
            r.update(handoff_sim_median_s=st.median(hs), handoff_sim_p95_s=pct(hs, .95), handoff_sim_max_s=max(hs))
    res = list(csv.DictReader((run/'resources.csv').open()))
    if res:
        for name, key in [('cpu_avg_pct', 'cpu_avg_pct'), ('cpu_max_core_pct', 'cpu_max_core_pct'), ('mem_used_gib', 'mem_used_gib')]:
            v = [float(x[key]) for x in res]
            r[name+'_median'] = st.median(v); r[name+'_max'] = max(v)
        g = [num(x['gpu_util_pct']) for x in res if num(x['gpu_util_pct']) is not None]
        gm = [num(x['gpu_mem_mib']) for x in res if num(x['gpu_mem_mib']) is not None]
        r.update(gpu_util_max=max(g) if g else None, gpu_mem_mib_max=max(gm) if gm else None)
        tops = {}
        for x in res:
            for item in x['top_procs_pct'].split():
                n, v = item.rsplit('=', 1); tops.setdefault(n, []).append(float(v))
        r['top_proc_pct_median_over_samples'] = {n: st.median(v) for n, v in sorted(tops.items(), key=lambda kv: -st.median(kv[1]))[:6] if len(v) > len(res)/2}
    return r
root = Path(sys.argv[1])
result = {}
for run in sys.argv[2:]:
    try:
        result[run] = one(root/run)
    except Exception as exc:
        result[run] = dict(error=type(exc).__name__+': '+str(exc))
(root/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
keys = sorted({k for v in result.values() for k in v})
with (root/'comparison.csv').open('w', newline='') as f:
    w = csv.writer(f); w.writerow(['metric', *result])
    for k in keys:
        w.writerow([k, *[result[r].get(k, '') for r in result]])
print((root/'comparison.csv').read_text())
