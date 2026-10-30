"""ROS-free single-worker planning mailbox and continuous-run path replacements."""

from concurrent.futures import ThreadPoolExecutor
import csv
import math
import time
from pathlib import Path
import numpy as np
from tapp.config import RESOLUTION
from tapp.collision import path_lethal_cells, line_of_sight_exact
from tapp.follower import MissionFollower
from tapp.mapfile import load_map_file
from tapp.prior import PriorMap, coarse_prior, coarse_elevation
from tapp.traversability import TraversabilityMap
from tapp.online_mission import OnlinePlanner, virtual_sense, ordered_tour


def load_online_maps(truth_map, prior_map):
    truth = load_map_file(truth_map)
    tm = truth["tmap"]
    if str(prior_map).startswith("coarse:"):
        cell_m = float(str(prior_map).split(":", 1)[1])
        prior = coarse_prior(tm, cell_m)
        prior_tm = TraversabilityMap(
            coarse_elevation(tm, cell_m), np.zeros(tm.shape, bool), tm.robot, tm.weights
        )
        mode = "soft"
    else:
        prior_file = Path(prior_map) if prior_map else Path(truth_map)
        loaded = load_map_file(prior_file)
        prior_tm = loaded["tmap"]
        if prior_tm.shape != tm.shape or loaded["resolution"] != truth["resolution"]:
            raise ValueError("truth/prior grids must match")
        prior = PriorMap(prior_tm.cost, prior_tm.lethal, RESOLUTION)
        mode = "hard" if prior_file.resolve() == Path(truth_map).resolve() else "soft"
    return truth, prior_tm, prior, mode


class AsyncOnlineMission:
    def __init__(
        self,
        truth_tm,
        prior_tm,
        prior,
        *,
        radius_m=10,
        prior_lethal_mode="soft",
        executor=None
    ):
        if not math.isfinite(radius_m) or radius_m <= 0:
            raise ValueError("radius must be positive")
        self.truth, self.prior_tm, self.prior = truth_tm, prior_tm, prior
        self.radius, self.mode = radius_m, prior_lethal_mode
        self.pool = executor or ThreadPoolExecutor(max_workers=1)
        self.pending = None
        self.version = 0
        self.state = None
        self.current_path = []
        self.sent = 0
        self.finished = True
        self.observations = []

    def start(self, mission):
        # Each generation has independent state; an old in-flight job can finish
        # but can never overwrite a new mission, even when cancellation fails.
        self.version += 1
        self.state = dict(mission=dict(mission), planner=None, leg=0, tour=None)
        self.current_path = []
        self.sent = 0
        self.finished = False
        self.observations = []

    def stop(self):
        self.version += 1
        self.finished = True

    def _work(self, state, position):
        cell = tuple(int(round(v / RESOLUTION)) for v in position)
        if state["planner"] is None:
            raw = np.asarray(state["mission"]["points"], float).reshape(-1, 2)
            if not 1 <= len(raw) <= 12 or not np.isfinite(raw).all():
                raise ValueError("online missions require 1..12 finite waypoints")
            points = [tuple(int(round(v / RESOLUTION)) for v in p) for p in raw]
            state["tour"] = ordered_tour(self.prior_tm, cell, points)
            state["planner"] = OnlinePlanner(
                self.prior.cost,
                self.prior.lethal,
                self.truth.weights,
                prior_lethal_mode=self.mode,
            )
        planner = state["planner"]
        for seen in state.pop("observations", []):
            planner.observe(
                *virtual_sense(
                    self.truth,
                    np.rint(np.asarray(seen) / RESOLUTION).astype(int),
                    self.radius,
                )
            )
        planner.observe(*virtual_sense(self.truth, cell, self.radius))
        if (
            planner.goal is not None
            and np.linalg.norm(
                np.asarray(position) - np.asarray(planner.goal) * RESOLUTION
            )
            <= 0.3
        ):
            state["leg"] += 1
            if state["leg"] >= len(state["tour"]["stops"]):
                return dict(finished=True)
            planner.goal = None
        if planner.goal is None:
            result = planner.start_leg(cell, state["tour"]["stops"][state["leg"]])
        else:
            result = planner.update(position)
        return result

    def _join(self, state, result, position):
        """Re-anchor a delayed result at the latest pose with the same exact LOS rule."""
        planner = state["planner"]
        pos = np.asarray(position, float) / RESOLUTION
        cell = tuple(int(round(v)) for v in pos)
        for seen in self.observations:
            planner.observe(
                *virtual_sense(
                    self.truth,
                    np.rint(np.asarray(seen) / RESOLUTION).astype(int),
                    self.radius,
                )
            )
        self.observations = []
        planner.observe(*virtual_sense(self.truth, cell, self.radius))
        path = [np.asarray(p, float) for p in result["path"]]
        if not path:
            return None
        best = None
        for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
            delta = b - a
            t = (
                float(np.clip(np.dot(pos - a, delta) / np.dot(delta, delta), 0, 1))
                if np.any(delta)
                else 0
            )
            d = float(np.linalg.norm(pos - (a + t * delta)))
            if best is None or d < best[0]:
                best = (d, i)
        rest = path[best[1] + 1 :] if best is not None else [path[-1]]
        known_lethal = planner.known & planner.lethal
        if rest and line_of_sight_exact(known_lethal, tuple(pos), tuple(rest[0])):
            joined = [pos] + rest
        else:
            joined = [pos, np.asarray(cell, float)] + rest
        if len(path_lethal_cells(joined, known_lethal)):
            # Never apply a delayed result whose connector/path is now blocked.
            planner.pos = pos.copy()
            return None
        planner.path = joined
        planner.pos = pos.copy()
        planner.seg = 0
        planner.since_replan = 0.0
        return (np.asarray(joined) * RESOLUTION).tolist()

    def tick(self, position, sim_time):
        command = None
        if not self.finished:
            self.observations.append(tuple(position))
        if self.pending is not None:
            if not self.pending.done():
                return None
            version, state, requested_time, requested_position = self.pending_state
            try:
                result = self.pending.result()
            except Exception as exc:
                result = dict(
                    success=False,
                    replanned=True,
                    reason=type(exc).__name__ + ": " + str(exc),
                )
            self.pending = None
            if version == self.version and not self.finished:
                if result.get("finished"):
                    self.finished = True
                elif not result["success"]:
                    self.finished = True
                    command = dict(
                        state["mission"],
                        online_generated=True,
                        online_error=result["reason"],
                    )
                    command["plan_history"] = (
                        state["planner"].events if state["planner"] else []
                    )
                elif result["replanned"]:
                    path = self._join(state, result, position)
                    if path is not None:
                        planner = state["planner"]
                        self.current_path = path
                        command = dict(
                            state["mission"],
                            path=path,
                            online_generated=True,
                            replace_path=self.sent > 0,
                            reason=(
                                "next_leg"
                                if result["reason"] == "start_leg" and state["leg"]
                                else result["reason"]
                            ),
                            leg_index=state["leg"],
                            final_leg=state["leg"] == len(state["tour"]["stops"]) - 1,
                            n_replans=sum(
                                e["reason"] != "start_leg" for e in planner.events
                            ),
                            plan_time_s=result["plan_time_s"],
                            planned_at=sim_time,
                            revision=self.sent + 1,
                            order=state["tour"]["order"],
                            plan_history=planner.events.copy(),
                            handoff_latency_s=time.perf_counter()
                            - self.pending_started,
                            sim_handoff_s=sim_time - requested_time,
                            pose_shift_m=float(
                                np.linalg.norm(
                                    np.asarray(position) - requested_position
                                )
                            ),
                        )
                        self.sent += 1
                    else:
                        # A fresh plan is computed in the worker, never in tick.
                        state["planner"].since_replan = state["planner"].replan_every_m
        if not self.finished:
            self.state["observations"] = self.observations
            self.observations = []
            self.pending_state = (
                self.version,
                self.state,
                sim_time,
                np.asarray(position, float),
            )
            self.pending_started = time.perf_counter()
            self.pending = self.pool.submit(self._work, self.state, tuple(position))
        return command

    def close(self):
        self.stop()
        self.pool.shutdown(wait=True)


