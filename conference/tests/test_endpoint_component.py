"""Task028b topology, immutable raw masks, live handoff and saved-case contract."""

from collections import deque
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
import numpy as np

from tapp.config import RESOLUTION
from tapp.collision import path_lethal_cells
from tapp.endpoint_policy import escape_maps, plan_endpoint, raw_mask
from ros2_jazzy.gz_checks.endpoint_runtime import make_lidar_runtime
from tests import test_endpoint_policy as legacy

ROOT = Path(__file__).resolve().parents[1]


def component_oracle(snapshot):
    """Independent graph traversal using only four adjacent inflated-only cells."""
    mask = snapshot['lethal'] & ~raw_mask(snapshot)
    start = tuple(snapshot['start'])
    reached = set()
    queue = deque([start] if mask[start] else [])
    while queue:
        point = queue.popleft()
        if point in reached:
            continue
        reached.add(point)
        x, y = point
        for neighbour in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if all(0 <= v < n for v, n in zip(neighbour, mask.shape)) and mask[neighbour]:
                queue.append(neighbour)
    expected = np.zeros(mask.shape, bool)
    for point in reached:
        expected[point] = True
    return expected


def test_topology_and_raw_protection():
    s = legacy.snapshot()
    s['lethal'][4:10, 4] = True
    s['lethal'][10, 5] = True  # Diagonal-only contact must not extend the component.
    s['cost'] = np.arange(s['cost'].size).reshape(s['cost'].shape).astype(float)+1
    before = {k: v.copy() for k, v in s.items() if isinstance(v, np.ndarray)}
    blocked, cost, relaxed = escape_maps(s, 'escape_component')
    assert np.array_equal(relaxed, component_oracle(s))
    assert relaxed[9, 4] and not relaxed[10, 5]
    assert np.linalg.norm((np.array([9, 4])-s['start'])*RESOLUTION) > .5
    assert not (relaxed & raw_mask(s)).any()
    assert np.all(cost[relaxed] == s['cost'][~s['lethal']].max())
    assert not blocked[relaxed].any()
    assert all(np.array_equal(s[k], v) for k, v in before.items())
    for name in ('detected', 'prior_raw', 'steep'):
        s = legacy.snapshot()
        s['lethal'][4:10, 4] = True
        s[name][6, 4] = True
        blocked, _, relaxed = escape_maps(s, 'escape_component')
        assert np.array_equal(relaxed, component_oracle(s))
        assert blocked[6, 4] and not relaxed[6:, 4].any()
        s[name][4, 4] = True
        result = plan_endpoint(s, 'escape_component')
        assert not result['success'] and not result['relaxed'].any()
    s = legacy.snapshot()
    s['lethal'][5:10, 4] = True
    assert not escape_maps(s, 'escape_component')[2].any()  # A free start is not an inflated-only cell.
    print('component topology: exact four-neighbour BFS, no free/diagonal bridges or distance cap; raw masks, costs and input arrays protected')


def test_component_search_and_handoff():
    s = legacy.snapshot()
    s['pose'][:2] = [2.24, 2.24]  # Same continuous-position fixture as the legacy tests.
    s['lethal'][3:6, 3:6] = True
    s['detected'][5, 4] = s['detected'][4, 5] = True
    assert not plan_endpoint(s, 'escape')['success']
    result = plan_endpoint(s, 'escape_component')
    assert result['success']
    assert np.array_equal(result['relaxed'], component_oracle(s))
    assert not len(path_lethal_cells(result['path'], raw_mask(s)))
    with tempfile.TemporaryDirectory() as temporary:
        prior, mapper = legacy.environment()
        mapper.lethal[:] = s['lethal']
        mapper.detected_obstacle[:] = s['detected']
        before = mapper.lethal.copy()
        folder = Path(temporary)
        runtime = make_lidar_runtime(prior, mapper, plan_log=folder/'plans.csv',
                                     endpoint_policy='escape_component', diagnostics=True, executor=legacy.Immediate())
        try:
            runtime.start(dict(id=1, order=[0], stops_cells=[[10, 4]]))
            runtime.tick(s['pose'][:2], 0.)
            command = runtime.tick(s['pose'][:2], .1)
            assert command.get('path') and runtime.sent == 1 and not runtime.hold
            assert not len(path_lethal_cells(np.asarray(command['path'])/RESOLUTION, s['detected']))
            assert np.array_equal(mapper.lethal, before)
            records = list((folder/'endpoint_masks').glob('*.npz'))
            applied = []
            for path in records:
                with np.load(path, allow_pickle=False) as arrays:
                    if arrays['applied']:
                        applied.append(np.unpackbits(arrays['relaxed_bits'], count=before.size).reshape(before.shape).astype(bool))
            assert len(applied) == 1 and np.array_equal(applied[0], component_oracle(s))
        finally:
            runtime.close()
    print('component runtime: enclosed synthetic start escapes through search AND latest-map handoff; mapper remains immutable')


