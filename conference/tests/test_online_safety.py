"""Task034 legacy bytes, real stopped-state handoff and closed-loop safety recovery."""
import ast
import csv
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from tapp.config import CostWeights, RESOLUTION, DEFAULT_W
from tapp.online_mission import OnlinePlanner
from tapp.online_safety import SafetyOnlinePlanner, SafetyMissionFollower
from tapp.traversability import TraversabilityMap
from tapp.prior import PriorMap
from tests.test_endpoint_policy import Immediate
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ros2_jazzy/src/thesis_bunker_mission'))
from thesis_bunker_mission.online_runtime import AsyncOnlineMission
from thesis_bunker_mission.online_safety import make_async_runtime, handle_safety_state
from ros2_jazzy.gz_checks.lidar_runtime import LidarOnlineMission
from ros2_jazzy.gz_checks.safety_runtime import make_safety_lidar_runtime

FIXTURE=ROOT/'results/diagnosis_033/fixtures/stuck_0847_C1_r2_t1345.npz'

class Mapper:
    def __init__(self, cost, lethal, known=None):
        self.cost,self.lethal=cost.copy(),lethal.copy()
        self.known=np.ones(cost.shape,bool) if known is None else known.copy()
    def snapshot(self): return self.known.copy(),self.cost.copy(),self.lethal.copy()


def setup_case(fixes='v1', *, lethal=None):
    z=np.zeros((24,24));mask=np.zeros(z.shape,bool) if lethal is None else lethal
    prior=dict(tmap=TraversabilityMap(z,np.zeros(z.shape,bool)))
    mapper=Mapper(z,mask)
    runtime=make_safety_lidar_runtime(prior,mapper,online_fixes=fixes,plan_log=None,executor=Immediate())
    mission=dict(id=1,map_id='fixture',order=[0,1],start_cells=[4,4],stops_cells=[[18,4]],
                 points=[[9.,2.]],path=[[2.,2.],[9.,2.]])
    runtime.start(mission)
    return runtime,mapper,mission


def test_default_bytes():
    capture=runpy.run_path(str(ROOT/'results/online_safety/verification/capture_defaults.py'))['capture']
    before=json.loads((ROOT/'results/online_safety/verification/defaults_before.json').read_text())
    for explicit in (False,True):
        actual=capture(explicit=explicit)
        for mode in ('coarse','fine','real'):
            a,b=actual.pop(mode),before[mode]
            assert a['without_environment_sha256']==b['without_environment_sha256']
            if a['environment']==b['environment']:
                assert a['full_sha256']==b['full_sha256']
        assert actual=={k:v for k,v in before.items() if k not in ('coarse','fine','real')}
    print('1 PASS: implicit/explicit none match pre-change runtime command JSON, plans/diagnostic bytes, follower trajectory/mission bytes and manifests')


def test_start_join():
    blocked=np.zeros((24,24),bool);blocked[4,4]=True
    for fixes in ('none','v1'):
        runtime,mapper,_=setup_case(fixes,lethal=blocked)
        try:
            runtime.tick([2.,2.],0.)
            result=runtime.pending.result()
            assert result['success']
            joined=runtime._join(runtime.state,result,[2.,2.])
            assert (joined is not None)==(fixes=='v1')
            if fixes=='v1':
                # Latest map changes after search: an outside obstacle still rejects.
                mapper.lethal[10,4]=True
                assert runtime._join(runtime.state,dict(path=[[4,4],[18,4]]),[2.,2.]) is None
        finally: runtime.close()
    # The perfect-radius adapter has the same start-cell-only contract.
    tm=TraversabilityMap(np.zeros((24,24)),np.zeros((24,24),bool));tm.lethal=blocked.copy()
    prior_tm=TraversabilityMap(np.zeros(tm.shape),np.zeros(tm.shape,bool))
    runtime=make_async_runtime(tm,prior_tm,PriorMap(tm.cost,np.zeros(tm.shape,bool),.5),online_fixes='v1',executor=Immediate())
    try:
        runtime.start(dict(id=1,map_id='fixture',points=[[9.,2.]]))
        runtime.tick([2.,2.],0.)
        result=runtime.pending.result()
        assert runtime._join(runtime.state,result,[2.,2.]) is not None
    finally: runtime.close()
    print('2 PASS: LiDAR and perfect-radius joins exempt only the start cell; later lethal cells remain rejected')


