"""Incremental TA*-S with the unchanged run_online sensing/trigger/splice rules.

Coordinates in plans are grid cells; update receives metres. Sensing is perfect
radius visibility of a fixed truth map, without occlusion or sensor noise.
Waypoints passed to run_online_mission are ordered stops; include the base as
the last stop to close a tour. Ordering is performed once, before execution.
"""

import math
import time
import numpy as np
from .collision import line_of_sight_exact, segment_cells
from .config import DEFAULT_W, RESOLUTION
from .planners import astar, line_of_sight, smooth_cost_aware
from .tour import cost_matrix, solve_tour, tour_legs


def virtual_sense(truth_tm, pos_cell, radius_m):
    if not math.isfinite(radius_m) or radius_m < 0:
        raise ValueError("sensing radius must be finite and nonnegative")
    cell = np.rint(pos_cell).astype(int)
    if cell.shape != (2,) or (cell < 0).any() or (cell >= truth_tm.shape).any():
        raise ValueError("position outside truth map")
    r = int(round(radius_m / RESOLUTION))
    lo = np.maximum(cell - r, 0)
    hi = np.minimum(cell + r + 1, truth_tm.shape)
    xx, yy = np.ogrid[lo[0] : hi[0], lo[1] : hi[1]]
    mask = np.zeros(truth_tm.shape, bool)
    mask[lo[0] : hi[0], lo[1] : hi[1]] = (xx - cell[0]) ** 2 + (
        yy - cell[1]
    ) ** 2 <= r * r
    return mask, truth_tm.cost, truth_tm.lethal


