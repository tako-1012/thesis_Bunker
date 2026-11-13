"""Task030 per-run and beach x condition descriptive tables (no tests, no energy).

Usage: python -m experiments.eval_ground_endpoint_report [results/eval_ground_endpoint]
Truth maps (evaluation_reference.npz) are read here only for evaluation.
"""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION, Robot
from tapp.real_beach import build_real
from tapp.traversability import slope_deg, inflate
from tapp.endpoint_policy import audit_path
from experiments.gz_online_batch_report import analyze_record
from experiments.gz_lidar_report import map_quality
from experiments.lidar_fine_report import map_audit
from experiments.endpoint_audit import audit_run
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts

CONDITIONS = {'C0': ('all_returns', 'none'), 'C1': ('non_obstacle', 'none'),
              'C2': ('non_obstacle', 'escape_component')}
PATCHES = ['08OB87_-0706', '08OB88_-1417', '08OB88_-0167', '08OB89_-0347', '08OB89_-0847']
FAILURE_CLASSES = ['goal_cell', 'start_cell', 'start_steep', 'corridor', 'other']


def bits(z, name):
    shape = tuple(z[name+'_shape'])
    return np.unpackbits(z[name+'_bits'], count=int(np.prod(shape))).reshape(shape).astype(bool)


def final_map(raw):
    """Final saved map; if the run was killed before saving, the newest periodic snapshot."""
    path = raw/'pointcloud_map.npz'
    if path.exists():
        with np.load(path, allow_pickle=False) as z:
            return dict(seen=z['seen'].copy(), lethal=z['lethal'].copy(), obstacle=z['obstacle'].copy(),
                        elev=z['elev'].copy()), 'pointcloud_map.npz'
    snaps = sorted((raw/'diag').glob('periodic_*.npz'))
    if not snaps:
        return None, 'none'
    with np.load(snaps[-1], allow_pickle=False) as z:
        return dict(seen=bits(z, 'seen'), lethal=bits(z, 'lethal'), obstacle=bits(z, 'detected'),
                    elev=z['elev'].copy()), snaps[-1].name


def contacts(xy, mask):
    """Exact centre-trajectory length inside mask cells and number of separate entries."""
    if len(xy) < 2:
        return 0., 0
    length = audit_path(xy, mask)['relaxed_length_m']
    cells = np.floor(xy/RESOLUTION+.5).astype(int)
    cells = np.clip(cells, 0, np.asarray(mask.shape)-1)
    inside = mask[cells[:, 0], cells[:, 1]]
    entries = int(inside[0]) + int((inside[1:] & ~inside[:-1]).sum())
    return float(length), entries


