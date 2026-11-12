"""Task031: frozen lab costs vs task013, neutral metrics first, beach-level tests."""
import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from multiprocessing import Pool
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tapp.lab_geometry import plan_lab
from tapp.real_beach import build_real, list_patches
from tapp.scenario import run_planner
from tapp.exact_planners import run_planner_exact
from tapp.metrics import evaluate, resample
from tapp.collision import path_lethal_cells
from tapp.config import DEFAULT_W, RESOLUTION
from experiments.abstract_figure import choose
from experiments.analyze import paired_test, holm

OFFLINE = ROOT/'results/real_beach_las/offline.csv'
METHODS = ['A*', 'TA*-S exact', 'lab_geometry', 'lab_geometry+0.35m']
NEUTRAL = ['steep_len', 'max_slope', 'p95_slope', 'max_roll', 'p95_roll',
           'max_pitch_dir', 'p95_pitch_dir', 'max_pitch', 'obstacle_cells', 'length_xy', 'climb']
OWN = ['mean_cost', 'J']
METRICS = NEUTRAL+OWN+['time']
CHECK = ['length_xy', 'length_3d', 'climb', 'max_slope', 'p95_slope', 'max_pitch', 'max_roll',
         'p95_roll', 'roll_frac', 'max_pitch_dir', 'pitch_frac', 'mean_cost', 'mean_rough',
         'p95_rough', 'steep_len', 'steep_frac', 'rock_hit', 'J', 'lethal_cells']


def path_metrics(path, sc):
    tm = sc['tmap']
    values = evaluate(path, tm)
    values.pop('energy_kj')  # Never collect or aggregate energy.
    x, y = resample(path)
    xi = np.clip(np.rint(x[:-1]).astype(int), 0, tm.shape[0]-1)
    yi = np.clip(np.rint(y[:-1]).astype(int), 0, tm.shape[1]-1)
    dx, dy = np.diff(x), np.diff(y)
    length = np.maximum(np.hypot(dx, dy), 1e-12)
    pitch = np.degrees(np.arctan(np.abs(tm.gx[xi, yi]*dx/length+tm.gy[xi, yi]*dy/length)))
    raw = sc['terrain']['rock'] | sc['water'] | sc['nodata']
    values.update(p95_pitch_dir=float(np.percentile(pitch, 95)),
                  obstacle_cells=len(path_lethal_cells(path, raw)),
                  lethal_cells=len(path_lethal_cells(path, tm.lethal)),
                  J=values['length_xy']*(1+DEFAULT_W*values['mean_cost']))
    return values


def compare_reference(rows, reference):
    audit = []
    for row in rows:
        if row['planner'] not in METHODS[:2]:
            continue
        ref = reference[(reference.kind == row['kind']) & (reference.side_m == row['side_m']) &
                        (reference.debris == row['debris']) & (reference.planner == row['planner'])]
        if len(ref) != 1:
            raise ValueError('reference missing/duplicate scenario')
        ref = ref.iloc[0]
        assert bool(row['success']) == bool(ref.success)
        for key in ('used_seed', 'redraws'):
            assert row[key] == ref[key]
        assert json.loads(row['crop_origin']) == json.loads(ref.crop_origin)
        if not row['success']:
            continue
        for metric in CHECK:
            a, b = float(row[metric]), float(ref[metric])
            ok = bool(np.isclose(a, b, rtol=1e-9, atol=1e-9))
            audit.append(dict(kind=row['kind'], side_m=row['side_m'], debris=row['debris'],
                              planner=row['planner'], metric=metric, actual=a, reference=b,
                              absolute_difference=abs(a-b), matched=ok))
            if not ok:
                raise AssertionError(('task013 parity', row['kind'], row['side_m'], row['debris'], row['planner'], metric, a, b))
    return audit


def run_case(job):
    name, side, debris, selected = job
    sc = build_real(name, side, 0, debris=debris, dataset='shizuoka_beach_las')
    raw = sc['terrain']['rock'] | sc['water'] | sc['nodata']
    base = dict(kind=name, side_m=side, seed=0, debris=debris, used_seed=sc['used_seed'],
                redraws=sc['redraws'], crop_origin=json.dumps(sc['crop_origin_cells']),
                start=list(sc['start']), goal=list(sc['goal']))
    rows, paths = [], {}
    for method in METHODS:
        if method == 'A*':
            result = run_planner('A*', sc)
        elif method == 'TA*-S exact':
            result = run_planner_exact('TA*-S', sc)
        else:
            result = plan_lab(sc['tmap'].elev, raw, sc['start'], sc['goal'], RESOLUTION,
                              .35 if method.endswith('+0.35m') else 0.)
        row = dict(base, planner=method, success=bool(result['success']), time=result['time'],
                   reason='' if result['success'] else 'no_path')
        if result['success']:
            row.update(path_metrics(result['path'], sc))
            if name in selected and side == 200 and not debris:
                paths[method] = np.asarray(result['path']).tolist()
        rows.append(row)
    reference = pd.read_csv(OFFLINE, float_precision='round_trip')
    audit = compare_reference(rows, reference)
    return dict(key=f'{name}:{side}:{debris}', rows=rows, audit=audit, paths=paths)


