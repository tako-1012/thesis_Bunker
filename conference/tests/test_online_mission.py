"""Exact legacy parity, stale-map safety and deterministic threaded ROS-free handoff."""

import ast
import csv
import json
from pathlib import Path
import sys
import tempfile
import threading
import importlib.util
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from fastapi.testclient import TestClient
from tapp.beach_scenario import build_beach
from tapp.real_beach import build_real, list_patches
from tapp.online import run_online
from tapp.online_mission import (
    run_online_mission,
    run_fixed_mission,
    ordered_tour,
    virtual_sense,
)
from tapp.prior import coarse_prior, PriorMap
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.traversability import TraversabilityMap
from tapp.follower import MissionFollower
from tapp.run_log import RunLog
from tapp.mapfile import load_map_file
from tapp.tour import sample_waypoints
from webui.server import app

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ros2_jazzy/src/thesis_bunker_mission"))
from thesis_bunker_mission.online_runtime import (
    AsyncOnlineMission,
    replace_running_path,
    record_plan_history,
    load_online_maps,
)


def test_legacy_parity():
    scenarios = [build_beach(k, 100, 100) for k in ["beach_gentle", "beach_steep"]]
    scenarios += [
        build_real(r["name"], 100, 0, dataset="shizuoka_beach_las")
        for r in list_patches("validation")[:2]
    ]
    for sc in scenarios:
        tm = sc["tmap"]
        for has_prior in [False, True]:
            prior = coarse_prior(tm, 10) if has_prior else None
            old = run_online(
                tm,
                sc["start"],
                sc["goal"],
                planner="TA*-S",
                exact_los=True,
                unknown_cost="adaptive",
                prior_lethal="soft",
                prior_map=prior,
                sense_radius_m=10,
            )
            new = run_online_mission(tm, prior, sc["start"], [sc["goal"]], radius_m=10)
            assert old["success"] == new["success"] and old["reason"] == new["reason"]
            assert old["n_plans"] == new["n_plans"] and np.array_equal(
                old["traj"], new["traj"]
            ), (sc["kind"], has_prior)
            assert len(path_lethal_cells(new["traj"], tm.lethal)) == 0
            assert len(new["plan_times"]) == new["n_plans"] and all(
                t >= 0 for t in new["plan_times"]
            )
        print(
            sc["kind"]
            + ": no-prior/coarse exact trajectory and plan-count parity; contact=0",
            flush=True,
        )


def test_stale_safety():
    witnesses = []
    for row in list_patches("validation", dataset="shizuoka_beach_las")[:3]:
        clean = build_real(row["name"], 200, 0, dataset="shizuoka_beach_las")
        truth = build_real(
            row["name"], 200, 0, debris=True, dataset="shizuoka_beach_las"
        )
        points = sample_waypoints(
            truth, 12, np.random.SeedSequence([0, 3000, 200, truth["patch_index"]])
        )[:5]
        tour = ordered_tour(clean["tmap"], truth["start"], points)
        prior = PriorMap(clean["tmap"].cost, clean["tmap"].lethal, RESOLUTION)
        result = run_online_mission(
            truth["tmap"], prior, truth["start"], tour["stops"], radius_m=10
        )
        fixed = run_fixed_mission(clean["tmap"], truth["start"], tour["stops"])
        assert result["success"] and fixed["success"]
        assert len(path_lethal_cells(result["traj"], truth["tmap"].lethal)) == 0
        hits = len(
            path_lethal_cells(fixed["traj"], truth["tmap"].rock & ~clean["tmap"].rock)
        )
        witnesses.append(hits)
        assert len(result["legs"]) == 6 and result["traj"][-1] == tuple(truth["start"])
        print(
            row["name"],
            "stale five-point tour: online contact=0; fixed debris cells=",
            hits,
            flush=True,
        )
    assert any(h > 0 for h in witnesses)


