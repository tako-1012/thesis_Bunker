"""Feasible natural-terrain scenarios with a separate deterministic seed namespace."""

import time
import numpy as np
from .config import Robot, CostWeights
from .natural_terrain import NATURAL_TYPES, generate_natural
from .terrain import sample_start_goal
from .traversability import TraversabilityMap
from .planners import astar


def build_natural(
    kind, side_m, seed, weights=CostWeights(), robot=Robot(), max_tries=20
):
    start = time.perf_counter()
    index = NATURAL_TYPES.index(kind)
    for k in range(max_tries):
        sd = int(
            np.random.SeedSequence([seed, 1000 + index, int(side_m), k]).generate_state(
                1
            )[0]
        )
        terrain = generate_natural(kind, side_m, sd)
        tm = TraversabilityMap(terrain["elev"], terrain["rock"], robot, weights)
        sg = sample_start_goal(tm.lethal, side_m, np.random.default_rng(sd + 7))
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
                terrain=terrain,
                generation_time=time.perf_counter() - start,
            )
    raise RuntimeError(f"no feasible natural scenario for {kind} {side_m} {seed}")
