#!/usr/bin/env python3
"""Analyze benchmark results, run statistical tests, generate visualizations and final reports.
This script is robust: errors are logged and processing proceeds where possible.
"""
import os
import sys
import json
import math
import time
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(__file__))
BR = os.path.join(ROOT, 'benchmark_results')
VIS = os.path.join(ROOT, 'visualization')
os.makedirs(VIS, exist_ok=True)

LOG = os.path.join(ROOT, 'progress_log.txt')

def log(msg):
    with open(LOG,'a') as f:
        f.write(f"[{time.ctime()}] {msg}\n")


def safe_load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        log(f"Failed to load {path}: {e}")
        return None


def enrich_path_lengths(data):
    changed = False
    for rec in data:
        if rec.get('path_length_meters') is None and rec.get('path'):
            try:
                path = rec['path']
                L = 0.0
                for i in range(len(path)-1):
                    a = path[i]; b = path[i+1]
                    dx = b[0]-a[0]; dy = b[1]-a[1]; dz = b[2]-a[2]
                    L += math.sqrt(dx*dx+dy*dy+dz*dz)
                rec['path_length_meters'] = L
                changed = True
            except Exception as e:
                rec['path_length_meters'] = None
                log(f"Failed computing length for rec {rec.get('scenario_id')}: {e}")
    return changed


def aggregate_by_planner(records):
    by_planner = defaultdict(list)
    for r in records:
        p = r.get('planner') or r.get('algorithm') or r.get('algorithm_name') or r.get('planner_name') or 'UNKNOWN'
        by_planner[p].append(r)
    return by_planner


def run_statistics(ta_vals, aha_vals):
    res = {}
    try:
        from scipy import stats
        import numpy as np
        ta = np.array(ta_vals)
        ah = np.array(aha_vals)
        # t-test (unequal variance)
        tstat, pval = stats.ttest_ind(ta, ah, equal_var=False, nan_policy='omit')
        # Cohen's d
        pooled_sd = math.sqrt(((ta.std(ddof=1)**2) + (ah.std(ddof=1)**2)) / 2.0)
        cohen_d = (ta.mean() - ah.mean()) / (pooled_sd if pooled_sd>0 else 1e-9)
        res.update({'t_stat': float(tstat), 'p_value': float(pval), 'cohen_d': float(cohen_d)})
    except Exception as e:
        log(f"Statistical tests skipped/failure: {e}")
        res['error'] = str(e)
    return res