def test_async_handoff():
    tm = TraversabilityMap(np.zeros((60, 60)), np.zeros((60, 60), bool))
    runtime = AsyncOnlineMission(tm, tm, PriorMap(tm.cost, tm.lethal, 0.5), radius_m=5)
    entered, release = threading.Event(), threading.Event()
    original = runtime._work
    count = 0

    def gated(state, pos):
        nonlocal count
        count += 1
        if count == 2:
            state["planner"].since_replan = state["planner"].replan_every_m
            entered.set()
            assert release.wait(10)
        return original(state, pos)

    runtime._work = gated
    mission = dict(
        id=101,
        map_id="fixture",
        points=[[20, 5]],
        path=[[5, 5], [20, 5]],
        lookahead_m=1.0,
    )
    try:
        runtime.start(mission)
        assert runtime.tick([5, 5], 0) is None
        runtime.pending.result(timeout=10)
        first = runtime.tick([5, 5], 0.1)
        assert first and not first["replace_path"] and entered.wait(10)
        old_path = list(runtime.current_path)
        assert runtime.tick([6, 5], 1.0) is None and runtime.current_path == old_path
        with tempfile.TemporaryDirectory() as tmp:
            log = RunLog(first, tmp)
            stream = log.stream
            record_plan_history(log, first)
            follower = MissionFollower(first["path"])
            v, w, done = follower.step(0.1, [5, 5, 0])
            assert v > 0 and not done
            log.write(follower.log_row(0.1, [5, 5, 0, 0, 0, 0], None, v, w))
            v, w, done = follower.step(1, [6, 5, 0])
            assert v > 0 and not done
            log.write(follower.log_row(1, [6, 5, 0, 0, 0, 0], None, v, w))
            release.set()
            runtime.pending.result(timeout=10)
            replacement = runtime.tick([6, 5], 1.1)
            assert (
                replacement
                and replacement["replace_path"]
                and replacement["reason"] == "distance"
            )
            assert replacement["path"][0] == [6.0, 5.0] and replacement["id"] == 101
            follower = replace_running_path(
                log, replacement, {}, 1.1, previous=follower
            )
            assert log.stream is stream and not stream.closed
            v, w, done = follower.step(2, [7, 5, 0])
            assert v > 0 and not done
            log.write(follower.log_row(2, [7, 5, 0, 0, 0, 0], None, v, w))
            for wrong in [dict(replacement, id=102), replacement]:
                try:
                    replace_running_path(log, wrong, {}, 2)
                except ValueError:
                    pass
                else:
                    raise AssertionError("cross-run/duplicate replacement accepted")
            log.close("stopped")
            assert (
                len(list(csv.DictReader((log.folder / "trajectory.csv").open()))) == 3
            )
            assert len(list(csv.DictReader((log.folder / "replans.csv").open()))) == 1
            assert len(list(csv.DictReader((log.folder / "plans.csv").open()))) == 2
        runtime.stop()
        if runtime.pending:
            runtime.pending.result(timeout=10)
        assert runtime.tick([7, 5], 3) is None
    finally:
        release.set()
        runtime.close()
    print(
        "async: worker blocked while simulation time advances, old path/positive commands continue; latest-pose replacement, one trajectory, plan/event logs and stale/cross-run rejection passed",
        flush=True,
    )


def test_maps_and_api():
    stem = "real_las_08OB87_-0206_200m_0"
    truth, prior_tm, prior, mode = load_online_maps(
        ROOT / "maps" / (stem + "_debris.npz"), ROOT / "maps" / (stem + ".npz")
    )
    original = build_real(
        "08OB87_-0206", 200, 0, debris=True, dataset="shizuoka_beach_las"
    )
    for key in ["cost", "lethal", "elev"]:
        assert np.array_equal(
            getattr(truth["tmap"], key), getattr(original["tmap"], key)
        )
    for key in ["water", "nodata"]:
        assert np.array_equal(truth[key], original[key])
    assert (
        np.array_equal(truth["obstacle"], original["terrain"]["rock"])
        and mode == "soft"
    )
    coarse = load_online_maps(ROOT / "maps" / (stem + ".npz"), "coarse:10")
    assert np.array_equal(coarse[2].cost, coarse_prior(coarse[0]["tmap"], 10).cost)
    for radius in [5, 10, 15]:
        mask, cost, lethal = virtual_sense(truth["tmap"], truth["start"], radius)
        assert (
            mask.shape == (400, 400)
            and mask.dtype == bool
            and cost is truth["tmap"].cost
            and lethal is truth["tmap"].lethal
        )
    with TestClient(app) as client:
        old = dict(map_id="file/flat_test_100m.npz", status="idle")
        assert client.post("/api/robot/state", json=old).status_code == 200
        assert "current_path" not in client.get("/api/robot/state").json()
        payload = dict(old, current_path=[[1, 2], [3, 4]], n_replans=3)
        assert client.post("/api/robot/state", json=payload).status_code == 200
        state = client.get("/api/robot/state").json()
        assert (
            state["current_path"] == payload["current_path"] and state["n_replans"] == 3
        )
        assert (
            client.post(
                "/api/robot/state", json=dict(payload, n_replans=-1)
            ).status_code
            == 422
        )
    launch = ast.parse(
        (ROOT / "ros2_jazzy/src/thesis_bunker_gz/launch/sim.launch.py").read_text()
    )
    assert any(
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "DeclareLaunchArgument"
        and n.args
        and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "online"
        and any(
            k.arg == "default_value"
            and isinstance(k.value, ast.Constant)
            and k.value.value == "false"
            for k in n.keywords
        )
        for n in ast.walk(launch)
    )
    print(
        "maps/API: debris elevations, cost/lethal/obstacle/water/nodata match; coarse prior, legacy telemetry, live path/count validation and online=false default passed",
        flush=True,
    )


