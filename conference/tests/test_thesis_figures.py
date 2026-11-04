"""Verify artifact completeness and independent beach-level archival calculations."""

from pathlib import Path
import re
import tempfile
import numpy as np
import pandas as pd
from thesis.make_figures import ROOT, make_all


def main():
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder)
        t1, t2, _ = make_all(output)
        for number in range(1, 8):
            for suffix in ("pdf", "png"):
                assert (output / f"F{number}.{suffix}").stat().st_size > 0
        for number in range(1, 4):
            for suffix in ("tex", "md"):
                assert (output / f"T{number}.{suffix}").stat().st_size > 0
        assert (output / "numbers.tex").stat().st_size > 0
        raw = pd.read_csv(ROOT / "results/real_beach_las/offline.csv")
        for row in t1.itertuples():
            g = raw[(raw.debris == row.debris) & raw.planner.isin(["A*", "TA*-S exact"])]
            p = g.groupby(["kind", "planner"])[row.metric].mean().unstack("planner")
            assert len(p) == row.n == 48
            assert row.delta_median == (p["TA*-S exact"] - p["A*"]).median()
            if row.metric != "length_xy":
                assert row.A_median == p["A*"].median()
                assert row.TAS_median == p["TA*-S exact"].median()
            assert row.p_holm >= row.p
        log = (ROOT / "results/online_mission/online_mission_log.txt").read_text()
        for row in t2.itertuples():
            matches = re.findall(r"^\s*stale\s+" + str(row.radius_m) + r"\s+" + row.mode + r"\s+48\s+\d+\s+\d+\s+48\s+(\d+)", log, re.M)
            assert matches and all(int(x) == row.touching for x in matches)
        for file in output.iterdir():
            if file.suffix in (".csv", ".json", ".md", ".tex", ".txt"):
                assert "energy" not in file.read_text().lower(), file
        print("thesis: F1-F7 PDF/PNG, T1-T3 LaTeX/Markdown and numbers.tex generated")
        print("statistics: 48 paired beaches, size means, medians and archived contact counts verified")
        print("outputs: no excluded measurement columns or values; all thesis figure tests passed")


if __name__ == "__main__":
    main()
