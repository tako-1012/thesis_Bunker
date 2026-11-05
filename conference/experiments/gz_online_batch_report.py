"""Task021 recorded-only descriptive comparison; missing trials stay unknown."""

import argparse
from contextlib import redirect_stdout
import io
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
from tapp.collision import path_lethal_cells
from tapp.real_beach import build_real
from tapp.pure_pursuit import prepare_path, path_distance
from experiments.gz_compare_report import rollover_details
from ros2_jazzy.gz_checks.online_batch_runtime import MODES, map_signature, read_csv_parts, csv_parts

MEASURES = ['goals_reached', 'lethal_cells', 'debris_cells', 'n_replans', 'elapsed_s',
            'deviation_mean_m', 'deviation_max_m', 'roll_p95_deg', 'roll_max_deg',
            'pitch_p95_deg', 'pitch_max_deg', 'plan_s_median', 'plan_s_p95', 'plan_s_max']
PHYSICAL = MEASURES + ['returned_to_start', 'n_plans', 'calls_over_1s', 'deviation_samples',
                       'out_of_bounds_samples', 'rolled_over', 'rollover_t_s',
                       'rollover_elapsed_s', 'rollover_x_m', 'rollover_y_m']


def reached_goals(xy, stops, tolerance=.3):
    """Count the ordered prefix of five targets, including segment-circle entries."""
    xy, stops = np.asarray(xy, float), np.asarray(stops, float)
    goal = 0
    for a, b in zip(xy, np.vstack((xy[1:], xy[-1:]))):
        lower = 0.
        delta = b - a
        length2 = float(delta @ delta)
        while goal < len(stops):
            centre = stops[goal]
            if np.linalg.norm(a + lower * delta - centre) <= tolerance:
                goal += 1
                continue
            if not length2:
                break
            offset = a - centre
            discriminant = float(offset @ delta)**2 - length2 * (float(offset @ offset) - tolerance**2)
            if discriminant < 0:
                break
            entry = (-float(offset @ delta) - np.sqrt(discriminant)) / length2
            exit_at = (-float(offset @ delta) + np.sqrt(discriminant)) / length2
            if exit_at < lower or entry > 1:
                break
            lower = max(lower, float(entry))
            goal += 1
    return goal


def analyze_record(folder, metadata, truth, clean):
    folder = Path(folder)
    mission = json.loads((folder / 'mission.json').read_text())
    records = read_csv_parts(folder / 'trajectory.csv')
    if not records:
        raise ValueError('no recorded ground-truth trajectory')
    trace = pd.DataFrame(records).astype(float)
    columns = ['t', 'x', 'y', 'z', 'roll', 'pitch', 'yaw', 'v', 'w']
    if not np.isfinite(trace[columns].to_numpy()).all() or (np.diff(trace.t) < 0).any():
        raise ValueError('invalid recorded trajectory or simulator time reset')
    xy = trace[['x', 'y']].to_numpy()
    stops = np.asarray(metadata['stops'][:5]) * RESOLUTION
    reached = reached_goals(xy, stops)
    returned = bool(np.linalg.norm(xy[-1] - np.asarray(metadata['start']) * RESOLUTION) <= .3)
    rollover = rollover_details(trace)
    recorded_status = mission['status']
    status = 'rollover' if rollover['rolled_over'] else ('timeout' if recorded_status == 'simulation_timeout' else recorded_status)
    if status == 'completed' and (reached != 5 or not returned):
        status = 'incomplete_waypoints'
    events = read_csv_parts(folder / 'plans.csv')
    times = [float(row['plan_time_s']) for row in events]
    plans_available = bool(csv_parts(folder / 'plans.csv'))
    if not all(np.isfinite(times)) or any(t < 0 for t in times):
        raise ValueError('invalid recorded planning times')
    revisions = read_csv_parts(folder / 'path_revisions.csv')
    deviation = []
    previous_t = -np.inf
    for i, revision in enumerate(revisions):
        began = float(revision['t'])
        if began < previous_t:
            raise ValueError('path revision time decreased')
        previous_t = began
        ended = float(revisions[i+1]['t']) if i+1 < len(revisions) else np.inf
        path = prepare_path(json.loads(revision['path']))
        positions = xy[(trace.t >= began) & (trace.t < ended)]
        deviation.extend(path_distance(position, path) for position in positions)
    tm = truth['tmap']
    cells = xy / RESOLUTION
    result = dict(status=status, recorded_status=recorded_status, completed=status == 'completed',
                  data_source=mission.get('data_source', 'unknown_recording'),
                  goals_reached=reached, returned_to_start=returned,
                  lethal_cells=len(path_lethal_cells(cells, tm.lethal)),
                  debris_cells=len(path_lethal_cells(cells, tm.rock & ~clean['tmap'].rock)),
                  out_of_bounds_samples=int(np.any((cells < 0) | (cells > np.asarray(tm.shape)-1), axis=1).sum()),
                  elapsed_s=float(mission.get('finished_t', trace.t.iloc[-1]) - mission.get('started_t', trace.t.iloc[0])),
                  deviation_mean_m=float(np.mean(deviation)) if deviation else None,
                  deviation_max_m=float(np.max(deviation)) if deviation else None,
                  deviation_samples=len(deviation) if csv_parts(folder / 'path_revisions.csv') else None,
                  n_plans=len(times) if plans_available else None,
                  n_replans=sum(row['reason'] != 'start_leg' for row in events) if plans_available else None,
                  plan_s_median=float(np.median(times)) if times else None,
                  plan_s_p95=float(np.percentile(times, 95)) if times else None,
                  plan_s_max=max(times) if times else None,
                  calls_over_1s=sum(t > 1 for t in times) if plans_available else None,
                  **rollover)
    for axis in ['roll', 'pitch']:
        angles = np.abs(np.degrees(trace[axis]))
        result[axis + '_p95_deg'] = float(np.percentile(angles, 95))
        result[axis + '_max_deg'] = float(np.max(angles))
    return result, trace


