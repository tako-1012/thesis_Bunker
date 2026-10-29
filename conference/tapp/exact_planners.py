"""Existing planner dispatcher with opt-in exact TA*-S smoothing for thesis work."""

from .config import DEFAULT_W
from .scenario import run_planner
from .planners import astar, smooth_cost_aware
from .collision import line_of_sight_exact


def run_planner_exact(name, sc, w=DEFAULT_W, plan_map=None):
    if name != "TA*-S":
        return run_planner(name, sc, w=w, plan_map=plan_map)
    tm = plan_map or sc["tmap"]
    mult = 1 + w * tm.cost
    r = astar(tm.lethal, sc["start"], sc["goal"], mult)
    if r["success"]:
        path, ts = smooth_cost_aware(
            r["path"], tm.lethal, mult, los=line_of_sight_exact
        )
        r = dict(r, path=path, time=r["time"] + ts, smooth_time=ts)
    return r
