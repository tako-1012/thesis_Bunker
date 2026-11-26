"""Opt-in goal selection on immutable LiDAR planning snapshots."""

import time

import numpy as np

from tapp.config import RESOLUTION
from tapp.distance_clearance import connector_clear
from tapp.goal_region import blocked_reason, choose_goal, eligible, in_grid
from tapp.planners import smooth_cost_aware
from tapp.traversability import inflate
from .online_batch_runtime import CsvChunks


class RingPlanner:
    def _original_open(self):
        original = self.original_goal
        tracking = getattr(self, 'tracking_clearance', None)
        if tracking is not None and in_grid(original, tracking.base_hard.shape) and tracking.base_hard[original]:
            return False
        return (in_grid(original, self.snapshot['lethal'].shape)
                and (not self.snapshot['lethal'][original]
                     or not getattr(self, 'goal_overrides', {}).get(original, True)))

    def _ring_eligible(self, cell):
        snapshot = self.snapshot
        blocked = snapshot['lethal']
        tracking = getattr(self, 'tracking_clearance', None)
        if tracking is not None:
            blocked = blocked | tracking.protected(self.tracking_relaxed_layers)
        return eligible(cell, blocked, snapshot['seen'], self.ring_steep_halo)

    def _plan(self, reason, initial=False):
        self.goal = self.original_goal
        if self._original_open():
            self.ring_blocked = False
        else:
            self.ring_blocked = True
            self.ring_began = time.perf_counter()
            snapshot = self.snapshot
            start = tuple(np.rint(self.pos).astype(int))
            blocked, mult = snapshot['lethal'], snapshot['cost']
            tracking = getattr(self, 'tracking_clearance', None)
            if tracking is not None:
                # A substitute has to be reachable under the start's
                # exception. It cannot itself ask to open another layer.
                blocked, mult, labels, self.tracking_relaxed_layers, _ = tracking.project(
                    blocked, mult, start, None, self.w)
                self.ring_tracking = blocked, mult, labels
            choice = choose_goal(start, self.original_goal, blocked, mult,
                                 snapshot['seen'], self.ring_steep_halo)
            self.ring_route = choice[1]['path'] if choice else None
            if choice:
                self.goal = choice[0]
        if self.goal == self.original_goal:
            self.snapshot.pop('original_goal', None)
        else:
            self.snapshot['original_goal'] = np.asarray(self.original_goal, int)
        return super()._plan(reason, initial=initial)

    def _unrelaxed_plan(self, reason, initial):
        if not self.ring_blocked:
            return super()._unrelaxed_plan(reason, initial)
        snapshot = self.snapshot
        blocked, mult = snapshot['lethal'], snapshot['cost']
        tracking = getattr(self, 'tracking_clearance', None)
        if tracking is not None:
            blocked, mult, labels = self.ring_tracking
        route = self.ring_route
        if route is not None:
            geometry = getattr(self, 'distance_geometry', None)
            smooth = geometry.smooth if geometry is not None else smooth_cost_aware
            path, _ = smooth(route, blocked, mult, los=self.los)
            self.path = [np.asarray(p, float) for p in path]
            if not initial:
                rest = self.path[1:]
                start = np.asarray(route[0], float)
                if not rest or not connector_clear(self, blocked, self.pos, start, rest[0]):
                    rest = [start]+rest
                self.path = [self.pos.copy()]+rest
            self.seg = 0
        self.plan_times.append(time.perf_counter()-self.ring_began)
        self.since_replan = 0.
        self.pending_new.fill(False)
        event = dict(reason=reason, success=route is not None, plan_time_s=self.plan_times[-1],
                     n_plans=len(self.plan_times))
        if tracking is not None:
            event['tracking_margin_relaxed'] = labels
        self.events.append(event)
        return dict(event, path=[p.tolist() for p in self.path] if route is not None else [], replanned=True)