def summary_tables(data):
    summary, effects = [], []
    for mode in MODES:
        group = data[data['mode'] == mode]
        measured = group[group.data_source.eq('gazebo')]
        known = len(measured)
        row = dict(mode=mode, scheduled=len(group), executed=known,
                   unexecuted=len(group)-known,
                   planning_infeasible=int(group.planning_status.ne('planned').sum()))
        for status in ['completed', 'stuck', 'rollover', 'timeout', 'no_path', 'incomplete_waypoints', 'runtime_error']:
            row[status] = int(measured.status.eq(status).sum()) if known else None
        known_statuses = ['completed', 'stuck', 'rollover', 'timeout', 'no_path', 'incomplete_waypoints', 'runtime_error']
        row['other_failure'] = int((~measured.status.isin(known_statuses)).sum()) if known else None
        for metric in MEASURES:
            row[metric+'_median'] = pd.to_numeric(measured[metric]).median()
        summary.append(row)
    pairs = data[data['mode'] == 'online'].merge(data[data['mode'] == 'fixed'], on='patch', suffixes=('_online', '_fixed'), validate='one_to_one')
    for metric in MEASURES:
        both = (pairs.data_source_online.eq('gazebo') & pairs.data_source_fixed.eq('gazebo') &
                pairs.completed_online.eq(True) & pairs.completed_fixed.eq(True))
        delta = pd.to_numeric(pairs.loc[both, metric+'_online']) - pd.to_numeric(pairs.loc[both, metric+'_fixed'])
        effects.append(dict(metric=metric, paired_completed=int(delta.notna().sum()),
                            online_minus_fixed_median=delta.median()))
    return pd.DataFrame(summary), pd.DataFrame(effects)


