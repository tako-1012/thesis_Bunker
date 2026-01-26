#!/usr/bin/env python3
"""Reproduce midterm (12/23) ADAPTIVE experiments and analyze smoothing effects.

Phases implemented:
 A-1: generate scenarios with same counts as midterm and save scenario_ids.json
 A-2: run ADAPTIVE (TA*) nosmooth and smoothed (Shortcut) and save results
 B-1/B-2: compute per-scenario smoothing effects and statistics
 B-2: generate PNG visualizations

Outputs (benchmark_results/):
 - scenario_ids.json
 - ta_star_midterm_reproduction_results.json
 - ta_star_midterm_reproduction_summary.json
 - ta_star_midterm_smoothed_results.json
 - ta_star_midterm_smoothed_summary.json
 - smoothing_effect_per_scenario.json
 - smoothing_effect_statistics.json
 - comparison CSVs and PNGs
"""
import os, sys, time, json, math
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_ROOT = os.path.abspath(os.path.join(ROOT, '..'))
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np
import multiprocessing as mp

from benchmark_full import PlannerBenchmark
from path_planner_3d.path_smoother import PathSmoother
from path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar


OUT_DIR = os.path.join(ROOT, 'benchmark_results')
os.makedirs(OUT_DIR, exist_ok=True)


def generate_midterm_scenarios():
    bench = PlannerBenchmark(output_dir=OUT_DIR)
    specs = {"SMALL": 30, "MEDIUM": 48, "LARGE": 18}
    scenarios = bench.generate_test_scenarios(num_scenarios_per_scale=specs)
    # convert numpy arrays to lists for JSON
    scen_list = []
    for s in scenarios:
        scen_list.append({
            'name': s.name,
            'start': s.start.tolist(),
            'goal': s.goal.tolist(),
            'bounds': s.bounds,
            'map_size': s.map_size,
            'complexity': s.complexity,
        })
    with open(os.path.join(OUT_DIR, 'scenario_ids.json'), 'w') as f:
        json.dump(scen_list, f, indent=2)
    return scenarios


