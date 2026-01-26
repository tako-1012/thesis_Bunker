#!/usr/bin/env python3
"""Produce detailed D*Lite analysis and comparisons.
Outputs:
 - benchmark_results/dlite_complete_analysis.json
 - benchmark_results/dlite_vs_others_comparison.json
 - benchmark_results/scenarios_where_dlite_not_fastest.json
"""
import json
import os
import numpy as np
from collections import defaultdict, Counter

ROOT = os.getcwd()
RESULTS = os.path.join(ROOT, 'benchmark_results', 'dataset2_6planners_results.json')
SCENARIOS = os.path.join(ROOT, 'dataset2_scenarios.json')
COMPLEX = os.path.join(ROOT, 'benchmark_results', 'complexity_method_comparison.json')
OUT_A = os.path.join(ROOT, 'benchmark_results', 'dlite_complete_analysis.json')
OUT_B = os.path.join(ROOT, 'benchmark_results', 'dlite_vs_others_comparison.json')
OUT_C = os.path.join(ROOT, 'benchmark_results', 'scenarios_where_dlite_not_fastest.json')


def load(p):
    with open(p,'r') as f:
        return json.load(f)


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def mann_whitney(a,b):
    try:
        from scipy.stats import mannwhitneyu
        stat, p = mannwhitneyu(a,b,alternative='two-sided')
        return {'method':'mannwhitneyu','stat':float(stat),'pvalue':float(p)}
    except Exception:
        return None


def bootstrap_p(a,b,iter=2000):
    a = np.array(a); b = np.array(b)
    if len(a)==0 or len(b)==0:
        return None
    obs = abs(a.mean()-b.mean())
    pooled = np.concatenate([a,b])
    rng = np.random.default_rng(1)
    count = 0
    for _ in range(iter):
        rng.shuffle(pooled)
        na = pooled[:len(a)]; nb = pooled[len(a):]
        if abs(na.mean()-nb.mean()) >= obs:
            count += 1
    p = (count+1)/(iter+1)
    return {'method':'bootstrap','pvalue':float(p)}


def main():
    results = load(RESULTS)
    scenarios = load(SCENARIOS)
    comp = load(COMPLEX)
    comp_map = {}
    if isinstance(comp, dict) and 'results' in comp:
        for e in comp['results']:
            comp_map[e.get('scenario_id')] = e.get('methods', {})

    # index
    by_sid = defaultdict(dict)
    planners = set()
    for r in results:
        sid = r.get('scenario_id')
        p = r.get('planner')
        planners.add(p)
        by_sid[sid][p] = r

    # 1. D*Lite overall stats
    d_entries = [by_sid[sid].get('D*Lite') for sid in by_sid if 'D*Lite' in by_sid[sid]]
    d_times = [safe_float(e.get('computation_time')) for e in d_entries if e and e.get('computation_time') is not None]
    d_success = sum(1 for e in d_entries if e and e.get('success'))
    total = len(d_entries)
    d_stats = {
        'total_runs': total,
        'success_count': d_success,
        'min_time': float(np.min(d_times)) if d_times else None,
        'max_time': float(np.max(d_times)) if d_times else None,
        'mean_time': float(np.mean(d_times)) if d_times else None,
        'std_time': float(np.std(d_times)) if d_times else None,
        'time_histogram': None
    }

    # 2. find scenarios where D*Lite not fastest
    not_fast = []
    for sid, entries in by_sid.items():
        if 'D*Lite' not in entries:
            continue
        # consider only successful planners
        cand = []
        for p, e in entries.items():
            t = safe_float(e.get('computation_time'))
            succ = bool(e.get('success'))
            if t is None or not succ:
                continue
            cand.append((p,t))
        if not cand:
            continue
        cand.sort(key=lambda x: x[1])
        fastest = cand[0][0]
        if fastest != 'D*Lite':
            meta = next((s for s in scenarios if s.get('id')==sid or s.get('scenario_id')==sid), {})
            not_fast.append({
                'scenario_id': sid,
                'fastest': fastest,
                'fastest_time': cand[0][1],
                'dlite_time': entries['D*Lite'].get('computation_time'),
                'env': meta.get('env') or meta.get('environment_type'),
                'map_size': meta.get('map_size'),
                'obstacle_ratio': meta.get('obstacle_ratio'),
                'complexity': comp_map.get(sid)
            })

    # 3. D*Lite vs others: ratios and tests
    comparisons = {}
    others = [p for p in sorted(planners) if p!='D*Lite']
    for o in others:
        pairs = []
        ratios = []
        dlist = []
        olist = []
        for sid, entries in by_sid.items():
            if 'D*Lite' not in entries or o not in entries:
                continue
            de = entries['D*Lite']; oe = entries[o]
            if not de.get('success') or not oe.get('success'):
                continue
            dt = safe_float(de.get('computation_time')); ot = safe_float(oe.get('computation_time'))
            if dt is None or ot is None or dt==0:
                continue
            ratios.append(ot/dt)
            dlist.append(dt); olist.append(ot)
        comparisons[o] = {
            'count': len(ratios),
            'mean_ratio_other_over_dlite': float(np.mean(ratios)) if ratios else None,
            'median_ratio': float(np.median(ratios)) if ratios else None,
            'd_mean_time': float(np.mean(dlist)) if dlist else None,
            'o_mean_time': float(np.mean(olist)) if olist else None,
            'stat_test': mann_whitney(dlist, olist) or bootstrap_p(dlist, olist)
        }

    # 4. scenarios where D*Lite is significantly slower (ratio>1.5)
    slow_scenarios = []
    for sid, entries in by_sid.items():
        if 'D*Lite' not in entries:
            continue
        de = entries['D*Lite']
        if not de.get('success'):
            continue
        dt = safe_float(de.get('computation_time'))
        other_times = [safe_float(e.get('computation_time')) for p,e in entries.items() if p!='D*Lite' and e.get('success')]
        other_times = [t for t in other_times if t is not None]
        if not other_times or dt is None:
            continue
        mean_other = float(np.mean(other_times))
        if dt > 1.5 * mean_other:
            meta = next((s for s in scenarios if s.get('id')==sid or s.get('scenario_id')==sid), {})
            slow_scenarios.append({'scenario_id': sid, 'dlite_time': dt, 'mean_other_time': mean_other, 'ratio': dt/mean_other,
                                   'env': meta.get('env') or meta.get('environment_type'), 'map_size': meta.get('map_size'),
                                   'obstacle_ratio': meta.get('obstacle_ratio'), 'complexity': comp_map.get(sid)})

    # prepare outputs
    outA = {'dlite_stats': d_stats, 'total_scenarios': len(by_sid)}
    outB = {'comparisons': comparisons}
    outC = {'not_fastest': not_fast, 'significantly_slower': slow_scenarios}

    with open(OUT_A,'w') as f:
        json.dump(outA, f, indent=2)
    with open(OUT_B,'w') as f:
        json.dump(outB, f, indent=2)
    with open(OUT_C,'w') as f:
        json.dump(outC, f, indent=2)

    print('Saved:', OUT_A, OUT_B, OUT_C)

if __name__=='__main__':
    main()
