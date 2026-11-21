"""Populate opt-in LiDAR scenarios from a prior-only waypoint preflight."""

import numpy as np

from tapp.config import RESOLUTION
from tapp.online_mission import run_fixed_mission
from tapp.prior_variants import prior_variant
from tapp.real_beach import build_real
from tapp.waypoint_feasibility import WAYPOINT_RADIUS_M, check_waypoints
from ros2_jazzy.gz_checks.online_batch_runtime import planning_map


def substitute_waypoints(meta, prior_tm, *, reuse_path=False):
    """Keep surviving visits in archived order and plan the resulting closed tour."""
    checks = check_waypoints(prior_tm.lethal, prior_tm.cost,
                             np.asarray(meta['start'])*RESOLUTION, np.asarray(meta['points'])*RESOLUTION)
    original_indexes = {p['index']: p['cell'] if p['status'] == 'ok' else p['replacement_cell']
                        for p in checks['points']}
    kept = [i for i, cell in original_indexes.items() if cell is not None]
    original_order = meta['order']
    # Case metadata uses 0 for the base. An absent tour has no archived order.
    visit_order = original_order[1:] if original_order else original_indexes
    effective = [original_indexes[i] for i in kept]
    effective_ranks = {i: rank for rank, i in enumerate(kept, 1)}
    visits = [i for i in visit_order if i in effective_ranks]
    order = [0, *(effective_ranks[i] for i in visits)] if visits else []
    stops = [*(original_indexes[i] for i in visits), meta['start']] if visits else []
    status, path, plan_times = 'no_path', [], []
    if checks['start']['status'] != 'ok':
        status = 'blocked_endpoint'
    elif reuse_path and meta['planning_status'] == 'planned' and effective == meta['points'] and stops == meta['stops']:
        status, path, plan_times = 'planned', meta['initial_path'], meta['fixed_plan_times']
    elif stops:
        plan = run_fixed_mission(prior_tm, meta['start'], stops)
        if plan['success']:
            status = 'planned'
            path = (np.asarray(plan['traj'])*RESOLUTION).tolist()
            plan_times = plan['plan_times']

    for point in checks['points']:
        point['effective_index'] = effective_ranks.get(point['index'])
        point['action'] = ('skipped' if point['effective_index'] is None
                           else 'substituted' if point['replacement_cell'] is not None else 'kept')
    checks.update(original_order=original_order, original_planning_status=meta['planning_status'],
                  original_blocked_prior=meta.get('blocked_prior'), original_blocked_truth=meta.get('blocked_truth'))
    # Truth-related endpoint flags belong to the archived goals only.
    result = {key: value for key, value in meta.items() if key not in ('blocked_prior', 'blocked_truth')}
    return dict(result, points=effective, order=order, stops=stops, initial_path=path,
                fixed_plan_times=plan_times, planning_status=status, waypoint_check=checks)


def prepare_waypoints(manifest, variant):
    """Check selected cases before the runtime constructs a world or publishes a goal."""
    manifest.update(waypoint_check='substitute', waypoint_check_radius_m=WAYPOINT_RADIUS_M)
    scenarios = list(manifest['scenarios'])
    for i, (case, meta) in enumerate(zip(manifest['cases'], scenarios)):
        if not case['selected'] or meta['planning_status'] == 'excluded_start':
            continue
        # Both runtime world modes verify the same prior elevation/rock/lethal
        # signatures. Obtain the prior without consulting evaluation terrain.
        prior = build_real(meta['patch'], manifest['side_m'], manifest['seed'], dataset=manifest['dataset'])
        prior, _ = prior_variant(prior, variant)
        tm = planning_map(prior, manifest['planner'])
        scenarios[i] = substitute_waypoints(meta, tm, reuse_path=variant == 'exact')
        case['planning_status'] = scenarios[i]['planning_status']
    manifest['scenarios'] = scenarios
