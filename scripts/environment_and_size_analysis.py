#!/usr/bin/env python3
"""Environment-type and size performance analysis.
Outputs:
 - benchmark_results/environment_type_performance.json
 - benchmark_results/statistical_significance.json
 - benchmark_results/best_planner_by_environment.json
 - benchmark_results/size_performance_analysis.json
 - benchmark_results/size_correlation.json
"""
import json
import os
import numpy as np
from collections import defaultdict, Counter

ROOT = os.getcwd()
RESULTS_PATH = os.path.join(ROOT, 'benchmark_results', 'dataset2_6planners_results.json')
SCENARIOS_PATH = os.path.join(ROOT, 'dataset2_scenarios.json')
OUT_ENV = os.path.join(ROOT, 'benchmark_results', 'environment_type_performance.json')
OUT_STATS = os.path.join(ROOT, 'benchmark_results', 'statistical_significance.json')
OUT_BEST = os.path.join(ROOT, 'benchmark_results', 'best_planner_by_environment.json')
OUT_SIZE = os.path.join(ROOT, 'benchmark_results', 'size_performance_analysis.json')
OUT_SIZECORR = os.path.join(ROOT, 'benchmark_results', 'size_correlation.json')


def load(p):
    with open(p,'r') as f:
        return json.load(f)


def try_scipy_test(a,b):
    try:
        from scipy.stats import mannwhitneyu
        stat, p = mannwhitneyu(a, b, alternative='two-sided')
        return {'method':'mannwhitneyu','stat':float(stat),'pvalue':float(p)}
    except Exception:
        return None


def bootstrap_mean_diff(a,b,iter=1000):
    # returns p-value two-sided by permutation/bootstrap
    a = np.array(a); b = np.array(b)
    if len(a)==0 or len(b)==0:
        return {'method':'bootstrap','pvalue':None}
    obs = abs(a.mean()-b.mean())
    pooled = np.concatenate([a,b])
    count = 0
    rng = np.random.default_rng(0)
    for _ in range(iter):
        rng.shuffle(pooled)
        na = pooled[:len(a)]; nb = pooled[len(a):]
        if abs(na.mean()-nb.mean()) >= obs:
            count += 1
    p = (count+1)/(iter+1)
    return {'method':'bootstrap','pvalue':float(p)}


