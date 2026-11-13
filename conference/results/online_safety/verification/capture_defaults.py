"""Pre-task034 deterministic runtime/follower/manifest bytes; no ROS processes."""
import hashlib,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'ros2_jazzy/src/thesis_bunker_mission'))
from tapp.traversability import TraversabilityMap
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.follower import MissionFollower
from tapp.run_log import RunLog
from tapp.prior import PriorMap
from tests.test_endpoint_policy import Immediate
from thesis_bunker_mission.online_runtime import AsyncOnlineMission
from ros2_jazzy.gz_checks.endpoint_runtime import make_lidar_runtime
from ros2_jazzy.gz_checks.lidar_checks import prepare_cases

def capture(explicit=False):
    result={}
    with tempfile.TemporaryDirectory() as temporary, patch('time.perf_counter',return_value=1.):
        root=Path(temporary); z=np.zeros((24,24)); mask=np.zeros(z.shape,bool)
        tm=TraversabilityMap(z,mask); prior=dict(tmap=tm)
        for kind in ('async','lidar','diagnostics'):
            folder=root/kind;folder.mkdir()
            if kind=='async':
                if explicit:
                    from thesis_bunker_mission.online_safety import make_async_runtime
                    runtime=make_async_runtime(tm,tm,PriorMap(tm.cost,tm.lethal,.5),executor=Immediate(),online_fixes='none')
                else: runtime=AsyncOnlineMission(tm,tm,PriorMap(tm.cost,tm.lethal,.5),executor=Immediate())
                mission=dict(id=1,map_id='fixture',points=[[8.,2.]],path=[[2.,2.],[8.,2.]])
            else:
                mapper=PointCloudMapFine(z);mapper.update(np.array([[2.,2.,-.8]]),np.zeros(6))
                creator=make_lidar_runtime
                options={}
                if explicit:
                    from ros2_jazzy.gz_checks.safety_runtime import make_safety_lidar_runtime
                    creator=make_safety_lidar_runtime;options['online_fixes']='none'
                runtime=creator(prior,mapper,plan_log=folder/'plans.csv',executor=Immediate(),diagnostics=kind=='diagnostics',**options)
                mission=dict(id=1,map_id='fixture',order=[0,1],start_cells=[4,4],stops_cells=[[16,4]],points=[[8.,2.]],path=[[2.,2.],[8.,2.]])
            commands=[];runtime.start(mission)
            for t,pos in [(0.,[2.,2.]),(.1,[2.,2.]),(.2,[2.5,2.]),(.3,[3.,2.])]:
                commands.append(runtime.tick(pos,t))
            runtime.close()
            result[kind]=dict(commands=json.dumps(commands,sort_keys=True),
                files={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()})
        follower=MissionFollower([[0.,0.],[10.,0.]])
        if explicit:
            from tapp.online_safety import make_follower
            follower=make_follower([[0.,0.],[10.,0.]],online_fixes='none')
        log=RunLog(dict(id=1,map_id='fixture'),root/'follower')
        commands=[]
        for t,pose in [(0.,[0.,0.,0.]),(1.,[1.,0.,0.]),(2.,[2.,.2,0.])]:
            v,w,done=follower.step(t,pose);commands.append([v,w,done,follower.status])
            log.write(follower.log_row(t,[*pose[:2],0.,0.,0.,pose[2]],None,v,w))
        log.close('stopped')
        result['follower']=dict(commands=commands,files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in log.folder.iterdir()})
        for mode,kwargs in [('coarse',{}),('fine',dict(map_method='fine')),('real',dict(map_method='fine',sensors='lidar_real+depth2'))]:
            if explicit: kwargs['online_fixes']='none'
            manifest=prepare_cases(root/mode,**kwargs)
            full=hashlib.sha256((root/mode/'manifest.json').read_bytes()).hexdigest()
            environment=manifest['input_environment']
            manifest['input_environment']={}
            normalized=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
            result[mode]=dict(full_sha256=full,without_environment_sha256=hashlib.sha256(normalized).hexdigest(),environment=environment)
    return result
if __name__=='__main__': print(json.dumps(capture(),indent=2,sort_keys=True))
