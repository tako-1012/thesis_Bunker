"""Bounded, lossless records of online searches and their accepted handoffs."""

import io
import json
from pathlib import Path
import sys
from threading import Lock

import numpy as np

from tapp.endpoint_policy import load_snapshot

LIMIT_BYTES = 100_000_000
STATUS_RESERVE = 4096


def encode(record):
    fields = {}
    for key, value in record.items():
        array = np.asarray(value)
        if array.dtype == bool and array.ndim > 0:
            fields[key+'_bits'] = np.packbits(array)
            fields[key+'_shape'] = array.shape
        else:
            fields[key] = array
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **fields)
    return buffer.getvalue()


class PlanMapStore:
    """Cost is XOR-delta encoded in byte planes, preserving all float64 bits."""

    def __init__(self, folder, limit=LIMIT_BYTES):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.limit = limit
        self.bytes = 0
        self.count = 0
        self.last_cost = None
        self.incomplete = False
        self.lock = Lock()

    def _write(self, name, data, sim_time):
        if self.incomplete:
            return False
        try:
            if self.bytes+len(data)+STATUS_RESERVE > self.limit:
                self._stop('storage limit', sim_time)
                return False
            target = self.folder/name
            temporary = target.with_suffix('.tmp')
            try:
                with temporary.open('xb') as stream:
                    stream.write(data)
                temporary.replace(target)
            finally:
                temporary.unlink(missing_ok=True)
            self.bytes += len(data)
            return True
        except OSError as error:
            self._stop(f'write failed: {error}', sim_time)
            return False

    def _stop(self, reason, sim_time):
        self.incomplete = True
        print(f'Plan map recording stopped at {sim_time} sim s: {reason}', file=sys.stderr)
        try:
            with (self.folder/'incomplete.json').open('x') as stream:
                json.dump(dict(reason=reason[:240], from_sim_time=float(sim_time)), stream)
        except OSError as error:
            print(f'Could not save plan map status: {error}', file=sys.stderr)

    def search(self, snapshot, result, classification):
        with self.lock:
            if self.incomplete:
                return None
            record = {key: snapshot[key] for key in (
                'lethal', 'known', 'seen', 'detected', 'obstacle_halo', 'prior_raw', 'prior_inflated',
                'steep', 'steep_halo', 'resolution_m', 'start', 'goal', 'pose', 'version', 'sim_time')}
            for key in ('fine_obstacle', 'fine_resolution_m', 'fine_origin_xy', 'veto_supported', 'relaxed',
                        'original_goal', 'retained_lethal', 'obstacle_cost', 'sigma_h', 'uncertain_steep'):
                if key in snapshot:
                    record[key] = snapshot[key]
            cost = np.array(snapshot['cost'], dtype=np.float64, copy=True, order='C')
            previous = self.last_cost
            delta = cost.view(np.uint64) if previous is None else cost.view(np.uint64) ^ previous.view(np.uint64)
            record.update(cost_bytes=delta.view(np.uint8).reshape(-1, 8).T,
                          path_cells=np.asarray(result['path'], float).reshape(-1, 2),
                          success=result['success'], reason=result['reason'], failure_class=classification)
            plan_id = self.count+1
            if self._write(f'plan_{plan_id:06d}.npz', encode(record), snapshot['sim_time']):
                self.count = plan_id
                self.last_cost = cost
                return plan_id
            return None

    def application(self, plan_id, command, sim_time):
        with self.lock:
            failure = bool(command.get('online_error'))
            record = dict(plan_id=plan_id, sim_time=sim_time, failed=failure,
                          revision=command.get('revision', 0) if not failure else 0,
                          path_m=np.asarray([] if failure else command['path'], float).reshape(-1, 2))
            self._write(f'applied_{plan_id:06d}.npz', encode(record), sim_time)


def read_plans(folder):
    previous = None
    for index, path in enumerate(sorted(Path(folder).glob('plan_*.npz')), 1):
        if path.name != f'plan_{index:06d}.npz':
            raise ValueError(f'missing predecessor for {path.name}')
        data = load_snapshot(path)
        shape = data['lethal'].shape
        delta = np.ascontiguousarray(data.pop('cost_bytes').T).view(np.uint64).reshape(shape)
        bits = delta if previous is None else delta ^ previous
        previous = bits
        data['cost'] = bits.view(np.float64).copy()
        data['unknown'] = ~data['known']
        yield index, data
