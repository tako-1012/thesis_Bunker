"""Task035 details: (a) snapshots where the followed path had map-lethal cells, (b) S1 truth/debris contact,
(c) 08OB89_-0847 stop 3 passage, (d) plan_fail causes. Truth is evaluation-only.
Run from conference/: python results/eval_035/details_035.py"""
import sys, csv, json, glob
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tapp.config import RESOLUTION, Robot
from tapp.collision import segment_cells
from tapp.traversability import slope_deg, inflate
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts
R = Path(__file__).resolve().parent/'runs'

def bits(z, n):
    s = tuple(z[n+'_shape']); return np.unpackbits(z[n+'_bits'], count=int(np.prod(s))).reshape(s).astype(bool)

def raw_of(d): return next((d/'physical_1/raw').iterdir())

print('(a) followed path with map-lethal cells (robot cell excluded) at saved 10 s maps')
for d in sorted(R.glob('*/*')):
    if not (d/'exit.txt').exists() or not (d/'diag_all').exists(): continue
    raw = raw_of(d)
    if not (raw/'path_revisions.csv').exists(): continue
    revs = [(float(r['t']), np.array(json.loads(r['path']))/RESOLUTION) for r in read_csv_parts(raw/'path_revisions.csv')]
    plans = list(csv.DictReader(open(raw/'replans.csv'))) if (raw/'replans.csv').exists() else []
    ev = list(csv.DictReader(open(raw/'safety_events.csv'))) if (raw/'safety_events.csv').exists() else []
    for f in sorted((d/'diag_all').glob('periodic_*.npz')):
        z = np.load(f); t = float(z['sim_time'])
        prior = [r for r in revs if r[0] <= t]
        if not prior: continue
        rt, p = prior[-1]
        L = bits(z, 'lethal').copy(); K = bits(z, 'known'); S = bits(z, 'steep')
        pos = z['pose'][:2]/RESOLUTION; cell = tuple(int(round(v)) for v in pos); L[cell] = False
        dd = [np.linalg.norm(pos-(a+np.clip(np.dot(pos-a, b-a)/max(np.dot(b-a, b-a), 1e-12), 0, 1)*(b-a))) for a, b in zip(p[:-1], p[1:])]
        k = int(np.argmin(dd)) if dd else 0
        rem = np.vstack([pos, p[k+1:]]) if len(p) > k+1 else np.vstack([pos, p[-1:]])
        cells = np.unique(np.concatenate([segment_cells(a, b, L.shape) for a, b in zip(rem[:-1], rem[1:])]), axis=0)
        hit = cells[L[tuple(cells.T)]]
        if len(hit):
            nxt = [r for r in plans if t < float(r['t']) <= t+3]
            dist = [round(float(np.linalg.norm(c-pos))*RESOLUTION, 2) for c in hit]
            print(f'  {d.parent.name} {d.name} snap t={t:.2f} rev t={rt:.2f} (dt={t-rt:.2f}s) lethal cells={hit.tolist()} dist_from_robot_m={dist} '
                  f'steep_infl={int(inflate(S, Robot().footprint_radius)[tuple(hit.T)].sum())} | next replans within 3 s: {[(r["t"], r["reason"]) for r in nxt]}')