def summarize(output, *, figures=True):
    output = Path(output).resolve()
    manifest = json.loads((output / 'manifest.json').read_text())
    metadata = {sc['patch']: sc for sc in manifest['scenarios']}
    cases = manifest['cases']
    if (len(metadata) != 10 or len(cases) != 20 or len({(c['patch'], c['mode']) for c in cases}) != 20
            or any({c['mode'] for c in cases if c['patch'] == name} != set(MODES) for name in metadata)):
        raise ValueError('expected the same ten beaches x fixed/online')
    rows, traces, maps = [], {}, {}
    for case in cases:
        patch = case['patch']
        if patch not in maps:
            truth = build_real(patch, 200, 0, debris=True, dataset='shizuoka_beach_las')
            clean = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
            if map_signature(truth) != metadata[patch]['truth_signature'] or map_signature(clean) != metadata[patch]['prior_signature']:
                raise ValueError('regenerated maps differ from the recorded inputs: ' + patch)
            maps[patch] = truth, clean
        row = dict(patch=patch, mode=case['mode'], planner=manifest['planner'],
                   planning_status=case['planning_status'], status='未実行', recorded_status=None,
                   completed=None, data_source=None, error=case.get('error', ''),
                   **{key: None for key in PHYSICAL})
        if case.get('run_folder'):
            try:
                measured, trace = analyze_record(output / case['run_folder'], metadata[patch], *maps[patch])
                row.update(measured)
                traces[patch, case['mode']] = trace
            except (ValueError, OSError, KeyError) as exc:
                row.update(status='記録不完全', error=type(exc).__name__ + ': ' + str(exc))
        elif case['planning_status'] != 'planned':
            row['status'] = 'planning_' + case['planning_status']
        rows.append(row)
    data = pd.DataFrame(rows)
    data.to_csv(output / 'runs.csv', index=False)
    summary, effects = summary_tables(data)
    summary.to_csv(output / 'summary.csv', index=False)
    effects.to_csv(output / 'paired_differences.csv', index=False)
    if figures:
        for patch, (truth, clean) in maps.items():
            tm = truth['tmap']
            fig, ax = plt.subplots(figsize=(7, 7))
            ax.imshow(tm.elev.T, origin='lower', extent=[-.25, 199.75, -.25, 199.75], cmap='terrain')
            overlay = np.zeros((*tm.shape, 4))
            overlay[tm.rock & ~clean['tmap'].rock] = [1, .2, 0, .85]
            ax.imshow(overlay.transpose(1, 0, 2), origin='lower', extent=[-.25, 199.75, -.25, 199.75])
            sc = metadata[patch]
            if sc['initial_path']:
                ax.plot(*np.asarray(sc['initial_path']).T, color='gray', ls='--', label='prior plan (not a recording)')
            for mode in MODES:
                if (patch, mode) in traces:
                    trace = traces[patch, mode]
                    status = data[(data.patch == patch) & (data['mode'] == mode)].iloc[0].status
                    ax.plot(trace.x, trace.y, label=mode + ' (' + status + ')')
            for i, point in enumerate(np.asarray(sc['stops'][:5]) * RESOLUTION, 1):
                ax.scatter(*point, marker='x', color='black')
                ax.annotate(str(i), point)
            actual = any((patch, mode) in traces for mode in MODES)
            ax.set(title=patch + ('; recorded trajectories' if actual else '; physical trials NOT EXECUTED'),
                   xlabel='x [m]', ylabel='y [m]', aspect='equal')
            ax.text(.01, .01, 'Orange: inflated debris footprint', transform=ax.transAxes,
                    bbox=dict(facecolor='white', alpha=.8), fontsize=8)
            ax.legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(output / (patch + '.png'), dpi=130)
            plt.close(fig)
    stream = io.StringIO()
    with redirect_stdout(stream):
        print('Task021: ten LAS test beaches x fixed/online; descriptive only, no hypothesis tests or energy.')
        print('Missing physical values are blank/None/NaN; planning failure is not a completed or safe trial.')
        print(data.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nCounts use actual Gazebo recordings only; 5 ordered targets plus return required for completion.')
        print(summary.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('\nOnline minus fixed; paired medians among two completed physical tours only.')
        print(effects.to_string(index=False, float_format=lambda x: f'{x:.6g}'))
        print('Deviation uses the follower-acknowledged active path; pre-first-plan samples are excluded.')
        print('Planning times: A* plus smoothing only, excluding map inflation, tour ordering and ROS handoff.')
        print('One second corresponds to 1m travel at the 1m/s speed cap; these timings alone do not prove real-time safety.')
        print('Sensor: perfect R10 traversability labels, including the dilation halo; no LiDAR, occlusion or error.')
    log = stream.getvalue()
    (output / 'gazebo_online_log.txt').write_text(log)
    print(log, end='')
    return data, summary, effects


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, nargs='?', default=ROOT / 'results/gazebo_online')
    summarize(parser.parse_args().output)
