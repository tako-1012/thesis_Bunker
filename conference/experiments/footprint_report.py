"""Task020 descriptive audits and three-method Gazebo tables, including unrun cases.

Cached baseline measurements are reused without rewriting them. With no new
Gazebo recording, only actual planner outputs are generated; physical fields
remain unknown. No hypothesis tests are applied to six Gazebo scenarios.
"""
import argparse
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tapp.config import RESOLUTION
from tapp.mapfile import load_map_file
from experiments.gz_compare_report import MEASURES,summarize
from ros2_jazzy.gz_checks.compare_checks import prepare_cases

METHODS=['A*','TA*-S','TA*-S+inflate']


def boolean(value):
    if pd.isna(value):return None
    if str(value).lower() not in ('true','false'):raise ValueError('invalid boolean recording')
    return str(value).lower()=='true'


def comparison_tables(data):
    """Keep executed denominators explicit; unknown rollovers never become zero."""
    summary=[]
    for name in METHODS:
        group=data[data.planner==name]
        executed=group.data_source.eq('gazebo')
        count=int(executed.sum())
        summary.append(dict(planner=name,scenarios=len(group),
                            planning_failed=int(group.status.isin(['no_path','blocked_endpoint']).sum()),
                            executed=count,completed=int(group.completed.eq(True).sum()) if count else None,
                            rolled_over=int(group.rolled_over.eq(True).sum()) if count else None,
                            unexecuted=int((~executed & ~group.status.isin(['no_path','blocked_endpoint'])).sum())))
    effects=[]
    for method,reference in [('TA*-S','A*'),('TA*-S+inflate','A*'),('TA*-S+inflate','TA*-S')]:
        left=data[data.planner==method];right=data[data.planner==reference]
        pair=left.merge(right,on='patch',suffixes=('_a','_b'),validate='one_to_one')
        both=pair.completed_a.eq(True)&pair.completed_b.eq(True)
        for metric in MEASURES:
            difference=pair.loc[both,metric+'_a']-pair.loc[both,metric+'_b']
            effects.append(dict(method=method,reference=reference,metric=metric,
                                paired_completed=int(both.sum()),delta_median=difference.median()))
    return pd.DataFrame(summary),pd.DataFrame(effects)


def penalty_audit(folder):
    data=pd.read_csv(folder/'offline.csv',float_precision='round_trip')
    rows=[]
    for (debris,side),group in data.groupby(['debris','side_m']):
        base=group[group.planner=='TA*-S']
        for name in ['TA*-S+inflate r0.5','TA*-S+inflate r0.39']:
            other=group[group.planner==name]
            joined=other.merge(base,on='patch',suffixes=('_a','_b'),validate='one_to_one')
            valid=joined[joined.success_a & joined.success_b]
            row=dict(debris=debris,side_m=side,planner=name,paired_success=len(valid),
                     lost_solutions=int((~joined.success_a & joined.success_b).sum()))
            for key in ['length_xy','mean_cost']:
                delta=valid[key+'_a']-valid[key+'_b']
                percent=100*(valid[key+'_a']/valid[key+'_b']-1)
                row.update({key+'_increased_cases':int((delta>1e-12).sum()),
                            key+'_delta_max':delta.max(),key+'_delta_pct_p90':percent.quantile(.9),
                            key+'_delta_pct_max':percent.max()})
            rows.append(row)
    result=pd.DataFrame(rows);result.to_csv(folder/'offline_increase_audit.csv',index=False)
    return result