def replay_saved():
    with np.load(FIXTURE,allow_pickle=False) as arrays:
        data={k:arrays[k].copy() for k in arrays.files}
    def bits(name):
        shape=tuple(data[name+'_shape'])
        return np.unpackbits(data[name+'_bits'],count=int(np.prod(shape))).reshape(shape).astype(bool)
    lethal,known=bits('lethal'),bits('known')
    cost=(data['cost']-1.)/DEFAULT_W
    pos=data['pose'][:2]
    rows=[]
    for fixes in ('none','v1'):
        tm=TraversabilityMap(np.zeros(cost.shape),np.zeros(cost.shape,bool))
        runtime=make_safety_lidar_runtime(dict(tmap=tm),Mapper(cost,lethal,known),online_fixes=fixes,plan_log=None,executor=Immediate())
        try:
            planner=(SafetyOnlinePlanner if fixes=='v1' else OnlinePlanner)(cost,np.zeros(cost.shape,bool),CostWeights())
            planner.observe(known,cost,lethal)
            planner.goal=tuple(data['goal']);planner.pos=pos/RESOLUTION
            # Use precisely the saved search multiplier, as replay_stuck.py.
            planner.planning_maps=lambda:(lethal.copy(),data['cost'].copy())
            result=planner._plan('distance')
            assert result['success']
            state=dict(planner=planner)
            runtime._safety_now=float(data['sim_time'])
            joined=runtime._join(state,result,pos)
            assert (joined is not None)==(fixes=='v1')
            from tapp.collision import path_lethal_cells
            exempt=lethal.copy();exempt[tuple(data['start'])]=False
            outside_hits=0 if joined is None else len(path_lethal_cells(np.asarray(joined)/RESOLUTION,exempt))
            assert outside_hits==0
            rows.append(dict(online_fixes=fixes,search_success=bool(result['success']),handoff=joined is not None,
                             path_points=0 if joined is None else len(joined),outside_start_lethal_cells=outside_hits,
                             start_lethal=bool(lethal[tuple(data['start'])])))
        finally: runtime.close()
    return rows


def test_saved():
    rows=replay_saved()
    print('3 PASS: actual stuck_0847_C1_r2_t1345 fixture search and handoff')
    print('online_fixes search_success handoff path_points outside_start_lethal_cells start_lethal')
    for row in rows: print(*row.values())
    return rows


def test_join_timeout():
    runtime,mapper,_=setup_case()
    mapper.lethal[10,4]=True
    runtime.state['planner']=SafetyOnlinePlanner(mapper.cost,np.zeros(mapper.cost.shape,bool),CostWeights())
    runtime.state['planner'].observe(*mapper.snapshot())
    runtime.state['planner'].goal=(18,4)
    runtime.state['planner'].pos=np.array([4.,4.])
    runtime.state['tour']=dict(order=[0,1],stops=[(18,4)])
    # A result computed before the latest mapper update crosses the new obstacle.
    runtime._plan_work=lambda state,pos: dict(success=True,replanned=True,reason='distance',
        path=[[4,4],[18,4]],plan_time_s=0.)
    try:
        runtime.tick([2.,2.],0.)
        for t in (1.,2.,10.999):
            assert runtime.tick([2.,2.],t) is None and not runtime.finished
        runtime.state['planner'].events=[dict(n_plans=1,reason='distance',success=True,plan_time_s=0.,failure_class='')]
        error=runtime.tick([2.,2.],11.)
        assert 'failure_class' not in error['plan_history'][0]
        assert runtime.finished and error['online_error']=='join_rejected'
        assert runtime.safety_events[0]['event']=='join_rejected'
        assert runtime.safety_events[-1]['detail']['duration_s']==10.
        assert runtime.tick([2.,2.],12.) is None
    finally: runtime.close()
    # A successful handoff resets the consecutive rejection interval.
    runtime,mapper,_=setup_case()
    try:
        runtime.tick([2.,2.],0.);result=runtime.pending.result()
        mapper.lethal[10,4]=True;runtime._safety_now=1.
        assert runtime._join(runtime.state,dict(path=[[4,4],[18,4]]),[2.,2.]) is None
        mapper.lethal[10,4]=False;runtime._safety_now=5.
        assert runtime._join(runtime.state,result,[2.,2.]) is not None and runtime._join_since is None
    finally: runtime.close()
    print('4 PASS: consecutive join rejection terminates at exactly 10 simulation seconds; acceptance resets the interval')


