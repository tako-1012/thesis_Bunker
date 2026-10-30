"""ROS-free tests for model geometry, package wiring, controller parity, reports and HTTP."""

import ast
import csv
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import xml.etree.ElementTree as ET
import numpy as np
from fastapi.testclient import TestClient

from tapp.config import Robot
from tapp.follower import MissionFollower
from tapp.mapfile import load_map_file, save_map
from tapp.robot_sim import simulate, initial_pose
from tapp.run_log import RunLog
from experiments.gz_run_report import analyze_run
from webui.server import app

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = ROOT / "ros2_jazzy"
for package in ("thesis_bunker_gz", "thesis_bunker_mission"):
    sys.path.insert(0, str(WORKSPACE / "src" / package))
from thesis_bunker_gz.model import make_model
from thesis_bunker_mission.transport import RobotHTTP, rpy, pose3d


def test_model():
    path = WORKSPACE / "src/thesis_bunker_gz/models/bunker/model.sdf"
    model = ET.parse(path).find("model")
    body = model.find('link[@name="base_link"]')
    assert float(body.findtext("inertial/mass")) == Robot().mass_kg
    size = np.fromstring(body.findtext("collision/geometry/box/size"), sep=" ")
    assert np.array_equal(size, [1.023, 0.778, 0.410])
    for tag, value in [
        ("ixx", Robot().mass_kg * (size[1] ** 2 + size[2] ** 2) / 12),
        ("iyy", Robot().mass_kg * (size[0] ** 2 + size[2] ** 2) / 12),
        ("izz", Robot().mass_kg * (size[0] ** 2 + size[1] ** 2) / 12),
    ]:
        assert math.isclose(float(body.findtext("inertial/inertia/" + tag)), value)
    drive = model.find('plugin[@name="gz::sim::systems::DiffDrive"]')
    assert float(drive.findtext("wheel_separation")) == 0.699
    joints = {j.attrib["name"]: j for j in model.findall("joint")}
    for side, sign in [("left", 1), ("right", -1)]:
        names = [e.text for e in drive.findall(side + "_joint")]
        assert 4 <= len(names) <= 6
        for name in names:
            assert name in joints and joints[name].attrib["type"] == "revolute"
            link = model.find('link[@name="' + joints[name].findtext("child") + '"]')
            assert np.fromstring(link.findtext("pose"), sep=" ")[1] == sign * 0.3495
    assert body.find('sensor[@type="imu"]') is not None
    poses = model.find('plugin[@name="gz::sim::systems::PosePublisher"]')
    assert (
        poses.findtext("publish_model_pose") == "true"
        and poses.findtext("publish_link_pose") == "false"
    )
    # Harmonic's PosePublisher ignores <topic> and always uses /model/<name>/pose.
    assert poses.find("topic") is None
    bridge = (WORKSPACE / "src/thesis_bunker_gz/config/bridge.yaml").read_text()
    truth = bridge.split("ros_topic_name: /ground_truth")[1].split("- ros_topic_name")[0]
    assert "gz_topic_name: /model/" + model.attrib["name"] + "/pose" in truth
    assert not model.findall(".//mesh")
    with tempfile.TemporaryDirectory() as tmp:
        generated = make_model(Path(tmp) / "bunker.sdf", mass_kg=Robot().mass_kg)
        assert generated.read_bytes() == path.read_bytes()
        # Only an explicit external directory adds a visual URI; never copy its contents.
        mesh = Path(tmp) / "BUNKER.STL"
        mesh.write_bytes(b"display-test-placeholder")
        generated = make_model(Path(tmp) / "optional.sdf", tmp)
        optional = ET.parse(generated)
        assert optional.find(".//visual/geometry/mesh/uri").text == mesh.as_uri()
        assert optional.find(".//collision/geometry/mesh") is None
    assert not list(WORKSPACE.rglob("*.STL"))
    print(
        "model: 150kg box inertia, 0.699m spacing, 4 wheels/side, DiffDrive joints, IMU, world pose and opt-in external visual passed",
        flush=True,
    )


