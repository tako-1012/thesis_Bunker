# Task 001: online replanning with a coarse prior map

Read `AGENTS.md` (repository root) first. Base branch: `realtime-map`.

## Background
`conference/tapp/online.py` simulates a robot that only knows the terrain within
a sensing radius and replans while driving. Unknown cells currently get a
constant or "adaptive" (mean observed) cost. Results (`conference/results/online/`)
show the weak point: on `ridge` maps the robot cannot see the pass and makes
large detours (e.g. ridge, 100 m, seed 7: 216 m driven vs 95 m with the full map).

In practice a **coarse global map** is often available (e.g. a 5 m or 10 m DEM
from a national survey or satellite). Goal of this task: use such a coarse map
as the prior for unknown cells, while fine local sensing overrides it.

## What to implement

### 1. New module `conference/tapp/prior.py`
```python
def coarse_prior(tmap, cell_m, z_noise_m=0.0, seed=0) -> PriorMap
```
- Build the coarse elevation from the ground-truth `tmap.elev` (resolution
  `tapp.config.RESOLUTION` = 0.5 m) by **block-averaging** to `cell_m`
  (5.0 or 10.0 m; block = round(cell_m / 0.5) cells; handle edges by averaging
  the partial blocks), then **bilinearly upsampling** back to the 0.5 m grid
  (same shape as `tmap.elev`).
- Optionally add i.i.d. Gaussian noise `z_noise_m` to each **coarse** cell before
  upsampling (seeded with `np.random.default_rng(seed)`).
- Rocks are NOT visible in the coarse map (too small).
- Compute slope, roughness and cost on the upsampled elevation with exactly the
  same formulas as `tapp/traversability.py` (reuse `TraversabilityMap` with an
  all-False rock mask and the same `robot`/`weights` as `tmap`).
- `PriorMap` = a small dataclass with fields `cost` (float array) and
  `lethal` (bool array, slope > limit in the coarse map), plus `cell_m`.

### 2. Extend `run_online` in `conference/tapp/online.py`
Add two keyword arguments with defaults that keep the old behaviour **exactly**:
```python
prior_map=None, prior_lethal="soft"
```
- If `prior_map is None`: unchanged behaviour (regression test below).
- Otherwise, for unknown cells use `prior_map.cost` instead of the constant /
  adaptive prior. `unknown_cost` is then ignored.
- `prior_lethal`:
  - `"hard"`: unknown cells with `prior_map.lethal` are treated as lethal;
  - `"soft"`: they are not lethal but get cost 1.0 (the maximum);
  - `"ignore"`: only `prior_map.cost` is used.
- Replanning trigger: a newly observed cell on the remaining path triggers a
  replan if it is truly lethal, or if its true cost exceeds the cost that was
  **assumed for that cell** (prior cost, or 1.0 for soft-lethal) by more than
  0.05, or if a cell assumed lethal (hard mode) turns out traversable
  (this can open a shorter route).
- Keep the junction fix (new plans join through the current cell centre).
- Return value: also report `n_plans`, `plan_time`, `max_plan_time` as now.

### 3. Experiment script `conference/experiments/online_prior.py`
Same structure and summary style as `conference/experiments/online_replanning.py`
(copy and adapt; do not modify the original). Test seeds `range(10)`, kinds
`tapp.terrain.TERRAIN_TYPES`, sizes (50, 100). Sensing radius 15 m, `w=DEFAULT_W`,
planner `"TA*-S"`. Variants:

| name | settings |
|---|---|
| `oracle TA*-S` | full map known (`run_planner("TA*-S", ...)`) |
| `oracle A*` | `run_planner("A*", ...)` (energy reference) |
| `online adaptive` | `unknown_cost="adaptive"` (current best, no prior map) |
| `online prior5 soft` | `coarse_prior(tm, 5.0)`, `prior_lethal="soft"` |
| `online prior5 hard` | `coarse_prior(tm, 5.0)`, `prior_lethal="hard"` |
| `online prior10 soft` | `coarse_prior(tm, 10.0)`, `prior_lethal="soft"` |
| `online prior5 soft noisy` | `coarse_prior(tm, 5.0, z_noise_m=0.5, seed=<scenario seed>)`, soft |

Write `conference/results/online_prior/online_prior.csv` and print (and save as
`online_prior_log.txt`) the same summary tables as `online_replanning.py`:
overall medians (success, steep exposure, dL/dE vs oracle TA*-S, dE vs A*,
slope95, n_plans, plan_time, max plan time), per size, **per terrain** (dL vs
oracle), and the list of failures with reasons. Use `multiprocessing.Pool`.

### 4. Figure `conference/experiments/demo_online_prior.py`
Copy `demo_online.py` and show, for ridge/100 m/seed 7: full map, `online adaptive`,
`online prior5 soft`, `online prior10 soft`. Save to
`conference/results/online_prior/demo_online_prior_ridge_7.png` (NOT under `paper/`).

## Tests: new file `conference/tests/test_online.py` (runnable as `python3 -m tests.test_online`)
1. **Regression**: `run_online(..., planner="TA*-S", unknown_cost="adaptive",
   sense_radius_m=15.0, w=8.0)` with `prior_map=None` on `build("ridge", 100, 0)` and
   `build("ridge", 100, 7)` must give `evaluate(traj)["length_xy"]`
   = 154.688509 and 215.530174 (abs tol 1e-6), and `n_plans` = 81 and 103.
2. **Perfect prior**: a `PriorMap` built directly from the true `tmap.cost` /
   `tmap.lethal` (not via `coarse_prior`) with `prior_lethal="hard"` must give a
   driven length within 2 % of `run_planner("TA*-S", ...)` on 4 scenarios
   (one per terrain kind, 50 m, seed 0).
3. **Coarse prior sanity**: for `coarse_prior(tm, 5.0)` the output arrays have the
   same shape as `tm.elev`; with `cell_m=0.5` the prior cost equals `tm.cost`
   computed without rocks (abs tol 1e-9).
4. **Safety**: for all variants of section 3 on `ridge` and `craters`, 50 m,
   seeds 0-4: the driven trajectory never enters a truly lethal cell
   (`evaluate(...)["steep_len"] == 0` and `rock_hit` is False).

## Done when
- `python3 -m tests.test_planners` and `python3 -m tests.test_online` pass.
- `python3 experiments/online_prior.py` runs end to end; CSV, log and figure exist.
- No protected file (see `AGENTS.md`) changed: `git diff --stat realtime-map` shows
  only new files plus `conference/tapp/online.py`.
- PR against `realtime-map` with the report described in `AGENTS.md`.

## Out of scope
D* Lite / incremental search, occlusion modelling, changes to the paper.
