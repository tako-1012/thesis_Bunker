"""Fixed-radius LAS footprint study: 192 offline scenarios and 96 R10 tours.

No parameter selection: 0.5m is Robot.footprint_radius, 0.39m is prescribed.
The old task014 waypoint order and uninflated full-truth oracle are shared by
all online variants, so dJ includes both clearance and incomplete-map costs.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
import gzip
import io
import json
from multiprocessing import Pool
import os
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
import scipy
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tapp.config import RESOLUTION
from tapp.footprint import with_inflated_steep,blocked_endpoints,steep_proximity_fraction,run_footprint_mission
from tapp.real_beach import build_real,list_patches
from tapp.exact_planners import run_planner_exact
from tapp.prior import PriorMap,coarse_prior,coarse_elevation
from tapp.traversability import TraversabilityMap
from tapp.online_mission import ordered_tour,run_online_mission
from tapp.collision import path_lethal_cells
from experiments.online_mission import scenarios
from experiments.beach_terrain import metrics
from experiments.analyze import paired_test,holm

OUT=ROOT/'results/footprint_steep'
VARIANTS=[('A*',None),('TA*-S',0),('TA*-S+inflate r0.5',.5),('TA*-S+inflate r0.39',.39)]
FIELDS=['length_xy','mean_cost','climb','p95_roll','steep_near_fraction']
CONTRASTS=[('TA*-S','A*'),('TA*-S+inflate r0.5','TA*-S'),('TA*-S+inflate r0.39','TA*-S')]


def offline_job(job):
    patch,side,debris=job
    sc=build_real(patch,side,0,debris=debris,dataset='shizuoka_beach_las')
    tm=sc['tmap'];rows=[];paths={}
    for name,radius in VARIANTS:
        other=sc if radius in (None,0) else with_inflated_steep(sc,radius)
        blocked=blocked_endpoints(other['tmap'],sc['start'],[sc['goal']]) if radius else []
        r=dict(success=False,path=[],time=0.) if blocked else run_planner_exact('A*' if name=='A*' else 'TA*-S',other)
        row=dict(patch=patch,side_m=side,debris=debris,seed=0,planner=name,
                 requested_radius_m=radius,success=bool(r['success']),
                 reason='blocked_endpoint' if blocked else ('' if r['success'] else 'no_path'),
                 planning_s=r['time'],start=json.dumps(sc['start']),goal=json.dumps(sc['goal']),
                 used_seed=sc['used_seed'],redraws=sc['redraws'],crop_origin=json.dumps(sc['crop_origin_cells']))
        if r['success']:
            measured=metrics(r['path'],tm)
            row.update({k:measured[k] for k in FIELDS if k!='steep_near_fraction'})
            row['steep_near_fraction']=steep_proximity_fraction(r['path'],tm,.5)
            row['lethal_cells']=len(path_lethal_cells(r['path'],tm.lethal))
            paths[name]=np.asarray(r['path']).tolist()
        rows.append(row)
    return dict(rows=rows,paths=paths)


def online_job(patch):
    source=next(r for r in list_patches('test',dataset='shizuoka_beach_las') if r['name']==patch)
    clean,stale,points=scenarios(source)
    coarse=coarse_prior(clean['tmap'],10)
    coarse_tm=TraversabilityMap(coarse_elevation(clean['tmap'],10),np.zeros(clean['tmap'].shape,bool),
                               clean['tmap'].robot,clean['tmap'].weights)
    refs={}
    for terrain,sc in [('clean',clean),('stale',stale)]:
        truth=sc['tmap'];tour=ordered_tour(truth,sc['start'],points[terrain])
        r=run_online_mission(truth,PriorMap(truth.cost,truth.lethal,RESOLUTION),sc['start'],tour['stops'],
                             radius_m=10,prior_lethal_mode='hard')
        if not r['success']:raise RuntimeError('original full-truth oracle failed: '+patch+' '+terrain)
        refs[terrain]=metrics(r['traj'],truth)['J']
    rows=[];timings=[];traces={}
    for prior_name,sc,prior_tm,prior,terrain in [
        ('coarse c10',clean,coarse_tm,coarse,'clean'),
        ('stale',stale,clean['tmap'],PriorMap(clean['tmap'].cost,clean['tmap'].lethal,RESOLUTION),'stale')]:
        try:
            tour=ordered_tour(prior_tm,sc['start'],points[terrain]);order_error=''
        except ValueError as exc:
            tour=None;order_error=str(exc)
        for name,radius in VARIANTS[1:]:
            base=dict(patch=patch,side_m=200,seed=0,prior=prior_name,radius_m=10,mode='online',
                      planner=name,requested_radius_m=radius,oracle_J=refs[terrain],
                      order=json.dumps(None if tour is None else tour['order']))
            if tour is None:
                rows.append(dict(base,success=False,reason='prior_order: '+order_error,n_plans=0,n_replans=0,
                                 contact_audited=False,lethal_cells=None,debris_cells=None))
                continue
            r=(run_online_mission(sc['tmap'],prior,sc['start'],tour['stops'],radius_m=10)
               if radius==0 else run_footprint_mission(sc['tmap'],prior,prior_tm,sc['start'],tour['stops'],
                                                       radius_m=10,footprint_radius_m=radius))
            audited=bool(r['n_plans'])
            debris_mask=(sc['tmap'].rock & ~clean['tmap'].rock if prior_name=='stale' else np.zeros(sc['tmap'].shape,bool))
            row=dict(base,success=r['success'],reason=r['reason'],n_plans=r['n_plans'],n_replans=r['n_replans'],
                     contact_audited=audited,
                     lethal_cells=len(path_lethal_cells(r['traj'],sc['tmap'].lethal)) if audited else None,
                     debris_cells=len(path_lethal_cells(r['traj'],debris_mask)) if audited else None)
            if r['success']:
                measured=metrics(r['traj'],sc['tmap'])
                row.update({k:measured[k] for k in FIELDS if k!='steep_near_fraction'})
                row.update(J=measured['J'],dJ=100*(measured['J']/refs[terrain]-1),
                           steep_near_fraction=steep_proximity_fraction(r['traj'],sc['tmap'],.5))
            rows.append(row)
            timings.extend(dict(base,call=i,seconds=t) for i,t in enumerate(r['plan_times']))
            traces[prior_name+'_'+name]=np.asarray(r['traj']).tolist()
    return dict(rows=rows,timings=timings,traces=traces)


def site_statistics(data):
    """One beach is one unit: require both sizes paired, then average within site.

    One prespecified Holm family: 2 debris conditions x 3 contrasts x 5 metrics.
    Unavailable comparisons count as p=1 in correction, with NA reported for them.
    """
    rows=[]
    for debris in [False,True]:
        subset=data[data.debris==debris]
        for method,reference in CONTRASTS:
            left=subset[subset.planner==method]
            right=subset[subset.planner==reference]
            paired=left.merge(right,on=['patch','side_m'],suffixes=('_a','_b'),validate='one_to_one')
            valid=paired[paired.success_a & paired.success_b]
            eligible=valid.groupby('patch').side_m.nunique()
            sites=eligible[eligible==2].index
            valid=valid[valid.patch.isin(sites)]
            for metric in FIELDS:
                grouped=valid.groupby('patch')[[metric+'_a',metric+'_b']].mean()
                if len(grouped):
                    p,effect,delta=paired_test(grouped[metric+'_a'],grouped[metric+'_b'])
                else:p=effect=delta=np.nan
                rows.append(dict(debris=debris,method=method,reference=reference,metric=metric,
                                 n_beaches=len(grouped),excluded_beaches=48-len(grouped),
                                 delta_median=delta,p=p,rank_biserial=effect))
    adjusted=holm([r['p'] if np.isfinite(r['p']) else 1 for r in rows])
    for row,p in zip(rows,adjusted):row['p_holm']=float(p) if np.isfinite(row['p']) else np.nan
    return pd.DataFrame(rows)


def table(title,data):
    print('\n'+title)
    print(data.to_string(index=False,float_format=lambda x:f'{x:.6g}'))


def summarize_offline(folder):
    records=[json.loads(p.read_text()) for p in sorted((folder/'offline_cache').glob('*.json'))]
    data=pd.DataFrame([row for record in records for row in record['rows']])
    if len(data)!=48*2*2*4:raise ValueError('incomplete offline experiment')
    data.to_csv(folder/'offline.csv',index=False)
    rows=[];penalties=[]
    for (debris,side,name),group in data.groupby(['debris','side_m','planner'],sort=False):
        ok=group[group.success]
        row=dict(debris=debris,side_m=side,planner=name,runs=len(group),solved=int(group.success.sum()),
                 blocked_endpoints=int(group.reason.eq('blocked_endpoint').sum()))
        row.update({k+'_median':ok[k].median() for k in FIELDS});rows.append(row)
        if name not in ('A*','TA*-S'):
            base=data[(data.debris==debris)&(data.side_m==side)&(data.planner=='TA*-S')]
            joined=group.merge(base,on='patch',suffixes=('_a','_b'),validate='one_to_one')
            pairs=joined[joined.success_a & joined.success_b]
            penalties.append(dict(debris=debris,side_m=side,planner=name,
                                  lost_solutions=int((joined.success_b & ~joined.success_a).sum()),
                                  gained_solutions=int((~joined.success_b & joined.success_a).sum()),paired_success=len(pairs),
                                  length_delta_median=(pairs.length_xy_a-pairs.length_xy_b).median(),
                                  length_delta_pct_median=(100*(pairs.length_xy_a/pairs.length_xy_b-1)).median(),
                                  cost_delta_median=(pairs.mean_cost_a-pairs.mean_cost_b).median(),
                                  cost_delta_pct_median=(100*(pairs.mean_cost_a/pairs.mean_cost_b-1)).median()))
    summary=pd.DataFrame(rows);summary.to_csv(folder/'offline_summary.csv',index=False)
    changes=pd.DataFrame(penalties);changes.to_csv(folder/'offline_penalties.csv',index=False)
    stats=site_statistics(data);stats.to_csv(folder/'offline_statistics.csv',index=False)
    table('A: complete-map LAS test scenarios; proximity is path length within 0.5m of steep cell centres',summary)
    table('Inflation versus unchanged TA*-S: feasibility and paired length/cost increases',changes)
    table('48 beaches as units; both sizes paired before averaging; one Holm family of 30 tests',stats)
    old=pd.read_csv(ROOT/'results/real_beach_las/offline.csv',float_precision='round_trip')
    old=old[old.planner.isin(['A*','TA*-S exact'])].rename(columns={'kind':'patch'})
    old['planner']=old.planner.replace({'TA*-S exact':'TA*-S'})
    paired=data[data.planner.isin(['A*','TA*-S'])].merge(old,on=['patch','side_m','debris','seed','planner'],suffixes=('_new','_old'),validate='one_to_one')
    assert len(paired)==384 and (paired.success_new==paired.success_old).all()
    audit=[]
    for metric in FIELDS[:-1]:
        difference=(paired[metric+'_new']-paired[metric+'_old']).abs().max()
        audit.append(dict(metric=metric,max_abs_difference=difference));assert difference<=1e-9
    baseline=pd.DataFrame(audit);baseline.to_csv(folder/'offline_baseline_audit.csv',index=False)
    table('Re-executed baseline versus archived task013 LAS results',baseline)
    return data


def summarize_online(folder):
    records=[json.loads(gzip.decompress(p.read_bytes())) for p in sorted((folder/'online_cache').glob('*.json.gz'))]
    data=pd.DataFrame([row for record in records for row in record['rows']])
    times=pd.DataFrame([row for record in records for row in record['timings']])
    if len(data)!=48*2*3:raise ValueError('incomplete R10 online experiment')
    data.to_csv(folder/'online.csv',index=False)
    assert len(times)==data.n_plans.sum()
    for patch,group in times.groupby('patch'):
        for part,start in enumerate(range(0,len(group),5000)):
            group.iloc[start:start+5000].to_csv(folder/f'plan_times_{patch}_{part}.csv',index=False)
    rows=[]
    for (prior,name),group in data.groupby(['prior','planner'],sort=False):
        ok=group[group.success]
        calls=times[(times.prior==prior)&(times.planner==name)].seconds
        rows.append(dict(prior=prior,planner=name,runs=len(group),completed=int(group.success.sum()),failed=int((~group.success).sum()),
                         contact_audited=int(group.contact_audited.sum()),touching=int((group.lethal_cells>0).sum()),
                         debris_touching=int((group.debris_cells>0).sum()),dJ_median=ok.dJ.median(),dJ_p90=ok.dJ.quantile(.9),dJ_max=ok.dJ.max(),
                         replans_median=group.n_replans.median(),replans_max=group.n_replans.max(),
                         completed_replans_median=ok.n_replans.median(),plan_calls=len(calls),plan_s_median=calls.median(),
                         plan_s_p95=calls.quantile(.95),plan_s_max=calls.max(),calls_over_1s=int((calls>1).sum())))
    summary=pd.DataFrame(rows);summary.to_csv(folder/'online_summary.csv',index=False)
    failure=data[~data.success].groupby(['prior','planner','reason']).size().reset_index(name='runs')
    failure.to_csv(folder/'online_failures.csv',index=False)
    table('B: task014 fixed prior tour order, R10; dJ vs unchanged full-truth oracle',summary)
    table('Incomplete tours (endpoints never moved)',failure)
    old=pd.read_csv(ROOT/'results/online_mission/missions.csv',float_precision='round_trip')
    old=old[(old.radius_m==10)&(old['mode']=='online')&old.prior.isin(['stale','coarse c10'])]
    joined=data[data.planner=='TA*-S'].merge(old,on=['patch','prior'],suffixes=('_new','_old'),validate='one_to_one')
    assert len(joined)==96
    audits=[]
    for key in ['success','n_plans','n_replans','lethal_cells','J','dJ','oracle_J']:
        a,b=joined[key+'_new'],joined[key+'_old']
        difference=(a.astype(float)-b.astype(float)).abs().max()
        audits.append(dict(field=key,max_abs_difference=difference));assert difference<=1e-9
    audit=pd.DataFrame(audits);audit.to_csv(folder/'online_baseline_audit.csv',index=False)
    table('Re-executed online control versus task014 archive (timings independently measured)',audit)
    return data


def example_plot(folder):
    sc=build_real('08OB88_-0167',200,0,dataset='shizuoka_beach_las')
    result=json.loads((folder/'offline_cache/08OB88_-0167_200_0.json').read_text())
    old=ROOT/'results/gazebo_compare/physical_run'
    manifest=json.loads((old/'manifest.json').read_text())
    case=next(c for c in manifest['cases'] if c['patch']=='08OB88_-0167' and c['planner']=='TA*-S')
    planned=np.asarray(case['path_cells'])*RESOLUTION
    trace=pd.read_csv(old/case['run_folder']/'trajectory.csv',float_precision='round_trip')
    hit=trace.iloc[np.flatnonzero(np.abs(trace.roll)>np.pi/2)[0]]
    tm=sc['tmap'];fig,axes=plt.subplots(1,2,figsize=(13,6))
    for ax in axes:
        radius=.5
        inflated=with_inflated_steep(sc,radius)['tmap']
        ax.imshow(tm.elev.T,origin='lower',extent=[-.25,199.75,-.25,199.75],cmap='terrain')
        overlay=np.zeros((*tm.shape,4));overlay[tm.steep]=[.5,0,0,.8]
        overlay[inflated.lethal & ~tm.lethal]=[1,.3,0,.6]
        ax.imshow(overlay.transpose(1,0,2),origin='lower',extent=[-.25,199.75,-.25,199.75])
        ax.plot(*planned.T,label='019 TA*-S planned',color='blue')
        ax.plot(trace.x,trace.y,label='019 TA*-S recorded',color='black',ls='--',lw=1)
        ax.scatter([hit.x],[hit.y],marker='o',facecolors='none',edgecolors='red',label='first rollover')
        for name,path in result['paths'].items():
            if name!=f'TA*-S+inflate r{radius}':continue
            xy=np.asarray(path)*RESOLUTION;ax.plot(*xy.T,label=name)
        status=next(r['reason'] or 'solved' for r in result['rows'] if r['planner']==f'TA*-S+inflate r{radius}')
        ax.scatter(*(np.asarray([sc['start'],sc['goal']])*RESOLUTION).T,marker='x',color='black')
        ax.set(title=f'r={radius}m: {status}',xlabel='x [m]',ylabel='y [m]');ax.legend()
    axes[1].set_xlim(max(-.25,hit.x-25),min(199.75,hit.x+25))
    axes[1].set_ylim(max(-.25,hit.y-20),min(199.75,hit.y+20))
    fig.suptitle('08OB88_-0167: original steep cells (dark), added exclusion (orange); endpoints unchanged')
    fig.tight_layout();fig.savefig(folder/'08OB88_-0167_clearance.png',dpi=150);plt.close(fig)


def protocol(folder,workers):
    sources=['tapp/footprint.py','experiments/footprint_steep.py','tapp/config.py','tapp/real_beach.py','tapp/online_mission.py','tapp/exact_planners.py']
    data=dict(dataset='shizuoka_beach_las',split='test',seed=0,radii_m=[.5,.39],
              raster_rule='same ceil(radius/0.5) disk as rocks; both prescribed radii map to one grid cell',
              proximity='exact arc length within 0.5m of steep cell centres',
              statistics='48 beach units; both sizes paired then averaged; 30-test Holm family',
              online='same task014 prior-fixed order, truth-label sensing, R10; shared unchanged oracle',
              environment=dict(python=sys.version,numpy=np.__version__,scipy=scipy.__version__,pandas=pd.__version__),
              dataset_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted((ROOT/'data/shizuoka_beach_las').rglob('*')) if p.is_file()},
              source_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources})
    path=folder/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=data:raise ValueError('source/protocol changed; use a new output folder')
    path.write_text(json.dumps(data,indent=2)+'\n')
    (folder/'execution.json').write_text(json.dumps(dict(workers=workers,python=sys.version,numpy=np.__version__),indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=OUT);parser.add_argument('--workers',type=int,default=3)
    parser.add_argument('--stage',choices=['offline','online','all','summarize'],default='all')
    args=parser.parse_args();folder=args.output.resolve();folder.mkdir(parents=True,exist_ok=True)
    protocol(folder,args.workers)
    patches=[r['name'] for r in list_patches('test',dataset='shizuoka_beach_las')]
    for stage in (['offline','online'] if args.stage=='all' else ([args.stage] if args.stage!='summarize' else [])):
        cache=folder/(stage+'_cache');cache.mkdir(exist_ok=True)
        jobs=([(p,s,d) for p in patches for s in [100,200] for d in [False,True]] if stage=='offline' else patches)
        name=lambda job: (f'{job[0]}_{job[1]}_{int(job[2])}'+'.json' if stage=='offline' else job+'.json.gz')
        pending=[job for job in jobs if not (cache/name(job)).exists()]
        worker=offline_job if stage=='offline' else online_job
        with Pool(args.workers) as pool:
            for job,result in zip(pending,pool.imap(worker,pending)):
                target=cache/name(job)
                payload=(json.dumps(result)+'\n').encode()
                target.write_bytes(payload if stage=='offline' else gzip.compress(payload,mtime=0))
                if target.stat().st_size>=5_000_000:raise ValueError('result cache exceeds 5MB: '+str(target))
                print(stage, name(job), 'saved',flush=True)
    stream=io.StringIO()
    with redirect_stdout(stream):
        if args.stage in ('all','offline','summarize'):
            summarize_offline(folder);example_plot(folder)
        if args.stage in ('all','online','summarize'):summarize_online(folder)
    log=stream.getvalue();(folder/(args.stage+'_log.txt')).write_text(log);print(log,end='')


if __name__=='__main__':main()
