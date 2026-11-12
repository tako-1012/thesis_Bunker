"""Task024: cached and rerun physical tours, descriptive pairs, unknowns retained."""

import argparse
from contextlib import redirect_stdout
import hashlib
import io
from itertools import combinations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import build_real
from ros2_jazzy.gz_checks.lidar_map import matched_task022_maps
from ros2_jazzy.gz_checks.edge_margin_checks import MODES
from experiments.gz_online_batch_report import analyze_record, PHYSICAL, MEASURES
from experiments.gz_lidar_report import map_quality, QUALITY

UPDATE_FIELDS = ['map_update_s_median', 'map_update_s_p95', 'map_update_s_max']
METRICS = MEASURES+UPDATE_FIELDS
STATUSES = ['completed', 'stuck', 'rollover', 'no_path', 'timeout', 'runtime_error', 'incomplete_waypoints']


def load_maps(patch):
    truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
    clean = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
    truth, clean, _ = matched_task022_maps(patch, truth, clean)
    return truth, clean


def cached_row(case):
    data = pd.read_csv(ROOT/case['archive_csv'], float_precision='round_trip')
    selected = data[(data.patch == case['patch']) & (data['mode'] == case['archive_mode'])]
    if len(selected) != 1:
        raise ValueError('cached physical row must be unique')
    return selected.iloc[0]


def summary_tables(data):
    summaries, pairs = [], []
    for mode in MODES:
        group = data[data['mode'] == mode]
        known = group[group.data_source.eq('gazebo')]
        eligible = group[group.record_origin.ne('excluded')]
        row = dict(mode=mode, scheduled=len(group), eligible=len(eligible), excluded=len(group)-len(eligible),
                   reused=int(group.record_origin.eq('reused').sum()),
                   rerun_requested=int(group.record_origin.eq('rerun').sum()),
                   rerun_recorded=int(known.record_origin.eq('rerun').sum()),
                   executed=len(known), unexecuted=len(eligible)-len(known))
        for status in STATUSES:
            row[status] = int(known.status.eq(status).sum()) if len(known) else None
        row['other_failure'] = int((~known.status.isin(STATUSES)).sum()) if len(known) else None
        for metric in METRICS:
            values = pd.to_numeric(known[metric]).dropna()
            row[metric+'_median'] = values.median() if len(values) else None
        summaries.append(row)
    for reference, method in combinations(MODES, 2):
        joined = data[data['mode'] == method].merge(data[data['mode'] == reference], on='patch',
                                                   suffixes=('_a', '_b'), validate='one_to_one')
        valid = (joined.completed_a.eq(True) & joined.completed_b.eq(True) &
                 joined.data_source_a.eq('gazebo') & joined.data_source_b.eq('gazebo'))
        for metric in METRICS:
            delta = (pd.to_numeric(joined.loc[valid, metric+'_a'])-
                     pd.to_numeric(joined.loc[valid, metric+'_b'])).dropna()
            pairs.append(dict(method=method, reference=reference, metric=metric, paired_completed=len(delta),
                              delta_median=delta.median() if len(delta) else None))
    return pd.DataFrame(summaries), pd.DataFrame(pairs)


