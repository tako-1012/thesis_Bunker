"""Footprint geometry, unchanged maps/zero-radius integration and rollover records."""
from contextlib import redirect_stdout
import hashlib
import csv
import io
import json
from pathlib import Path
import tempfile
import numpy as np

from tapp.config import RESOLUTION
from tapp.traversability import TraversabilityMap
from tapp.footprint import (inflate_steep, with_inflated_steep, blocked_endpoints,
                            steep_proximity_fraction, run_footprint_mission)
from tapp.real_beach import build_real
from tapp.exact_planners import run_planner_exact
from tapp.online_mission import run_online_mission
from tapp.run_log import RunLog
from experiments.gz_compare_report import analyze_case, rollover_details, annotate_existing

ROOT=Path(__file__).resolve().parents[1]


def test_dilation():
    tm=TraversabilityMap(np.zeros((41,41)),np.zeros((41,41),bool))
    tm.steep[20,20]=True;tm.lethal[20,20]=True
    tm.rock[4,4]=True;tm.lethal[4,4]=True
    original=tm.lethal.copy();cost=tm.cost.copy()
    x,y=np.indices(tm.shape)
    expected=((x-20)**2+(y-20)**2)*RESOLUTION**2<=.5**2
    expected[4,4]=True
    assert np.array_equal(inflate_steep(tm),expected)
    assert np.array_equal(inflate_steep(tm,0),original)
    assert np.array_equal(inflate_steep(tm,.39),expected)  # same ceil-to-cell rule as rocks
    sc=dict(tmap=tm,start=(19,20),goal=(30,30))
    changed=with_inflated_steep(sc)
    assert changed is not sc and changed['tmap'] is not tm
    assert changed['tmap'].cost is tm.cost
    assert np.array_equal(tm.lethal,original) and np.array_equal(tm.cost,cost)
    assert blocked_endpoints(changed['tmap'],sc['start'],[sc['goal']])==[0]
    assert changed['start']==sc['start'] and changed['goal']==sc['goal']
    for invalid in (-1,float('nan'),float('inf')):
        try:inflate_steep(tm,invalid)
        except ValueError:pass
        else:raise AssertionError('invalid radius accepted')
    print('dilation: 0.5m circle, rocks not doubled, zero radius, immutable costs/endpoints and raster rounding passed')


def test_proximity():
    tm=TraversabilityMap(np.zeros((41,41)),np.zeros((41,41),bool))
    tm.steep[20,20]=True
    path=[(15,20),(25,20)]
    assert abs(steep_proximity_fraction(path,tm)-.2)<1e-12
    tm.steep[21,20]=True
    assert abs(steep_proximity_fraction(path,tm)-.3)<1e-12
    assert abs(steep_proximity_fraction(path[::-1],tm)-.3)<1e-12
    assert steep_proximity_fraction([(15,21),(25,21)],tm)==0
    assert steep_proximity_fraction(path,tm,0)==0
    print('proximity: analytic line-circle lengths, overlapping unions and tangencies passed')


def test_requested_beach():
    sc=build_real('08OB88_-0167',200,0,dataset='shizuoka_beach_las')
    changed=with_inflated_steep(sc)
    assert changed['start']==sc['start'] and changed['goal']==sc['goal']
    result=run_planner_exact('TA*-S',changed)
    if result['success']:
        assert steep_proximity_fraction(result['path'],sc['tmap'])<1e-12
        print('requested LAS case: feasible inflated path has zero 0.5m steep proximity')
    else:
        print('requested LAS case: inflated planner reports no_path without moving endpoints')


def test_zero_radius_online():
    tm=TraversabilityMap(np.zeros((50,50)),np.zeros((50,50),bool))
    a=run_online_mission(tm,None,(5,5),[(40,35)],radius_m=10)
    b=run_footprint_mission(tm,None,None,(5,5),[(40,35)],radius_m=10,footprint_radius_m=0)
    assert a['success']==b['success'] and a['n_plans']==b['n_plans']
    assert np.array_equal(a['traj'],b['traj'])
    print('online: zero radius preserves exact task014 trajectory and planning count')