def test_known_changed():
    for cls in (OnlinePlanner,SafetyOnlinePlanner):
        cost=np.zeros((24,24));lethal=np.zeros(cost.shape,bool);known=np.ones(cost.shape,bool)
        planner=cls(cost,lethal,CostWeights())
        planner.observe(known,cost,lethal);planner.start_leg((4,4),(18,4))
        lethal[10,15]=True;planner.observe(known,cost,lethal)
        assert not planner.update([2.,2.],distance_m=0)['replanned']
        lethal[10,4]=True;planner.observe(known,cost,lethal)
        result=planner.update([2.,2.],distance_m=0)
        assert result['replanned']==(cls is SafetyOnlinePlanner)
        if cls is SafetyOnlinePlanner:
            assert result['reason']=='lethal_changed' and not planner.pending_changed.any()
    print('5 PASS: known free-to-lethal on remaining path triggers lethal_changed only in v1; off-path changes do not replan; pending changes reset on planning')


def test_follower():
    for axis in (3,4):
        for deg,unsafe in ((26.,True),(-26.,True),(24.,False),(25.,False)):
            follower=SafetyMissionFollower([[0.,0.],[10.,0.]])
            pose=np.zeros(6);pose[0]=1.;pose[axis]=np.deg2rad(deg)
            v,w,done=follower.step(0.,pose)
            assert (follower.status=='unsafe_tilt')==unsafe
            if unsafe: assert v==w==0 and done
    for distance,unsafe in ((.8,True),(.7,False),(.75,False)):
        follower=SafetyMissionFollower([[0.,0.],[10.,0.]])
        v,w,done=follower.step(0.,[1.,distance,0.,0.,0.,0.])
        assert (follower.status=='off_path')==unsafe
        if unsafe: assert v==w==0 and done
    follower=SafetyMissionFollower([[0.,0.],[10.,0.]])
    assert follower.step(0.,[1.,0.,0.,0.,0.,0.],imu_rpy=[0.,np.deg2rad(26.),0.])==(0.,0.,True)
    follower=SafetyMissionFollower([[0.,0.],[10.,0.]])
    assert follower.step(0.,[1.,0.,0.,np.deg2rad(26.),0.,0.],imu_rpy=[0.,0.,0.])==(0.,0.,True)
    print('6 PASS: +/-26deg roll/pitch and 0.8m deviation stop; 24/25deg and 0.7/0.75m do not; zero linear and angular speed')


def test_safety_recovery():
    runtime,mapper,mission=setup_case()
    try:
        runtime.tick([2.,2.],0.);first=runtime.tick([2.,2.],.1)
        assert first and runtime.sent==1
        # A follower stop invalidates the pending old revision.
        assert handle_safety_state(runtime,dict(mission_id=1,status='off_path',safety_revision=1))
        assert runtime._safety_hold
        runtime.tick([2.5,2.8],1.)
        replacement=runtime.tick([2.5,2.8],1.1)
        assert replacement and replacement['reason']=='off_path' and replacement['replace_path']
        assert replacement['path'][0]==[2.5,2.8] and not runtime._safety_hold
        handle_safety_state(runtime,dict(mission_id=1,status='unsafe_tilt',safety_revision=1))
        assert not runtime._safety_hold  # Stale pre-replacement message.
        mapper.lethal[18,4]=True
        handle_safety_state(runtime,dict(mission_id=1,status='unsafe_tilt',safety_revision=2))
        runtime.tick([2.5,2.8],2.)
        error=runtime.tick([2.5,2.8],2.1)
        assert error['online_error'] and runtime.finished
        events=[r['event'] for r in runtime.safety_events]
        assert 'off_path' in events and 'safety_replanned' in events and 'unsafe_tilt' in events
    finally: runtime.close()
    print('safety recovery PASS: stop invalidates old work, replans from measured position, accepts replacement, ignores stale status and ends on no-path')


