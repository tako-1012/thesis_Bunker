"""Audit task-014 output identities, call counts and measured incomplete-leg distances."""

from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from tapp.real_beach import list_patches
from tapp.config import RESOLUTION


def main():
    folder=ROOT/'results/online_mission'
    data=pd.read_csv(folder/'missions.csv')
    keys=['patch','prior','radius_m','mode']
    expected={(r['name'],prior,radius,mode) for r in list_patches('test',dataset='shizuoka_beach_las')
              for prior in ['oracle','coarse c10','stale'] for radius in [5,10,15]
              for mode in (['online','fixed'] if prior=='stale' else ['online'])}
    assert not data.duplicated(keys).any() and set(map(tuple,data[keys].to_numpy()))==expected
    calls=pd.concat([pd.read_csv(p) for p in folder.glob('plan_times_*.csv')],ignore_index=True)
    assert not calls.duplicated(keys+['call']).any()
    counts=calls.groupby(keys).size().to_dict()
    for row in data.itertuples():
        assert counts.get((row.patch,row.prior,row.radius_m,row.mode),0)==row.n_plans
    for relative,wanted in json.loads((folder/'experiment_source_sha256.json').read_text()).items():
        assert hashlib.sha256((ROOT.parent/relative).read_bytes()).hexdigest()==wanted
    failed=[]
    for row in data[~data.success].itertuples():
        detail=json.loads((folder/'traces'/(row.patch+'.json')).read_text())
        key=row.prior.replace(' ','_')+f'_R{row.radius_m}_{row.mode}'
        leg=detail[key+'_legs'][-1]
        with np.load(folder/'traces'/(row.patch+'.npz'),allow_pickle=False) as arrays:
            points=arrays[key][leg['start_index']:leg['end_index']+1]
        travelled=float(np.linalg.norm(np.diff(points,axis=0),axis=1).sum()*RESOLUTION)
        straight=float(np.linalg.norm(np.asarray(leg['goal'])-points[0])*RESOLUTION)
        if row.reason=='too_long': assert travelled>6*straight
        failed.append(dict(patch=row.patch,prior=row.prior,radius_m=row.radius_m,mode=row.mode,reason=row.reason,
                           failed_leg=len(detail[key+'_legs']),leg_travelled_m=travelled,leg_straight_m=straight,
                           travelled_over_straight=travelled/straight))
    failures=pd.DataFrame(failed)
    failures.to_csv(folder/'failure_details.csv',index=False)
    values=calls[calls['mode']=='online'].seconds
    overall=dict(online_calls=len(values),median_s=values.median(),p95_s=values.quantile(.95),max_s=values.max(),calls_over_1s=int((values>1).sum()))
    stream=io.StringIO()
    with redirect_stdout(stream):
        print('All prescribed identities, unique calls, per-mission planning counts and frozen source hashes passed.')
        print('\nIncomplete-leg distances from saved executed trajectories, default max_factor=6 unchanged')
        print(failures.to_string(index=False))
        print('\nAll online search+exact smoothing calls; load-dependent wall times, not physical measurements')
        print(pd.DataFrame([overall]).to_string(index=False))
    log=stream.getvalue()
    (folder/'audit_log.txt').write_text(log)
    (folder/'planning_timing_audit.json').write_text(json.dumps(overall,indent=2)+'\n')
    print(log,end='')


if __name__=='__main__':
    main()
