"""Predict task078 scan-to-map observability from the task075 reference geometry."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
from functools import lru_cache
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import numpy as np

from experiments.localizability_rays import LandmarkSurfaces, RayScanner, TerrainMesh
from experiments.offline_localization import (
    MIN_INFORMATION, NORMAL_NEIGHBORS, MapRegistration, load_backends, MissingLocalizationPackages,
)
from ros2_jazzy.gz_checks import lidar_checks
from ros2_jazzy.gz_checks.online_batch_runtime import planning_map
from tapp.config import RESOLUTION
from tapp.landmark_world import landmark_mask, landmark_points, place_landmarks, terrain_points, with_landmarks
from tapp.online_mission import run_fixed_mission

PATCHES = ('08OB88_-1417', '08OB86_-0205')
DENSITIES = (0, 10, 40, 160)
SEEDS = (0, 1, 2)
GRID_M, PATH_M = 5., 1.
EIGEN_COLUMNS = ('minimum_scaled_eigenvalue',
                 *(f'{kind}_eig{i}' for kind in ('translation', 'rotation') for i in range(1, 4)))
DIRECTION_COLUMNS = ('weak_rx', 'weak_ry', 'weak_rz', 'weak_tx', 'weak_ty', 'weak_tz')
SAMPLE_COLUMNS = ('patch', 'density_per_ha', 'seed', 'x_m', 'y_m', 'model_z_m', 'scan_points',
                  'gicp_source_voxels', 'inliers', 'converged', 'status', *EIGEN_COLUMNS,
                  'weak_axis', *DIRECTION_COLUMNS, 'at_or_below_1')


def prepare_manifest(patch, density, seed):
    """Use the exact task078 CLI preparation path without importing ROS."""
    with TemporaryDirectory(prefix='task079-prepare-') as output:
        env = dict(os.environ, THESIS_FINE_PROTOCOL='rtf_check', THESIS_ONLY_PATCH=patch,
                   THESIS_STALE_TIMEOUT_S='1.0', THESIS_RENDER='gpu')
        subprocess.run(
            [sys.executable, '-m', 'ros2_jazzy.gz_checks.lidar_checks', '--prepare-only', '--output', output,
             '--patch-count', '3', '--map', 'fine', '--ground-estimate', 'non_obstacle',
             '--online-fixes', 'v2', '--sensors', 'lidar_real+depth2', '--diagnostics',
             '--terrain-source', 'prior', '--obstacle-clearance', 'distance', '--save-plan-maps',
             '--pose-trace', '--real-time-factor', '1.0', '--landmarks', str(density),
             '--landmark-seed', str(seed), '--record-sensors', '--record-sensors-seconds', '120'],
            cwd=lidar_checks.ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
        return json.loads((Path(output)/'manifest.json').read_text())


def selected_scenario(manifest):
    (index,) = (i for i, case in enumerate(manifest['cases']) if case['selected'])
    return manifest['cases'][index].copy(), manifest['scenarios'][index]


def placement(truth, case, scenario, manifest):
    settings = manifest['landmark_world']
    return place_landmarks(truth, case['patch'], settings['density_per_ha'], settings['seed'],
                           [scenario['start'], *scenario['points'], *scenario['stops']])


def initial_path(prior, scenario, objects, footprint):
    if not objects:
        return scenario['initial_path']
    updated = with_landmarks(prior, footprint)
    result = run_fixed_mission(planning_map(updated, 'TA*-S+inflate'), scenario['start'], scenario['stops'])
    return (np.asarray(result['traj'])*RESOLUTION).tolist() if result['success'] else []


def sample_path(path):
    """Sample horizontal arc length, keeping the exact final endpoint."""
    points = np.asarray(path, dtype=float)
    distances = np.r_[0., np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    keep = np.r_[True, np.diff(distances) > 0.]
    distances, points = distances[keep], points[keep]
    metres = np.r_[np.arange(0., distances[-1], PATH_M), distances[-1]]
    return metres, np.column_stack([np.interp(metres, distances, xy) for xy in points.T])


def measurement_noise(patch, xy, shape):
    # Same rays and radial errors at a location across all 078 conditions.
    x, y = (0. if v == 0. else float(v) for v in xy)
    digest = hashlib.sha256(f'079:{patch}:{x.hex()}:{y.hex()}'.encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:16], 'big')).standard_normal(shape)


def evaluate_scan(matcher, scan, pose):
    xyz = scan.reshape(-1, 3)
    xyz = xyz[np.isfinite(xyz).all(axis=1)]
    source = matcher.preprocess(xyz)[0] if len(xyz) >= NORMAL_NEIGHBORS else None
    _, result = matcher.match(source, pose, gated=True)
    info = result['information'] if result['inliers'] >= NORMAL_NEIGHBORS else None
    row = dict(scan_points=len(xyz), gicp_source_voxels=len(source) if source is not None else 0,
               inliers=result['inliers'], converged=int(result['converged']), status=result['status'])
    if info is not None:
        row.update(zip(EIGEN_COLUMNS, (info.weakest, *info.translation, *info.rotation)))
        row.update(zip(DIRECTION_COLUMNS, info.weak_direction_world))
        row.update(weak_axis=info.weak_axis, at_or_below_1=int(info.weakest <= MIN_INFORMATION))
    return row


def distribution(rows):
    good = [row for row in rows if 'at_or_below_1' in row]
    count = sum(row['at_or_below_1'] for row in good)
    result = dict(samples=len(rows), with_information=len(good), unavailable=len(rows)-len(good),
                  not_converged=sum(not r['converged'] for r in rows), at_or_below_1=count,
                  fraction_at_or_below_1=count/len(good) if good else None)
    for key in EIGEN_COLUMNS:
        p10, median = np.percentile([r[key] for r in good], [10, 50]) if good else (None, None)
        result.update({f'{key}_p10': p10, f'{key}_median': median})
    return result


def path_lengths(rows):
    if not rows:
        return dict(path_m=None, weak_m=None, weak_fraction=None, max_weak_m=None,
                    unavailable_m=None, not_converged_m=None)
    weak = current = longest = unavailable = not_converged = 0.
    for row, following in zip(rows, rows[1:]):
        delta = following['distance_m']-row['distance_m']
        flag = row.get('at_or_below_1')
        current = current+delta if flag == 1 else 0.
        longest = max(longest, current)
        weak += delta*(flag == 1)
        unavailable += delta*(flag is None)
        not_converged += delta*(not row['converged'])
    length = rows[-1]['distance_m']
    known = length-unavailable
    return dict(path_m=length, weak_m=weak, weak_fraction=weak/known if known > 0 else None,
                max_weak_m=longest, unavailable_m=unavailable, not_converged_m=not_converged)


def recorded_index(roots):
    """Find candidate task078 manifests by patch, density and commanded seed."""
    index = {}
    for root in roots:
        paths = sorted(root.rglob('manifest.json')) if root.is_dir() else [root]
        for path in paths:
            manifest = json.loads(path.read_text())
            settings = manifest.get('landmark_world', {})
            if not {'density_per_ha', 'seed'} <= settings.keys():
                continue
            for case in manifest.get('cases', []):
                if case.get('selected') and case['patch'] in PATCHES:
                    key = case['patch'], settings['density_per_ha'], settings['seed']
                    index.setdefault(key, []).append((path, case))
    return index


def compare_recorded(candidates, objects, path, digest):
    """Keep unverifiable cases distinct from either matches or disagreements."""
    checked = []
    for manifest_file, case in candidates:
        folder = manifest_file.parent/case['run_folder'] if case.get('run_folder') else None
        mission_file = folder/'mission.json' if folder is not None else None
        item = dict(manifest=str(manifest_file))
        item['placement'] = ('unavailable' if 'landmarks' not in case else
                             'match' if case['landmarks'] == objects else 'mismatch')
        if 'initial planning failed on landmark prior' in case.get('error', ''):
            item['path'] = 'match' if not path else 'mismatch'
        elif mission_file is not None and mission_file.is_file():
            mission = json.loads(mission_file.read_text())
            item['path'] = 'match' if mission.get('path') == path else 'mismatch'
        else:
            item['path'] = 'unavailable'
        ref = folder/'reference_cloud.npz' if folder is not None else None
        item['reference'] = 'unavailable'
        if ref is not None and ref.is_file():
            with np.load(ref, allow_pickle=False) as data:
                actual = hashlib.sha256(np.ascontiguousarray(data['xyz'])).hexdigest()
            item['reference'] = 'match' if actual == digest else 'mismatch'
        checked.append(item)
    return checked


def comparison_status(comparisons, field):
    kinds = {r[field] for r in comparisons}
    return 'mismatch' if 'mismatch' in kinds else 'match' if 'match' in kinds else 'unavailable'


def csv_output(path, columns, rows):
    with path.open('x', newline='') as out:
        writer = csv.DictWriter(out, columns, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({key: format(val, '.10g') if isinstance(val, (float, np.floating)) else val
                             for key, val in row.items()})


def run_patch(patch, output, recordings):
    _, _, backend = load_backends()
    first = prepare_manifest(patch, 0, 0)
    case, meta = selected_scenario(first)
    truth, prior = lidar_checks.case_world_inputs(case, meta, first)
    elevation = truth['tmap'].elev
    mesh = TerrainMesh(elevation)
    scanner = RayScanner(mesh, lidar_checks.LidarSpec(**first['lidar_spec']))
    terrain = terrain_points(elevation)
    step = round(GRID_M/RESOLUTION)

    @lru_cache(maxsize=1600)
    def ground_at(x, y):
        pose = scanner.pose(x, y)
        return pose, scanner.ground_ranges(pose[:3, 3])

    grid_rows, path_rows, summaries, descriptions = [], [], [], []
    zero = None
    for density in DENSITIES:
        for seed in SEEDS:
            prepared = first if (density, seed) == (0, 0) else prepare_manifest(patch, density, seed)
            case, scenario = selected_scenario(prepared)
            area, objects = placement(truth, case, scenario, prepared)
            footprint = landmark_mask(elevation.shape, objects)
            path = initial_path(prior, scenario, objects, footprint)
            key = dict(patch=patch, density_per_ha=density, seed=seed)

            if not density and zero is not None:
                grid, route, digest = zero
            else:
                reference = (np.concatenate([terrain, *(landmark_points(obj).astype(np.float32) for obj in objects)])
                             if objects else terrain)
                digest = hashlib.sha256(reference).hexdigest()
                matcher = MapRegistration(reference, backend)
                surfaces = LandmarkSurfaces(objects)
                free = ~with_landmarks(truth, footprint)['tmap'].lethal if objects else ~truth['tmap'].lethal
                points = np.argwhere(free[::step, ::step])*GRID_M

                def at(xy):
                    pose, ground = ground_at(*xy)
                    normals = measurement_noise(patch, xy, scanner.slopes.shape)
                    scan = scanner.scan(pose[:3, 3], surfaces, normals, ground=ground)
                    return dict(x_m=xy[0], y_m=xy[1], model_z_m=mesh.height(*xy),
                                **evaluate_scan(matcher, scan, pose))

                grid = [at(xy) for xy in points]
                route = []
                if path:
                    distances, points = sample_path(path)
                    route = [dict(distance_m=s, **at(xy)) for s, xy in zip(distances, points)]
                if not density:
                    zero = grid, route, digest
                del matcher, reference

            objects_data = [asdict(item) for item in objects]
            comparisons = compare_recorded(recordings.get((patch, density, seed), []), objects_data, path, digest)
            descriptions.append(dict(**key, land_area_m2=area, landmark_count=len(objects),
                                     landmarks=objects_data, reference_xyz_sha256=digest,
                                     path=path, comparisons_078=comparisons,
                                     archived_world_elevation=first['world_input']))
            grid_rows.extend(dict(**key, **r) for r in grid)
            path_rows.extend(dict(**key, **r) for r in route)
            sums = dict(**key, landmark_count=len(objects), **distribution(grid))
            summaries.append(dict(**sums, path_status='planned' if path else 'no_path',
                                  **path_lengths(route), route_samples=len(route),
                                  placement_078=comparison_status(comparisons, 'placement'),
                                  path_078=comparison_status(comparisons, 'path'),
                                  reference_078=comparison_status(comparisons, 'reference')))
            print(f'{patch} {density:3d}/ha seed={seed} objects={len(objects):3d} '
                  f'grid={len(grid):3d} path={len(route):3d} complete', flush=True)

    csv_output(output/f'grid_{patch}.csv', SAMPLE_COLUMNS, grid_rows)
    csv_output(output/f'route_{patch}.csv', (*SAMPLE_COLUMNS, 'distance_m'), path_rows)
    return summaries, descriptions, grid_rows, path_rows


def grouped(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row['patch'], row['density_per_ha']), []).append(row)
    return groups


def plots(output, patches, grid_rows, path_rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.colors import SymLogNorm

    grids = grouped([r for r in grid_rows if r['seed'] == 0])
    routes = grouped(path_rows)
    maximum = max((r[EIGEN_COLUMNS[0]] for r in grid_rows if EIGEN_COLUMNS[0] in r), default=MIN_INFORMATION)
    norm = SymLogNorm(linthresh=MIN_INFORMATION, vmin=0., vmax=max(maximum, MIN_INFORMATION))
    fig, axes = plt.subplots(len(patches), len(DENSITIES), squeeze=False, figsize=(13, 3.5*len(patches)),
                             sharex=True, sharey=True, layout='constrained')
    for patch, row in zip(patches, axes):
        for density, ax in zip(DENSITIES, row):
            samples = grids.get((patch, density), [])
            drawn = [s for s in samples if 'at_or_below_1' in s]
            coords = np.array([(s['x_m'], s['y_m']) for s in drawn]).reshape(-1, 2)
            dot = ax.scatter(*coords.T, c=[s[EIGEN_COLUMNS[0]] for s in drawn], s=9, norm=norm, cmap='viridis')
            weak = [s for s in drawn if s['at_or_below_1']]
            ax.scatter([s['x_m'] for s in weak], [s['y_m'] for s in weak], marker='s',
                       facecolors='none', edgecolors='#c6402b', linewidths=.5, s=20)
            half_vectors = 2.*np.array([(s['weak_tx'], s['weak_ty']) for s in drawn]).reshape(-1, 2)
            ax.add_collection(LineCollection(np.stack((coords-half_vectors, coords+half_vectors), axis=1),
                                             colors='#152135', linewidths=.45, alpha=.7))
            ax.set(title=f'{patch} · {density}/ha', aspect='equal', xlim=(-5, 205), ylim=(-5, 205))
            ax.set_xlabel('Alongshore x (m)')
        row[0].set_ylabel('Cross-shore y (m)')
    ticks = [value for value in (0., .5, 1., 2., 5., 10., 20., 50.) if value <= norm.vmax]
    fig.colorbar(dot, ax=axes, label='Minimum scaled eigenvalue', shrink=.8, ticks=ticks, format='%g')
    fig.suptitle('Seed 0 · red square: ≤ 1 · line: horizontal projection of weakest mode')
    fig.savefig(output/'map_seed0.png', dpi=175)
    plt.close(fig)

    fig, axes = plt.subplots(len(patches), len(DENSITIES), squeeze=False, figsize=(13, 2.85*len(patches)),
                             sharey=True, layout='constrained')
    for patch, row in zip(patches, axes):
        for density, ax in zip(DENSITIES, row):
            series = routes.get((patch, density), [])
            for seed, color in zip(SEEDS, ('#253b68', '#cd6a35', '#319486')):
                track = [s for s in series if s['seed'] == seed]
                if track:
                    ax.plot([s['distance_m'] for s in track],
                            [s.get(EIGEN_COLUMNS[0], np.nan) for s in track], lw=.8, label=f'Seed {seed}', color=color)
            ax.axhline(MIN_INFORMATION, ls='--', lw=.7, color='#585f6c')
            ax.set(title=f'{patch} · {density}/ha', xlabel='Initial path distance (m)')
            ax.grid(alpha=.2)
        row[0].set_ylabel('Minimum scaled eigenvalue')
    axes[0, -1].legend(loc='upper right', frameon=False, fontsize=8)
    fig.savefig(output/'routes.png', dpi=175)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--manifest-root', type=Path, action='append', default=[],
                        help='078 metadata directory tree or individual manifest.json (repeatable)')
    parser.add_argument('--jobs', type=int, choices=(1, 2), default=1)
    parser.add_argument('--patch', choices=PATCHES, action='append', help='default: all 078 beaches')
    args = parser.parse_args(argv)
    patches = list(dict.fromkeys(args.patch or PATCHES))
    try:
        load_backends()
    except MissingLocalizationPackages as exc:
        parser.exit(2, f'{exc}\n')
    recordings = recorded_index(args.manifest_root)
    args.out.mkdir(parents=True, exist_ok=False)
    arguments = [(patch, args.out, recordings) for patch in patches]
    if args.jobs == 1:
        results = [run_patch(*arg) for arg in arguments]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futures = [pool.submit(run_patch, *arg) for arg in arguments]
            results = [future.result() for future in futures]
    summary, descriptions, grid, route = [[r for data in results for r in data[i]] for i in range(4)]
    csv_output(args.out/'summary_by_seed.csv', summary[0].keys(), summary)
    by_density = [dict(patch=patch, density_per_ha=density, **distribution(rows))
                  for (patch, density), rows in grouped(grid).items()]
    csv_output(args.out/'summary_by_density.csv', by_density[0].keys(), by_density)
    (args.out/'worlds.json').write_text(json.dumps(dict(
        config=dict(grid_m=GRID_M, path_m=PATH_M, min_information=MIN_INFORMATION,
                    packages={n: version(n) for n in ('numpy', 'scipy', 'small_gicp', 'kiss-icp', 'matplotlib')}),
        worlds=descriptions), indent=2)+'\n')
    plots(args.out, patches, grid, route)
    print('patch density n fraction_le_1 lambda_p10 lambda_median')
    for row in by_density:
        display = [row[k] for k in ('patch', 'density_per_ha', 'with_information', 'fraction_at_or_below_1',
                                   'minimum_scaled_eigenvalue_p10', 'minimum_scaled_eigenvalue_median')]
        print(*['-' if v is None else f'{v:.6g}' if isinstance(v, (float, np.floating)) else v for v in display])
    if not args.manifest_root:
        print('078 actual manifests: unavailable (no --manifest-root supplied)')
    if any('mismatch' in (r['placement_078'], r['path_078'], r['reference_078']) for r in summary):
        parser.exit(1, '078 manifest discrepancies; see worlds.json and summary_by_seed.csv\n')


if __name__ == '__main__':
    main()
