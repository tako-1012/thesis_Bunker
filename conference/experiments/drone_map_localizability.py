"""Compare near-truth LiDAR registration on ODM and coastal LAS terrain (081B)."""

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from importlib.metadata import version
import json
from pathlib import Path
import platform
import warnings

import numpy as np

from experiments.drone_map_rays import RasterTerrain
from experiments.localizability_rays import LandmarkSurfaces, RayScanner
from experiments.localizability_scan import (
    PATCHES, SAMPLE_COLUMNS, csv_output, distribution, evaluate_scan, measurement_noise,
)
from experiments.offline_localization import MIN_INFORMATION, MapRegistration, load_backends
from ros2_jazzy.src.thesis_bunker_gz.thesis_bunker_gz.lidar import LidarSpec
from tapp.landmark_world import TERRAIN_STEP_M
from tapp.real_beach import load_patch

ROOT = Path(__file__).resolve().parents[1]
ODM_DIR = ROOT/'data/drone_odm/2024-04-24'
# 079 uses the lidar_real minimum range and the standard LidarSpec otherwise.
SPEC = LidarSpec(min_range_m=.9)
FINE_M, COARSE_M = .1, .5
STEP_M, PHASE_M = 1., .75
LAS_SIZE_M, CUT_COUNT, CUT_SEED = (38, 43), 5, 0
CONDITIONS = ('a', 'b', 'c')
EDGE_BANDS = ('0-5', '5-10', '10+')
WEAK_AXES = ('alongshore', 'cross_shore', 'vertical', 'rotation')
COLUMNS = ('condition', 'scene', 'patch', 'edge_distance_m', 'edge_band',
           *(name for name in SAMPLE_COLUMNS if name not in ('patch', 'density_per_ha', 'seed')))


@dataclass
class Scene:
    condition: str
    name: str
    patch: str
    elevation: np.ndarray
    spacing: float
    offset: tuple[float, float] = (0., 0.)
    reference: np.ndarray | None = None

    @property
    def size(self):
        return np.asarray(self.elevation.shape)*self.spacing

    def mesh(self):
        return RasterTerrain(self.elevation, self.spacing, origin_xy=(self.spacing/2,)*2)


def median_coarsen(z):
    """Full 5x5 blocks only, leaving blocks with no measurements empty."""
    nx, ny = np.asarray(z.shape)//5
    blocks = z[:5*nx, :5*ny].reshape(nx, 5, ny, 5)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='All-NaN slice encountered', category=RuntimeWarning)
        return np.nanmedian(blocks, axis=(1, 3))


def load_odm(folder):
    with np.load(folder/'elevation_10cm.npz', allow_pickle=False) as data:
        if float(data['cell_size_m']) != FINE_M:
            raise ValueError('expected a 10 cm DSM')
        origin = data['origin_utm_xyz_m']
        elevation = np.where(data['point_count'] > 0, data['z_median'], np.nan).T
    parts = []
    for file in sorted(folder.glob('point_cloud_5cm_*.npz')):
        with np.load(file, allow_pickle=False) as data:
            if not np.array_equal(data['origin_utm_xyz_m'], origin):
                raise ValueError(f'point cloud has a different origin: {file}')
            parts.append(data['xyz'])
    return elevation, np.concatenate(parts)


