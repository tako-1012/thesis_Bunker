#!/usr/bin/env python3
import csv
import os
import matplotlib.pyplot as plt
import numpy as np

IN_FILE = os.path.join('results','complexity_comparison.csv')
OUT_DIR = 'presentation'
OUT_FILE = os.path.join(OUT_DIR, 'complexity_comparison_300dpi.png')

def read_csv(path):
    rows = []
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows

def parse_float(s):
    if s is None or s == '':
        return np.nan
    try:
        return float(s)
    except:
        # strip possible asterisks
        return float(s.replace('*',''))

def plot_grouped_bar(data_rows):
    complexities = ['SIMPLE','MODERATE','COMPLEX']
    planners = [r['planner'] for r in data_rows]
    n_planners = len(planners)

    # build matrix: rows=complexities, cols=planners
    values = np.zeros((len(complexities), n_planners))
    for j, r in enumerate(data_rows):
        for i, comp in enumerate(complexities):
            values[i,j] = parse_float(r.get(comp, ''))

    # plot
    fig_w = 1200/300  # inches
    fig_h = 800/300
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    x = np.arange(len(complexities))
    total_width = 0.8
    width = total_width / n_planners

    cmap = plt.get_cmap('tab10')
    for j in range(n_planners):
        offsets = x - total_width/2 + width/2 + j*width
        ax.bar(offsets, values[:,j], width=width, label=planners[j], color=cmap(j % 10))

    ax.set_yscale('log')
    ax.set_xticks(x)
    ax.set_xticklabels(complexities, fontsize=10)
    ax.set_ylabel('計算時間 (秒, log scale)', fontsize=10)
    ax.set_title('全6手法の複雑度別平均計算時間', fontsize=12)
    ax.grid(axis='y', which='both', linestyle='--', linewidth=0.5)

    # legend
    ax.legend(title='手法', fontsize=9, title_fontsize=10, loc='upper left', bbox_to_anchor=(1.02,1))

    plt.tight_layout()
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(OUT_FILE, dpi=300)
    print(f'Saved {OUT_FILE}')

def main():
    if not os.path.exists(IN_FILE):
        print(f'Input file not found: {IN_FILE}')
        return
    rows = read_csv(IN_FILE)
    if not rows:
        print('No data in input file')
        return
    plot_grouped_bar(rows)

if __name__ == '__main__':
    main()
