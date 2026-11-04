"""Task021 fixed LAS scenarios and opt-in task020 masks around task014 runtime."""

import csv
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ros2_jazzy/src/thesis_bunker_mission'))
from tapp.config import RESOLUTION
from tapp.footprint import with_inflated_steep, blocked_endpoints
from tapp.real_beach import list_patches
from tapp.prior import PriorMap
from tapp.online_mission import ordered_tour, run_fixed_mission, OnlinePlanner
from experiments.online_mission import scenarios
from thesis_bunker_mission.online_runtime import AsyncOnlineMission

PLANNERS = ('TA*-S+inflate', 'TA*-S')
MODES = ('fixed', 'online')
MAX_BYTES = 4_800_000


def planning_map(sc, planner):
    if planner not in PLANNERS:
        raise ValueError('unknown planner')
    return with_inflated_steep(sc, .5)['tmap'] if planner == PLANNERS[0] else sc['tmap']


def map_signature(sc):
    tm = sc['tmap']
    return {key: hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()
            for key, value in [('elev', tm.elev), ('lethal', tm.lethal), ('rock', tm.rock)]}


def scenario_case(row, planner=PLANNERS[0]):
    clean, truth, points = scenarios(row)
    # Task014's order is selected on the original prior, then shared unchanged.
    tour = ordered_tour(clean['tmap'], truth['start'], points['stale'])
    prior_tm, truth_tm = planning_map(clean, planner), planning_map(truth, planner)
    blocked_truth = blocked_endpoints(truth_tm, truth['start'], tour['stops'])
    blocked_prior = blocked_endpoints(prior_tm, truth['start'], tour['stops'])
    blocked = bool(blocked_truth or blocked_prior)
    fixed = None if blocked else run_fixed_mission(prior_tm, truth['start'], tour['stops'])
    status = 'blocked_endpoint' if blocked else ('planned' if fixed['success'] else 'no_path')
    return dict(patch=row['name'], patch_index=truth['patch_index'], planner=planner,
                truth=truth, clean=clean, truth_tm=truth_tm, prior_tm=prior_tm,
                start=list(truth['start']), points=[list(p) for p in points['stale']],
                tour=tour, fixed=fixed, planning_status=status,
                blocked_truth=blocked_truth, blocked_prior=blocked_prior)


def scenario_cases(planner=PLANNERS[0]):
    return [scenario_case(row, planner) for row in list_patches('test', dataset='shizuoka_beach_las')[:10]]


def case_metadata(sc):
    fixed = sc['fixed']
    return dict(patch=sc['patch'], patch_index=sc['patch_index'], planner=sc['planner'],
                start=sc['start'], points=sc['points'], order=list(sc['tour']['order']),
                stops=[list(p) for p in sc['tour']['stops']], planning_status=sc['planning_status'],
                blocked_truth=sc['blocked_truth'], blocked_prior=sc['blocked_prior'],
                truth_signature=map_signature(sc['truth']), prior_signature=map_signature(sc['clean']),
                initial_path=[] if fixed is None else (np.asarray(fixed['traj']) * RESOLUTION).tolist(),
                fixed_plan_times=[] if fixed is None else fixed['plan_times'])