def select_crops(z, shape, *, count=CUT_COUNT, seed=CUT_SEED):
    """Choose land-only windows, without replacement among their lower-left cells."""
    nx, ny = shape
    missing = ~np.isfinite(z) | (z < 0.)
    prefix = np.pad(missing, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    counts = prefix[nx:, ny:]-prefix[:-nx, ny:]-prefix[nx:, :-ny]+prefix[:-nx, :-ny]
    candidates = np.argwhere(counts == 0)
    return candidates[np.random.default_rng(seed).choice(len(candidates), count, replace=False)]


def scenes():
    z, reference = load_odm(ODM_DIR)
    yield Scene('a', 'a', 'Kyutech', z, FINE_M, reference=reference)
    yield Scene('b', 'b', 'Kyutech', median_coarsen(z), COARSE_M)
    nx, ny = (round(side/COARSE_M) for side in LAS_SIZE_M)
    for patch in PATCHES:
        z = load_patch(patch, dataset='shizuoka_beach_las')
        for number, (i, j) in enumerate(select_crops(z, (nx, ny)), 1):
            yield Scene('c', f'c_{patch}_{number}', patch, z[i:i+nx, j:j+ny].copy(),
                        COARSE_M, (float(i*COARSE_M), float(j*COARSE_M)))


def terrain_reference(mesh):
    step = TERRAIN_STEP_M
    x, y = np.meshgrid(*(o+np.arange(round(length/step)+1)*step
                         for o, length in zip(mesh.origin_xy, mesh.bounds)), indexing='ij')
    z = mesh.height(x, y)
    valid = np.isfinite(z)
    return np.column_stack((x[valid], y[valid], z[valid]))


def scan_sites(mesh, size):
    # 0.75 + k metres are vertex locations at both 0.1 and 0.5 m spacing.
    for x in np.arange(PHASE_M, size[0], STEP_M):
        for y in np.arange(PHASE_M, size[1], STEP_M):
            z = float(mesh.height(x, y))
            if np.isfinite(z):
                edge = min(x, y, size[0]-x, size[1]-y)
                yield x, y, z, edge, EDGE_BANDS[int(edge >= 5.)+int(edge >= 10.)]


def evaluate_scene(scene, output):
    _, _, backend = load_backends()
    mesh = scene.mesh()
    scanner = RayScanner(mesh, SPEC)
    reference = scene.reference if scene.reference is not None else terrain_reference(mesh)
    matcher = MapRegistration(reference, backend)
    landmarks = LandmarkSurfaces([])
    rows = []
    for x, y, z, edge, band in scan_sites(mesh, scene.size):
        pose = scanner.pose(x, y)
        noise = measurement_noise(scene.patch, (x+scene.offset[0], y+scene.offset[1]), scanner.slopes.shape)
        scan = scanner.scan(pose[:3, 3], landmarks, noise)
        row = dict(condition=scene.condition, scene=scene.name, patch=scene.patch,
                   x_m=x, y_m=y, model_z_m=z, edge_distance_m=edge, edge_band=band)
        row.update(evaluate_scan(matcher, scan, pose))
        rows.append(row)
    csv_output(output/f'points_{scene.name}.csv', COLUMNS, rows)
    print(f'{scene.name}: {len(rows)} samples, {len(reference)} reference points', flush=True)
    metadata = dict(condition=scene.condition, scene=scene.name, patch=scene.patch,
                    shape_xy=scene.elevation.shape, size_xy_m=scene.size.tolist(),
                    offset_xy_m=scene.offset, spacing_m=scene.spacing, reference_points=len(reference),
                    missing_cells=int(np.count_nonzero(~np.isfinite(scene.elevation))))
    return rows, metadata


def summaries(results):
    rows = [row for samples, _ in results for row in samples]
    a_sites = {(r['x_m'], r['y_m']) for r in rows if r['condition'] == 'a'}
    b_sites = {(r['x_m'], r['y_m']) for r in rows if r['condition'] == 'b'}
    common = a_sites & b_sites
    groups = []
    for subset in ('all', 'paired_sites'):
        for condition in CONDITIONS if subset == 'all' else ('a', 'b'):
            same = [r for r in rows if r['condition'] == condition
                    and (subset == 'all' or (r['x_m'], r['y_m']) in common)]
            for band in ('all', *EDGE_BANDS):
                groups.append((subset, condition, band, same))
    for patch in PATCHES:
        same = [r for r in rows if r['patch'] == patch]
        for band in ('all', *EDGE_BANDS):
            groups.append((patch, 'c', band, same))
    for samples, meta in results:
        if meta['condition'] == 'c':
            groups.append((meta['scene'], 'c', 'all', samples))

    for subset, condition, band, source in groups:
        selected = [r for r in source if band == 'all' or r['edge_band'] == band]
        weak = Counter(r['weak_axis'] for r in selected if 'weak_axis' in r)
        yield dict(subset=subset, condition=condition, edge_band=band, **distribution(selected),
                   **{f'weak_{axis}': weak[axis] for axis in WEAK_AXES})


def plot_fine(scene, rows, output):
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    values = 'minimum_scaled_eigenvalue'
    available = [r for r in rows if values in r]
    unavailable = [r for r in rows if values not in r]
    fig, ax = plt.subplots(figsize=(6.5, 6), layout='constrained')
    width, height = scene.size
    ax.imshow(np.isfinite(scene.elevation.T), extent=(0, width, 0, height), origin='lower',
              interpolation='nearest', cmap='gray', vmin=0, vmax=1, alpha=.24)
    norm = LogNorm(vmin=.01, vmax=max(MIN_INFORMATION*2, max(r[values] for r in available)))
    scatter = ax.scatter([r['x_m'] for r in available], [r['y_m'] for r in available],
                         c=[r[values] for r in available], cmap='viridis', norm=norm, s=11)
    if unavailable:
        ax.scatter([r['x_m'] for r in unavailable], [r['y_m'] for r in unavailable],
                   c='red', s=10, marker='x', label='Information unavailable')
        ax.legend(loc='upper left')
    colorbar = fig.colorbar(scatter, ax=ax, label='Minimum scaled eigenvalue', extend='min')
    colorbar.ax.axhline(MIN_INFORMATION, color='black', lw=1)
    ax.set(xlabel='Local east (m)', ylabel='Local north (m)', aspect='equal', xlim=(0, width), ylim=(0, height),
           title='Kyutech · 10 cm DSM / 5 cm reference cloud')
    fig.savefig(output/'kyutech_10cm.png', dpi=180)
    plt.close(fig)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error('--workers must be positive')
    args.out.mkdir(parents=True, exist_ok=False)
    jobs = list(scenes())
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(evaluate_scene, scene, args.out) for scene in jobs]
        results = [future.result() for future in futures]
    summary = list(summaries(results))
    csv_output(args.out/'summary.csv', tuple(summary[0]), summary)
    plot_fine(jobs[0], results[0][0], args.out)
    metadata = dict(python=platform.python_version(),
                    packages={name: version(name) for name in ('numpy', 'scipy', 'matplotlib', 'kiss-icp', 'small_gicp')},
                    lidar=asdict(SPEC), minimum_information=MIN_INFORMATION, lidar_pose='079 (level, +x)',
                    sample_step_m=STEP_M, sample_phase_xy_m=(PHASE_M, PHASE_M), las_crop_seed=CUT_SEED,
                    edge_bands_m=(0., 5., 10.), scenes=[meta for _, meta in results])
    (args.out/'metadata.json').write_text(json.dumps(metadata, indent=2)+'\n')
    metric = 'minimum_scaled_eigenvalue'
    print('subset condition edge   n   with_info  not_converged   <=1      %     p10     median    weak x/y/z/rot')
    for row in summary:
        pct = 100*row['fraction_at_or_below_1'] if row['fraction_at_or_below_1'] is not None else float('nan')
        p10 = row[f'{metric}_p10'] if row[f'{metric}_p10'] is not None else float('nan')
        median = row[f'{metric}_median'] if row[f'{metric}_median'] is not None else float('nan')
        weak = '/'.join(str(row[f'weak_{axis}']) for axis in WEAK_AXES)
        print(f"{row['subset']:22} {row['condition']} {row['edge_band']:5} {row['samples']:6d} "
              f"{row['with_information']:6d} {row['not_converged']:6d} {row['at_or_below_1']:6d} "
              f'{pct:6.2f} {p10:7.4f} {median:7.4f}   {weak}')


if __name__ == '__main__':
    main()
