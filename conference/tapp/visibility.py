"""Ground-surface visibility using exact supercover cells and a raised sensor.

Each supercover cell height is compared to the ray at the projection of its
centre. Source/target cells are excluded from intermediate blockers; the target
is its surface centre. This is a discrete DEM occlusion model, not a LiDAR model.
"""

from functools import lru_cache
import math
import numpy as np
from .collision import segment_cells
from .config import RESOLUTION
from .online_mission import OnlinePlanner, virtual_sense


@lru_cache(maxsize=8)
def _rays(radius_cells):
    r = int(math.ceil(radius_cells))
    xx, yy = np.mgrid[-r:r+1, -r:r+1]
    targets = np.column_stack((xx.ravel(), yy.ravel()))
    targets = targets[(targets**2).sum(axis=1) <= radius_cells**2]
    cells, owners = [], []
    for index, target in enumerate(targets):
        if not target.any():
            continue
        touched = segment_cells((r,r), target+r, (2*r+1,2*r+1))-r
        touched = touched[np.any(touched != 0, axis=1) & np.any(touched != target, axis=1)]
        cells.extend(touched)
        owners.extend([index]*len(touched))
    cells = np.asarray(cells, dtype=int).reshape(-1,2)
    owners = np.asarray(owners, dtype=int)
    delta = targets[owners]
    t = np.sum(cells*delta,axis=1)/np.sum(delta*delta,axis=1)
    t = np.clip(t,0,1)
    for value in (targets,cells,owners,t):
        value.flags.writeable=False
    return targets,cells,owners,t


def visible_cells(elev, pos_cell, radius_m, sensor_height_m=0.8) -> np.ndarray:
    """Return visible cell centres, within the physical radius (0.5m grid).

    Positions are rounded to the nearest cell, as in virtual_sense. Sensor height
    is an assumption above the local surface, rather than measured LiDAR geometry.
    """
    z = np.asarray(elev, float)
    pos = np.asarray(pos_cell, float)
    if z.ndim != 2 or not np.isfinite(z).all() or pos.shape != (2,) or not np.isfinite(pos).all():
        raise ValueError("finite 2D terrain and a finite 2D position are required")
    if not math.isfinite(radius_m) or radius_m < 0 or not math.isfinite(sensor_height_m) or sensor_height_m <= 0:
        raise ValueError("radius must be nonnegative and sensor height positive")
    pos = np.rint(pos).astype(int)
    if (pos<0).any() or (pos>=z.shape).any():
        raise ValueError("position outside elevation map")
    targets,cells,owners,t = _rays(float(radius_m)/RESOLUTION)
    destinations = targets+pos
    inside = ((destinations>=0)&(destinations<z.shape)).all(axis=1)
    end_z = np.zeros(len(targets))
    end_z[inside] = z[tuple(destinations[inside].T)]
    middle = cells+pos
    valid = ((middle>=0)&(middle<z.shape)).all(axis=1) & inside[owners]
    owner = owners[valid]
    sensor_z = float(z[tuple(pos)])+sensor_height_m
    rise = end_z[owner]-sensor_z
    ray_height = sensor_z+t[valid]*rise
    blocked = z[tuple(middle[valid].T)] >= ray_height
    occluded = np.bincount(owner[blocked], minlength=len(targets))>0
    seen = destinations[inside & ~occluded]
    mask = np.zeros(z.shape, bool)
    mask[tuple(seen.T)] = True
    return mask


def _surface(truth_tm, rock_mask, obstacle_height_m):
    if not math.isfinite(obstacle_height_m) or obstacle_height_m < 0:
        raise ValueError("obstacle height must be nonnegative")
    # Heights already embedded in elev (e.g. boulder bumps) must not be added twice.
    # Pass only the raw mask of obstacles with missing height (LAS: driftwood).
    # tm.rock is inflated and also contains water/nodata, so it is not a surface.
    rock = np.zeros(truth_tm.shape,bool) if rock_mask is None else np.asarray(rock_mask,bool)
    if rock.shape != truth_tm.shape:
        raise ValueError("obstacle mask shape differs from terrain")
    return np.asarray(truth_tm.elev, float)+rock*obstacle_height_m


def virtual_sense_los(truth_tm, pos_cell, radius_m, sensor_height_m=0.8, *,
                      rock_mask=None, obstacle_height_m=0.3):
    """virtual_sense tuple; supply raw unmeasured obstacles for the assumed 0.3m height."""
    surface = _surface(truth_tm,rock_mask,obstacle_height_m)
    return visible_cells(surface,pos_cell,radius_m,sensor_height_m),truth_tm.cost,truth_tm.lethal


def run_visibility_mission(
    truth_tm, prior, start, waypoints, *, radius_m, step_m=1.0,
    sensor_height_m=0.8, rock_mask=None, obstacle_height_m=0.3, los=True, **kw
):
    """Follow ordered stops with run_online's exact idealized step integration."""
    if not math.isfinite(step_m) or step_m <= 0:
        raise ValueError("step must be finite and positive")
    max_factor = kw.pop("max_factor", 6.0)
    surface = _surface(truth_tm, rock_mask, obstacle_height_m)
    fractions, contacts = [], []
    last_observation = {}
    def sense(tm, pos, radius):
        disk, cost, lethal = virtual_sense(tm, pos, radius)
        mask = visible_cells(surface, pos, radius, sensor_height_m) if los else disk
        fractions.append(float(mask.sum() / disk.sum()))
        last_observation.update(cell=np.asarray(pos,int).copy(), mask=mask)
        return mask, cost, lethal
    planner = OnlinePlanner(
        None if prior is None else prior.cost,
        None if prior is None else prior.lethal,
        truth_tm.weights,
        **kw
    )
    traj, legs = [tuple(np.asarray(start, float))], []
    def record_position(point):
        touched=segment_cells(traj[-1],point,truth_tm.shape)
        hits=touched[truth_tm.lethal[tuple(touched.T)]]
        for hit in hits:
            known=bool(planner.known[tuple(hit)])
            visible=bool(last_observation["mask"][tuple(hit)])
            inside=bool(np.linalg.norm((hit-last_observation["cell"])*RESOLUTION)<=radius_m)
            cause=("already_known" if known else ("outside_last_radius" if not inside else "occluded"))
            contacts.append(dict(cell=hit.tolist(),segment_start=list(traj[-1]),segment_end=np.asarray(point,float).tolist(),
                                 sensor_cell=last_observation["cell"].tolist(),known_before=known,visible_last=visible,cause=cause))
        traj.append(tuple(point))
    pos = np.array(start, float)
    for goal in waypoints:
        before = len(planner.plan_times)
        planner.observe(*sense(truth_tm, np.rint(pos).astype(int), radius_m))
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
                record_position(pos)
            moved = (step_m / RESOLUTION - left) * RESOLUTION
            travelled += moved
            if math.dist(pos, goal) < 0.75:
                record_position(np.array(goal,float))
                pos = np.array(goal, float)
                break
            if travelled > max_factor * straight or moved == 0:
                reason = "too_long" if moved else "no_progress"
                break
            planner.observe(
                *sense(truth_tm, np.rint(pos).astype(int), radius_m)
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
        visible_fractions=fractions,
        contact_events=contacts,
    )
