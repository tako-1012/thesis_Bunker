"""Fresh-world A*/TA*-S physical trials; scenario helpers need no ROS imports."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import list_patches,build_real
from tapp.exact_planners import run_planner_exact
from tapp.footprint import with_inflated_steep,blocked_endpoints
from tapp.metrics import evaluate
from tapp.mapfile import scenario_to_mapfile,load_map_file
from data_prep.export_gazebo import export_gazebo
from data_prep.export_maps import LAS_ATTRIBUTION
from experiments.gz_compare_report import summarize,MAP_MEASURES


def scenario_cases(planners=None):
    """Exactly task-009 seed-zero clean 200m start/goal paths, first six test patches."""
    planners=["A*","TA*-S"] if planners is None else list(planners)
    if not planners or len(set(planners))!=len(planners) or not set(planners)<={"A*","TA*-S","TA*-S+inflate"}:
        raise ValueError("invalid comparison methods")
    cases=[]
    for row in list_patches("test",dataset="shizuoka_beach_las")[:6]:
        sc=build_real(row["name"],200,0,dataset="shizuoka_beach_las")
        for planner in planners:
            plan_sc=with_inflated_steep(sc) if planner=="TA*-S+inflate" else sc
            blocked=blocked_endpoints(plan_sc["tmap"],sc["start"],[sc["goal"]]) if planner=="TA*-S+inflate" else []
            result=(dict(success=False,path=[],time=0.0) if blocked else
                    run_planner_exact("TA*-S" if planner=="TA*-S+inflate" else planner,plan_sc))
            if not result["success"] and planner!="TA*-S+inflate":raise RuntimeError("offline planning failed: "+row["name"]+" "+planner)
            measured=evaluate(result["path"],sc["tmap"]) if result["success"] else {k:None for k in MAP_MEASURES}
            cases.append(dict(patch=row["name"],planner=planner,scenario=sc,
                              start=list(sc["start"]),goal=list(sc["goal"]),
                              path_cells=np.asarray(result["path"],float) if result["success"] else np.empty((0,2)),
                              map_metrics={k:measured[k] for k in MAP_MEASURES},planning_s=result["time"],
                              planning_status="planned" if result["success"] else ("blocked_endpoint" if blocked else "no_path")))
    return cases


def prepare_cases(output,world_root=None,*,cases=None,planners=None):
    output=Path(output).resolve();(output/"maps").mkdir(parents=True,exist_ok=True)
    cases=scenario_cases(planners) if cases is None else cases
    manifest=dict(dataset="shizuoka_beach_las",side_m=200,seed=0,cases=[],world_exports={},world_errors={},world_max_pixels=4097)
    manifest["planners"]=list(dict.fromkeys(c["planner"] for c in cases))
    for case in cases:
        name=case["patch"];filename=f'real_las_{name}_200m_0.npz';path=output/"maps"/filename
        if not path.exists():
            scenario_to_mapfile(case["scenario"],path,name,name,"task019 LAS Ground, test, seed=0, clean",LAS_ATTRIBUTION)
        if world_root is not None and name not in manifest["world_exports"] and name not in manifest["world_errors"]:
            try:
                manifest["world_exports"][name]=export_gazebo(path,Path(world_root)/name,max_pixels=manifest["world_max_pixels"])
            except (ValueError,OSError) as exc:
                # Keep every scenario and its failure visible; never alter a map or
                # relax the exporter's reconstruction-error threshold.
                manifest["world_errors"][name]=type(exc).__name__+": "+str(exc)
        entry=dict(patch=name,planner=case["planner"],map_file="maps/"+filename,
                                      start=case["start"],goal=case["goal"],path_cells=case["path_cells"].tolist(),
                                      map_metrics=case["map_metrics"],planning_s=case["planning_s"],run_folder=None,
                                      planning_status=case.get("planning_status","planned"))
        if entry["planning_status"]!="planned":
            entry.update(error="planning: "+entry["planning_status"],termination=entry["planning_status"])
        if name in manifest["world_errors"]:
            entry["error"]="world export failed: "+manifest["world_errors"][name]
        manifest["cases"].append(entry)
    return manifest


def run_checks(output,planners=None):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String,Empty
    from thesis_bunker_gz.model import make_model
    from thesis_bunker_mission.transport import pose3d
    import scipy

    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    if (output/"manifest.json").exists():
        raise FileExistsError("choose a new output folder; existing recordings will not be overwritten")

    class Observer(Node):
        def __init__(self):
            super().__init__("compare_checks_observer")
            self.t=self.pose=self.state=None
            self.create_subscription(Clock,"/clock",self.clock,qos_profile_sensor_data)
            self.create_subscription(PoseArray,"/ground_truth",self.ground,qos_profile_sensor_data)
            self.create_subscription(String,"/mission/state",self.status,10)
            self.command=self.create_publisher(String,"/mission/command",10)
            self.stop=self.create_publisher(Empty,"/mission/stop",10)
        def clock(self,msg):self.t=msg.clock.sec+msg.clock.nanosec/1e9
        def ground(self,msg):
            if msg.poses:self.pose=pose3d(msg.poses[0])
        def status(self,msg):self.state=json.loads(msg.data)
        def wait_until(self,predicate,wall_limit=120):
            deadline=time.monotonic()+wall_limit
            while not predicate():
                if time.monotonic()>deadline:raise TimeoutError("missing/stalled ROS or Gazebo telemetry")
                rclpy.spin_once(self,timeout_sec=.05)

    rclpy.init()
    try:
        with tempfile.TemporaryDirectory(prefix="thesis-gz-compare-worlds-") as world_tmp:
            manifest=prepare_cases(output,world_tmp,planners=planners)
            manifest["environment"]=dict(image=os.environ.get("THESIS_ROS_IMAGE","thesis/jazzy-gz:1"),
                gazebo=subprocess.check_output(["gz","sim","--versions"],text=True).strip(),
                python=sys.version,numpy=np.__version__,scipy=scipy.__version__)
            def save():
                (output/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
            save()
            for number,case in enumerate(manifest["cases"],1):
                label=case["patch"]+"_"+case["planner"].replace("*","star")
                if case.get("error"):
                    print(f'{number}/{len(manifest["cases"])} {label}: {case["error"]}',flush=True)
                    continue
                folder=output/"raw"/label;folder.mkdir(parents=True,exist_ok=True)
                observer=Observer();processes=[];streams=[]
                try:
                    with tempfile.TemporaryDirectory(prefix="thesis-gz-compare-run-") as runtime:
                        runtime=Path(runtime);world=Path(world_tmp)/case["patch"]/"world.sdf"
                        tree=ET.parse(world);w=tree.find("world")
                        w.find("physics/real_time_factor").text="1"
                        for uri in tree.findall(".//heightmap/uri"):uri.text=(world.parent/"heightmap.png").as_uri()
                        sc=load_map_file(output/case["map_file"])
                        model=ET.parse(make_model(runtime/"bunker.sdf",mass_kg=sc["tmap"].robot.mass_kg)).find("model")
                        x,y=np.array(case["start"])*RESOLUTION;z=float(sc["tmap"].elev[tuple(case["start"])] )+.1
                        ET.SubElement(model,"pose").text=f"{x} {y} {z} 0 0 0";w.append(model)
                        tree.write(runtime/"world.sdf",encoding="utf-8",xml_declaration=True)
                        map_id="file/"+Path(case["map_file"]).name
                        commands=[["gz","sim","-s","-r","--seed","0",str(runtime/"world.sdf")],
                                  ["ros2","run","ros_gz_bridge","parameter_bridge","--ros-args","-p","config_file:="+str(ROOT/"ros2_jazzy/src/thesis_bunker_gz/config/bridge.yaml")],
                                  ["ros2","run","thesis_bunker_mission","path_follower","--ros-args","-p","use_sim_time:=true","-p","map_id:="+map_id,"-p","run_root:="+str(folder/"runs")]]
                        for i,command in enumerate(commands):
                            stream=(folder/f'process_{i}.log').open("w");streams.append(stream)
                            processes.append(subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True))
                        def ready():
                            if any(p.poll() is not None for p in processes):raise RuntimeError("a simulator/bridge/follower process exited before telemetry; inspect process logs")
                            return observer.t is not None and observer.pose is not None and observer.state is not None and observer.command.get_subscription_count()>0
                        observer.wait_until(ready)
                        settled=observer.t+5;observer.wait_until(lambda:observer.t>=settled)
                        case["start_pose_recorded"]=observer.pose
                        path=np.asarray(case["path_cells"])*RESOLUTION
                        mission=dict(id=1,map_id=map_id,map_file=str((output/case["map_file"]).resolve()),
                                     patch=case["patch"],planner=case["planner"],data_source="gazebo",path=path.tolist(),
                                     points=[(np.array(case["goal"])*RESOLUTION).tolist()],lookahead_m=1.)
                        message=String();message.data=json.dumps(mission);observer.command.publish(message)
                        began=observer.t;limit=max(120,6*float(np.linalg.norm(np.diff(path,axis=0),axis=1).sum())+60)
                        terminal={"completed","stuck","no_path","pose_timeout","invalid_mission","time_reset"}
                        observer.wait_until(lambda:(observer.state and observer.state.get("mission_id")==1 and observer.state["status"] in terminal) or observer.t-began>limit or any(p.poll() is not None for p in processes),wall_limit=max(180,limit*3))
                        if any(p.poll() is not None for p in processes):raise RuntimeError("a simulator/bridge/follower process exited during the trial")
                        case["termination"]="simulation_timeout" if observer.t-began>limit else (observer.state or {}).get("status","missing_state")
                        observer.stop.publish(Empty());ended=observer.t+.2
                        observer.wait_until(lambda:observer.t>=ended,wall_limit=10)
                        logs=sorted((folder/"runs").glob("*/mission.json"))
                        if not logs:raise RuntimeError("no durable follower recording")
                        case["run_folder"]=str(logs[-1].parent.relative_to(output))
                        print(f'{number}/{len(manifest["cases"])} {label}: {case["termination"]}',flush=True)
                except Exception as exc:
                    case["error"]=type(exc).__name__+": "+str(exc)
                finally:
                    for process in reversed(processes):
                        if process.poll() is None:
                            os.killpg(process.pid,signal.SIGINT)
                            try:process.wait(timeout=10)
                            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                    for stream in streams:stream.close()
                    if not case["run_folder"]:
                        logs=sorted((folder/"runs").glob("*/mission.json"))
                        if logs:case["run_folder"]=str(logs[-1].parent.relative_to(output))
                    observer.destroy_node();save()
            data,_=summarize(output)
            if any(c.get("error") and c.get("planning_status")=="planned" for c in manifest["cases"]) or data.status.eq("記録不完全").any():raise RuntimeError("some physical trials were not completed; inspect manifest.json")
    finally:rclpy.shutdown()


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--output",type=Path,default=ROOT/"results/gazebo_compare")
    parser.add_argument("--planners",nargs="+",choices=["A*","TA*-S","TA*-S+inflate"])
    args=parser.parse_args();run_checks(args.output,args.planners)
