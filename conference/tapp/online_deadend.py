"""Optional dead-end memory and per-leg hard-prior fallback for OnlinePlanner."""

import math
import numpy as np
from .collision import segment_cells
from .config import RESOLUTION
from .online_mission import OnlinePlanner, virtual_sense


class DeadendPlanner(OnlinePlanner):
    def __init__(self, *args, r_A=0.0, k_A=1.0, N_B=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not math.isfinite(r_A) or r_A < 0 or not math.isfinite(k_A) or k_A < 1:
            raise ValueError("memory radius must be nonnegative and multiplier at least one")
        if N_B is not None and (isinstance(N_B, bool) or int(N_B) != N_B or N_B < 0):
            raise ValueError("fallback threshold must be a nonnegative integer or None")
        self.r_A, self.k_A, self.N_B = float(r_A), float(k_A), N_B
        self.base_mode = self.mode
        self.memory = None
        self.leg_replans = 0
        self.memory_events = 0
        self.hard_switches = 0

    def planning_maps(self):
        lethal, mult = super().planning_maps()
        if self.r_A > 0 and self.k_A > 1:
            if self.memory is None:
                self.memory = np.zeros(self.known.shape, bool)
            penalized = self.memory & ~self.known
            mult[penalized] = 1 + (mult[penalized] - 1) * self.k_A
        return lethal, mult

    def _remember_blocked(self):
        if self.r_A == 0 or self.k_A == 1 or not self.pending_new.any():
            return
        blocked = []
        remaining = self._remaining()
        for a, b in zip(remaining[:-1], remaining[1:]):
            cells = segment_cells(a, b, self.known.shape)
            hit = self.pending_new[tuple(cells.T)] & self.lethal[tuple(cells.T)]
            blocked.extend(cells[hit])
        if not blocked:
            return
        if self.memory is None:
            self.memory = np.zeros(self.known.shape, bool)
        radius = self.r_A / RESOLUTION
        for cell in np.unique(np.asarray(blocked), axis=0):
            lo = np.maximum(0, np.floor(cell-radius).astype(int))
            hi = np.minimum(self.known.shape, np.ceil(cell+radius).astype(int)+1)
            xx, yy = np.ogrid[lo[0]:hi[0], lo[1]:hi[1]]
            region = np.s_[lo[0]:hi[0], lo[1]:hi[1]]
            self.memory[region] |= ((xx-cell[0])**2 + (yy-cell[1])**2 <= radius**2) & ~self.known[region]
        self.memory_events += 1

    def _plan(self, reason, initial=False):
        if reason != "start_leg":
            # Check the old remaining path even when the distance trigger won priority.
            self._remember_blocked()
            self.leg_replans += 1
            if self.N_B is not None and self.leg_replans > self.N_B and self.mode != "hard":
                self.mode = "hard"
                self.hard_switches += 1
        return super()._plan(reason, initial=initial)

    def start_leg(self, pos_cell, goal_cell):
        self.leg_replans = 0
        self.mode = self.base_mode
        return super().start_leg(pos_cell, goal_cell)


def run_deadend_mission(truth_tm, prior, start, waypoints, *, radius_m,
                        step_m=1.0, r_A=0.0, k_A=1.0, N_B=None, **kw):
    """Task-014 integration verbatim, with a different planner factory only.

    Memory persists through the tour; hard fallback resets at each new leg.
    Observation, triggers, joining, step size and the six-times limit are unchanged.
    """
    if not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("step must be finite and positive")
    max_factor = kw.pop("max_factor", 6.0)
    planner = DeadendPlanner(None if prior is None else prior.cost,
                             None if prior is None else prior.lethal,
                             truth_tm.weights, r_A=r_A, k_A=k_A, N_B=N_B, **kw)
    traj, legs = [tuple(np.asarray(start, float))], []
    pos = np.array(start, float)
    for goal in waypoints:
        before = len(planner.plan_times)
        planner.observe(*virtual_sense(truth_tm, np.rint(pos).astype(int), radius_m))
        result = planner.start_leg(pos, goal)
        began = len(traj)-1
        reason = "" if result["success"] else "no_path"
        travelled = 0.0
        straight = math.dist(pos, goal)*RESOLUTION
        path, seg = [np.array(p, float) for p in result["path"]], 0
        while not reason:
            left = step_m/RESOLUTION
            while left > 1e-9 and seg < len(path)-1:
                delta = path[seg+1]-pos
                length = float(np.hypot(*delta))
                if length <= left:
                    pos = path[seg+1].copy()
                    seg += 1
                    left -= length
                else:
                    pos = pos+delta/length*left
                    left = 0.0
                traj.append(tuple(pos))
            moved = (step_m/RESOLUTION-left)*RESOLUTION
            travelled += moved
            if math.dist(pos, goal) < .75:
                traj.append(tuple(np.array(goal, float)))
                pos = np.array(goal, float)
                break
            if travelled > max_factor*straight or moved == 0:
                reason = "too_long" if moved else "no_progress"
                break
            planner.observe(*virtual_sense(truth_tm, np.rint(pos).astype(int), radius_m))
            result = planner.update(pos*RESOLUTION, distance_m=moved)
            if not result["success"]:
                reason = "no_path"
                break
            if result["replanned"]:
                path, seg = [np.array(p, float) for p in result["path"]], 0
        legs.append(dict(start_index=began, end_index=len(traj)-1, goal=list(goal),
                         success=not reason, reason=reason,
                         n_plans=len(planner.plan_times)-before))
        if reason:
            break
    success = len(legs) == len(waypoints) and all(leg["success"] for leg in legs)
    return dict(success=success, reason=legs[-1]["reason"] if legs else "", traj=traj,
                n_plans=len(planner.plan_times),
                n_replans=sum(e["reason"] != "start_leg" for e in planner.events),
                plan_times=planner.plan_times, plan_time=sum(planner.plan_times),
                max_plan_time=max(planner.plan_times, default=0.0), legs=legs,
                events=planner.events, memory_events=planner.memory_events,
                hard_switches=planner.hard_switches)
