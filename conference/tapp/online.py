"""Online planning with a limited sensing radius (exploratory, not in the paper).

The robot starts with no map knowledge. At every step it senses all cells
within `sense_radius_m` (perfect local mapping, no occlusion yet), updates its
planning map and moves `step_m` along the current plan. Unknown cells are
assumed traversable with cost `unknown_cost`: a number (0 = optimistic
free-space assumption) or "adaptive", the mean cost of the cells observed so
far. It replans when a newly observed cell on the remaining path is
lethal or costlier than assumed, and every `replan_every_m` metres.

The executed trajectory is evaluated on the ground truth with tapp.metrics.
"""
import math
import time

import numpy as np

from .config import RESOLUTION
from .planners import astar, smooth_cost_aware


class OnlineResult(dict):
    pass


def _disk(r_cells):
    yy, xx = np.mgrid[-r_cells:r_cells + 1, -r_cells:r_cells + 1]
    return xx ** 2 + yy ** 2 <= r_cells ** 2


def run_online(tm, start, goal, *, planner="TA*-S", w=8.0, unknown_cost=0.0,
               sense_radius_m=15.0, step_m=1.0, replan_every_m=10.0, max_factor=6.0):
    n = tm.shape[0]
    r = int(round(sense_radius_m / RESOLUTION))
    disk = _disk(r)
    known = np.zeros((n, n), dtype=bool)
    terrain_aware = planner in ("TA*", "TA*-S")

    def sense(cell):
        x, y = cell
        x0, x1 = max(x - r, 0), min(x + r + 1, n)
        y0, y1 = max(y - r, 0), min(y + r + 1, n)
        sub = disk[x0 - (x - r):x1 - (x - r), y0 - (y - r):y1 - (y - r)]
        before = known[x0:x1, y0:y1].copy()
        known[x0:x1, y0:y1] |= sub
        return known[x0:x1, y0:y1] & ~before, (x0, y0)

    def prior():
        if unknown_cost == "adaptive":
            return float(tm.cost[known].mean()) if known.any() else 0.0
        return float(unknown_cost)

    def planning_maps():
        lethal = known & tm.lethal
        cost = np.where(known, tm.cost, prior())
        return lethal, 1.0 + w * cost if terrain_aware else None

    def plan(cell):
        lethal, mult = planning_maps()
        if planner == "A*-HC":
            r_ = astar(lethal, cell, goal)
        else:
            r_ = astar(lethal, cell, goal, mult)
        if r_["success"] and planner == "TA*-S":
            p, ts = smooth_cost_aware(r_["path"], lethal, mult)
            r_ = dict(r_, path=p, time=r_["time"] + ts)
        return r_

    pos = np.array(start, dtype=float)
    traj = [tuple(pos)]
    sense(start)
    t_plan, n_plans, t_max = 0.0, 0, 0.0
    res = plan(start)
    t_plan += res["time"]; n_plans += 1; t_max = max(t_max, res["time"])
    if not res["success"]:
        return OnlineResult(success=False, reason="no_path", traj=traj, plan_time=t_plan,
                            n_plans=n_plans, max_plan_time=t_max)
    path = [np.array(p, dtype=float) for p in res["path"]]
    seg = 0                                   # index of current segment start
    since_replan = 0.0
    straight = math.dist(start, goal) * RESOLUTION
    travelled = 0.0
    step_c = step_m / RESOLUTION
    t0 = time.perf_counter()
    while True:
        # advance step_c cells along the polyline
        left = step_c
        while left > 1e-9 and seg < len(path) - 1:
            d = path[seg + 1] - pos
            L = float(np.hypot(*d))
            if L <= left:
                pos = path[seg + 1].copy()
                seg += 1
                left -= L
            else:
                pos = pos + d / L * left
                left = 0.0
            traj.append(tuple(pos))
        moved = step_c - left
        travelled += moved * RESOLUTION
        since_replan += moved * RESOLUTION
        cell = (int(round(pos[0])), int(round(pos[1])))
        if math.dist(pos, goal) < 0.75:
            break
        if travelled > max_factor * straight:
            return OnlineResult(success=False, reason="too_long", traj=traj, plan_time=t_plan,
                                n_plans=n_plans, max_plan_time=t_max)
        new, (ox, oy) = sense(cell)
        # does newly observed terrain invalidate the remaining plan?
        trigger = since_replan >= replan_every_m
        if not trigger and new.any():
            rem = np.array([pos] + path[seg + 1:])
            for a, b in zip(rem[:-1], rem[1:]):
                L = max(int(np.ceil(np.hypot(*(b - a)) * 2)), 1)
                t = np.linspace(0, 1, L + 1)[:, None]
                pts = np.rint(a + (b - a) * t).astype(int)
                xs, ys = pts[:, 0], pts[:, 1]
                newly = np.zeros(len(xs), dtype=bool)
                inside = (xs >= ox) & (xs < ox + new.shape[0]) & (ys >= oy) & (ys < oy + new.shape[1])
                newly[inside] = new[xs[inside] - ox, ys[inside] - oy]
                if (newly & tm.lethal[xs, ys]).any():
                    trigger = True
                    break
                if terrain_aware and (newly & (tm.cost[xs, ys] > prior() + 0.05)).any():
                    trigger = True
                    break
        if trigger:
            res = plan(cell)
            t_plan += res["time"]; n_plans += 1; t_max = max(t_max, res["time"])
            since_replan = 0.0
            if not res["success"]:
                return OnlineResult(success=False, reason="no_path", traj=traj, plan_time=t_plan,
                                    n_plans=n_plans, max_plan_time=t_max)
            path = [pos.copy()] + [np.array(p, dtype=float) for p in res["path"][1:]]
            seg = 0
    traj.append(tuple(np.array(goal, dtype=float)))
    return OnlineResult(success=True, reason="", traj=traj, plan_time=t_plan, n_plans=n_plans,
                        max_plan_time=t_max, sim_time=time.perf_counter() - t0)
