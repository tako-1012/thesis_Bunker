"""Scenario construction and the set of compared planners."""
import numpy as np

from . import terrain
from .config import Robot, CostWeights, DEFAULT_W
from .planners import astar, lazy_theta, smooth_cost_aware
from .traversability import TraversabilityMap

PLANNERS = ("A*", "Theta*", "A*-HC", "TA*", "TA*-S")


def build(kind, side_m, seed, weights=CostWeights(), robot=Robot(), max_tries=20):
    """Deterministic scenario; re-draws (seed offset) until a feasible path exists
    under the hard slope constraint, so every planner has a solvable instance."""
    kidx = terrain.TERRAIN_TYPES.index(kind)
    for k in range(max_tries):
        sd = int(np.random.SeedSequence([seed, kidx, int(side_m), k]).generate_state(1)[0])
        t = terrain.generate(kind, side_m, sd)
        tm = TraversabilityMap(t["elev"], t["rock"], robot, weights)
        sg = terrain.sample_start_goal(tm.lethal, side_m, np.random.default_rng(sd + 7))
        if sg is None:
            continue
        s, g = sg
        if astar(tm.lethal, s, g)["success"]:
            return {"kind": kind, "side_m": side_m, "seed": seed, "used_seed": sd,
                    "redraws": k, "tmap": tm, "start": s, "goal": g}
    raise RuntimeError(f"no feasible scenario for {kind} {side_m} {seed}")


def run_planner(name, sc, w=DEFAULT_W, plan_map=None):
    """plan_map: TraversabilityMap used for planning (defaults to ground truth)."""
    tm = plan_map or sc["tmap"]
    s, g = sc["start"], sc["goal"]
    if name == "A*":
        return astar(tm.rock, s, g)
    if name == "Theta*":
        return lazy_theta(tm.rock, s, g)
    if name == "A*-HC":
        return astar(tm.lethal, s, g)
    mult = 1.0 + w * tm.cost
    if name == "TA*":
        return astar(tm.lethal, s, g, mult)
    if name == "TA*-S":
        r = astar(tm.lethal, s, g, mult)
        if r["success"]:
            path, ts = smooth_cost_aware(r["path"], tm.lethal, mult)
            r = dict(r, path=path, time=r["time"] + ts, smooth_time=ts)
        return r
    raise ValueError(name)