def run_row(run_dir, patch, cond, rep, metadata, terrain):
    phys = run_dir/'physical_1'
    raw = next((phys/'raw').iterdir())
    manifest = json.loads((phys/'manifest.json').read_text())
    exit_code = (run_dir/'exit.txt').read_text().strip()
    expected = CONDITIONS[cond]
    if (manifest.get('ground_estimate', 'all_returns'), manifest.get('endpoint_policy', 'none')) != expected or not manifest['diagnostics']:
        raise ValueError(f'{run_dir}: manifest conditions differ from {cond}')
    if manifest['map_method'] != 'fine' or manifest['real_time_factor'] != .3 or manifest['only_patch'] != patch:
        raise ValueError(f'{run_dir}: manifest run settings differ')
    with np.load(raw/'evaluation_reference.npz', allow_pickle=False) as z:
        ref = {k: z[k].copy() for k in z.files}
    truth = dict(tmap=SimpleNamespace(elev=ref['truth_elev'], rock=ref['truth_rock'], lethal=ref['truth_lethal'],
                                      shape=ref['truth_elev'].shape))
    prior = dict(tmap=SimpleNamespace(elev=ref['prior_elev'], rock=ref['prior_rock'], lethal=ref['prior_lethal'],
                                      shape=ref['prior_elev'].shape))
    measured, trace = analyze_record(raw, metadata, truth, prior)
    row = dict(patch=patch, condition=cond, rep=rep, exit_code=exit_code, **measured)
    if exit_code in ('124', '137'):
        row['status'] = 'wall_timeout'
        row['completed'] = False
    # stop outcomes (task028b): arrived / nearby / unreachable
    status_path = raw/'endpoint_status.json'
    row.update(stops_arrived=None, stops_nearby=None, stops_unreachable=None, retries=None,
               start_applications=None, goal_applications=None, relaxed_cells=None)
    if status_path.exists():
        es = json.loads(status_path.read_text())
        outcomes = [s['outcome'] for s in es['stops']]
        row.update(stops_arrived=outcomes.count('arrived'), stops_nearby=outcomes.count('nearby'),
                   stops_unreachable=outcomes.count('unreachable'), retries=es.get('retries'),
                   start_applications=es.get('start_applications'), goal_applications=es.get('goal_applications'),
                   relaxed_cells=es.get('relaxed_cells'))
    # failure classes
    plans = read_csv_parts(raw/'plans.csv')
    failed = [p for p in plans if p['success'] != 'True']
    row['failed_plans'] = len(failed)
    for name in FAILURE_CLASSES:
        row['fail_'+name] = sum(p.get('failure_class') == name for p in failed)
    row['fail_unclassified'] = sum(p.get('failure_class') not in FAILURE_CLASSES for p in failed)
    # map errors (023 definitions) + steep / obstacle-inflation split
    fmap, source = final_map(raw)
    row['map_source'] = source
    if fmap is not None:
        tmp = raw.parent.parent.parent/'_audit_map.npz'
        np.savez(tmp, seen=fmap['seen'], lethal=fmap['lethal'], obstacle=fmap['obstacle'])
        try:
            row.update(map_audit(tmp, truth['tmap'], terrain))
        finally:
            tmp.unlink()
        robot = Robot()
        steep = inflate(slope_deg(fmap['elev']) > robot.max_slope_deg, robot.footprint_radius)
        fp = fmap['seen'] & fmap['lethal'] & ~ref['truth_lethal']
        row['map_fp_steep_cells'] = int((fp & steep).sum())
        row['map_fp_obstacle_only_cells'] = int((fp & ~steep).sum())
    try:
        q = map_quality(raw, truth)
        row.update({k: q[k] for k in ('map_update_s_median', 'map_update_s_p95', 'map_update_s_max',
                                       'map_updates', 'map_failed_updates', 'queue_drops',
                                       'height_abs_error_median_m', 'height_abs_error_p95_m')})
    except (ValueError, OSError, KeyError) as exc:
        row['map_quality_error'] = type(exc).__name__+': '+str(exc)
    # safety: exact centre-line length in truth lethal / debris cells
    xy = trace[['x', 'y']].to_numpy()
    debris = ref['truth_rock'] & ~ref['prior_rock']
    row['truth_lethal_len_m'], row['truth_lethal_entries'] = contacts(xy, ref['truth_lethal'])
    row['debris_len_m'], row['debris_entries'] = contacts(xy, debris)
    # stationary tail (time since last movement > 0.05 m)
    moved = np.flatnonzero(np.linalg.norm(xy - xy[-1], axis=1) > .05)
    row['stationary_tail_s'] = float(trace.t.iloc[-1] - trace.t.iloc[moved[-1]+1]) if len(moved) else float(trace.t.iloc[-1]-trace.t.iloc[0])
    row['sim_end_t'] = float(trace.t.iloc[-1])
    # C2 relaxed-cell audit
    row.update(relaxed_len_m=None, relaxed_truth_lethal_len_m=None, relaxed_applied_plans=None)
    if (raw/'endpoint_trajectory.csv').exists() and (raw/'endpoint_masks').exists():
        audit = audit_run(raw, ref['truth_lethal'])
        row.update(relaxed_len_m=audit['relaxed_length_m'], relaxed_truth_lethal_len_m=audit['truth_lethal_length_m'],
                   relaxed_applied_plans=audit['applied_plans'])
    row['plan_fail_snapshots'] = len(list((raw/'diag').glob('plan_fail_*.npz')))
    return row


