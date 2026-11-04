"""Paired descriptive Gazebo comparisons; six beaches do not support hypothesis tests."""

import argparse
import csv
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments.gz_run_report import analyze_run
from tapp.mapfile import load_map_file
from tapp.config import RESOLUTION
from tapp.metrics import evaluate

MEASURES=["elapsed_s","deviation_mean_m","deviation_max_m","path_lethal_cells",
          "roll_p95_actual_deg","pitch_p95_actual_deg","roll_max_actual_deg","pitch_max_actual_deg","climb_actual_m"]
MAP_MEASURES=["length_xy","climb","mean_cost","p95_slope","p95_roll","max_roll","max_pitch_dir"]
ROLLOVER_FIELDS=["recorded_status","rolled_over","rollover_t_s","rollover_elapsed_s","rollover_x_m","rollover_y_m"]


def rollover_details(trace):
    """First recorded sample strictly beyond 90 degrees; times are simulator seconds."""
    hits=np.flatnonzero(np.abs(trace.roll.to_numpy())>np.pi/2)
    out=dict(rolled_over=bool(len(hits)),rollover_t_s=None,rollover_elapsed_s=None,
             rollover_x_m=None,rollover_y_m=None)
    if len(hits):
        row=trace.iloc[int(hits[0])]
        out.update(rollover_t_s=float(row.t),rollover_elapsed_s=float(row.t-trace.t.iloc[0]),
                   rollover_x_m=float(row.x),rollover_y_m=float(row.y))
    return out


def mark_rollover(result,trace):
    """Classify the aggregate only; the original mission status remains untouched."""
    out=dict(result,recorded_status=result["status"],**rollover_details(trace))
    if out["rolled_over"]:
        out.update(status="rollover",completed=False)
    return out


def analyze_case(folder,case,output):
    """Resolve portable map paths in a temporary view; never rewrite a raw recording."""
    folder=Path(folder);record=folder/case["run_folder"]
    mission=json.loads((record/"mission.json").read_text())
    map_file=folder/case["map_file"]
    with tempfile.TemporaryDirectory(prefix="gz-compare-analysis-") as tmp:
        tmp=Path(tmp)
        (tmp/"trajectory.csv").symlink_to((record/"trajectory.csv").resolve())
        mission["map_file"]=str(map_file.resolve())
        (tmp/"mission.json").write_text(json.dumps(mission)+"\n")
        result=analyze_run(tmp,output)
    trace=pd.read_csv(record/"trajectory.csv")
    result.update(roll_max_actual_deg=float(np.max(np.abs(np.degrees(trace.roll)))),
                  pitch_max_actual_deg=float(np.max(np.abs(np.degrees(trace.pitch)))),
                  climb_actual_m=float(np.maximum(np.diff(trace.z.to_numpy()),0).sum()))
    tm=load_map_file(map_file)["tmap"]
    predicted=evaluate(np.asarray(mission["path"])/RESOLUTION,tm)
    result.update({"map_"+key:predicted[key] for key in MAP_MEASURES})
    return mark_rollover(result,trace),trace


