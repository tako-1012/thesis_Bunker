"""Task027 ROS-free regression, mount, fusion, depth and geometry checks."""

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import numpy as np
from scipy.spatial.transform import Rotation
from tapp.sensor_geometry import REAL_MOUNTS, DepthCameraSpec, SensorMount, sensor_configuration, transform_sensor_points
from tapp.pointcloud_map_fine import PointCloudMapFine
from tapp.pointcloud_map_multi import PointCloudMapMulti
from ros2_jazzy.gz_checks.lidar_map import make_pointcloud_map, fine_protocol, sensor_bridge_config

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ros2_jazzy/src/thesis_bunker_gz'))
from thesis_bunker_gz.model import make_model
from thesis_bunker_gz.lidar import LidarSpec
from experiments.sensor_coverage import visible, intervals


def local_cloud(world, pose, mount):
    body = (np.asarray(world)-pose[:3]) @ Rotation.from_euler('xyz',pose[3:]).as_matrix()
    return (body-mount.xyz) @ Rotation.from_euler('xyz',mount.rpy).as_matrix()


def raises(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('expected ValueError')


def test_legacy_bytes():
    expected=json.loads((ROOT/'results/real_sensors/legacy_sha256.json').read_text())
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for name,lidar in [('model.sdf',False),('model_lidar.sdf',True)]:
            path=make_model(root/name,lidar=lidar)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==expected[name]
        mapper=make_pointcloud_map(np.zeros((40,40)),map_method='fine')
        assert type(mapper) is PointCloudMapFine
        mapper.update(np.array([[3.01,3.01,-.4]]*3+[[3.,3.,-.8]]*20),[2,2,0,0,0,0])
        mapper.save(root/'fine.npz')
        assert hashlib.sha256((root/'fine.npz').read_bytes()).hexdigest()==expected['fine.npz']
    assert fine_protocol()['real_time_factor']==.3
    print('PASS legacy model SDF (with/without LiDAR) and fine-map NPZ SHA256 match pre-change bytes')


def test_preset_sdf():
    expected={'lidar':((-.24,0,1.05),(0,0,0)),
              'camera1':((.4,.27,.41),(0,0,.345)), 'camera2':((.4,-.27,.41),(0,0,-.345))}
    with tempfile.TemporaryDirectory() as temp:
        tree=ET.parse(make_model(Path(temp)/'real.sdf',sensor_preset='real_bunker',depth_cameras=True))
        for name,(xyz,rpy) in expected.items():
            node=tree.find(f".//sensor[@name='{name}']")
            np.testing.assert_allclose(list(map(float,node.findtext('pose').split())),[*xyz,*rpy],atol=1e-15)
            assert node.findtext('gz_frame_id')==name
        lidar=tree.find(".//sensor[@name='lidar']")
        assert float(lidar.findtext('lidar/range/min'))==.9
        assert float(lidar.findtext('lidar/range/max'))==30
        assert int(lidar.findtext('lidar/scan/vertical/samples'))==16
        assert int(lidar.findtext('lidar/scan/horizontal/samples'))==1800
        for name in ('camera1','camera2'):
            node=tree.find(f".//sensor[@name='{name}']")
            assert node.get('type')=='depth_camera'
            assert node.findtext('topic')=='/'+name
            camera=node.find('camera'); spec=DepthCameraSpec()
            assert int(camera.findtext('image/width'))==214 and int(camera.findtext('image/height'))==125
            assert float(camera.findtext('clip/near'))==.6 and float(camera.findtext('clip/far'))==6
            assert float(node.findtext('update_rate'))==10
            assert float(camera.findtext('noise/stddev'))==.01
            assert camera.find('.//intrinsics') is None
            horizontal=float(camera.findtext('horizontal_fov'))
            np.testing.assert_allclose(np.rad2deg(horizontal),87)
            vertical=np.rad2deg(2*np.arctan(spec.height/spec.width*np.tan(horizontal/2)))
            assert abs(vertical-58) <= .1
        one=ET.parse(make_model(Path(temp)/'lidar.sdf',sensor_preset='real_bunker'))
        assert one.find(".//sensor[@name='camera1']") is None
    left,right=REAL_MOUNTS['camera1'],REAL_MOUNTS['camera2']
    np.testing.assert_array_equal(right.xyz,[left.xyz[0],-left.xyz[1],left.xyz[2]])
    assert right.rpy[2]==-left.rpy[2]
    raises(lambda: make_model('/tmp/task027-invalid.sdf',sensor_preset='bad'))
    print('PASS real preset mounts, symmetry, unchanged LiDAR spec and camera FOV/ranges without intrinsics')


def test_a2_projection_and_other_values():
    baseline=ROOT/'results/real_sensors/a2/verification/legacy'
    old_spec=json.loads((baseline/'depth_camera_spec.json').read_text())
    expected_spec=dict(old_spec,width=214,height=125)
    assert asdict(DepthCameraSpec())==expected_spec
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        for name,kwargs in [('default.sdf',{}),('lidar.sdf',dict(lidar=True)),
                            ('real_lidar.sdf',dict(sensor_preset='real_bunker'))]:
            assert make_model(root/name,**kwargs).read_bytes()==(baseline/name).read_bytes(),name
        actual=make_model(root/'depth2.sdf',sensor_preset='real_bunker',depth_cameras=True)
        tree=ET.parse(actual)
        assert tree.find('.//intrinsics') is None
        expected=ET.parse(baseline/'depth2.sdf')
        for name in ('camera1','camera2'):
            old=expected.find(f".//sensor[@name='{name}']/camera")
            old.find('image/width').text='214';old.find('image/height').text='125'
            old.remove(old.find('lens'))
            camera=tree.find(f".//sensor[@name='{name}']/camera")
            width=int(camera.findtext('image/width'));height=int(camera.findtext('image/height'))
            horizontal=float(camera.findtext('horizontal_fov'))
            vertical=float(np.rad2deg(2*np.arctan(height/width*np.tan(horizontal/2))))
            assert (width,height)==(214,125) and abs(vertical-58) <= .1
            print(f'A2 {name}: image={width}x{height}, horizontal_deg={np.rad2deg(horizontal):.12f}, vertical_deg={vertical:.12f}, intrinsics=absent')
        ET.indent(expected)
        assert actual.read_bytes()==ET.tostring(expected.getroot(),encoding='utf-8',xml_declaration=True)
    print('PASS A2: three camera-free SDFs byte-identical; depth SDF/spec change only prescribed resolution and intrinsics')


def test_full_rigid_transform():
    mount=SensorMount((.4,-.27,.76),(.12,-.08,-.345))
    pose=np.array([4.,5.,.2,.1,-.2,.7])
    points=np.array([[1.,.1,.2],[2.,-.3,-.2]])
    transform=np.eye(4);transform[:3,:3]=Rotation.from_euler('xyz',pose[3:]).as_matrix();transform[:3,3]=pose[:3]
    extrinsic=np.eye(4);extrinsic[:3,:3]=Rotation.from_euler('xyz',mount.rpy).as_matrix();extrinsic[:3,3]=mount.xyz
    expected=(transform@extrinsic@np.c_[points,np.ones(len(points))].T).T[:,:3]
    np.testing.assert_allclose(transform_sensor_points(points,pose,mount),expected,atol=1e-14)
    raises(lambda: transform_sensor_points(points,[0]*5,mount))
    raises(lambda: SensorMount((0,0,float('nan'))))
    raises(lambda: DepthCameraSpec(width=0).validate())
    print('PASS arbitrary sensor/model roll-pitch-yaw and translation match independent homogeneous transform')


def test_ground_box_and_attribution():
    pose=np.array([5.,5.,0.,0.,0.,.25])
    mapper=PointCloudMapMulti(np.zeros((40,40)))
    # Dense level ground, projected through each outward camera independently.
    for sensor in ('camera1','camera2'):
        mount=REAL_MOUNTS[sensor]
        local=np.array([[x,y,-.76] for x in (2.,2.5,3.) for y in (-.2,0.,.2)])
        world=transform_sensor_points(local,pose,mount)
        assert np.allclose(world[:,2],0)
        result=mapper.update(local,pose,sensor=sensor,stamp=1.)
        assert result['accepted_points']==len(local)
    assert mapper.seen.any() and not mapper.fine_obstacle.any()
    np.testing.assert_allclose(mapper.elev,0,atol=1e-14)
    # Two LiDAR returns and one camera return share a single fine-cell history.
    world=np.array([[7.01,5.51,.4]]*2)
    mapper.update(local_cloud(world,pose,REAL_MOUNTS['lidar']),pose,sensor='lidar',stamp=2.)
    assert not mapper.fine_obstacle.any()
    mapper.update(local_cloud(world[:1],pose,REAL_MOUNTS['camera1']),pose,sensor='camera1',stamp=2.1)
    assert mapper.fine_obstacle.any() and mapper.lethal[14,11]
    record=mapper.first_detections[0]
    assert record['supporting_returns']==dict(lidar=2,camera1=1,camera2=0)
    assert record['triggering_sensor']=='camera1' and record['stamp_sim_s']==2.1
    before=mapper.fine_inflated.copy()
    mapper.update(local_cloud(world,pose,REAL_MOUNTS['camera2']),pose,sensor='camera2',stamp=2.2)
    np.testing.assert_array_equal(mapper.fine_inflated,before)
    assert len(mapper.first_detections)==1
    with tempfile.TemporaryDirectory() as temp:
        path=Path(temp)/'map.npz';mapper.save(path)
        data=json.loads(Path(str(path)+'.sensors.json').read_text())
        assert data['counters']['camera1']['first_detected_cells']==1
        assert data['first_detections'][0]==record
    print('PASS both outward cameras: ground/box registration, shared 2+1 evidence, one inflation and saved provenance')


def test_blind_near_boxes():
    pose=np.array([5.,5.,0.,0.,0.,0.])
    for distance in (1.5,2.,3.):
        assert not visible(distance,0,.4,'lidar_real')
        assert visible(distance,0,.4,'lidar_real+depth2')
        for sensor in ('camera1','camera2'):
            mapper=PointCloudMapMulti(np.zeros((40,40)))
            world=np.array([[5+distance+.01,5.01,.4]]*3)
            result=mapper.update(local_cloud(world,pose,REAL_MOUNTS[sensor]),pose,sensor=sensor)
            assert result['accepted_points']==3
            assert mapper.detected_obstacle[int(round((5+distance)*2)),10]
    # At 4m a .3m target can already intersect the lowest real LiDAR beam;
    # 1m also remains blind to these camera mounts. Do not claim all 1-4m visible.
    assert visible(4.,0,.3,'lidar_real')
    assert not visible(1.,0,.3,'lidar_real+depth2')
    print('PASS synthetic camera boxes in LiDAR blind zone at 1.5/2/3m; residual 1m blind zone disclosed')


def test_sensor_filters_and_fine_rule():
    pose=np.array([5.,5.,0.,0.,0.,0.])
    mapper=PointCloudMapMulti(np.zeros((40,40)))
    rejected=np.array([[.5,0,0],[7,0,0],[2,5,0],[2,0,5],[np.nan,0,0],[np.inf,0,0]])
    assert mapper.update(rejected,pose,sensor='camera1')['accepted_points']==0
    assert mapper.update(np.array([[.8,0,0],[30,0,0]]),pose,sensor='lidar')['accepted_points']==0
    raises(lambda: mapper.update(np.zeros((1,3)),pose,sensor='missing'))
    raises(lambda: PointCloudMapMulti(np.zeros((10,10)),sensors='legacy'))
    raises(lambda: PointCloudMapMulti(np.zeros((10,10)),obstacle_height_m=.2))
    # All map arrays must equal the unchanged fine engine fed registered points.
    reference=PointCloudMapFine(np.zeros((40,40)),min_range_m=0,max_range_m=1e12)
    world=np.array([[7.01,5.01,.4]]*3+[[7.,5.,0.]]*16)
    sensor='camera2'; points=local_cloud(world,pose,REAL_MOUNTS[sensor])
    mapper=PointCloudMapMulti(np.zeros((40,40)))
    mapper.update(points,pose,sensor=sensor)
    registered=transform_sensor_points(points,pose,REAL_MOUNTS[sensor])
    reference.update(registered-[0,0,.8],[0]*6)
    for name in ('elev','seen','lethal','detected_obstacle','fine_obstacle','fine_inflated'):
        assert getattr(mapper,name).tobytes()==getattr(reference,name).tobytes(),name
    print('PASS per-sensor range/FOV/finite filtering and byte-identical task023 fusion/inflation for registered input')


def test_manifest_and_wrapper():
    from ros2_jazzy.gz_checks.lidar_checks import prepare_cases
    bridge=(ROOT/'ros2_jazzy/gz_checks/lidar_bridge.yaml').read_text()
    assert sensor_bridge_config(bridge)==sensor_bridge_config(bridge,'lidar_real')==bridge
    combined=sensor_bridge_config(bridge,'lidar_real+depth2')
    assert combined.startswith(bridge)
    assert combined.count('ros_topic_name: /camera')==2
    assert combined.count('gz_type_name: gz.msgs.PointCloudPacked')==3
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        for mode in ('lidar_real','lidar_real+depth2'):
            manifest=prepare_cases(root/mode,map_method='fine',sensors=mode)
            assert manifest['lidar_spec']==asdict(LidarSpec(min_range_m=.9))
            assert manifest['sensor_height_m']==1.4
            assert manifest['sensor']==manifest['sensors']==mode
            config=manifest['sensor_configuration']
            assert config==sensor_configuration(mode)
            assert len(config['mounts'])==(3 if mode.endswith('depth2') else 1)
            if mode.endswith('depth2'):
                assert config['depth_camera_spec']['width']==214 and config['depth_camera_spec']['height']==125
            selected=make_pointcloud_map(np.zeros((10,10)),map_method='fine',sensors=mode)
            assert isinstance(selected,PointCloudMapMulti)
        raises(lambda: prepare_cases(root/'bad',sensors='lidar_real'))
        binary=root/'docker'
        binary.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["TASK027_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n');binary.chmod(0o755)
        env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],TASK027_ARGS=str(root/'args.json'))
        args=['--map','fine','--sensors','lidar_real+depth2']
        subprocess.run(['bash',str(ROOT/'ros2_jazzy/gz_checks/run_lidar_checks.sh'),str(root/'wrapper'),*args],env=env,check=True)
        assert json.loads((root/'args.json').read_text())[-len(args):]==args
    print('PASS manifest records all real specs/mounts; explicit fine selection; Docker wrapper forwards sensor flags')


