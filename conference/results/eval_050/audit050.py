"""Calculate terrain safety, end-map metrics, and termination evidence for task 050."""
import csv
import json
from pathlib import Path

import numpy as np

from experiments.eval_runs import read_csv, read_trajectory
from tapp.config import RESOLUTION, Robot
from tapp.endpoint_policy import audit_path, load_snapshot
from tapp.traversability import inflate, slope_deg

ROOT = Path(__file__).resolve().parent
ROBOT = Robot()
RADIUS = ROBOT.footprint_radius
GOAL_0167 = (137, 294)
MODES = {"S": "sensor", "P": "prior", "V": "prior_veto"}


def load(path):
    return json.loads(path.read_text())


def write(name, rows):
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (ROOT / name).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_rows(path):
    return read_csv(path)[1]


def steep_mask(elev):
    return slope_deg(elev) > ROBOT.max_slope_deg


def length(xy, mask, halo):
    item = audit_path(xy, halo, mask)
    return item["truth_lethal_length_m"], item["relaxed_length_m"]


def terrain_metrics(raw, row, ref, final):
    condition = row["condition"]
    prior = steep_mask(ref["prior_elev"])
    truth = steep_mask(ref["truth_elev"])
    planned_steep = steep_mask(final["elev"]) if condition == "S" else final["terrain_steep"]
    true_halo, planned_halo = inflate(truth, RADIUS), inflate(planned_steep, RADIUS)
    known = final["seen"] if condition == "S" else final["seen"] | planned_halo
    blocked = final["lethal"] & known
    trace, _, _ = read_trajectory(raw)
    travel_core, travel_halo = length(trace[:, 1:], truth, true_halo)
    revisions = [np.array(json.loads(record["path"])) for record in csv_rows(raw / "path_revisions.csv")]
    assert revisions and all(path.ndim == 2 and path.shape[1] == 2 for path in revisions)
    measured = [length(path, truth, true_halo) for path in revisions]
    pcore, phalo = np.array(measured).T
    metrics = dict(path_revisions=len(measured), plan_true_steep_m=float(pcore.sum()),
        plan_true_halo_m=float(phalo.sum()), plan_max_one_revision_steep_m=float(pcore.max()),
        plan_max_one_revision_halo_m=float(phalo.max()), plan_revisions_in_halo=int((phalo>1e-9).sum()),
        travel_true_steep_m=travel_core, travel_true_halo_m=travel_halo,
        map_false_steep_023=int((final["seen"] & blocked & planned_halo & ~ref["truth_lethal"]).sum()),
        map_false_halo=int((blocked & planned_halo & ~(ref["truth_lethal"] | true_halo)).sum()),
        map_miss_steep=int((truth & ~blocked).sum()),
        map_miss_halo=int((true_halo & ~blocked).sum()),
        map_seen_miss_steep=int((final["seen"] & truth & ~blocked).sum()),
        map_seen_miss_halo=int((final["seen"] & true_halo & ~blocked).sum()),
        exact_prior_height_equal=bool(np.array_equal(ref["prior_elev"], ref["truth_elev"])),
        prior_truth_elev_max_abs_m=float(np.abs(ref["prior_elev"]-ref["truth_elev"]).max()),
        prior_missed_true_steep=int((truth & ~prior).sum()),
        prior_extra_steep=int((prior & ~truth).sum()))
    if condition == "V":
        supported = final["veto_supported"]
        added = planned_steep & ~prior
        assert not np.any(added & ~supported)
        metrics.update(veto_supported=int(supported.sum()), veto_supported_true=int((supported & truth).sum()),
            veto_supported_nonsteep=int((supported & ~truth).sum()), veto_added=int(added.sum()),
            veto_added_true=int((added & truth).sum()), veto_added_false=int((added & ~truth).sum()))
    return metrics, prior, truth, planned_steep, blocked, trace, revisions


def unpack_fine(final):
    shape = tuple(final["fine_shape"])
    return np.unpackbits(final["fine_inflated_bits"], count=int(np.prod(shape))).reshape(shape).astype(bool)


