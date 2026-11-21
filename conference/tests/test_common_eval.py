"""Known geometry and read-only replay of task030, 035 and 037 archives."""

from collections import Counter
from contextlib import redirect_stdout, redirect_stderr
import gzip
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import tempfile

import numpy as np

from experiments import eval_runs as audit

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/'results'


def keyed(rows):
    result = {(row['patch'], row['condition'], row['rep']): row for row in rows}
    assert len(result) == len(rows)
    return result


def same(actual, expected):
    try:
        return math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12)
    except (TypeError, ValueError):
        return actual.casefold() == expected.casefold()


def replay(name, experiment, output, reference=None):
    args = [str(RESULTS/name), '--experiment', experiment, '--out', str(output)]
    if reference is not None:
        args.extend(['--reference-root', str(reference)])
    log = StringIO()
    with redirect_stdout(log):
        audit.main(args)
    print(log.getvalue(), end='')
    actual = keyed(audit.read_csv(output/'runs.csv')[1])
    expected = keyed(audit.read_csv(RESULTS/name/'runs.csv')[1])
    assert actual.keys() == expected.keys()
    return actual, expected


def assert_columns(actual, expected, columns, *, allow_missing=False):
    matched = Counter()
    for trial, before in expected.items():
        after = actual[trial]
        for column in columns:
            if not before[column]:
                continue
            if not after[column] and allow_missing:
                assert column in json.loads(after['missing_reasons']), (trial, column)
                continue
            assert same(after[column], before[column]), (trial, column, after[column], before[column])
            matched[column] += 1
    assert matched.keys() == set(columns), matched
    return matched


def archive_030(output):
    ref = RESULTS/'gazebo_lidar/physical_10/raw'
    # 030 omitted references because the task022 archives contain the same bytes.
    # Check all the archived hashes before using the separate reference root.
    digests = {}
    for line in (RESULTS/'eval_ground_endpoint/not_committed.txt').read_text().splitlines():
        if line.endswith('/evaluation_reference.npz'):
            sha, _, path = line.split()
            patch = Path(path).parent.name
            if patch not in digests:
                digests[patch] = hashlib.sha256((ref/patch/'evaluation_reference.npz').read_bytes()).hexdigest()
            assert digests[patch] == sha, patch
    assert len(digests) == 5
    actual, expected = replay('eval_ground_endpoint', '030', output, ref)
    counts = assert_columns(actual, expected, (
        'exit_code', 'outcome', 'status', 'recorded_status', 'goals_reached', 'returned_to_start',
        'truth_lethal_len_m', 'truth_lethal_entries', 'debris_len_m', 'debris_entries', 'lethal_cells',
        'debris_cells', 'rolled_over', 'rollover_t_s', 'deviation_mean_m', 'deviation_max_m',
        'n_plans', 'failed_plans', 'fail_goal_cell', 'fail_start_cell', 'fail_start_steep',
        'map_fp_cells', 'map_fn_cells', 'map_fp_steep_cells', 'map_fp_obstacle_only_cells',
        'detector_fp_cells', 'detector_fn_cells', 'map_updates', 'map_update_s_p95',
        'stops_unreachable', 'relaxed_len_m', 'relaxed_truth_lethal_len_m'), allow_missing=True)
    for key in ('outcome', 'goals_reached', 'truth_lethal_len_m', 'debris_len_m', 'deviation_max_m'):
        assert counts[key] == 45, counts
    assert counts['map_fp_cells'] == 43 and counts['relaxed_len_m'] == 15, counts
    assert sum(row['board_outcome'] == 'stuck' for row in actual.values()) == 2
    assert sum(row['rolled_over'] == 'True' for row in actual.values()) == 3
    print('030 compared per-field counts:', dict(counts))