print('\n(b) S1 contact with truth-lethal / debris cells')
d = R/'08OB86_-0205/S1_r1'; raw = raw_of(d)
ref = np.load(raw/'evaluation_reference.npz'); debris = ref['truth_rock'] & ~ref['prior_rock']
T = np.array([[float(r[k]) for k in ('t', 'x', 'y', 'roll', 'pitch')] for r in read_csv_parts(raw/'trajectory.csv')])
c = np.clip(np.rint(T[:, 1:3]/RESOLUTION).astype(int), 0, 399)
inside = debris[c[:, 0], c[:, 1]]
for i in np.flatnonzero(inside[1:] & ~inside[:-1])+1:
    j = i
    while j < len(inside) and inside[j]: j += 1
    cc = c[i]
    print(f'  entered debris cell {tuple(cc)} at t={T[i,0]:.2f} pos=({T[i,1]:.2f},{T[i,2]:.2f}) left t={T[min(j,len(T)-1),0]:.2f}; truth_lethal={bool(ref["truth_lethal"][tuple(cc)])}')
    snaps = sorted((d/'diag_all').glob('periodic_*.npz'))
    for f in snaps:
        z = np.load(f)
        if float(z['sim_time']) <= T[i, 0] < float(z['sim_time'])+10:
            Lm, Sm, Dm = bits(z, 'lethal'), bits(z, 'seen'), bits(z, 'detected')
            print(f'    map at t={float(z["sim_time"]):.1f}: cell seen={bool(Sm[tuple(cc)])} lethal={bool(Lm[tuple(cc)])} detected_5x5={int(Dm[cc[0]-2:cc[0]+3, cc[1]-2:cc[1]+3].sum())} '
                  f'truth_rock_5x5={int(ref["truth_rock"][cc[0]-2:cc[0]+3, cc[1]-2:cc[1]+3].sum())} prior_rock_5x5={int(ref["prior_rock"][cc[0]-2:cc[0]+3, cc[1]-2:cc[1]+3].sum())}')
    revs = [(float(r['t']), r['path']) for r in read_csv_parts(raw/'path_revisions.csv')]
    rv = [r for r in revs if r[0] <= T[i, 0]][-1]
    pp = np.array(json.loads(rv[1]))/RESOLUTION
    pc = np.unique(np.concatenate([segment_cells(a, b, debris.shape) for a, b in zip(pp[:-1], pp[1:])]), axis=0)
    print(f'    followed path rev t={rv[0]:.2f} crosses debris cells: {int(debris[tuple(pc.T)].sum())}; truth-lethal cells: {int(ref["truth_lethal"][tuple(pc.T)].sum())}')

print('\n(c) 08OB89_-0847 around stop 3 (cells 281,117): robot cell lethal at join?')
for k in (1, 2, 3):
    raw = raw_of(R/f'08OB89_-0847/P1_r{k}')
    ev = [r for r in csv.DictReader(open(raw/'safety_events.csv')) if 105 <= float(r['sim_time']) <= 140]
    for r in ev:
        if r['event'] != 'join_accepted' or '[280, 117]' in r['detail'] or '[281, 117]' in r['detail'] or r['event'] != 'join_accepted':
            print(f'  r{k} {r["sim_time"]} {r["event"]} {r["detail"]}')

print('\n(d) plan_fail causes')
for f in sorted(R.glob('*/*/physical_1/raw/*/diag/plan_fail_*.npz')):
    z = np.load(f); raw = f.parents[1]
    L, S, D, P = bits(z, 'lethal'), bits(z, 'steep'), bits(z, 'detected'), bits(z, 'prior_raw')
    ref = np.load(raw/'evaluation_reference.npz'); g = tuple(z['goal']); s = tuple(z['start'])
    si = inflate(S, Robot().footprint_radius)
    fc = [p['failure_class'] for p in read_csv_parts(raw/'plans.csv') if p['success'] != 'True']
    print(f'  {f.parents[4].name} {f.parents[3].name} t={float(z["sim_time"]):.1f} class={fc} pose=({z["pose"][0]:.1f},{z["pose"][1]:.1f}) '
          f'goal={g} goal_lethal={bool(L[g])} by_steep_infl={bool(si[g])} detected_5x5={int(D[g[0]-2:g[0]+3, g[1]-2:g[1]+3].sum())} '
          f'map_slope={slope_deg(z["elev"])[g]:.1f} truth_slope={slope_deg(ref["truth_elev"])[g]:.1f} truth_lethal={bool(ref["truth_lethal"][g])} '
          f'truth_lethal_5x5={ref["truth_lethal"][g[0]-2:g[0]+3, g[1]-2:g[1]+3].mean():.2f} start_lethal={bool(L[s])}')