def worker_run_single(scen, do_smooth=False, return_pipe=None):
    try:
        # instantiate TA* similarly to other scripts
        start = tuple(scen.start)
        goal = tuple(scen.goal)
        grid_size = 100 if scen.map_size == 'SMALL' else (500 if scen.map_size == 'MEDIUM' else 1000)
        world_size = 10.0 if scen.map_size == 'SMALL' else (50.0 if scen.map_size == 'MEDIUM' else 100.0)
        z_dim = max(50, grid_size // 10)
        ta = TerrainAwareAStar(voxel_size=0.5, grid_size=(grid_size, grid_size, z_dim), min_bound=(0.0,0.0,0.0), use_cost_calculator=False)
        # create dummy voxel grid and set terrain if available on scenario
        try:
            cost_map = scen.terrain_cost_map
        except Exception:
            cost_map = np.ones((grid_size, grid_size), dtype=np.float32) * 0.1
        voxel_grid = np.zeros((grid_size, grid_size, z_dim), dtype=np.uint8)
        ta.set_terrain_data(voxel_grid, {'slopes': np.array([0.0]), 'terrain_cost_map': cost_map})

        t0 = time.time()
        path = ta.plan_path(start, goal)
        smooth_time = 0.0
        if do_smooth and path is not None:
            st0 = time.time()
            smoother = PathSmoother()
            sm = smoother.shortcut(path, ta, max_iter=10)
            st1 = time.time()
            smooth_time = st1 - st0
            if sm is not None and len(sm) <= len(path):
                path = sm
        t1 = time.time()
        elapsed = t1 - t0
        success = path is not None and len(path) > 1
        path_length = None
        if success:
            path_length = float(np.sum([np.linalg.norm(np.array(path[i+1]) - np.array(path[i])) for i in range(len(path)-1)]))
        res = {
            'scenario_name': scen.name,
            'map_size': scen.map_size,
            'complexity': scen.complexity,
            'success': success,
            'computation_time': elapsed,
            'smoothing_time': smooth_time,
            'path_length_meters': path_length,
            'nodes_explored': ta.last_search_stats.get('nodes_explored', None) if hasattr(ta, 'last_search_stats') else None,
        }
        if return_pipe:
            return_pipe.send(('ok', res))
        else:
            return res
    except Exception as e:
        if return_pipe:
            return_pipe.send(('err', str(e)))
        else:
            return {'scenario_name': scen.name, 'error': str(e)}


def run_reproduction(scenarios, do_smooth=False, timeout_map=None, out_file='ta_star_midterm_reproduction_results.json'):
    results = []
    total = len(scenarios)
    out_path = os.path.join(OUT_DIR, out_file)
    for i, scen in enumerate(scenarios):
        idx = i+1
        print(f"[{idx}/{total}] {'SMOOTH' if do_smooth else 'NOSMOOTH'} {scen.name}...", flush=True)
        parent_conn, child_conn = mp.Pipe()
        p = mp.Process(target=worker_run_single, args=(scen, do_smooth, child_conn))
        p.start()
        # timeout per size
        if scen.map_size == 'SMALL': to = 30
        elif scen.map_size == 'MEDIUM': to = 60
        else: to = 120
        p.join(timeout=to)
        if p.is_alive():
            p.terminate(); p.join()
            print('  Timeout')
            results.append({'scenario_name': scen.name, 'error': 'timeout'})
        else:
            try:
                status, payload = parent_conn.recv()
                if status == 'ok': results.append(payload)
                else: results.append({'scenario_name': scen.name, 'error': payload})
            except EOFError:
                results.append({'scenario_name': scen.name, 'error': 'no_result'})
        # flush
        with open(out_path, 'w') as f:
            json.dump(results, f, indent=2)
    return results


def summarize(results):
    succ = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]
    by_size = defaultdict(list)
    for r in succ:
        by_size[r['map_size']].append(r['computation_time'])
    stats = {}
    for k,v in by_size.items():
        stats[k] = {'count': len(v), 'mean': float(np.mean(v)), 'median': float(np.median(v))}
    return {'total': len(results), 'success': len(succ), 'fail': len(failed), 'by_size': stats}


def analyze_smoothing(nos_results, smo_results):
    # map by scenario_name
    nos_map = {r['scenario_name']: r for r in nos_results if 'scenario_name' in r}
    smo_map = {r['scenario_name']: r for r in smo_results if 'scenario_name' in r}
    per = []
    size_buckets = defaultdict(list)
    for name, n in nos_map.items():
        s = smo_map.get(name)
        if s is None or 'error' in n or 'error' in s:
            continue
        before_len = n.get('path_length_meters')
        after_len = s.get('path_length_meters')
        if before_len is None or after_len is None:
            continue
        improvement = (before_len - after_len) / before_len * 100.0 if before_len>0 else 0.0
        time_diff = s.get('computation_time') - n.get('computation_time')
        pct_overhead = (time_diff / n.get('computation_time') * 100.0) if n.get('computation_time') and n.get('computation_time')>0 else None
        rec = {'scenario_name': name, 'map_size': n['map_size'], 'before_len': before_len, 'after_len': after_len, 'improvement_pct': improvement, 'time_diff_s': time_diff, 'overhead_pct': pct_overhead}
        per.append(rec)
        size_buckets[n['map_size']].append(rec['improvement_pct'])
    # stats per size
    stats = {}
    for size, vals in size_buckets.items():
        stats[size] = {'count': len(vals), 'mean_impr': float(np.mean(vals)), 'median_impr': float(np.median(vals)), 'max_impr': float(np.max(vals)), 'min_impr': float(np.min(vals)), 'std_impr': float(np.std(vals))}
    return per, stats