def summarize(folder,output=None):
    folder=Path(folder).resolve();output=Path(output) if output else folder/"report"
    output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((folder/"manifest.json").read_text())
    cases=manifest["cases"]
    ids=[(c["patch"],c["planner"]) for c in cases]
    planners=manifest.get("planners",["A*","TA*-S"])
    if not planners or len(set(planners))!=len(planners) or not set(planners)<={"A*","TA*-S","TA*-S+inflate"}:
        raise ValueError("invalid comparison methods")
    if len(cases)!=6*len(planners) or len(set(ids))!=len(cases) or len({c["patch"] for c in cases})!=6:
        raise ValueError("comparison manifest must contain six distinct beaches x selected methods")
    if any({c["planner"] for c in cases if c["patch"]==patch}!=set(planners) for patch,_ in ids):
        raise ValueError("each beach needs the same selected methods")
    rows,trajectories=[],{}
    for case in cases:
        row=dict(patch=case["patch"],planner=case["planner"],status="実行失敗" if case.get("error") else "未実行",completed=None,data_source=None,error=case.get("error",""))
        if case.get("planning_status") in ("blocked_endpoint","no_path"):
            row.update(status=case["planning_status"],completed=False)
        row.update({key:None for key in MEASURES})
        row.update({key:None for key in ROLLOVER_FIELDS})
        row.update({"map_"+key:case["map_metrics"].get(key) for key in MAP_MEASURES})
        if case.get("run_folder"):
            try:
                measured,trace=analyze_case(folder,case,output/"runs"/case["patch"]/case["planner"].replace("*","star"))
            except (ValueError,OSError,KeyError) as exc:
                row.update(status="記録不完全",error=type(exc).__name__+": "+str(exc))
                rows.append(row)
                continue
            row.update(status=measured["status"],completed=measured["completed"],data_source=measured["data_source"])
            row.update({key:measured[key] for key in ROLLOVER_FIELDS})
            row.update({key:measured[key] for key in MEASURES})
            row.update({"map_"+key:measured["map_"+key] for key in MAP_MEASURES})
            row["roll_p95_recorded_xy_map_deg"]=measured["roll_p95_map_deg"]
            row["pitch_p95_recorded_xy_map_deg"]=measured["pitch_p95_map_deg"]
            trajectories[case["patch"],case["planner"]]=trace
        rows.append(row)
    data=pd.DataFrame(rows);data.to_csv(output/"runs.csv",index=False)
    effects=[]
    legacy=set(planners)=={"A*","TA*-S"}
    comparisons=[("TA*-S","A*"),("TA*-S+inflate","A*"),("TA*-S+inflate","TA*-S")]
    for method,reference in comparisons:
        if not {method,reference}<=set(planners):continue
        for metric in MEASURES:
            values=data.pivot(index="patch",columns="planner",values=metric)[[method,reference]]
            completed=data.pivot(index="patch",columns="planner",values="completed")[[method,reference]]
            paired=values.loc[completed.eq(True).all(axis=1)].dropna()
            delta=paired[method]-paired[reference]
            effect=dict(metric=metric,paired_completed=len(paired),delta_median=delta.median())
            if not legacy:effect.update(method=method,reference=reference)
            effects.append(effect)
    columns=["metric","paired_completed","delta_median"]+(["method","reference"] if not legacy and len(planners)>1 else [])
    differences=pd.DataFrame(effects,columns=columns);differences.to_csv(output/"paired_differences.csv",index=False)
    for patch in sorted({c["patch"] for c in cases}):
        traces={planner:trajectories[patch,planner] for planner in planners if (patch,planner) in trajectories}
        if not traces:continue
        case=next(c for c in cases if c["patch"]==patch)
        tm=load_map_file(folder/case["map_file"])["tmap"]
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        axes[0].imshow(tm.elev.T,origin="lower",extent=[-.25,(tm.shape[0]-.5)*RESOLUTION,-.25,(tm.shape[1]-.5)*RESOLUTION],cmap="terrain")
        for planner,trace in traces.items():
            axes[0].plot(trace.x,trace.y,label=planner)
            axes[1].plot(trace.t-trace.t.iloc[0],np.degrees(trace.roll),label=planner)
        axes[0].set(xlabel="x [m]",ylabel="y [m]",aspect="equal")
        axes[1].set(xlabel="Time [s]",ylabel="Recorded roll [deg]")
        for ax in axes:ax.legend()
        fig.suptitle(patch);fig.tight_layout();fig.savefig(output/(patch+".png"),dpi=130);plt.close(fig)
    stream=io.StringIO()
    with redirect_stdout(stream):
        print("Six beaches x "+str(len(planners))+" planners; descriptive trends only, no hypothesis tests.")
        print("Missing physical recordings are 未実行; paired differences use only two completed recordings.")
        print(data.to_string(index=False,float_format=lambda x:f"{x:.6g}"))
        print("\nTA*-S minus A*: paired median differences" if legacy else "\nPaired median differences: method minus reference (only each pair completed)")
        print(differences.to_string(index=False,float_format=lambda x:f"{x:.6g}"))
        print("Climb sums positive recorded z increments without denoising; it includes physical/logging noise.")
    log=stream.getvalue();(output/"compare_log.txt").write_text(log);print(log,end="")
    return data,differences


def annotate_existing(folder):
    """Add rollover columns without recalculating any archived numeric measurement.

    csv preserves the exact text of existing values. Only runs.csv and the printed
    comparison table change; raw recordings, per-run reports and figures do not.
    """
    folder=Path(folder).resolve();output=folder/"report"
    with (output/"runs.csv").open() as stream:
        reader=csv.DictReader(stream);fields=list(reader.fieldnames);rows=list(reader)
    manifest=json.loads((folder/"manifest.json").read_text())
    cases={(c["patch"],c["planner"]):c for c in manifest["cases"]}
    for row in rows:
        case=cases[row["patch"],row["planner"]]
        if not case.get("run_folder"):
            continue
        record=folder/case["run_folder"]
        mission=json.loads((record/"mission.json").read_text())
        trace=pd.read_csv(record/"trajectory.csv",float_precision="round_trip")
        row.update(recorded_status=mission["status"],**rollover_details(trace))
        if row["rolled_over"]:
            row.update(status="rollover",completed="False")
    with (output/"runs.csv").open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields+[f for f in ROLLOVER_FIELDS if f not in fields],lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    data=pd.read_csv(output/"runs.csv",float_precision="round_trip")
    effects=pd.read_csv(output/"paired_differences.csv",float_precision="round_trip")
    lines=["Six beaches x two planners; descriptive trends only, no hypothesis tests.",
           "rollover: first recorded |roll| > 90 deg; recorded_status preserves the original mission status.",
           data.to_string(index=False,float_format=lambda x:f"{x:.6g}"),
           "\nTA*-S minus A*: paired median differences (both completed, without rollover)",
           effects.to_string(index=False,float_format=lambda x:f"{x:.6g}"),
           "Climb sums positive recorded z increments without denoising; it includes physical/logging noise."]
    log="\n".join(lines)+"\n";(output/"compare_log.txt").write_text(log);print(log,end="")
    return data,effects


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("folder",type=Path);parser.add_argument("--output",type=Path)
    parser.add_argument("--annotate-existing",action="store_true")
    args=parser.parse_args()
    if args.annotate_existing:annotate_existing(args.folder)
    else:summarize(args.folder,args.output)
