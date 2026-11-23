"""Check archived LiDAR figures, numeric macros and optional study inputs."""

from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import pandas as pd

from thesis import make_lidar_figures as figures


RESULTS = figures.ROOT/"results"
FILES = {"F8.pdf", "F8.png", "F9.pdf", "F9.png", "F10.pdf", "F10.png",
         "F9_statistics.csv", "numbers_lidar.tex", "sources.json",
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
    for name in ("F8", "F9", "F10"):
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


def test_050(output):
    archived = read(RESULTS/"eval_050/common_eval/runs.csv")
    t4 = read(output/"T4.csv").query("study == '050'").set_index("condition")
    t5 = read(output/"T5.csv").query("study == '050'")
    assert list(t4.index) == ["S", "P", "V"]
    assert list(t4["condition_label"]) == ["050 S", "050 P", "050 V"]
    assert len(t5) == 6
    commands = macros(output)
    for condition, rows in archived.groupby("condition"):
        completed = rows["board_outcome"].eq("completed").sum()
        assert t4.loc[condition, "completed"] == completed
        assert commands[f"LidarTFourTaskZeroFiveZero{condition}Completed"] == completed
        for patch, group in [(None, rows), ("08OB88_00332", rows[rows["patch"] == "08OB88_00332"])]:
            subset = t5[t5["patch"].eq(patch) if patch else t5["patch"].isna()]
            actual = subset[subset["condition"] == condition].iloc[0]
            assert actual["n"] == len(group)
            expected = {
                "debris_entries": group["debris_entries"].sum(),
                "debris_runs": group["debris_len_m"].gt(0).sum(),
                "debris_m": group["debris_len_m"].sum(),
                "box_intervals": group["truth_below_radius_entries"].sum(),
                "box_s": group["truth_below_radius_s"].sum(),
            }
            tag = "ZeroEightOBEightEightZeroZeroThreeThreeTwo" if patch else ""
            prefix = f"LidarTFiveTaskZeroFiveZero{condition}{tag}"
            for field, value in expected.items():
                assert math.isclose(actual[field], value, rel_tol=1e-8)
                suffix = "".join(word.capitalize() for word in field.split("_"))
                assert math.isclose(commands[prefix+suffix], value, rel_tol=1e-8)
            assert actual["debris_runs_n"] == group["debris_len_m"].notna().sum()
    assert "08OB88_00332 only" in (output/"T5.md").read_text()
    print("050 PASS: completion and both T5 scopes are recalculated from the committed CSV")


def test_057(root):
    root.mkdir()
    results, output = root/"results", root/"out"
    results.mkdir()
    for directory in ("eval_050", "eval_044"):
        (results/directory).symlink_to(RESULTS/directory, target_is_directory=True)
    log = StringIO()
    with redirect_stdout(log):
        figures.make_all(output, results)
    assert "Skipped missing results file:" in log.getvalue() and "eval_057/common_eval/runs.csv" in log.getvalue()
    assert set(read(output/"T4.csv")["study"]) == {"044", "050"}
    assert_outputs(output)
    before = (output/"F10.png").read_bytes()

    csv = results/"eval_057/common_eval/runs.csv"
    csv.parent.mkdir(parents=True)
    csv.write_text("condition,patch,rep,board_outcome,no_path_type,debris_len_m,debris_entries,"
                   "truth_below_radius_entries,truth_below_radius_s\n"
                   "S,08OB88_00332,1,completed,,0,0,0,0\n"
                   "PG,08OB88_00332,1,no_path,goal_cell,0.25,1,2,1.5\n"
                   "SGN,example,1,partial,,,,,\n")
    figures.make_all(output, results)
    assert_outputs(output)
    t4 = read(output/"T4.csv").query("study == '057'").set_index("condition")
    assert list(t4.index) == ["S", "PG", "SGN"]
    assert list(t4["condition_label"]) == ["057 S", "057 PG", "057 SGN"]
    assert list(t4["completed"]) == [1, 0, 0]
    t5 = read(output/"T5.csv").query("study == '057'").set_index("condition")
    assert t5.loc["PG", "box_intervals"].tolist() == [2, 2]
    assert t5.loc["SGN", "box_s_n"] == 0 and pd.isna(t5.loc["SGN", "box_s"])
    t6 = read(output/"T6.csv").query("study == '057' and metric == 'goal_cell'")
    assert list(t6["count"]) == [1]
    assert before != (output/"F10.png").read_bytes()
    assert macros(output)["LidarTFourTaskZeroFiveSevenPGNoPath"] == 1
    assert json.loads((output/"sources.json").read_text())[str(csv)] == hashlib.sha256(csv.read_bytes()).hexdigest()
    print("057 PASS: missing input is reported and an added CSV updates F10, the tables and input hashes")


def test_legacy_rows(root, current):
    # Use the unmodified generator on the same archives and library versions.
    base = "150c27a"
    source = subprocess.check_output(
        ["git", "show", f"{base}:conference/thesis/make_lidar_figures.py"], cwd=figures.ROOT)
    previous, output = root/"original_figures.py", root/"before"
    previous.write_bytes(source)
    subprocess.run([sys.executable, str(previous), "--results", str(RESULTS), "--output", str(output)],
                   check=True, capture_output=True, text=True)
    tasks = ("030", "035", "037", "039", "044")
    for table in ("T4", "T5", "T6"):
        before = read(output/f"{table}.csv")
        after = read(current/f"{table}.csv")
        before = before[before["study"].isin(tasks)].reset_index(drop=True)
        after = after.loc[after["study"].isin(tasks), before.columns].reset_index(drop=True)
        pd.testing.assert_frame_equal(before, after, check_exact=True)
    assert (output/"F9_statistics.csv").read_bytes() == (current/"F9_statistics.csv").read_bytes()
    old_commands = macros(output)
    new_commands = macros(current)
    assert {name: new_commands[name] for name in old_commands} == old_commands
    print("legacy PASS: same-environment 030–044 tables, F9 statistics and all prior numeric macros match")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        test_archive(root/"archive")
        test_missing_and_extension(root)
        test_050(root/"archive")
        test_057(root/"terrain")
        test_legacy_rows(root, root/"archive")
    print("all LiDAR figure tests passed")
