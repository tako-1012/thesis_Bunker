"""Alongshore scenarios with water inflated as an obstacle and unchanged costs."""

import time
import numpy as np
from .config import Robot, CostWeights
from .beach_terrain import BEACH_TYPES, generate_beach
from .terrain import sample_start_goal
from .traversability import TraversabilityMap
from .planners import astar


def build_beach(kind, side_m, seed, weights=CostWeights(), robot=Robot(), max_tries=20):
    start = time.perf_counter()
    index = BEACH_TYPES.index(kind)
    for k in range(max_tries):
        sd = int(
            np.random.SeedSequence([seed, 2000 + index, int(side_m), k]).generate_state(
                1
            )[0]
        )
        t = generate_beach(kind, side_m, sd)
        tm = TraversabilityMap(t["elev"], t["rock"] | t["water"], robot, weights)
        # The landward strip remains forbidden even on its locally noisy edge.
        # Steep slopes define it in the supplied TraversabilityMap; choose endpoints outside it.
        candidate = tm.lethal | t["landward"]
        sg = sample_start_goal(candidate, side_m, np.random.default_rng(sd + 7))
        if sg is not None and astar(tm.lethal, *sg)["success"]:
            return dict(
                kind=kind,
                side_m=side_m,
                seed=seed,
                used_seed=sd,
                redraws=k,
                tmap=tm,
                start=sg[0],
                goal=sg[1],
                terrain=t,
                water=t["water"],
                wet=t["wet"],
                generation_time=time.perf_counter() - start,
            )
    raise RuntimeError(f"no feasible beach scenario for {kind} {side_m} {seed}")