def test_rollovers():
    for angles,expected,first in [([0,90,-90,89],False,None),([0,90,-91,120],True,2),([0,91,-120,0],True,1)]:
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            mission=dict(map_id='file/flat_test_100m.npz',map_file=str(ROOT/'maps/flat_test_100m.npz'),
                         data_source='rollover_test_fixture',path=[[10,10],[11,10]],lookahead_m=1.)
            log=RunLog(mission,folder/'raw')
            for i,angle in enumerate(angles):
                log.write(dict(t=10+i,x=10+.1*i,y=10,z=0,roll=float(np.radians(angle)),pitch=0,yaw=0,v=0,w=0))
            log.close('stuck')
            before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in log.folder.iterdir()}
            case=dict(run_folder=str(log.folder.relative_to(folder)),map_file=mission['map_file'])
            with redirect_stdout(io.StringIO()):result,trace=analyze_case(folder,case,folder/'analysis')
            assert result['rolled_over'] is expected
            assert result['recorded_status']=='stuck'
            assert result['status']==('rollover' if expected else 'stuck')
            assert result['completed'] is False
            if expected:
                assert result['rollover_t_s']==10+first
                assert result['rollover_elapsed_s']==first
                assert result['rollover_x_m']==10+.1*first and result['rollover_y_m']==10
            else:assert result['rollover_t_s'] is None
            assert all(hashlib.sha256((log.folder/p).read_bytes()).hexdigest()==h for p,h in before.items())
            report=folder/'report';report.mkdir()
            original=dict(patch='fixture',planner='A*',status='stuck',completed='False',elapsed_s='1.0000000000000001')
            with (report/'runs.csv').open('w',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(original));writer.writeheader();writer.writerow(original)
            (report/'paired_differences.csv').write_text('metric,paired_completed,delta_median\nelapsed_s,0,0\n')
            (folder/'manifest.json').write_text(json.dumps(dict(cases=[dict(case,patch='fixture',planner='A*')])))
            with redirect_stdout(io.StringIO()):annotate_existing(folder)
            with (report/'runs.csv').open() as stream:annotated=next(csv.DictReader(stream))
            assert annotated['elapsed_s']==original['elapsed_s']
            assert annotated['status']==('rollover' if expected else 'stuck')
            assert annotated['recorded_status']=='stuck'
            assert all(hashlib.sha256((log.folder/p).read_bytes()).hexdigest()==h for p,h in before.items())
    print('rollover: strict +/-90deg threshold, first time/position and immutable fake records passed')


def test_statistical_units():
    import pandas as pd
    from experiments.footprint_steep import VARIANTS,FIELDS,site_statistics
    rows=[]
    for debris in [False,True]:
        for patch in ['fixture_a','fixture_b']:
            for side in [100,200]:
                for name,radius in VARIANTS:
                    value=8. if patch=='fixture_a' and side==200 and radius else 0.
                    row=dict(patch=patch,side_m=side,debris=debris,planner=name,
                             success=not (patch=='fixture_b' and side==100 and radius==.39))
                    row.update({k:value for k in FIELDS});rows.append(row)
    stats=site_statistics(pd.DataFrame(rows))
    row=stats[(stats.method=='TA*-S+inflate r0.5') & ~stats.debris & (stats.metric=='length_xy')].iloc[0]
    assert row.n_beaches==2 and row.delta_median==2  # per-beach means [4,0], not four pseudo-replicates
    row=stats[(stats.method=='TA*-S+inflate r0.39') & ~stats.debris & (stats.metric=='length_xy')].iloc[0]
    assert row.n_beaches==1 and row.excluded_beaches==47
    assert len(stats)==30
    print('statistics: two sizes averaged within beach, incomplete pairs excluded, one fixed Holm family passed (synthetic fixtures only)')


def test_gazebo_selection():
    from ros2_jazzy.gz_checks.compare_checks import scenario_cases
    from tapp.collision import path_lethal_cells
    cases=scenario_cases(['TA*-S+inflate'])
    assert len(cases)==6 and all(c['planner']=='TA*-S+inflate' for c in cases)
    for case in cases:
        sc=case['scenario'];inflated=with_inflated_steep(sc)['tmap']
        assert case['start']==list(sc['start']) and case['goal']==list(sc['goal'])
        if case['planning_status']=='planned':
            assert len(path_lethal_cells(case['path_cells'],inflated.lethal))==0
        else:
            assert case['planning_status'] in ('no_path','blocked_endpoint') and not len(case['path_cells'])
    print('Gazebo selection: six fixed scenarios, inflated-only selection and explicit infeasibility passed')