def write_csvs(nos_summary, smo_summary, per_smoothing, smoothing_stats):
    import csv
    # comparison CSV
    comp_csv = os.path.join(OUT_DIR, 'midterm_reproduction_comparison.csv')
    with open(comp_csv, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['環境','中間発表','再現(なし)_mean','再現(あり)_mean','差(なし)','差(あり)'])
        # midterm reference: read from all_planners_comparison.csv
        ref_csv = os.path.join(ROOT, 'all_planners_comparison.csv')
        ref = {}
        if os.path.exists(ref_csv):
            with open(ref_csv) as f:
                for line in f:
                    if line.startswith('ADAPTIVE,'):
                        parts = line.strip().split(',')
                        if len(parts)>=3:
                            ref[parts[1]] = float(parts[2])
        for size in ['Small','Medium','Large']:
            mid = ref.get(size, '')
            nmean = nos_summary['by_size'].get(size, {}).get('mean','')
            smean = smo_summary['by_size'].get(size, {}).get('mean','')
            w.writerow([size, mid, nmean, smean, (nmean-mid) if mid!='' and nmean!='' else '', (smean-mid) if mid!='' and smean!='' else ''])

    # smoothing effect per scenario
    with open(os.path.join(OUT_DIR, 'smoothing_effect_per_scenario.json'), 'w') as f:
        json.dump(per_smoothing, f, indent=2)
    with open(os.path.join(OUT_DIR, 'smoothing_effect_statistics.json'), 'w') as f:
        json.dump(smoothing_stats, f, indent=2)


