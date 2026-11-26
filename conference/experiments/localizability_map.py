"""Measure how uniquely a visible LAS height patch matches its reference map."""

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from functools import lru_cache
from itertools import combinations, product
from pathlib import Path

import numpy as np

from tapp.config import RESOLUTION, Robot
from tapp.real_beach import fill_nodata, list_patches, load_patch
from tapp.sensor_geometry import REAL_MOUNTS
from tapp.traversability import slope_deg
from tapp.visibility import _rays

DATASET = 'shizuoka_beach_las'
RADII = (20., 40.)
SPACING_M = 5.
SIGMA_M = .05
AMBIGUOUS_OFFSET_M = 1.
TRANSLATION_CELLS = range(-6, 7)  # 0.5 m per cell
YAW_DEGREES = range(-10, 11, 2)
AXES = ('tangent', 'normal', 'yaw')
SENSOR_HEIGHT_M = REAL_MOUNTS['lidar'].xyz[2]
ORIGIN = (0, 0, 0)


def axis_trial(axis, value):
    return tuple(value if i == axis else 0 for i in range(3))


AXIS_TRIALS = tuple(tuple(axis_trial(i, v) for v in grid)
                    for i, grid in enumerate((TRANSLATION_CELLS, TRANSLATION_CELLS, YAW_DEGREES)))
MIXED_AXES = tuple(combinations(range(3), 2))
STEPS = (1, 1, 2)


def mixed_trials(a, b):
    return [tuple(x+y for x, y in zip(axis_trial(a, sa*STEPS[a]), axis_trial(b, sb*STEPS[b])))
            for sa, sb in product((-1, 1), repeat=2)]


MIXED_TRIALS = {axes: mixed_trials(*axes) for axes in MIXED_AXES}
TRIALS = tuple(dict.fromkeys(trial for group in (*AXIS_TRIALS, *MIXED_TRIALS.values()) for trial in group))
TRIAL_INDEX = {trial: i for i, trial in enumerate(TRIALS)}
CLASSIFIED = ('determined', 'tangent_only', 'ambiguous', 'insufficient')


@lru_cache(maxsize=4)
def ray_geometry(radius_m, stride):
    """Pack the existing supercover rays in near-to-far order for early occlusion exits."""
    targets, middle, owners, fractions = _rays(radius_m/RESOLUTION)
    order = np.lexsort((fractions, owners))
    owners = owners[order]
    counts = np.bincount(owners, minlength=len(targets))
    starts = counts.cumsum()-counts
    positions = np.arange(len(owners))-starts[owners]
    shape = (len(targets), int(counts.max()))
    steps = np.zeros(shape, np.int32)
    t = np.full(shape, -1.)
    steps[owners, positions] = middle[order, 0]*stride+middle[order, 1]
    t[owners, positions] = fractions[order]
    return targets, counts, steps, t


def visible_land(filled, land, cell, radius_m):
    """The land subset of visibility.visible_cells, using its exact ray geometry."""
    nx, ny = filled.shape
    offsets, counts, steps, fraction = ray_geometry(radius_m, ny)
    targets = offsets+cell
    active = np.flatnonzero(((0 <= targets) & (targets < (nx, ny))).all(axis=1))
    active = active[land[tuple(targets[active].T)]]
    origin = cell[0]*ny+cell[1]
    flat = filled.ravel()
    sensor_z = flat[origin]+SENSOR_HEIGHT_M
    rise = np.zeros(len(offsets))
    rise[active] = filled[tuple(targets[active].T)]-sensor_z
    # Rays between cell centres inside the rectangular grid never leave it.
    # Padded entries point at the source and are masked from the comparison.
    for start in range(0, steps.shape[1], 12):
        has_blockers = counts[active] > start
        selected = active[has_blockers]
        if not len(selected):
            break
        part = slice(start, start+12)
        t = fraction[selected, part]
        candidate = flat[origin+steps[selected, part]]
        occluded = ((t >= 0.) & (candidate >= sensor_z+t*rise[selected, None])).any(axis=1)
        has_blockers[has_blockers] = occluded
        active = active[~has_blockers]
    return active


