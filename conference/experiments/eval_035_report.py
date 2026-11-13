"""Task035 descriptive tables: stage 1 (C1+v1, 5 beaches x 3) next to task030 C1, and stage 2 (S1-S5 once).

Usage: python -m experiments.eval_035_report [results/eval_035]
No tests of significance, no energy. Truth (evaluation_reference.npz) is evaluation-only.
"""
import argparse
import csv
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
from tapp.collision import segment_cells
from experiments.gz_online_batch_report import analyze_record
from experiments.gz_lidar_report import map_quality
from experiments.lidar_fine_report import map_audit
from experiments.eval_ground_endpoint_report import final_map, contacts, describe, FAILURE_CLASSES
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts

PATCHES = ['08OB87_-0706', '08OB88_-1417', '08OB88_-0167', '08OB89_-0347', '08OB89_-0847']
STAGE2 = '08OB86_-0205'
EXPECTED = {
    'P1': dict(sensors=None, obstacle_reference=None),
    'S1': dict(sensors='lidar_real+depth2', obstacle_reference='prior'),
    'S2': dict(sensors='lidar_real+depth2', obstacle_reference='local'),
    'S3': dict(sensors='lidar_real+depth2', obstacle_reference='local', debris='true'),
    'S4': dict(sensors='lidar_real+depth2', obstacle_reference='local', prior='perturbed'),
    'S5': dict(sensors='lidar_real+depth2', obstacle_reference='local', prior='none'),
}
REAL_TIME_PERIOD_S = 1/3.  # 0.3x: one 0.1 s sim scan takes 0.33 s wall


def bits(z, n):
    s = tuple(z[n+'_shape'])
    return np.unpackbits(z[n+'_bits'], count=int(np.prod(s))).reshape(s).astype(bool)


def safety_events(raw):
    path = raw/'safety_events.csv'
    if not path.exists():
        return []
    rows = []
    for r in csv.DictReader(open(path)):
        rows.append(dict(t=float(r['sim_time']), event=r['event'], detail=json.loads(r['detail'] or '{}')))
    return rows


def after_stop(events, trace, end_t, horizon=30.):
    """For each unsafe_tilt/off_path stop: replanned? moved >1 m within 30 s? stationary until the end?"""
    out = []
    xy, t = trace[['x', 'y']].to_numpy(), trace.t.to_numpy()
    for e in events:
        if e['event'] not in ('unsafe_tilt', 'off_path'):
            continue
        later = [x for x in events if e['t'] <= x['t'] <= e['t']+horizon]
        replanned = any(x['event'] == 'safety_replanned' for x in later)
        i = int(np.searchsorted(t, e['t']))
        window = (t >= e['t']) & (t <= e['t']+horizon)
        moved = float(np.max(np.linalg.norm(xy[window]-xy[min(i, len(xy)-1)], axis=1))) if window.any() else 0.
        tail = (t >= e['t'])
        moved_total = float(np.max(np.linalg.norm(xy[tail]-xy[min(i, len(xy)-1)], axis=1))) if tail.any() else 0.
        out.append(dict(t=e['t'], kind=e['event'], replanned_30s=replanned, moved_30s_m=round(moved, 2),
                        moved_until_end_m=round(moved_total, 2), seconds_to_end=round(end_t-e['t'], 1)))
    return out