REPLAN_FIELDS = [
    "t",
    "reason",
    "plan_time_s",
    "leg_index",
    "n_replans",
    "revision",
    "handoff_latency_s",
    "sim_handoff_s",
    "pose_shift_m",
]


def record_plan_history(log, mission):
    target = log.folder / "replans.csv"
    if not target.exists():
        with target.open("w", newline="") as stream:
            csv.DictWriter(
                stream, fieldnames=REPLAN_FIELDS, lineterminator="\n"
            ).writeheader()
    target = log.folder / "plans.csv"
    exists = target.exists()
    previous = int(log.mission.get("logged_plan_calls", 0))
    with target.open("a", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["n_plans", "reason", "success", "plan_time_s"],
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        for event in mission.get("plan_history", []):
            if event["n_plans"] > previous:
                writer.writerow(event)
                previous = event["n_plans"]
    log.mission["logged_plan_calls"] = previous
    log._save()


def replace_running_path(log, mission, settings, sim_time, previous=None):
    """Validate before replacement, append an event, and retain the RunLog stream."""
    if mission["map_id"] != log.mission["map_id"] or mission.get(
        "id"
    ) != log.mission.get("id"):
        raise ValueError("replacement must belong to the same run")
    if int(mission["revision"]) <= int(log.mission.get("revision", 0)):
        raise ValueError("stale path revision")
    follower = MissionFollower(mission["path"], **settings)
    if previous is not None and previous.status == "running":
        for attr in ("_anchor", "_motion_t", "_last_t"):
            setattr(follower, attr, getattr(previous, attr))
    record_plan_history(log, mission)
    target = log.folder / "replans.csv"
    exists = target.exists()
    with target.open("a", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REPLAN_FIELDS, lineterminator="\n")
        if not exists:
            writer.writeheader()
        writer.writerow(
            dict(t=sim_time, **{k: mission[k] for k in REPLAN_FIELDS if k != "t"})
        )
    log.mission.update(
        {
            k: mission[k]
            for k in ("revision", "n_replans", "path", "leg_index", "final_leg")
        }
    )
    log._save()
    return follower
