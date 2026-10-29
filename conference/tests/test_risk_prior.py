"""Coarse-map regression, validation calibration, risk costs and online safety.

Run: python3 -m tests.test_risk_prior (from conference/).
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from tapp.config import DEFAULT_W
from tapp.metrics import evaluate
from tapp.online import run_online
from tapp.prior import coarse_elevation, coarse_prior
from tapp.risk_prior import calibrate, load_calibration, risk_prior, save_calibration
from tapp.scenario import build
from tapp.terrain import TERRAIN_TYPES
from tapp.traversability import TraversabilityMap, slope_deg


def test_coarse_refactor():
    count = 0
    for kind in TERRAIN_TYPES:
        tm = build(kind, 50, 0)["tmap"]
        for cell in (5.0, 10.0):
            for noise in (0.0, 0.5):
                elev = coarse_elevation(tm, cell, noise, seed=0)
                expected = TraversabilityMap(elev, np.zeros(tm.shape, dtype=bool), tm.robot, tm.weights)
                pm = coarse_prior(tm, cell, noise, seed=0)
                assert np.array_equal(pm.cost, expected.cost)
                assert np.array_equal(pm.lethal, expected.lethal)
                assert pm.cell_m == cell
                count += 1
    for cell, noise in ((0.0, 0.0), (0.1, 0.0), (np.nan, 0.0), (5.0, -0.5)):
        for func in (coarse_elevation, coarse_prior):
            try:
                func(tm, cell, noise)
            except ValueError:
                pass
            else:
                raise AssertionError((func.__name__, cell, noise))
    print(f"coarse elevation/refactor passed ({count} terrain/cell/noise combinations)", flush=True)


def test_calibration():
    args = dict(seeds=(100,), sizes=(50,), kinds=("hills", "rocky"))
    calib = calibrate(10.0, **args)
    assert calib == calibrate(10.0, **args)
    assert calib.edges_deg == [0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 90.0]
    assert np.all((np.asarray(calib.p_lethal) >= 0) & (np.asarray(calib.p_lethal) <= 1))
    counts = np.zeros(len(calib.counts), dtype=int)
    cost_sums, lethal_sums = np.zeros(len(counts)), np.zeros(len(counts))
    total = 0
    for kind in args["kinds"]:
        tm = build(kind, 50, 100)["tmap"]
        bins = np.digitize(slope_deg(coarse_elevation(tm, 10.0)), calib.edges_deg[1:-1])
        total += tm.elev.size
        for b in range(len(counts)):
            mask = bins == b
            counts[b] += int(mask.sum())
            cost_sums[b] += tm.cost[mask].sum()
            lethal_sums[b] += int(tm.lethal[mask].sum())
    assert sum(calib.counts) == total
    np.testing.assert_array_equal(calib.counts, counts)
    occupied = counts > 0
    np.testing.assert_allclose(np.asarray(calib.mean_cost)[occupied], cost_sums[occupied] / counts[occupied],
                               rtol=0, atol=1e-12)
    np.testing.assert_allclose(np.asarray(calib.p_lethal)[occupied], lethal_sums[occupied] / counts[occupied],
                               rtol=0, atol=1e-12)
    with tempfile.TemporaryDirectory(prefix="risk-calibration-test-") as directory:
        path = Path(directory) / "calibration_10.json"
        save_calibration(calib, path)
        assert load_calibration(path) == calib
    for seed in range(10):
        with patch("tapp.risk_prior.build") as builder:
            try:
                calibrate(10.0, seeds=(100, seed), sizes=(50,))
            except ValueError:
                pass
            else:
                raise AssertionError(seed)
            builder.assert_not_called()
    print("calibration passed (all-cell counts/means, deterministic pooling, JSON, test-seed rejection)", flush=True)


def test_empty_bins():
    # Synthetic cells exercise leading/interior empty bins and exact boundaries.
    slopes = np.array([[5.0, 6.0, 20.0], [25.0, 89.0, 90.0]])
    tm = SimpleNamespace(cost=np.array([[0.1, 0.3, 0.6], [0.7, 0.8, 0.9]]),
                         lethal=np.array([[False, True, False], [True, True, False]]))
    with patch("tapp.risk_prior.build", return_value={"tmap": tm}), \
            patch("tapp.risk_prior.coarse_elevation", return_value=slopes), \
            patch("tapp.risk_prior.slope_deg", return_value=slopes):
        calib = calibrate(5.0, seeds=(100,), sizes=(50,), kinds=("hills",))
    assert calib.counts == [0, 0, 2, 0, 0, 0, 0, 0, 1, 0, 3]
    np.testing.assert_allclose(calib.mean_cost, [0.2] * 8 + [0.6, 0.6, 0.8], rtol=0, atol=1e-15)
    np.testing.assert_allclose(calib.p_lethal, [0.5] * 8 + [0.0, 0.0, 2 / 3], rtol=0, atol=1e-15)
    print("empty-bin fallback and boundary assignment passed", flush=True)


def test_cost():
    tm = build("rocky", 50, 0)["tmap"]
    for cell in (5.0, 10.0, 20.0):
        calib = calibrate(cell, seeds=(100,), sizes=(50,), kinds=("hills", "rocky"))
        for noise in (0.0, 0.5):
            elev = coarse_elevation(tm, cell, noise, seed=100)
            bins = np.digitize(slope_deg(elev), calib.edges_deg[1:-1])
            previous = np.zeros(tm.shape)
            for lam in (0.0, 0.25, 0.5, 1.0, 2.0):
                pm = risk_prior(tm, cell, calib, lam, noise, seed=100)
                expected = np.clip(np.asarray(calib.mean_cost)[bins] + lam * np.asarray(calib.p_lethal)[bins], 0, 1)
                assert np.array_equal(pm.cost, expected)
                assert np.array_equal(pm.lethal, coarse_prior(tm, cell, noise, seed=100).lethal)
                assert ((pm.cost >= 0) & (pm.cost <= 1)).all()
                assert (pm.cost >= previous).all()
                previous = pm.cost
    for kwargs in (dict(cell_m=5.0, lam=0.0), dict(cell_m=20.0, lam=-1.0), dict(cell_m=20.0, lam=np.nan)):
        try:
            risk_prior(tm, calib=calib, **kwargs)
        except ValueError:
            pass
        else:
            raise AssertionError(kwargs)
    print("risk cost passed (expected means, lambda monotonicity/clipping, noise, unchanged lethal mask)", flush=True)


def test_safety():
    calib = calibrate(20.0, sizes=(50,))
    count, successes = 0, 0
    for kind in ("ridge", "craters"):
        for seed in range(5):
            sc = build(kind, 50, seed)
            tm = sc["tmap"]
            for lam in (0.0, 1.0):
                pm = risk_prior(tm, 20.0, calib, lam)
                for radius in (5.0, 15.0):
                    r = run_online(tm, sc["start"], sc["goal"], planner="TA*-S", w=DEFAULT_W,
                                   sense_radius_m=radius, prior_map=pm, prior_lethal="soft")
                    m = evaluate(r["traj"], tm)
                    assert m["steep_len"] == 0 and not m["rock_hit"], (kind, seed, lam, radius, m)
                    successes += int(r["success"])
                    count += 1
    print(f"risk-prior safety passed ({count} trajectories, {successes} successful; 20 m cells, R=5/15 m, lambda=0/1)", flush=True)


if __name__ == "__main__":
    test_coarse_refactor()
    test_calibration()
    test_empty_bins()
    test_cost()
    test_safety()
    print("all risk-prior tests passed")
