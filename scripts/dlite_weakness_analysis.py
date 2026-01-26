#!/usr/bin/env python3
"""Analyze dataset2 results to find D*Lite weaknesses and planner advantages.
Outputs:
 - benchmark_results/dlite_weakness_analysis.json
 - benchmark_results/planner_advantage_matrix.json
 - benchmark_results/conditional_performance.json
"""
import json
import os
import numpy as np
from collections import defaultdict, Counter

ROOT = os.getcwd()
RESULTS_PATH = os.path.join(ROOT, 'benchmark_results', 'dataset2_6planners_results.json')
SCENARIOS_PATH = os.path.join(ROOT, 'dataset2_scenarios.json')
COMPLEXITY_PATH = os.path.join(ROOT, 'benchmark_results', 'complexity_method_comparison.json')
OUT1 = os.path.join(ROOT, 'benchmark_results', 'dlite_weakness_analysis.json')
OUT2 = os.path.join(ROOT, 'benchmark_results', 'planner_advantage_matrix.json')
OUT3 = os.path.join(ROOT, 'benchmark_results', 'conditional_performance.json')


def load_json(p):
    with open(p, 'r') as f:
        return json.load(f)


def main():
    results = load_json(RESULTS_PATH)
    scenarios = load_json(SCENARIOS_PATH)
    comp = load_json(COMPLEXITY_PATH)
    if isinstance(comp, dict) and 'results' in comp:
        comp_list = comp['results']
    else:
        comp_list = comp

    # index
    by_scenario = defaultdict(dict)
    planners_set = set()
    for r in results:
        sid = r.get('scenario_id')
        pl = r.get('planner')
        planners_set.add(pl)
        by_scenario[sid][pl] = r

    # index complexity by scenario
    comp_by_sid = {c.get('scenario_id'): c.get('methods', {}) for c in comp_list}
    # index scenarios metadata
    scen_by_sid = {s.get('id', s.get('scenario_id', None)): s for s in scenarios}

    # 1) D*Lite relative slowness
    slow_cases = []
    ratios = []
    for sid, entries in by_scenario.items():
        if 'D*Lite' not in entries:
            continue
        dentry = entries['D*Lite']
        dtime = float(dentry.get('computation_time', float('nan')))
        other_times = [float(e.get('computation_time', float('nan'))) for p,e in entries.items() if p!='D*Lite']
        other_times = [t for t in other_times if not np.isnan(t) and t>0]
        if len(other_times)==0:
            continue
        mean_others = float(np.mean(other_times))
        ratio = dtime / mean_others if mean_others>0 else float('inf')
        ratios.append(ratio)
        if ratio > 1.5:  # D*Lite notably slower
            # collect metadata
            meta = scen_by_sid.get(sid, {})
            c = comp_by_sid.get(sid, {})
            slow_cases.append({
                'scenario_id': sid,
                'dtime': dtime,
                'mean_other_time': mean_others,
                'ratio': ratio,
                'map_size': meta.get('map_size', meta.get('map', meta.get('map_size'))),
                'env': meta.get('env', meta.get('environment_type')),
                'obstacle_ratio': meta.get('obstacle_ratio'),
                'complexity': {k: v.get('complexity') for k,v in c.items()} if c else {}
            })

    # aggregate slow_cases characteristics
    env_counter = Counter([c.get('env') for c in slow_cases])
    sizes = [c.get('map_size') for c in slow_cases if c.get('map_size') is not None]
    obs = [c.get('obstacle_ratio') for c in slow_cases if c.get('obstacle_ratio') is not None]
    avg_ratio = float(np.mean(ratios)) if ratios else None

    dlite_weakness = {
        'count_slow_cases': len(slow_cases),
        'avg_ratio_over_others': avg_ratio,
        'env_distribution': dict(env_counter),
        'map_size_summary': {
            'mean': float(np.mean(sizes)) if sizes else None,
            'median': float(np.median(sizes)) if sizes else None,
            'min': int(np.min(sizes)) if sizes else None,
            'max': int(np.max(sizes)) if sizes else None
        },
        'obstacle_ratio_summary': {
            'mean': float(np.mean(obs)) if obs else None,
            'median': float(np.median(obs)) if obs else None
        },
        'examples': slow_cases[:20]
    }

    # 2) D*Lite success check
    d_results = [r for r in results if r.get('planner')=='D*Lite']
    total_d = len(d_results)
    d_success = sum(1 for r in d_results if r.get('success'))
    failures = [r for r in d_results if not r.get('success')]
    # check errors/timeouts
    errors = [r for r in failures if r.get('error')]
    timeouts = [r for r in failures if r.get('computation_time', 0) >= 180]

    dlite_status = {
        'total_runs': total_d,
        'success_count': d_success,
        'failure_count': len(failures),
        'failures_sample': failures[:10],
        'errors': errors[:10],
        'timeouts': timeouts[:10]
    }

    # 3) Planner advantage (fastest counts)
    planners = sorted(list(planners_set))
    advantage_counts = {p:0 for p in planners}
    advantage_examples = {p:[] for p in planners}
    for sid, entries in by_scenario.items():
        # find fastest among available planners
        cand = []
        for p,e in entries.items():
            t = e.get('computation_time', None)
            if t is None:
                continue
            try:
                t = float(t)
            except Exception:
                continue
            if not e.get('success', False):
                continue
            cand.append((p,t))
        if not cand:
            continue
        cand.sort(key=lambda x: x[1])
        best = cand[0][0]
        advantage_counts[best] += 1
        if len(advantage_examples[best])<10:
            advantage_examples[best].append({'scenario_id': sid, 'time': cand[0][1]})

    planner_advantage = {
        'advantage_counts': advantage_counts,
        'examples': advantage_examples
    }

    # 4) Conditional performance: correlations and buckets
    # gather per-scenario metrics
    rows = []
    for sid, entries in by_scenario.items():
        meta = scen_by_sid.get(sid,{})
        compm = comp_by_sid.get(sid, {})
        row = {'scenario_id': sid, 'map_size': meta.get('map_size'), 'env': meta.get('env', meta.get('environment_type')),
               'obstacle_ratio': meta.get('obstacle_ratio')}
        # slope mean if available
        m1 = compm.get('Method1_Slope')
        row['slope_mean'] = m1.get('slope_mean') if m1 else None
        # times per planner
        for p in planners:
            entry = entries.get(p)
            row[p+'_time'] = float(entry.get('computation_time')) if entry and entry.get('computation_time') is not None else None
            row[p+'_success'] = bool(entry.get('success')) if entry else False
        rows.append(row)

    # convert to arrays for correlation
    def corr(x,y):
        try:
            xm = np.array([v for v in x if v is not None and not np.isnan(v)])
            ym = np.array([y[i] for i,v in enumerate(x) if v is not None and not np.isnan(v)])
            if len(xm)<3:
                return None
            return float(np.corrcoef(xm, ym)[0,1])
        except Exception:
            return None

    cond = {}
    # map_size vs D*Lite time
    map_sizes = [r['map_size'] for r in rows]
    dl_times = [r.get('D*Lite_time') for r in rows]
    cond['correlation'] = {
        'map_size_vs_dlite_time': corr(map_sizes, dl_times),
        'obstacle_vs_dlite_time': corr([r.get('obstacle_ratio') for r in rows], dl_times),
        'slope_vs_dlite_time': corr([r.get('slope_mean') for r in rows], dl_times)
    }

    # bucketed averages
    def bucket_stats(xvals, yvals, bins=4):
        # xvals list, yvals list
        arr = [(x,y) for x,y in zip(xvals,yvals) if x is not None and y is not None and not np.isnan(x) and not np.isnan(y)]
        if not arr:
            return []
        xs, ys = zip(*arr)
        xs = np.array(xs); ys = np.array(ys)
        bins_edges = np.percentile(xs, np.linspace(0,100,bins+1))
        stats = []
        for i in range(bins):
            lo = bins_edges[i]; hi = bins_edges[i+1]
            mask = (xs>=lo) & (xs<=hi) if i==bins-1 else (xs>=lo) & (xs<hi)
            if mask.sum()==0:
                stats.append({'bin':(float(lo),float(hi)),'count':0,'mean_y':None})
            else:
                stats.append({'bin':(float(lo),float(hi)),'count':int(mask.sum()),'mean_y':float(ys[mask].mean())})
        return stats

    cond['buckets'] = {
        'map_size_buckets_vs_dlite_time': bucket_stats([r['map_size'] for r in rows], dl_times, bins=4),
        'obstacle_buckets_vs_dlite_time': bucket_stats([r.get('obstacle_ratio') for r in rows], dl_times, bins=4),
        'slope_buckets_vs_dlite_time': bucket_stats([r.get('slope_mean') for r in rows], dl_times, bins=4)
    }

    # save outputs
    with open(OUT1, 'w') as f:
        json.dump({'dlite_weakness': dlite_weakness, 'dlite_status': dlite_status}, f, indent=2)
    with open(OUT2, 'w') as f:
        json.dump(planner_advantage, f, indent=2)
    with open(OUT3, 'w') as f:
        json.dump(cond, f, indent=2)

    print('Saved:', OUT1, OUT2, OUT3)


if __name__=='__main__':
    main()
