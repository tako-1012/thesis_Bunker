"""Compare two recorded Gazebo LiDAR runs of the same beach (read-only on both run folders).

Usage: python3 -m experiments.run_divergence RUN_A RUN_B [--label-a A --label-b B]
where each RUN is a raw run folder (`.../raw/<patch>`) holding mission.json, trajectory.csv,
map_updates.csv, replans.csv, plans.csv, first_cloud.npz and, when the run closed cleanly,
pointcloud_map.npz.  The parent manifest.json (two levels up) is used for settings.

Reports, without changing any file:
  * inputs/settings: scenario stops/start/signatures, map method, real_time_factor, stale timeout,
    LiDAR spec, Gazebo version, evaluation-reference hash;
  * start: started_t, start pose, first cloud stamp; whether the first clouds share geometry
    and differ only by range noise (independent noise draws -> std ~ sqrt(2) * sigma);
  * sensing/mapping: map-update counts, cloud-interval stats (sim time), queue drops, any shared cloud hashes;
  * trajectories: same-elapsed-time distance (max, first time > 0.5 m) versus shape distance
    (nearest-point distance between the two traces, max and p95) -- a large same-time distance with a
    small shape distance means the same route at different times;
  * outcome: status, goals reached, elapsed, replans; for a failed run, the state at the end
    (time, position, leg, last plan results, lethal cells within 1 m of the robot and of the current goal).
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

RES = 0.5


def load(run):
    run = Path(run)
    manifest_path = run.parent.parent / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    mission = json.loads((run / "mission.json").read_text())
    traj = pd.read_csv(run / "trajectory.csv")
    t0 = mission.get("started_t", traj.t.iloc[0])
    traj = traj[traj.t >= t0].copy()
    traj["s"] = traj.t - t0
    out = dict(run=run, manifest=manifest, mission=mission, traj=traj, t0=t0)
    for name in ["map_updates", "replans", "plans"]:
        f = run / f"{name}.csv"
        out[name] = pd.read_csv(f) if f.exists() else pd.DataFrame()
    out["first_cloud"] = np.load(run / "first_cloud.npz") if (run / "first_cloud.npz").exists() else None
    out["map"] = np.load(run / "pointcloud_map.npz") if (run / "pointcloud_map.npz").exists() else None
    ref = run / "evaluation_reference.npz"
    out["ref_sha"] = hashlib.sha256(ref.read_bytes()).hexdigest()[:16] if ref.exists() else None
    patch = run.name
    out["scenario"] = next((s for s in manifest.get("scenarios", []) if s.get("patch") == patch), {})
    return out


def settings(r):
    m = r["manifest"]
    sc = r["scenario"]
    return dict(map_method=m.get("map_method", "coarse"), real_time_factor=m.get("real_time_factor"),
                stale_timeout_s=m.get("stale_timeout_s"), protocol=m.get("protocol"),
                gazebo=str(m.get("environment", {}).get("gazebo", ""))[:12],
                image=m.get("environment", {}).get("image"), lidar_spec=json.dumps(m.get("lidar_spec"), sort_keys=True),
                start=json.dumps(sc.get("start")), stops=json.dumps(sc.get("stops")),
                truth_signature=json.dumps(sc.get("truth_signature"), sort_keys=True),
                prior_signature=json.dumps(sc.get("prior_signature"), sort_keys=True), evaluation_reference=r["ref_sha"])


def first_cloud(a, b):
    fa, fb = a["first_cloud"], b["first_cloud"]
    if fa is None or fb is None:
        return "first_cloud.npz missing"
    text = f"stamp A {float(fa['stamp']):.3f} B {float(fb['stamp']):.3f}; pose diff max {np.abs(fa['pose'] - fb['pose']).max():.4f}"
    if abs(float(fa["stamp"]) - float(fb["stamp"])) > 1e-6:
        return text + "; different scan times, so the clouds are not compared"
    pa, pb = fa["points"], fb["points"]
    if pa.shape != pb.shape:
        return text + f"; shapes differ {pa.shape} {pb.shape}"
    ra, rb = np.linalg.norm(pa, axis=1), np.linalg.norm(pb, axis=1)
    ok = np.isfinite(ra) & np.isfinite(rb) & (ra < 29) & (rb < 29)
    if not ok.any():
        return text + "; no comparable returns"
    d = ra[ok] - rb[ok]
    direction = np.abs(pa[ok] / ra[ok, None] - pb[ok] / rb[ok, None]).max()
    return (text + f"; identical={np.array_equal(pa, pb)}; ray-direction max diff {direction:.1e}; "
            f"range diff mean {d.mean():.4f} std {d.std():.4f} m (n={ok.sum()})")


def sensing(r):
    u = r["map_updates"]
    if u.empty:
        return dict(updates=0)
    gaps = np.diff(u.stamp.values)
    return dict(updates=len(u), failed=int((u.status != "ok").sum()), first_stamp=round(float(u.stamp.iloc[0]), 3),
                gap_median=round(float(np.median(gaps)), 3) if len(gaps) else None,
                gap_max=round(float(gaps.max()), 3) if len(gaps) else None,
                queue_drops=int(u.queue_drops.iloc[-1]), update_s_median=round(float(u.update_s.median()), 3),
                update_s_max=round(float(u.update_s.max()), 3))


def trajectories(a, b):
    ta, tb = a["traj"], b["traj"]
    end = min(ta.s.max(), tb.s.max())
    grid = np.arange(0, end, 0.5)
    xa = np.c_[np.interp(grid, ta.s, ta.x), np.interp(grid, ta.s, ta.y)]
    xb = np.c_[np.interp(grid, tb.s, tb.x), np.interp(grid, tb.s, tb.y)]
    same = np.linalg.norm(xa - xb, axis=1)
    # Shape is compared over the common elapsed window only (a longer run would otherwise look different).
    pa, pb = ta.loc[ta.s <= end, ["x", "y"]].values, tb.loc[tb.s <= end, ["x", "y"]].values
    da, db = cKDTree(pb).query(pa)[0], cKDTree(pa).query(pb)[0]
    shape = np.r_[da, db]
    first = float(grid[np.argmax(same > 0.5)]) if (same > 0.5).any() else None
    i = int(np.argmax(same))
    return dict(compared_s=round(float(end), 1), same_time_max=round(float(same.max()), 2),
                same_time_at_s=round(float(grid[i]), 1), first_over_0_5m_s=first,
                shape_max=round(float(shape.max()), 2), shape_p95=round(float(np.percentile(shape, 95)), 2),
                shape_at_same_time_max=round(float(min(cKDTree(pb).query(xa[i])[0], cKDTree(pa).query(xb[i])[0])), 2))


def outcome(r):
    m, t = r["mission"], r["traj"]
    p = r["plans"]
    fails = p[p.success.astype(str) == "False"] if not p.empty else p
    out = dict(status=m.get("status"), elapsed=round(float(t.s.max()), 1), replans=len(r["replans"]), plan_calls=len(p),
               failed_plans=len(fails), end_xy=[round(float(t.x.iloc[-1]), 2), round(float(t.y.iloc[-1]), 2)])
    if r["map"] is not None and out["status"] not in ("completed",):
        lethal = r["map"]["lethal"]
        xy = np.array(out["end_xy"]) / RES
        ii, jj = np.indices(lethal.shape)
        near = (np.hypot(ii - xy[0], jj - xy[1]) <= 1.0 / RES) & lethal
        out["lethal_within_1m_of_robot"] = int(near.sum())
        stops = r["scenario"].get("stops") or []
        leg = int(r["replans"].leg_index.iloc[-1]) if not r["replans"].empty and "leg_index" in r["replans"] else None
        if leg is not None and leg < len(stops):
            g = np.array(stops[leg])
            out["current_goal_cell"] = stops[leg]
            out["goal_cell_lethal"] = bool(lethal[tuple(g)])
            out["lethal_within_1m_of_goal"] = int(((np.hypot(ii - g[0], jj - g[1]) <= 1.0 / RES) & lethal).sum())
        if not p.empty:
            out["last_plans"] = p.tail(3).to_dict("records")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    ap.add_argument("--label-a", default="A")
    ap.add_argument("--label-b", default="B")
    args = ap.parse_args()
    a, b = load(args.run_a), load(args.run_b)
    sa, sb = settings(a), settings(b)
    print(f"== {args.label_a}: {a['run']}\n== {args.label_b}: {b['run']}")
    print("-- inputs/settings (differences only)")
    diff = {k: (sa[k], sb[k]) for k in sa if sa[k] != sb[k]}
    print("   none" if not diff else "\n".join(f"   {k}: {va} | {vb}" for k, (va, vb) in diff.items()))
    print("-- start / first cloud")
    print(f"   started_t A {a['t0']:.3f} B {b['t0']:.3f}; start pose A {a['mission'].get('start_pose')} B {b['mission'].get('start_pose')}")
    print("   " + first_cloud(a, b))
    print("-- sensing / mapping")
    print(f"   A {sensing(a)}\n   B {sensing(b)}")
    shared = set(a["map_updates"].get("cloud_sha256", [])) & set(b["map_updates"].get("cloud_sha256", []))
    print(f"   identical point clouds shared by both runs: {len(shared)}")
    print("-- trajectories (same elapsed time vs shape)")
    print("   " + json.dumps(trajectories(a, b)))
    print("-- outcome")
    print(f"   A {json.dumps(outcome(a), default=str)}\n   B {json.dumps(outcome(b), default=str)}")


if __name__ == "__main__":
    main()
