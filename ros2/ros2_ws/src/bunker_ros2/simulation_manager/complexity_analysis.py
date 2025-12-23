#!/usr/bin/env python3
"""Scenario complexity analysis and performance aggregation.

Reads `scenarios/benchmark_scenarios.json` and result JSON files to:
- classify scenarios into Easy/Medium/Hard by name-based rules
- aggregate counts by complexity and map size (small/medium/large)
- compute per-planner stats (avg/min/max times, success rate)
- write CSVs and PNG plots to benchmark_results directory
"""
import json
import os
from pathlib import Path
import re
import math
from collections import defaultdict, Counter
import statistics
import sys

OUT_DIR = Path('ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results')
OUT_DIR.mkdir(parents=True, exist_ok=True)


def load_scenarios(path='scenarios/benchmark_scenarios.json'):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Scenarios file not found: {p}")
    with open(p, 'r') as f:
        data = json.load(f)
    return data


def map_size_from_difficulty(difficulty: str):
    d = (difficulty or '').lower()
    if d == 'easy':
        return 'small'
    if d == 'medium':
        return 'medium'
    if d in ('hard', 'very_hard'):
        return 'large'
    return 'medium'


COMPLEXITY_RULES = {
    'easy': ['flat', 'short', 'minimal', 'simple', 'easy'],
    'medium': ['gentle', 'long', 'moderate', 'medium'],
    'hard': ['steep', 'obstacle', 'narrow', 'complex', 'hard'],
}


def classify_by_name(name: str):
    n = (name or '').lower()
    for label, keys in COMPLEXITY_RULES.items():
        for k in keys:
            if k in n:
                return label
    return 'medium'


def find_result_files():
    files = []
    # common locations
    candidates = [
        Path('ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results'),
        Path('results'),
    ]
    for base in candidates:
        if not base.exists():
            continue
        for p in base.rglob('*.json'):
            files.append(p)
    return sorted(set(files))


def load_results(files):
    # returns dict: planner -> list of run dicts
    planners = defaultdict(list)
    for f in files:
        try:
            with open(f, 'r') as fh:
                j = json.load(fh)
        except Exception:
            continue
        planner_name = None
        if isinstance(j, dict) and 'planner' in j:
            planner_name = j.get('planner')
        # some old files may be a list or dict of runs
        runs = None
        if isinstance(j, dict) and 'runs' in j and isinstance(j['runs'], list):
            runs = j['runs']
        elif isinstance(j, list):
            runs = j
        elif isinstance(j, dict) and 'results' in j and isinstance(j['results'], dict):
            # e.g., {'results': {'TA_STAR': [...]}}
            for k, v in j['results'].items():
                if isinstance(v, list):
                    planners[k].extend(v)
            continue
        if runs is None:
            continue
        if planner_name is None:
            # try to infer planner name from filename
            planner_name = f.stem.upper()
        planners[planner_name].extend(runs)
    return planners


def aggregate(scenarios):
    # classify scenarios
    rows = []
    complexity_map = {}
    size_counter = Counter()
    for s in scenarios:
        name = s.get('name')
        terrain = s.get('terrain_type', '')
        difficulty = s.get('difficulty', '')
        map_size = map_size_from_difficulty(difficulty)
        complexity = classify_by_name(name)
        rows.append({'scenario_name': name, 'complexity': complexity, 'map_size': map_size, 'terrain_type': terrain})
        complexity_map[name] = {'complexity': complexity, 'map_size': map_size}
        size_counter[map_size] += 1
    return rows, complexity_map, size_counter


def compute_stats(planners, complexity_map):
    # planners: dict planner->list of runs
    stats = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(lambda: defaultdict(int))
    for planner, runs in planners.items():
        for r in runs:
            name = r.get('scenario') or r.get('scenario_name') or r.get('name')
            if not name:
                continue
            cinfo = complexity_map.get(name)
            complexity = cinfo['complexity'] if cinfo else classify_by_name(name)
            t = r.get('computation_time')
            success = bool(r.get('success'))
            counts[planner][complexity] += 1
            if t is not None and success:
                try:
                    stats[planner][complexity].append(float(t))
                except Exception:
                    pass
    # compute summary
    summary = []
    for planner, cmap in stats.items():
        for complexity, times in cmap.items():
            total = counts[planner].get(complexity, 0)
            succ = len(times)
            avg = statistics.mean(times) if times else float('nan')
            mn = min(times) if times else float('nan')
            mx = max(times) if times else float('nan')
            success_rate = (succ / total * 100.0) if total > 0 else float('nan')
            summary.append({'complexity': complexity, 'planner': planner, 'avg_time': avg, 'min_time': mn, 'max_time': mx, 'success_rate': success_rate, 'scenario_count': total})
    return summary