def test_ros_follower_recovery():
    class Twist:
        def __init__(self):
            self.linear=SimpleNamespace(x=0.);self.angular=SimpleNamespace(z=0.)
    stubs={'rclpy':SimpleNamespace(ok=lambda:True), 'rclpy.node':SimpleNamespace(Node=object),
        'rclpy.qos':SimpleNamespace(qos_profile_sensor_data=None),
        'geometry_msgs.msg':SimpleNamespace(PoseArray=object,Twist=Twist),
        'sensor_msgs.msg':SimpleNamespace(Imu=object),
        'std_msgs.msg':SimpleNamespace(String=SimpleNamespace,Empty=object)}
    runtime,mapper,_=setup_case()
    try:
        runtime.tick([2.,2.],0.);first=runtime.tick([2.,2.],.1)
        with patch.dict(sys.modules,stubs),tempfile.TemporaryDirectory() as output:
            path=ROOT/'ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py'
            spec=importlib.util.spec_from_file_location('thesis_bunker_mission._safety_follower_fixture',path)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            node=module.PathFollower.__new__(module.PathFollower)
            node.online=True;node.online_fixes='v1';node.map_id='fixture'
            node.pose=[2.,2.,0.,0.,0.,0.];node.imu=None;node.log=None;node.follower=None
            node.current_mission=None;node.n_replans=0;node.mission_id=0
            clock=[.1];states=[];velocities=[]
            node.get_parameter=lambda key:SimpleNamespace(value=output if key=='run_root' else 10.)
            node.get_clock=lambda:SimpleNamespace(now=lambda:SimpleNamespace(nanoseconds=int(clock[0]*1e9)))
            node.get_logger=lambda:SimpleNamespace(info=lambda _:None,error=lambda _:None)
            node.cmd=SimpleNamespace(publish=lambda msg:velocities.append((msg.linear.x,msg.angular.z)))
            node.state=SimpleNamespace(publish=lambda msg:states.append(json.loads(msg.data)))
            node.on_mission(SimpleNamespace(data=json.dumps(first)))
            original_log=node.log;original_stream=node.log.stream
            node.pose_received=time.monotonic();node.tick()
            node.pose[3]=np.deg2rad(26.);clock[0]=1.
            node.pose_received=time.monotonic();node.tick()
            assert states[-1]['status']=='unsafe_tilt' and velocities[-1]==(0.,0.)
            assert node.log is original_log and not original_stream.closed
            assert (node.log.folder/'safety_stops.csv').exists()
            assert handle_safety_state(runtime,states[-1])
            node.pose=[2.5,2.8,0.,0.,0.,0.]
            runtime.tick(node.pose[:2],1.);replacement=runtime.tick(node.pose[:2],1.1)
            node.on_mission(SimpleNamespace(data=json.dumps(replacement)))
            assert node.log is original_log and node.log.stream is original_stream
            clock[0]=1.1;node.pose_received=time.monotonic();node.tick()
            assert states[-1]['status']=='running' and states[-1]['safety_revision']==2
            node.stop()
    finally:runtime.close()
    print('ROS adapter PASS: real callbacks publish zero/status, preserve the open run, relay the stop and resume on a replanned path')


