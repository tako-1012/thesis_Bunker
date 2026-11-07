#!/usr/bin/env python3
"""Top-view trajectory figures from saved records only; nothing is recomputed or smoothed."""
import csv, json, sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
C = Path('/home/kotaro/thesis_Bunker/conference/results')
BLUE, ORANGE, INK, MUTED, SURFACE = '#2a78d6', '#eb6834', '#0b0b0b', '#52514e', '#fcfcfb'
plt.rcParams.update({'font.size': 10, 'text.color': INK, 'axes.labelcolor': MUTED, 'xtick.color': MUTED, 'ytick.color': MUTED,
                     'axes.edgecolor': '#d8d7d2', 'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE})
def track(path):
    r = list(csv.DictReader(open(path)))
    return [float(x['x']) for x in r], [float(x['y']) for x in r]
def draw(panels, labels, out, title):
    fig, axes = plt.subplots(1, len(panels), figsize=(4.2*len(panels)+.4, 4.8), squeeze=False)
    for ax, (name, a, b, note) in zip(axes[0], panels):
        for path, colour, label, z in ((b, BLUE, labels[1], 2), (a, ORANGE, labels[0], 3)):
            x, y = track(path)
            ax.plot(x, y, color=colour, lw=2, label=label, zorder=z, solid_capstyle='round')
            ax.plot(x[-1], y[-1], 'o', ms=8, color=colour, mec=SURFACE, mew=2, zorder=z+2)
        ax.set_title(f'{name}\n{note}', fontsize=10, loc='left')
        ax.set_aspect('equal', adjustable='datalim'); ax.grid(color='#ecebe6', lw=.8)
        ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
        for s in ('top', 'right'):
            ax.spines[s].set_visible(False)
    h, l = axes[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc='lower center', ncol=2, frameon=False)
    fig.suptitle(title, x=.02, ha='left', fontsize=12)
    fig.tight_layout(rect=(0, .07, 1, .97))
    fig.savefig(out, dpi=150)
first = C/'hayashi_first_gazebo_check'
ref = C/'lidar_fine/physical_10/raw'
m = {c['patch']: c['termination'] for c in json.load(open(first/'physical_3/manifest.json'))['cases'] if c['selected']}
mr = {c['patch']: c['termination'] for c in json.load(open(C/'lidar_fine/physical_10/manifest.json'))['cases']}
draw([(p, first/'physical_3/raw'/p/'trajectory.csv', ref/p/'trajectory.csv', f'hayashi: {m[p]} / cloud: {mr[p]}') for p in m],
     ('hayashi (RTF 0.3)', 'cloud task023 (RTF 0.3)'), first/'tracks_hayashi_vs_cloud.png', 'Recorded centre trajectories: hayashi vs cloud')
r = C/'hayashi_rtf1_check'
p = '08OB86_-0205'
draw([(p, r/'rtf_1/physical_1/raw'/p/'trajectory.csv', r/'rtf_0.3/physical_1/raw'/p/'trajectory.csv', 'both completed; dot = end')],
     ('target RTF 1.0', 'target RTF 0.3'), r/'tracks_rtf1_vs_rtf03.png', 'Recorded centre trajectories by target RTF')
