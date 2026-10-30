"""Physical stale-map comparison with the same five goals, without synthetic measurements."""

import argparse
import csv
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.mapfile import load_map_file
from tapp.real_beach import list_patches
from tapp.tour import sample_waypoints
from tapp.online_mission import ordered_tour, run_fixed_mission
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION


def run_checks(output):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String, Empty
    from thesis_bunker_gz.model import make_model
    from thesis_bunker_mission.transport import pose3d

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    stem = "real_las_08OB87_-0206_200m_0"
    truth_file = ROOT / "maps" / (stem + "_debris.npz")
    prior_file = ROOT / "maps" / (stem + ".npz")
    truth, prior = load_map_file(truth_file), load_map_file(prior_file)
    index = next(
        i
        for i, r in enumerate(list_patches(dataset="shizuoka_beach_las"))
        if r["name"] == "08OB87_-0206"
    )
    points = sample_waypoints(truth, 12, np.random.SeedSequence([0, 3000, 200, index]))[
        :5
    ]
    tour = ordered_tour(prior["tmap"], truth["start"], points)
    fixed = run_fixed_mission(prior["tmap"], truth["start"], tour["stops"])
    if not fixed["success"]:
        raise RuntimeError("prior-only planning failed")
    world = ROOT / "gazebo_worlds/real_las_08OB87_-0206_debris/world.sdf"
    result = dict(
        truth_map=truth_file.name,
        prior_map=prior_file.name,
        sense_radius_m=10,
        points=(np.asarray(points) * RESOLUTION).tolist(),
        seed=0,
        sensing="perfect radius visibility of truth map; no LiDAR, occlusion or measurement error",
        gazebo_version=subprocess.check_output(
            ["gz", "sim", "--versions"], text=True
        ).strip(),
        runs=[],
        errors=[],
    )
    rclpy.init()

    class Observer(Node):
        def __init__(self):
            super().__init__("online_checks_observer")
            self.t = None
            self.pose = None
            self.state = None
            self.history = []
            self.create_subscription(
                Clock, "/clock", self.clock, qos_profile_sensor_data
            )
            self.create_subscription(
                PoseArray, "/ground_truth", self.ground_truth, qos_profile_sensor_data
            )
            self.create_subscription(String, "/mission/state", self.on_state, 10)
            self.command = self.create_publisher(String, "/mission/command", 10)
            self.stop = self.create_publisher(Empty, "/mission/stop", 10)

        def clock(self, msg):
            self.t = msg.clock.sec + msg.clock.nanosec / 1e9

        def ground_truth(self, msg):
            if msg.poses:
                self.pose = pose3d(msg.poses[0])
                self.history.append(self.pose)

        def on_state(self, msg):
            self.state = json.loads(msg.data)

        def wait_until(self, predicate, wall_limit=120):
            deadline = time.monotonic() + wall_limit
            while not predicate():
                if time.monotonic() > deadline:
                    raise TimeoutError("missing/stalled ROS or Gazebo telemetry")
                rclpy.spin_once(self, timeout_sec=0.05)

    for online in [False, True]:
        label = "online" if online else "fixed"
        folder = output / label
        folder.mkdir(exist_ok=True)
        processes = []
        streams = []
        observer = Observer()
        try:
            with tempfile.TemporaryDirectory(prefix="online-gz-") as tmp:
                tmp = Path(tmp)
                tree = ET.parse(world)
                w = tree.find("world")
                w.find("physics/real_time_factor").text = "1"
                for uri in tree.findall(".//heightmap/uri"):
                    uri.text = (world.parent / "heightmap.png").as_uri()
                model = ET.parse(
                    make_model(tmp / "bunker.sdf", mass_kg=truth["tmap"].robot.mass_kg)
                ).find("model")
                x, y = truth["start_xy"]
                z = float(truth["tmap"].elev[truth["start"]]) + 0.1
                ET.SubElement(model, "pose").text = f"{x} {y} {z} 0 0 0"
                w.append(model)
                tree.write(tmp / "world.sdf", encoding="utf-8", xml_declaration=True)
                commands = [
                    ["gz", "sim", "-s", "-r", str(tmp / "world.sdf")],
                    [
                        "ros2",
                        "run",
                        "ros_gz_bridge",
                        "parameter_bridge",
                        "--ros-args",
                        "-p",
                        "config_file:="
                        + str(
                            ROOT / "ros2_jazzy/src/thesis_bunker_gz/config/bridge.yaml"
                        ),
                    ],
                    [
                        "ros2",
                        "run",
                        "thesis_bunker_mission",
                        "path_follower",
                        "--ros-args",
                        "-p",
                        "use_sim_time:=true",
                        "-p",
                        "online:=" + str(online).lower(),
                        "-p",
                        "map_id:=file/" + truth_file.name,
                        "-p",
                        "run_root:=" + str(folder / "runs"),
                    ],
                ]
                if online:
                    commands.append(
                        [
                            "ros2",
                            "run",
                            "thesis_bunker_mission",
                            "online_planner",
                            "--ros-args",
                            "-p",
                            "use_sim_time:=true",
                            "-p",
                            "truth_map:=" + str(truth_file),
                            "-p",
                            "prior_map:=" + str(prior_file),
                            "-p",
                            "sense_radius_m:=10.0",
                        ]
                    )
                for i, command in enumerate(commands):
                    stream = (folder / f"process_{i}.log").open("w")
                    streams.append(stream)
                    processes.append(
                        subprocess.Popen(
                            command,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    )
                observer.wait_until(
                    lambda: observer.t is not None
                    and observer.pose is not None
                    and observer.state is not None
                    and observer.command.get_subscription_count() > 0
                )
                settled = observer.t + 5
                observer.wait_until(lambda: observer.t >= settled)
                mission = dict(
                    id=1,
                    map_id="file/" + truth_file.name,
                    path=(np.asarray(fixed["traj"]) * RESOLUTION).tolist(),
                    points=result["points"],
                    lookahead_m=1.0,
                )
                observer.history = []
                started = observer.t
                start_pose = observer.pose
                msg = String()
                msg.data = json.dumps(mission)
                observer.command.publish(msg)
                distance = float(
                    np.linalg.norm(
                        np.diff(np.asarray(fixed["traj"]), axis=0), axis=1
                    ).sum()
                    * RESOLUTION
                )
                sim_limit = max(120, 6 * distance)
                terminal = {
                    "completed",
                    "stuck",
                    "no_path",
                    "pose_timeout",
                    "invalid_mission",
                    "time_reset",
                }

                def done():
                    return (
                        (
                            observer.state
                            and observer.state.get("mission_id") == 1
                            and observer.state["status"] in terminal
                        )
                        or observer.t - started > sim_limit
                        or any(p.poll() is not None for p in processes)
                    )

                observer.wait_until(done, wall_limit=max(180, sim_limit * 3))
                status = observer.state["status"] if observer.state else "missing_state"
                if observer.t - started > sim_limit:
                    status = "simulation_timeout"
                observer.stop.publish(Empty())
                end = observer.t + 0.2
                observer.wait_until(lambda: observer.t >= end, wall_limit=10)
                poses = np.asarray(observer.history, float)
                path = poses[:, :2] / RESOLUTION
                hits = path_lethal_cells(path, truth["tmap"].lethal)
                debris = path_lethal_cells(
                    path, truth["tmap"].rock & ~prior["tmap"].rock
                )
                logs = sorted((folder / "runs").glob("*/mission.json"))
                if not logs:
                    raise RuntimeError("no durable follower run log")
                run = logs[-1].parent
                replans = (
                    list(csv.DictReader((run / "replans.csv").open()))
                    if (run / "replans.csv").exists()
                    else []
                )
                plans = (
                    list(csv.DictReader((run / "plans.csv").open()))
                    if (run / "plans.csv").exists()
                    else []
                )
                times = (
                    [float(p["plan_time_s"]) for p in plans]
                    if online
                    else fixed["plan_times"]
                )
                result["runs"].append(
                    dict(
                        mode=label,
                        completed=status == "completed",
                        status=status,
                        sim_elapsed_s=observer.t - started,
                        start_pose=start_pose,
                        lethal_cells=len(hits),
                        debris_cells=len(debris),
                        n_replans=observer.state.get("n_replans", 0),
                        path_replacements=len(replans),
                        plan_times_s=times,
                        plan_s_median=float(np.median(times)) if times else None,
                        plan_s_p95=float(np.percentile(times, 95)) if times else None,
                        plan_s_max=max(times) if times else None,
                        run_folder=str(run.relative_to(output)),
                    )
                )
                print(json.dumps(result["runs"][-1], ensure_ascii=False), flush=True)
        except Exception as exc:
            result["errors"].append(
                dict(mode=label, error=type(exc).__name__ + ": " + str(exc))
            )
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
            for stream in streams:
                stream.close()
            observer.destroy_node()
            (output / "results.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            )
    rclpy.shutdown()
    if result["errors"]:
        raise RuntimeError(
            "Gazebo checks incomplete; see results.json and process logs"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run_checks(parser.parse_args().output)