def test_a2_wrapper_protocol_environment():
    reference=json.loads((ROOT/'results/real_sensors/a2/verification/legacy/wrapper_args.json').read_text())
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        binary=root/'docker'
        binary.write_text('#!/usr/bin/env python3\nimport os,sys,json\nopen(os.environ["TASK027A2_ARGS"],"w").write(json.dumps(sys.argv[1:]))\n')
        binary.chmod(0o755)
        env=dict(os.environ,PATH=str(root)+os.pathsep+os.environ['PATH'],TASK027A2_ARGS=str(root/'args.json'))
        for name in ('THESIS_FINE_PROTOCOL','THESIS_ONLY_PATCH','THESIS_REAL_TIME_FACTOR','THESIS_STALE_TIMEOUT_S',
                     'THESIS_ROS_IMAGE','THESIS_ROS_DOMAIN_ID','THESIS_SOFTWARE_RENDERING'):
            env.pop(name,None)
        variations=[{}, {'THESIS_FINE_PROTOCOL':'rtf_check'}, {'THESIS_ONLY_PATCH':'08OB86_-0205'},
                    {'THESIS_FINE_PROTOCOL':'rtf_check','THESIS_ONLY_PATCH':'08OB86_-0205'},
                    {'THESIS_FINE_PROTOCOL':'','THESIS_ONLY_PATCH':''}]
        for label,extra in [('default',[]),('fine',['--map','fine','--sensors','lidar_real+depth2'])]:
            for index,values in enumerate(variations):
                output=root/(label+str(index))
                subprocess.run(['bash',str(ROOT/'ros2_jazzy/gz_checks/run_lidar_checks.sh'),str(output),*extra],
                               env=dict(env,**values),check=True,capture_output=True)
                args=json.loads((root/'args.json').read_text())
                args=[arg.replace(str(ROOT),'<CONFERENCE>').replace(str(output),'<OUTPUT>') for arg in args]
                args=['THESIS_OUTPUT_UID=<UID>' if arg.startswith('THESIS_OUTPUT_UID=') else
                      'THESIS_OUTPUT_GID=<GID>' if arg.startswith('THESIS_OUTPUT_GID=') else arg for arg in args]
                added=[]
                for name in ('THESIS_FINE_PROTOCOL','THESIS_ONLY_PATCH'):
                    if name in values:
                        added.extend(['-e',name+'='+values[name]])
                expected=reference[label][:5]+added+reference[label][5:]
                assert json.dumps(args).encode()==json.dumps(expected).encode(),(label,values)
    print('PASS A2 wrapper: unset flags preserve full legacy argv bytes; individual/both/empty supplied values forwarded (fake Docker only)')


