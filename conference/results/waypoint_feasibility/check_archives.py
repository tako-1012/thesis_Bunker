"""Check the two archived waypoint cohorts and compare recorded goal_cell failures."""

import argparse
from collections import Counter
import csv
from functools import lru_cache
import json
from pathlib import Path
import re

import numpy as np

from ros2_jazzy.gz_checks.online_batch_runtime import map_signature, planning_map
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import classify_failure, load_snapshot
from tapp.real_beach import build_real
from tapp.traversability import inflate, slope_deg
from tapp.waypoint_feasibility import check_waypoints

RESULTS = Path('results')


def read_csv(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


@lru_cache
def prior_for(patch):
    return build_real(patch, 200, 0, dataset='shizuoka_beach_las')


def cohort(path, name):
    manifest = json.loads(path.read_text())
    rows = []
    for meta in manifest['scenarios']:
        patch = meta['patch']
        prior = prior_for(patch)
        assert map_signature(prior) == meta['prior_signature'], patch
        tm = planning_map(prior, manifest['planner'])
        checked = check_waypoints(tm.lethal, tm.cost,
                                  np.asarray(meta['start'])*RESOLUTION, np.asarray(meta['points'])*RESOLUTION)
        for point in checked['points']:
            cell = tuple(point['cell'])
            rows.append(dict(cohort=name, patch=patch, waypoint_index=point['index'],
                             visit_number=meta['order'].index(point['index']),
                             cell_x=cell[0], cell_y=cell[1], status=point['status'], reason=point['reason'],
                             replacement_cell=point['replacement_cell'], shift_m=point['shift_m'],
                             prior_slope_deg=tm.slope[cell]))
    return rows


def old_failure_rows():
    root = RESULTS/'eval_ground_endpoint'
    diagnoses = {}
    for row in read_csv(root/'plan_fail_causes.csv'):
        diagnoses.setdefault((row['patch'], row['run']), []).append(row)
    for row in read_csv(root/'runs.csv'):
        if row['status'] != 'no_path' or not int(row['fail_goal_cell']):
            continue
        key = row['patch'], f"{row['condition']}_r{row['rep']}"
        failure = max(diagnoses[key], key=lambda d: float(d['sim_time']))
        assert failure['failure_class'] == 'goal_cell', key
        goal = tuple(map(int, failure['goal_cell'].split(',')))
        yield '030', row, goal, failure['goal_by_steep_infl'] == 'True', 'plan_fail_causes.csv', root

    root = RESULTS/'eval_035'
    for row in read_csv(root/'runs.csv'):
        if row['status'] != 'no_path' or not float(row['fail_goal_cell']):
            continue
        patch, condition, rep = (row[key] for key in ('patch', 'condition', 'rep'))
        diag = root/'runs'/patch/f'{condition}_r{rep}'/'physical_1'/'raw'/patch/'diag'
        snapshot = max(diag.glob('plan_fail_*.npz'))
        data = load_snapshot(snapshot)
        assert classify_failure(data) == 'goal_cell'
        goal = tuple(map(int, data['goal']))
        steep = inflate(data['steep'], Robot().footprint_radius)
        yield '035', row, goal, bool(steep[goal]), snapshot.name, root

    root = RESULTS/'real_sensors_compare'
    evidence = {(r['patch'], r['condition'], r['rep']): r for r in read_csv(root/'failure_evidence.csv')}
    for row in read_csv(root/'runs.csv'):
        if row['status'] != 'no_path' or not int(row['fail_goal_cell']):
            continue
        key = tuple(row[name] for name in ('patch', 'condition', 'rep'))
        failure = evidence[key]
        assert failure['goal_map_lethal'] == 'True'
        goal = tuple(map(int, re.findall(r'np\.int64\((\d+)\)', failure['goal'])))
        assert len(goal) == 2
        yield '037', row, goal, failure['goal_inflated_steep'] == 'True', 'failure_evidence.csv', root

    root = RESULTS/'rtf_compare'/'stage_b'
    # Coordinates of each terminal goal_cell are explicitly recorded in REPORT_B_ja.md.
    goals = {'08OB88_-0167': (137, 294), '08OB89_-0847': (281, 117)}
    for row in read_csv(root/'common_eval'/'runs.csv'):
        if row['status'] == 'no_path' and row['no_path_type'] == 'goal_cell':
            yield '039', row, goals[row['patch']], True, 'REPORT_B_ja.md and common_eval/runs.csv', root


def replay_failures(cohort_rows):
    by_goal = {(r['patch'], r['cell_x'], r['cell_y']): r for r in cohort_rows}
    rows = []
    for experiment, run, goal, steep, evidence, root in old_failure_rows():
        patch, condition, rep = (run[key] for key in ('patch', 'condition', 'rep'))
        entry = by_goal[patch, *goal]
        reached = int(float(run['goals_reached']))
        # Cross-check the saved target against the archived visit order.
        assert entry['visit_number'] == reached+1, (experiment, patch, condition, rep, goal)
        raw = root/'runs'/patch/f'{condition}_r{rep}'/'physical_1'/'raw'/patch
        file = raw/'pointcloud_map.npz'
        seen = lethal = replacement_final_lethal = None
        if file.is_file():
            with np.load(file, allow_pickle=False) as data:
                seen, lethal = bool(data['seen'][goal]), bool(data['lethal'][goal])
                if entry['replacement_cell'] is not None:
                    replacement_final_lethal = bool(data['lethal'][tuple(entry['replacement_cell'])])
        rows.append(dict(experiment=experiment, patch=patch, condition=condition, rep=rep,
                         visit_number=entry['visit_number'], goal_x=goal[0], goal_y=goal[1],
                         prior_status=entry['status'], prior_reason=entry['reason'],
                         replacement_cell=entry['replacement_cell'], shift_m=entry['shift_m'],
                         failure_steep_inflated=steep, failure_evidence=evidence,
                         final_map=str(file) if file.is_file() else None,
                         final_goal_seen=seen, final_goal_lethal=lethal,
                         final_replacement_lethal=replacement_final_lethal))
    return rows


def main(output):
    standard = cohort(RESULTS/'gazebo_lidar/physical_10/manifest.json', 'standard')
    edge = cohort(RESULTS/'edge_margin/refresh/manifest.json', '024')
    rows = standard+edge
    failures = replay_failures(standard)
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output/'waypoints.csv', rows)
    write_csv(output/'goal_cell.csv', failures)
    summary = []
    for name in ('standard', '024'):
        for patch in dict.fromkeys(r['patch'] for r in rows):
            group = [r for r in rows if r['cohort'] == name and r['patch'] == patch]
            counts = Counter(r['status'] for r in group)
            summary.append(dict(cohort=name, patch=patch, waypoints=len(group),
                                ok=counts['ok'], blocked_cell=counts['blocked_cell'],
                                unreachable=counts['unreachable'],
                                substituted=sum(r['shift_m'] is not None for r in group),
                                skipped=sum(r['status'] != 'ok' and r['shift_m'] is None for r in group)))
    write_csv(output/'summary.csv', summary)
    for row in summary:
        print(*(f'{k}={v}' for k, v in row.items()))
    for experiment in ('030', '035', '037', '039'):
        subset = [r for r in failures if r['experiment'] == experiment]
        counts = Counter(r['prior_status'] for r in subset)
        print(experiment, 'terminal goal_cell:', len(subset), 'prior:', dict(counts),
              'by steep inflation:', sum(r['failure_steep_inflated'] for r in subset),
              'final goal lethal / available:',
              f"{sum(r['final_goal_lethal'] is True for r in subset)}/{sum(r['final_goal_lethal'] is not None for r in subset)}")
        for key, n in Counter((r['patch'], r['visit_number'], r['goal_x'], r['goal_y']) for r in subset).items():
            print(' ', *key, 'n=', n)
    shifts = [r['shift_m'] for r in rows if r['shift_m'] is not None]
    print('replacement distances (m): n=', len(shifts),
          'min/median/max=', (min(shifts), float(np.median(shifts)), max(shifts)) if shifts else 'unavailable')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
