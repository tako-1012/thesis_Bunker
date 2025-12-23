#!/usr/bin/env python3
"""Generate comparison tables and Dijkstra detailed stats from benchmark results.

Produces:
- all_planners_comparison.csv / .tsv
- ta_star_by_complexity.csv / .tsv
- PNGs: all_planners_by_size_barplot.png, success_rate_comparison.png, ta_star_complexity_boxplot.png
- dijkstra_detailed_stats.csv / .tsv
- dijkstra_success_by_size.png, dijkstra_time_distribution.png
"""
import json
from pathlib import Path
from collections import defaultdict, Counter
import statistics
import math
import csv

ROOT = Path('ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results')
ROOT.mkdir(parents=True, exist_ok=True)

FULL = ROOT / 'full_benchmark_results.json'
DIJ = ROOT / 'dijkstra_dwa_results.json'

def map_size_from_scenario_name(name):
    n = (name or '').lower()
    # map size strictly from explicit size tokens in the scenario name
    if 'small' in n:
        return 'Small'
    if 'medium' in n:
        return 'Medium'
    if 'large' in n:
        return 'Large'
    # fallback default
    return 'Medium'


def safe_mean(lst):
    return statistics.mean(lst) if lst else float('nan')


def load_full():
    with open(FULL,'r') as f:
        data = json.load(f)
    return data


def compute_planner_stats(full_data):
    planners = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(lambda: defaultdict(int))
    for e in full_data:
        p = e.get('planner_name')
        s = e.get('scenario_name')
        comp = e.get('complexity')
        size = map_size_from_scenario_name(s)
        t = e.get('computation_time')
        succ = bool(e.get('success'))
        counts[p][size] += 1
        if t is not None:
            planners[p][size].append((t, succ))
    summary = []
    for p, sizes in planners.items():
        for size, vals in sizes.items():
            total = counts[p][size]
            succ_count = sum(1 for (_,s) in vals if s)
            times = [t for (t,s) in vals if s]
            avg = safe_mean(times)
            mn = min(times) if times else float('nan')
            mx = max(times) if times else float('nan')
            summary.append({'planner':p, 'map_size':size, 'avg_time':avg, 'min_time':mn, 'max_time':mx, 'success_rate': (succ_count/total*100.0 if total>0 else float('nan')), 'total_runs': total, 'success_count': succ_count})
    return summary


def load_dijkstra():
    with open(DIJ,'r') as f:
        j = json.load(f)
    runs = j.get('runs', []) if isinstance(j, dict) else j
    # normalize
    entries = []
    for r in runs:
        name = r.get('scenario') or r.get('scenario_name') or r.get('scenario_name')
        size = r.get('size_label') or r.get('map_size')
        if not size:
            # infer from name
            ln = (name or '').lower()
            if 'short' in ln or 'flat' in ln or 'minimal' in ln:
                size = 'Small'
            elif 'medium' in ln or 'long' in ln:
                size = 'Medium'
            elif 'large' in ln or 'complex' in ln:
                size = 'Large'
            else:
                size = 'Medium'
        else:
            size = str(size).capitalize()
        t = r.get('computation_time')
        succ = bool(r.get('success'))
        entries.append({'scenario': name, 'map_size': size, 'time': t, 'success': succ})
    return entries


def compute_dijkstra_stats(entries):
    total = len(entries)
    succ = sum(1 for e in entries if e['success'])
    fail = total - succ
    succ_times = [e['time'] for e in entries if e['success'] and e['time'] is not None]
    all_times = [e['time'] for e in entries if e['time'] is not None]
    overall_succ_mean = safe_mean(succ_times)
    overall_mean = safe_mean(all_times)
    by_size = defaultdict(list)
    for e in entries:
        by_size[e['map_size']].append(e)
    size_summary = {}
    for size, lst in by_size.items():
        tot = len(lst)
        sc = sum(1 for e in lst if e['success'])
        times = [e['time'] for e in lst if e['success'] and e['time'] is not None]
        size_summary[size] = {'total': tot, 'success': sc, 'fail': tot-sc, 'success_rate': (sc/tot*100.0 if tot>0 else float('nan')), 'avg_time_success': safe_mean(times)}
    return {'total': total, 'success': succ, 'fail': fail, 'overall_succ_mean': overall_succ_mean, 'overall_mean': overall_mean, 'by_size': size_summary, 'entries': entries}


