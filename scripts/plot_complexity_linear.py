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
OUT_FILE = os.path.join(OUT_DIR, 'complexity_comparison_linear_300dpi.png')

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

PLANNERS = ['TA*','D* Lite','SAFETY','HPA*','RRT*','Dijkstra']
COMPLEXITIES = ['SIMPLE','MODERATE','COMPLEX']

def load_results():
    with open(JSON_FILE) as f:
        data = json.load(f)
    res = {}
    for e in data:
        pname = e.get('planner_name')
        comp = e.get('complexity')
        t = e.get('computation_time')
        succ = e.get('success', True)
        if pname is None or comp is None or t is None:
            continue
        if pname not in PLANNER_MAP:
            continue
        key = PLANNER_MAP[pname]
        if not succ:
            continue
        res.setdefault(key, {}).setdefault(comp, []).append(float(t))
    return res

def ensure_font():
    preferred = ['Noto Sans CJK JP','Noto Sans CJK','DejaVu Sans']
    available = [f.name for f in font_manager.fontManager.ttflist]
    for name in preferred:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            return name
    return None

def compute_means(results):
    means = {p: {c: np.nan for c in COMPLEXITIES} for p in PLANNERS}
    for p in PLANNERS:
        for c in COMPLEXITIES:
            arr = results.get(p, {}).get(c, [])
            if arr:
                means[p][c] = float(np.mean(arr))
    return means

def plot_linear(means):
    x = np.arange(len(COMPLEXITIES))
    n = len(PLANNERS)
    total_width = 0.85
    width = total_width / n

    # build value matrix
    values = np.zeros((len(COMPLEXITIES), n))
    for j,p in enumerate(PLANNERS):
        for i,c in enumerate(COMPLEXITIES):
            v = means.get(p, {}).get(c, np.nan)
            values[i,j] = np.nan if np.isnan(v) else v

    fig_w = 1400/300; fig_h = 800/300
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    cmap = plt.get_cmap('tab10')
    for j in range(n):
        offs = x - total_width/2 + width/2 + j*width
        ax.bar(offs, values[:,j], width=width, label=PLANNERS[j], color=cmap(j%10))

    ax.set_yscale('linear')
    ax.set_xticks(x)
    # rotate complexity labels slightly for readability
    ax.set_xticklabels(COMPLEXITIES, fontsize=10, rotation=20)
    ax.set_ylabel('計算時間 (秒)', fontsize=11)
    ax.set_title('全6手法の複雑度別平均計算時間（線形）', fontsize=13)

    # set y limit a bit above max non-nan
    vmax = np.nanmax(values)
    if not np.isnan(vmax):
        ax.set_ylim(0, vmax * 1.2)

    # no per-bar numeric labels to avoid clutter; rely on y-axis ticks

    ax.grid(axis='y', linestyle='--', alpha=0.6)
    ax.legend(title='手法', fontsize=9, title_fontsize=10, loc='upper left', bbox_to_anchor=(1.02,1))
    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(OUT_FILE, dpi=300)
    plt.close(fig)
    print(f'Saved {OUT_FILE}')

def main():
    if not os.path.exists(JSON_FILE):
        print('Input JSON not found:', JSON_FILE)
        return
    ensure_font()
    results = load_results()
    means = compute_means(results)
    plot_linear(means)

if __name__ == '__main__':
    main()
