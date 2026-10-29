#!/usr/bin/env python3
"""Audit unchanged paper paths and compare sampled/exact online collision checks."""
import argparse
import csv
import io
import json
import os
import sys
import time
from contextlib import redirect_stdout
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tapp.collision import path_lethal_cells
from tapp.config import DEFAULT_W
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.scenario import build, run_planner
from tapp.terrain import TERRAIN_TYPES

OUT = Path(__file__).resolve().parent.parent / 'results' / 'exact_los'
CONDITIONS = ((15, 5), (10, 10), (10, 20), (5, 10), (5, 20))
KEY = ['kind', 'side_m', 'seed']
FIELDS = ['length_xy', 'length_3d', 'energy_kj', 'mean_cost', 'steep_len', 'rock_hit', 'p95_slope']


def paper(args):
    kind, size, seed = args
    sc = build(kind, size, seed)
    rows = []
    for name in ('TA*', 'TA*-S'):
        r = run_planner(name, sc, w=DEFAULT_W)
        row = dict(kind=kind, side_m=size, seed=seed, planner=name, success=r['success'], plan_time=r['time'])
        if r['success']:
            row.update(evaluate(r['path'], sc['tmap']))
            row['lethal_cells'] = len(path_lethal_cells(r['path'], sc['tmap'].lethal))
        rows.append(row)
    return rows


def online(args):
    kind, size, seed, radius, cell = args
    sc = build(kind, size, seed)
    tm = sc['tmap']
    pm = coarse_prior(tm, cell)
    oracle = run_planner('TA*-S', sc, w=DEFAULT_W)
    ref = evaluate(oracle['path'], tm)
    jo = ref['length_xy'] * (1 + DEFAULT_W * ref['mean_cost'])
    rows = []
    for exact in (False, True):
        r = run_online(tm, sc['start'], sc['goal'], planner='TA*-S', w=DEFAULT_W,
                       prior_map=pm, prior_lethal='soft', sense_radius_m=radius, exact_los=exact)
        # Partial failed trajectories are audited too; dJ only describes complete runs.
        m = evaluate(r['traj'], tm)
        row = dict(kind=kind, side_m=size, seed=seed, R_m=radius, cell_m=cell, exact_los=exact,
                   success=r['success'], reason=r['reason'], n_plans=r['n_plans'], plan_time=r['plan_time'],
                   lethal_cells=len(path_lethal_cells(r['traj'], tm.lethal)), **m)
        if r['success']:
            row['dJ'] = 100 * (m['length_xy'] * (1 + DEFAULT_W * m['mean_cost']) / jo - 1)
        rows.append(row)
    return rows


def run_pool(worker, tasks, workers, filename):
    rows = []
    tasks.sort(key=lambda t: -t[1])
    start = time.perf_counter()
    with Pool(workers) as pool:
        for i, rs in enumerate(pool.imap_unordered(worker, tasks), 1):
            rows.extend(rs)
            if i % 10 == 0:
                print(f'{filename}: {i}/{len(tasks)} ({time.perf_counter()-start:.0f}s)', flush=True)
    rows.sort(key=lambda r: (r['kind'], r['side_m'], r['seed'], r.get('R_m', 0),
                             r.get('cell_m', 0), r.get('planner', ''), r.get('exact_los', False)))
    with open(OUT / filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def mismatches(new, old, keys, fields=FIELDS):
    joined = new.set_index(keys).join(old.set_index(keys)[fields + ['success']], rsuffix='_saved', validate='one_to_one')
    mismatch = joined.success != joined.success_saved
    for field in fields:
        if field == 'rock_hit':
            mismatch |= joined[field] != joined[field + '_saved']
        else:
            mismatch |= ~np.isclose(joined[field], joined[field + '_saved'], rtol=0, atol=1e-9, equal_nan=True)
    return joined[mismatch].reset_index()


def summary():
    a, b = pd.read_csv(OUT/'paper_audit.csv'), pd.read_csv(OUT/'online.csv')
    saved = pd.read_csv(OUT.parent/'test_results.csv')
    saved = saved[(saved.exp=='main') & saved.planner.isin(['TA*','TA*-S'])]
    ma = mismatches(a, saved, KEY+['planner'])
    old = pd.read_csv(OUT.parent/'risk_prior/risk_prior.csv')
    old = old[old.variant=='coarse']
    mb = mismatches(b[~b.exact_los], old, KEY+['R_m','cell_m'], FIELDS + ['n_plans'])
    # Counts are row-level: touching a cell is distinct from sampled exposure.
    for frame in (a,b):
        frame['touch'] = frame.lethal_cells > 0
        frame['sampled_exposure'] = (frame.steep_len > 0) | frame.rock_hit
    report = io.StringIO()
    with redirect_stdout(report):
        print('A: unchanged paper planners')
        print(a.groupby('planner').agg(paths=('success','size'),success=('success','mean'),
              touching_paths=('touch','sum'),sampled_exposure=('sampled_exposure','sum')).to_string())
        print(f'\nA: saved-result mismatches (absolute tolerance 1e-9; timing excluded): {len(ma)}')
        if len(ma): print(ma[KEY+['planner']].to_string(index=False))
        print('\nB: online replanning')
        print(b.groupby(['R_m','cell_m','exact_los']).agg(success=('success','mean'),
              touching_runs=('touch','sum'),sampled_exposure=('sampled_exposure','sum'),
              dJ_median=('dJ','median'),dJ90=('dJ',lambda x:x.quantile(.9)),
              plans=('n_plans','median'),plan_time=('plan_time','median')).round(6).to_string())
        print(f'\nB: saved coarse mismatches (absolute tolerance 1e-9; timing excluded): {len(mb)}')
        if len(mb): print(mb[KEY+['R_m','cell_m']].to_string(index=False))
        print('\nB: trajectories touching lethal cells:')
        touched=b[b.touch]
        print(touched[['R_m','cell_m']+KEY+['exact_los','lethal_cells']].to_string(index=False))
        failures=b[~b.success]
        print('\nfailures:',failures.groupby(['exact_los','reason']).size().to_dict())
        if len(failures): print(failures[['R_m','cell_m']+KEY+['exact_los','reason']].to_string(index=False))
    value=report.getvalue()
    print(value,end='',flush=True)
    (OUT/'exact_los_log.txt').write_text(value)
    ma.to_csv(OUT/'paper_mismatches.csv',index=False)
    mb.to_csv(OUT/'online_mismatches.csv',index=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--summary-only',action='store_true')
    parser.add_argument('--workers',type=int,default=os.cpu_count() or 1)
    args=parser.parse_args()
    if args.workers<1: parser.error('--workers must be positive')
    OUT.mkdir(parents=True,exist_ok=True)
    start=time.perf_counter()
    if not args.summary_only:
        run_pool(paper,[(k,s,sd) for k in TERRAIN_TYPES for s in (50,100,200) for sd in range(10)],args.workers,'paper_audit.csv')
        run_pool(online,[(k,s,sd,r,c) for k in TERRAIN_TYPES for s in (50,100) for sd in range(10)
                        for r,c in CONDITIONS],args.workers,'online.csv')
    summary()
    if not args.summary_only:
        runtime=dict(total_s=time.perf_counter()-start,workers=args.workers,python=sys.version.split()[0])
        (OUT/'runtime.json').write_text(json.dumps(runtime,indent=2)+'\n')
        print('runtime:',json.dumps(runtime),flush=True)


if __name__=='__main__': main()