def write_all_planners_csv(summary, out_csv, out_tsv):
    fields = ['planner','map_size','avg_time','min_time','max_time','success_rate','total_runs','success_count']
    with open(out_csv,'w',newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in sorted(summary, key=lambda x:(x['planner'], x['map_size'])):
            w.writerow({k: ('' if (isinstance(r.get(k), float) and math.isnan(r.get(k))) else r.get(k)) for k in fields})
    with open(out_tsv,'w',newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter='\t')
        w.writeheader()
        for r in sorted(summary, key=lambda x:(x['planner'], x['map_size'])):
            w.writerow({k: ('' if (isinstance(r.get(k), float) and math.isnan(r.get(k))) else r.get(k)) for k in fields})


def write_ta_by_complexity(full_data, out_csv, out_tsv, out_png):
    # ADAPTIVE corresponds to TA*
    entries = [e for e in full_data if e.get('planner_name')=='ADAPTIVE']
    by_comp = defaultdict(list)
    for e in entries:
        comp = e.get('complexity')
        if e.get('success') and e.get('computation_time') is not None:
            by_comp[comp].append(e.get('computation_time'))
    rows = []
    for comp, times in by_comp.items():
        rows.append({'complexity': comp, 'avg_time': safe_mean(times), 'min_time': min(times) if times else float('nan'), 'max_time': max(times) if times else float('nan'), 'success_rate': 100.0, 'scenario_count': len(times)})
    fields = ['complexity','avg_time','min_time','max_time','success_rate','scenario_count']
    with open(out_csv,'w',newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if (isinstance(r.get(k), float) and math.isnan(r.get(k))) else r.get(k)) for k in fields})
    with open(out_tsv,'w',newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter='\t')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('' if (isinstance(r.get(k), float) and math.isnan(r.get(k))) else r.get(k)) for k in fields})
    # boxplot
    try:
        import matplotlib.pyplot as plt
    except Exception:
        print('matplotlib not available for TA* boxplot')
        return
    labels = sorted(by_comp.keys())
    data = [by_comp[l] for l in labels]
    fig, ax = plt.subplots(figsize=(7,4))
    ax.boxplot(data, labels=labels, showmeans=True)
    ax.set_ylabel('Computation Time (s)')
    ax.set_title('ADAPTIVE (TA*) by Complexity')
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def make_plots(summary, dijkstra_stats, out_bar, out_success):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        print('matplotlib not available for plots')
        return
    # prepare data: planners x sizes
    planners = sorted(set(r['planner'] for r in summary))
    sizes = ['Small','Medium','Large']
    avg_map = {p: {s: float('nan') for s in sizes} for p in planners}
    success_map = {p: {s: float('nan') for s in sizes} for p in planners}
    for r in summary:
        p = r['planner']; s = r['map_size']
        avg_map[p][s] = r['avg_time']
        success_map[p][s] = r['success_rate']
    # bar plot grouped
    x = np.arange(len(planners))
    width = 0.2
    fig, ax = plt.subplots(figsize=(10,5))
    for i,s in enumerate(sizes):
        vals = [avg_map[p][s] if not (isinstance(avg_map[p][s], float) and math.isnan(avg_map[p][s])) else 0.0 for p in planners]
        ax.bar(x + (i-1)*width, vals, width, label=s)
    ax.set_xticks(x)
    ax.set_xticklabels(planners, rotation=45, ha='right')
    ax.set_ylabel('Avg Time (s)')
    ax.set_title('All Planners: Avg Time by Map Size')
    ax.legend()
    fig.tight_layout(); fig.savefig(out_bar); plt.close(fig)

    # success rate per planner per size
    fig, ax = plt.subplots(figsize=(10,5))
    for i,s in enumerate(sizes):
        vals = [success_map[p][s] if not (isinstance(success_map[p][s], float) and math.isnan(success_map[p][s])) else 0.0 for p in planners]
        ax.bar(x + (i-1)*width, vals, width, label=s)
    ax.set_xticks(x)
    ax.set_xticklabels(planners, rotation=45, ha='right')
    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Success Rate by Planner and Map Size')
    ax.legend()
    fig.tight_layout(); fig.savefig(out_success); plt.close(fig)