def handoff_audit(run_dir, raw):
    """Paths followed at each saved 10 s map (diag_all): map-lethal cells on the remaining path, robot cell excluded.
    'at_handoff' = the revision was handed over within 1 s before the snapshot (closest available to handoff time)."""
    revs = [dict(t=float(r['t']), path=np.array(json.loads(r['path']))/RESOLUTION)
            for r in read_csv_parts(raw/'path_revisions.csv')]
    rows = []
    for f in sorted((run_dir/'diag_all').glob('periodic_*.npz')):
        z = np.load(f)
        t = float(z['sim_time'])
        prior = [r for r in revs if r['t'] <= t]
        if not prior:
            continue
        rev = prior[-1]
        L = bits(z, 'lethal').copy()
        pos = np.asarray(z['pose'][:2], float)/RESOLUTION
        cell = tuple(int(round(v)) for v in pos)
        if all(0 <= v < n for v, n in zip(cell, L.shape)):
            L[cell] = False
        p = rev['path']
        # remaining part: from the nearest segment onward
        d = [np.linalg.norm(pos-(a+np.clip(np.dot(pos-a, b-a)/max(np.dot(b-a, b-a), 1e-12), 0, 1)*(b-a))) for a, b in zip(p[:-1], p[1:])]
        k = int(np.argmin(d)) if d else 0
        rem = np.vstack([pos, p[k+1:]]) if len(p) > k+1 else np.vstack([pos, p[-1:]])
        cells = np.unique(np.concatenate([segment_cells(a, b, L.shape) for a, b in zip(rem[:-1], rem[1:])]), axis=0) if len(rem) > 1 else np.empty((0, 2), int)
        hits = int(L[tuple(cells.T)].sum()) if len(cells) else 0
        rows.append(dict(snap_t=t, rev_t=rev['t'], at_handoff=t-rev['t'] <= 1.0, lethal_on_remaining=hits))
    return rows


def run_row(run_dir, patch, cond, rep, terrain):
    phys = run_dir/'physical_1'
    raw = next((phys/'raw').iterdir())
    manifest = json.loads((phys/'manifest.json').read_text())
    exit_code = (run_dir/'exit.txt').read_text().strip()
    if manifest.get('online_fixes') != 'v1' or manifest.get('ground_estimate') != 'non_obstacle' or not manifest['diagnostics']:
        raise ValueError(f'{run_dir}: not C1+v1 with diagnostics')
    if manifest['map_method'] != 'fine' or manifest['real_time_factor'] != .3 or manifest['only_patch'] != patch:
        raise ValueError(f'{run_dir}: run settings differ')
    exp = EXPECTED[cond]
    if exp.get('sensors') and manifest.get('sensors') != exp['sensors']:
        raise ValueError(f'{run_dir}: sensors differ')
    metadata = next(s for s in manifest['scenarios'] if s['patch'] == patch)
    with np.load(raw/'evaluation_reference.npz', allow_pickle=False) as z:
        ref = {k: z[k].copy() for k in z.files}
    truth = dict(tmap=SimpleNamespace(elev=ref['truth_elev'], rock=ref['truth_rock'], lethal=ref['truth_lethal'], shape=ref['truth_elev'].shape))
    prior = dict(tmap=SimpleNamespace(elev=ref['prior_elev'], rock=ref['prior_rock'], lethal=ref['prior_lethal'], shape=ref['prior_elev'].shape))
    measured, trace = analyze_record(raw, metadata, truth, prior)
    row = dict(patch=patch, condition=cond, rep=rep, exit_code=exit_code, **measured)
    events = safety_events(raw)
    mission = json.loads((raw/'mission.json').read_text())
    row['online_error'] = str(mission.get('online_error', '') or '')
    if exit_code in ('124', '137'):
        row['status'] = 'wall_timeout'
    elif any(e['event'] == 'join_rejected_timeout' for e in events) or 'join_rejected' in row['online_error']:
        row['status'] = 'join_rejected'
    plans = read_csv_parts(raw/'plans.csv')
    failed = [p for p in plans if p['success'] != 'True']
    row['failed_plans'] = len(failed)
    for name in FAILURE_CLASSES:
        row['fail_'+name] = sum(p.get('failure_class') == name for p in failed)
    row['replans_lethal_changed'] = sum(p['reason'] == 'lethal_changed' for p in plans)
    for ev in ('join_accepted', 'join_rejected', 'join_rejected_timeout', 'unsafe_tilt', 'off_path', 'safety_replanned'):
        row['ev_'+ev] = sum(e['event'] == ev for e in events)
    row['join_accepted_with_blocked'] = sum(1 for e in events if e['event'] == 'join_accepted' and e['detail'].get('blocked_cells'))
    stops = after_stop(events, trace, float(trace.t.iloc[-1]))
    row['stops_detail'] = json.dumps(stops)
    row['stops_then_moved'] = sum(s['moved_until_end_m'] > 1.0 for s in stops)
    row['stops_then_stationary'] = sum(s['moved_until_end_m'] <= 1.0 for s in stops)
    ho = handoff_audit(run_dir, raw)
    row['snapshots'] = len(ho)
    row['snap_handoff_n'] = sum(h['at_handoff'] for h in ho)
    row['snap_handoff_with_lethal'] = sum(h['at_handoff'] and h['lethal_on_remaining'] > 0 for h in ho)
    row['snap_any_with_lethal'] = sum(h['lethal_on_remaining'] > 0 for h in ho)
    fmap, source = final_map(raw)
    row['map_source'] = source
    if fmap is not None:
        tmp = run_dir/'_audit_map.npz'
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
        row.update({k: q.get(k) for k in ('map_update_s_median', 'map_update_s_p95', 'map_update_s_max', 'map_updates',
                                           'map_failed_updates', 'queue_drops')})
    except (ValueError, OSError, KeyError) as exc:
        row['map_quality_error'] = type(exc).__name__+': '+str(exc)
    xy = trace[['x', 'y']].to_numpy()
    debris = ref['truth_rock'] & ~ref['prior_rock']
    row['truth_lethal_len_m'], row['truth_lethal_entries'] = contacts(xy, ref['truth_lethal'])
    row['debris_len_m'], row['debris_entries'] = contacts(xy, debris)
    row['plan_fail_snapshots'] = len(list((raw/'diag').glob('plan_fail_*.npz')))
    return row, raw