def archive_035(output):
    actual, expected = replay('eval_035', '035', output)
    counts = assert_columns(actual, expected, (
        'exit_code', 'outcome', 'status', 'n_plans', 'n_replans', 'failed_plans', 'fail_goal_cell',
        'ev_off_path', 'ev_unsafe_tilt', 'ev_safety_replanned', 'map_updates', 'map_update_s_median',
        'map_update_s_p95', 'map_update_s_max', 'queue_drops'), allow_missing=False)
    assert sum(float(row['ev_off_path']) for key, row in actual.items() if key[1] == 'P1') == 23
    assert all(row['debris_len_m'] == '' and row['map_fp_cells'] == '' for row in actual.values())
    saved = audit.read_csv(RESULTS/'eval_035/stage2_sensor_updates.csv')[1]
    for old in saved:
        new = actual[('08OB86_-0205', old['condition'], '1')]
        for archived, common in (('updates', 'map_updates'), ('failed', 'map_failed_updates'),
                                 ('update_s_median', 'map_update_s_median'), ('update_s_p95', 'map_update_s_p95'),
                                 ('update_s_max', 'map_update_s_max'), ('over_period', 'updates_over_target_period'),
                                 ('queue_drops_last', 'queue_drops_last')):
            if old[archived]:
                assert same(new[old['sensor']+'_'+common], old[archived]), (old, common)
    assert actual[('08OB86_-0205', 'S2', '1')]['elapsed_s'] == ''
    print('035 compared per-field counts:', dict(counts), f'plus {len(saved)} sensor rows')


def archive_037(output):
    actual, expected = replay('real_sensors_compare', '037', output)
    counts = assert_columns(actual, expected, ('exit_code',))
    assert counts['exit_code'] == 30
    for row in actual.values():
        reasons = json.loads(row['missing_reasons'])
        for field in ('outcome', 'debris_len_m', 'ev_off_path', 'map_fp_cells', 'lidar_map_update_s_p95'):
            assert not row[field] and field in reasons
    board = audit.read_csv(output/'outcomes_board.csv')[1]
    assert all(not row['完走'] and not row['経路なし'] for row in board)
    # Secondary cross-check of the published 037 aggregates. These tables
    # are expectations only, never substituted for the absent raw inputs.
    history = audit.read_csv(RESULTS/'real_sensors_compare/outcome_counts.csv')[1]
    for row in history:
        group = [r for (p, c, _), r in expected.items() if (p, c) == (row['patch'], row['condition'])]
        assert len(group) == 3
        for field in ('completed', 'no_path'):
            assert sum(r['outcome'] == field for r in group) == int(row[field])
    stops = audit.read_csv(RESULTS/'real_sensors_compare/stop_followup.csv')[1]
    assert len(stops) == sum(int(float(row['ev_off_path'])) for row in expected.values()) == 52
    assert math.isclose(float(expected[('08OB89_-0847', 'L', '2')]['debris_len_m']), .077, abs_tol=.001)
    print('037 matched 30 metadata/exit records; absent raw outcome, geometry, events and updates stayed blank')


