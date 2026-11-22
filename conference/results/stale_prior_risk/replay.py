"""Measure stale-prior risk from the 047 final maps and their saved first returns."""

import argparse
from collections import defaultdict
import json
from pathlib import Path

import numpy as np

from results.terrain_from_prior import replay as archive
from ros2_jazzy.gz_checks.online_batch_runtime import map_signature
from tapp.collision import line_of_sight_exact
from tapp.config import RESOLUTION
from tapp.endpoint_policy import audit_path, load_snapshot
from tapp.footprint import inflate_steep
from tapp.online_mission import OnlinePlanner
from tapp.planners import astar, smooth_cost_aware
from tapp.pointcloud_map_fine import PointCloudMapFine, TERRAIN_SOURCES, veto_steep
from tapp.prior_variants import PRIOR_VARIANTS, prior_variant
from tapp.real_beach import build_real
from tapp.traversability import TraversabilityMap, inflate, slope_deg

ROOT = archive.ROOT
COUNT_FIELDS = ('miss_steep', 'miss_halo', 'false_steep', 'false_halo')


def terrain_metrics(blocked, steep, truth, truth_steep, seen, radius):
    halo = inflate(steep, radius)
    truth_halo = inflate(truth_steep, radius)
    masks = dict(miss_steep=truth_steep & ~blocked, miss_halo=truth_halo & ~blocked,
                 false_steep=steep & blocked & ~truth.lethal,
                 false_halo=halo & blocked & ~(truth.lethal | truth_halo))
    return {key: int(mask.sum()) for key, mask in masks.items()} | {
        'seen_'+key: int((mask & seen).sum()) for key, mask in masks.items()}


def measure(prior, observation, steep, *, seen, truth, truth_steep, start, goal):
    planner = OnlinePlanner(prior.cost, inflate_steep(prior), prior.weights, prior_lethal_mode='soft')
    planner.observe(*observation)
    blocked, mult = planner.planning_maps()
    result = terrain_metrics(blocked, steep, truth, truth_steep, seen, prior.robot.footprint_radius)
    status = 'goal_blocked' if blocked[goal] else 'no_path'
    length = halo_length = None
    if not blocked[goal]:
        planned = astar(blocked, start, goal, mult)
        if planned['success']:
            path, _ = smooth_cost_aware(planned['path'], blocked, mult, los=line_of_sight_exact)
            path_m = np.asarray(path)*RESOLUTION
            length = audit_path(path_m, truth_steep)['relaxed_length_m']
            halo_length = audit_path(path_m, inflate(truth_steep, prior.robot.footprint_radius))['relaxed_length_m']
            status = 'route'
    return dict(result, start_blocked=bool(blocked[start]), route_status=status,
                path_true_steep_m=length, path_true_halo_m=halo_length)


def final_observation(prior, seen, saved, obstacle_halo, template, variant, mode):
    robot = prior.robot
    if mode == 'sensor':
        # The archived run fused against the exact prior. Under another prior
        # restore that variant in the cells never measured by the sensor.
        elev = np.where(seen, saved['elev'], prior.elev)
        steep = slope_deg(elev) > robot.max_slope_deg
        cost = saved['cost'] if variant == 'exact' else TraversabilityMap(
            elev, template.raw_obstacle, robot, prior.weights).cost
    else:
        cost, steep = prior.cost, prior.steep
        if mode == 'prior_veto':
            combined_elev = np.where(seen, saved['elev'], prior.elev)
            steep = veto_steep(steep, combined_elev, template._veto_supported, robot.max_slope_deg)
    halo = inflate(steep, robot.footprint_radius)
    known = seen if mode == 'sensor' else seen | halo
    return (known, cost, prior.rock | obstacle_halo | halo), steep


