"""Natural-terrain determinism, spectra, rock area law, feasibility and safety."""

import numpy as np
from tapp.natural_terrain import (
    NATURAL_TYPES,
    H,
    generate_natural,
    fractal_surface,
    spectrum_slope,
    ROCK_K,
)
from tapp.natural_scenario import build_natural
from tapp.scenario import run_planner
from tapp.planners import astar
from tapp.online import run_online
from tapp.prior import coarse_prior
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION


def test_generation():
    for kind in NATURAL_TYPES:
        a = generate_natural(kind, 50, 100)
        b = generate_natural(kind, 50, 100)
        c = generate_natural(kind, 50, 101)
        assert np.array_equal(a["elev"], b["elev"]) and np.array_equal(
            a["rock"], b["rock"]
        )
        assert not np.array_equal(a["elev"], c["elev"])
        assert a["elev"].shape == (round(50 / RESOLUTION),) * 2
        assert np.isfinite(a["elev"]).all() and a["rock"].dtype == bool
    for kind in NATURAL_TYPES:
        for size in (100, 200):
            t = generate_natural(kind, size, 100)
            assert (
                t["elev"].shape == (round(size / RESOLUTION),) * 2
                and np.isfinite(t["elev"]).all()
            )
    print(
        "natural generation determinism, distinct seeds, shape and finite values passed",
        flush=True,
    )


def test_spectrum():
    slopes = [
        spectrum_slope(fractal_surface(128, np.random.default_rng(s))) for s in range(5)
    ]
    assert abs(np.mean(slopes) + (2 * H + 2)) <= 0.3, slopes
    print("pre-erosion radial spectrum passed:", slopes, flush=True)


def test_rocks():
    ds = np.concatenate(
        [
            generate_natural("boulders", 100, s)["rock_diameters"]
            for s in range(100, 105)
        ]
    )
    q = 1.79 + 0.152 / ROCK_K
    for d in (0.4, 0.6, 1.0):
        measured = np.sum(np.pi * ds[ds >= d] ** 2 / 4) / (5 * 100**2)
        expected = ROCK_K * np.exp(-q * d)
        assert abs(measured / expected - 1) <= 0.30, (d, measured, expected)
        print("rock area law:", d, measured, expected, flush=True)


def test_scenarios_and_safety():
    count = 0
    for kind in NATURAL_TYPES:
        for seed in range(3):
            sc = build_natural(kind, 50, seed)
            tm = sc["tmap"]
            if seed == 0:
                assert astar(tm.lethal, sc["start"], sc["goal"])["success"]
                assert run_planner("TA*-S", sc)["success"]
            r = run_online(
                tm,
                sc["start"],
                sc["goal"],
                prior_map=coarse_prior(tm, 10),
                sense_radius_m=5,
                exact_los=True,
            )
            assert len(path_lethal_cells(r["traj"], tm.lethal)) == 0, (kind, seed)
            count += 1
    print(
        f"natural scenarios and exact online safety passed ({count} trajectories)",
        flush=True,
    )



def test_experiment_oracle_audit():
    import tempfile
    from pathlib import Path
    from experiments import natural_terrain as experiment

    previous = experiment.OUT
    with tempfile.TemporaryDirectory(prefix="natural-audit-test-") as directory:
        experiment.OUT = Path(directory)
        try:
            _, _, rows = experiment.run(("mountain", 50, 100, "test"))
        finally:
            experiment.OUT = previous
    sc = build_natural("mountain", 50, 100)
    for name in ("A*", "TA*-S"):
        path = run_planner(name, sc)["path"]
        expected = len(path_lethal_cells(path, sc["tmap"].lethal))
        row = next(row for row in rows if row["variant"] == "oracle " + name)
        assert row["lethal_cells"] == expected
    print("experiment oracle contact audit passed (both reference planners)", flush=True)

if __name__ == "__main__":
    test_generation()
    test_spectrum()
    test_rocks()
    test_scenarios_and_safety()
    test_experiment_oracle_audit()
    print("all natural-terrain tests passed")