def outcome(row):
    if row['status'] == 'rollover':
        return 'rollover'
    if row['status'] == 'completed':
        return 'completed'
    if row['status'] == 'incomplete_waypoints':
        return 'partial'
    return row['status']


def sensor_update_table(raw):
    """Per-sensor map update times and drops from map_updates.csv (multi-sensor runs)."""
    rows = read_csv_parts(raw/'map_updates.csv')
    df = pd.DataFrame(rows)
    out = []
    key = 'sensor' if 'sensor' in df.columns else None
    groups = df.groupby(key) if key else [('lidar', df)]
    for name, g in groups:
        ok = g[g.status == 'ok'] if 'status' in g else g
        t = pd.to_numeric(ok.update_s, errors='coerce').dropna()
        drops = pd.to_numeric(g.get('queue_drops', pd.Series(dtype=float)), errors='coerce').dropna()
        out.append(dict(sensor=name, updates=len(ok), failed=int((g.status != 'ok').sum()) if 'status' in g else None,
                        update_s_median=t.median(), update_s_p95=t.quantile(.95), update_s_max=t.max(),
                        over_period=int((t > REAL_TIME_PERIOD_S).sum()), queue_drops_last=int(drops.iloc[-1]) if len(drops) else None))
    return out


def main(output):
    output = Path(output).resolve()
    rows, sensor_rows = [], []
    for patch in PATCHES+[STAGE2]:
        folder = output/'runs'/patch
        if not folder.exists():
            continue
        truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
        for run_dir in sorted(folder.iterdir()):
            if not (run_dir/'exit.txt').exists():
                continue
            cond, rep = run_dir.name.split('_r')
            try:
                row, raw = run_row(run_dir, patch, cond, int(rep), truth['terrain'])
            except ValueError as exc:
                # e.g. S2: the trial stopped before the follower recorded any pose; keep it as an incomplete record
                raw = next((run_dir/'physical_1'/'raw').iterdir())
                mission = json.loads((raw/'mission.json').read_text())
                manifest = json.loads((run_dir/'physical_1'/'manifest.json').read_text())
                case = next(c for c in manifest['cases'] if c.get('run_folder'))
                row = dict(patch=patch, condition=cond, rep=int(rep), exit_code=(run_dir/'exit.txt').read_text().strip(),
                           status=mission.get('status'), online_error=case.get('error', ''),
                           elapsed_s=float(mission.get('finished_t', 0))-float(mission.get('started_t', 0)),
                           stops_detail='[]', record_error=type(exc).__name__+': '+str(exc))
            rows.append(row)
            if cond.startswith('S'):
                for s in sensor_update_table(raw):
                    sensor_rows.append(dict(condition=cond, **s))
            print(patch, cond, rep, row['status'], flush=True)
    data = pd.DataFrame(rows)
    data['outcome'] = data.apply(outcome, axis=1)
    data.to_csv(output/'runs.csv', index=False)
    # stage 1 next to task030 C1
    old = pd.read_csv(ROOT/'results/eval_ground_endpoint/runs.csv')
    old = old[old.condition == 'C1'].copy()
    old['condition'] = '030_C1'
    stage1 = data[data.condition == 'P1']
    both = pd.concat([old, stage1], ignore_index=True)
    table = []
    for patch in PATCHES:
        for cond in ['030_C1', 'P1']:
            g = both[(both.patch == patch) & (both.condition == cond)]
            r = dict(patch=patch, condition=cond, n=len(g))
            for o in ['completed', 'partial', 'no_path', 'stuck', 'wall_timeout', 'join_rejected', 'rollover']:
                r[o] = int(g.outcome.eq(o).sum())
            for col in ['goals_reached', 'elapsed_s', 'truth_lethal_len_m', 'debris_len_m', 'map_fp_cells',
                        'map_fp_steep_cells', 'map_fp_obstacle_only_cells', 'map_fn_cells', 'replans_lethal_changed',
                        'ev_unsafe_tilt', 'ev_off_path', 'stops_then_moved', 'stops_then_stationary', 'ev_join_rejected',
                        'snap_handoff_with_lethal', 'plan_s_median', 'plan_s_max', 'map_update_s_median', 'map_update_s_max']:
                r[col] = describe(g[col]) if col in g else '-'
            table.append(r)
    table = pd.DataFrame(table)
    table.to_csv(output/'stage1_summary.csv', index=False)
    sensors = pd.DataFrame(sensor_rows)
    sensors.to_csv(output/'stage2_sensor_updates.csv', index=False)
    with pd.option_context('display.width', 300, 'display.max_columns', 80, 'display.max_colwidth', 60):
        cols = ['patch', 'condition', 'rep', 'outcome', 'online_error', 'goals_reached', 'elapsed_s', 'failed_plans',
                'replans_lethal_changed', 'ev_join_rejected', 'ev_join_rejected_timeout', 'ev_unsafe_tilt', 'ev_off_path',
                'ev_safety_replanned', 'stops_then_moved', 'stops_then_stationary', 'join_accepted_with_blocked',
                'snap_handoff_n', 'snap_handoff_with_lethal', 'snap_any_with_lethal', 'truth_lethal_len_m', 'debris_len_m',
                'rolled_over', 'map_fp_cells', 'map_fn_cells', 'map_update_s_median', 'map_update_s_p95', 'map_update_s_max', 'map_source']
        text = ('Task035 per run\n'+data[[c for c in cols if c in data]].to_string(index=False, float_format=lambda x: f'{x:.4g}')
                + '\n\nStage 1: task030 C1 vs C1+v1 (min/median/max over 3 runs; counts for outcomes)\n'+table.to_string(index=False)
                + '\n\nStage 2 per-sensor map updates (0.3x period = 0.333 s wall)\n'+(sensors.to_string(index=False) if len(sensors) else '(none)')
                + '\n\nSafety stops (unsafe_tilt/off_path) and what followed\n'
                + '\n'.join(f"{r.patch} {r.condition} r{r.rep}: {r.stops_detail}" for r in data.itertuples() if r.stops_detail != '[]') + '\n')
    (output/'report_log.txt').write_text(text)
    print(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT/'results/eval_035')
    main(parser.parse_args().output)
