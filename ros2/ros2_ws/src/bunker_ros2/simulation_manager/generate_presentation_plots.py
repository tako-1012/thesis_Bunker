#!/usr/bin/env python3
"""Generate presentation-ready high-resolution plots and TSVs.

Settings:
 - DPI 300, fonts: title 16, axis 14, legend 12
 - Aspect ratio 16:9
 - Output PNG (300dpi) and PDF (vector) and TSVs into `presentation/`
"""
import json
from pathlib import Path
from collections import defaultdict
import statistics
import csv

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
except Exception:
    print('matplotlib/numpy are required')
    raise

# Prefer a CJK-capable font when available so Japanese labels render correctly
try:
    import matplotlib.font_manager as _fm
    preferred_fonts = ['Noto Sans CJK JP', 'Noto Sans CJK', 'Noto Sans JP', 'TakaoPGothic', 'DejaVu Sans']
    available = [f.name for f in _fm.fontManager.ttflist]
    for _name in preferred_fonts:
        if _name in available:
            import matplotlib
            matplotlib.rcParams['font.family'] = _name
            break
except Exception:
    pass

ROOT = Path('ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results')
OUT = ROOT / 'presentation'
OUT.mkdir(parents=True, exist_ok=True)

FULL = ROOT / 'full_benchmark_results.json'
DIJ = ROOT / 'dijkstra_dwa_results.json'

FONT_TITLE = 16
FONT_AX = 14
FONT_LEG = 12
DPI = 300
ASPECT_RATIO = (16,9)

def safe_mean(lst):
    return statistics.mean(lst) if lst else float('nan')

def load_full():
    with open(FULL,'r') as f:
        return json.load(f)

def load_dijkstra():
    with open(DIJ,'r') as f:
        j=json.load(f)
    runs = j.get('runs',[]) if isinstance(j,dict) else j
    return runs, j

def compute_all_planner_summary(full_data, dij_runs):
    # from full_data compute per-planner per-size avg time and success rate
    def map_size(name):
        n=(name or '').lower()
        if 'small' in n: return 'Small'
        if 'medium' in n: return 'Medium'
        if 'large' in n: return 'Large'
        return 'Unknown'

    planners = defaultdict(lambda: defaultdict(list))
    counts = defaultdict(lambda: defaultdict(int))
    for e in full_data:
        p=e.get('planner_name')
        s=map_size(e.get('scenario_name',''))
        t=e.get('computation_time')
        succ=bool(e.get('success'))
        counts[p][s]+=1
        if t is not None:
            planners[p][s].append((t,succ))

    # include DIJKSTRA from dij_runs
    dij_map = defaultdict(list)
    dij_counts = defaultdict(int)
    for r in dij_runs:
        name = r.get('scenario') or r.get('scenario_name') or ''
        ln = (name or '').lower()
        if any(tok in ln for tok in ('short','flat','minimal')):
            size='Small'
        elif any(tok in ln for tok in ('medium','long')):
            size='Medium'
        elif any(tok in ln for tok in ('large','complex','spiral','zigzag','steep')):
            size='Large'
        else:
            size='Unknown'
        t = r.get('computation_time')
        succ = bool(r.get('success'))
        dij_counts[size]+=1
        if t is not None:
            dij_map[size].append((t,succ))

    # build summary list including DIJKSTRA_DWA
    summary = []
    for p, sizes in planners.items():
        for s, vals in sizes.items():
            total = counts[p][s]
            succ_count = sum(1 for (_t,ss) in vals if ss)
            times = [t for (t,ss) in vals if ss]
            summary.append({'planner':p,'map_size':s,'avg_time': safe_mean(times),'success_rate': (succ_count/total*100.0 if total>0 else float('nan')),'total_runs': total,'success_count': succ_count})

    # add DIJKSTRA_DWA (initially from runs)
    total_d = sum(dij_counts.values())
    for s, vals in dij_map.items():
        total = dij_counts[s]
        succ_count = sum(1 for (t,ss) in vals if ss)
        times = [t for (t,ss) in vals if ss]
        summary.append({'planner':'DIJKSTRA_DWA','map_size':s,'avg_time': safe_mean(times),'success_rate': (succ_count/total*100.0 if total>0 else float('nan')),'total_runs': total,'success_count': succ_count})

    # If a curated dijkstra summary CSV exists, prefer its values (canonical source)
    dij_csv = ROOT / 'dijkstra_detailed_stats.csv'
    if dij_csv.exists():
        # parse CSV of form metric,value
        vals = {}
        try:
            with open(dij_csv,'r') as fh:
                for line in fh:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        k = parts[0].strip()
                        v = parts[1].strip()
                        vals[k] = v
        except Exception:
            vals = {}
        # map metrics to summary override
        # expected keys: Small_total, Small_success, Small_success_rate, Small_avg_time_success, etc.
        override_rows = []
        for size in ('Small','Medium','Large'):
            tot_k = f'{size}_total'
            succ_k = f'{size}_success'
            rate_k = f'{size}_success_rate'
            avg_k = f'{size}_avg_time_success'
            if rate_k in vals or avg_k in vals:
                try:
                    total = int(float(vals.get(tot_k, '0')))
                except Exception:
                    total = 0
                try:
                    succ_count = int(float(vals.get(succ_k, '0')))
                except Exception:
                    succ_count = 0
                try:
                    success_rate = float(vals.get(rate_k, 'nan'))
                except Exception:
                    success_rate = float('nan')
                try:
                    avg_time = float(vals.get(avg_k, 'nan'))
                except Exception:
                    avg_time = float('nan')
                override_rows.append({'planner':'DIJKSTRA_DWA','map_size':size,'avg_time': avg_time,'success_rate': success_rate,'total_runs': total,'success_count': succ_count})
        # remove existing DIJKSTRA_DWA rows and append overrides
        summary = [r for r in summary if r.get('planner')!='DIJKSTRA_DWA'] + override_rows

    return summary