def map_at(final, ref, prior, truth, steep, blocked, cell):
    halo = inflate(steep, RADIUS)
    kind = dict(estimated_steep_halo=bool(halo[cell]), prior_steep_halo=bool(inflate(prior,RADIUS)[cell]),
        true_steep_halo=bool(inflate(truth,RADIUS)[cell]), true_lethal=bool(ref["truth_lethal"][cell]),
        prior_rock_halo=bool(ref["prior_rock"][cell]), sensor_obstacle_halo=bool(unpack_fine(final)[tuple(5*np.array(cell)+2)]),
        map_lethal=bool(final["lethal"][cell]), map_seen=bool(final["seen"][cell]), map_blocked=bool(blocked[cell]))
    return kind


def fine_at(snapshot, cell):
    fine = snapshot["fine_obstacle"]
    target = np.array(cell)*5+2
    lo, hi = np.maximum(target-5,0), np.minimum(target+6,fine.shape)
    coords = np.argwhere(fine[tuple(slice(a,b) for a,b in zip(lo,hi))])+lo
    d = np.maximum(2*np.abs(coords-target)-1,0)
    return bool((np.sum(d*d,axis=1)<=100).any())


def failure_at(raw, row, ref, prior, truth):
    files = sorted((raw/"diag").glob("plan_fail_*.npz"))
    if not files:
        return {}
    z = load_snapshot(files[-1])
    cell = tuple(z["goal"])
    return dict(failure_snapshot=files[-1].name, failure_t_s=float(z["sim_time"]), goal=list(map(int,cell)),
        goal_blocked=bool(z["lethal"][cell]), goal_seen=bool(z["seen"][cell]), goal_known=bool(z["known"][cell]),
        estimated_steep_halo=bool(inflate(z["steep"],RADIUS)[cell]),
        prior_steep_halo=bool(inflate(prior,RADIUS)[cell]),
        additional_steep_halo=bool(inflate(z["steep"] & ~prior,RADIUS)[cell]),
        true_steep_halo=bool(inflate(truth,RADIUS)[cell]),
        prior_rock_halo=bool(ref["prior_rock"][cell]), detected_obstacle_halo=fine_at(z,cell),
        terrain_slope_at_goal_deg=float(slope_deg(z["elev"])[cell]),
        true_lethal=bool(ref["truth_lethal"][cell]))


def terminal(raw, row, tag, ref, prior, truth, steep, blocked, trace, final):
    main = load(raw/"mission.json")
    logs = sorted((raw/"follower").glob("*/mission.json"))
    assert len(logs) == 1
    follower = load(logs[0])
    events = csv_rows(raw/"safety_events.csv")
    updates = csv_rows(raw/"map_updates.csv")
    final_pose = trace[-1,1:]
    last = csv_rows(raw/"trajectory.csv")[-1]
    stats = load(raw/"sensor_status_multi.json")
    available = [s["last_stamp"] for s in stats.values() if s["last_stamp"] is not None]
    last_pose_window = trace[trace[:,0]>=trace[-1,0]-3]
    tilt = [dict(sim_t=float(e["sim_time"]), **json.loads(e["detail"]))
            for f in (raw/"follower").glob("*/safety_stops.csv") for e in csv_rows(f)
            if e["event"]=="unsafe_tilt"]
    extra = {}
    if row["outcome"] == "stuck":
        snapshots = sorted((raw/"diag").glob("periodic_*.npz"))
        if snapshots:
            z = load_snapshot(snapshots[-1])
            cell = tuple(np.rint(final_pose/RESOLUTION).astype(int))
            near = tuple(slice(max(0,i-2),i+3) for i in cell)
            extra.update(snapshot_s=float(z["sim_time"]), snapshot_cell_blocked=bool(z["lethal"][cell]),
                         snapshot_blocked_5x5=int(z["lethal"][near].sum()))
        before = trace[trace[:,0]>=trace[-1,0]-10][0,1:]
        extra["last_10_s_net_m"] = float(np.linalg.norm(final_pose-before))
    if tag["patch"] == "08OB88_-0167" and tag["condition"] == "P" and tag["rep"] == "1":
        halo = inflate(truth,RADIUS)
        brackets = [(a[0],b[0]) for a,b in zip(trace[:-1],trace[1:])
                    if audit_path([a[1:],b[1:]],halo)["relaxed_length_m"]>1e-9]
        extra.update(first_halo_segment_start_s=brackets[0][0],last_halo_segment_end_s=brackets[-1][1])
    return dict(tag, outcome=row["outcome"], no_path_type=row["no_path_type"],
        online_error=follower.get("online_error",""), mission_end_s=main["finished_t"], last_pose_s=trace[-1,0],
        last_map_stamp_s=max(float(u["stamp"]) for u in updates),
        sensors_last_stamps=json.dumps({k:s["last_stamp"] for k,s in stats.items()},sort_keys=True),
        min_last_sensor_stamp=min(available,default=None),
        last_x_m=final_pose[0], last_y_m=final_pose[1], last_v_m_s=last["v"], last_w_rad_s=last["w"],
        last_3_s_net_m=float(np.linalg.norm(last_pose_window[-1,1:]-last_pose_window[0,1:])),
        last_3_pose_gap_sim_s=float(np.diff(last_pose_window[:,0]).max()),
        current_cell=list(map(int,np.rint(final_pose/RESOLUTION))),
        **map_at(final,ref,prior,truth,steep,blocked,tuple(np.rint(final_pose/RESOLUTION).astype(int))),
        unsafe_tilt_poses=json.dumps([dict(sim_t=e["sim_t"], pitch_deg=np.degrees(e["pose"][4]),
                         roll_deg=np.degrees(e["pose"][3]), x=e["pose"][0], y=e["pose"][1]) for e in tilt]),
        last_safety_events=json.dumps(events[-5:]), stops_detail=row["stops_detail"], **extra)


