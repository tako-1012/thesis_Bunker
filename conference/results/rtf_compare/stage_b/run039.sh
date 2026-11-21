#!/usr/bin/env bash
# Task 039 B: run paired rates sequentially with the historical passive probe.
set -euo pipefail
cd "$(dirname "$0")/../../.."
root="$PWD/results/rtf_compare/stage_b"
py="$HOME/.venvs/thesis-python/bin/python"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 OPENBLAS_NUM_THREADS=1
while tmux has-session -t =tests039 2>/dev/null; do sleep 3; done
test -s "$root/tests/finished.txt"
count=$(find tests -maxdepth 1 -name 'test_*.py' | wc -l)
awk -v n="$count" '$2 != 0 {bad++} END {exit !(NR == n && !bad)}' "$root/tests/summary.txt"
"$py" -m pip check
while IFS= read -r pin; do
  grep -Fxi -- "$pin" "$root/tests/pip_freeze.txt"
done < <(awk '/^[[:alnum:]]+==/' requirements-venv.txt)
test "$(git branch --show-current)" = claude/039-rtf-compare
test -z "$(git status --short -uno)"
commit=$(git rev-parse HEAD)
image=$(docker image inspect thesis/jazzy-gz:1 --format '{{.Id}}')
exec 9>"$root/run.lock"
flock -n 9
nvidia-smi > "$root/gpu.txt"
probe=/conference/results/rtf_check/hayashi_rtf_repeat/probe.py
domain=64
for patch in 08OB86_-0205 08OB88_-1417 08OB88_-0167 08OB88_00332 08OB89_-0847; do
  for rep in 1 2 3; do
    for factor in 0.3 1.0; do
      run="$root/runs/$patch/${factor}_r$rep"
      test ! -e "$run"
      test -z "$(docker ps -q)"
      if pgrep -f '[g]z sim' || pgrep -x ruby; then exit 2; fi
      mkdir -p "$run"
      args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v2
            --sensors lidar_real+depth2 --diagnostics --real-time-factor "$factor")
      {
        echo "started=$(date -Is) commit=$commit tracked_changes=0"
        echo "image=$image patch=$patch rep=$rep domain=$domain rendering=software stale_sim_s=1.0"
        printf 'args=%s\n' "${args[*]}"
      } > "$run/run_conditions.txt"
      echo "$(date -Is) START $patch $factor $rep"
      THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID="$domain" \
        THESIS_SOFTWARE_RENDERING=1 THESIS_STALE_TIMEOUT_S=1.0 THESIS_ROS_IMAGE=thesis/jazzy-gz:1 \
        bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
        > "$run/console_log.txt" 2>&1 &
      runner=$!
      probe_pid=
      # The unchanged runner owns the container; attach only to its exact output mount.
      while kill -0 "$runner" 2>/dev/null; do
        id=$(docker ps -q --filter ancestor=thesis/jazzy-gz:1)
        if [[ "$id" =~ ^[0-9a-f]+$ ]] && [[ "$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/output"}}{{.Source}}{{end}}{{end}}' "$id")" == "$run/physical_1" ]]; then
          docker exec --user "$(id -u):$(id -g)" "$id" bash -c \
            'source /opt/ros/jazzy/setup.bash && exec python3 "$1" /output/probe.csv' bash "$probe" \
            > "$run/probe_log.txt" 2>&1 &
          probe_pid=$!
          break
        fi
        sleep 0.2
      done
      rc=0
      wait "$runner" || rc=$?
      if [[ -n "$probe_pid" ]]; then wait "$probe_pid" || true; fi
      echo "$rc" > "$run/exit.txt"
      echo "$(date -Is) END $patch $factor $rep exit=$rc bytes=$(du -sb "$run" | cut -f1)"
    done
  done
done
"$py" - "$root" <<'PY' | tee "$root/summary_log.txt"
"""Summarize task 039 from the unchanged Gazebo runner and 2026-11-07 probe."""
import csv
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

from experiments.eval_ground_endpoint_report import contacts
from experiments.eval_035_report import safety_events
from experiments.gz_online_batch_report import analyze_record
from ros2_jazzy.gz_checks.online_batch_runtime import read_csv_parts