def write_tsv(summary, path):
    fields = ['planner','map_size','avg_time','success_rate','total_runs','success_count']
    with open(path,'w',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=fields,delimiter='\t')
        w.writeheader()
        for r in sorted(summary, key=lambda x:(x['planner'], x['map_size'])):
            w.writerow({k: ('' if (isinstance(r.get(k), float) and (r.get(k)!=r.get(k))) else r.get(k)) for k in fields})

def plot_all_planners(summary):
    planners = sorted(set(r['planner'] for r in summary))
    sizes = ['Small','Medium','Large']
    avg_map = {p:{s:float('nan') for s in sizes} for p in planners}
    succ_map = {p:{s:float('nan') for s in sizes} for p in planners}
    for r in summary:
        p=r['planner']; s=r['map_size']
        if s in sizes:
            avg_map[p][s]=r['avg_time']
            succ_map[p][s]=r['success_rate']

    # mapping for display names (Japanese-friendly)
    DISPLAY_MAP = {
        'ADAPTIVE': 'TA*（提案）',
        'DIJKSTRA_DWA': 'Dijkstra',
        'DSTAR_LITE': 'D* Lite',
        'HPA_STAR': 'HPA*',
        'RRT_STAR': 'RRT*',
        'SAFETY_FIRST': 'SAFETY'
    }
    display_names = [DISPLAY_MAP.get(p, p) for p in planners]

    x = np.arange(len(planners))
    width = 0.2
    fig, ax = plt.subplots(figsize=(16,9))
    size_labels_jp = {'Small': '小', 'Medium': '中', 'Large': '大'}
    for i,s in enumerate(sizes):
        vals = [avg_map[p][s] if not (isinstance(avg_map[p][s], float) and (avg_map[p][s]!=avg_map[p][s])) else 0.0 for p in planners]
        ax.bar(x + (i-1)*width, vals, width, label=size_labels_jp.get(s, s))
    ax.set_xticks(x)
    ax.set_xticklabels(display_names, rotation=45, ha='right', fontsize=FONT_AX)
    ax.set_ylabel('計算時間（秒）', fontsize=FONT_AX)
    ax.set_title('全手法のマップサイズ別平均計算時間', fontsize=FONT_TITLE)
    ax.legend(title='マップサイズ', fontsize=FONT_LEG)
    # use linear scale for presentation (avoid log which hides small values)
    ax.set_yscale('linear')
    # set reasonable ylim based on data to keep small values visible
    try:
        import numpy as _np
        all_vals = []
        for p in planners:
            for s in sizes:
                v = avg_map.get(p, {}).get(s)
                if isinstance(v, (int, float)) and (v==v):
                    all_vals.append(v)
        if all_vals:
            vmax = max(all_vals)
            ax.set_ylim(0, vmax * 1.2)
    except Exception:
        pass
    fig.tight_layout()
    png = OUT / 'all_planners_by_size_300dpi.png'
    pdf = OUT / 'all_planners_by_size.pdf'
    fig.savefig(png, dpi=DPI)
    fig.savefig(pdf)
    plt.close(fig)

    # success rate plot
    fig, ax = plt.subplots(figsize=(16,9))
    for i,s in enumerate(sizes):
        vals = [succ_map[p][s] if not (isinstance(succ_map[p][s], float) and (succ_map[p][s]!=succ_map[p][s])) else 0.0 for p in planners]
        ax.bar(x + (i-1)*width, vals, width, label=size_labels_jp.get(s, s))
    ax.set_xticks(x)
    ax.set_xticklabels(display_names, rotation=45, ha='right', fontsize=FONT_AX)
    ax.set_ylabel('成功率（%）', fontsize=FONT_AX)
    ax.set_title('手法別成功率（マップサイズごと）', fontsize=FONT_TITLE)
    ax.legend(title='マップサイズ', fontsize=FONT_LEG)
    fig.tight_layout()
    png2 = OUT / 'success_rate_comparison_300dpi.png'
    pdf2 = OUT / 'success_rate_comparison.pdf'
    fig.savefig(png2, dpi=DPI)
    fig.savefig(pdf2)
    plt.close(fig)

