"""Task033 B: timeline of the last 30 s before each C2 rollover on 08OB88_-0167, and whether
map-lethal cells on the followed path were NEW (first seen) or ALREADY KNOWN when they turned lethal.

python results/diagnosis_033/rollover_timeline.py RAW_RUN_DIR ROLLOVER_T
"""
import sys, glob, csv, json
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.collision import segment_cells
from tapp.traversability import slope_deg, inflate
from tapp.config import Robot


def bits(z, n):
    s = tuple(z[n+'_shape'])
    return np.unpackbits(z[n+'_bits'], count=int(np.prod(s))).reshape(s).astype(bool)


raw, t_roll = Path(sys.argv[1]), float(sys.argv[2])
t0 = t_roll-30
ref = np.load(raw/'evaluation_reference.npz')
truth_slope = slope_deg(ref['truth_elev'])
revs = [r for r in csv.DictReader(open(raw/'path_revisions.csv'))]
replans = {float(r['t']): r for r in csv.DictReader(open(raw/'replans.csv'))}
traj = np.array([[float(r[k]) for k in ('t', 'x', 'y', 'roll', 'pitch')] for r in csv.DictReader(open(raw/'trajectory.csv'))])
print(f'== {raw.parents[2].name}  rollover_t={t_roll}')
print('-- masks (search/handoff) in window: t phase original_goal -> goal relaxed_cells applied')
for f in sorted((raw/'endpoint_masks').glob('*.npz')):
    z = np.load(f)
    t = float(z['sim_time'])
    if t0-30 <= t <= t_roll:
        relaxed = int(np.unpackbits(z['relaxed_bits']).sum())
        if str(z['phase']) == 'search' or relaxed or tuple(z['goal']) != tuple(z['original_goal']):
            print(f'  {t:7.2f} {str(z["phase"]):7s} {tuple(z["original_goal"])} -> {tuple(z["goal"])} relaxed={relaxed} applied={bool(z["applied"])}')
print('-- path revisions in window: t, reason, end, n_points; truth max slope along path')
for r in revs:
    t = float(r['t'])
    if t0 <= t <= t_roll:
        p = np.array(json.loads(r['path']))
        cells = np.unique(np.concatenate([segment_cells(a/.5, b/.5, ref['truth_lethal'].shape) for a, b in zip(p[:-1], p[1:])]), axis=0)
        rp = replans.get(t, {})
        print(f'  {t:7.2f} {rp.get("reason", "?"):10s} end={tuple(np.round(p[-1], 1))} n={len(p)} '
              f'truth_lethal_cells={int(ref["truth_lethal"][tuple(cells.T)].sum())} truth_slope_max={truth_slope[tuple(cells.T)].max():.1f}')
print('-- robot every 2 s: t x y roll_deg pitch_deg truth_slope_here')
for row in traj[(traj[:, 0] >= t0) & (traj[:, 0] <= t_roll+1)][::40]:
    c = tuple(np.clip(np.rint(row[1:3]/.5).astype(int), 0, 399))
    print(f'  {row[0]:7.2f} {row[1]:6.2f} {row[2]:6.2f} {np.degrees(row[3]):6.1f} {np.degrees(row[4]):6.1f} {truth_slope[c]:5.1f}')
print('-- periodic snapshots: lethal cells on the path being followed, split by how they became lethal')
snaps = sorted((raw/'diag').glob('periodic_*.npz'))
prev = None
for f in snaps:
    z = np.load(f)
    t = float(z['sim_time'])
    L, K, S = bits(z, 'lethal'), bits(z, 'known'), bits(z, 'steep')
    rv = [r for r in revs if float(r['t']) <= t][-1]
    p = np.array(json.loads(rv['path']))/.5
    cells = np.unique(np.concatenate([segment_cells(a, b, L.shape) for a, b in zip(p[:-1], p[1:])]), axis=0)
    on = cells[L[tuple(cells.T)]]
    line = f'  snap t={t:.1f} following rev t={rv["t"]} path_cells={len(cells)} map_lethal_on_path={len(on)}'
    if prev is not None and len(on):
        pt, pL, pK = prev
        was_known = pK[tuple(on.T)]
        was_lethal = pL[tuple(on.T)]
        line += (f' | at prev snap t={pt:.1f}: already_known={int(was_known.sum())} (of which already_lethal={int((was_known & was_lethal).sum())}),'
                 f' first_seen_after={int((~was_known).sum())}; raw_steep_now={int(S[tuple(on.T)].sum())} steep_infl_now={int(inflate(S, Robot().footprint_radius)[tuple(on.T)].sum())}')
    print(line)
    prev = (t, L, K)