root = Path(sys.argv[1])
rows, sources = [], []


def read_json(path):
    return json.loads(path.read_text())


def trial(run, row):
    out = run / "physical_1"
    manifest = read_json(out / "manifest.json")
    case, = [c for c in manifest["cases"] if c["selected"]]
    assert case["patch"] == row["patch"] == manifest["only_patch"]
    assert manifest["real_time_factor"] == row["factor"]
    assert manifest["online_fixes"] == "v2" and manifest["sensors"] == "lidar_real+depth2"
    assert manifest["map_method"] == "fine" and manifest["ground_estimate"] == "non_obstacle"
    assert manifest["diagnostics"] and manifest["software_rendering"] == "1"
    row.update(execution=manifest["execution"], termination=case["termination"], error=case["error"])
    if not case["run_folder"]:
        raise ValueError("no run folder in manifest")
    raw = out / case["run_folder"]
    mission = read_json(raw / "mission.json")
    row.update(online_error=mission.get("online_error") or (mission.get("final_state") or {}).get("online_error"))
    try:
        with np.load(raw / "evaluation_reference.npz") as ref:
            shape = ref["truth_lethal"].shape
            truth = dict(tmap=SimpleNamespace(rock=ref["truth_rock"], lethal=ref["truth_lethal"], shape=shape))
            prior = dict(tmap=SimpleNamespace(rock=ref["prior_rock"]))
        meta = next(m for m in manifest["scenarios"] if m["patch"] == row["patch"])
        measured, trace = analyze_record(raw, meta, truth, prior)
        xy = trace[["x", "y"]].to_numpy()
        events = safety_events(raw)
        row.update(status=measured["status"], goals_reached=measured["goals_reached"],
                   truth_lethal_m=contacts(xy, truth["tmap"].lethal)[0],
                   debris_m=contacts(xy, truth["tmap"].rock & ~prior["tmap"].rock)[0],
                   **{k: sum(e["event"] == k for e in events)
                      for k in ("unsafe_tilt", "unsafe_tilt_repeat", "off_path")})
        if row["unsafe_tilt_repeat"] and row["status"] != "rollover":
            row["status"] = "unsafe_tilt_repeat"
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row["outcome_record_error"] = repr(exc)

    t0, t1 = mission["started_t"], mission["finished_t"]
    wall = float(mission["wall_elapsed_s"])
    ratio = (float(t1) - float(t0)) / wall
    row.update(sim_s=t1-t0, wall_s=wall, measured_rtf=ratio)
    if not np.isfinite(ratio) or ratio <= 0:
        raise ValueError("invalid timing")
    updates = pd.DataFrame(u for u in read_csv_parts(raw / "map_updates.csv")
                           if t0 <= float(u["stamp"]) <= t1)
    durations = pd.to_numeric(updates.update_s, errors="coerce")
    period = .1 / ratio  # same measured-RTF denominator as the 2026-11-07 report
    row.update(map_errors=int(updates.status.ne("ok").sum()),
               updates=len(updates), update_period_wall_s=period,
               over_period_share=float((durations.dropna() > period).mean()),
               over_target_period_share=float((durations.dropna() > .1 / row["factor"]).mean()))
    status = read_json(raw / "sensor_status_multi.json")
    row["queue_drops"] = sum(d["queue_drops"] for d in status.values())
    row["queue_drops_last_update"] = int(updates.queue_drops.iloc[-1])
    for name, group in updates.assign(duration=durations).groupby("sensor"):
        u = group.duration.dropna()
        sources.append(dict(patch=row["patch"], factor=row["factor"], rep=row["rep"], sensor=name,
                            updates=len(u), errors=int(group.status.ne("ok").sum()),
                            queue_drops=status[name]["queue_drops"], median_s=u.median(),
                            p95_s=u.quantile(.95), max_s=u.max(), over_period_share=(u > period).mean()))
    with (out / "probe.csv").open() as stream:
        probe_rows = [p for p in csv.DictReader(stream) if p["status"] == "running" and p["sim_t"]]
    if len(probe_rows) < 3:
        raise ValueError("insufficient running probe samples")
    sim = np.array([float(p["sim_t"]) for p in probe_rows])
    real = np.array([float(p["wall_s"]) for p in probe_rows])
    age = [float(p["cloud_age_sim_s"]) for p in probe_rows if p["cloud_age_sim_s"]]
    row.update(probe_samples=len(probe_rows), probe_start_offset_sim_s=sim[0]-t0,
               probe_end_offset_sim_s=t1-sim[-1], probe_rtf=(sim[-1]-sim[0])/(real[-1]-real[0]),
               cloud_age_max_sim_s=max(age), cloud_age_p95_sim_s=np.percentile(age, 95),
               cmd_vel_hz_sim=sum(int(p["cmd_count"]) for p in probe_rows)/(sim[-1]-sim[0]),
               cmd_vel_hz_sim_aligned=sum(int(p["cmd_count"]) for p in probe_rows[1:])/(sim[-1]-sim[0]),
               cmd_vel_hz_wall=sum(int(p["cmd_count"]) for p in probe_rows)/(real[-1]-real[0]),
               cmd_gap_max_sim_s=max(float(p["cmd_gap_max_sim_s"]) for p in probe_rows),
               cmd_gap_max_wall_s=max(float(p["cmd_gap_max_wall_s"]) for p in probe_rows))