def plot_ta_boxplot(full_data):
    # ADAPTIVE by complexity
    entries = [e for e in full_data if e.get('planner_name')=='ADAPTIVE' and e.get('success') and e.get('computation_time') is not None]
    by_comp = defaultdict(list)
    for e in entries:
        comp = e.get('complexity')
        by_comp[comp].append(e.get('computation_time'))
    labels = sorted(by_comp.keys())
    data = [by_comp[l] for l in labels]
    fig, ax = plt.subplots(figsize=(16,9))
    ax.boxplot(data, labels=labels, showmeans=True)
    ax.set_ylabel('Computation Time (s)', fontsize=FONT_AX)
    ax.set_title('ADAPTIVE (TA*) by Complexity', fontsize=FONT_TITLE)
    ax.tick_params(axis='x', labelsize=FONT_AX)
    fig.tight_layout()
    png = OUT / 'ta_star_complexity_boxplot_300dpi.png'
    pdf = OUT / 'ta_star_complexity_boxplot.pdf'
    fig.savefig(png, dpi=DPI)
    fig.savefig(pdf)
    plt.close(fig)

def plot_dijkstra(dij_runs, dij_meta):
    # bucket sizes and compute success rates and successful times
    by_size = defaultdict(list)
    counts = defaultdict(int)
    for r in dij_runs:
        name = r.get('scenario') or r.get('scenario_name') or ''
        ln = (name or '').lower()
        if any(tok in ln for tok in ('short','flat','minimal')):
            size='Small'
        elif any(tok in ln for tok in ('medium','long')):
            size='Medium'
        elif any(tok in ln for tok in ('large','complex','spiral','zigzag','steep')):
            size='Large'
        else:
            size='Unknown'
        counts[size]+=1
        by_size[size].append(r)

    sizes = ['Small','Medium','Large']
    success_rates = []
    for s in sizes:
        lst = by_size.get(s,[])
        tot = len(lst)
        succ = sum(1 for e in lst if e.get('success'))
        success_rates.append((succ/tot*100.0) if tot>0 else 0.0)

    fig, ax = plt.subplots(figsize=(16,9))
    ax.bar(sizes, success_rates, color=['#6bbf59','#f4c542','#e05a5a'])
    ax.set_ylabel('Success Rate (%)', fontsize=FONT_AX)
    ax.set_title('Dijkstra+DWA Success Rate by Map Size', fontsize=FONT_TITLE)
    fig.tight_layout()
    png = OUT / 'dijkstra_success_by_size_300dpi.png'
    pdf = OUT / 'dijkstra_success_by_size.pdf'
    fig.savefig(png, dpi=DPI)
    fig.savefig(pdf)
    plt.close(fig)

    # time distribution of successful runs
    times = [e.get('computation_time') for e in dij_runs if e.get('success') and e.get('computation_time') is not None]
    fig, ax = plt.subplots(figsize=(16,9))
    ax.hist(times, bins=30, color='#4c72b0')
    ax.set_xlabel('Computation Time (s)', fontsize=FONT_AX)
    ax.set_ylabel('Count', fontsize=FONT_AX)
    ax.set_title('Dijkstra+DWA Successful Time Distribution', fontsize=FONT_TITLE)
    fig.tight_layout()
    png2 = OUT / 'dijkstra_time_distribution_300dpi.png'
    pdf2 = OUT / 'dijkstra_time_distribution.pdf'
    fig.savefig(png2, dpi=DPI)
    fig.savefig(pdf2)
    plt.close(fig)

    # write TSV summary for dijkstra
    out_tsv = OUT / 'dijkstra_detailed_stats_presentation.tsv'
    with open(out_tsv,'w',newline='') as fh:
        w=csv.writer(fh, delimiter='\t')
        w.writerow(['metric','value'])
        w.writerow(['total_runs', dij_meta.get('total_runs', len(dij_runs))])
        w.writerow(['successful_runs', dij_meta.get('successful_runs', sum(1 for e in dij_runs if e.get('success')))])
        w.writerow(['failed_runs', dij_meta.get('failed_runs', sum(1 for e in dij_runs if not e.get('success')))])
        for s in sizes:
            lst = by_size.get(s,[])
            tot = len(lst)
            succ = sum(1 for e in lst if e.get('success'))
            w.writerow([f'{s}_total', tot])
            w.writerow([f'{s}_success', succ])
            w.writerow([f'{s}_success_rate', (succ/tot*100.0) if tot>0 else 0.0])


def main():
    full = load_full()
    dij_runs, dij_meta = load_dijkstra()
    summary = compute_all_planner_summary(full, dij_runs)
    # write TSV of all planners
    write_tsv(summary, OUT / 'all_planners_comparison_presentation.tsv')
    # plots
    plot_all_planners(summary)
    plot_ta_boxplot(full)
    plot_dijkstra(dij_runs, dij_meta)
    print('Wrote presentation outputs to', OUT)


if __name__ == '__main__':
    main()