@lru_cache(maxsize=4)
def rotated_offsets(radius_m, stride):
    offsets = ray_geometry(radius_m, stride)[0]
    tables = {}
    for degrees in YAW_DEGREES:
        angle = np.deg2rad(degrees)
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        xy = offsets@rotation.T
        # Snap only machine roundoff at integer coordinates.
        xy = np.where(np.abs(xy-np.rint(xy)) < 1e-12, np.rint(xy), xy)
        left = np.floor(xy).astype(int)
        f, g = (xy-left).T
        base = left[:, 0]*stride+left[:, 1]
        weights = np.column_stack(((1-f)*(1-g), (1-f)*g, f*(1-g), f*g))
        tables[degrees] = (base, weights)
    return tables


def centred_mse(delta):
    if len(delta) < 2:
        return np.nan
    centred = delta-delta.mean()
    return float(np.dot(centred, centred)/len(centred))


class HeightMatcher:
    def __init__(self, raw, max_radius=RADII[-1]):
        self.radius = max_radius
        self.land = np.isfinite(raw) & (raw >= 0.)
        self.filled = fill_nodata(raw)
        self.pad = int(np.ceil(max_radius/RESOLUTION))+max(TRANSLATION_CELLS)+2
        self.reference = np.pad(np.where(self.land, raw, np.nan), self.pad, constant_values=np.nan)
        self.stride = self.reference.shape[1]
        self.rotations = rotated_offsets(max_radius, self.stride)
        self.offsets = ray_geometry(max_radius, raw.shape[1])[0]

    def profile(self, cell, indices, radii=RADII, *, source_height_offset_m=0.):
        """Compare one visible excerpt to valid overlapping cells at each displaced pose."""
        if max(radii) > self.radius:
            raise ValueError('comparison radius exceeds visibility radius')
        offsets = self.offsets[indices]
        src = self.filled[tuple((offsets+cell).T)]+source_height_offset_m
        in_radius = [(offsets**2).sum(axis=1) <= (r/RESOLUTION)**2 for r in radii]
        flat = self.reference.ravel()
        origin = (cell[0]+self.pad)*self.stride+cell[1]+self.pad
        rotations = {}
        for yaw, (base, weights) in self.rotations.items():
            rotations[yaw] = base[indices], weights[indices]
        costs = np.empty((len(radii), len(TRIALS)))
        counts = np.zeros(costs.shape, np.uint16)
        for j, (along, seaward, yaw) in enumerate(TRIALS):
            base, weights = rotations[yaw]
            sample = origin+along*self.stride-seaward+base
            if yaw:
                nearby = flat[sample[:, None]+[0, 1, self.stride, self.stride+1]]
                target = (np.where(weights == 0., 0., nearby)*weights).sum(axis=1)
            else:
                target = flat[sample]
            delta = target-src
            paired = np.isfinite(delta)
            for i, inside in enumerate(in_radius):
                selected = delta[paired & inside]
                counts[i, j] = len(selected)
                costs[i, j] = centred_mse(selected)
        return costs, counts


def assess(costs, radius):
    def cost(trial):
        return costs[TRIAL_INDEX[trial]]

    base = cost(ORIGIN)
    steps = (RESOLUTION, RESOLUTION, radius*np.deg2rad(STEPS[2]))
    hessian = np.full((3, 3), np.nan)
    for axis, (raw_step, step) in enumerate(zip(STEPS, steps)):
        hessian[axis, axis] = (cost(axis_trial(axis, raw_step))+cost(axis_trial(axis, -raw_step))-2*base)/step**2
    for (a, b), trials in MIXED_TRIALS.items():
        mm, mp, pm, pp = map(cost, trials)
        hessian[a, b] = hessian[b, a] = (pp-pm-mp+mm)/(4*steps[a]*steps[b])
    eigenvalues = direction = np.full(3, np.nan)
    weak_axis = 'unavailable'
    if np.isfinite(hessian).all():
        eigenvalues, eigenvectors = np.linalg.eigh(hessian)
        if np.isclose(eigenvalues[0], eigenvalues[1], atol=1e-12, rtol=1e-8):
            weak_axis = 'tied'
        else:
            direction = eigenvectors[:, 0]
            axis = np.argmax(np.abs(direction))
            direction = direction*np.sign(direction[axis])
            weak_axis = AXES[axis]
    states = []
    for i, trials in enumerate(AXIS_TRIALS):
        scale = RESOLUTION if i < 2 else radius*np.pi/180
        far = np.array([cost(trial) for trial in trials if abs(trial[i])*scale >= AMBIGUOUS_OFFSET_M])
        if np.isfinite(base) and (far < base+SIGMA_M**2).any():
            states.append('ambiguous')
        elif np.isfinite(base) and np.isfinite(far).all():
            states.append('determined')
        else:
            states.append('insufficient')
    if states == ['ambiguous', 'determined', 'determined']:
        category = 'tangent_only'
    elif 'ambiguous' in states:
        category = 'ambiguous'
    elif 'insufficient' in states:
        category = 'insufficient'
    else:
        category = 'determined'
    return category, states, hessian, eigenvalues, direction, weak_axis