class OnlinePlanner:
    def __init__(
        self,
        prior_cost,
        prior_lethal,
        robot_weights,
        *,
        w=DEFAULT_W,
        prior_lethal_mode="soft",
        unknown_cost="adaptive",
        replan_every_m=10.0,
        exact_los=True
    ):
        if prior_lethal_mode not in ("soft", "hard", "ignore"):
            raise ValueError("invalid prior lethal mode")
        if (prior_cost is None) != (prior_lethal is None):
            raise ValueError("both prior arrays or neither are required")
        if (
            not math.isfinite(w)
            or w < 0
            or not math.isfinite(replan_every_m)
            or replan_every_m <= 0
        ):
            raise ValueError("invalid weight or replanning distance")
        if unknown_cost != "adaptive" and (
            not math.isfinite(float(unknown_cost)) or float(unknown_cost) < 0
        ):
            raise ValueError("invalid unknown cost")
        # Costs already incorporate these weights; do not recompute terrain features.
        self.robot_weights = robot_weights
        self.prior_cost = (
            None if prior_cost is None else np.array(prior_cost, float, copy=True)
        )
        self.prior_lethal = (
            None if prior_lethal is None else np.array(prior_lethal, bool, copy=True)
        )
        if self.prior_cost is not None:
            if (
                self.prior_cost.ndim != 2
                or self.prior_cost.shape != self.prior_lethal.shape
                or not np.isfinite(self.prior_cost).all()
                or (self.prior_cost < 0).any()
            ):
                raise ValueError("invalid prior arrays")
        self.w, self.mode, self.unknown_cost = w, prior_lethal_mode, unknown_cost
        self.replan_every_m, self.exact_los = replan_every_m, exact_los
        self.los = line_of_sight_exact if exact_los else line_of_sight
        self.known = None
        self.pending_new = None
        self.path = []
        self.seg = 0
        self.plan_times = []
        self.events = []
        self.goal = None
        self.pos = None
        self.since_replan = 0.0

    def observe(self, mask, cost, lethal):
        mask, cost, lethal = (
            np.asarray(mask, bool),
            np.asarray(cost, float),
            np.asarray(lethal, bool),
        )
        if (
            mask.ndim != 2
            or mask.shape != cost.shape
            or mask.shape != lethal.shape
            or not np.isfinite(cost[mask]).all()
            or (cost[mask] < 0).any()
        ):
            raise ValueError("invalid observation arrays")
        if self.known is None:
            if self.prior_cost is not None and self.prior_cost.shape != mask.shape:
                raise ValueError("prior and observations must have the same shape")
            self.known = np.zeros(mask.shape, bool)
            self.pending_new = self.known.copy()
            self.cost = np.zeros(mask.shape, float)
            self.lethal = self.known.copy()
        if mask.shape != self.known.shape:
            raise ValueError("observation shape changed")
        new = mask & ~self.known
        self.known |= mask
        self.pending_new |= new
        self.cost[mask], self.lethal[mask] = cost[mask], lethal[mask]
        return new

    def _unknown(self):
        if self.unknown_cost == "adaptive":
            return float(self.cost[self.known].mean()) if self.known.any() else 0.0
        return float(self.unknown_cost)

    def planning_maps(self):
        if self.known is None:
            if self.prior_cost is None:
                raise ValueError(
                    "observe at least once before planning without a prior"
                )
            self.observe(
                np.zeros(self.prior_cost.shape, bool),
                self.prior_cost,
                self.prior_lethal,
            )
        lethal = self.known & self.lethal
        if self.prior_cost is None:
            assumed = self._unknown()
        else:
            assumed = (
                np.where(self.prior_lethal, 1.0, self.prior_cost)
                if self.mode == "soft"
                else self.prior_cost
            )
            if self.mode == "hard":
                lethal |= ~self.known & self.prior_lethal
        return lethal, 1.0 + self.w * np.where(self.known, self.cost, assumed)

    def _plan(self, reason, initial=False):
        lethal, mult = self.planning_maps()
        cell = tuple(int(round(v)) for v in self.pos)
        began = time.perf_counter()
        result = astar(lethal, cell, self.goal, mult)
        if result["success"]:
            path, _ = smooth_cost_aware(result["path"], lethal, mult, los=self.los)
        elapsed = time.perf_counter() - began
        self.plan_times.append(elapsed)
        self.since_replan = 0.0
        if result["success"]:
            if initial:
                self.path = [np.array(p, float) for p in path]
            else:
                rest = [np.array(p, float) for p in path[1:]]
                if rest and self.los(
                    self.known & self.lethal, tuple(self.pos), tuple(rest[0])
                ):
                    self.path = [self.pos.copy()] + rest
                else:
                    self.path = [self.pos.copy(), np.array(cell, float)] + rest
            self.seg = 0
        self.pending_new.fill(False)
        event = dict(
            reason=reason,
            success=bool(result["success"]),
            plan_time_s=elapsed,
            n_plans=len(self.plan_times),
            path=[p.tolist() for p in self.path] if result["success"] else [],
        )
        self.events.append({k: v for k, v in event.items() if k != "path"})
        return dict(event, replanned=True)

    def start_leg(self, pos_cell, goal_cell):
        self.pos = np.asarray(pos_cell, float).copy()
        self.goal = tuple(int(v) for v in goal_cell)
        if self.pos.shape != (2,) or not np.isfinite(self.pos).all():
            raise ValueError("invalid start")
        return self._plan("start_leg", initial=True)

    def _remaining(self):
        if len(self.path) < 2:
            return [self.pos]
        # Forward-only projection locates progress on the current polyline.
        best = None
        for i in range(self.seg, len(self.path) - 1):
            a, b = self.path[i : i + 2]
            delta = b - a
            t = (
                float(np.clip(np.dot(self.pos - a, delta) / np.dot(delta, delta), 0, 1))
                if np.any(delta)
                else 0.0
            )
            distance = float(np.linalg.norm(self.pos - (a + t * delta)))
            if best is None or distance < best[0]:
                best = (distance, i)
        self.seg = best[1]
        return [self.pos] + self.path[self.seg + 1 :]

    def update(self, pos_xy, *, distance_m=None):
        """Update from measured metres; simulator can supply exact polyline travel."""
        pos = np.asarray(pos_xy, float) / RESOLUTION
        if self.goal is None or pos.shape != (2,) or not np.isfinite(pos).all():
            raise ValueError("start a leg and provide a finite position first")
        moved = (
            float(np.linalg.norm(pos - self.pos) * RESOLUTION)
            if distance_m is None
            else float(distance_m)
        )
        if not math.isfinite(moved) or moved < 0:
            raise ValueError("invalid travelled distance")
        self.since_replan += moved
        self.pos = pos.copy()
        remaining = self._remaining()
        reason = "distance" if self.since_replan >= self.replan_every_m else None
        new = self.pending_new
        if (
            not reason
            and self.mode == "hard"
            and self.prior_lethal is not None
            and (new & self.prior_lethal & ~self.lethal).any()
        ):
            reason = "prior_cleared"
        if not reason and new.any():
            for a, b in zip(remaining[:-1], remaining[1:]):
                if self.exact_los:
                    points = segment_cells(a, b, self.known.shape)
                else:
                    n = max(int(np.ceil(np.linalg.norm(b - a) * 2)), 1)
                    points = np.rint(
                        a + (b - a) * np.linspace(0, 1, n + 1)[:, None]
                    ).astype(int)
                xs, ys = points[:, 0], points[:, 1]
                newly = new[xs, ys]
                if (newly & self.lethal[xs, ys]).any():
                    reason = "new_lethal"
                    break
                assumed = (
                    self._unknown()
                    if self.prior_cost is None
                    else (
                        np.where(
                            self.prior_lethal[xs, ys], 1.0, self.prior_cost[xs, ys]
                        )
                        if self.mode == "soft"
                        else self.prior_cost[xs, ys]
                    )
                )
                if (newly & (self.cost[xs, ys] > assumed + 0.05)).any():
                    reason = "new_cost"
                    break
        if reason:
            return self._plan(reason)
        self.pending_new.fill(False)
        return dict(
            success=True,
            replanned=False,
            reason="",
            path=[p.tolist() for p in self.path],
            n_plans=len(self.plan_times),
        )


