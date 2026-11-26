"""Extract the directly recorded evidence around the point-cloud stop in 0847 GD r6."""
import csv
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "runs/08OB89_-0847/GD_r6/physical_1/raw/08OB89_-0847"


def read_json(path):
    return json.loads(path.read_text())


def table(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    mission = read_json(RAW / "mission.json")
    manifest = read_json(RAW.parents[1] / "manifest.json")
    (follower,) = sorted((RAW / "follower").glob("*/mission.json"))
    stop = mission["finished_t"]
    start = mission["started_t"]
    end_ros = mission["final_state"]["sim_time"]
    perception = mission["perception"]
    final_sensors = read_json(RAW / "sensor_status_multi.json")
    updates = table(RAW / "map_updates.csv")

    poses = {}
    for name in ("follower", "planner", "observer"):
        data = [r for r in table(RAW / "pose_trace" / (name + "_pose.csv"))
                if r["has_pose"] == "1"]
        window = [r for r in data if start <= int(r["stamp_ns"])/1e9 <= end_ros]
        mono = [int(r["mono_ns"]) for r in window]
        poses[name] = dict(window_samples=len(mono), max_receive_gap_s=max(b-a for a,b in zip(mono,mono[1:]))/1e9,
                           last_header_stamp_s=int(data[-1]["stamp_ns"])/1e9)
    follower_poses = [r for r in table(RAW / "pose_trace/follower_pose.csv")
                      if r["has_pose"] == "1" and start <= int(r["stamp_ns"])/1e9 <= end_ros]
    tick = table(RAW / "pose_trace/follower_tick.csv")
    lo, hi = (int(follower_poses[i]["mono_ns"]) for i in (0, -1))
    ticks = [r for r in tick if lo <= int(r["mono_ns"]) <= hi]
    cpu = [float(r["cpu_pct"]) for r in table(RAW / "pose_trace/cpu.csv")
           if r["cpu_pct"] and lo <= int(r["mono_ns"]) <= hi]
    sensors = {}
    for sensor, state in perception["sensors"].items():
        near_end = [r for r in updates if r["sensor"] == sensor and r["status"] == "ok"
                    and start <= float(r["stamp"]) <= end_ros]
        durations = [float(r["update_s"]) for r in near_end]
        sensors[sensor] = dict(at_mission_end=state, at_shutdown=final_sensors[sensor],
            age_at_mission_end_s=stop-state["last_stamp"],
            successful_updates_by_message_stamp=len(near_end), max_update_s=max(durations, default=None),
            median_update_s=median(durations) if durations else None,
            over_pointcloud_period_0_1_s=sum(v>.1 for v in durations),
            latest_accepted_in_update_log_s=max(float(r["stamp"]) for r in updates
                if r["sensor"]==sensor and r["status"]=="ok" and int(r["accepted_points"])>0))
    plans = table(RAW / "plans.csv")
    output = dict(
        run=str(RAW.relative_to(ROOT)), status=mission["status"], follower_error=read_json(follower)["online_error"],
        started_sim_s=start, finished_sim_s=stop, recorder_terminal_state_sim_s=end_ros,
        stale_timeout_sim_s=manifest["stale_timeout_s"], perception_ready=perception["ready"],
        oldest_accepted_stamp=perception["last_cloud_stamp"], sensors=sensors,
        poses=poses, pose_timeouts=sum(int(r["pose_timeout"]) for r in tick), tick_samples=len(ticks),
        max_tick_interval_s=max(int(r["interval_ns"]) for r in ticks if r["interval_ns"])/1e9,
        max_tick_duration_s=max(int(r["duration_ns"]) for r in ticks)/1e9,
        total_cpu_pct_samples_in_mission=cpu, plan_successes=sum(r["success"]=="True" for r in plans),
        plan_failures=sum(r["success"]!="True" for r in plans), safety_events=table(RAW / "safety_events.csv"),
        last_map_updates=[{k:r[k] for k in ("stamp","sensor","status","update_s","queue_drops","accepted_points")}
                          for r in updates[-10:]],
        map_update_errors=[r["error"] for r in updates if r["status"]!="ok"])
    print(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
