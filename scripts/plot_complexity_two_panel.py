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
OUT_FILE = os.path.join(OUT_DIR, 'complexity_two_panel_300dpi.png')

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

def plot_two_panel(means):
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

    vmax = np.nanmax(values)

    fig_w = 1800/300; fig_h = 800/300
    fig, (ax_l, ax_r) = plt.subplots(1,2, figsize=(fig_w, fig_h), gridspec_kw={'width_ratios':[1,1]})
    cmap = plt.get_cmap('tab10')

    # left: zoomed (small-range) - show up to small_ylim
    small_ylim = max(0.5, np.nanpercentile(values, 50)) * 1.5
    small_ylim = max(small_ylim, 3.0) if np.nanmax(values) > 3.0 else max(small_ylim, np.nanmax(values)*1.2)

    for j in range(n):
        offs = x - total_width/2 + width/2 + j*width
        ax_l.bar(offs, values[:,j], width=width, color=cmap(j%10))
        ax_r.bar(offs, values[:,j], width=width, color=cmap(j%10), label=PLANNERS[j] if j==0 else None)

    # left settings
    ax_l.set_ylim(0, small_ylim)
    ax_l.set_xticks(x)
    ax_l.set_xticklabels(COMPLEXITIES, fontsize=10, rotation=20)
    ax_l.set_ylabel('計算時間 (秒)', fontsize=11)
    ax_l.set_title('拡大 (小さい値)', fontsize=12)
    ax_l.grid(axis='y', linestyle='--', alpha=0.6)

    # right settings (full)
    ax_r.set_ylim(0, vmax * 1.2)
    ax_r.set_xticks(x)
    ax_r.set_xticklabels(COMPLEXITIES, fontsize=10, rotation=20)
    ax_r.set_title('全体（フルスケール）', fontsize=12)
    ax_r.grid(axis='y', linestyle='--', alpha=0.6)

    # place legend below the two panels to avoid overlapping the right panel
    handles = [plt.Rectangle((0,0),1,1, color=cmap(i%10)) for i in range(n)]
    labels = PLANNERS
    fig.legend(handles, labels, title='手法', loc='upper center', bbox_to_anchor=(0.5, -0.08), ncol=6, fontsize=9, title_fontsize=10)

    fig.suptitle('全6手法の複雑度別平均計算時間 — 左: 拡大 / 右: 全体', fontsize=14)
    # leave space at bottom for horizontal legend
    plt.subplots_adjust(bottom=0.18)
    plt.tight_layout(rect=[0,0,0.95,0.95])
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
    plot_two_panel(means)

if __name__ == '__main__':
    main()