def ordered_tour(prior_tm, start, waypoints):
    """Fix a closed directed terrain tour on the prior, as in mission.plan_mission."""
    points = [tuple(start)] + [tuple(p) for p in waypoints]
    sc = dict(tmap=prior_tm)
    matrix = cost_matrix(sc, points, kappa=1 / prior_tm.robot.rolling_coeff)
    order, _ = solve_tour(matrix["C"])
    if not order:
        raise ValueError("no tour on prior map")
    stops = [points[b] for _, b in tour_legs(order)]
    path = [points[0]]
    for a, b in tour_legs(order):
        path.extend(matrix["paths"][a, b][1:])
    return dict(order=order, stops=stops, path=path)


def run_fixed_mission(prior_tm, start, waypoints, *, w=DEFAULT_W):
    """Execute prior-only exact paths without sensing, including unsafe truth areas."""
    path, timings, legs = [tuple(start)], [], []
    pos = tuple(start)
    for goal in waypoints:
        began = time.perf_counter()
        result = astar(prior_tm.lethal, pos, tuple(goal), 1 + w * prior_tm.cost)
        if result["success"]:
            leg, _ = smooth_cost_aware(
                result["path"],
                prior_tm.lethal,
                1 + w * prior_tm.cost,
                los=line_of_sight_exact,
            )
            path.extend(leg[1:])
        timings.append(time.perf_counter() - began)
        legs.append(
            dict(
                success=bool(result["success"]),
                goal=list(goal),
                reason="" if result["success"] else "no_path",
            )
        )
        if not result["success"]:
            break
        pos = tuple(goal)
    success = len(legs) == len(waypoints) and all(l["success"] for l in legs)
    return dict(
        success=success,
        reason="" if success else "no_path",
        traj=path,
        n_plans=len(timings),
        n_replans=0,
        plan_times=timings,
        plan_time=sum(timings),
        max_plan_time=max(timings, default=0),
        legs=legs,
    )


def run_online_mission(
    truth_tm, prior, start, waypoints, *, radius_m, step_m=1.0, **kw
):
    """Follow ordered stops with run_online's exact idealized step integration."""
    if not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("step must be finite and positive")
    max_factor = kw.pop("max_factor", 6.0)
    planner = OnlinePlanner(
        None if prior is None else prior.cost,
        None if prior is None else prior.lethal,
        truth_tm.weights,
        **kw
    )
    traj, legs = [tuple(np.asarray(start, float))], []
    pos = np.array(start, float)
    for goal in waypoints:
        before = len(planner.plan_times)
        planner.observe(*virtual_sense(truth_tm, np.rint(pos).astype(int), radius_m))
        result = planner.start_leg(pos, goal)
        began = len(traj) - 1
        reason = "" if result["success"] else "no_path"
        travelled = 0.0
        straight = math.dist(pos, goal) * RESOLUTION
        path, seg = [np.array(p, float) for p in result["path"]], 0
        while not reason:
            left = step_m / RESOLUTION
            while left > 1e-9 and seg < len(path) - 1:
                delta = path[seg + 1] - pos
                length = float(np.hypot(*delta))
                if length <= left:
                    pos = path[seg + 1].copy()
                    seg += 1
                    left -= length
                else:
                    pos = pos + delta / length * left
                    left = 0.0
                traj.append(tuple(pos))
            moved = (step_m / RESOLUTION - left) * RESOLUTION
            travelled += moved
            if math.dist(pos, goal) < 0.75:
                traj.append(tuple(np.array(goal, float)))
                pos = np.array(goal, float)
                break
            if travelled > max_factor * straight or moved == 0:
                reason = "too_long" if moved else "no_progress"
                break
            planner.observe(
                *virtual_sense(truth_tm, np.rint(pos).astype(int), radius_m)
            )
            result = planner.update(pos * RESOLUTION, distance_m=moved)
            if not result["success"]:
                reason = "no_path"
                break
            if result["replanned"]:
                path, seg = [np.array(p, float) for p in result["path"]], 0
        legs.append(
            dict(
                start_index=began,
                end_index=len(traj) - 1,
                goal=list(goal),
                success=not reason,
                reason=reason,
                n_plans=len(planner.plan_times) - before,
            )
        )
        if reason:
            break
    success = len(legs) == len(waypoints) and all(leg["success"] for leg in legs)
    return dict(
        success=success,
        reason=legs[-1]["reason"] if legs else "",
        traj=traj,
        n_plans=len(planner.plan_times),
        n_replans=sum(e["reason"] != "start_leg" for e in planner.events),
        plan_times=planner.plan_times,
        plan_time=sum(planner.plan_times),
        max_plan_time=max(planner.plan_times, default=0.0),
        legs=legs,
        events=planner.events,
    )
