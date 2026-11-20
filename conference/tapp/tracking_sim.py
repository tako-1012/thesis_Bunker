"""Euler tracking with optional first-order actuator lag and weaker turning."""

import math

import numpy as np

from .pure_pursuit import PurePursuit
from .tracking import CornerSlowPursuit, validate_tracking

TIME_CONSTANT_S = .3
TURN_GAIN = .8


def lagged_velocity(v, w, v_command, w_command, dt):
    """Exact first-order velocity update over one constant-command step."""
    fraction = -math.expm1(-dt/TIME_CONSTANT_S)
    return v+fraction*(v_command-v), w+fraction*(TURN_GAIN*w_command-w)


def simulate_tracking(path, start_pose, *, tracking='default', lagged=False, dt=.05, max_time_s=None):
    """Same Euler pose integration and goal criterion as robot_sim."""
    validate_tracking(tracking)
    ctl = (CornerSlowPursuit if tracking == 'corner_slow' else PurePursuit)(path)
    pose = np.asarray(start_pose, float).copy()
    if pose.shape != (3,) or not np.isfinite(pose).all():
        raise ValueError('start pose must be finite xy/yaw')
    if not math.isfinite(dt) or dt <= 0:
        raise ValueError('time step must be positive and finite')
    if max_time_s is None:
        max_time_s = max(60., 4*ctl.arc[-1]/ctl.v_max + 2*math.pi*len(ctl.path)/ctl.w_max)
    if not math.isfinite(max_time_s) or max_time_s <= 0 or max_time_s/dt > 2_000_000:
        raise ValueError('invalid simulation horizon')
    trace = [[0., *pose.tolist()]]
    v = w = 0.
    done = False
    for step in range(math.ceil(max_time_s/dt)):
        command_v, command_w, done = ctl.command(pose)
        if done:
            break
        h = min(dt, max_time_s-trace[-1][0])
        v, w = lagged_velocity(v, w, command_v, command_w, h) if lagged else (command_v, command_w)
        pose[0] += v*math.cos(pose[2])*h
        pose[1] += v*math.sin(pose[2])*h
        pose[2] = (pose[2]+w*h+math.pi) % (2*math.pi)-math.pi
        trace.append([min((step+1)*dt, max_time_s), *pose.tolist()])
    if not done:
        done = ctl.command(pose)[2]
    return dict(trajectory=trace, elapsed_s=float(trace[-1][0]), completed=bool(done))
