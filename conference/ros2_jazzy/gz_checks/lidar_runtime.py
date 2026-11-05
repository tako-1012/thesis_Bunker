"""Task021 async planning on point-cloud observations; no truth or radius sensor."""

from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tapp.config import RESOLUTION
from tapp.prior import PriorMap
from tapp.online_mission import OnlinePlanner
from tapp.collision import line_of_sight_exact, path_lethal_cells
from ros2_jazzy.gz_checks.online_batch_runtime import BatchOnlineMission, planning_map


class LidarOnlineMission(BatchOnlineMission):
    """Keep the original worker mailbox and handoff protocol, replacing both senses."""
    def __init__(self, prior, mapper, *, plan_log=None, executor=None):
        tm = planning_map(prior, 'TA*-S+inflate')
        super().__init__(None, prior['tmap'], PriorMap(tm.cost, tm.lethal, RESOLUTION),
                         prior_lethal_mode='soft', plan_log=plan_log, executor=executor)
        self.mapper = mapper

    def _observe(self, planner):
        planner.observe(*self.mapper.snapshot())

    def _plan_work(self, state, position):
        state.pop('observations', None)  # Poses cannot reveal terrain labels.
        cell = tuple(int(round(v/RESOLUTION)) for v in position)
        if state['planner'] is None:
            mission = state['mission']
            state['tour'] = dict(order=mission['order'], stops=[tuple(p) for p in mission['stops_cells']])
            state['planner'] = OnlinePlanner(self.prior.cost, self.prior.lethal,
                                             self.prior_tm.weights, prior_lethal_mode=self.mode)
        planner = state['planner']
        self._observe(planner)
        if planner.goal is not None and np.linalg.norm(np.asarray(position)-np.asarray(planner.goal)*RESOLUTION) <= .3:
            state['leg'] += 1
            if state['leg'] >= len(state['tour']['stops']):
                return dict(finished=True)
            planner.goal = None
        if planner.goal is None:
            return planner.start_leg(cell, state['tour']['stops'][state['leg']])
        return planner.update(position)

    def _join(self, state, result, position):
        planner = state['planner']
        pos = np.asarray(position, float)/RESOLUTION
        cell = tuple(int(round(v)) for v in pos)
        self.observations = []
        self._observe(planner)
        path = [np.asarray(p, float) for p in result['path']]
        if not path:
            return None
        best = None
        for i, (a, b) in enumerate(zip(path[:-1], path[1:])):
            delta = b-a
            t = float(np.clip(np.dot(pos-a, delta)/np.dot(delta, delta), 0, 1)) if np.any(delta) else 0.
            distance = float(np.linalg.norm(pos-(a+t*delta)))
            if best is None or distance < best[0]:
                best = distance, i
        rest = path[best[1]+1:] if best is not None else [path[-1]]
        known_lethal = planner.known & planner.lethal
        if rest and line_of_sight_exact(known_lethal, tuple(pos), tuple(rest[0])):
            joined = [pos]+rest
        else:
            joined = [pos, np.asarray(cell, float)]+rest
        if len(path_lethal_cells(joined, known_lethal)):
            planner.pos = pos.copy()
            return None
        planner.path, planner.pos = joined, pos.copy()
        planner.seg, planner.since_replan = 0, 0.
        return (np.asarray(joined)*RESOLUTION).tolist()