def test_packages():
    for name in ("thesis_bunker_gz", "thesis_bunker_mission"):
        folder = WORKSPACE / "src" / name
        package = ET.parse(folder / "package.xml")
        assert (
            package.findtext("name") == name
            and package.findtext("export/build_type") == "ament_python"
        )
        source = (folder / "setup.py").read_text()
        ast.parse(source)
        assert (folder / "resource" / name).is_file() and (
            folder / "setup.cfg"
        ).is_file()
        if name == "thesis_bunker_mission":
            assert "path_follower" in source and "webui_bridge" in source
    launch = WORKSPACE / "src/thesis_bunker_gz/launch/sim.launch.py"
    source = launch.read_text()
    ast.parse(source)
    assert all(
        s in source
        for s in (
            "lab_mesh_dir",
            "conference_dir",
            "webui",
            "path_follower",
            "webui_bridge",
            "ros_gz_bridge",
        )
    )
    for path in WORKSPACE.rglob("*.py"):
        compile(path.read_text(), str(path), "exec")
    assert (WORKSPACE / "gz_checks/run_gz_checks.sh").is_file()
    print(
        "packages: ament_python metadata, resource markers, node entry points, launch/bridge configuration and Python syntax passed",
        flush=True,
    )


def kinematic_fixture():
    sc = load_map_file(ROOT / "maps/flat_test_100m.npz")
    path = [[10, 10], [20, 10], [20, 20], [10, 10]]
    result = simulate(sc, path, initial_pose(path), max_time_s=120)
    return sc, path, result


def test_follower():
    sc, path, result = kinematic_fixture()
    follower = MissionFollower(path)
    pose = np.array(initial_pose(path))
    trace = [[0.0, *pose.tolist()]]
    dt = 0.05
    for step in range(2400):
        v, w, done = follower.step(step * dt, pose)
        if done:
            break
        pose[0] += v * math.cos(pose[2]) * dt
        pose[1] += v * math.sin(pose[2]) * dt
        pose[2] = (pose[2] + w * dt + math.pi) % (2 * math.pi) - math.pi
        trace.append([(step + 1) * dt, *pose.tolist()])
    assert follower.status == "completed" and np.array_equal(
        trace, result["trajectory"]
    )
    stopped = MissionFollower([[10, 10], [20, 10]], stall_timeout_s=2)
    assert not stopped.step(0, [10, 10, 0])[2]
    assert not stopped.step(1, [10, 10, 0])[2]
    assert (
        stopped.step(2, [10, 10, 0]) == (0.0, 0.0, True) and stopped.status == "stuck"
    )
    row = follower.log_row(5, [1, 2, 3, 0.1, 0.2, 0.3], [0.4, 0.5, 0.6], 0.7, 0.8)
    assert row == dict(t=5, x=1, y=2, z=3, roll=0.4, pitch=0.5, yaw=0.3, v=0.7, w=0.8)
    print(
        "follower: bit-identical kinematic trajectory, completion, stationary watchdog and CSV fields passed",
        flush=True,
    )


def test_report():
    sc, path, result = kinematic_fixture()
    with tempfile.TemporaryDirectory() as tmp:
        logger = RunLog(
            dict(
                map_id="file/flat_test_100m.npz",
                path=path,
                points=path[1:],
                lookahead_m=1.0,
                data_source="synthetic_robot_sim",
            ),
            tmp,
        )
        for t, x, y, yaw in result["trajectory"]:
            logger.write(
                dict(t=t, x=x, y=y, z=0.0, roll=0.0, pitch=0.0, yaw=yaw, v=0.0, w=0.0)
            )
        logger.close("completed")
        report = analyze_run(logger.folder, Path(tmp) / "report")
        assert (
            report["completed"]
            and report["path_lethal_cells"] == result["path_lethal_cells"]
        )
        for key in ("deviation_mean_m", "deviation_max_m", "elapsed_s"):
            assert math.isclose(report[key], result[key], abs_tol=1e-12)
        assert all(
            (Path(tmp) / "report" / p).is_file()
            for p in (
                "summary.json",
                "summary.csv",
                "paths.png",
                "attitude.png",
                "report_log.txt",
            )
        )
        # An analytic plane exercises the existing heading-gradient attitude
        # calculation without inventing physical roll/pitch measurements.
        grid_x, grid_y = np.mgrid[:40, :40] * 0.5
        map_file = Path(tmp) / "plane.npz"
        save_map(map_file, 0.1 * grid_x + 0.2 * grid_y, start_xy=[2, 2])
        plane = load_map_file(map_file)
        plane_path = [[2, 2], [10, 2]]
        plane_run = simulate(plane, plane_path, initial_pose(plane_path))
        logger = RunLog(
            dict(
                map_id="analytic_plane",
                map_file=str(map_file),
                path=plane_path,
                data_source="synthetic_robot_sim",
            ),
            tmp,
        )
        for t, x, y, yaw in plane_run["trajectory"]:
            logger.write(
                dict(
                    t=t,
                    x=x,
                    y=y,
                    z=0.1 * x + 0.2 * y,
                    roll=0.0,
                    pitch=0.0,
                    yaw=yaw,
                    v=0.0,
                    w=0.0,
                )
            )
        logger.close("completed")
        predicted = analyze_run(logger.folder, Path(tmp) / "plane_report")
        assert math.isclose(
            predicted["roll_p95_map_deg"], math.degrees(math.atan(0.2)), abs_tol=1e-10
        )
        assert math.isclose(
            predicted["pitch_p95_map_deg"], math.degrees(math.atan(0.1)), abs_tol=1e-10
        )
    print(
        "report: synthetic robot_sim CSV deviation/contact/time parity, kinematic comparison and plots passed (not Gazebo measurements)",
        flush=True,
    )