def synthetic(root):
    raw = root/'B_r2'/'physical_1'/'raw'/'beach'
    raw.mkdir(parents=True)
    (raw/'mission.json').write_text(json.dumps(dict(status='no_path', started_t=0, finished_t=5, wall_elapsed_s=5)))
    for name, content in {
        'trajectory.csv': 't,x,y,roll,pitch\n0,-2,0,0,0\n2,0,0,0,0\n',
        'path_revisions.csv': 't,path\n0,"[[-2,1],[0,1],[0,2]]"\n3,"[[0,0],[4,0]]"\n',
        'plans.csv': 'reason,success,plan_time_s,failure_class\nstart_leg,False,0.03,goal_cell\n',
        'debris_footprints.csv': 'xmin,ymin,xmax,ymax\n0,-0.25,1,0.25\n',
        'clearance.csv': 'sim_time,clearance_m\n0,\n3,0.13\n5,0.25\n',
        'safety_events.csv': 'sim_time,event,detail\n2,off_path,{}\n3,safety_replanned,{}\n',
        'map_updates.csv': 'stamp,status,sensor,update_s,queue_drops\n1,ok,lidar,0.11,0\n2,ok,camera1,0.01,0\n',
    }.items():
        (raw/name).write_text(content)
    with gzip.open(raw/'trajectory_part001.csv.gz', 'wt') as stream:
        stream.write('t,x,y,roll,pitch\n3,1,0,0,0\n5,3,0,0,0\n')
    (raw.parents[1]/'probe.csv').write_text(
        'status,sim_t,wall_s,cmd_count,cloud_age_sim_s\nrunning,0,1,7,0.3\n'
        'running,1,2,20,0.5\nrunning,2,3,18,0.4\n')
    map_file = root/'names.csv'
    map_file.write_text('path,condition\nB_r2,centre\n')
    result = audit.evaluate_run(raw, '042', audit.read_conditions(map_file))
    assert result['rep'] == 2 and result['condition'] == 'centre'
    assert result['outcome'] == 'no_path' and result['no_path_type'] == 'goal_cell'
    assert result['deviation_max_t_s'] == 0 and result['deviation_max_x_m'] == -2
    assert result['deviation_max_m'] == result['deviation_p95_m'] == 1
    assert math.isclose(result['deviation_max_curvature_inv_m'], 2/math.sqrt(5))
    assert result['min_truth_clearance_m'] == 0 and result['truth_below_radius_entries'] == 1
    assert math.isclose(result['truth_below_radius_s'], 2)
    assert result['min_observed_clearance_m'] == .13
    assert result['stops_replanned_and_moved_30s'] == 1
    assert result['cmd_vel_hz_sim'] == 19 and result['cloud_age_sim_max_s'] == .5
    assert result['lidar_update_over_period_count'] == 1
    assert 'camera2_map_updates' in json.loads(result['missing_reasons'])
    assert 'map_fp_cells' in json.loads(result['missing_reasons'])

    box = [dict(xmin=0, ymin=0, xmax=1, ymax=1)]
    tangent = audit.box_metrics(np.array([0, 5]), np.array([[-2., -.5], [3., -.5]]), box)
    assert tangent['min_truth_clearance_m'] == .5
    assert not tangent['truth_below_radius_entries'] and not tangent['truth_below_radius_s']
    twice = audit.box_metrics(np.array([0, 5, 10]), np.array([[-2., .5], [3., .5], [-2., .5]]), box)
    assert twice['truth_below_radius_entries'] == 2 and math.isclose(twice['truth_below_radius_s'], 4)
    corner = audit.box_metrics(np.array([0, 10]), np.array([[-1., -1.], [0., 0.]]), box)
    assert math.isclose(corner['truth_below_radius_s'], 5/math.sqrt(2))
    overlap = audit.box_metrics(np.array([0, 5]), np.array([[-2., .5], [3., .5]]),
                                box + [dict(xmin=.5, ymin=0, xmax=1.5, ymax=1)])
    assert overlap['truth_below_radius_entries'] == 1 and math.isclose(overlap['truth_below_radius_s'], 2.5)
    empty = audit.box_metrics(np.array([0]), np.array([[0., 0.]]), [])
    assert empty['truth_footprints'] == empty['truth_below_radius_entries'] == 0
    assert empty['min_truth_clearance_m'] is None

    args = [str(raw), str(raw), '--conditions', str(map_file), '--out', str(root/'output')]
    audit.main(args)
    assert len(audit.read_csv(root/'output/runs.csv')[1]) == 1
    definitions = (root/'output/definitions_ja.md').read_text()
    assert all(f'`{field}`' in definitions for field in audit.SCHEMA)
    with redirect_stderr(StringIO()):
        try:
            audit.main(args)
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError('existing output was accepted')
    with (raw/'safety_events.csv').open('a') as stream:
        stream.write('4,unsafe_tilt_repeat,{}\n')
    repeated = audit.evaluate_run(raw, '042')
    assert repeated['ev_unsafe_tilt_repeat'] == 1 and repeated['outcome'] == 'unsafe_tilt_repeat'
    assert repeated['board_outcome'] == 'other_error'
    (raw.parents[2]/'exit.txt').touch()
    (raw/'trajectory_part001.csv.gz').rename(raw/'trajectory_part002.csv.gz')
    bad = audit.evaluate_run(raw, '042')
    assert 'missing CSV part' in json.loads(bad['missing_reasons'])['deviation_max_m']
    assert bad['n_plans'] == 1
    assert 'exit.txt' in json.loads(bad['missing_reasons'])['exit_code']
    print('synthetic: geometry, revision boundaries, stops, timing, gzip, omissions and overwrite protection passed')


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        synthetic(root)
        archive_030(root/'030')
        archive_035(root/'035')
        archive_037(root/'037')
    print('all common evaluation tests passed')


if __name__ == '__main__':
    main()