def sample_positions(filled, land):
    step = round(SPACING_M/RESOLUTION)
    eligible = land & (slope_deg(filled) <= Robot().max_slope_deg)
    return np.argwhere(eligible[::step, ::step])*step


def coordinates(cells):
    # The LAS generator floors (u+100)/res and (v+50)/res; data are cell centres.
    return (cells+.5)*RESOLUTION+[-100., -50.]


def gap_stats(cells, classes):
    return np.diff(np.unique(cells[classes == 'determined', 0]))*RESOLUTION


def summary(patch, split, radius, classes, gaps):
    counts = {kind: int((classes == kind).sum()) for kind in CLASSIFIED}
    n = len(classes)
    tested = n-counts['insufficient']
    uncertain = counts['tangent_only']+counts['ambiguous']
    return dict(patch=patch, split=split, radius_m=radius, positions=n, tested=tested,
                insufficient=counts['insufficient'], ambiguous=uncertain,
                tangent_only=counts['tangent_only'], determined=counts['determined'],
                ambiguous_pct=100*uncertain/tested if tested else None,
                tangent_only_pct=100*counts['tangent_only']/tested if tested else None,
                gap_n=len(gaps), gap_median_m=float(np.median(gaps)) if len(gaps) else None,
                gap_max_m=float(gaps.max()) if len(gaps) else None)


def plot_map(path, name, raw, coords, classes, states):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    land = np.isfinite(raw) & (raw >= 0.)
    colors = dict(determined='#00786f', tangent_only='#d36607', ambiguous='#963b72', insufficient='#59646b')
    labels = dict(determined='Determined', tangent_only='Alongshore only', ambiguous='Other ambiguity',
                  insufficient='Insufficient overlap')
    lo, hi = np.quantile(raw[land], [.02, .98]) if land.any() else (0., 1.)
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 5.3), sharex=True, sharey=True)
    extent = [-100, 100, -50, 150]
    for i, (ax, radius) in enumerate(zip(axes, RADII)):
        ax.set_facecolor('#e7eaec')
        sea = np.ma.masked_where(~(np.isfinite(raw) & (raw < 0.)), np.ones(raw.shape))
        ax.imshow(sea.T, extent=extent, origin='lower', cmap='Blues', vmin=0., vmax=3.8, interpolation='nearest')
        ax.imshow(np.ma.masked_where(~land, raw).T, extent=extent, origin='lower', cmap='Greys',
                  vmin=lo, vmax=hi if hi > lo else lo+1., interpolation='nearest', alpha=.52)
        for kind, color in colors.items():
            x, y = coords[classes[:, i] == kind].T
            ax.scatter(x, y, s=7, color=color, marker='x' if kind == 'insufficient' else 'o', linewidths=.4)
        for axis, vector in enumerate(([2., 0.], [0., 2.])):
            xy = coords[states[:, i, axis] == 'ambiguous']
            ax.add_collection(LineCollection(np.stack([xy-vector, xy+vector], axis=1),
                                             color='#282935', linewidths=.57, zorder=4))
        xy = coords[states[:, i, 2] == 'ambiguous']
        ax.scatter(*xy.T, s=13, marker='o', edgecolors='#282935', facecolors='none', linewidths=.42, zorder=4)
        ax.set_title(f'R = {radius:.0f} m', fontsize=11, fontweight='semibold', loc='left')
        ax.set_xticks([-100, -50, 0, 50, 100])
        ax.set_yticks([-50, 0, 50, 100, 150])
        ax.tick_params(labelsize=8, length=2)
        ax.set_xlabel('Alongshore (m)', fontsize=9)
    axes[0].set_ylabel('Sea to land (m)', fontsize=9)
    fig.text(.09, .94, name, fontsize=15, fontweight='semibold', color='#212a30')
    handles = [Line2D([], [], label=labels[k], color=c, marker='x' if k == 'insufficient' else 'o',
                      markersize=5, linestyle='none') for k, c in colors.items()]
    handles.extend((Line2D([], [], color='#282935', label='Translation axis', linewidth=1.),
                    Line2D([], [], marker='o', markerfacecolor='none', color='#282935',
                           label='Yaw ambiguity', markersize=5, linestyle='none')))
    fig.legend(handles=handles, loc='lower center', bbox_to_anchor=(.52, .018), fontsize=8,
               frameon=False, ncols=3, columnspacing=1.7)
    fig.subplots_adjust(left=.095, right=.982, top=.875, bottom=.20, wspace=.115)
    fig.savefig(path, dpi=150, facecolor='white')
    plt.close(fig)


