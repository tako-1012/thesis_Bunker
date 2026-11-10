"""Task028 opt-in adapter; the legacy runtime is returned verbatim by default."""
import json
import time
import numpy as np
from tapp.config import RESOLUTION
from tapp.online_mission import OnlinePlanner
from tapp.endpoint_policy import (plan_endpoint, classify_failure, SnapshotStore,
                                  RetryState, escape_maps, ENDPOINT_POLICIES)
from tapp.collision import path_lethal_cells, line_of_sight_exact
from .lidar_runtime import LidarOnlineMission
from .online_batch_runtime import CsvChunks


def capture(mapper, planner, position, pose, sim_time, goal):
    # PointCloudMapFine publishes masks under these locks in this same order.
    with mapper._update_lock, mapper._lock:
        seen, cost, lethal = mapper.seen.copy(), mapper.tm.cost.copy(), mapper.lethal.copy()
        planner.observe(seen, cost, lethal)
        planning_lethal, planning_cost = planner.planning_maps()
        return dict(lethal=planning_lethal.copy(), cost=planning_cost.copy(), seen=seen, known=planner.known.copy(),
                    detected=mapper.detected_obstacle.copy(), prior_raw=mapper.raw_obstacle.copy(),
                    steep=mapper.tm.steep.copy(), elev=mapper.elev.copy(),
                    fine_obstacle=mapper.fine_obstacle.copy(), fine_resolution_m=.1,
                    fine_origin_xy=np.array([-.25, -.25]), resolution_m=RESOLUTION, version=int(mapper.version),
                    pose=np.asarray(pose, float), start=np.rint(np.asarray(position)/RESOLUTION).astype(int),
                    goal=np.asarray(goal, int), sim_time=float(sim_time))


class EndpointPlanner(OnlinePlanner):
    def _plan(self, reason, initial=False):
        snapshot = self.snapshot
        snapshot['start'] = np.rint(self.pos).astype(int)
        snapshot['goal'] = np.asarray(self.target if self.policy != 'none' else self.goal, int)
        if self.policy == 'none':
            result = super()._plan(reason, initial=initial)
        else:
            began = time.perf_counter()
            outcome = plan_endpoint(snapshot, self.policy)
            self.endpoint_result = outcome
            self.goal = tuple(outcome['goal'])
            self.path = [np.asarray(p, float) for p in outcome['path']]
            self.seg, self.since_replan = 0, 0.
            self.pending_new.fill(False)
            self.plan_times.append(time.perf_counter()-began)
            event = dict(n_plans=len(self.plan_times), reason=reason,
                         success=bool(outcome['success']), plan_time_s=self.plan_times[-1])
            self.events.append(event)
            result = dict(event, path=[p.tolist() for p in self.path], replanned=True)
            self.owner.record_relaxation(outcome, snapshot, 'search')
        if self.owner.diagnostics:
            actual = dict(snapshot)
            if self.policy != 'none':
                actual.update(pre_policy_lethal=snapshot['lethal'], lethal=outcome['lethal'],
                              cost=outcome['cost'], original_goal=snapshot['goal'], goal=outcome['goal'])
            self.events[-1]['failure_class'] = '' if result['success'] else classify_failure(actual)
            if not result['success']:
                self.owner.diagnostics.save(actual, failure=True)
        return result


