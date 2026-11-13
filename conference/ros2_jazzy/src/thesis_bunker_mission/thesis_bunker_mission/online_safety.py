"""Task034 latest-map handoff, bounded rejection and asynchronous safety recovery."""

import csv
import json
import time
from pathlib import Path
import numpy as np
from tapp.config import RESOLUTION
from tapp.collision import path_lethal_cells, line_of_sight_exact
from tapp.online_mission import ordered_tour, virtual_sense
from tapp.online_safety import SafetyOnlinePlanner, JOIN_TIMEOUT_S, SAFETY_STATES, validate_fixes
from .online_runtime import AsyncOnlineMission


def append_event(path, sim_time, event, detail):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open('a', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['sim_time', 'event', 'detail'], lineterminator='\n')
        if not exists:
            writer.writeheader()
        writer.writerow(dict(sim_time=sim_time, event=event, detail=json.dumps(detail, sort_keys=True)))


class SafetyRuntimeMixin:
    """Worker state is touched only after its old future has finished."""
    def __init__(self, *args, **kwargs):
        self.online_fixes = 'v1'
        plan_log = kwargs.get('plan_log')
        self.safety_log = Path(plan_log).parent/'safety_events.csv' if plan_log else None
        self.safety_events = []
        self._join_since = None
        self._safety_hold = False
        self._safety_request = None
        self._safety_now = 0.
        super().__init__(*args, **kwargs)

    def start(self, mission):
        super().start(mission)
        self._join_since = None
        self._safety_hold = False
        self._safety_request = None
        self.safety_events = []

    def record_safety(self, event, **detail):
        record = dict(sim_time=self._safety_now, event=event, detail=detail)
        self.safety_events.append(record)
        if self.safety_log is not None:
            append_event(self.safety_log, self._safety_now, event, detail)

    def safety_stop(self, status, *, revision=None):
        if status not in SAFETY_STATES or self.finished or self._safety_hold:
            return
        if revision is not None and revision != self.sent:
            return  # A delayed report from a replaced path cannot stop its successor.
        self._safety_hold = True
        self._safety_request = status
        self.version += 1  # Discard an in-flight pre-stop path.
        self.record_safety(status, revision=self.sent)

    def _join(self, state, result, position):
        planner = state['planner']
        pos = np.asarray(position, float)/RESOLUTION
        cell = tuple(int(round(v)) for v in pos)
        self._observe_join(planner, position)
        path = [np.asarray(p, float) for p in result['path']]
        blocked = (planner.known & planner.lethal).copy()
        if all(0 <= v < n for v, n in zip(cell, blocked.shape)):
            blocked[cell] = False  # Only the robot's actual cell is exempt.
        best = None
        for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
            delta = b-a
            f = float(np.clip(np.dot(pos-a, delta)/np.dot(delta, delta), 0, 1)) if np.any(delta) else 0.
            distance = float(np.linalg.norm(pos-(a+f*delta)))
            if best is None or distance < best[0]:
                best = distance, i
        rest = path[best[1]+1:] if best is not None else path[-1:]
        joined = ([pos]+rest if rest and line_of_sight_exact(blocked, pos, rest[0])
                  else [pos, np.asarray(cell, float)]+rest)
        hits = path_lethal_cells(joined, blocked) if rest else np.empty((0, 2), int)
        if not rest or len(hits):
            if self._join_since is None:
                self._join_since = self._safety_now
            self.record_safety('join_rejected', blocked_cells=hits.tolist())
            planner.pos = pos.copy()
            return None
        planner.path, planner.pos = joined, pos.copy()
        planner.seg, planner.since_replan = 0, 0.
        self._join_since = None
        self._safety_hold = False
        self.record_safety('join_accepted', blocked_cells=[], start_cell=list(cell))
        return (np.asarray(joined)*RESOLUTION).tolist()

    def _force_safety_plan(self, state, position, observe):
        reason = state.pop('_safety_replan', None)
        if reason is None:
            return None
        planner = state['planner']
        observe(planner)
        planner.pos = np.asarray(position, float)/RESOLUTION
        if planner.goal is None:
            planner.goal = state['tour']['stops'][state['leg']]
        return planner._plan(reason)

    def tick(self, position, sim_time):
        self._safety_now = float(sim_time)
        if (not self.finished and self._join_since is not None
                and sim_time-self._join_since >= JOIN_TIMEOUT_S):
            self.record_safety('join_rejected_timeout', duration_s=sim_time-self._join_since)
            self.finished = True
            self.version += 1
            planner = self.state.get('planner')
            return dict(self.state['mission'], online_generated=True, online_error='join_rejected',
                        plan_history=[{k: v for k, v in event.items() if k != 'failure_class'}
                                      for event in planner.events] if planner else [])
        if self._safety_request is not None:
            if self.pending is not None and not self.pending.done():
                return None
            if self.pending is not None:
                try:
                    self.pending.result()
                except Exception:
                    pass  # This invalidated pre-stop result must never be applied.
                self.pending = None
            self.state['_safety_replan'] = self._safety_request
            self.record_safety('safety_replan_requested', reason=self._safety_request, position=list(position))
            self._safety_request = None
        command = super().tick(position, sim_time)
        if command and command.get('reason') in SAFETY_STATES:
            self.record_safety('safety_replanned', reason=command['reason'], revision=command['revision'])
        return command


class SafetyAsyncOnlineMission(SafetyRuntimeMixin, AsyncOnlineMission):
    def _sense(self, planner, position):
        for seen in self.observations:
            planner.observe(*virtual_sense(self.truth, np.rint(np.asarray(seen)/RESOLUTION).astype(int), self.radius))
        self.observations = []
        planner.observe(*virtual_sense(self.truth, np.rint(np.asarray(position)/RESOLUTION).astype(int), self.radius))

    def _observe_join(self, planner, position):
        self._sense(planner, position)

    def _work(self, state, position):
        if state['planner'] is None:
            raw = np.asarray(state['mission']['points'], float).reshape(-1, 2)
            if not 1 <= len(raw) <= 12 or not np.isfinite(raw).all():
                raise ValueError('online missions require 1..12 finite waypoints')
            points = [tuple(int(round(v/RESOLUTION)) for v in p) for p in raw]
            cell = tuple(int(round(v/RESOLUTION)) for v in position)
            state['tour'] = ordered_tour(self.prior_tm, cell, points)
            state['planner'] = SafetyOnlinePlanner(self.prior.cost, self.prior.lethal, self.truth.weights,
                                                    prior_lethal_mode=self.mode)
        def observe_worker(planner):
            for seen in state.pop('observations', []):
                planner.observe(*virtual_sense(self.truth, np.rint(np.asarray(seen)/RESOLUTION).astype(int), self.radius))
            planner.observe(*virtual_sense(self.truth, np.rint(np.asarray(position)/RESOLUTION).astype(int), self.radius))
        result = self._force_safety_plan(state, position, observe_worker)
        return result if result is not None else super()._work(state, position)


def make_async_runtime(*args, online_fixes='none', **kwargs):
    validate_fixes(online_fixes)
    cls = SafetyAsyncOnlineMission if online_fixes == 'v1' else AsyncOnlineMission
    return cls(*args, **kwargs)


def handle_safety_state(runtime, state):
    if (getattr(runtime, 'online_fixes', 'none') == 'v1' and runtime.state
            and state.get('mission_id') == runtime.state['mission'].get('id')
            and state.get('status') in SAFETY_STATES):
        runtime.safety_stop(state['status'], revision=state.get('safety_revision'))
        return True
    return False