class BatchOnlineMission(AsyncOnlineMission):
    """Use task014's worker/handoff unchanged, with a preselected shared tour."""
    def __init__(self, *args, plan_log=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.plan_log = CsvChunks(plan_log, ['n_plans', 'reason', 'success', 'plan_time_s']) if plan_log else None

    def _work(self, state, position):
        try:
            return self._plan_work(state, position)
        finally:
            # Log every completed search, including failed/rejected handoffs.
            planner = state.get('planner')
            if self.plan_log is not None and planner is not None:
                for event in planner.events[state.get('_logged_plan_calls', 0):]:
                    self.plan_log.write(event)
                state['_logged_plan_calls'] = len(planner.events)

    def _plan_work(self, state, position):
        if state['planner'] is None:
            mission = state['mission']
            stops = [tuple(p) for p in mission['stops_cells']]
            if blocked_endpoints(self.truth, mission['start_cells'], stops):
                return dict(success=False, replanned=True, reason='blocked_endpoint')
            state['tour'] = dict(order=mission['order'], stops=stops)
            state['planner'] = OnlinePlanner(self.prior.cost, self.prior.lethal,
                                             self.truth.weights, prior_lethal_mode=self.mode)
        return super()._work(state, position)

    def close(self):
        super().close()
        if self.plan_log is not None:
            self.plan_log.close()


def make_runtime(truth, prior, planner=PLANNERS[0], *, executor=None, plan_log=None):
    truth_tm, prior_tm = planning_map(truth, planner), planning_map(prior, planner)
    return BatchOnlineMission(truth_tm, prior['tmap'],
                              PriorMap(prior_tm.cost, prior_tm.lethal, RESOLUTION),
                              radius_m=10, prior_lethal_mode='soft', executor=executor, plan_log=plan_log)


class CsvChunks:
    """Streaming CSV parts, repeated headers, strictly less than the 5MB limit."""
    def __init__(self, path, fields, limit=MAX_BYTES):
        self.path, self.fields, self.limit = Path(path), list(fields), limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.part = -1
        self.stream = None
        self._next()

    def _next(self):
        if self.stream is not None:
            self.stream.close()
        self.part += 1
        path = self.path if self.part == 0 else self.path.with_name(self.path.stem + f'_part{self.part:03d}.csv')
        self.stream = path.open('w', newline='')
        self.writer = csv.DictWriter(self.stream, fieldnames=self.fields, lineterminator='\n')
        self.writer.writeheader()
        self.stream.flush()

    def write(self, row):
        import io
        buf = io.StringIO(newline='')
        writer = csv.DictWriter(buf, fieldnames=self.fields, lineterminator='\n')
        writer.writerow(row)
        line = buf.getvalue()
        if len(line.encode()) + len(','.join(self.fields).encode()) + 1 >= self.limit:
            raise ValueError('a single CSV record exceeds the storage limit')
        if self.stream.tell() + len(line.encode()) >= self.limit:
            self._next()
        self.stream.write(line)
        self.stream.flush()

    def close(self):
        self.stream.close()


def csv_parts(path):
    path = Path(path)
    return ([path] if path.exists() else []) + sorted(path.parent.glob(path.stem + '_part[0-9][0-9][0-9].csv'))


def read_csv_parts(path):
    path = Path(path)
    rows, header = [], None
    for i, part in enumerate(csv_parts(path)):
        expected = path if i == 0 else path.with_name(path.stem + f'_part{i:03d}.csv')
        if part != expected:
            raise ValueError('missing CSV part: ' + str(expected))
        with part.open() as stream:
            reader = csv.DictReader(stream)
            if header is not None and header != reader.fieldnames:
                raise ValueError('CSV part headers differ')
            header = reader.fieldnames
            rows.extend(reader)
    return rows


def split_follower_logs(folder, limit=MAX_BYTES):
    """Split new task021 follower CSV and process logs after its processes stop."""
    for path in Path(folder).rglob('*.csv'):
        if path.stat().st_size < limit:
            continue
        with path.open() as stream:
            reader = csv.DictReader(stream)
            fields, rows = reader.fieldnames, list(reader)
        writer = CsvChunks(path, fields, limit=limit)
        try:
            for row in rows:
                writer.write(row)
        finally:
            writer.close()
    for path in Path(folder).rglob('process_*.txt'):
        if path.stat().st_size < limit:
            continue
        content = path.read_bytes()
        for i, start in enumerate(range(0, len(content), limit-1)):
            target = path if i == 0 else path.with_name(path.stem + f'_part{i:03d}.txt')
            target.write_bytes(content[start:start+limit-1])
