"""Euler unicycle tracking only: no slip, terrain dynamics or collision avoidance."""

import math
import numpy as np
from .config import RESOLUTION
from .collision import path_lethal_cells
from .pure_pursuit import PurePursuit, path_distance


def initial_pose(path_xy):
    from .pure_pursuit import prepare_path

    p = prepare_path(path_xy)
    yaw = math.atan2(*(p[1] - p[0])[::-1]) if len(p) > 1 else 0.0
    return [float(p[0, 0]), float(p[0, 1]), yaw]


def simulate(
    sc, path_xy, start_pose, dt=0.05, max_time_s=None, controller_kwargs=None
) -> dict:
    controller = PurePursuit(path_xy, **(controller_kwargs or {}))
    pose = np.asarray(start_pose, dtype=float).copy()
    if pose.shape != (3,) or not np.isfinite(pose).all():
        raise ValueError("開始姿勢が不正です")
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError("時間刻みは正の有限値にしてください")
    if max_time_s is None:
        max_time_s = max(
            60.0,
            4 * controller.arc[-1] / controller.v_max
            + 2 * math.pi * len(controller.path) / controller.w_max,
        )
    if not math.isfinite(max_time_s) or max_time_s <= 0 or max_time_s / dt > 2_000_000:
        raise ValueError("シミュレーションの時間範囲が不正です")
    trace = [[0.0, *pose.tolist()]]
    done = False
    for step in range(int(math.ceil(max_time_s / dt))):
        v, w, done = controller.command(pose)
        if done:
            break
        delta_t = min(dt, max_time_s - trace[-1][0])
        pose[0] += v * math.cos(pose[2]) * delta_t
        pose[1] += v * math.sin(pose[2]) * delta_t
        pose[2] = (pose[2] + w * delta_t + math.pi) % (2 * math.pi) - math.pi
        trace.append([min((step + 1) * dt, max_time_s), *pose.tolist()])
    if not done:
        done = controller.command(pose)[2]
    xy = np.asarray(trace)[:, 1:3]
    distances = np.array([path_distance(p, controller.path) for p in xy])
    hits = path_lethal_cells(xy / RESOLUTION, sc["tmap"].lethal)
    outside = np.any(
        (xy < 0) | (xy > (np.array(sc["tmap"].shape) - 1) * RESOLUTION), axis=1
    )
    return dict(
        trajectory=trace,
        elapsed_s=float(trace[-1][0]),
        deviation_mean_m=float(distances.mean()),
        deviation_max_m=float(distances.max()),
        path_lethal_cells=len(hits),
        lethal_cells=hits.tolist(),
        out_of_bounds_samples=int(outside.sum()),
        completed=bool(done),
        dt=dt,
        lookahead_m=controller.lookahead_m,
    )