def summarize(output, *, figures=True):
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text())
    metadata = {s['patch']: s for s in manifest['scenarios']}
    audits = {s['patch']: s for s in manifest['waypoint_audit']}
    cases = manifest['cases']
    if (manifest['task'] != 24 or manifest['edge_margin_m'] != 10 or len(metadata) != 10 or len(cases) != 40
            or {(c['patch'], c['mode']) for c in cases} != {(p, m) for p in metadata for m in MODES}):
        raise ValueError('retain exactly ten patches x four methods with the fixed 10m margin')
    for name, checksum in manifest['archive_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != checksum:
            raise ValueError('an archived input/recording changed: '+name)
    rows, traces, maps = [], {}, {}
    for case in cases:
        patch, origin = case['patch'], case['record_origin']
        if origin not in ('reused', 'rerun', 'excluded'):
            raise ValueError('unknown recording origin')
        audit = audits[patch]
        if (origin == 'reused' and (audit['points_changed'] or not audit['eligible'])):
            raise ValueError('cannot reuse a changed or excluded tour')
        row = dict(patch=patch, mode=case['mode'], record_origin=origin, execution='未実行',
                   planner=manifest['planner'], planning_status=case['planning_status'],
                   status='未実行', recorded_status=None, completed=None, data_source=None,
                   error=case.get('error', ''), **dict.fromkeys(PHYSICAL+QUALITY+['sensor_error']))
        if origin == 'excluded':
            row.update(status='対象外', execution='対象外')
        elif origin == 'reused':
            cached = cached_row(case)
            for field in PHYSICAL+QUALITY+['status', 'recorded_status', 'completed', 'data_source', 'sensor_error']:
                if field in cached:
                    row[field] = cached[field]
            row['execution'] = '再利用'
        elif case.get('run_folder'):
            folder = (output/case['run_folder']).resolve()
            if not folder.is_relative_to(output):
                raise ValueError('new recordings must stay inside their output folder')
            try:
                if patch not in maps:
                    maps[patch] = load_maps(patch)
                measured, trace = analyze_record(folder, metadata[patch], *maps[patch])
                row.update(measured, execution='実走' if measured['data_source'] == 'gazebo' else '非Gazebo記録')
                traces[patch, case['mode']] = trace
            except (ValueError, KeyError, OSError) as exc:
                row.update(status='記録不完全', execution='記録不完全', error=type(exc).__name__+': '+str(exc))
            else:
                if case['mode'] in ('lidar', 'fine'):
                    try:
                        row.update(map_quality(folder, maps[patch][0]))
                    except (ValueError, KeyError, OSError) as exc:
                        row['error'] += '; map audit: '+type(exc).__name__+': '+str(exc)
        elif case['planning_status'] != 'planned':
            row['status'] = 'planning_'+case['planning_status']
        rows.append(row)
    data = pd.DataFrame(rows)
    summary, pairs = summary_tables(data)
    data.to_csv(output/'runs.csv', index=False)
    summary.to_csv(output/'summary.csv', index=False)
    pairs.to_csv(output/'paired_differences.csv', index=False)
    waypoint_rows = []
    for audit in manifest['waypoint_audit']:
        for i, (old, new, old_m, new_m) in enumerate(zip(audit['old_points'], audit['new_points'], audit['old_edge_m'], audit['new_edge_m']), 1):
            waypoint_rows.append(dict(patch=audit['patch'], points_changed=audit['points_changed'], eligible=audit['eligible'],
                                      start=repr(audit['start']), start_edge_m=audit['start_edge_m'], slot=i,
                                      old_point=repr(old), old_edge_m=old_m, new_point=repr(new), new_edge_m=new_m))
    waypoints = pd.DataFrame(waypoint_rows)
    waypoints.to_csv(output/'waypoints.csv', index=False)
    if figures:
        for patch in sorted({p for p, _ in traces}):
            truth, clean = maps[patch]
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.imshow(truth['tmap'].elev.T, origin='lower', extent=[-.25, 199.75, -.25, 199.75], cmap='terrain')
            ax.contour(truth['tmap'].rock.T & ~clean['tmap'].rock.T, levels=[.5], colors=['orange'],
                       extent=[0, 199.5, 0, 199.5], linewidths=.5)
            for mode in MODES:
                if (patch, mode) in traces:
                    trace = traces[patch, mode]
                    ax.plot(trace.x, trace.y, label=mode)
            points = np.asarray(metadata[patch]['points'])*RESOLUTION
            ax.scatter(points[:, 0], points[:, 1], c='black', marker='x', label='new targets')
            ax.set(title=patch+' task024 reruns', xlabel='x [m]', ylabel='y [m]', aspect='equal')
            ax.legend()
            fig.tight_layout()
            fig.savefig(output/('trajectory_'+patch+'.png'), dpi=130)
            plt.close(fig)
    fields = ['patch', 'mode', 'record_origin', 'execution', 'status', 'goals_reached', 'lethal_cells', 'debris_cells',
              'plan_s_median', 'plan_s_p95', 'plan_s_max', *UPDATE_FIELDS,
              'roll_p95_deg', 'roll_max_deg', 'pitch_p95_deg', 'pitch_max_deg']
    stream = io.StringIO()
    with redirect_stdout(stream):
        print('Task024: fixed 10m edge margin, same ten LAS test patches, four methods; no tuning.')
        print('Distance uses outermost grid centres [0,199.5]m; start is never moved.')
        print('Waypoint audit: old/new cell coordinates and edge distances [m].')
        print(waypoints.to_string(index=False))
        print('\nrecord_origin: reused = archived unchanged tour; rerun = new tour requested; execution states whether it ran.')
        print(data[fields].to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nCounts and per-run medians among actual recordings only; partial counts do not establish disappearance of rollovers.')
        print(summary.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nMethod minus reference: paired medians only where BOTH complete the five targets and return.')
        print(pairs.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('Missing physical/map timings remain None/NaN. No hypothesis tests or energy columns.')
        print('Contact is audited on centre trajectories; it does not establish clearance of the entire body.')
    log = stream.getvalue()
    (output/'edge_margin_log.txt').write_text(log)
    print(log, end='')
    return data, summary, pairs


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT/'results/edge_margin')
    summarize(parser.parse_args().output)