def test_component_lifecycle():
    def component_factory(*args, **kwargs):
        assert kwargs['endpoint_policy'] == 'escape'
        kwargs['endpoint_policy'] = 'escape_component'
        return make_lidar_runtime(*args, **kwargs)
    with patch.object(legacy, 'make_lidar_runtime', side_effect=component_factory):
        legacy.test_substitute_replan()
        legacy.test_retry_runtime()
        legacy.test_delayed_handoff()
    print('component lifecycle: unchanged nearby-target tracking, one timed retry, skip and stale-handoff stop contracts passed')


def test_legacy_bytes_and_selection():
    from experiments.endpoint_replay import replay
    from ros2_jazzy.gz_checks import lidar_checks
    reference = ROOT/'results/endpoint_policy/b/verification/legacy'
    assert json.dumps(replay(), ensure_ascii=False, indent=2)+'\n' == (reference/'replay.json').read_text()
    with tempfile.TemporaryDirectory() as temporary, patch.dict(os.environ):
        for key in ('THESIS_FINE_PROTOCOL', 'THESIS_ONLY_PATCH', 'THESIS_REAL_TIME_FACTOR', 'THESIS_STALE_TIMEOUT_S'):
            os.environ.pop(key, None)
        root = Path(temporary)
        for name, kwargs in [('coarse', {}), ('fine', dict(map_method='fine')),
                             ('escape', dict(map_method='fine', endpoint_policy='escape')),
                             ('escape_diag', dict(map_method='fine', endpoint_policy='escape', diagnostics=True))]:
            expected = json.loads((reference/(name+'_manifest.json')).read_text())
            expected['input_environment'] = dict(python=sys.version, numpy=np.__version__)
            lidar_checks.prepare_cases(root/name, **kwargs)
            assert (root/name/'manifest.json').read_bytes() == (json.dumps(expected, ensure_ascii=False, indent=2)+'\n').encode()
        expected = json.loads((root/'escape/manifest.json').read_text())
        expected['endpoint_policy'] = 'escape_component'
        lidar_checks.prepare_cases(root/'component', map_method='fine', endpoint_policy='escape_component')
        assert json.loads((root/'component/manifest.json').read_text()) == expected
    with patch.object(sys, 'argv', ['lidar_checks.py', '--map', 'fine', '--endpoint-policy', 'escape_component']), \
         patch.object(lidar_checks, 'run_checks') as execute:
        lidar_checks.main()
        assert execute.call_args.kwargs['endpoint_policy'] == 'escape_component'
    print('legacy bytes: original three-case escape replay and four preparation variants unchanged; new CLI choice/manifest accepted')


def test_saved_component_contract():
    from experiments.endpoint_replay import compare_replay, saved_snapshot, ROOT as replay_root
    rows = compare_replay()
    assert len(rows) == 6
    assert all(row['raw_cells_cleared'] == row['raw_path_cells'] == 0 for row in rows)
    failed = []
    for row in rows:
        print('028b saved replay:', row)
        if row['failure_class'] == 'start_cell' and row['policy'] == 'escape_component' and row['result'] != 'path':
            snapshot = saved_snapshot(replay_root/row['case'])
            start = tuple(snapshot['start'])
            failed.append(dict(case=row['case'], start=list(map(int, start)),
                               raw_start={name: bool(snapshot[name][start]) for name in ('detected', 'prior_raw', 'steep')}))
    assert not failed, ('Required saved-start paths conflict with immutable raw-start protection', failed)
    print('saved component contract: both start failures have paths; all raw obstacle cells remain protected')


if __name__ == '__main__':
    test_topology_and_raw_protection()
    test_component_search_and_handoff()
    test_component_lifecycle()
    test_legacy_bytes_and_selection()
    test_saved_component_contract()
    print('all task028b component tests passed (Python only; Gazebo not run)')