def analyze_patch(args):
    entry, output = args
    name = entry['name']
    raw = load_patch(name, dataset=DATASET)
    matcher = HeightMatcher(raw)
    cells = sample_positions(matcher.filled, matcher.land)
    n = len(cells)
    classes = np.empty((n, 2), dtype='U12')
    axes = np.empty((n, 2), dtype='U12')
    states = np.empty((n, 2, 3), dtype='U12')
    costs = np.empty((n, 2, len(TRIALS)))
    overlap = np.empty(costs.shape, dtype=np.uint16)
    hessians = np.empty((n, 2, 3, 3))
    eigenvalues = np.empty((n, 2, 3))
    weak_vectors = np.empty_like(eigenvalues)
    for j, cell in enumerate(cells):
        indices = visible_land(matcher.filled, matcher.land, cell, RADII[-1])
        costs[j], overlap[j] = matcher.profile(cell, indices)
        for i, radius in enumerate(RADII):
            (classes[j, i], states[j, i], hessians[j, i], eigenvalues[j, i],
             weak_vectors[j, i], axes[j, i]) = assess(costs[j, i], radius)
    coords = coordinates(cells)
    np.savez_compressed(output/'points'/f'{name}.npz', cells=cells, coordinates_m=coords, radii_m=RADII,
                        trials_cell_cell_deg=TRIALS, mse_m2=costs, overlap_n=overlap, category=classes,
                        axis_status=states, hessian=hessians, eigenvalues=eigenvalues,
                        weak_vector=weak_vectors, weak_axis=axes)
    plot_map(output/'maps'/f'{name}.png', name, raw, coords, classes, states)
    gaps = [gap_stats(cells, classes[:, i]) for i in range(len(RADII))]
    rows = [summary(name, entry['split'], radius, classes[:, i], gaps[i]) for i, radius in enumerate(RADII)]
    return rows, classes, gaps


def write_csv(path, rows):
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def aggregate(results):
    rows, all_classes, all_gaps = zip(*results)
    by_radius = [summary('all', 'all', radius, np.concatenate([x[:, i] for x in all_classes]),
                         np.concatenate([x[i] for x in all_gaps])) for i, radius in enumerate(RADII)]
    return [row for pair in rows for row in pair], by_radius


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new output directory')
    parser.add_argument('--patch', action='append', help='limit to a named patch (repeatable)')
    parser.add_argument('--workers', type=int, default=1)
    args = parser.parse_args(argv)
    entries = list_patches(dataset=DATASET)
    if args.patch:
        unknown = set(args.patch)-{r['name'] for r in entries}
        if unknown:
            parser.error(f'unknown patches: {", ".join(sorted(unknown))}')
        entries = [r for r in entries if r['name'] in args.patch]
    if args.workers < 1:
        parser.error('workers must be positive')
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out/'points').mkdir()
    (args.out/'maps').mkdir()
    workload = [(entry, args.out) for entry in entries]

    def collect(iterator):
        results = []
        for entry, result in zip(entries, iterator):
            results.append(result)
            print(f"{entry['name']}: {len(result[1])} positions", flush=True)
        return results

    if args.workers == 1:
        results = collect(map(analyze_patch, workload))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            results = collect(pool.map(analyze_patch, workload))
    rows, total = aggregate(results)
    write_csv(args.out/'summary.csv', rows)
    write_csv(args.out/'pooled.csv', total)
    print(f'Patches: {len(entries)}')
    print((args.out/'pooled.csv').read_text(), end='')


if __name__ == '__main__':
    main()