def evaluate(row):
    patch = row['patch']
    final = ROOT/row['archive_map']
    raw = final.parent
    physical = raw.parents[1]
    reference, archived_prior, truth = archive.load_reference(physical, patch)
    if ROOT/row['reference'] != reference:
        raise ValueError('047 reference does not match the recorded world')
    scenario = build_real(patch, 200, 0, dataset='shizuoka_beach_las')
    if map_signature(scenario) != map_signature(dict(tmap=archived_prior)):
        raise ValueError(f'{patch}: rebuilt prior differs from signed reference')
    manifest = json.loads((physical/'manifest.json').read_text())
    if manifest.get('sensors', 'legacy') != 'legacy' or manifest.get('obstacle_reference_mode', 'prior') != 'prior':
        raise ValueError('these trials use the fine legacy LiDAR')
    terminal = load_snapshot(max((raw/'diag').glob('plan_fail_*.npz')))
    saved, obstacle_halo = archive.reconstruct(PointCloudMapFine(archived_prior.elev, terminal['prior_raw']), terminal, final)
    if int(saved['version']) != int(row['map_version']):
        raise ValueError('047 map version differs')
    with np.load(raw/'first_cloud.npz', allow_pickle=False) as frames:
        points, pose = frames['points'], frames['pose']
    goal = tuple(int(row['goal_'+axis]) for axis in ('x', 'y'))
    failure_start = tuple(int(row['start_'+axis]) for axis in ('x', 'y'))
    initial_start = tuple(json.loads((raw/'mission.json').read_text())['start_cells'])
    truth_steep = slope_deg(truth.elev) > scenario['tmap'].robot.max_slope_deg
    seen_final = saved['seen']
    identity = {key: row[key] for key in ('patch', 'condition', 'rep', 'goal_x', 'goal_y')}
    rows = []
    for variant in PRIOR_VARIANTS:
        base, _ = prior_variant(scenario, variant)
        prior, terrain = base['tmap'], base['terrain']
        raw_obstacle = terrain['rock'] | terrain['water'] | terrain['nodata']
        for mode in TERRAIN_SOURCES:
            mapper = PointCloudMapFine(prior.elev, raw_obstacle, robot=prior.robot, weights=prior.weights,
                                       ground_estimate=manifest.get('ground_estimate', 'all_returns'),
                                       sensor_height_m=manifest['sensor_height_m'],
                                       max_range_m=manifest['lidar_spec']['max_range_m'],
                                       range_resolution_m=manifest['lidar_spec']['range_resolution_m'],
                                       terrain_source=mode)
            mapper.update(points, pose)
            if (mapper.seen & ~seen_final).any():
                raise ValueError(f'{final}: first frame coverage is outside final coverage')
            supported = int(mapper._veto_supported.sum()) if mode == 'prior_veto' else None
            for stage, seen, start in (('final', seen_final, failure_start), ('first_cloud', mapper.seen, initial_start)):
                key = dict(identity, stage=stage, prior_variant=variant, terrain_source=mode, start_x=start[0], start_y=start[1],
                           seen_cells=int(seen.sum()), confirmed_veto_support_cells=supported)
                if stage == 'final':
                    observation, steep = final_observation(prior, seen, saved, obstacle_halo, mapper, variant, mode)
                    if variant == 'exact' and mode == 'sensor' and not np.array_equal(observation[2], saved['lethal']):
                        raise ValueError(f'{final}: reconstruction disagrees with the saved sensor lethal map')
                else:
                    observation, steep = mapper.planning_snapshot(), mapper.tm.steep
                metrics = measure(prior, observation, steep, seen=seen, truth=truth, truth_steep=truth_steep,
                                  start=start, goal=goal)
                if stage == 'final' and variant == 'exact' and mode in ('sensor', 'prior'):
                    if (metrics['route_status'] == 'route') != (row[mode+'_route'] == 'True'):
                        raise ValueError(f'{final}: {mode} reachability disagrees with 047')
                rows.append(dict(key, **metrics))
    return rows


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in ('stage', 'prior_variant', 'terrain_source'))].append(row)
    summary = []
    for (stage, variant, mode), group in groups.items():
        lengths = [r for r in group if r['route_status'] == 'route']
        row = dict(stage=stage, prior_variant=variant, terrain_source=mode, runs=len(group), routes=len(lengths),
                   start_blocked=sum(r['start_blocked'] for r in group))
        for key in (*COUNT_FIELDS, *('seen_'+key for key in COUNT_FIELDS)):
            row[key] = sum(r[key] for r in group)
        for key in ('path_true_steep_m', 'path_true_halo_m'):
            row[key] = round(sum(r[key] for r in lengths), 6) if lengths else None
        summary.append(row)
    return summary


def main(output):
    references = archive.read_csv(ROOT/'results/terrain_from_prior/runs.csv')
    cohort = [row for row in references if row['map_source'] == 'final']
    if len(cohort) != 14:
        raise ValueError('expected 14 final maps from 047')
    rows = [result for row in cohort for result in evaluate(row)]
    summary = summarize(rows)
    output.mkdir(parents=True, exist_ok=True)
    archive.write_csv(output/'runs.csv', rows)
    archive.write_csv(output/'summary.csv', summary)
    print(f'{len(cohort)} runs have both a final map and a first cloud; {len(references)-len(cohort)} others omitted')
    print((output/'summary.csv').read_text(), end='')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    main(parser.parse_args().out)