class RingRuntimeMixin:
    goal_region = 'ring'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.goal_log = CsvChunks(self.folder/'goal_region.csv',
            ['sim_time', 'leg_index', 'map_version', 'event', 'original_x', 'original_y',
             'goal_x', 'goal_y', 'shift_m', 'reason'])

    def _new_planner(self, cls, stops):
        return super()._new_planner(cls, stops, mixin=RingPlanner)

    def _observe(self, planner):
        state = self.state
        planner.original_goal = state['tour']['stops'][state['leg']]
        super()._observe(planner)
        # Even when task055 suppresses some inflation in the map, a ring
        # endpoint must be outside the full steep neighbourhood.
        planner.ring_steep_halo = inflate(planner.snapshot['steep'], self.mapper.robot.footprint_radius)

    def _plan_leg(self, state, position, cell):
        planner = state['planner']
        original = state['tour']['stops'][state['leg']]
        if planner.goal is not None:
            at_original = planner.goal == original
            original_open = planner._original_open()
            applied = state.get('ring_applied') == (state['leg'], planner.goal)
            if (at_original != original_open or not applied
                    or (not at_original and not planner._ring_eligible(planner.goal))):
                planner.pos = np.asarray(position, float)/RESOLUTION
                return planner._plan('goal_region_restore' if not at_original and original_open
                                     else 'goal_region_replan')
            if np.linalg.norm(np.asarray(position)-np.asarray(planner.goal)*RESOLUTION) <= .3:
                state.setdefault('ring_outcomes', []).append(dict(index=state['leg'], target=list(original),
                    goal=list(planner.goal), outcome='arrived' if at_original else 'nearby'))
                state['leg'] += 1
                if state['leg'] == len(state['tour']['stops']):
                    return dict(finished=True)
                original = state['tour']['stops'][state['leg']]
                planner.original_goal = original
                planner.goal = None
        if planner.goal is None:
            return planner.start_leg(cell, original)
        return planner.update(position)

    def _observe_join(self, planner, position):
        # _join captures once, so the eligibility and inherited connector
        # checks see the same version of the latest map.
        self.observations = []

    def _join(self, state, result, position):
        planner = state['planner']
        self._observe(planner)
        snapshot = planner.snapshot
        original, goal = planner.original_goal, planner.goal
        original_open = planner._original_open()
        if goal != original:
            start = tuple(np.rint(np.asarray(position)/RESOLUTION).astype(int))
            start_clear = in_grid(start, snapshot['lethal'].shape) and not snapshot['lethal'][start]
            allowed = not original_open and start_clear and planner._ring_eligible(goal)
        else:
            allowed = original_open
        joined = super()._join(state, result if allowed else dict(result, path=[]), position)
        if joined is not None:
            applied, previous = (state['leg'], goal), state.get('ring_applied')
            if applied != previous and (goal != original or
                    (previous is not None and previous[0] == state['leg'] and previous[1] != original)):
                self.goal_log.write(dict(sim_time=snapshot['sim_time'], leg_index=state['leg'],
                    map_version=snapshot['version'], event='restore' if goal == original else 'substitute',
                    original_x=original[0], original_y=original[1], goal_x=goal[0], goal_y=goal[1],
                    shift_m=float(np.linalg.norm(np.subtract(goal, original))*RESOLUTION),
                    reason='original_open' if goal == original else blocked_reason(snapshot, original)))
            state['ring_applied'] = applied
        return joined

    def tick(self, position, sim_time):
        was_finished = self.finished
        command = super().tick(position, sim_time)
        state = self.state
        if command and 'revision' in command and command.get('final_leg'):
            # Require a fresh-map arrival check only for a final substitute.
            leg, goal = state['ring_applied']
            state['ring_wait_for_finish'] = goal != state['tour']['stops'][leg]
            if state['ring_wait_for_finish']:
                command['final_leg'] = False
        if (command is None and not was_finished and self.finished and state is not None
                and state.get('ring_wait_for_finish') and state['leg'] == len(state['tour']['stops'])):
            return dict(state['mission'], endpoint_finished=True, endpoint_outcomes=state['ring_outcomes'])
        return command

    def close(self):
        super().close()
        self.goal_log.close()
