"""Task021 cached controls plus measured LiDAR trials; unknown values stay blank."""

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import build_real
from experiments.gz_online_batch_report import analyze_record, MEASURES, PHYSICAL
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts, csv_parts, map_signature
from ros2_jazzy.gz_checks.lidar_checks import verify_inputs

MODES = ('fixed', 'online', 'lidar')
QUALITY = ['height_cells', 'height_abs_error_median_m', 'height_abs_error_p95_m', 'height_abs_error_max_m',
           'map_update_s_median', 'map_update_s_p95', 'map_update_s_max', 'map_updates',
           'map_failed_updates', 'queue_drops', 'sim_to_wall_ratio']


def map_quality(folder, truth=None):
    folder = Path(folder)
    result = dict.fromkeys(QUALITY+['sensor_error'])
    path = folder/'pointcloud_map.npz'
    if path.exists():
        with np.load(path, allow_pickle=False) as data:
            elev, seen = data['elev'], data['seen']
            if (elev.ndim != 2 or seen.shape != elev.shape or seen.dtype != bool or
                    (truth is not None and elev.shape != truth['tmap'].shape)):
                raise ValueError('invalid estimated map grid')
            if not np.isfinite(elev[seen]).all():
                raise ValueError('invalid observed heights')
            result['height_cells'] = int(seen.sum())
            error = np.abs(elev[seen]-truth['tmap'].elev[seen]) if truth is not None else []
            if len(error):
                result.update(height_abs_error_median_m=float(np.median(error)),
                              height_abs_error_p95_m=float(np.percentile(error, 95)),
                              height_abs_error_max_m=float(np.max(error)))
    if csv_parts(folder/'map_updates.csv'):
        updates = read_csv_parts(folder/'map_updates.csv')
        times = [float(row['update_s']) for row in updates if row['status'] == 'ok']
        if not np.isfinite(times).all() or any(t < 0 for t in times):
            raise ValueError('invalid recorded map update times')
        result.update(map_updates=len(times), map_failed_updates=sum(row['status'] != 'ok' for row in updates))
        if times:
            result.update(map_update_s_median=float(np.median(times)), map_update_s_p95=float(np.percentile(times, 95)),
                          map_update_s_max=max(times))
    if (folder/'sensor_status.json').exists():
        sensor = json.loads((folder/'sensor_status.json').read_text())
        result['queue_drops'] = sensor['queue_drops']
        result['sensor_error'] = sensor.get('error')
    if (folder/'mission.json').exists():
        mission = json.loads((folder/'mission.json').read_text())
        wall = mission.get('wall_elapsed_s')
        if wall is not None and wall > 0 and mission.get('started_t') is not None and mission.get('finished_t') is not None:
            result['sim_to_wall_ratio'] = (mission['finished_t']-mission['started_t'])/wall
    return result


def tables(data):
    rows, pairs = [], []
    statuses = ['completed', 'stuck', 'rollover', 'timeout', 'no_path', 'incomplete_waypoints', 'runtime_error']
    for mode in MODES:
        group = data[data['mode'] == mode]
        measured = group[group.data_source.eq('gazebo')]
        row = dict(mode=mode, scheduled=len(group), selected=int(group.selected.sum()),
                   executed=len(measured), unexecuted=len(group)-len(measured))
        for status in statuses:
            row[status] = int(measured.status.eq(status).sum()) if len(measured) else None
        for field in MEASURES+QUALITY:
            values = pd.to_numeric(measured[field]).dropna()
            row[field+'_median'] = values.median() if len(values) else None
        rows.append(row)
    for method, reference in [('online', 'fixed'), ('lidar', 'fixed'), ('lidar', 'online')]:
        joined = data[data['mode'] == method].merge(data[data['mode'] == reference], on='patch', suffixes=('_a', '_b'), validate='one_to_one')
        valid = (joined.completed_a.eq(True) & joined.completed_b.eq(True) & joined.data_source_a.eq('gazebo') & joined.data_source_b.eq('gazebo'))
        for metric in MEASURES:
            delta = pd.to_numeric(joined.loc[valid, metric+'_a'])-pd.to_numeric(joined.loc[valid, metric+'_b'])
            delta = delta.dropna()
            pairs.append(dict(method=method, reference=reference, metric=metric,
                              paired_completed=len(delta), delta_median=delta.median() if len(delta) else None))
    return pd.DataFrame(rows), pd.DataFrame(pairs)