def make_plots(all_records):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception as e:
        log(f"Plotting unavailable: {e}")
        return []

    files = []
    by_planner = aggregate_by_planner(all_records)
    planners = sorted(by_planner.keys())

    # path_length_comparison.png - boxplot
    fig, ax = plt.subplots(figsize=(10,6), dpi=300)
    data = [ [r.get('path_length_meters') for r in by_planner[p] if r.get('path_length_meters') is not None] for p in planners ]
    ax.boxplot(data, labels=planners, showfliers=False)
    ax.set_ylabel('Path length (m)')
    ax.set_title('Path length comparison')
    f1 = os.path.join(VIS, 'path_length_comparison.png')
    fig.tight_layout(); fig.savefig(f1); plt.close(fig)
    files.append(f1)

    # computation_time_comparison.png - boxplot
    fig, ax = plt.subplots(figsize=(10,6), dpi=300)
    data = [ [r.get('computation_time') for r in by_planner[p] if r.get('computation_time') is not None] for p in planners ]
    ax.boxplot(data, labels=planners, showfliers=False)
    ax.set_ylabel('Computation time (s)')
    ax.set_title('Computation time comparison')
    f2 = os.path.join(VIS, 'computation_time_comparison.png')
    fig.tight_layout(); fig.savefig(f2); plt.close(fig)
    files.append(f2)

    # tradeoff_plot.png - mean time vs mean length
    means = []
    for p in planners:
        vals = [r.get('path_length_meters') for r in by_planner[p] if r.get('path_length_meters') is not None]
        times = [r.get('computation_time') for r in by_planner[p] if r.get('computation_time') is not None]
        means.append((p, float(sum(vals)/len(vals)) if vals else None, float(sum(times)/len(times)) if times else None))
    fig, ax = plt.subplots(figsize=(8,6), dpi=300)
    # filter out planners with missing means
    filt = [m for m in means if (m[1] is not None and m[2] is not None)]
    if filt:
        xs = [m[2] for m in filt]
        ys = [m[1] for m in filt]
        labels = [m[0] for m in filt]
        ax.scatter(xs, ys)
        for i, txt in enumerate(labels):
            ax.annotate(txt, (xs[i], ys[i]))
    else:
        ax.text(0.5, 0.5, 'No data', ha='center')
    ax.set_xlabel('Mean computation time (s)')
    ax.set_ylabel('Mean path length (m)')
    ax.set_title('Time vs Path-length tradeoff')
    f3 = os.path.join(VIS, 'tradeoff_plot.png')
    fig.tight_layout(); fig.savefig(f3); plt.close(fig)
    files.append(f3)

    # environment_comparison.png - grouped by map_size for TA* and AHA*
    # try to extract TA* and AHA* only
    ta = [r for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('TA')!=-1]
    aha = [r for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('AHA')!=-1]
    try:
        import numpy as np
        sizes = ['SMALL','MEDIUM','LARGE']
        fig, ax = plt.subplots(figsize=(10,6), dpi=300)
        width = 0.35
        x = np.arange(len(sizes))
        ta_means = [ np.mean([r.get('path_length_meters') for r in ta if r.get('map_size')==s and r.get('path_length_meters') is not None]) if any(r.get('map_size')==s for r in ta) else 0 for s in sizes ]
        aha_means = [ np.mean([r.get('path_length_meters') for r in aha if r.get('map_size')==s and r.get('path_length_meters') is not None]) if any(r.get('map_size')==s for r in aha) else 0 for s in sizes ]
        ax.bar(x - width/2, ta_means, width, label='TA*')
        ax.bar(x + width/2, aha_means, width, label='AHA*')
        ax.set_xticks(x); ax.set_xticklabels(sizes)
        ax.set_ylabel('Mean path length (m)')
        ax.set_title('Environment (size) comparison: TA* vs AHA*')
        ax.legend()
        f4 = os.path.join(VIS, 'environment_comparison.png')
        fig.tight_layout(); fig.savefig(f4); plt.close(fig)
        files.append(f4)
    except Exception as e:
        log(f"Failed environment plot: {e}")

    return files