def test_api():
    with TestClient(app) as client:
        request = dict(
            map_id="file/flat_test_100m.npz", path=[[10, 10], [20, 10]], lookahead_m=1.0
        )
        sent = client.post("/api/robot/mission", json=request)
        assert sent.status_code == 200
        number = sent.json()["id"]
        fetched = client.get("/api/robot/mission", params={"after": number - 1})
        assert fetched.status_code == 200 and fetched.json()["path"] == request["path"]
        assert (
            client.get("/api/robot/mission", params={"after": number}).status_code
            == 204
        )
        for payload in (
            dict(request, map_id="invalid"),
            dict(request, path=[]),
            dict(request, path=[[float("inf"), 0]]),
        ):
            # JSON itself cannot encode infinity in httpx; finite out-of-map input covers that boundary.
            if payload["path"] and not np.isfinite(payload["path"]).all():
                payload["path"] = [[-1, 0]]
            assert client.post("/api/robot/mission", json=payload).status_code == 422
        state = dict(
            map_id=request["map_id"],
            mission_id=number,
            status="running",
            pose=[10, 10, 0, 0, 0, 0],
            sim_time=1.0,
        )
        assert client.post("/api/robot/state", json=state).status_code == 200
        received = client.get("/api/robot/state").json()
        assert received["connected"] and received["pose"] == state["pose"]
        with patch(
            "webui.robot_api.time.time", return_value=received["received_at"] + 4
        ):
            assert not client.get("/api/robot/state").json()["connected"]
        http = RobotHTTP("http://unused", request["map_id"])
        with patch.object(http, "_request", return_value=dict(request, id=number)):
            mission, error = http.poll()
            assert mission["id"] == number and error is None
        with patch.object(
            http, "_request", return_value=dict(request, id=number + 1, map_id="other")
        ):
            mission, error = http.poll()
            assert mission is None and error["status"] == "map_mismatch"
    print(
        "API: send/fetch/id/204, telemetry/freshness, invalid map/path 422 and bridge map rejection passed",
        flush=True,
    )


def test_worlds():
    fixture = json.loads((WORKSPACE / "gz_checks/baseline_worlds.json").read_text())
    for name, old in fixture.items():
        folder = ROOT / "gazebo_worlds" / name
        world = ET.parse(folder / "world.sdf")
        assert (
            hashlib.sha256((folder / "heightmap.png").read_bytes()).hexdigest()
            == old["png_sha256"]
        )
        model = world.find('.//model[@name="terrain"]')
        pose = np.fromstring(model.findtext("pose"), sep=" ")
        assert np.array_equal(pose[:3], old["heightmap_pos"]) and np.array_equal(
            pose[3:], [0, 0, 0]
        )
        for hm in model.findall(".//heightmap"):
            assert hm.findtext("pos") == "0 0 0"
        actual = [
            ET.tostring(m, encoding="unicode").strip()
            for m in world.findall(".//model")
            if m.attrib["name"].startswith("obstacle_")
        ]
        assert actual == old["obstacles"]
        plugins = {p.attrib["name"] for p in world.findall(".//world/plugin")}
        assert {"gz::sim::systems::Sensors", "gz::sim::systems::Imu"} <= plugins
    print(
        "worlds: original PNG hashes/obstacle XML preserved, effective terrain transforms unchanged, sensors and IMU added",
        flush=True,
    )


if __name__ == "__main__":
    for check in (
        test_model,
        test_packages,
        test_follower,
        test_report,
        test_api,
        test_worlds,
    ):
        check()
    print("all ROS-free ROS2/Gazebo tests passed", flush=True)