def outcome(row):
    """completed: all five ordered stops reached and returned (and, under 028b, no nearby/unreachable stop)."""
    skipped = sum(int(row[k] or 0) for k in ('stops_nearby', 'stops_unreachable') if pd.notna(row[k]))
    if row['status'] == 'rollover':
        return 'rollover'
    if row['status'] == 'completed':
        return 'partial' if skipped else 'completed'
    if row['status'] == 'incomplete_waypoints':
        return 'partial'
    return row['status']


def describe(values):
    values = pd.to_numeric(pd.Series(values)).dropna()
    if not len(values):
        return '-'
    f = lambda v: f'{v:.3g}' if abs(v) < 1000 else f'{v:.0f}'
    return f'{f(values.min())}/{f(values.median())}/{f(values.max())}'


def group_table(data):
    rows = []
    for patch in PATCHES:
        for cond in CONDITIONS:
            g = data[(data.patch == patch) & (data.condition == cond)]
            r = dict(patch=patch, condition=cond, n=len(g))
            for o in ['completed', 'partial', 'no_path', 'stuck', 'wall_timeout', 'rollover']:
                r[o] = int(g.outcome.eq(o).sum())
            for col in ['goals_reached', 'stops_arrived', 'stops_nearby', 'stops_unreachable', 'elapsed_s',
                        'failed_plans'] + ['fail_'+c for c in FAILURE_CLASSES] + [
                        'map_fp_cells', 'map_fp_steep_cells', 'map_fp_obstacle_only_cells', 'map_fn_cells',
                        'clearance_fp_cells', 'truth_lethal_len_m', 'truth_lethal_entries', 'debris_len_m',
                        'debris_entries', 'relaxed_len_m', 'relaxed_truth_lethal_len_m',
                        'plan_s_median', 'plan_s_max', 'map_update_s_median', 'map_update_s_max', 'retries', 'n_plans']:
                r[col] = describe(g[col])
            rows.append(r)
    return pd.DataFrame(rows)


def main(output):
    output = Path(output).resolve()
    rows = []
    for patch in PATCHES:
        truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
        terrain = truth['terrain']
        for cond in CONDITIONS:
            for rep in (1, 2, 3):
                run_dir = output/'runs'/patch/f'{cond}_r{rep}'
                manifest = json.loads((run_dir/'physical_1/manifest.json').read_text())
                metadata = next(s for s in manifest['scenarios'] if s['patch'] == patch)
                rows.append(run_row(run_dir, patch, cond, rep, metadata, terrain))
                print(patch, cond, rep, rows[-1]['status'], flush=True)
    data = pd.DataFrame(rows)
    data['outcome'] = data.apply(outcome, axis=1)
    data.to_csv(output/'runs.csv', index=False)
    table = group_table(data)
    table.to_csv(output/'summary.csv', index=False)
    with pd.option_context('display.width', 250, 'display.max_columns', 80, 'display.max_colwidth', 40):
        lines = ['Task030 per run', data[['patch', 'condition', 'rep', 'outcome', 'status', 'goals_reached',
                 'stops_arrived', 'stops_nearby', 'stops_unreachable', 'elapsed_s', 'failed_plans',
                 'map_fp_cells', 'map_fp_steep_cells', 'map_fp_obstacle_only_cells', 'map_fn_cells',
                 'truth_lethal_len_m', 'debris_len_m', 'relaxed_len_m', 'relaxed_truth_lethal_len_m',
                 'rolled_over', 'retries', 'map_source']].to_string(index=False, float_format=lambda x: f'{x:.4g}'),
                 '', 'Beach x condition (min/median/max over 3 runs; counts for outcomes)', table.to_string(index=False)]
    text = '\n'.join(lines)+'\n'
    (output/'report_log.txt').write_text(text)
    print(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT/'results/eval_ground_endpoint')
    main(parser.parse_args().output)