def test_follower_adapter():
    class Twist:
        def __init__(self):
            self.linear = SimpleNamespace(x=0.0)
            self.angular = SimpleNamespace(z=0.0)

    stubs = {
        "rclpy": SimpleNamespace(ok=lambda: True),
        "rclpy.node": SimpleNamespace(Node=object),
        "rclpy.qos": SimpleNamespace(qos_profile_sensor_data=None),
        "geometry_msgs.msg": SimpleNamespace(PoseArray=object, Twist=Twist),
        "sensor_msgs.msg": SimpleNamespace(Imu=object),
        "std_msgs.msg": SimpleNamespace(String=SimpleNamespace, Empty=object),
    }
    with patch.dict(sys.modules, stubs), tempfile.TemporaryDirectory() as output:
        file = (
            ROOT
            / "ros2_jazzy/src/thesis_bunker_mission/thesis_bunker_mission/path_follower.py"
        )
        spec = importlib.util.spec_from_file_location(
            "thesis_bunker_mission._follower_fixture", file
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for online, stuck in [(False, False), (True, False), (True, True)]:
            node = module.PathFollower.__new__(module.PathFollower)
            states = []
            clock = [0.0]
            node.online = online
            node.map_id = "fixture"
            node.pose = [5.0, 5.0, 0.0, 0.0, 0.0, 0.0]
            node.imu = None
            node.log = None
            node.follower = None
            node.current_mission = None
            node.n_replans = 0
            node.mission_id = 0
            node.get_parameter = lambda key: SimpleNamespace(
                value=output if key == "run_root" else 10.0
            )
            node.get_clock = lambda: SimpleNamespace(
                now=lambda: SimpleNamespace(nanoseconds=int(clock[0] * 1e9))
            )
            node.get_logger = lambda: SimpleNamespace(
                info=lambda _: None, error=lambda _: None
            )
            node.cmd = SimpleNamespace(publish=lambda _: None)
            node.state = SimpleNamespace(
                publish=lambda msg: states.append(json.loads(msg.data))
            )
            mission = dict(
                id=7,
                map_id="fixture",
                path=[[5, 5], [6, 5]],
                final_leg=False,
                revision=1,
                n_replans=0,
                plan_history=[],
            )
            node.on_mission(SimpleNamespace(data=json.dumps(mission)))
            folder = node.log.folder
            stream = node.log.stream
            node.pose_received = __import__("time").monotonic()
            node.tick()
            clock[0] = 11.0 if stuck else 1.0
            if not stuck:
                node.pose[:2] = [6, 5]
            node.pose_received = __import__("time").monotonic()
            node.tick()
            if online and not stuck:
                assert (
                    node.last_status == "waiting_for_plan" and node.log.stream is stream
                )
                replacement = dict(
                    mission,
                    path=[[6, 5], [7, 5]],
                    final_leg=True,
                    revision=2,
                    replace_path=True,
                    reason="next_leg",
                    plan_time_s=0.01,
                    leg_index=1,
                    handoff_latency_s=0.02,
                    sim_handoff_s=0.02,
                    pose_shift_m=0.0,
                )
                node.on_mission(SimpleNamespace(data=json.dumps(replacement)))
                assert node.log.folder == folder and node.log.stream is stream
                clock[0] = 2.0
                node.pose[:2] = [7, 5]
                node.pose_received = __import__("time").monotonic()
                node.tick()
            assert node.log is None and node.last_status == (
                "stuck" if stuck else "completed"
            )
            assert ("current_path" in states[-1]) == online
            rows = list(csv.DictReader((folder / "trajectory.csv").open()))
            assert len(rows) == (3 if online and not stuck else 2)
        node.on_mission(
            SimpleNamespace(
                data=json.dumps(
                    dict(
                        id=8, map_id="fixture", online_error="no_path", plan_history=[]
                    )
                )
            )
        )
        assert states[-1]["mission_id"] == 8 and states[-1]["status"] == "no_path"
    print(
        "follower adapter: legacy completion/telemetry unchanged; intermediate-leg CSV stays open; final completion and stationary watchdog terminate the run",
        flush=True,
    )


if __name__ == "__main__":
    for check in [
        test_legacy_parity,
        test_stale_safety,
        test_async_handoff,
        test_follower_adapter,
        test_maps_and_api,
    ]:
        check()
    print("all online-mission tests passed", flush=True)