class EndpointRuntime(LidarOnlineMission):
    def __init__(self, prior, mapper, *, plan_log, endpoint_policy, diagnostics, executor=None):
        if not hasattr(mapper, 'fine_obstacle'):
            raise ValueError('task028 requires --map fine')
        super().__init__(prior, mapper, plan_log=plan_log, executor=executor)
        self.policy = endpoint_policy
        self.folder = plan_log.parent
        self.diagnostics = SnapshotStore(self.folder/'diag') if diagnostics else None
        if diagnostics:
            self.plan_log.close()
            self.plan_log = CsvChunks(plan_log, ['n_plans', 'reason', 'success', 'plan_time_s', 'failure_class'])
        self.pose = None
        self.relax_index = 0
        self.hold = False
        self.finished_sent = False
        self.outcomes = []
        self.stats = dict(start_applications=0, goal_applications=0, relaxed_cells=0, retries=0)
        self.audit_log = CsvChunks(self.folder/'endpoint_trajectory.csv',
            ['sim_time', 'x', 'y', 'z', 'roll', 'pitch', 'yaw']) if self.policy != 'none' else None

    def _observe(self, planner):
        # Worker and join both get an immutable map, independent of later updates.
        state = self.state
        context = state.get('_context', (0., self.pose))
        position = state.get('_position', self.pose[:2])
        goal = planner.goal or state['mission']['stops_cells'][state['leg']]
        planner.snapshot = capture(self.mapper, planner, position, context[1], context[0], goal)
        if self.diagnostics:
            self.diagnostics.tick(planner.snapshot)

    def record_relaxation(self, result, snapshot, phase):
        if self.policy == 'none':
            return
        mask = result['relaxed']
        self.relax_index += 1
        folder = self.folder/'endpoint_masks'
        folder.mkdir(exist_ok=True)
        np.savez_compressed(folder/f'{self.relax_index:06d}.npz', relaxed_bits=np.packbits(mask),
                            relaxed_shape=mask.shape, sim_time=snapshot['sim_time'], phase=phase,
                            version=snapshot['version'], original_goal=snapshot['goal'], goal=result['goal'],
                            applied=(phase == 'handoff' and result['success']))
        if phase == 'search':
            self.stats['start_applications'] += int(mask.any())
            self.stats['relaxed_cells'] += int(mask.sum())
            self.stats['goal_applications'] += int(tuple(snapshot['goal']) != tuple(result['goal']))

    def _plan_work(self, state, position):
        if state['planner'] is None:
            state['tour'] = dict(order=state['mission']['order'], stops=[tuple(p) for p in state['mission']['stops_cells']])
            planner = EndpointPlanner(self.prior.cost, self.prior.lethal, self.prior_tm.weights, prior_lethal_mode=self.mode)
            planner.owner, planner.policy = self, self.policy
            state['planner'] = planner
            state['retry'] = RetryState()
        if self.policy == 'none':
            return super()._plan_work(state, position)
        planner = state['planner']
        now = state['_context'][0]
        if planner.goal is not None and not self.hold and np.linalg.norm(np.asarray(position)-np.asarray(planner.goal)*RESOLUTION) <= .3:
            self._advance(state, planner.endpoint_result['outcome'])
        if state['leg'] >= len(state['tour']['stops']):
            return dict(finished=True)
        if self.hold and not state['retry'].ready(now):
            return dict(success=True, replanned=False)
        retry = self.hold
        planner.target = state['tour']['stops'][state['leg']]
        self._observe(planner)
        if planner.goal is None or retry:
            # Use measured continuous position, not the rounded cell, for the halo.
            planner.pos = np.asarray(position)/RESOLUTION
            planner.goal = state['tour']['stops'][state['leg']]
            result = planner._plan('endpoint_retry' if retry and state['retry'].retried else 'start_leg', initial=True)
        else:
            result = planner.update(position)
        if not result['success']:
            if state['retry'].failed(now) == 'unreachable':
                self._advance(state, 'unreachable')
            else:
                self.stats['retries'] += 1
            self.hold = True
            return dict(success=True, replanned=False)
        if result.get('replanned'):
            self.hold = False
        return result

    def _advance(self, state, outcome):
        self.outcomes.append(dict(index=state['leg'], target=list(state['tour']['stops'][state['leg']]),
                                  outcome=outcome, retries=state['retry'].retries))
        state['leg'] += 1
        state['planner'].goal = None
        state['retry'] = RetryState()
        self._save_status()

    def _save_status(self):
        (self.folder/'endpoint_status.json').write_text(json.dumps(dict(stops=self.outcomes, **self.stats), indent=2)+'\n')

    def _join(self, state, result, position):
        if self.policy == 'none':
            return super()._join(state, result, position)
        planner = state['planner']
        self._observe(planner)
        snapshot = planner.snapshot
        snapshot['pose'] = np.asarray(self.pose)
        snapshot['start'] = np.rint(np.asarray(position)/RESOLUTION).astype(int)
        # Revalidate at the latest map/pose, never blindly apply an old clearance.
        lethal, cost, relaxed = escape_maps(snapshot, self.policy)
        clearance = dict(lethal=lethal, cost=cost, relaxed=relaxed, goal=snapshot['goal'], success=True)
        pos = np.asarray(position, float)/RESOLUTION
        cell = np.rint(pos)
        path = [np.asarray(p, float) for p in result['path']]
        best = None
        for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
            delta = b-a
            fraction = float(np.clip(np.dot(pos-a, delta)/np.dot(delta, delta), 0, 1)) if np.any(delta) else 0.
            distance = float(np.linalg.norm(pos-(a+fraction*delta)))
            if best is None or distance < best[0]:
                best = distance, i
        rest = path[best[1]+1:] if best is not None else path[-1:]
        if not rest:
            joined = None
        else:
            joined = ([pos]+rest if line_of_sight_exact(lethal, pos, rest[0]) else [pos, cell]+rest)
            if len(path_lethal_cells(joined, lethal)):
                joined = None
        if joined is not None:
            planner.path, planner.pos = joined, pos.copy()
            planner.seg, planner.since_replan = 0, 0.
            joined = (np.asarray(joined)*RESOLUTION).tolist()
        if joined is not None:
            self.record_relaxation(clearance, snapshot, 'handoff')
        else:
            self._reject_join(state)
        return joined

    def _reject_join(self, state):
        self.hold = True
        if state['retry'].failed(state['_context'][0]) == 'unreachable':
            self._advance(state, 'unreachable')
        else:
            self.stats['retries'] += 1

    def tick(self, position, sim_time):
        if self.pose is None:
            self.pose = np.r_[position, 0., 0., 0., 0.]
        else:
            self.pose = np.asarray(self.pose, float).copy()
            self.pose[:2] = position
        if self.audit_log and not self.finished:
            self.audit_log.write(dict(zip(self.audit_log.fields, [sim_time, *self.pose])))
        if self.state is not None and (self.pending is None or self.pending.done()):
            self.state['_context'] = (float(sim_time), np.array(self.pose, copy=True))
            self.state['_position'] = tuple(position)
        command = super().tick(position, sim_time)
        if self.policy != 'none' and self.state is not None:
            if self.finished:
                if self.finished_sent:
                    return None
                self.finished_sent = True
                self._save_status()
                return dict(self.state['mission'], endpoint_finished=True, endpoint_outcomes=self.outcomes)
            if self.hold:
                return dict(self.state['mission'], endpoint_hold=True)
            if command:
                command['final_leg'] = False  # Runtime records the final outcome before completion.
        if command and 'plan_history' in command:
            command['plan_history'] = [{k: v for k, v in e.items() if k != 'failure_class'} for e in command['plan_history']]
        return command

    def close(self):
        super().close()
        if self.audit_log:
            self.audit_log.close()
            self._save_status()


def make_lidar_runtime(prior, mapper, *, plan_log, endpoint_policy='none', diagnostics=False, executor=None):
    if endpoint_policy not in ENDPOINT_POLICIES:
        raise ValueError('unknown endpoint policy')
    if endpoint_policy == 'none' and not diagnostics:
        return LidarOnlineMission(prior, mapper, plan_log=plan_log, executor=executor)
    return EndpointRuntime(prior, mapper, plan_log=plan_log, endpoint_policy=endpoint_policy,
                           diagnostics=diagnostics, executor=executor)
