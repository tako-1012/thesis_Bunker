#!/usr/bin/env python3
import os
import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

BASE = os.path.join('ros2','ros2_ws','src','path_planner_3d','path_planner_3d','benchmark_results')
JSON_FILE = os.path.join(BASE, 'benchmark_results.json')
OUT_DIR = 'presentation'
BAR_OUT = os.path.join(OUT_DIR, 'complexity_comparison_300dpi.png')
BOX_OUT = os.path.join(OUT_DIR, 'complexity_boxplot_300dpi.png')

# target planners mapping from dataset names to display names
PLANNER_MAP = {
    'ADAPTIVE': 'TA*',
    'TA_STAR': 'TA*',
    'DSTAR_LITE': 'D* Lite',
    'SAFETY_FIRST': 'SAFETY',
    'HPA_STAR': 'HPA*',
    'RRT_STAR': 'RRT*',
    'DIJKSTRA_DWA': 'Dijkstra',
    'DIJKSTRA': 'Dijkstra',
}

COMPLEXITIES = ['SIMPLE','MODERATE','COMPLEX']

def load_data():
    with open(JSON_FILE) as f:
        data = json.load(f)
    # structure: planner -> complexity -> list of times (success only)
    results = {}
    for entry in data:
        pname = entry.get('planner_name')
        comp = entry.get('complexity')
        time = entry.get('computation_time')
        succ = entry.get('success', True)
        if pname is None or comp is None or time is None:
            continue
        # map planner name
        if pname in PLANNER_MAP:
            key = PLANNER_MAP[pname]
        else:
            # skip planners not in map
            continue
        if not succ:
            # skip failures for timing distributions (matches earlier note for Dijkstra)
            continue
        results.setdefault(key, {}).setdefault(comp, []).append(float(time))
    return results

def ensure_font():
    # prefer Noto Sans CJK JP if available, fallback to DejaVu Sans
    preferred = ['Noto Sans CJK JP','Noto Sans CJK JP Regular','Noto Sans CJK','DejaVu Sans']
    available = [f.name for f in font_manager.fontManager.ttflist]
    for name in preferred:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            return name
    # otherwise leave default
    return None

def plot_grouped_bar(results):
    planners = ['TA*','D* Lite','SAFETY','HPA*','RRT*','Dijkstra']
    n_planners = len(planners)
    values = np.full((len(COMPLEXITIES), n_planners), np.nan)
    for j,p in enumerate(planners):
        for i,c in enumerate(COMPLEXITIES):
            arr = results.get(p, {}).get(c, [])
            if arr:
                values[i,j] = np.mean(arr)

    fig_w = 1200/300; fig_h = 800/300
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    x = np.arange(len(COMPLEXITIES))
    total_width = 0.8
    width = total_width / n_planners
    cmap = plt.get_cmap('tab10')
    for j in range(n_planners):
        offs = x - total_width/2 + width/2 + j*width
        ax.bar(offs, values[:,j], width=width, label=planners[j], color=cmap(j%10))

    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(COMPLEXITIES, fontsize=10)
    ax.set_ylabel('計算時間 (秒, log scale)', fontsize=10)
    ax.set_title('全6手法の複雑度別平均計算時間', fontsize=12)
    ax.grid(axis='y', which='both', linestyle='--', linewidth=0.5)
    ax.legend(title='手法', fontsize=9, title_fontsize=10, loc='upper left', bbox_to_anchor=(1.02,1))
    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(BAR_OUT, dpi=300)
    plt.close(fig)
    print(f'Saved {BAR_OUT}')

def plot_boxplot(results):
    planners = ['TA*','D* Lite','SAFETY','HPA*','RRT*','Dijkstra']
    n = len(planners)
    # We will create grouped boxplots: for each planner, three boxes for SIMPLE/MODERATE/COMPLEX
    data_groups = []
    labels = []
    colors = []
    cmap = plt.get_cmap('Set2')
    for i,p in enumerate(planners):
        for j,c in enumerate(COMPLEXITIES):
            arr = results.get(p, {}).get(c, [])
            data_groups.append(arr if arr else [np.nan])
            labels.append(p if j==1 else '')  # show planner label once centered
            colors.append(cmap(j))

    fig_w = 1200/300; fig_h = 800/300
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    # positions
    positions = []
    spacing = 1.5
    pos = 1
    for i in range(n):
        positions.extend([pos, pos+0.4, pos+0.8])
        pos += spacing

    bp = ax.boxplot(data_groups, positions=positions, widths=0.35, patch_artist=True, showfliers=False)
    for patch, col in zip(bp['boxes'], colors):
        patch.set_facecolor(col)

    ax.set_yscale('log')
    ax.set_xticks([ (i*spacing)+0.4 for i in range(n)])
    ax.set_xticklabels(planners, fontsize=10)
    ax.set_ylabel('計算時間 (秒, log scale)', fontsize=10)
    ax.set_title('各手法の計算時間分布（成功ケース）', fontsize=12)
    # legend for complexities
    from matplotlib.patches import Patch
    legend_elems = [Patch(facecolor=cmap(i), label=COMPLEXITIES[i]) for i in range(len(COMPLEXITIES))]
    ax.legend(handles=legend_elems, title='複雑度', fontsize=9, title_fontsize=10, loc='upper left', bbox_to_anchor=(1.02,1))
    ax.grid(axis='y', which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()
    fig.savefig(BOX_OUT, dpi=300)
    plt.close(fig)
    print(f'Saved {BOX_OUT}')

def main():
    if not os.path.exists(JSON_FILE):
        print('benchmark_results.json not found:', JSON_FILE)
        return
    name = ensure_font()
    if name:
        print('Using font:', name)
    else:
        print('Preferred fonts not found; using default matplotlib font (CJK glyphs may be missing)')
    results = load_data()
    plot_grouped_bar(results)
    plot_boxplot(results)

if __name__ == '__main__':
    main()
