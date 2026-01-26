#!/usr/bin/env python3
"""Complexity-based planner selector (percentile rule)

Outputs:
 - benchmark_results/complexity_selector_assignments.json
 - benchmark_results/complexity_selector_distribution.png
 - prints summary to stdout
"""
import json
import os
import argparse
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def load_complexities(path):
    with open(path, 'r') as f:
        data = json.load(f)
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data


def load_benchmark_results(path):
    with open(path, 'r') as f:
        data = json.load(f)
    return data


def build_result_index(results_list):
    # results_list: list of dicts from dataset2_6planners_results.json
    # index by scenario_id -> planner -> entry
    idx = {}
    for r in results_list:
        sid = r.get('scenario_id')
        planner = r.get('planner')
        if sid is None or planner is None:
            continue
        idx.setdefault(sid, {})[planner] = r
    return idx


def compute_composite(entry, weight_method2=None):
    # entry has 'methods' dict
    methods = ['Method1_Slope', 'Method2_Obstacle', 'Method3_Balanced', 'Method4_Statistical']
    vals = []
    for m in methods:
        v = entry['methods'].get(m, {}).get('complexity', None)
        if v is None:
            return None
        vals.append(float(v))
    if weight_method2 is None:
        return float(np.mean(vals))
    else:
        # weight_method2 is the weight assigned to Method2; remaining distributed equally
        w2 = float(weight_method2)
        rem = 1.0 - w2
        w_each = rem / 3.0
        weights = [w_each, w2, w_each, w_each]
        return float(np.dot(vals, weights))


def assign_by_percentile(entries, scores, lower_pct=33, upper_pct=67):
    # returns dict scenario_id -> assignment
    p_low = np.percentile(scores, lower_pct)
    p_high = np.percentile(scores, upper_pct)
    assignments = {}
    for e, s in zip(entries, scores):
        sid = e.get('scenario_id')
        if sid is None:
            continue
        if s <= p_low:
            assignments[sid] = 'AHA*'
        elif s <= p_high:
            assignments[sid] = 'RRT*'
        else:
            assignments[sid] = 'D*Lite'
    return assignments, p_low, p_high


def evaluate_assignments(assignments, result_index):
    # compute stats per assigned planner
    stats = {}
    for sid, planner in assignments.items():
        stats.setdefault(planner, {'count':0,'success_count':0,'times':[],'path_lengths':[],'nodes':[],'missing':0,'entries':[]})
        stats[planner]['count'] += 1
        entry = None
        if sid in result_index and planner in result_index[sid]:
            entry = result_index[sid][planner]
        else:
            # missing (e.g., AHA* not present)
            stats[planner]['missing'] += 1
        if entry:
            stats[planner]['entries'].append(entry)
            succ = bool(entry.get('success', False))
            stats[planner]['success_count'] += 1 if succ else 0
            stats[planner]['times'].append(float(entry.get('computation_time', 0.0)))
            stats[planner]['path_lengths'].append(float(entry.get('path_length_meters', 0.0)))
            stats[planner]['nodes'].append(int(entry.get('nodes_explored', 0)))
    # finalize
    for planner, s in stats.items():
        c = s['count']
        m = s['missing']
        succs = s['success_count']
        s['success_rate'] = float(succs) / float(c) if c>0 else float('nan')
        s['avg_time'] = float(np.mean(s['times'])) if len(s['times'])>0 else float('nan')
        s['avg_path'] = float(np.mean(s['path_lengths'])) if len(s['path_lengths'])>0 else float('nan')
        s['avg_nodes'] = float(np.mean(s['nodes'])) if len(s['nodes'])>0 else float('nan')
    return stats


def plot_distribution(scores, assignments, out_path):
    # scores: list aligned with entries; assignments: dict sid->planner
    sids = list(assignments.keys())
    labs = [assignments[sid] for sid in sids]
    # build arrays aligned
    vals = []
    labs_ordered = []
    for sid in sids:
        vals.append(scores_by_sid[sid])
        labs_ordered.append(assignments[sid])
    vals = np.array(vals)
    # plot histogram colored by group
    plt.figure(figsize=(8,4))
    groups = ['AHA*','RRT*','D*Lite']
    colors = {'AHA*':'#ff9999','RRT*':'#99ccff','D*Lite':'#99ff99'}
    for g in groups:
        gvals = vals[[i for i,l in enumerate(labs_ordered) if l==g]]
        if len(gvals)>0:
            plt.hist(gvals, bins=30, alpha=0.7, color=colors[g], label=f'{g} (n={len(gvals)})')
    plt.xlabel('Composite Complexity')
    plt.ylabel('Count')
    plt.title('Composite Score Distribution by Assigned Planner')
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200)
    plt.close()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--complexity', default=os.path.join('benchmark_results','complexity_method_comparison.json'))
    ap.add_argument('--results', default=os.path.join('benchmark_results','dataset2_6planners_results.json'))
    ap.add_argument('--weight_method2', type=float, default=None,
                    help='If set, weight for Method2 (0-1). Remaining weight distributed equally among others')
    ap.add_argument('--out', default=os.path.join('benchmark_results','complexity_selector_assignments.json'))
    ap.add_argument('--dist', default=os.path.join('benchmark_results','complexity_selector_distribution.png'))
    args = ap.parse_args()

    complexities = load_complexities(args.complexity)
    results = load_benchmark_results(args.results)
    result_index = build_result_index(results)

    entries = complexities
    composite_scores = []
    global scores_by_sid
    scores_by_sid = {}
    for e in entries:
        sid = e.get('scenario_id')
        s = compute_composite(e, weight_method2=args.weight_method2)
        if s is None:
            continue
        composite_scores.append(s)
        scores_by_sid[sid] = s

    assignments, p_low, p_high = assign_by_percentile(entries, composite_scores)

    stats = evaluate_assignments(assignments, result_index)

    # warnings for AHA* assigned in Dataset2
    aha_assigned = [sid for sid,a in assignments.items() if a=='AHA*']
    aha_warning = False
    if len(aha_assigned)>0:
        # since Dataset2 had no AHA* successful runs, flag warning
        aha_warning = True

    out = {
        'params':{
            'weight_method2': args.weight_method2,
            'percentiles':{'low':p_low,'high':p_high}
        },
        'assignments': assignments,
        'stats': stats,
        'aha_warning': aha_warning,
        'counts': {p: stats.get(p,{}).get('count',0) for p in ['AHA*','RRT*','D*Lite']}
    }

    with open(args.out, 'w') as f:
        json.dump(out, f, indent=2)

    # plot distribution
    plot_distribution(composite_scores, assignments, args.dist)

    # print summary
    print('Assignment counts:')
    for p in ['AHA*','RRT*','D*Lite']:
        c = out['counts'].get(p,0)
        print(f'  {p}: {c}')

    print('\nPer-planner stats:')
    for p, s in stats.items():
        print(f'\nPlanner: {p}')
        print(f"  Count: {s['count']}")
        print(f"  Missing results: {s['missing']}")
        print(f"  Success rate: {s.get('success_rate',0):.3f}")
        print(f"  Avg time: {s.get('avg_time','nan')}")
        print(f"  Avg path length: {s.get('avg_path','nan')}")

    if aha_warning:
        print('\nWARNING: AHA* assigned to scenarios in Dataset2 - AHA* is known to fail on Dataset2')

    print('\nSaved assignments to:', args.out)
    print('Saved distribution plot to:', args.dist)
