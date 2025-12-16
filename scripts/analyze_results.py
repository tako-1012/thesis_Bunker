#!/usr/bin/env python3
"""
Analyze benchmark JSON files in `results/` and produce summary statistics.

Outputs: `results/analysis_summary.json` and prints a concise table.
"""
import json
import os
from pathlib import Path
import math
from collections import defaultdict


RESULTS_DIR = Path(__file__).resolve().parents[1] / 'results'
OUT_FILE = RESULTS_DIR / 'analysis_summary.json'


def find_time_field(d):
    # prefer exact known names
    candidates = ['computation_time', 'time_s', 'time_sec', 'time', 'duration', 'duration_s', 'duration_ms']
    for c in candidates:
        if c in d:
            return c
    # fallback: any key containing 'time' or 'duration' or 'ms'
    for k in d.keys():
        kl = k.lower()
        if 'time' in kl or 'duration' in kl or 'ms' in kl:
            return k
    return None


def is_success(d):
    if 'success' in d:
        return bool(d['success'])
    if 'status' in d:
        s = str(d['status']).lower()
        return s in ('ok', 'success', 'completed')
    # if neither present, assume success
    return True


def to_seconds(val, key_name=None):
    # If key name indicates ms, convert
    if key_name and 'ms' in key_name.lower():
        return float(val) / 1000.0
    try:
        v = float(val)
    except Exception:
        return None
    # Heuristic: if value > 1000, assume ms
    if v > 1000:
        return v / 1000.0
    return v


def safe_mean(xs):
    return sum(xs) / len(xs) if xs else None


def safe_std(xs):
    if not xs:
        return None
    mean = safe_mean(xs)
    var = sum((x-mean)**2 for x in xs) / len(xs)
    return math.sqrt(var)


def analyze_file(path: Path, aggregate):
    with open(path, 'r') as f:
        data = json.load(f)

    # Support two schemas: top-level 'results' dict mapping scenario-> {scenario, results}
    top_results = data.get('results', {})
    if isinstance(top_results, dict):
        # each scenario
        for scen_key, scen_val in top_results.items():
            scenario = scen_val.get('scenario', {})
            terrain_type = scenario.get('terrain_type') or scenario.get('terrain') or scenario.get('description') or 'unknown'
            # normalize terrain_type: look for keywords
            t = str(terrain_type).lower()
            if 'flat' in t:
                terrain = 'flat'
            elif 'slope' in t or 'gentle' in t or 'steep' in t or 'slope' in t:
                terrain = 'slope'
            elif 'complex' in t or 'obstacle' in t or 'hazard' in t:
                terrain = 'complex'
            else:
                terrain = t

            results_map = scen_val.get('results', {})
            if not isinstance(results_map, dict):
                continue
            for planner_name, r in results_map.items():
                # determine success
                if not is_success(r):
                    aggregate['attempts'][planner_name] += 1
                    aggregate['failures'][planner_name] += 1
                    continue
                aggregate['attempts'][planner_name] += 1
                # find time
                time_key = find_time_field(r)
                if time_key is None:
                    # skip if no time
                    aggregate['no_time_count'][planner_name] += 1
                    continue
                secs = to_seconds(r[time_key], key_name=time_key)
                if secs is None:
                    aggregate['no_time_count'][planner_name] += 1
                    continue
                aggregate['successes'][planner_name] += 1
                aggregate['times'][planner_name].append(secs)
                # per-terrain
                aggregate['terrain_times'][planner_name][terrain].append(secs)

    elif isinstance(top_results, list):
        # list of result entries
        for entry in top_results:
            planner_name = entry.get('planner_name') or entry.get('planner') or entry.get('algorithm') or 'unknown'
            if not is_success(entry):
                aggregate['attempts'][planner_name] += 1
                aggregate['failures'][planner_name] += 1
                continue
            aggregate['attempts'][planner_name] += 1
            time_key = find_time_field(entry)
            if time_key is None:
                aggregate['no_time_count'][planner_name] += 1
                continue
            secs = to_seconds(entry[time_key], key_name=time_key)
            if secs is None:
                aggregate['no_time_count'][planner_name] += 1
                continue
            aggregate['successes'][planner_name] += 1
            aggregate['times'][planner_name].append(secs)
            terrain = entry.get('complexity') or entry.get('terrain') or 'unknown'
            aggregate['terrain_times'][planner_name][terrain].append(secs)


def main():
    files = sorted([p for p in RESULTS_DIR.glob('benchmark_results_*.json')])
    if not files:
        print('No benchmark_results_*.json files found in results/.')
        return

    aggregate = {
        'attempts': defaultdict(int),
        'successes': defaultdict(int),
        'failures': defaultdict(int),
        'times': defaultdict(list),
        'terrain_times': defaultdict(lambda: defaultdict(list)),
        'no_time_count': defaultdict(int)
    }

    for f in files:
        analyze_file(f, aggregate)

    summary = {}
    for planner, times in aggregate['times'].items():
        summary[planner] = {
            'attempts': aggregate['attempts'][planner],
            'successes': aggregate['successes'][planner],
            'failures': aggregate['failures'][planner],
            'count_with_time': len(times),
            'mean_time_s': safe_mean(times),
            'std_time_s': safe_std(times),
            'min_time_s': min(times) if times else None,
            'max_time_s': max(times) if times else None,
            'terrain_means_s': {terrain: safe_mean(vals) for terrain, vals in aggregate['terrain_times'][planner].items()}
        }

    # write out
    with open(OUT_FILE, 'w') as f:
        json.dump({'files_analyzed': [str(p.name) for p in files], 'summary': summary}, f, indent=2)

    # print concise table
    print('\nAnalysis completed. Summary (per planner):')
    for planner, s in summary.items():
        print(f"\n- {planner}:")
        print(f"  Attempts: {s['attempts']}, Successes: {s['successes']}, Failures: {s['failures']}")
        print(f"  Count(with time): {s['count_with_time']}")
        print(f"  Mean time: {s['mean_time_s']:.4f}s  Std: {s['std_time_s']:.4f}s  Min: {s['min_time_s']:.4f}s  Max: {s['max_time_s']:.4f}s")
        print(f"  Terrain means:")
        for terrain, m in s['terrain_means_s'].items():
            print(f"    {terrain}: {m:.4f}s")

    print(f"\nDetailed JSON written to: {OUT_FILE}")


if __name__ == '__main__':
    main()
