"""Headless physical measurements; thresholds are not fitted to the resulting runs."""

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import re
import xml.etree.ElementTree as ET
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.mapfile import load_map_file
from tapp.mission import plan_mission
from tapp.tour import sample_waypoints
from experiments.gz_run_report import analyze_run


def map_for_world(world):
    text = (world.parent / "README_ja.md").read_text()
    match = re.search(r"元地図：`([^`]+)`", text)
    if not match or Path(match[1]).name != match[1]:
        raise ValueError("world README must name its source map")
    return match[1]


def run_checks(output):
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import qos_profile_sensor_data
    from geometry_msgs.msg import PoseArray, Twist
    from rosgraph_msgs.msg import Clock
    from std_msgs.msg import String, Empty
    from thesis_bunker_gz.model import make_model
    from thesis_bunker_mission.transport import pose3d

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(image=os.environ.get('THESIS_ROS_IMAGE','osrf/ros:jazzy-desktop-full'),
                  gazebo_version=subprocess.check_output(['gz','sim','--versions'],text=True).strip(),
                  seed=100, terrain=[], bunker=[], drive=None, tours=[], errors=[])
    rclpy.init()

    class Observer(Node):
        def __init__(self, probe_count=0):
            super().__init__("gz_checks_observer")
            self.t = None
            self.pose = None
            self.history = []
            self.probes = {}
            self.status = None
            self.create_subscription(
                Clock, "/clock", self.clock, qos_profile_sensor_data
            )
            self.create_subscription(
                PoseArray, "/ground_truth", self.ground_truth, qos_profile_sensor_data
            )
            # PosePublisher ignores <topic>; each probe publishes /model/probe_<i>/pose.
            for i in range(probe_count):
                self.create_subscription(
                    PoseArray, f"/model/probe_{i}/pose", self.probe, qos_profile_sensor_data
                )
            self.create_subscription(String, "/mission/state", self.state, 10)
            self.vel = self.create_publisher(Twist, "/cmd_vel", 10)
            self.mission = self.create_publisher(String, "/mission/command", 10)
            self.stop = self.create_publisher(Empty, "/mission/stop", 10)

        def clock(self, msg):
            self.t = msg.clock.sec + msg.clock.nanosec / 1e9

        def ground_truth(self, msg):
            if msg.poses:
                self.pose = pose3d(msg.poses[0])
                self.history.append((self.t, self.pose))

        def probe(self, msg):
            for p in msg.poses:
                self.probes[(round(p.position.x, 3), round(p.position.y, 3))] = (
                    p.position.z
                )

        def state(self, msg):
            self.status = json.loads(msg.data)

        def wait(self, seconds, command=None):
            deadline = time.monotonic() + max(60, seconds * 3)
            if self.t is None:
                while self.t is None:
                    if time.monotonic() > deadline:
                        raise TimeoutError("no /clock")
                    rclpy.spin_once(self, timeout_sec=0.05)
            target = self.t + seconds
            while self.t < target:
                if time.monotonic() > deadline:
                    raise TimeoutError("simulation clock stalled")
                if command is not None:
                    self.vel.publish(command)
                rclpy.spin_once(self, timeout_sec=0.01)

        def ready(self, probe_count=0, body=False):
            deadline = time.monotonic() + 120
            while (
                self.t is None
                or len(self.probes) < probe_count
                or (body and self.pose is None)
            ):
                if time.monotonic() > deadline:
                    raise TimeoutError("missing physical telemetry")
                rclpy.spin_once(self, timeout_sec=0.05)

    def world_file(world, sc, folder, with_bunker=False, probes=None):
        tree = ET.parse(world)
        w = tree.getroot().find("world")
        w.find("physics/real_time_factor").text = "5"
        for uri in tree.findall(".//heightmap/uri"):
            uri.text = (world.parent / "heightmap.png").as_uri()
        if with_bunker:
            make_model(folder / "bunker.sdf", mass_kg=sc["tmap"].robot.mass_kg)
            model = ET.parse(folder / "bunker.sdf").getroot().find("model")
            x, y = sc["start_xy"]
            z = float(sc["tmap"].elev[sc["start"]]) + 0.1
            ET.SubElement(model, "pose").text = f"{x} {y} {z} 0 0 0"
            w.append(model)
        if probes:
            for i, (x, y, z) in enumerate(probes):
                m = ET.SubElement(w, "model", name=f"probe_{i}")
                ET.SubElement(m, "pose").text = f"{x} {y} {z+1} 0 0 0"
                link = ET.SubElement(m, "link", name="ball")
                inertial = ET.SubElement(link, "inertial")
                ET.SubElement(inertial, "mass").text = "1"
                inertia = ET.SubElement(inertial, "inertia")
                for key in ("ixx", "iyy", "izz"):
                    ET.SubElement(inertia, key).text = "0.001"
                for tag in ("collision", "visual"):
                    item = ET.SubElement(link, tag, name=tag)
                    geo = ET.SubElement(item, "geometry")
                    ET.SubElement(ET.SubElement(geo, "sphere"), "radius").text = "0.05"
                joint = ET.SubElement(
                    m, "joint", name="vertical_guide", type="prismatic"
                )
                ET.SubElement(joint, "parent").text = "world"
                ET.SubElement(joint, "child").text = "ball"
                ET.SubElement(ET.SubElement(joint, "axis"), "xyz").text = "0 0 1"
                plugin = ET.SubElement(
                    m,
                    "plugin",
                    filename="gz-sim-pose-publisher-system",
                    name="gz::sim::systems::PosePublisher",
                )
                for key, value in dict(
                    publish_model_pose="true",
                    publish_link_pose="false",
                    use_pose_vector_msg="true",
                    update_frequency="20",
                ).items():
                    ET.SubElement(plugin, key).text = value
        target = folder / "world.sdf"
        tree.write(target, encoding="utf-8", xml_declaration=True)
        return target

    def execute(world, sc, label, callback, body=False, probes=None, follower=False):
        processes = []
        streams = []
        observer = Observer(len(probes or []))
        try:
            with tempfile.TemporaryDirectory(prefix="thesis-gz-check-") as tmp:
                runtime = world_file(world, sc, Path(tmp), body, probes)
                commands = [
                    ["gz", "sim", "-s", "-r", str(runtime)],
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
                        "ros_gz_bridge",
                        "parameter_bridge",
                        *[
                            f"/model/probe_{i}/pose@geometry_msgs/msg/PoseArray[gz.msgs.Pose_V"
                            for i in range(len(probes or []))
                        ],
                    ],
                ]
                if follower:
                    commands.append(
                        [
                            "ros2",
                            "run",
                            "thesis_bunker_mission",
                            "path_follower",
                            "--ros-args",
                            "-p",
                            "use_sim_time:=true",
                            "-p",
                            "map_id:=file/" + sc["_filename"],
                            "-p",
                            "run_root:=" + str(output / "runs"),
                        ]
                    )
                for i, command in enumerate(commands):
                    stream = (output / f"{label}_{i}.log").open("w")
                    streams.append(stream)
                    processes.append(
                        subprocess.Popen(
                            command,
                            stdout=stream,
                            stderr=subprocess.STDOUT,
                            start_new_session=True,
                        )
                    )
                observer.ready(len(probes or []), body)
                observer.wait(5)
                return callback(observer)
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

    worlds = sorted((ROOT / "gazebo_worlds").glob("*/world.sdf"))
    for world in worlds:
        filename = map_for_world(world)
        sc = load_map_file(ROOT / "maps" / filename)
        sc["_filename"] = filename
        try:
            land = np.argwhere(
                ~sc["water"] & ~sc["nodata"] & ~sc["obstacle"] & ~sc["tmap"].lethal
            )
            indices = np.random.default_rng(100).choice(len(land), 20, replace=False)
            probes = [
                (float(x) * 0.5, float(y) * 0.5, float(sc["tmap"].elev[x, y]))
                for x, y in land[indices]
            ]

            def heights(o):
                samples = [
                    dict(
                        x=x,
                        y=y,
                        expected_z=z,
                        measured_ground_z=o.probes[(round(x, 3), round(y, 3))] - 0.05,
                    )
                    for x, y, z in probes
                ]
                errors = [
                    abs(s["measured_ground_z"] - s["expected_z"]) for s in samples
                ]
                return dict(
                    world=world.parent.name,
                    samples=samples,
                    max_height_error_m=max(errors),
                    fallen=sum(
                        s["measured_ground_z"] < s["expected_z"] - 1 for s in samples
                    ),
                )

            result["terrain"].append(
                execute(
                    world, sc, "terrain_" + world.parent.name, heights, probes=probes
                )
            )

            def placement(o):
                o.history = []
                o.wait(5)
                values = np.array([p[1] for p in o.history if p[0] is not None])
                expected = float(sc["tmap"].elev[sc["start"]])
                return dict(
                    map=filename,
                    pose=o.pose,
                    z_range_m=float(np.ptp(values[:, 2])),
                    xy_drift_m=float(np.linalg.norm(values[-1, :2] - values[0, :2])),
                    expected_ground_z=expected,
                    fallen=bool(o.pose[2] < expected - 1),
                )

            result["bunker"].append(
                execute(
                    world, sc, "placement_" + world.parent.name, placement, body=True
                )
            )
            if filename.startswith("flat"):

                def drive(o):
                    start = np.array(o.pose)
                    cmd = Twist()
                    cmd.linear.x = 0.5
                    o.wait(10, cmd)
                    after = np.array(o.pose)
                    o.vel.publish(Twist())
                    o.wait(1)
                    o.history = []
                    turn_start = np.array(o.pose)
                    cmd = Twist()
                    cmd.angular.z = 0.5
                    o.wait(10, cmd)
                    o.vel.publish(Twist())
                    yaw = np.unwrap(np.array([p[1][5] for p in o.history]))
                    angle = float(yaw[-1] - yaw[0])
                    return dict(
                        forward_m=float(np.linalg.norm(after[:2] - start[:2])),
                        forward_ratio=float(np.linalg.norm(after[:2] - start[:2]) / 5),
                        turn_rad=angle,
                        turn_ratio=angle / 5,
                        turn_xy_drift_m=float(
                            np.linalg.norm(np.array(o.pose[:2]) - turn_start[:2])
                        ),
                    )

                result["drive"] = execute(world, sc, "drive", drive, body=True)

            def tour(o):
                points = (np.asarray(sample_waypoints(sc, 5, 100)) * 0.5).tolist()
                plan = plan_mission(sc, sc["start_xy"], points)
                deadline = time.monotonic() + 30
                while o.mission.get_subscription_count() == 0:
                    if time.monotonic() > deadline:
                        raise TimeoutError("path_follower unavailable")
                    rclpy.spin_once(o, timeout_sec=0.05)
                o.status = None
                mission = String()
                mission.data = json.dumps(
                    dict(
                        id=1,
                        map_id="file/" + filename,
                        path=plan["path"],
                        points=points,
                        lookahead_m=1.0,
                    )
                )
                o.mission.publish(mission)
                start = o.t
                limit = max(120, 6 * plan["metrics"]["length_xy"] + 60)
                while o.t - start < limit:
                    o.wait(0.5)
                    if (
                        o.status
                        and o.status.get("mission_id") == 1
                        and o.status["status"]
                        in ("completed", "stuck", "pose_timeout", "invalid_mission")
                    ):
                        break
                else:
                    o.stop.publish(Empty())
                    o.wait(1)
                folders = sorted((output / "runs").glob("*"))
                run = next(
                    p
                    for p in reversed(folders)
                    if json.loads((p / "mission.json").read_text())["map_id"]
                    == "file/" + filename
                )
                return analyze_run(run, output / ("report_" + world.parent.name))

            result["tours"].append(
                execute(
                    world,
                    sc,
                    "tour_" + world.parent.name,
                    tour,
                    body=True,
                    follower=True,
                )
            )
        except Exception as exc:
            result["errors"].append(dict(world=world.parent.name, error=repr(exc)))
        (output / "results.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        )
    rclpy.shutdown()
    result["failed"] = bool(
        result["errors"]
        or any(x["fallen"] for x in result["terrain"])
        or any(x["fallen"] for x in result["bunker"])
        or any(x["fallen_samples"] for x in result["tours"])
    )
    (output / "results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    outcome = run_checks(parser.parse_args().output)
    sys.exit(bool(outcome["failed"]))