def main():
    results = load(RESULTS_PATH)
    scenarios = load(SCENARIOS_PATH)

    # index scenarios metadata by id
    scen_by_id = {s.get('id', s.get('scenario_id')): s for s in scenarios}

    # group by environment
    env_groups = defaultdict(list)
    planners = set()
    for r in results:
        sid = r.get('scenario_id')
        pl = r.get('planner')
        planners.add(pl)
        env = None
        if sid in scen_by_id:
            env = scen_by_id[sid].get('env') or scen_by_id[sid].get('environment_type')
        if env is None:
            # try extracting from id string
            if isinstance(sid, str):
                if 'steep' in sid.lower(): env='steep'
                elif 'dense' in sid.lower(): env='dense'
                elif 'complex' in sid.lower(): env='complex'
                elif 'beach' in sid.lower(): env='beach'
        if env is None:
            env='unknown'
        env_groups[env].append(r)

    planners = sorted(list(planners))

    env_perf = {}
    best_by_env = {}
    for env, entries in env_groups.items():
        # compute per-planner stats
        stats = {}
        for p in planners:
            ps = [float(e.get('computation_time', np.nan)) for e in entries if e.get('planner')==p and e.get('computation_time') is not None]
            succ = [1 if e.get('success') else 0 for e in entries if e.get('planner')==p and e.get('computation_time') is not None]
            stats[p] = {
                'count': len(ps),
                'mean_time': float(np.mean(ps)) if ps else None,
                'std_time': float(np.std(ps)) if ps else None,
                'success_rate': float(np.sum(succ))/len(succ) if succ else None
            }
        env_perf[env] = stats
        # determine fastest by mean_time among those with count>0
        min_time = None; best=None
        for p, s in stats.items():
            if s['mean_time'] is None:
                continue
            if min_time is None or s['mean_time']<min_time:
                min_time = s['mean_time']; best=p
        best_by_env[env] = {'best_planner': best, 'mean_time': min_time}

    # statistical significance: pairwise comparisons per environment between D*Lite and RRT*
    stats_out = {}
    for env, entries in env_groups.items():
        d_times = [float(e.get('computation_time')) for e in entries if e.get('planner')=='D*Lite' and e.get('success')]
        r_times = [float(e.get('computation_time')) for e in entries if e.get('planner')=='RRT*' and e.get('success')]
        th_times = [float(e.get('computation_time')) for e in entries if e.get('planner')=='Theta*' and e.get('success')]
        res = {}
        # D*Lite vs RRT*
        if d_times and r_times:
            sc = try_scipy_test(d_times, r_times)
            if sc is None:
                sc = bootstrap_mean_diff(d_times, r_times)
            res['D*Lite_vs_RRT*'] = sc
        else:
            res['D*Lite_vs_RRT*'] = None
        # D*Lite vs Theta*
        if d_times and th_times:
            sc = try_scipy_test(d_times, th_times)
            if sc is None:
                sc = bootstrap_mean_diff(d_times, th_times)
            res['D*Lite_vs_Theta*'] = sc
        else:
            res['D*Lite_vs_Theta*'] = None
        stats_out[env] = res

    # size analysis: compute percentiles to split into Small/Medium/Large approx counts (48/72/24)
    # collect map_size from scenarios
    sizes = []
    sid_to_size = {}
    for s in scenarios:
        sid = s.get('id', s.get('scenario_id'))
        ms = s.get('map_size') or s.get('map', {}).get('size') if isinstance(s.get('map'), dict) else s.get('map_size')
        try:
            ms = int(ms)
        except Exception:
            ms = None
        sid_to_size[sid] = ms
        if ms is not None:
            sizes.append(ms)
    # thresholds at 33.33% and 83.33%
    if sizes:
        t1 = np.percentile(sizes, 33.3333)
        t2 = np.percentile(sizes, 83.3333)
    else:
        t1=t2=None

    size_groups = {'Small':[], 'Medium':[], 'Large':[]}
    for sid,sz in sid_to_size.items():
        if sz is None:
            continue
        if sz <= t1:
            size_groups['Small'].append(sid)
        elif sz <= t2:
            size_groups['Medium'].append(sid)
        else:
            size_groups['Large'].append(sid)

    size_perf = {}
    for size_label, sids in size_groups.items():
        entries = [r for r in results if r.get('scenario_id') in sids]
        stats = {}
        for p in planners:
            ps = [float(e.get('computation_time', np.nan)) for e in entries if e.get('planner')==p and e.get('computation_time') is not None]
            succ = [1 if e.get('success') else 0 for e in entries if e.get('planner')==p and e.get('computation_time') is not None]
            stats[p] = {
                'count': len(ps),
                'mean_time': float(np.mean(ps)) if ps else None,
                'std_time': float(np.std(ps)) if ps else None,
                'success_rate': float(np.sum(succ))/len(succ) if succ else None
            }
        size_perf[size_label] = {'count_scenarios': len(sids), 'stats': stats}

    # size correlation: correlate map_size with times per planner
    corr = {}
    for p in planners:
        times = []
        sizes_al = []
        for r in results:
            sid = r.get('scenario_id')
            sz = sid_to_size.get(sid)
            t = r.get('computation_time')
            if sz is None or t is None:
                continue
            try:
                times.append(float(t)); sizes_al.append(float(sz))
            except Exception:
                continue
        if len(times)>=3:
            corr[p] = float(np.corrcoef(sizes_al, times)[0,1])
        else:
            corr[p] = None

    # save files
    with open(OUT_ENV,'w') as f:
        json.dump({'environment_performance': env_perf}, f, indent=2)
    with open(OUT_STATS,'w') as f:
        json.dump({'statistical_tests': stats_out}, f, indent=2)
    with open(OUT_BEST,'w') as f:
        json.dump({'best_by_environment': best_by_env}, f, indent=2)
    with open(OUT_SIZE,'w') as f:
        json.dump({'size_bins':{'t1':t1,'t2':t2}, 'size_performance': size_perf}, f, indent=2)
    with open(OUT_SIZECORR,'w') as f:
        json.dump({'size_correlation': corr}, f, indent=2)

    print('Saved:', OUT_ENV, OUT_STATS, OUT_BEST, OUT_SIZE, OUT_SIZECORR)

if __name__=='__main__':
    main()
