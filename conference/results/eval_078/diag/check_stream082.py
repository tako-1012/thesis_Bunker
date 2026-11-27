"""Compare the recorder and mapper's last LiDAR timestamps in preserved runs."""

from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def write(name, data):
    with (ROOT / name).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)


def lidar_timestamps(trial, experiment):
    physical = trial / "physical_1"
    manifest = read(physical / "manifest.json")
    case, = [case for case in manifest["cases"] if case["selected"]]
    raw = physical / case["run_folder"]
    recorder = raw / "sensors"
    mission = read(raw / "mission.json")
    stop = mission["finished_t"]
    lidar = mission["perception"]["sensors"]["lidar"]
    stamp = lidar["last_stamp"]
    chunks = []
    for path in sorted(recorder.glob("chunk_*.npz")):
        with np.load(path, allow_pickle=False) as archive:
            if "lidar_stamp_ns" in archive:
                chunks.append(archive["lidar_stamp_ns"])
    stamps = np.concatenate(chunks) if chunks else np.empty(0, dtype=np.int64)
    end_ns = round(stop*1e9)
    prior = stamps[stamps <= end_ns]
    after = stamps[stamps > end_ns]
    previous = int(prior[-1]) if len(prior) else None
    ref = round(stamp*1e9) if stamp is not None else None
    delta = (previous-ref)/1e9 if previous is not None and ref is not None else None
    return dict(experiment=experiment, beach=case["patch"], trial=trial.name, mission_end_s=stop,
                mapper_received=lidar["received"], mapper_processed=lidar["processed"],
                mapper_queue_drops=lidar["queue_drops"], mapper_last_s=stamp,
                recorder_lidar_frames=len(stamps), recorder_last_at_stop_s=previous/1e9 if previous is not None else None,
                recorder_after_terminal_frames=len(after), recorder_last_minus_mapper_s=delta,
                recorder_age_at_stop_s=(end_ns-previous)/1e9 if previous is not None else None,
                recorder_max_interval_s=np.diff(stamps).max()/1e9 if len(stamps)>1 else None)


def main():
    data = [lidar_timestamps(trial, "078") for trial in sorted((ROOT.parent/"runs").glob("*/*"))]
    data.extend(lidar_timestamps(ROOT/"confirmations"/mode, "082") for mode in ("off", "on"))
    assert len(data) == 26
    write("lidar_stamp_comparison.csv", data)

    replay = ROOT.parent/"runs/08OB88_-1417/d160_s0/offline_localization"
    with (replay/"trajectory.csv").open(newline="") as stream:
        trace = list(csv.DictReader(stream))
    with (replay/"alignments.csv").open(newline="") as stream:
        events = list(csv.DictReader(stream))
    summary = []
    for method in ("odometry", "map_only", "combined"):
        attempted = [e for e in events if e["method"] == method]
        accepted = [e for e in attempted if e["accepted"] == "True"]
        last = accepted[-1] if accepted else None
        if len(accepted) and method == "map_only":
            last_pos = [trace[int(last["scan"])][f"{method}_{axis}"] for axis in "xyz"]
            final_pos = [trace[-1][f"{method}_{axis}"] for axis in "xyz"]
            assert last_pos == final_pos
        status = Counter(e["status"] for e in attempted)
        summary.append(dict(method=method, frames=len(trace), first_error_m=trace[0][f"{method}_error_m"],
                            final_error_m=trace[-1][f"{method}_error_m"], attempted=len(attempted),
                            accepted=len(accepted), not_converged=status["not_converged"],
                            last_accept_s=last["time_s"] if last else None,
                            last_accept_error_m=trace[int(last["scan"])][f"{method}_error_m"] if last else None,
                            final_time_s=trace[-1]["time_s"], truth_distance_m=trace[-1]["truth_distance_m"]))
    write("first_replay_alignments.csv", summary)
    recorded = [r for r in data if r["experiment"] == "078"]
    print("078 recorder minus mapper stamp (s)", Counter(r["recorder_last_minus_mapper_s"] for r in recorded))
    print("082", [r for r in data if r["experiment"] == "082"])
    print("078 first replay", summary)


if __name__ == "__main__":
    main()