def test_diagnostics_and_pending_worker():
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from tapp.pointcloud_map_fine import PointCloudMapFine
    with tempfile.TemporaryDirectory() as temporary:
        z=np.zeros((24,24));prior=dict(tmap=TraversabilityMap(z,np.zeros(z.shape,bool)))
        runtime=make_safety_lidar_runtime(prior,PointCloudMapFine(z),online_fixes='v1',
            diagnostics=True,endpoint_policy='none',plan_log=Path(temporary)/'plans.csv',executor=Immediate())
        try:
            runtime.start(dict(id=1,map_id='fixture',order=[0,1],stops_cells=[[18,4]],points=[[9.,2.]]))
            runtime.tick([2.,2.],0.);command=runtime.tick([2.,2.],.1)
            assert command and isinstance(runtime.state['planner'],SafetyOnlinePlanner)
            assert runtime.stats['start_applications']==runtime.stats['goal_applications']==0
            assert not (Path(temporary)/'endpoint_masks').exists()
            assert (Path(temporary)/'safety_events.csv').exists()
        finally:runtime.close()
    runtime,mapper,_=setup_case()
    entered,release=threading.Event(),threading.Event()
    try:
        runtime.tick([2.,2.],0.);first=runtime.tick([2.,2.],.1)
        runtime.pending.result();runtime.pending=None
        old_pool=runtime.pool;runtime.pool=ThreadPoolExecutor(max_workers=1)
        original=runtime._work
        def delayed(state,position):
            entered.set()
            assert release.wait(10.)
            return original(state,position)
        runtime._work=delayed
        runtime.tick([2.,2.],.2);assert entered.wait(10.)
        runtime.safety_stop('off_path',revision=1)
        assert runtime.tick([3.,3.],1.) is None and runtime.sent==1
        release.set();runtime.pending.result(timeout=10.)
        runtime._work=original
        runtime.tick([3.,3.],1.1);runtime.pending.result(timeout=10.)
        command=runtime.tick([3.,3.],1.2)
        assert command['path'][0]==[3.,3.] and command['reason']=='off_path'
        assert command['revision']==2
        old_pool.shutdown(wait=True)
    finally:
        release.set();runtime.close()
    print('diagnostics/concurrency PASS: v1 records diagnostics without 028b relaxation; busy pre-stop work cannot hand off and recovery uses the latest pose')


def test_configuration():
    from ros2_jazzy.gz_checks import lidar_checks
    with tempfile.TemporaryDirectory() as tmp:
        manifest=lidar_checks.prepare_cases(Path(tmp)/'prepare',map_method='fine',online_fixes='v1',ground_estimate='non_obstacle')
        assert manifest['online_fixes']=='v1'
        assert manifest['online_safety']['join_timeout_sim_s']==10.
        assert manifest['online_safety']['max_tilt_deg']==25. and manifest['online_safety']['off_path_m']==.75
        with patch.object(sys,'argv',['lidar_checks.py','--online-fixes','v1']),patch.object(lidar_checks,'run_checks') as run:
            lidar_checks.main();assert run.call_args.kwargs['online_fixes']=='v1'
        try: lidar_checks.prepare_cases(Path(tmp)/'invalid',map_method='fine',online_fixes='v1',endpoint_policy='escape_component')
        except ValueError: pass
        else: raise AssertionError('task028 must not be enabled by v1')
    # Execute the production command extension with inert command arrays.
    tree=ast.parse(Path(lidar_checks.__file__).read_text())
    extension=next(n for n in ast.walk(tree) if isinstance(n,ast.If) and 'online_fixes' in ast.unparse(n.test)
                   and any(isinstance(k,ast.Name) and k.id=='commands' for statement in n.body for k in ast.walk(statement)))
    commands=[['gz'],['bridge'],['follower'],['planner']]
    exec(compile(ast.fix_missing_locations(ast.Module(body=[extension],type_ignores=[])),'<commands>','exec'),dict(commands=commands,manifest=dict(online_fixes='v1')))
    assert commands[-1][-2:]==commands[-2][-2:]==['-p','online_fixes:=v1']
    print('configuration PASS: v1 manifest/CLI and both ROS parameter commands; 028b unchanged and excluded from v1')

if __name__=='__main__':
    for test in (test_default_bytes,test_start_join,test_saved,test_join_timeout,test_known_changed,test_follower,test_safety_recovery,test_ros_follower_recovery,test_diagnostics_and_pending_worker,test_configuration): test()
    print('all online-safety tests passed; requirement 7 is checked by the complete conference/tests run')