def write_csv(rows, perf_summary):
    import csv
    scsv = OUT_DIR / 'scenario_complexity.csv'
    with open(scsv, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['scenario_name', 'complexity', 'map_size', 'terrain_type'])
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    pcsv = OUT_DIR / 'complexity_performance.csv'
    with open(pcsv, 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=['complexity', 'planner', 'avg_time', 'success_rate', 'scenario_count'])
        writer.writeheader()
        for p in perf_summary:
            writer.writerow({'complexity': p['complexity'], 'planner': p['planner'], 'avg_time': ('' if math.isnan(p['avg_time']) else f"{p['avg_time']:.3f}"), 'success_rate': ('' if math.isnan(p['success_rate']) else f"{p['success_rate']:.1f}"), 'scenario_count': p['scenario_count']})

    return scsv, pcsv


def make_plots(rows, perf_summary):
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        print('matplotlib not available, skipping plots:', e)
        return []

    out_files = []
    # distribution bar
    comp_counts = Counter([r['complexity'] for r in rows])
    labels = ['easy', 'medium', 'hard']
    vals = [comp_counts.get(l, 0) for l in labels]
    fig, ax = plt.subplots(figsize=(6,4))
    ax.bar(labels, vals, color=['#6bbf59','#f4c542','#e05a5a'])
    ax.set_ylabel('Scenario Count')
    ax.set_title('Complexity Distribution')
    f1 = OUT_DIR / 'complexity_distribution.png'
    fig.tight_layout()
    fig.savefig(f1)
    plt.close(fig)
    out_files.append(f1)

    # complexity by size (stacked)
    size_map = defaultdict(Counter)
    for r in rows:
        size_map[r['map_size']][r['complexity']] += 1
    sizes = ['small','medium','large']
    comp = labels
    matrix = {c: [size_map[s].get(c,0) for s in sizes] for c in comp}
    fig, ax = plt.subplots(figsize=(7,4))
    bottom = np.zeros(len(sizes))
    colors = ['#6bbf59','#f4c542','#e05a5a']
    for i,c in enumerate(comp):
        vals = matrix[c]
        ax.bar(sizes, vals, bottom=bottom, label=c.capitalize(), color=colors[i])
        bottom = bottom + np.array(vals)
    ax.set_ylabel('Count')
    ax.set_title('Complexity by Map Size')
    ax.legend()
    f2 = OUT_DIR / 'complexity_by_size.png'
    fig.tight_layout()
    fig.savefig(f2)
    plt.close(fig)
    out_files.append(f2)

    # complexity vs performance boxplot (use perf_summary: use avg_time per planner->complexity)
    comp_groups = {l: [] for l in labels}
    for p in perf_summary:
        if p['complexity'] in comp_groups and not math.isnan(p['avg_time']):
            comp_groups[p['complexity']].append(p['avg_time'])
    fig, ax = plt.subplots(figsize=(7,4))
    data = [comp_groups[l] for l in labels]
    ax.boxplot(data, labels=[l.capitalize() for l in labels], showmeans=True)
    ax.set_ylabel('Computation Time (s)')
    ax.set_title('Complexity vs Computation Time (per-planner averages)')
    f3 = OUT_DIR / 'complexity_vs_performance.png'
    fig.tight_layout()
    fig.savefig(f3)
    plt.close(fig)
    out_files.append(f3)

    return out_files


def main():
    scenarios = load_scenarios()
    rows, complexity_map, size_counter = aggregate(scenarios)

    result_files = find_result_files()
    planners = load_results(result_files)
    perf_summary = compute_stats(planners, complexity_map)

    scsv, pcsv = write_csv(rows, perf_summary)
    plots = make_plots(rows, perf_summary)

    # Print summary tables to stdout
    total = len(rows)
    easy = sum(1 for r in rows if r['complexity']=='easy')
    med = sum(1 for r in rows if r['complexity']=='medium')
    hard = sum(1 for r in rows if r['complexity']=='hard')
    print('Complexity summary: total', total)
    print(f'Easy: {easy}, Medium: {med}, Hard: {hard}')
    print('Size breakdown:', dict(size_counter))
    print('CSV files:', scsv, pcsv)
    for p in plots:
        print('Plot:', p)


if __name__ == '__main__':
    main()