def test_comparison_denominators():
    import pandas as pd
    from experiments.footprint_report import comparison_tables,METHODS
    from experiments.gz_compare_report import MEASURES
    rows=[]
    for patch in ['fixture_a','fixture_b']:
        for index,name in enumerate(METHODS):
            absent=name=='TA*-S+inflate'
            rollover=patch=='fixture_b' and name=='A*'
            row=dict(patch=patch,planner=name,data_source=None if absent else 'gazebo',
                     status=('no_path' if patch=='fixture_b' else '未実行') if absent else ('rollover' if rollover else 'completed'),
                     completed=(False if patch=='fixture_b' else None) if absent else not rollover,
                     rolled_over=None if absent else rollover)
            row.update({key:None if absent else float(index+1) for key in MEASURES});rows.append(row)
    summary,effects=comparison_tables(pd.DataFrame(rows))
    new=summary[summary.planner=='TA*-S+inflate'].iloc[0]
    assert new.executed==0 and new.planning_failed==1 and new.unexecuted==1
    assert pd.isna(new.completed) and pd.isna(new.rolled_over)
    pair=effects[(effects.method=='TA*-S') & (effects.reference=='A*')]
    assert pair.paired_completed.eq(1).all() and pair.delta_median.eq(1).all()
    missing=effects[effects.method=='TA*-S+inflate']
    assert missing.paired_completed.eq(0).all() and missing.delta_median.isna().all()
    print('comparison: unknown physical outcomes stay unknown; rollover pairs excluded; explicit executed denominator passed (fixtures only)')


def test_three_method_pairing():
    import pandas as pd
    from unittest.mock import patch
    from experiments.gz_compare_report import summarize,MEASURES,MAP_MEASURES,ROLLOVER_FIELDS
    planners=['A*','TA*-S','TA*-S+inflate']
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp);cases=[]
        for i in range(6):
            for name in planners:
                failed=i==0 and name=='TA*-S+inflate'
                cases.append(dict(patch='fixture_'+str(i),planner=name,
                                  map_file=str(ROOT/'maps/flat_test_100m.npz'),
                                  map_metrics={k:0. for k in MAP_MEASURES},
                                  run_folder=None if failed else 'mocked_recording',
                                  planning_status='no_path' if failed else 'planned'))
        (root/'manifest.json').write_text(json.dumps(dict(planners=planners,cases=cases)))
        def mock_analyze(folder,case,output):
            result=dict(status='completed',completed=True,data_source='test_fixture',
                        roll_p95_map_deg=0.,pitch_p95_map_deg=0.)
            result.update({k:0. for k in MEASURES})
            result.update({'map_'+k:0. for k in MAP_MEASURES})
            result.update({k:None for k in ROLLOVER_FIELDS})
            result.update(recorded_status='completed',rolled_over=False)
            return result,pd.DataFrame(dict(t=[0.,1.],x=[10.,11.],y=[10.,10.],roll=[0.,0.]))
        with patch('experiments.gz_compare_report.analyze_case',side_effect=mock_analyze),redirect_stdout(io.StringIO()):
            data,effects=summarize(root)
        original=effects[(effects.method=='TA*-S') & (effects.reference=='A*')]
        inflated=effects[effects.method=='TA*-S+inflate']
        assert len(data)==18 and original.paired_completed.eq(6).all()
        assert inflated.paired_completed.eq(5).all()
    print('three-method reports: each contrast uses its own completion cohort; third-method failure does not drop old pairs (fixtures only)')


if __name__=='__main__':
    test_dilation();test_proximity();test_requested_beach();test_zero_radius_online();test_rollovers()
    test_statistical_units();test_gazebo_selection();test_comparison_denominators();test_three_method_pairing()
    print('all footprint and rollover tests passed')
