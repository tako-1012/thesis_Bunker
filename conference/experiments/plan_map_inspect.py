"""Inspect the saved search map active at a box approach or a blocked goal."""

import argparse
import json
from pathlib import Path

import numpy as np

from experiments.eval_runs import discover, read_csv, read_trajectory, write_csv
from ros2_jazzy.gz_checks.plan_maps import read_plans
from tapp.collision import path_lethal_cells
from tapp.config import Robot
from tapp.obstacle_clearance import path_clearance

APPROACH_FIELDS = ('run', 'time', 'x', 'y', 'distance_m', 'box_index', 'plan', 'plan_time', 'handoff_time', 'revision',
                   'path_time_basis',
                   'search_path_distance_m', 'applied_path_distance_m', 'box_detected_cells',
                   'detection_grid_m', 'nearby_halo_cells', 'nearby_blocked_halo_cells', 'path_halo_cells')
GOAL_FIELDS = ('run', 'goal_x', 'goal_y', 'failure_plan', 'failure_time', 'failure_cause',
               'first_blocked_plan', 'first_blocked_time', 'first_blocked_cause', 'blocked_on_first_plan')
SKIP_FIELDS = ('run', 'analysis', 'reason')


def closest_approach(trace, boxes):
    """Minimize planar distance along timestamped, linearly interpolated poses."""
    if not len(boxes):
        raise ValueError('no debris footprint records')
    lower, upper = boxes[:, :2], boxes[:, 2:]
    if not np.isfinite(boxes).all() or (upper <= lower).any():
        raise ValueError('invalid debris footprint bounds')
    best = (float('inf'), float('inf'), -1, None)
    if len(trace) == 1:
        trace = np.repeat(trace, 2, axis=0)
    for start, end in zip(trace[:-1], trace[1:]):
        a, b = start[1:], end[1:]
        delta = b-a
        gap = np.maximum(np.maximum(lower-np.maximum(a, b), np.minimum(a, b)-upper), 0.)
        for j in np.flatnonzero(np.linalg.norm(gap, axis=1) <= best[0]):
            lo, hi = lower[j], upper[j]
            # Closest pair is an endpoint, a rectangle-edge crossing, or
            # the projection of a rectangle corner onto the segment.
            nonzero = delta != 0.
            bounds = [0., 1., *((lo-a)[nonzero]/delta[nonzero]), *((hi-a)[nonzero]/delta[nonzero])]
            if nonzero.any():
                corners = np.array([[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], lo[1]], [hi[0], hi[1]]])
                bounds.extend((corners-a)@delta/(delta@delta))
            u = np.unique(np.clip(bounds, 0., 1.))
            candidates = a+u[:, None]*delta
            distances = np.linalg.norm(np.maximum(np.maximum(lo-candidates, candidates-hi), 0.), axis=1)
            k = np.argmin(distances)
            choice = (float(distances[k]), float(start[0]+u[k]*(end[0]-start[0])), int(j))
            if choice < best[:3]:
                best = (*choice, candidates[k])
    return best


def box_evidence(plan, path_m, box):
    lo, hi = box[:2], box[2:]
    fine = 'fine_obstacle' in plan
    resolution = float(plan['resolution_m'])
    cell_m = float(plan['fine_resolution_m']) if fine else resolution
    origin = plan['fine_origin_xy'] if fine else -cell_m/2
    detected = plan['fine_obstacle'] if fine else plan['detected']
    xy = np.argwhere(detected)*cell_m+origin
    overlaps = (xy < hi).all(axis=1) & (xy+cell_m > lo).all(axis=1)
    # Geographic subset of the recorded obstacle halo, including cells
    # whose closed squares intersect the box's robot-radius neighbourhood.
    x, y = np.ogrid[:plan['lethal'].shape[0], :plan['lethal'].shape[1]]
    dx = np.maximum(np.maximum(lo[0]-(x+.5)*resolution, (x-.5)*resolution-hi[0]), 0.)
    dy = np.maximum(np.maximum(lo[1]-(y+.5)*resolution, (y-.5)*resolution-hi[1]), 0.)
    nearby = plan['obstacle_halo'] & (dx*dx+dy*dy <= Robot().footprint_radius**2)
    blocked = nearby & plan['lethal']
    return dict(box_detected_cells=int(overlaps.sum()), detection_grid_m=cell_m,
                nearby_halo_cells=int(nearby.sum()), nearby_blocked_halo_cells=int(blocked.sum()),
                path_halo_cells=len(path_lethal_cells(path_m/resolution, blocked)))


def causes(plan, goal):
    if 'retained_lethal' in plan and plan['retained_lethal'][goal]:
        return 'retained_planner_observation'
    names = []
    for raw, halo, name in [('detected', 'obstacle_halo', 'detected_obstacle'),
                            ('prior_raw', 'prior_inflated', 'prior_obstacle'),
                            ('steep', 'steep_halo', 'steep')]:
        if plan[raw][goal]:
            names.append(name)
        elif plan[halo][goal]:
            names.append(name+'_inflation')
    return '+'.join(names) or 'unknown'


def active_handoff(raw, applications, time):
    _, revisions = read_csv(raw/'path_revisions.csv')
    if revisions:
        observed = max((item for item in enumerate(revisions) if float(item[1]['t']) <= time),
                       key=lambda item: (float(item[1]['t']), item[0]), default=None)
        if observed is None:
            return None, 'follower_revision'
        row = observed[1]
        path = np.asarray(json.loads(row['path']), float)
        return next((a for a in reversed(applications) if not a['failed']
                     and float(a['sim_time']) <= float(row['t'])
                     and np.array_equal(a['path_m'], path)), None), 'follower_revision'
    return next((a for a in reversed(applications) if not a['failed'] and float(a['sim_time']) <= time),
                None), 'planner_handoff'