for run in sorted(root.glob("runs/*/*")):
    factor, rep = run.name.split("_r")
    row = dict(patch=run.parent.name, factor=float(factor), rep=int(rep),
               exit_code=int((run/"exit.txt").read_text()))
    try:
        trial(run, row)
    except (OSError, ValueError, KeyError, AttributeError, TypeError, ZeroDivisionError, AssertionError, StopIteration) as exc:
        row["measurement_error"] = repr(exc)
    rows.append(row)

result = pd.DataFrame(rows)
for col in ("measured_rtf", "map_errors", "queue_drops", "over_period_share",
            "cmd_vel_hz_sim", "cloud_age_max_sim_s"):
    if col not in result:
        result[col] = np.nan
result["valid"] = (result.measured_rtf.sub(result.factor).abs() <= result.factor*.01) & result.map_errors.eq(0)
slow = result[result.factor.eq(.3)].set_index(["patch", "rep"]).queue_drops
result["paired_03_drops"] = [slow.get((r.patch, r.rep), np.nan) for r in result.itertuples()]
result["keeps_up"] = (result.factor.eq(1) & result.valid
                      & result.queue_drops.le(result.paired_03_drops)
                      & result.over_period_share.le(.01) & result.cmd_vel_hz_sim.ge(19)
                      & result.cloud_age_max_sim_s.lt(1))
result.to_csv(root / "runs.csv", index=False)
pd.DataFrame(sources).to_csv(root / "sensor_updates.csv", index=False)
print("走行と安全性")
cols = ["patch", "factor", "rep", "exit_code", "status", "goals_reached", "truth_lethal_m",
        "debris_m", "unsafe_tilt", "off_path", "unsafe_tilt_repeat"]
print(result.reindex(columns=cols).to_string(index=False))
if "status" not in result:
    result["status"] = "unknown"
outcomes = result.groupby(["patch", "factor"]).status.value_counts(dropna=False).unstack(fill_value=0)
outcomes.to_csv(root / "outcomes.csv")
cols = ["measured_rtf", "map_errors", "queue_drops", "over_period_share", "cmd_vel_hz_sim",
        "cloud_age_max_sim_s", "truth_lethal_m", "debris_m", "unsafe_tilt", "off_path", "unsafe_tilt_repeat"]
grouped = result.reindex(columns=["patch", "factor", *cols]).groupby(["patch", "factor"])[cols].agg(["count", "min", "median", "max"])
grouped.to_csv(root / "grouped.csv")
print(outcomes.to_string())
print("倍率と処理の判定")
print(result[["patch", "factor", "rep", "valid", "keeps_up", *cols[:6], "paired_03_drops"]].to_string(index=False))
print("有効な回", result.groupby("factor").valid.sum().to_dict())
print("1.0 倍で追いついた回", int(result.keeps_up.sum()), "/ 15")
print("走行記録", len(result), "/ 30")
PY
date -Is > "$root/finished.txt"
