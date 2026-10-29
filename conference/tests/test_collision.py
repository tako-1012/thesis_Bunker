"""Exact closed-cell intersections against an independent SAT reference."""
import numpy as np
from tapp.collision import segment_cells, line_of_sight_exact, path_lethal_cells
from tapp.planners import line_of_sight, smooth_cost_aware
from tapp.scenario import build, run_planner
from tapp.prior import coarse_prior
from tapp.online import run_online
from tapp.metrics import evaluate
from tapp.config import DEFAULT_W


def sat(a, b, shape):
    cells = np.indices(shape).reshape(2, -1).T
    mid, half = (a + b) / 2, (b - a) / 2
    offset = cells - mid
    h = 0.5 + 1e-9
    hit = (np.abs(offset) <= np.abs(half) + h).all(axis=1)
    normal = np.array([-half[1], half[0]])
    hit &= np.abs(offset @ normal) <= h * np.abs(normal).sum()
    return cells[hit]


def test_segments():
    rng = np.random.default_rng(100)
    for i in range(2000):
        a, b = rng.uniform(0, 19, (2, 2))
        if i % 3 == 0:
            a = np.round(a * 2) / 2
        if i % 5 == 0:
            b = np.round(b * 2) / 2
        if i % 11 == 0:
            b = a.copy()
        actual = segment_cells(a, b, (20, 20))
        expected = sat(a, b, (20, 20))
        assert np.array_equal(actual, expected), (i, a, b, actual, expected)
        assert np.array_equal(actual, segment_cells(b, a, (20, 20)))
    for a, b in (([-2, -2], [21, 21]), ([0.5, -3], [0.5, 23]),
                 ([-2, -2], [-1, -1]), ([0.5, 0.5], [0.5, 0.5])):
        assert np.array_equal(segment_cells(a, b, (20, 20)), sat(np.array(a), np.array(b), (20, 20)))
    blocked = np.ones((3, 3), dtype=bool)
    assert path_lethal_cells([], blocked).shape == (0, 2)
    assert len(path_lethal_cells([(0.5, 0.5)], blocked)) == 4
    hits = path_lethal_cells([(0, 0), (2, 2), (0, 0)], blocked)
    assert len(hits) == len(np.unique(hits, axis=0))
    print('segment_cells passed (2000 seeded segments vs exhaustive SAT, reversal and boundary cases)', flush=True)


def test_grazing():
    blocked = np.zeros((6, 6), dtype=bool)
    blocked[3, 2] = True
    a, b = (1.19286796, 1.77048902), (3.15312682, 1.37377099)
    assert line_of_sight(blocked, a, b)
    assert not line_of_sight(blocked, a, b, step=0.001)
    assert not line_of_sight_exact(blocked, a, b)
    assert np.array_equal(path_lethal_cells([a, b], blocked), [[3, 2]])
    print('corner-grazing reproduction and exact rejection passed', flush=True)


def test_regression():
    for kind, seed, radius, cell in (('ridge', 7, 15, 5), ('craters', 0, 10, 10)):
        sc = build(kind, 100, seed)
        tm = sc['tmap']
        r = run_online(tm, sc['start'], sc['goal'], prior_map=coarse_prior(tm, cell), sense_radius_m=radius)
        assert r['success']
        m = evaluate(r['traj'], tm)
        if kind == 'ridge':
            assert abs(m['length_xy'] - 95.218208) <= 1e-6
            assert r['n_plans'] == 67
        else:
            assert abs(m['steep_len'] - 0.0997987) <= 1e-6
    sc = build('hills', 100, 0)
    tm = sc['tmap']
    raw = run_planner('TA*', sc, w=DEFAULT_W)
    mult = 1 + DEFAULT_W * tm.cost
    p0, _ = smooth_cost_aware(raw['path'], tm.lethal, mult)
    p1, _ = smooth_cost_aware(raw['path'], tm.lethal, mult, los=line_of_sight)
    assert p0 == p1 == run_planner('TA*-S', sc, w=DEFAULT_W)['path']
    print('legacy online and smoothing regressions passed', flush=True)


def test_safety():
    cases = [('craters', 100, 0, 10, 10, 'astar')]
    cases += [(kind, 50, seed, radius, 5, search) for kind in ('ridge', 'craters')
              for seed in range(5) for radius in (5, 15) for search in ('astar', 'dstar_lite')]
    for kind, size, seed, radius, cell, search in cases:
        sc = build(kind, size, seed)
        tm = sc['tmap']
        r = run_online(tm, sc['start'], sc['goal'], prior_map=coarse_prior(tm, cell),
                       sense_radius_m=radius, search=search, exact_los=True)
        assert r['success'], (kind, size, seed, radius, search, r['reason'])
        hits = path_lethal_cells(r['traj'], tm.lethal)
        assert len(hits) == 0, (kind, size, seed, radius, search, hits)
    print(f'exact online safety passed ({len(cases)} trajectories, A* and D* Lite)', flush=True)


if __name__ == '__main__':
    test_segments()
    test_grazing()
    test_regression()
    test_safety()
    print('all collision tests passed')