def make_plots(nos_summary, smo_summary, per_smoothing):
    import matplotlib.pyplot as plt
    sizes = ['Small','Medium','Large']
    n_means = [nos_summary['by_size'].get(s, {}).get('mean', float('nan')) for s in sizes]
    s_means = [smo_summary['by_size'].get(s, {}).get('mean', float('nan')) for s in sizes]
    mid_refs = []
    # read midterm refs
    ref_csv = os.path.join(ROOT, 'all_planners_comparison.csv')
    ref = {}
    if os.path.exists(ref_csv):
        with open(ref_csv) as f:
            for line in f:
                if line.startswith('ADAPTIVE,'):
                    parts=line.strip().split(',')
                    if len(parts)>=3: ref[parts[1]] = float(parts[2])
    mid_refs = [ref.get(s, float('nan')) for s in sizes]

    # Fig1 three-way computation time
    x = np.arange(len(sizes))
    width = 0.25
    fig, ax = plt.subplots(figsize=(6,3))
    ax.bar(x - width, mid_refs, width, label='Midterm', color='gray')
    ax.bar(x, n_means, width, label='96 nosmooth', color='C0')
    ax.bar(x + width, s_means, width, label='96 smoothed', color='C2')
    ax.set_xticks(x); ax.set_xticklabels(sizes)
    ax.set_yscale('log')
    ax.set_ylabel('Computation time (s, log)')
    ax.legend()
    fig.savefig(os.path.join(OUT_DIR, 'comparison_computation_time_three_way.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Fig2 overhead percentage
    overheads = []
    for i,s in enumerate(sizes):
        n=n_means[i]; m=mid_refs[i]
        if not math.isnan(n) and not math.isnan(m) and m>0:
            overheads.append((n - m)/m*100.0)
        else:
            overheads.append(float('nan'))
    fig, ax = plt.subplots(figsize=(5,3))
    colors = ['red' if v>0 else 'green' for v in overheads]
    ax.bar(sizes, overheads, color=colors)
    ax.axhline(0, color='k', linewidth=0.6)
    ax.set_ylabel('Overhead vs midterm (%)')
    fig.savefig(os.path.join(OUT_DIR, 'smoothing_overhead_percentage.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Fig3 path length improvement boxplots
    by_size = defaultdict(list)
    for r in per_smoothing:
        by_size[r['map_size']].append(r['improvement_pct'])
    data = [by_size.get(s, []) for s in sizes]
    fig, ax = plt.subplots(figsize=(6,3))
    ax.boxplot(data, labels=sizes, showmeans=True)
    ax.set_ylabel('Path length improvement (%)')
    fig.savefig(os.path.join(OUT_DIR, 'path_length_improvement.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Fig4 scatter smoothing none vs smoothed lengths
    xs = [r['before_len'] for r in per_smoothing]
    ys = [r['after_len'] for r in per_smoothing]
    cmap = {'SMALL': 'C0','MEDIUM':'C1','LARGE':'C2'}
    fig, ax = plt.subplots(figsize=(5,5))
    for r in per_smoothing:
        ax.scatter(r['before_len'], r['after_len'], color=cmap.get(r['map_size'], 'k'), alpha=0.7)
    maxv = max(max(xs or [0]), max(ys or [0]))
    ax.plot([0,maxv],[0,maxv], '--', color='gray')
    ax.set_xlabel('No-smooth path length (m)')
    ax.set_ylabel('Smoothed path length (m)')
    fig.savefig(os.path.join(OUT_DIR, 'smoothing_effect_scatter.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)

    # Fig5 time vs quality tradeoff
    fig, ax = plt.subplots(figsize=(6,4))
    for r in per_smoothing:
        nt = nos_map_time.get(r['scenario_name'], 0.0)
        st = smo_map_time.get(r['scenario_name'], 0.0)
        ax.scatter(nt, r['before_len'], color='C0', alpha=0.4)
        ax.scatter(st, r['after_len'], color='C2', alpha=0.4)
    ax.set_xlabel('Computation time (s)')
    ax.set_ylabel('Path length (m)')
    fig.savefig(os.path.join(OUT_DIR, 'time_vs_quality_tradeoff.png'), dpi=300, bbox_inches='tight')
    plt.close(fig)


if __name__ == '__main__':
    print('Phase A-1: Generate scenarios (midterm spec)')
    scenarios = generate_midterm_scenarios()
    print(f'Generated {len(scenarios)} scenarios; saved to scenario_ids.json')

    print('Phase A-2: Run ADAPTIVE (no smoothing)')
    nos = run_reproduction(scenarios, do_smooth=False, out_file='ta_star_midterm_reproduction_results.json')
    with open(os.path.join(OUT_DIR, 'ta_star_midterm_reproduction_results.json'), 'w') as f:
        json.dump(nos, f, indent=2)
    nos_summary = summarize(nos)
    with open(os.path.join(OUT_DIR, 'ta_star_midterm_reproduction_summary.json'), 'w') as f:
        json.dump(nos_summary, f, indent=2)

    print('Phase A-2: Run ADAPTIVE (with Shortcut smoothing)')
    smo = run_reproduction(scenarios, do_smooth=True, out_file='ta_star_midterm_smoothed_results.json')
    with open(os.path.join(OUT_DIR, 'ta_star_midterm_smoothed_results.json'), 'w') as f:
        json.dump(smo, f, indent=2)
    smo_summary = summarize(smo)
    with open(os.path.join(OUT_DIR, 'ta_star_midterm_smoothed_summary.json'), 'w') as f:
        json.dump(smo_summary, f, indent=2)

    print('Phase B: Analyze smoothing effect')
    per_smoothing, smoothing_stats = analyze_smoothing(nos, smo)
    with open(os.path.join(OUT_DIR, 'smoothing_effect_per_scenario.json'), 'w') as f:
        json.dump(per_smoothing, f, indent=2)
    with open(os.path.join(OUT_DIR, 'smoothing_effect_statistics.json'), 'w') as f:
        json.dump(smoothing_stats, f, indent=2)

    print('Write comparison CSVs')
    write_csvs(nos_summary, smo_summary, per_smoothing, smoothing_stats)

    print('Generate plots')
    # prepare globals for plot function
    # build maps for time lookup
    global nos_map_time, smo_map_time
    nos_map_time = {r.get('scenario_name'): r.get('computation_time') for r in nos if 'scenario_name' in r}
    smo_map_time = {r.get('scenario_name'): r.get('computation_time') for r in smo if 'scenario_name' in r}
    make_plots(nos_summary, smo_summary, per_smoothing)

    print('All done. Outputs under', OUT_DIR)