def test_coverage():
    near=(1.4-.3)/np.tan(np.deg2rad(15))
    assert not visible(near-.24-.01,0,.3,'lidar_real')
    assert visible(near-.24+.01,0,.3,'lidar_real')
    # A discrete-beam gap survives beyond the continuous close coverage.
    assert not visible(12.-.24,0,.3,'lidar_real')
    assert not visible(-2.,0,.3,'lidar_real+depth2')
    assert visible(2.,1.,.4,'lidar_real+depth2')==visible(2.,-1.,.4,'lidar_real+depth2')
    assert intervals(np.array([0,1,1,0,1],bool),np.arange(5.))==[[1.,2.],[4.,4.]]
    print('PASS analytic 4.105m LiDAR near bound, discrete-beam gap, rear blind zone and camera symmetry')


def test_ros_adapter_without_ros():
    """Run actual ROS adapter methods with a minimal transport harness."""
    import ast
    import time
    from concurrent.futures import Future
    from types import SimpleNamespace as Obj
    from tapp.pointcloud_map import decode_xyz
    source=ROOT/'ros2_jazzy/gz_checks/lidar_planner.py'
    tree=ast.parse(source.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LidarPlannerNode')
    cls.bases=[]
    names={'stamp','on_cloud','_update','_collect','multi_map_tick'}
    cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    scope=dict(time=time,np=np,hashlib=hashlib,decode_xyz=decode_xyz,json=json,String=Obj)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[])),str(source),'exec'),scope)
    node=scope['LidarPlannerNode']()
    node.multi=True;node.mapping_finished=False
    node.mapper=PointCloudMapMulti(np.zeros((30,30)))
    node.pending_by_sensor={};node.received_clouds=node.dropped=0
    node.source_state={name:dict(received=0,processed=0,queue_drops=0,last_stamp=None,error='') for name in REAL_MOUNTS}
    node.future=None;node.last_error=node.terminal_sensor_error=''
    node.last_cloud_stamp=None;node.observed_cells=0;node.stale_timeout_s=1.
    node.get_clock=lambda:Obj(now=lambda:Obj(nanoseconds=1_100_000_000))
    pose=np.array([4.,4.,0.,0.,0.,0.]);stamps=[];messages=[];rows=[]
    node.poses=Obj(at=lambda stamp:(stamps.append(stamp) or pose))
    node.sensor_state=Obj(publish=lambda message:messages.append(json.loads(message.data)))
    node.log=Obj(write=rows.append)
    node.update_fields=['stamp','status','error','version','input_points','accepted_points','observed_cells','update_s','decode_s','queue_drops','cloud_sha256','sensor','new_obstacle_cells']
    def submit(fn,*args):
        future=Future()
        try: future.set_result(fn(*args))
        except Exception as exc: future.set_exception(exc)
        return future
    node.map_pool=Obj(submit=submit)
    with tempfile.TemporaryDirectory() as temp:
        node.folder=Path(temp)
        world=np.array([[6.01,4.01,.4]]*3)
        for name,mount in REAL_MOUNTS.items():
            data=local_cloud(world,pose,mount).astype('<f4').tobytes()
            message=Obj(header=Obj(frame_id=name,stamp=Obj(sec=1,nanosec=0)),
                fields=[Obj(name=axis,offset=i*4,datatype=7,count=1) for i,axis in enumerate('xyz')],
                data=data,point_step=12,row_step=36,width=3,height=1,is_bigendian=False)
            node.on_cloud(message,name)
            if name=='camera1': node.on_cloud(message,name)
        assert len(node.pending_by_sensor)==3 and node.dropped==1
        for _ in range(4): node.multi_map_tick()
        assert [row['sensor'] for row in rows]==['lidar','camera1','camera2']
        assert all(row['status']=='ok' for row in rows),rows
        assert stamps==[1.,1.,1.]
        assert messages[-1]['ready'] and not messages[0]['ready']
        assert all(state['processed']==1 for state in node.source_state.values())
        assert all((node.folder/name).exists() for name in ('first_cloud.npz','first_cloud_camera1.npz','first_cloud_camera2.npz'))
        node.get_clock=lambda:Obj(now=lambda:Obj(nanoseconds=3_000_000_000))
        node.multi_map_tick()
        assert not messages[-1]['ready']
        message.header.frame_id='camera1_optical'
        raises(lambda:node._update(message,pose,'camera2'))
    print('PASS actual ROS adapter: bounded queues, fair sources, stamped transforms, logs and freshness (transport mocked)')


if __name__=='__main__':
    for test in (test_legacy_bytes,test_preset_sdf,test_a2_projection_and_other_values,test_full_rigid_transform,test_ground_box_and_attribution,
                 test_blind_near_boxes,test_sensor_filters_and_fine_rule,test_manifest_and_wrapper,test_a2_wrapper_protocol_environment,
                 test_coverage,test_ros_adapter_without_ros):
        test()
    print('all real sensor tests passed (synthetic/geometry only; Gazebo not run)')