def summarize(data):
    summary, tests = [], []
    for (debris, method), group in data.groupby(['debris', 'planner'], sort=False):
        good = group[group.success]
        row = dict(debris=debris, planner=method, scheduled=len(group), solved=len(good))
        row.update({m: good[m].median() for m in METRICS})
        row.update(contact_runs=int((good.obstacle_cells > 0).sum()), steep_runs=int((good.steep_len > 0).sum()))
        summary.append(row)
    # Both sizes must succeed for BOTH methods before averaging within beach.
    # Holm is one predeclared family: three contrasts x two debris states x all metrics.
    for debris in (False, True):
        for method in (METHODS[0], *METHODS[2:]):
            group = data[(data.debris == debris) & data.planner.isin([method, METHODS[1]])]
            pivot = group.pivot(index=['kind', 'side_m'], columns='planner', values='success')
            valid = pivot.all(axis=1).unstack('side_m').all(axis=1)
            selected = group[group.kind.isin(valid[valid].index) & group.success]
            means = selected.groupby(['kind', 'planner'])[METRICS].mean()
            for metric in METRICS:
                pair = means[metric].unstack('planner').dropna()
                if len(pair):
                    p, effect, delta = paired_test(pair[method], pair[METHODS[1]])
                else:
                    p = effect = delta = np.nan
                tests.append(dict(debris=debris, method=method, reference=METHODS[1], metric=metric,
                                  n_beaches=len(pair), excluded_beaches=48-len(pair),
                                  method_mean_size_median=pair[method].median() if len(pair) else np.nan,
                                  reference_mean_size_median=pair[METHODS[1]].median() if len(pair) else np.nan,
                                  delta_median=delta, p=p, rank_biserial=effect))
    tests = pd.DataFrame(tests)
    finite = tests.p.notna()
    tests.loc[finite, 'p_holm'] = holm(tests.loc[finite, 'p'].to_numpy())
    return pd.DataFrame(summary)[['debris', 'planner', 'scheduled', 'solved', *NEUTRAL,
                                 'contact_runs', 'steep_runs', *OWN, 'time']], tests


def figures(results, selected, output):
    for rule, name in selected.items():
        case = next(r for r in results if r['key'] == f'{name}:200:False')
        sc = build_real(name, 200, 0, dataset='shizuoka_beach_las')
        fig, ax = plt.subplots(figsize=(8, 7))
        ax.imshow(sc['tmap'].slope.T, origin='lower', extent=[-.25, 199.75, -.25, 199.75], cmap='YlOrBr', vmin=0, vmax=25)
        raw = sc['terrain']['rock'] | sc['water'] | sc['nodata']
        ax.contour(raw.T, levels=[.5], colors='black', linewidths=.5, extent=[0, 199.5, 0, 199.5])
        for method, style in zip(METHODS, ['--', '-', '-.', ':']):
            if method in case['paths']:
                pts = np.asarray(case['paths'][method])*RESOLUTION
                ax.plot(pts[:, 0], pts[:, 1], style, label=method, lw=1.5)
        for point, marker in ((sc['start'], 'o'), (sc['goal'], '*')):
            ax.scatter(point[0]*RESOLUTION, point[1]*RESOLUTION, marker=marker, c='black')
        ax.set(title=rule+' (predefined): '+name, xlabel='x [m]', ylabel='y [m]', aspect='equal')
        ax.legend(); fig.tight_layout()
        for extension in ('png', 'pdf'):
            fig.savefig(output/(rule+'.'+extension), dpi=180)
        plt.close(fig)
    (output/'figure_selection.json').write_text(json.dumps(selected, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'results/lab_baseline')
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    out = args.output; out.mkdir(parents=True, exist_ok=True)
    checkpoint = out/'checkpoint.json'
    source = hashlib.sha256(Path(__file__).read_bytes()+(ROOT/'tapp/lab_geometry.py').read_bytes()+OFFLINE.read_bytes()).hexdigest()
    done = {}
    if checkpoint.exists():
        if not args.resume: raise FileExistsError('use a fresh output or --resume')
        previous = json.loads(checkpoint.read_text()); assert previous['source'] == source
        done = previous['results']
    selected, _ = choose(pd.read_csv(OFFLINE))
    names = [r['name'] for r in list_patches('test', dataset='shizuoka_beach_las')]
    jobs = [(name, side, debris, list(selected.values())) for name in names for side in (100, 200) for debris in (False, True)]
    todo = [j for j in jobs if f'{j[0]}:{j[1]}:{j[2]}' not in done]
    began = time.perf_counter()
    with Pool(args.workers) as pool:
        for result in pool.imap_unordered(run_case, todo):
            done[result['key']] = result
            checkpoint.write_text(json.dumps(dict(source=source, results=done))+'\n')
            print('completed', len(done), '/', len(jobs), flush=True)
    results = [done[f'{j[0]}:{j[1]}:{j[2]}'] for j in jobs]
    data = pd.DataFrame([row for r in results for row in r['rows']])
    data.to_csv(out/'runs.csv', index=False)
    pd.DataFrame([a for r in results for a in r['audit']]).to_csv(out/'parity.csv', index=False)
    table, tests = summarize(data)
    table.to_csv(out/'summary.csv', index=False); tests.to_csv(out/'tests.csv', index=False)
    figures(results, selected, out)
    log = io.StringIO()
    with redirect_stdout(log):
        print('Task031: neutral metrics first; paired unit is beach, sizes averaged; no energy.')
        print('mean_cost and J use OUR terrain objective and favour our method; not neutral metrics.')
        print(table.to_string(index=False))
        print('\nTwo-sided Wilcoxon, one Holm family over all predefined contrasts/metrics/debris states:')
        print(tests.to_string(index=False))
        print('A*/TA*-S path metrics match task013 at rtol=atol=1e-9. Runtime is remeasured, not matched.')
        print('Figure selection:', selected)
    (out/'lab_baseline_log.txt').write_text(log.getvalue()); print(log.getvalue(), end='')
    (out/'runtime.json').write_text(json.dumps(dict(wall_s=time.perf_counter()-began, workers=args.workers,
        python=sys.version, executable=sys.executable, prefix=sys.prefix, numpy=np.__version__, resumed=args.resume), indent=2)+'\n')

if __name__ == '__main__': main()