def summarize(output, baseline=None, *, figures=True):
    output = Path(output).resolve()
    baseline = ROOT/'results/gazebo_online/physical_run' if baseline is None else Path(baseline).resolve()
    manifest = json.loads((output/'manifest.json').read_text())
    original = json.loads((baseline/'manifest.json').read_text())
    if manifest['scenarios'] != original['scenarios']:
        raise ValueError('LiDAR cohort changed task021 scenarios, endpoints, or tour order')
    cases = manifest['cases']
    if len(cases) != 10 or len({c['patch'] for c in cases}) != 10 or any(c['mode'] != 'lidar' for c in cases):
        raise ValueError('LiDAR manifest must retain ten distinct scenarios, including unselected ones')
    old = pd.read_csv(baseline/'runs.csv', float_precision='round_trip')
    if len(old) != 20 or set(old['mode']) != {'fixed', 'online'}:
        raise ValueError('expected task021 twenty cached physical control rows')
    old['selected'] = True
    for field in QUALITY:
        old[field] = None
    rows, maps, traces, audits = [], {}, {}, []
    for case, meta in zip(cases, manifest['scenarios']):
        if case['patch'] != meta['patch']:
            raise ValueError('scenario order mismatch')
        patch = case['patch']
        truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
        prior = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
        audits.append(verify_inputs(patch, meta, truth, prior))
        exact_height = False
        if case.get('run_folder'):
            reference = output/case['run_folder']/'evaluation_reference.npz'
            if reference.exists():
                with np.load(reference, allow_pickle=False) as data:
                    loaded = []
                    for name in ['truth', 'prior']:
                        z = data[name+'_elev'].copy()
                        rock, lethal = data[name+'_rock'].copy(), data[name+'_lethal'].copy()
                        if (z.shape != truth['tmap'].shape or not np.isfinite(z).all() or rock.shape != z.shape or lethal.shape != z.shape
                                or rock.dtype != bool or lethal.dtype != bool):
                            raise ValueError('invalid actual-run evaluation reference')
                        loaded.append(dict(tmap=SimpleNamespace(elev=z, rock=rock, lethal=lethal, shape=z.shape)))
                truth, prior = loaded
                exact_height = True
                if case.get('input_audit') and (map_signature(truth) != case['input_audit']['signatures']['truth'] or
                                                 map_signature(prior) != case['input_audit']['signatures']['prior']):
                    raise ValueError('actual-run evaluation reference hash mismatch')
            elif case.get('input_audit'):
                exact_height = map_signature(truth)['elev'] == case['input_audit']['signatures']['truth']['elev']
        maps[patch] = truth, prior
        row = dict(patch=patch, mode='lidar', planner='TA*-S+inflate', selected=case['selected'],
                   planning_status=case['planning_status'], status='未実行', recorded_status=None,
                   completed=None, data_source=None, error=case.get('error', ''),
                   sensor_error=None,
                   **dict.fromkeys(PHYSICAL+QUALITY))
        if case.get('run_folder'):
            folder = output/case['run_folder']
            try:
                measured, trace = analyze_record(folder, meta, truth, prior)
                row.update(measured)
                traces[patch, 'lidar'] = trace
            except (ValueError, OSError, KeyError) as exc:
                row.update(status='記録不完全', error=type(exc).__name__+': '+str(exc))
            try:
                row.update(map_quality(folder, truth if exact_height else None))
                if not exact_height and (folder/'pointcloud_map.npz').exists():
                    row['error'] += '; height error unavailable: exact actual-run evaluation grid missing'
            except (ValueError, OSError, KeyError) as exc:
                row['error'] += '; mapping audit: '+str(exc)
        rows.append(row)
    data = pd.concat([old, pd.DataFrame(rows)], ignore_index=True)
    (output/'baseline_input_audit.json').write_text(json.dumps(audits, indent=2)+'\n')
    data.to_csv(output/'runs.csv', index=False)
    summary, effects = tables(data)
    summary.to_csv(output/'summary.csv', index=False)
    effects.to_csv(output/'paired_differences.csv', index=False)
    if figures:
        old_cases = {(c['patch'], c['mode']): c for c in original['cases']}
        for meta in manifest['scenarios']:
            patch = meta['patch']
            truth, prior = maps[patch]
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.imshow(truth['tmap'].elev.T, origin='lower', extent=[-.25, 199.75, -.25, 199.75], cmap='terrain')
            overlay = np.zeros((*truth['tmap'].shape, 4))
            overlay[truth['tmap'].rock & ~prior['tmap'].rock] = [1, .2, 0, .8]
            ax.imshow(overlay.transpose(1, 0, 2), origin='lower', extent=[-.25, 199.75, -.25, 199.75])
            for mode in MODES:
                trace = traces.get((patch, mode))
                if mode != 'lidar' and old_cases[patch, mode].get('run_folder'):
                    path = baseline/old_cases[patch, mode]['run_folder']/'trajectory.csv'
                    trace = pd.DataFrame(read_csv_parts(path)).astype(float)
                if trace is not None and len(trace):
                    ax.plot(trace.x, trace.y, label=mode+(' (task021 recording)' if mode != 'lidar' else ' (LiDAR recording)'))
            for i, point in enumerate(np.asarray(meta['stops'][:5])*RESOLUTION, 1):
                ax.scatter(*point, marker='x', color='black')
                ax.annotate(str(i), point)
            ax.set(title=patch+('' if (patch, 'lidar') in traces else '; LiDAR NOT EXECUTED'), xlabel='x [m]', ylabel='y [m]', aspect='equal')
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(output/(patch+'.png'), dpi=130)
            plt.close(fig)
    stream = io.StringIO()
    with redirect_stdout(stream):
        print('Task022: task021 fixed/R10 controls plus LiDAR, ten identical LAS scenarios; descriptive only.')
        print('Controls are cached task021 physical measurements. Unknown LiDAR outcomes remain blank/None/NaN.')
        print(data.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nCounts use actual recordings; selected is the requested 3/10 LiDAR rollout stage.')
        print(summary.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nMethod minus reference; only both completed physical tours; no hypothesis tests or energy.')
        print(effects.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('Height errors: absolute errors in the final unique hit cells; median return surface versus truth DEM.')
        print('Mapping times include PointCloud2 decoding, registration, fusion and feature recomputation; not planning/ROS handoff.')
        print('R10 control and 30m LiDAR differ in range/beam sparsity/occlusion/noise; this is not an isolated occlusion comparison.')
        print('Keep 08OB89_00152: task021 rollover is a map-boundary artifact, not a measured planner effect.')
    log = stream.getvalue()
    (output/'gazebo_lidar_log.txt').write_text(log)
    print(log, end='')
    return data, summary, effects


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT/'results/gazebo_lidar')
    args = parser.parse_args()
    summarize(args.output)
