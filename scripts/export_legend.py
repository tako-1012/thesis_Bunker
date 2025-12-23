#!/usr/bin/env python3
import os
import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

OUT_DIR = 'presentation'
OUT_FILE = os.path.join(OUT_DIR, 'legend_all_planners_300dpi.png')

PLANNERS = ['TA*','D* Lite','SAFETY','HPA*','RRT*','Dijkstra']

def ensure_font():
    preferred = ['Noto Sans CJK JP','Noto Sans CJK','DejaVu Sans']
    available = [f.name for f in font_manager.fontManager.ttflist]
    for name in preferred:
        if name in available:
            matplotlib.rcParams['font.family'] = name
            return name
    return None

def main():
    ensure_font()
    cmap = plt.get_cmap('tab10')
    handles = [plt.Rectangle((0,0),1,1, color=cmap(i%10)) for i in range(len(PLANNERS))]
    fig = plt.figure(figsize=(6,1))
    ax = fig.add_subplot(111)
    ax.axis('off')
    legend = ax.legend(handles, PLANNERS, loc='center', ncol=len(PLANNERS), frameon=False, fontsize=12)
    os.makedirs(OUT_DIR, exist_ok=True)
    fig.savefig(OUT_FILE, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved {OUT_FILE}')

if __name__ == '__main__':
    main()
