"""Combine the 084 point and replay diagnostics into reviewable tables."""
from collections import Counter
import csv
from pathlib import Path
import statistics


ROOT = Path(__file__).resolve().parent
TRIALS = (
    ("1417_d160_s0", "1417・160・0"),
    ("1417_d0_s0", "1417・0・0"),
    ("0205_d40_s1", "0205・40・1"),
)
MODES = ("raw", "filtered")
METHODS = {"odometry": "積み上げ", "map_only": "地図に重ねる", "combined": "組み合わせ"}
AXES = ("alongshore", "cross_shore", "vertical", "rotation", "unavailable")


def read(path):
    with (ROOT / path).open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(path, rows):
    with (ROOT / path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def lines(path):
    return (ROOT / path).read_text().strip()


def table(headers, rows):
    return "\n".join(
        "| " + " | ".join(map(str, row)) + " |"
        for row in (headers, ["---"] * len(headers), *rows)
    )


def number(value, decimals=2):
    return f"{float(value):.{decimals}f}" if value != "" else "—"


def triad(row, keys, decimals=2):
    return " / ".join(number(row[k], decimals) for k in keys)


def without_mode(rows):
    return [{k: v for k, v in row.items() if k != "mode"} for row in rows]


def main():
    if lines("replay_exit.txt") != "0":
        raise RuntimeError("Replay did not finish successfully")
    bands = read("near_points_by_band.csv")
    scans = read("near_points_by_scan.csv")
    recurrence = read("near_point_recurrence.csv")
    point_rows, motion_rows, replay_rows, failure_rows = [], [], [], []
    comparisons, failures = [], []
    for key, label in TRIALS:
        trial_scans = [row for row in scans if row["trial"] == key]
        box = sum(int(row["body_box_points"]) for row in trial_scans)
        removed = sum(int(row["removed_from_076"]) for row in trial_scans)
        assert removed == 0 and box == 0

        for band in (row for row in bands if row["trial"] == key):
            point_rows.append((
                label, band["band"], f'{band["frames_with_points"]}/{band["frames"]}',
                band["points"], triad(band, ("min_per_scan", "median_per_scan", "max_per_scan"), 0),
                *(triad(band, (f"{axis}_min_m", f"{axis}_median_m", f"{axis}_max_m"), 3)
                  if int(band["points"]) else "—" for axis in "xyz"),
            ))
            if int(band["points"]):
                near_scan = [row for row in trial_scans if int(row[band["band"]])]
                timing = [(int(row["stamp_ns"]) - int(trial_scans[0]["stamp_ns"])) / 1e9
                          for row in near_scan]
                by_motion = Counter(row["motion"] for row in near_scan)
                print(label, band["band"], "near scan time [s]", min(timing), max(timing),
                      dict(by_motion), flush=True)
        r = next(row for row in recurrence if row["trial"] == key and row["band"] == "1–2m")
        motion_rows.append((label, r["stationary_frames"], r["moving_frames"], r["cells_in_both"],
                            r["cells_in_at_least_half_of_both"], box, removed))

        base = ROOT / "replay" / key
        pairs = []
        for mode in MODES:
            summary = read(base / mode / "summary.csv")
            events = read(base / mode / "alignments.csv")
            assert [row["method"] for row in summary] == list(METHODS)
            assert all(int(row["frames"]) == len(trial_scans) and row["discarded_scans"] == "0"
                       for row in summary)
            pairs.append((summary, events))
            comparisons.extend(summary)
            for method in ("map_only", "combined"):
                selected = [r for r in events if r["method"] == method]
                failed = [r for r in selected if r["converged"] == "False"]
                assert all(r["converged"] in ("True", "False") for r in selected)
                totals = next(row for row in summary if row["method"] == method)
                assert len(selected) == int(totals["attempts"])
                assert len(selected) - len(failed) == int(totals["converged"])
                values = [float(r["minimum_scaled_eigenvalue"]) for r in failed
                          if r["minimum_scaled_eigenvalue"]]
                counts = Counter(r["weak_axis"] for r in failed)
                assert len(values) + counts["unavailable"] == len(failed)
                stats = {
                    "trial": key, "mode": mode, "method": method, "attempts": len(selected),
                    "not_converged": len(failed), "with_information": len(values),
                    "min_eigenvalue": min(values) if values else "",
                    "median_eigenvalue": statistics.median(values) if values else "",
                    "max_eigenvalue": max(values) if values else "",
                    "eigenvalue_le_1": sum(v <= 1 for v in values),
                    **{axis: counts[axis] for axis in AXES},
                    "converged_but_rejected": sum(r["converged"] == "True" and r["accepted"] == "False"
                                                  for r in selected),
                }
                failures.append(stats)
                if mode == "raw":
                    failure_rows.append((
                        label, METHODS[method], f"{len(failed)}/{len(selected)}", len(values),
                        triad(stats, ("min_eigenvalue", "median_eigenvalue", "max_eigenvalue"), 3),
                        stats["eigenvalue_le_1"], *(counts[axis] for axis in AXES),
                        stats["converged_but_rejected"],
                    ))

        raw, filtered = pairs
        assert without_mode(raw[0]) == without_mode(filtered[0]), key
        assert without_mode(raw[1]) == without_mode(filtered[1]), key
        for row in raw[0]:
            errors = [number(row[f"{metric}_error_m"]) for metric in ("mean", "p95", "max", "final")]
            if row["attempts"]:
                fraction = float(row["converged_fraction"])
                convergence = f'{row["converged"]}/{row["attempts"]} ({fraction:.1%})'
            else:
                convergence = "—"
            replay_rows.append((label, METHODS[row["method"]], *errors, convergence))

    write("replay_comparison.csv", comparisons)
    write("failed_alignment_summary.csv", failures)
    report = (ROOT / "report084_template.md").read_text()
    replacements = {
        "POINTS": table(("砂浜・個/ha・seed", "距離", "点のあるスキャン", "総点数", "点/スキャン 最小 / 中央 / 最大",
                         "x 前＋ (m)", "y 左＋ (m)", "z 上＋ (m)"), point_rows),
        "MOTION": table(("砂浜・個/ha・seed", "静止スキャン", "走行スキャン", "双方の同じ 5 cm 格子",
                         "双方の半数以上に出た格子", "車体の箱内", "076 から追加で除外"), motion_rows),
        "REPLAY": table(("砂浜・個/ha・seed", "076 の方法", "平均 (m)", "95% 値 (m)", "最大 (m)", "最後 (m)",
                         "収束 / 試行"), replay_rows),
        "FAILED": table(("砂浜・個/ha・seed", "076 の方法", "未収束 / 試行", "固有値あり",
                          "最小固有値の最小 / 中央 / 最大", "固有値 ≤1", "海岸沿い", "海岸横断", "鉛直",
                          "回転", "不明", "収束後に不採用"), failure_rows),
        "SCANS": str(len(scans)),
        "PIN": lines("execution_commit.txt"),
        "START": lines("started.txt"),
        "END": lines("finished.txt"),
        "TESTS": str(len(lines("tests/summary.txt").splitlines())),
        "TEST_EXIT": lines("tests/suite_exit.txt"),
    }
    for name, value in replacements.items():
        report = report.replace("{{" + name + "}}", value)
    assert "{{" not in report
    with (ROOT / "REPORT_ja.md").open("x") as stream:
        stream.write(report)
    print("Six replays compared; raw and filtered metrics and alignment rows are identical")


if __name__ == "__main__":
    main()
