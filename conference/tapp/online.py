"""Online planning with a limited sensing radius (exploratory, not in the paper).

The robot starts with no map knowledge. At every step it senses all cells
within `sense_radius_m` (perfect local mapping, no occlusion yet), updates its
planning map and moves `step_m` along the current plan. Unknown cells are
assumed traversable with cost `unknown_cost`: a number (0 = optimistic
free-space assumption) or "adaptive", the mean cost of the cells observed so
far. An optional coarse prior supplies unknown costs and a hard, soft or ignored
lethal mask instead. It replans when a newly observed cell on the remaining path is
lethal or costlier than assumed, and every `replan_every_m` metres.
The optional D* Lite backend reuses searches for fixed unknown-cell priors.
`record_plan_times=True` adds per-call wall times with identical boundaries:
search/update/extraction/smoothing, excluding map assembly and execution.
Legacy A* timing fields retain their original measurement boundaries.

The executed trajectory is evaluated on the ground truth with tapp.metrics.
"""
import math
import time

import numpy as np

from .collision import line_of_sight_exact, segment_cells
from .config import RESOLUTION
from .dstar_lite import DStarLite
from .planners import astar, line_of_sight, smooth_cost_aware


class OnlineResult(dict):
    pass


def _disk(r_cells):
    yy, xx = np.mgrid[-r_cells:r_cells + 1, -r_cells:r_cells + 1]
    return xx ** 2 + yy ** 2 <= r_cells ** 2


def run_online(tm, start, goal, *, planner="TA*-S", w=8.0, unknown_cost=0.0,
               sense_radius_m=15.0, step_m=1.0, replan_every_m=10.0, max_factor=6.0,
               prior_map=None, prior_lethal="soft", search="astar", record_plan_times=False, exact_los=False):
    if search not in ("astar", "dstar_lite"):
        raise ValueError("search must be 'astar' or 'dstar_lite'")
    if search == "dstar_lite":
        if prior_map is None and unknown_cost == "adaptive":
            raise ValueError("D* Lite requires a fixed unknown-cell cost or a prior map")
        if planner == "A*-HC":
            raise NotImplementedError("D* Lite is not implemented for A*-HC")
    if prior_lethal not in ("hard", "soft", "ignore"):
        raise ValueError("prior_lethal must be 'hard', 'soft' or 'ignore'")
    if prior_map is not None:
        if prior_map.cost.shape != tm.shape or prior_map.lethal.shape != tm.shape:
            raise ValueError("prior arrays must match the terrain shape")
        assumed_cost = (np.where(prior_map.lethal, 1.0, prior_map.cost)
                        if prior_lethal == "soft" else prior_map.cost)
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
        if prior_map is None:
            cost = np.where(known, tm.cost, prior())
        else:
            if prior_lethal == "hard":
                lethal = lethal | (~known & prior_map.lethal)
            cost = np.where(known, tm.cost, assumed_cost)
        return lethal, 1.0 + w * cost if terrain_aware else None

    los = line_of_sight_exact if exact_los else line_of_sight
    dstar = None
    last_lethal = last_mult = None
    plan_times = []
    timing = {"plan_times": plan_times} if record_plan_times else {}

    def plan(cell):
        nonlocal dstar, last_lethal, last_mult
        lethal, mult = planning_maps()
        if search == "dstar_lite" or record_plan_times:
            t0 = time.perf_counter()
        if search == "dstar_lite":
            if mult is None:
                mult = np.ones(tm.shape, dtype=float)
            if dstar is None:
                dstar = DStarLite(lethal, mult, cell, goal)
            else:
                changed = np.argwhere((lethal != last_lethal) | (mult != last_mult))
                dstar.update_cells(changed, lethal, mult)
                dstar.move_start(cell)
            last_lethal, last_mult = lethal, mult
            stats = dstar.compute()
            p = dstar.path()
            r_ = dict(stats, path=p, success=p is not None)
        elif planner == "A*-HC":
            r_ = astar(lethal, cell, goal)
        else:
            r_ = astar(lethal, cell, goal, mult)
        if r_["success"] and planner == "TA*-S":
            if exact_los:
                p, ts = smooth_cost_aware(r_["path"], lethal, mult, los=los)
            else:
                p, ts = smooth_cost_aware(r_["path"], lethal, mult)
            r_ = dict(r_, path=p, time=r_["time"] + ts)
        if search == "dstar_lite" or record_plan_times:
            elapsed = time.perf_counter() - t0
            if search == "dstar_lite":
                r_["time"] = elapsed
            if record_plan_times:
                plan_times.append(elapsed)
        return r_

    pos = np.array(start, dtype=float)
    traj = [tuple(pos)]
    sense(start)
    t_plan, n_plans, t_max = 0.0, 0, 0.0
    res = plan(start)
    t_plan += res["time"]; n_plans += 1; t_max = max(t_max, res["time"])
    if not res["success"]:
        return OnlineResult(success=False, reason="no_path", traj=traj, plan_time=t_plan,
                            n_plans=n_plans, max_plan_time=t_max, **timing)
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
                                n_plans=n_plans, max_plan_time=t_max, **timing)
        new, (ox, oy) = sense(cell)
        # does newly observed terrain invalidate the remaining plan?
        trigger = since_replan >= replan_every_m
        if prior_map is not None and prior_lethal == "hard" and new.any():
            region = np.s_[ox:ox + new.shape[0], oy:oy + new.shape[1]]
            # Clearing a false prior obstacle can open a route off the old path.
            trigger |= bool((new & prior_map.lethal[region] & ~tm.lethal[region]).any())
        if not trigger and new.any():
            rem = np.array([pos] + path[seg + 1:])
            for a, b in zip(rem[:-1], rem[1:]):
                if exact_los:
                    pts = segment_cells(a, b, tm.shape)
                else:
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
                assumed = prior() if prior_map is None else assumed_cost[xs, ys]
                if (terrain_aware or prior_map is not None) and (newly & (tm.cost[xs, ys] > assumed + 0.05)).any():
                    trigger = True
                    break
        if trigger:
            res = plan(cell)
            t_plan += res["time"]; n_plans += 1; t_max = max(t_max, res["time"])
            since_replan = 0.0
            if not res["success"]:
                return OnlineResult(success=False, reason="no_path", traj=traj, plan_time=t_plan,
                                    n_plans=n_plans, max_plan_time=t_max, **timing)
            # join the new plan through the centre of the current cell, so the
            # connecting segment never cuts across a lethal neighbour
            rest = [np.array(p, dtype=float) for p in res["path"][1:]]
            if rest and los(known & tm.lethal, tuple(pos), tuple(rest[0])):
                path = [pos.copy()] + rest
            else:
                path = [pos.copy(), np.array(cell, dtype=float)] + rest
            seg = 0
    traj.append(tuple(np.array(goal, dtype=float)))
    return OnlineResult(success=True, reason="", traj=traj, plan_time=t_plan, n_plans=n_plans,
                        max_plan_time=t_max, sim_time=time.perf_counter() - t0, **timing)
