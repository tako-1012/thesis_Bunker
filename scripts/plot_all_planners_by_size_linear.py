#!/usr/bin/env python3
import os
import csv
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

CSV_FILE = os.path.join('ros2','ros2_ws','src','path_planner_3d','path_planner_3d','benchmark_results','all_planners_comparison.csv')
OUT_DIR = 'presentation'
OUT_FILE = os.path.join(OUT_DIR, 'all_planners_by_size_linear_300dpi.png')

# display name mapping
DISPLAY_MAP = {
    'ADAPTIVE': 'TA*',
    'DSTAR_LITE': 'D* Lite',
    'HPA_STAR': 'HPA*',
    'RRT_STAR': 'RRT*',
    'SAFETY_FIRST': 'SAFETY',
    'DIJKSTRA_DWA': 'Dijkstra',
}

# define plotting order (keys as in CSV -> display label)
ORDER_KEYS = ['ADAPTIVE','DSTAR_LITE','SAFETY_FIRST','HPA_STAR','RRT_STAR','DIJKSTRA_DWA']
PLOT_LABELS = [DISPLAY_MAP[k] for k in ORDER_KEYS]

SIZE_ORDER = ['Small','Medium','Large']

def ensure_font():
    preferred = ['Noto Sans CJK JP','Noto Sans CJK','DejaVu Sans']
    available = [f.name for f in font_manager.fontManager.ttflist]
    for name in preferred:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            return name
    return None

def read_csv(path):
    data = {}
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            planner = r['planner'].strip()
            map_size = r.get('map_size') or r.get('map_size'.upper())
            try:
                avg = float(r.get('avg_time','nan'))
            except:
                avg = np.nan
            data.setdefault(planner, {})[map_size] = avg
    return data

def plot(planners, data):
    # use fixed plotting order defined by ORDER_KEYS
    labels = PLOT_LABELS
    n = len(labels)
    m = len(SIZE_ORDER)

    values = np.full((m, n), np.nan)
    for j,key in enumerate(ORDER_KEYS):
        for i,s in enumerate(SIZE_ORDER):
            values[i,j] = data.get(key, {}).get(s, np.nan)

    fig_w = 2400/300; fig_h = 1200/300
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    x = np.arange(n)
    total_width = 0.75
    width = total_width / m
    cmap = plt.get_cmap('tab10')
    for i in range(m):
        offs = x - total_width/2 + width/2 + i*width
        ax.bar(offs, values[i,:], width=width, label={'Small':'小','Medium':'中','Large':'大'}[SIZE_ORDER[i]] + f' ({SIZE_ORDER[i]})', color=cmap(i))

    ax.set_yscale('linear')
    ax.set_xticks(x)
    # use vertical labels to avoid overlap
    ax.set_xticklabels(labels, rotation=90, ha='center', fontsize=9)
    ax.set_ylabel('計算時間（秒）', fontsize=11)
    ax.set_title('全手法のマップサイズ別平均計算時間', fontsize=13)
    vmax = np.nanmax(values)
    if not np.isnan(vmax):
        ax.set_ylim(0, vmax * 1.2)

    # no per-bar numeric labels to avoid clutter; rely on y-axis ticks

    ax.grid(axis='y', linestyle='--', alpha=0.6)
    # move legend below the plot to free space (give more negative y so it sits clearly below)
    ax.legend(title='マップサイズ', fontsize=9, title_fontsize=10, loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=3, framealpha=0.95)
    # leave extra bottom margin so legend placed below is visible
    plt.subplots_adjust(bottom=0.28, right=0.98)
    # avoid tight_layout() here; instead save with bbox_inches='tight' and padding to prevent clipping
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(OUT_FILE, dpi=300, bbox_inches='tight', pad_inches=0.5)
    plt.close(fig)
    print(f'Saved {OUT_FILE}')

def main():
    if not os.path.exists(CSV_FILE):
        print('Input CSV not found:', CSV_FILE)
        return
    ensure_font()
    data = read_csv(CSV_FILE)
    plot(ORDER_KEYS, data)

if __name__ == '__main__':
    main()
