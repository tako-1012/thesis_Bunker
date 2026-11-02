"""Paired descriptive Gazebo comparisons; six beaches do not support hypothesis tests."""

import argparse
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
    return result,trace


def summarize(folder,output=None):
    folder=Path(folder).resolve();output=Path(output) if output else folder/"report"
    output.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((folder/"manifest.json").read_text())
    cases=manifest["cases"]
    ids=[(c["patch"],c["planner"]) for c in cases]
    if len(cases)!=12 or len(set(ids))!=12 or len({c["patch"] for c in cases})!=6:
        raise ValueError("comparison manifest must contain six distinct beaches x two methods")
    if any({c["planner"] for c in cases if c["patch"]==patch}!={"A*","TA*-S"} for patch,_ in ids):
        raise ValueError("each beach needs A* and TA*-S")
    rows,trajectories=[],{}
    for case in cases:
        row=dict(patch=case["patch"],planner=case["planner"],status="実行失敗" if case.get("error") else "未実行",completed=None,data_source=None,error=case.get("error",""))
        row.update({key:None for key in MEASURES})
        row.update({"map_"+key:case["map_metrics"].get(key) for key in MAP_MEASURES})
        if case.get("run_folder"):
            try:
                measured,trace=analyze_case(folder,case,output/"runs"/case["patch"]/case["planner"].replace("*","star"))
            except (ValueError,OSError,KeyError) as exc:
                row.update(status="記録不完全",error=type(exc).__name__+": "+str(exc))
                rows.append(row)
                continue
            row.update(status=measured["status"],completed=measured["completed"],data_source=measured["data_source"])
            row.update({key:measured[key] for key in MEASURES})
            row.update({"map_"+key:measured["map_"+key] for key in MAP_MEASURES})
            row["roll_p95_recorded_xy_map_deg"]=measured["roll_p95_map_deg"]
            row["pitch_p95_recorded_xy_map_deg"]=measured["pitch_p95_map_deg"]
            trajectories[case["patch"],case["planner"]]=trace
        rows.append(row)
    data=pd.DataFrame(rows);data.to_csv(output/"runs.csv",index=False)
    effects=[]
    for metric in MEASURES:
        values=data.pivot(index="patch",columns="planner",values=metric)
        completed=data.pivot(index="patch",columns="planner",values="completed")
        mask=completed.eq(True).all(axis=1)
        paired=values.loc[mask].dropna()
        delta=paired["TA*-S"]-paired["A*"]
        effects.append(dict(metric=metric,paired_completed=len(paired),delta_median=delta.median()))
    differences=pd.DataFrame(effects);differences.to_csv(output/"paired_differences.csv",index=False)
    for patch in sorted({c["patch"] for c in cases}):
        traces={planner:trajectories[patch,planner] for planner in ["A*","TA*-S"] if (patch,planner) in trajectories}
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
        print("Six beaches x two planners; descriptive trends only, no hypothesis tests.")
        print("Missing physical recordings are 未実行; paired differences use only two completed recordings.")
        print(data.to_string(index=False,float_format=lambda x:f"{x:.6g}"))
        print("\nTA*-S minus A*: paired median differences")
        print(differences.to_string(index=False,float_format=lambda x:f"{x:.6g}"))
        print("Climb sums positive recorded z increments without denoising; it includes physical/logging noise.")
    log=stream.getvalue();(output/"compare_log.txt").write_text(log);print(log,end="")
    return data,differences


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("folder",type=Path);parser.add_argument("--output",type=Path)
    args=parser.parse_args();summarize(args.folder,args.output)