def online_pair_audit(folder):
    """Descriptive paired changes without adding post-hoc hypothesis tests."""
    data=pd.read_csv(folder/'online.csv',float_precision='round_trip');rows=[]
    for prior,group in data.groupby('prior'):
        base=group[group.planner=='TA*-S']
        for name in ['TA*-S+inflate r0.5','TA*-S+inflate r0.39']:
            pair=group[group.planner==name].merge(base,on='patch',suffixes=('_a','_b'),validate='one_to_one')
            valid=pair[pair.success_a & pair.success_b]
            rows.append(dict(prior=prior,planner=name,paired_success=len(valid),
                             lost_completed=int((pair.success_b & ~pair.success_a).sum()),
                             gained_completed=int((~pair.success_b & pair.success_a).sum()),
                             J_delta_median=(valid.J_a-valid.J_b).median(),
                             J_delta_pct_p90=(100*(valid.J_a/valid.J_b-1)).quantile(.9),
                             J_delta_pct_max=(100*(valid.J_a/valid.J_b-1)).max(),
                             length_delta_pct_max=(100*(valid.length_xy_a/valid.length_xy_b-1)).max()))
    result=pd.DataFrame(rows);result.to_csv(folder/'online_paired_audit.csv',index=False)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,default=ROOT/'results/gazebo_compare/physical_run')
    parser.add_argument('--inflated',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'results/footprint_steep/gazebo_comparison')
    args=parser.parse_args();output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    baseline=args.baseline.resolve()
    source_manifest=json.loads((baseline/'manifest.json').read_text())
    old=pd.read_csv(baseline/'report/runs.csv',float_precision='round_trip')
    if 'rolled_over' not in old:raise ValueError('annotate the task019 archive first with --annotate-existing')
    if args.inflated is None:
        inflated=output/'planning_only'
        manifest=prepare_cases(inflated,planners=['TA*-S+inflate'])
        manifest['execution']='planning_only; no physical Gazebo trial performed'
        (inflated/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        with redirect_stdout(io.StringIO()):new,_=summarize(inflated)
    else:
        inflated=args.inflated.resolve()
        manifest=json.loads((inflated/'manifest.json').read_text())
        if not (inflated/'report/runs.csv').exists():
            with redirect_stdout(io.StringIO()):summarize(inflated)
        new=pd.read_csv(inflated/'report/runs.csv',float_precision='round_trip')
    old_cases={(c['patch'],c['planner']):(baseline,c) for c in source_manifest['cases']}
    cases=dict(old_cases)
    for case in manifest['cases']:
        if case['planner']!='TA*-S+inflate':raise ValueError('new recording must select inflated TA*-S only')
        reference=old_cases[case['patch'],'TA*-S'][1]
        if (case['start'],case['goal'])!=(reference['start'],reference['goal']):
            raise ValueError('new trial changed scenario endpoints')
        cases[case['patch'],case['planner']]=(inflated,case)
    data=pd.concat([old,new],ignore_index=True)
    for column in ['completed','rolled_over']:data[column]=data[column].map(boolean)
    if len(data)!=18 or data[['patch','planner']].duplicated().any() or data.patch.nunique()!=6:
        raise ValueError('expected six beaches x three methods')
    data.to_csv(output/'runs.csv',index=False)
    summary,effects=comparison_tables(data)
    summary.to_csv(output/'summary.csv',index=False);effects.to_csv(output/'paired_differences.csv',index=False)
    for patch in dict.fromkeys(data.patch):
        base,case=old_cases[patch,'A*']
        tm=load_map_file(base/case['map_file'])['tmap']
        fig,axes=plt.subplots(1,2,figsize=(12,5));missing=[]
        axes[0].imshow(tm.elev.T,origin='lower',extent=[-.25,199.75,-.25,199.75],cmap='terrain')
        for name in METHODS:
            record_folder,c=cases[patch,name]
            row=data[(data.patch==patch)&(data.planner==name)].iloc[0]
            if not c.get('run_folder') or row.data_source!='gazebo':
                missing.append(name+': '+str(row.status));continue
            trace=pd.read_csv(record_folder/c['run_folder']/'trajectory.csv',float_precision='round_trip')
            label=name+' ('+str(row.status)+')'
            axes[0].plot(trace.x,trace.y,label=label)
            axes[1].plot(trace.t-trace.t.iloc[0],np.degrees(trace.roll),label=label)
        if missing:
            axes[0].text(.02,.02,'\n'.join(missing).replace('未実行','not executed'),transform=axes[0].transAxes,
                         fontsize=8,bbox=dict(facecolor='white',alpha=.85))
        axes[0].set(xlabel='x [m]',ylabel='y [m]',aspect='equal')
        axes[1].set(xlabel='Simulator time from first sample [s]',ylabel='Recorded roll [deg]')
        for ax in axes:ax.legend(fontsize=7)
        fig.suptitle(patch);fig.tight_layout();fig.savefig(output/(patch+'.png'),dpi=130);plt.close(fig)
    increases=penalty_audit(ROOT/'results/footprint_steep')
    online_changes=online_pair_audit(ROOT/'results/footprint_steep')
    stream=io.StringIO()
    with redirect_stdout(stream):
        print('Task020: three-method comparison; six beaches; descriptive only, no hypothesis tests.')
        print('Unknown physical values are blank/None/NaN. Planning failure is not a rollover-free physical trial.')
        print(data.to_string(index=False,float_format=lambda x:f'{x:.6g}'))
        print('\nPlanning/execution denominators (rollovers among executed recordings only)')
        print(summary.to_string(index=False,float_format=lambda x:f'{x:.6g}'))
        print('\nPaired median method minus reference; only both completed without rollover')
        print(effects.to_string(index=False,float_format=lambda x:f'{x:.6g}'))
        print('\nOffline increases versus TA*-S (descriptive maxima, no extra tests)')
        print(increases.to_string(index=False,float_format=lambda x:f'{x:.6g}'))
        print('\nOnline paired changes versus unchanged TA*-S (descriptive, no extra tests)')
        print(online_changes.to_string(index=False,float_format=lambda x:f'{x:.6g}'))
    log=stream.getvalue();(output/'comparison_log.txt').write_text(log);print(log,end='')
    (output/'sources.json').write_text(json.dumps(dict(
        baseline=os.path.relpath(baseline,ROOT),inflated=os.path.relpath(inflated,ROOT),
        new_physical_records=int(new.data_source.eq('gazebo').sum()),
        note='Cached baseline numeric values reused; no raw recording changed.'),indent=2)+'\n')


if __name__=='__main__':main()
