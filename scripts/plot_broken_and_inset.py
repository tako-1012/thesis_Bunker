#!/usr/bin/env python3
"""
Generate two example plots demonstrating:
- broken axis
- inset zoom

Saves PNGs to results/ directory.
"""
import os
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import inset_axes, mark_inset


def ensure_results_dir():
    os.makedirs('results', exist_ok=True)


def get_dummy_data():
    methods = ['TA* (提案)', 'Dijkstra', 'D* Lite', 'HPA*', 'RRT*', 'SAFETY']
    sizes = ['小', '中', '大']
    data = np.array([
        [0.01, 1.3, 4.3],   # TA*
        [19.0, 58.5, 4.4],  # Dijkstra
        [0.0, 1.2, 4.5],    # D* Lite
        [0.3, 6.5, 25.4],   # HPA*
        [24.0,27.5,41.0],   # RRT*
        [0.2,5.5,22.0],     # SAFETY
    ])
    return methods, sizes, data


def plot_broken_axis(methods, sizes, data, outpath):
    x = np.arange(len(methods))
    width = 0.25
    fig, (ax_top, ax_bot) = plt.subplots(2, 1, sharex=True, figsize=(12,6), gridspec_kw={'height_ratios':[3,1]})

    for i, s in enumerate(sizes):
        ax_top.bar(x + (i-1)*width, data[:,i], width, label=s)
        ax_bot.bar(x + (i-1)*width, data[:,i], width, label='_nolegend_')

    ax_top.set_ylim(15, 70)
    ax_bot.set_ylim(0, 3)

    # Draw break marks
    d = .015
    kwargs = dict(transform=ax_top.transAxes, color='k', clip_on=False)
    ax_top.plot((-d, +d), (-d, +d), **kwargs)
    kwargs.update(transform=ax_bot.transAxes)
    ax_bot.plot((-d, +d), (1-d, 1+d), **kwargs)

    ax_bot.set_xticks(x)
    ax_bot.set_xticklabels(methods, rotation=30)
    ax_top.legend(title='マップサイズ')
    ax_top.set_ylabel('計算時間（秒）')
    plt.suptitle('Broken axis: マップサイズ間の大きなギャップを切断')
    plt.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


def plot_inset_zoom(methods, sizes, data, outpath):
    x = np.arange(len(methods))
    width = 0.25
    fig, ax = plt.subplots(figsize=(12,5))
    for i, s in enumerate(sizes):
        ax.bar(x + (i-1)*width, data[:,i], width, label=s)
    ax.set_xticks(x); ax.set_xticklabels(methods, rotation=30)
    ax.set_ylabel('計算時間（秒）')
    ax.legend(title='マップサイズ')

    # inset for small values
    axins = inset_axes(ax, width="40%", height="40%", loc='upper left', bbox_to_anchor=(0.02,0.6,1,1), bbox_transform=ax.transAxes)
    for i in range(len(sizes)):
        axins.bar(x + (i-1)*width, data[:,i], width)
    axins.set_ylim(0, 3)
    axins.set_xticks([])
    mark_inset(ax, axins, loc1=2, loc2=4, fc="none", ec="0.5")

    plt.title('Inset zoom: 小さい値を拡大表示')
    plt.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)


def main():
    ensure_results_dir()
    methods, sizes, data = get_dummy_data()
    out1 = os.path.join('results', 'plot_broken_axis.png')
    out2 = os.path.join('results', 'plot_inset_zoom.png')
    try:
        plot_broken_axis(methods, sizes, data, out1)
        plot_inset_zoom(methods, sizes, data, out2)
    except Exception as e:
        print('プロットに失敗しました:', e)
        print('matplotlib がインストールされているか確認してください。')
        raise
    print('Saved:', out1)
    print('Saved:', out2)


if __name__ == '__main__':
    main()