def make_reports(all_records, stats_results, plot_files):
    # FINAL_REPORT.md
    try:
        summary_lines = []
        summary_lines.append('# FINAL REPORT')
        # simple ranking by mean path length
        by_planner = aggregate_by_planner(all_records)
        ranking = []
        import statistics
        for p, recs in by_planner.items():
            vals = [r.get('path_length_meters') for r in recs if r.get('path_length_meters') is not None]
            if vals:
                ranking.append((p, statistics.mean(vals), len(vals)))
        ranking.sort(key=lambda x: x[1])
        summary_lines.append('\n## 7手法ランキング (平均経路長)')
        for i, (p, meanlen, n) in enumerate(ranking, start=1):
            summary_lines.append(f"{i}. {p}: {meanlen:.3f} m (n={n})")

        # TA* vs AHA*
        ta_vals = [r.get('path_length_meters') for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('TA')!=-1 and r.get('path_length_meters') is not None]
        aha_vals = [r.get('path_length_meters') for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('AHA')!=-1 and r.get('path_length_meters') is not None]
        summary_lines.append('\n## TA* vs AHA*')
        if ta_vals and aha_vals:
            summary_lines.append(f"TA* mean: {statistics.mean(ta_vals):.3f} m ({len(ta_vals)} samples)")
            summary_lines.append(f"AHA* mean: {statistics.mean(aha_vals):.3f} m ({len(aha_vals)} samples)")
            summary_lines.append('統計検定結果:')
            summary_lines.append(json.dumps(stats_results, indent=2))
        else:
            summary_lines.append('TA* or AHA* samples missing')

        # files
        summary_lines.append('\n## 生成ファイル')
        for fp in plot_files:
            summary_lines.append(f"- {os.path.relpath(fp, ROOT)}")

        final_path = os.path.join(ROOT, 'FINAL_REPORT.md')
        with open(final_path, 'w') as f:
            f.write('\n'.join(summary_lines))
        log(f"Wrote FINAL_REPORT.md")
    except Exception as e:
        log(f"Failed to create FINAL_REPORT.md: {e}")

    # PAPER_DATA.md minimal
    try:
        pd_lines = []
        pd_lines.append('%% PAPER_DATA for LaTeX tables')
        pd_lines.append('\n% Mean path lengths per planner')
        by_planner = aggregate_by_planner(all_records)
        import statistics
        pd_lines.append('\\begin{tabular}{lrr}')
        pd_lines.append('Planner & MeanLength & N \\\hline')
        for p, recs in by_planner.items():
            vals = [r.get('path_length_meters') for r in recs if r.get('path_length_meters') is not None]
            if not vals:
                continue
            pd_lines.append(f'{p} & {statistics.mean(vals):.3f} & {len(vals)} \\\\')
        pd_lines.append('\\end{tabular}')
        pd_path = os.path.join(ROOT, 'PAPER_DATA.md')
        with open(pd_path, 'w') as f:
            f.write('\n'.join(pd_lines))
        log('Wrote PAPER_DATA.md')
    except Exception as e:
        log(f"Failed to create PAPER_DATA.md: {e}")


def main():
    log('Starting analysis_and_report')
    # load main results
    full = safe_load_json(os.path.join(BR, 'full_benchmark_results.json')) or []

    # augment with AHA selected and TA* 96 if present
    extra = []
    for fname in ['ta_star_smoothed_96_full_results.json', 'aha_star_96_baseline_results.json', 'aha_star_96_optimized_results.json']:
        p = os.path.join(BR, fname)
        if os.path.exists(p):
            d = safe_load_json(p) or []
            # attach planner name if missing
            for r in d:
                if 'planner' not in r:
                    if 'nodes_explored' in r and 'iterations' in r:
                        r['planner'] = 'AHA*'
                    else:
                        r['planner'] = r.get('planner', 'UNKNOWN')
            extra.extend(d)
    all_records = list(full) + extra

    # Phase 3: ensure path_length_meters
    try:
        changed = enrich_path_lengths(all_records)
        if changed:
            outp = os.path.join(BR, 'full_benchmark_results_enriched.json')
            with open(outp,'w') as f:
                json.dump(all_records, f, indent=2)
            log('Enriched path lengths and saved full_benchmark_results_enriched.json')
    except Exception as e:
        log(f'Phase3 enrichment error: {e}')

    # Phase 4: stats and plots
    ta_vals = [r.get('path_length_meters') for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('TA')!=-1 and r.get('path_length_meters') is not None]
    aha_vals = [r.get('path_length_meters') for r in all_records if (r.get('planner') or r.get('algorithm_name') or '').upper().find('AHA')!=-1 and r.get('path_length_meters') is not None]
    stats_results = run_statistics(ta_vals, aha_vals)
    with open(os.path.join(BR, 'statistical_tests_results.json'), 'w') as f:
        json.dump(stats_results, f, indent=2)
    plot_files = make_plots(all_records)

    # Phase 5: reports
    make_reports(all_records, stats_results, plot_files)

    log('analysis_and_report complete')


if __name__ == '__main__':
    main()
