"""Check task049 archives, numeric macros, missing inputs and the 044 extension."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import re
import tempfile

import pandas as pd

from thesis import make_lidar_figures as figures


RESULTS = figures.ROOT/"results"
FILES = {"F8.pdf", "F8.png", "F9.pdf", "F9.png", "F9_statistics.csv", "numbers_lidar.tex", "sources.json",
         *(f"T{n}.{suffix}" for n in (4, 5, 6) for suffix in ("csv", "md", "tex"))}


def read(path):
    return pd.read_csv(path, dtype={"study": str, "condition": str, "setup": str})


def macros(output):
    commands = re.findall(r"\\newcommand\{\\([A-Za-z]+)\}\{([^{}]+)\}",
                          (output/"numbers_lidar.tex").read_text())
    assert len(commands) == len(dict(commands)) and commands
    return {key: float(value) for key, value in commands}


def assert_outputs(output):
    assert {file.name for file in output.iterdir()} == FILES
    for name in ("F8", "F9"):
        assert (output/f"{name}.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert (output/f"{name}.pdf").read_bytes().startswith(b"%PDF-")
    for name in ("T4", "T5", "T6"):
        assert r"\begin{tabular}" in (output/f"{name}.tex").read_text()
        assert "| Task |" in (output/f"{name}.md").read_text()


def test_archive(output):
    figures.make_all(output)
    assert_outputs(output)
    t4, t5, t6 = (read(output/f"T{i}.csv") for i in (4, 5, 6))
    commands = macros(output)

    raw030 = read(RESULTS/"eval_ground_endpoint/runs.csv")
    controls = raw030[raw030["condition"] == "C1"]
    board = read(RESULTS/"common_eval/archive_outcomes_board.csv")
    board_stuck = board[(board["実験"] == 30) & board["条件"].str.startswith("C1")]["止まったまま"].sum()
    c1 = t4[(t4["study"] == "030") & (t4["condition"] == "C1")].iloc[0]
    assert c1["completed"] == controls["outcome"].eq("completed").sum()
    assert c1["stuck"] == board_stuck
    assert commands["LidarTFourTaskZeroThreeZeroCOneStuck"] == board_stuck

    pilot = read(RESULTS/"eval_035/runs.csv").query("condition == 'S1'")
    assert not ((t4["study"] == "035") & t4["condition"].isin(["S1", "S2"])).any()
    assert math.isclose(commands["LidarTFiveTaskZeroThreeFiveSOneDebrisM"], pilot["debris_len_m"].sum(), rel_tol=1e-8)
    assert t5[t5["study"] == "030"]["off_path"].isna().all()
    assert "LidarTFiveTaskZeroThreeZeroCOneOffPath" not in commands

    rtf = read(RESULTS/"rtf_compare/stage_b/common_eval/runs.csv")
    for condition in ("0.3", "1.0"):
        group = rtf[rtf["condition"] == condition]
        observed = t4[(t4["study"] == "039") & (t4["condition"] == condition)].iloc[0]
        assert observed["n"] == len(group)
        assert observed["completed"] == group["board_outcome"].eq("completed").sum()
    ratio_one = rtf[rtf["condition"] == "1.0"]
    assert math.isclose(commands["LidarTFiveTaskZeroThreeNineOneDotZeroMinBoxM"],
                        ratio_one["min_truth_clearance_m"].min(), rel_tol=1e-8)
    assert commands["LidarTFiveTaskZeroThreeNineOneDotZeroUnsafeTilt"] == ratio_one["ev_unsafe_tilt"].sum()

    timings = read(RESULTS/"rtf_compare/stage_b/sensor_updates.csv")
    lidar = timings[(timings["factor"] == .3) & (timings["sensor"] == "lidar")]
    bench = read(RESULTS/"map_speed/timing.csv")
    old = bench.query("version == 'before' and mapper == 'PointCloudMapMulti' "
                      "and stage == 'total' and ground == 'all_returns' and sensor == 'camera1'").iloc[0]
    assert math.isclose(commands["LidarFNineTaskZeroThreeNineZeroDotThreeLidarPNineFiveMs"],
                        1000*lidar["p95_s"].median(), rel_tol=1e-8)
    assert math.isclose(commands["LidarFNineTaskZeroThreeEightBeforeCameraOneMedianMs"], old["median_ms"])

    checks = read(RESULTS/"waypoint_feasibility/goal_cell.csv")
    replay = read(RESULTS/"terrain_from_prior/goals.csv")
    assert commands["LidarTSixTaskZeroFourSixPreflightFlaggedCount"] == checks["prior_status"].isin(
        ["blocked_cell", "unreachable"]).sum()
    assert commands["LidarTSixTaskZeroFourSixPreflightFlaggedN"] == checks["prior_status"].notna().sum()
    assert commands["LidarTSixTaskZeroFourSevenFinalMapGainedRouteCount"] == replay["final_recovered"].sum()
    assert commands["LidarTSixTaskZeroFourSevenFailureSnapshotGainedRouteN"] == replay["failure_snapshot_n"].sum()
    assert commands["LidarTSixTaskZeroFourSevenReplayCoverageMissingMapCount"] == replay["missing_n"].sum()
    for task, group in checks.groupby("experiment"):
        total = t6[(t6["study"] == str(task).zfill(3)) & (t6["metric"] == "goal_cell")]["count"]
        assert len(total) == 1 and total.iloc[0] == len(group)

    provenance = json.loads((output/"sources.json").read_text())
    expected = {f"results/{study.csv}" for study in figures.STUDIES if (RESULTS/study.csv).is_file()}
    expected.update({"results/waypoint_feasibility/goal_cell.csv", "results/terrain_from_prior/goals.csv",
                     "results/map_speed/timing.csv", "results/rtf_compare/stage_b/sensor_updates.csv"})
    assert set(provenance) == expected
    for file, digest in provenance.items():
        assert digest == hashlib.sha256((figures.ROOT/file).read_bytes()).hexdigest()
    print("archive PASS: all figures/tables, macros recalculated from source CSVs and exact input hashes")


def test_missing_and_extension(root):
    results = root/"results"
    results.mkdir()
    for directory in ("eval_ground_endpoint", "real_sensors_compare", "rtf_compare", "waypoint_feasibility",
                      "terrain_from_prior", "map_speed"):
        (results/directory).symlink_to(RESULTS/directory, target_is_directory=True)
    future = results/"eval_044/common_eval"
    future.mkdir(parents=True)
    (future/"runs.csv").write_text("condition,patch,rep,board_outcome,no_path_type,rolled_over\n"
                                  "D,example,1,no_path,goal_cell,False\n"
                                  "D,example,2,other_error,,\n"
                                  "D,example,3,,,\n")
    log = StringIO()
    output = root/"out"
    with redirect_stdout(log):
        figures.make_all(output, results)
    assert "Skipped missing results file" in log.getvalue() and "eval_035/runs.csv" in log.getvalue()
    assert_outputs(output)
    t4 = read(output/"T4.csv")
    assert "035" not in set(t4["study"])
    assert "039" in set(t4["study"])
    d = t4.loc[t4["study"] == "044"].iloc[0]
    assert (d["no_path"], d["other"], d["unknown"]) == (1, 1, 1)
    t6 = read(output/"T6.csv")
    assert len(t6[(t6["study"] == "044") & (t6["metric"] == "goal_cell")]) == 1
    assert macros(output)["LidarTFourTaskZeroFourFourDNoPath"] == 1
    for protected in (figures.ROOT/"paper", figures.ROOT/"thesis/out", figures.ROOT/"results", results):
        try:
            figures.make_all(protected/"task049-test", results)
        except ValueError as error:
            assert "protected" in str(error)
        else:
            raise AssertionError("protected destination accepted")
    print("missing/044 PASS: remaining outputs and missing-input message; common schema extends the figures")
    print("output guard PASS: existing results, pillar-one output and paper paths rejected")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_archive(root/"archive")
        test_missing_and_extension(root)
    print("all LiDAR figure tests passed")