def write_dijkstra_csv(dstat, out_csv, out_tsv):
    # create a csv with overall and per-size rows
    fields = ['metric','value']
    with open(out_csv,'w',newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['metric','value'])
        w.writerow(['total_runs', dstat['total']])
        w.writerow(['success', dstat['success']])
        w.writerow(['fail', dstat['fail']])
        w.writerow(['overall_succ_mean', dstat['overall_succ_mean']])
        w.writerow(['overall_mean', dstat['overall_mean']])
        for size, info in dstat['by_size'].items():
            w.writerow([f'{size}_total', info['total']])
            w.writerow([f'{size}_success', info['success']])
            w.writerow([f'{size}_fail', info['fail']])
            w.writerow([f'{size}_success_rate', info['success_rate']])
            w.writerow([f'{size}_avg_time_success', info['avg_time_success']])
    with open(out_tsv,'w',newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        w.writerow(['metric','value'])
        w.writerow(['total_runs', dstat['total']])
        w.writerow(['success', dstat['success']])
        w.writerow(['fail', dstat['fail']])
        w.writerow(['overall_succ_mean', dstat['overall_succ_mean']])
        w.writerow(['overall_mean', dstat['overall_mean']])
        for size, info in dstat['by_size'].items():
            w.writerow([f'{size}_total', info['total']])
            w.writerow([f'{size}_success', info['success']])
            w.writerow([f'{size}_fail', info['fail']])
            w.writerow([f'{size}_success_rate', info['success_rate']])
            w.writerow([f'{size}_avg_time_success', info['avg_time_success']])


def plot_dijkstra(dstat, out_success, out_time):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        print('matplotlib not available for Dijkstra plots')
        return
    sizes = sorted(dstat['by_size'].keys())
    success_rates = [dstat['by_size'][s]['success_rate'] for s in sizes]
    fig, ax = plt.subplots(figsize=(6,4))
    ax.bar(sizes, success_rates, color=['#6bbf59','#f4c542','#e05a5a'])
    ax.set_ylabel('Success Rate (%)')
    ax.set_title('Dijkstra+DWA Success Rate by Map Size')
    fig.tight_layout(); fig.savefig(out_success); plt.close(fig)

    # time distribution: successful times
    times = [e['time'] for e in dstat['entries'] if e['success'] and e['time'] is not None]
    fig, ax = plt.subplots(figsize=(6,4))
    ax.hist(times, bins=30, color='#4c72b0')
    ax.set_xlabel('Computation Time (s)')
    ax.set_ylabel('Count')
    ax.set_title('Dijkstra+DWA Successful Time Distribution')
    fig.tight_layout(); fig.savefig(out_time); plt.close(fig)


def main():
    full = load_full()
    summary = compute_planner_stats(full)
    # write all planners CSV/TSV
    out_csv = ROOT / 'all_planners_comparison.csv'
    out_tsv = ROOT / 'all_planners_comparison.tsv'
    write_all_planners_csv(summary, out_csv, out_tsv)

    # TA* by complexity
    out_ta_csv = ROOT / 'ta_star_by_complexity.csv'
    out_ta_tsv = ROOT / 'ta_star_by_complexity.tsv'
    out_ta_png = ROOT / 'ta_star_complexity_boxplot.png'
    write_ta_by_complexity(full, out_ta_csv, out_ta_tsv, out_ta_png)

    # plots for all planners
    out_bar = ROOT / 'all_planners_by_size_barplot.png'
    out_success = ROOT / 'success_rate_comparison.png'
    make_plots(summary, None, out_bar, out_success)

    # Dijkstra stats
    dij_entries = load_dijkstra()
    dstat = compute_dijkstra_stats(dij_entries)
    out_d_csv = ROOT / 'dijkstra_detailed_stats.csv'
    out_d_tsv = ROOT / 'dijkstra_detailed_stats.tsv'
    write_dijkstra_csv(dstat, out_d_csv, out_d_tsv)
    out_ds = ROOT / 'dijkstra_success_by_size.png'
    out_dt = ROOT / 'dijkstra_time_distribution.png'
    plot_dijkstra(dstat, out_ds, out_dt)

    print('Wrote comparison CSVs and plots to', ROOT)


if __name__ == '__main__':
    main()
