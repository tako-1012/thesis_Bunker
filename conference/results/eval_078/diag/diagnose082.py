"""Frame hypotheses and timing checks for the preserved 078 and 082 runs."""

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import sys

import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from experiments.offline_localization import MIN_RANGE_M, MAX_RANGE_M, poses_from_xyz_quat, synchronized_truth
from experiments.recording_bridge import open_archive
from tapp.sensor_recording import iter_lidar

ROOT = Path(__file__).resolve().parent
PATCHES = ("08OB88_-1417", "08OB86_-0205")
SELECTED = ((PATCHES[0], "d160_s0"), (PATCHES[0], "d0_s0"), (PATCHES[1], "d40_s1"))
SENSORS = ("lidar", "camera1", "camera2")


def read(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def write(name, data):
    columns = list(dict.fromkeys(key for row in data for key in row))
    with (ROOT / name).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(data)
    print(name, len(data), flush=True)


def raw_run(root):
    physical = root / "physical_1"
    manifest = read(physical / "manifest.json")
    case, = [case for case in manifest["cases"] if case["selected"]]
    return physical / case["run_folder"], manifest, case


def variants(mount):
    identity = np.eye(3)
    yield "baseline", mount, identity, 0., False
    yield "no_mount", np.eye(4), identity, 0., False
    for delta in (-.35, .35):
        adjusted = mount.copy()
        adjusted[2, 3] += delta
        yield f"mount_z_{delta:+g}m", adjusted, identity, 0., False
    yield "swap_xy", mount, identity[[1, 0, 2]], 0., False
    for index, axis in enumerate("xyz"):
        flipped = identity.copy()
        flipped[index, index] = -1
        yield f"flip_{axis}", mount, flipped, 0., False
    yield "flip_xyz", mount, -identity, 0., False
    for yaw in (-90, 90, 180):
        yield f"lidar_yaw_{yaw:+d}deg", mount, Rotation.from_euler("z", yaw, degrees=True).as_matrix(), 0., False
    for shift in (-.5, -.1, .1, .5):
        yield f"truth_time_{shift:+g}s", mount, identity, shift, False
    yield "truth_misread_as_wxyz", mount, identity, 0., True


def quantiles(values, fields=(50, 90)):
    return np.percentile(values, fields) if len(values) else [None for _ in fields]


def frame_check(raw, tag, workers):
    source = open_archive(raw)
    stamps = source.lidar_stamp_ns
    valid = np.flatnonzero((stamps >= source.truth_stamp_ns[0] + 500_000_000)
                           & (stamps <= source.truth_stamp_ns[-1] - 500_000_000))
    assert len(valid) >= 20, raw
    chosen = set(valid[np.linspace(0, len(valid)-1, 20, dtype=int)])
    scans = []
    for i, scan in enumerate(iter_lidar(raw/"sensors")):
        if i in chosen:
            expected_stamp = int(stamps[i])
            assert scan.stamp_ns == expected_stamp
            xyz = scan.xyz.reshape(-1, 3)
            xyz = xyz[np.isfinite(xyz).all(axis=1)]
            ranges = np.linalg.norm(xyz, axis=1)
            xyz = xyz[(ranges > MIN_RANGE_M) & (ranges < MAX_RANGE_M)]
            assert len(xyz) > 0, (raw, i)
            scans.append((expected_stamp, xyz))
        if i == max(chosen):
            break
    assert len(scans) == 20
    selected_ns = np.asarray([stamp for stamp, _ in scans], dtype=np.int64)
    with np.load(raw/"reference_cloud.npz", allow_pickle=False) as reference:
        cloud = reference["xyz"]
    tree = cKDTree(cloud)
    world_rows, scan_rows = [], []
    for label, mount, axes, shift, wrong in variants(source.base_from_lidar):
        truth = source.truth_values.copy()
        if wrong:
            truth[:, 3:] = np.roll(truth[:, 3:], -1, axis=1)
        keep, pose = synchronized_truth(selected_ns + round(shift*1e9), source.truth_stamp_ns,
                                        poses_from_xyz_quat(truth))
        assert np.array_equal(keep, np.arange(len(scans))), (raw, label)
        dists = []
        for (stamp, xyz), world in zip(scans, pose @ mount, strict=True):
            rotated = xyz @ axes.T @ world[:3, :3].T + world[:3, 3]
            dist = tree.query(rotated, k=1, workers=workers)[0]
            dists.append(dist)
            if label == "baseline":
                p50, p90 = quantiles(dist)
                scan_rows.append(dict(tag, scan_sim_s=stamp/1e9, points=len(dist),
                                      median_m=p50, p90_m=p90))
        all_dist = np.concatenate(dists)
        p50, p90 = quantiles(all_dist)
        world_rows.append(dict(tag, hypothesis=label, scans=len(scans), points=len(all_dist),
                               first_scan_sim_s=selected_ns[0]/1e9, last_scan_sim_s=selected_ns[-1]/1e9,
                               reference_points=len(cloud), median_m=p50, p90_m=p90,
                               fraction_under_5cm=np.mean(all_dist < .05)))
    return world_rows, scan_rows, pose_check(raw, tag, source)


def pose_check(raw, tag, source):
    # pose_trace captures both clocks but no XYZ. Resolve the observer's ROS
    # receipt clock to trajectory.csv, then join that pose on the header stamp.
    observer = defaultdict(list)
    for row in rows(raw/"pose_trace/observer_pose.csv"):
        if row["has_pose"] == "1" and row["stamp_source"] == "header" and row["ros_ns"]:
            observer[int(row["ros_ns"])].append(int(row["stamp_ns"]))
    trajectory = defaultdict(list)
    for row in rows(raw/"trajectory.csv"):
        trajectory[round(float(row["t"])*1e9)].append(
            [float(row[k]) for k in ("x", "y", "z", "roll", "pitch", "yaw")])
    truth = dict(zip(source.truth_stamp_ns, source.truth_values, strict=True))
    saved, seen = [], []
    ambiguous = missing_stamp = 0
    for ros_ns, poses in trajectory.items():
        stamps = observer[ros_ns]
        if len(stamps) != len(poses):
            ambiguous += len(poses)
            continue
        for stamp, pose in zip(stamps, poses, strict=True):
            if stamp not in truth:
                missing_stamp += 1
                continue
            saved.append(truth[stamp])
            seen.append(pose)
    assert saved, raw
    saved, seen = np.asarray(saved), np.asarray(seen)
    xyz = np.linalg.norm(saved[:, :3]-seen[:, :3], axis=1)
    angles = np.degrees((Rotation.from_quat(saved[:, 3:]).inv() *
                         Rotation.from_euler("xyz", seen[:, 3:])).magnitude())
    return dict(tag, recorded_truth=len(truth), observer_rows=sum(map(len, trajectory.values())),
                exact_header_join_rows=len(xyz), ambiguous_observer_rows=ambiguous,
                observer_rows_without_recorded_header=missing_stamp,
                position_median_m=np.median(xyz), position_p90_m=np.percentile(xyz, 90), position_max_m=max(xyz),
                orientation_median_deg=np.median(angles), orientation_p90_deg=np.percentile(angles, 90),
                orientation_max_deg=max(angles), mount_xyz_m=json.dumps(source.base_from_lidar[:3, 3].tolist()),
                mount_rotation_deg=json.dumps(Rotation.from_matrix(source.base_from_lidar[:3, :3]).as_euler(
                    "xyz", degrees=True).tolist()),
                extrinsic_source=source.extrinsic_source)


def timing(root, tag):
    raw, manifest, case = raw_run(root)
    m = read(raw/"mission.json")
    begin, end, wall = m["started_t"], m["finished_t"], m["wall_elapsed_s"]
    follower = [read(f) for f in (raw/"follower").glob("*/mission.json")]
    errors = ",".join(sorted({j["online_error"] for j in follower if j.get("online_error")}))
    percep = m.get("perception") or {}
    ages = {name: (end-stamp if (stamp := percep.get("sensors", {}).get(name, {}).get("last_stamp")) is not None
                   else None) for name in SENSORS}
    present = {sensor: age for sensor, age in ages.items() if age is not None}
    sensor_meta = raw/"sensors/metadata.json"
    fields = {}
    if sensor_meta.is_file():
        metadata = read(sensor_meta)
        fields.update(sensor_bytes=sum(p.stat().st_size for p in sensor_meta.parent.iterdir() if p.is_file()),
                      sensor_chunks=metadata["chunks"], record_state=metadata["status"],
                      record_sim_s=(metadata["end_ns"]-metadata["begin_ns"])/1e9)
        for name, count in metadata["saved"].items():
            fields[f"saved_{name}"] = count
            fields[f"received_{name}"] = metadata["received"][name]
    cpu = [float(row["cpu_pct"]) for row in rows(raw/"pose_trace/cpu.csv") if row["cpu_pct"]]
    updates = [float(row["update_s"]) for row in rows(raw/"map_updates.csv")
               if row["status"] == "ok" and row["update_s"]]
    return dict(tag, status=m["status"], follower_error=errors, mission_start_sim_s=begin, mission_end_sim_s=end,
                duration_sim_s=end-begin, duration_wall_s=wall, measured_rtf=(end-begin)/wall,
                **{f"age_{name}_s": ages[name] for name in SENSORS},
                oldest_sensor=max(present, key=present.get) if present else None,
                gpu_rendered=case["rendering"]["gpu_rendered"],
                image=manifest["environment"]["image"], exit_code=int((root/"exit.txt").read_text()),
                system_cpu_samples=len(cpu), system_cpu_median_pct=quantiles(cpu)[0],
                map_update_samples=len(updates), map_update_median_s=quantiles(updates)[0],
                map_update_p95_s=quantiles(updates, (95,))[0], **fields)


def process_summary(folder, mode):
    series = defaultdict(list)
    for row in rows(folder/"process_usage.csv"):
        series[row["role"], row["pid"]].append(row)
    output = []
    for (role, pid), sample in sorted(series.items()):
        values = [float(r["cpu_percent_one_core"]) for r in sample if r["cpu_percent_one_core"]]
        p50, p95 = quantiles(values, (50, 95))
        output.append(dict(mode=mode, process=role, pid=pid, samples=len(sample),
                           cpu_median_pct_one_core=p50, cpu_p95_pct_one_core=p95,
                           cpu_total_s_last=sample[-1]["cpu_total_s"],
                           cpu_peak_pct_one_core=max(values) if values else None,
                           rss_peak_bytes=max(int(row["rss_bytes"]) for row in sample)))
    return output


def main():
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    assert workers in (1, 2)
    base = ROOT.parent / "runs"
    trial_paths = [base / beach / f"d{density}_s{seed}"
                   for density in (0, 10, 40, 160) for beach in PATCHES for seed in range(3)]
    assert set(trial_paths) == {p for p in base.glob("*/*") if p.is_dir()}
    original = []
    for run in trial_paths:
        density, seed = run.name.split("_")
        info = dict(beach=run.parent.name, density_per_ha=int(density[1:]), seed=int(seed[1:]))
        original.append(timing(run, info))
    assert Counter(r["follower_error"] for r in original) == {"lidar_unavailable_or_stale": 24}
    write("078_timing.csv", original)
    comparisons, process = [], []
    for mode in ("off", "on"):
        folder = ROOT / "confirmations" / mode
        comparisons.append(timing(folder, dict(mode=mode)))
        process.extend(process_summary(folder, mode))
    write("082_comparison.csv", comparisons)
    write("082_process_usage_summary.csv", process)
    frames, scans, poses = [], [], []
    for beach, label in SELECTED:
        trial = base / beach / label
        raw, _, _ = raw_run(trial)
        frame_rows, scan_rows, pose_row = frame_check(raw, dict(beach=beach, trial=label), workers)
        frames.extend(frame_rows)
        scans.extend(scan_rows)
        poses.append(pose_row)
        baseline = frame_rows[0]
        best = min(frame_rows, key=lambda r: r["median_m"])
        print(f"{beach}/{label}: {baseline['median_m']:.6f}/{baseline['p90_m']:.6f} m; "
              f"best {best['hypothesis']} {best['median_m']:.6f}; pose matches {pose_row['exact_header_join_rows']}",
              flush=True)
    write("frame_hypotheses.csv", frames)
    write("frame_baseline_scans.csv", scans)
    write("truth_pose_comparison.csv", poses)


if __name__ == "__main__":
    main()
