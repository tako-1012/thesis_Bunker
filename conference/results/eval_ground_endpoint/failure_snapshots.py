"""Task030: describe each diag/plan_fail_*.npz and the moments before each rollover / hang.

Run from conference/: python results/eval_ground_endpoint/failure_snapshots.py
Truth (evaluation_reference.npz) is evaluation-only.
"""
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION, Robot
from tapp.traversability import slope_deg, inflate
from tapp.endpoint_policy import audit_path
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts

OUT = Path(__file__).resolve().parent
ROBOT = Robot()


def bits(z, name):
    shape = tuple(z[name+'_shape'])
    return np.unpackbits(z[name+'_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)


def load_snapshot(path):
    with np.load(path, allow_pickle=False) as z:
        snap = {k: bits(z, k) for k in ('lethal', 'seen', 'known', 'detected', 'prior_raw', 'steep')}
        snap.update(elev=z['elev'].copy(), pose=z['pose'].copy(), start=z['start'].copy(),
                    goal=z['goal'].copy(), sim_time=float(z['sim_time']))
    snap['steep_infl'] = inflate(snap['steep'], ROBOT.footprint_radius)
    snap['obstacle_part'] = snap['lethal'] & ~snap['steep_infl']
    return snap


def window(mask, c, r=3):
    c = np.asarray(c, int)
    lo, hi = np.maximum(c-r, 0), np.minimum(c+r+1, mask.shape)
    return mask[lo[0]:hi[0], lo[1]:hi[1]]


def cell_reason(snap, ref, c, label):
    c = tuple(int(v) for v in c)
    truth_slope = slope_deg(ref['truth_elev'])
    map_slope = slope_deg(snap['elev'])
    w = window(snap['lethal'], c, 2)
    return {f'{label}_cell': f'{c[0]},{c[1]}',
            f'{label}_map_lethal': bool(snap['lethal'][c]),
            f'{label}_by_steep_infl': bool(snap['steep_infl'][c]),
            f'{label}_by_obstacle_only': bool(snap['obstacle_part'][c]),
            f'{label}_raw_steep': bool(snap['steep'][c]),
            f'{label}_map_slope_deg': round(float(map_slope[c]), 1),
            f'{label}_map_dz_vs_truth_m': round(float(snap['elev'][c]-ref['truth_elev'][c]), 2),
            f'{label}_truth_lethal': bool(ref['truth_lethal'][c]),
            f'{label}_truth_slope_deg': round(float(truth_slope[c]), 1),
            f'{label}_lethal_frac_5x5': round(float(w.mean()), 2),
            f'{label}_truth_lethal_frac_5x5': round(float(window(ref['truth_lethal'], c, 2).mean()), 2),
            f'{label}_raw_steep_5x5': int(window(snap['steep'], c, 2).sum()),
            f'{label}_detected_5x5': int(window(snap['detected'], c, 2).sum())}


def plan_fail_rows():
    rows = []
    for raw in sorted(OUT.glob('runs/*/*/physical_1/raw/*')):
        run = raw.parents[2]
        patch, cond_rep = run.parent.name, run.name
        fails = sorted((raw/'diag').glob('plan_fail_*.npz'))
        if not fails:
            continue
        with np.load(raw/'evaluation_reference.npz', allow_pickle=False) as z:
            ref = {k: z[k].copy() for k in z.files}
        plans = [p for p in read_csv_parts(raw/'plans.csv') if p['success'] != 'True']
        for i, path in enumerate(fails):
            snap = load_snapshot(path)
            row = dict(patch=patch, run=cond_rep, file=path.name, sim_time=round(snap['sim_time'], 2),
                       failure_class=plans[i]['failure_class'] if i < len(plans) else '?',
                       reason=plans[i]['reason'] if i < len(plans) else '?',
                       pose_xy=f"{snap['pose'][0]:.2f},{snap['pose'][1]:.2f}",
                       start_goal_dist_m=round(float(np.linalg.norm(snap['start']-snap['goal'])*RESOLUTION), 2))
            row.update(cell_reason(snap, ref, snap['start'], 'start'))
            row.update(cell_reason(snap, ref, snap['goal'], 'goal'))
            rows.append(row)
    return pd.DataFrame(rows)


def rollover_rows(runs):
    rows = []
    for _, r in runs[runs.outcome.eq('rollover')].iterrows():
        raw = next((OUT/'runs'/r.patch/f'{r.condition}_r{r.rep}'/'physical_1'/'raw').iterdir())
        with np.load(raw/'evaluation_reference.npz', allow_pickle=False) as z:
            ref = {k: z[k].copy() for k in z.files}
        trace = pd.DataFrame(read_csv_parts(raw/'trajectory.csv')).astype(float)
        t0 = float(r.rollover_t_s)
        before = trace[(trace.t >= t0-10) & (trace.t <= t0)]
        xy = before[['x', 'y']].to_numpy()
        snaps = [s for s in sorted((raw/'diag').glob('periodic_*.npz'))]
        snap = None
        for s in snaps:
            cand = load_snapshot(s)
            if cand['sim_time'] <= t0:
                snap = cand
        cells = np.unique(np.floor(xy/RESOLUTION+.5).astype(int), axis=0)
        truth_slope = slope_deg(ref['truth_elev'])
        row = dict(patch=r.patch, run=f'{r.condition}_r{r.rep}', rollover_t=t0,
                   rollover_xy=f'{r.rollover_x_m:.2f},{r.rollover_y_m:.2f}',
                   len_last10s_m=round(float(np.linalg.norm(np.diff(xy, axis=0), axis=1).sum()), 2),
                   truth_lethal_len_last10s_m=round(audit_path(xy, ref['truth_lethal'])['relaxed_length_m'], 2),
                   cells_last10s=len(cells),
                   truth_lethal_cells_last10s=int(ref['truth_lethal'][tuple(cells.T)].sum()),
                   truth_rock_cells_last10s=int(ref['truth_rock'][tuple(cells.T)].sum()),
                   truth_slope_max_last10s=round(float(truth_slope[tuple(cells.T)].max()), 1),
                   snapshot=None)
        if snap is not None:
            row.update(snapshot=f"t={snap['sim_time']:.1f}",
                       map_lethal_cells_on_path=int(snap['lethal'][tuple(cells.T)].sum()),
                       map_seen_cells_on_path=int(snap['seen'][tuple(cells.T)].sum()),
                       map_slope_max_on_path=round(float(slope_deg(snap['elev'])[tuple(cells.T)].max()), 1))
        # relaxed masks applied in the 10 s window
        relaxed_hits = 0
        for m in sorted((raw/'endpoint_masks').glob('*.npz')):
            with np.load(m, allow_pickle=False) as z:
                if bool(z['applied']) and t0-60 <= float(z['sim_time']) <= t0:
                    shape = tuple(z['relaxed_shape'])
                    mask = np.unpackbits(z['relaxed_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)
                    relaxed_hits = max(relaxed_hits, int(mask[tuple(cells.T)].sum()))
        row['relaxed_cells_on_path_last60s_masks'] = relaxed_hits
        rows.append(row)
    return pd.DataFrame(rows)


def main():
    runs = pd.read_csv(OUT/'runs.csv')
    pf = plan_fail_rows()
    ro = rollover_rows(runs)
    pf.to_csv(OUT/'plan_fail_causes.csv', index=False)
    ro.to_csv(OUT/'rollover_context.csv', index=False)
    with pd.option_context('display.width', 400, 'display.max_columns', 60):
        text = 'plan_fail snapshots\n'+pf.to_string(index=False)+'\n\nrollover (last 10 s)\n'+ro.to_string(index=False)+'\n'
    (OUT/'failure_snapshots_log.txt').write_text(text)
    print(text)


if __name__ == '__main__':
    main()
