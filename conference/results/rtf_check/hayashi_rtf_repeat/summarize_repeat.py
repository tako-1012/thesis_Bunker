#!/usr/bin/env python3
"""Per-run outcomes and pairwise trajectory gaps from saved records only; nothing is recomputed.
Gap: for each sample of A, the distance to the nearest sample of B; both directions are pooled.
Usage: summarize_repeat.py ROOT [PATCH]"""
import csv, json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
root = Path(sys.argv[1])
patch = sys.argv[2] if len(sys.argv) > 2 else '08OB87_-0706'
C = root.parent
def locate(run):
    return run/'physical_1/raw'/patch
refs = {'first_0.3': C/'hayashi_first_gazebo_check/physical_3/raw'/patch,
        'cloud_0.3': C/'lidar_fine/physical_10/raw'/patch}
runs = {p.name: locate(p) for p in sorted(root.glob('rtf_*')) if locate(p).is_dir()}
runs.update({k: v for k, v in refs.items() if v.is_dir()})
rows = []
for name, raw in runs.items():
    r = dict(run=name)
    try:
        m = json.loads((raw/'mission.json').read_text())
        s = m.get('final_state') or {}
        pose = s.get('pose') or [None, None]
        r.update(status=m.get('status'), sim_s=round(m['finished_t']-m['started_t'], 2),
                 wall_s=round(m.get('wall_elapsed_s', float('nan')), 1), end_x=pose[0], end_y=pose[1],
                 n_replans=s.get('n_replans'), error=s.get('error'))
        p = list(csv.DictReader((raw/'plans.csv').open()))
        r['plans'] = len(p)
        for key in ('status', 'ok', 'success', 'found'):
            if p and key in p[0]:
                r['plans_by_'+key] = dict((v, sum(x[key] == v for x in p)) for v in sorted({x[key] for x in p}))
        t = np.array([[float(x['x']), float(x['y'])] for x in csv.DictReader((raw/'trajectory.csv').open())])
        r['path_m'] = round(float(np.linalg.norm(np.diff(t, axis=0), axis=1).sum()), 1)
        r['_t'] = t
    except Exception as exc:
        r['read_error'] = type(exc).__name__+': '+str(exc)
    rows.append(r)
keys = [k for r in rows for k in r if not k.startswith('_')]
keys = list(dict.fromkeys(keys))
with (root/'runs_summary.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, keys, extrasaction='ignore'); w.writeheader(); w.writerows(rows)
with (root/'trajectory_gaps.csv').open('w', newline='') as f:
    w = csv.writer(f); w.writerow(['a', 'b', 'median_m', 'p95_m', 'max_m'])
    have = [r for r in rows if '_t' in r]
    for i, a in enumerate(have):
        for b in have[i+1:]:
            d = np.r_[cKDTree(b['_t']).query(a['_t'])[0], cKDTree(a['_t']).query(b['_t'])[0]]
            w.writerow([a['run'], b['run'], *[round(float(v), 2) for v in (np.median(d), np.percentile(d, 95), d.max())]])
print((root/'runs_summary.csv').read_text()); print((root/'trajectory_gaps.csv').read_text())