def main():
    rows = csv_rows(ROOT/"common_eval/runs.csv")
    assert len(rows) == 45
    measurements, goals, failures, terminals = [], [], [], []
    for row in rows:
        raw = Path(row["run"])
        tag = {key:row[key] for key in ("patch","condition","rep")}
        manifest = load(raw.parents[1]/"manifest.json")
        assert manifest.get("terrain_source","sensor") == MODES[row["condition"]]
        assert manifest.get("prior_variant","exact")=="exact" and manifest.get("obstacle_reference_mode","prior")=="prior"
        assert manifest["only_patch"]==row["patch"] and manifest["execution"]=="finished"
        assert manifest["real_time_factor"]==.3 and manifest["online_fixes"]=="v2"
        assert manifest["software_rendering"]=="1" and manifest["diagnostics"]
        assert manifest["map_method"]=="fine" and manifest["ground_estimate"]=="non_obstacle"
        assert manifest["sensors"]=="lidar_real+depth2"
        assert manifest.get("obstacle_clearance","centre")=="centre" and manifest.get("tracking","default")=="default"
        with np.load(raw/"evaluation_reference.npz") as ref, np.load(raw/"pointcloud_map.npz") as final:
            metrics, prior, truth, steep, blocked, trace, revisions = terrain_metrics(raw,row,ref,final)
            measurements.append(dict(tag,**metrics))
            failure = failure_at(raw,row,ref,prior,truth)
            if row["outcome"]=="no_path":
                failures.append(dict(tag, failure_type=row["no_path_type"], **failure))
            if row["patch"]=="08OB88_-0167":
                ends = sum(np.array_equal(np.rint(path[-1]/RESOLUTION),GOAL_0167) for path in revisions)
                goals.append(dict(tag, outcome=row["outcome"], reached=row["goals_reached"],
                    published_paths_to_goal=ends,
                    **{"final_"+k:v for k,v in map_at(final,ref,prior,truth,steep,blocked,GOAL_0167).items()},
                    **failure))
            if row["outcome"]!="completed" or int(row["ev_unsafe_tilt"]):
                terminals.append(terminal(raw,row,tag,ref,prior,truth,steep,blocked,trace,final))
    for name, data in (("terrain_runs.csv",measurements),("0167_goals.csv",goals),
                       ("no_path_evidence.csv",failures),("terminal_evidence.csv",terminals)):
        write(name,data)
        print(name,len(data))


if __name__ == "__main__":
    main()