def inspect(raw, approaches, failures, skipped):
    def skip(analysis, reason):
        skipped.append(dict(run=str(raw), analysis=analysis, reason=reason))
        print(f'{raw} [{analysis}] skipped: {reason}')

    folder = raw/'plan_maps'
    if not any(folder.glob('plan_*.npz')):
        skip('approach and goal_cell', 'no saved search maps; cannot inspect box detection or first goal block')
        return
    marker = folder/'incomplete.json'
    cutoff = float(json.loads(marker.read_text())['from_sim_time']) if marker.is_file() else float('inf')
    applications = []
    for path in folder.glob('applied_*.npz'):
        with np.load(path, allow_pickle=False) as data:
            applications.append({key: data[key] for key in data.files})
    applications.sort(key=lambda row: (float(row['sim_time']), int(row['plan_id'])))
    mission_file = raw/'mission.json'
    status = json.loads(mission_file.read_text()).get('status') if mission_file.is_file() else None
    terminal = applications[-1] if applications and applications[-1]['failed'] and status in (None, 'no_path') else None
    if status == 'no_path' and terminal is None:
        skip('goal_cell', 'no terminal search application recorded')
    failure_id = int(terminal['plan_id']) if terminal is not None else None

    approach = active = boxes = path_time_basis = None
    try:
        trace, _, _ = read_trajectory(raw)
        _, rows = read_csv(raw/'debris_footprints.csv')
        boxes = np.asarray([[float(r[k]) for k in ('xmin', 'ymin', 'xmax', 'ymax')] for r in rows]).reshape(-1, 4)
        approach = closest_approach(trace, boxes)
        if approach[1] >= cutoff:
            skip('approach', 'approach is after plan recording became incomplete')
        else:
            active, path_time_basis = active_handoff(raw, applications, approach[1])
            if active is None:
                skip('approach', 'no saved search for the path at closest approach')
    except (OSError, ValueError, KeyError) as error:
        skip('approach', str(error))
    selected = int(active['plan_id']) if active is not None else None
    if selected is None and failure_id is None:
        return

    goal = None
    if failure_id is not None:
        file = folder/f'plan_{failure_id:06d}.npz'
        if file.is_file():
            with np.load(file, allow_pickle=False) as data:
                if str(data['failure_class']) == 'goal_cell':
                    goal = tuple(data['goal'])
        else:
            skip('goal_cell', 'terminal search map is missing')

    selected_plan = failed = first_block = None
    last_needed = max(selected or 0, failure_id if goal is not None else 0)
    for index, plan in read_plans(folder):
        if index == selected:
            selected_plan = plan
        if goal is not None and first_block is None and plan['lethal'][goal]:
            first_block = (index, float(plan['sim_time']), causes(plan, goal))
        if index == failure_id and goal is not None:
            failed = plan
        if index >= last_needed:
            break
    if selected_plan is not None:
        distance, t, box_index, xy = approach
        box = boxes[box_index]
        bounds = box[None, :2], box[None, 2:]
        approaches.append(dict(run=str(raw), time=t, x=xy[0], y=xy[1], distance_m=distance, box_index=box_index,
                               plan=selected, plan_time=float(selected_plan['sim_time']),
                               handoff_time=float(active['sim_time']), revision=int(active['revision']),
                               path_time_basis=path_time_basis,
                               search_path_distance_m=path_clearance(selected_plan['path_cells']*selected_plan['resolution_m'], *bounds),
                               applied_path_distance_m=path_clearance(active['path_m'], *bounds),
                               **box_evidence(selected_plan, active['path_m'], box)))
    elif selected is not None:
        skip('approach', 'applied search map is missing')
    if failed is not None and first_block is not None:
        index, stamp, cause = first_block
        failures.append(dict(run=str(raw), goal_x=goal[0], goal_y=goal[1], failure_plan=failure_id,
                             failure_time=float(failed['sim_time']), failure_cause=causes(failed, goal),
                             first_blocked_plan=index, first_blocked_time=stamp,
                             first_blocked_cause=cause, blocked_on_first_plan=(index == 1)))
    elif goal is not None:
        skip('goal_cell', 'reported failed goal is absent from the saved lethal masks')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if not args.runs.is_dir():
        parser.error('runs directory does not exist')
    args.out.mkdir(parents=True, exist_ok=False)
    approaches, failures, skipped = [], [], []
    for raw in ([args.runs] if (args.runs/'plan_maps').is_dir() else discover(args.runs)):
        try:
            inspect(raw, approaches, failures, skipped)
        except (OSError, ValueError, KeyError, IndexError) as error:
            skipped.append(dict(run=str(raw), analysis='saved maps', reason=str(error)))
            print(f'{raw} [saved maps] skipped: {error}')
    for name, fields, rows in [('approach', APPROACH_FIELDS, approaches), ('goal_cell', GOAL_FIELDS, failures),
                               ('skipped', SKIP_FIELDS, skipped)]:
        write_csv(args.out/(name+'.csv'), fields, rows)
        print(f'{name}: {len(rows)} rows')


if __name__ == '__main__':
    main()
