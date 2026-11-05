"""Select dead-end safeguards on validation beaches, then freeze and evaluate test tours."""

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from multiprocessing import Pool
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from experiments.online_mission import scenarios, table
from experiments.beach_terrain import metrics
from tapp.config import RESOLUTION
from tapp.collision import path_lethal_cells
from tapp.real_beach import list_patches, build_real
from tapp.prior import PriorMap, coarse_prior, coarse_elevation
from tapp.traversability import TraversabilityMap
from tapp.online_mission import ordered_tour, run_online_mission
from tapp.online_deadend import run_deadend_mission

OUT = ROOT / "results/online_deadend"
KEY = ["patch", "prior", "radius_m"]
RADII_A = (3.0, 6.0, 10.0)
FACTORS_A = (2.0, 4.0, 8.0)
THRESHOLDS_B = (10, 30, 60)


def source_hashes():
    paths = ["tapp/online_deadend.py", "tapp/online_mission.py", "tapp/real_beach.py", "data/shizuoka_beach_las/index.json"]
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


def variants(selection):
    a, b = selection["A"], selection["B"]
    return {"baseline": {}, "A": a, "B": b, "A+B": dict(a, **b)}


def run_patch(job):
    row, configs, radii = job
    clean, stale, points = scenarios(row)
    coarse = coarse_prior(clean["tmap"], 10)
    coarse_tm = TraversabilityMap(coarse_elevation(clean["tmap"], 10),
                                 np.zeros(clean["tmap"].shape, bool),
                                 clean["tmap"].robot, clean["tmap"].weights)
    references = {}
    for name, sc in [("clean", clean), ("stale", stale)]:
        tm = sc["tmap"]
        tour = ordered_tour(tm, sc["start"], points[name])
        result = run_online_mission(tm, PriorMap(tm.cost, tm.lethal, RESOLUTION),
                                    sc["start"], tour["stops"], radius_m=10, prior_lethal_mode="hard")
        if not result["success"]:
            raise RuntimeError("full-truth oracle failed: " + row["name"])
        references[name] = metrics(result["traj"], tm)["J"]
    rows, times, traces = [], [], {}
    for prior_name in ("coarse c10", "stale"):
        sc = stale if prior_name == "stale" else clean
        truth = sc["tmap"]
        prior_tm = clean["tmap"] if prior_name == "stale" else coarse_tm
        prior = PriorMap(prior_tm.cost, prior_tm.lethal, RESOLUTION) if prior_name == "stale" else coarse
        tour = ordered_tour(prior_tm, sc["start"], points["stale" if prior_name == "stale" else "clean"])
        oracle = references["stale" if prior_name == "stale" else "clean"]
        for radius in radii:
            for method, config in configs.items():
                if method == "baseline":
                    result = run_online_mission(truth, prior, sc["start"], tour["stops"], radius_m=radius)
                else:
                    result = run_deadend_mission(truth, prior, sc["start"], tour["stops"], radius_m=radius, **config)
                key = dict(patch=row["name"], split=row["split"], side_m=200, seed=0,
                           prior=prior_name, radius_m=radius, method=method)
                out = dict(key, success=result["success"], reason=result["reason"],
                           n_plans=result["n_plans"], n_replans=result["n_replans"],
                           lethal_cells=len(path_lethal_cells(result["traj"], truth.lethal)),
                           debris_cells=len(path_lethal_cells(result["traj"], truth.rock & ~clean["tmap"].rock)),
                           oracle_J=oracle, order=json.dumps(tour["order"]),
                           memory_events=result.get("memory_events", 0), hard_switches=result.get("hard_switches", 0))
                if result["success"]:
                    m = metrics(result["traj"], truth)
                    out.update(J=m["J"], dJ=100*(m["J"]/oracle-1), length_xy=m["length_xy"])
                rows.append(out)
                times.extend(dict(key, call=i, seconds=t) for i,t in enumerate(result["plan_times"]))
                trace_key = f'{prior_name.replace(" ", "_")}_R{radius}_{method}'
                traces[trace_key] = np.asarray(result["traj"], float)
    return row["name"], rows, times, traces


def execute(split, configs, radii, output, workers):
    rows = list_patches(split, dataset="shizuoka_beach_las")
    output.mkdir(parents=True, exist_ok=True)
    (output / "traces").mkdir(exist_ok=True)
    records, timings = [], []
    began = time.perf_counter()
    with Pool(workers) as pool:
        for i, (name, data, plans, traces) in enumerate(pool.imap(run_patch, [(r,configs,radii) for r in rows]), 1):
            records.extend(data)
            timings.extend(plans)
            np.savez_compressed(output / "traces" / (name+".npz"), **traces)
            print(f'{split}: {i}/{len(rows)} {name} ({time.perf_counter()-began:.1f}s)', file=sys.stderr, flush=True)
    data, plans = pd.DataFrame(records), pd.DataFrame(timings)
    data.to_csv(output / "missions.csv", index=False)
    for (method, prior), group in plans.groupby(["method", "prior"]):
        group.to_csv(output / f'plan_times_{method.replace("+", "plus")}_{prior.replace(" ", "_")}.csv', index=False)
    (output / "runtime.json").write_text(json.dumps(dict(wall_s=time.perf_counter()-began, workers=workers), indent=2)+"\n")
    return data, plans


def select_parameters(output, workers, reuse=False):
    configs = {"baseline": {}}
    configs.update({f"A_r{r:g}_k{k:g}": dict(r_A=r, k_A=k) for r in RADII_A for k in FACTORS_A})
    configs.update({f"B_N{n}": dict(N_B=n) for n in THRESHOLDS_B})
    # Both priors at R10: a fixed validation design, chosen before any test run.
    if reuse:
        previous=json.loads((output/"selection.json").read_text())
        if previous["source_sha256"] != source_hashes() or previous["candidates"] != configs:
            raise ValueError("saved validation does not match the current planner/candidates")
        data=pd.read_csv(output/"validation/missions.csv",float_precision="round_trip")
        if set(data.split)!={"validation"} or set(data.method)!=set(configs):
            raise ValueError("reuse accepts only the complete validation sweep")
    else:
        data, _ = execute("validation", configs, [10], output / "validation", workers)
    baseline = data[data.method == "baseline"][KEY+["success", "dJ"]]
    scores = []
    for method, group in data[data.method != "baseline"].groupby("method"):
        paired = group.merge(baseline, on=KEY, validate="one_to_one", suffixes=("", "_base"))
        delta = paired.loc[paired.success & paired.success_base, "dJ"] - paired.loc[paired.success & paired.success_base, "dJ_base"]
        scores.append(dict(method=method, runs=len(group), touching=int((group.lethal_cells>0).sum()),
                           failed=int((~group.success).sum()), too_long=int(group.reason.eq("too_long").sum()),
                           baseline_completed_lost=int((paired.success_base & ~paired.success).sum()),
                           positive_delta_median=float(np.maximum(delta,0).median()) if len(delta) else np.inf,
                           delta_median=float(delta.median()) if len(delta) else np.inf,
                           positive_delta_mean=float(np.maximum(delta,0).mean()) if len(delta) else np.inf,
                           delta_mean=float(delta.mean()) if len(delta) else np.inf))
    frame = pd.DataFrame(scores)
    ranking = ["touching", "failed", "baseline_completed_lost", "too_long", "positive_delta_mean", "delta_mean", "method"]
    chosen = {}
    for family in ("A", "B"):
        best = frame[frame.method.str.startswith(family+"_")].sort_values(ranking).iloc[0].method
        chosen[family] = configs[best]
        chosen[family+"_candidate"] = best
    chosen.update(validation_patches=[r["name"] for r in list_patches("validation", dataset="shizuoka_beach_las")],
                  validation_radii=[10], candidates=configs, ranking=ranking, source_sha256=source_hashes(), test_data_used=False)
    frame.to_csv(output / "validation_scores.csv", index=False)
    # This file is written before execute('test', ...); timings never enter selection.
    (output / "selection.json").write_text(json.dumps(chosen, indent=2, allow_nan=False)+"\n")
    table("Validation-only parameter selection: both priors, R10; lower lexicographic score wins", frame)
    return chosen


def paired_results(data):
    base = data[data.method == "baseline"][KEY+["success", "reason", "dJ", "lethal_cells"]]
    paired = data[data.method != "baseline"].merge(base, on=KEY, validate="many_to_one", suffixes=("", "_baseline"))
    paired["paired_success"] = paired.success & paired.success_baseline
    paired["dJ_delta"] = np.where(paired.paired_success, paired.dJ-paired.dJ_baseline, np.nan)
    return paired


def audit_baseline(data, output):
    old = pd.read_csv(ROOT / "results/online_mission/missions.csv", float_precision="round_trip")
    old = old[(old["mode"] == "online") & old.prior.isin(["stale", "coarse c10"])]
    new = data[data.method == "baseline"]
    paired = new.merge(old, on=KEY, how="outer", validate="one_to_one", suffixes=("", "_014"), indicator=True)
    if not paired._merge.eq("both").all():
        raise AssertionError("baseline scenario identities differ from task 014")
    checks = []
    for col in ["success", "n_plans", "n_replans", "lethal_cells", "debris_cells", "order"]:
        same = paired[col].eq(paired[col+"_014"])
        checks.append(dict(field=col, matching=int(same.sum()), runs=len(same)))
        if not same.all():
            raise AssertionError("task-014 baseline differs: "+col)
    for col in ["oracle_J", "J", "dJ", "length_xy"]:
        a,b=paired[col].to_numpy(float),paired[col+"_014"].to_numpy(float)
        checks.append(dict(field=col, max_abs_difference=float(np.nanmax(np.abs(a-b)))))
        if not np.allclose(a,b,atol=1e-10,rtol=1e-12,equal_nan=True):
            raise AssertionError("task-014 baseline differs: "+col)
    audit = pd.DataFrame(checks)
    audit.to_csv(output / "baseline_014_audit.csv", index=False)
    table("Unchanged baseline vs task 014 (wall timings are newly measured)", audit)
    return old


def summarize(data, timings, output):
    summary = []
    for (prior,radius,method), g in data.groupby(["prior","radius_m","method"], sort=False):
        times = timings[(timings.prior==prior)&(timings.radius_m==radius)&(timings.method==method)].seconds
        ok = g[g.success]
        summary.append(dict(prior=prior,radius_m=radius,method=method,runs=len(g),completed=int(g.success.sum()),
                            too_long=int(g.reason.eq("too_long").sum()),touching=int((g.lethal_cells>0).sum()),
                            dJ_median=ok.dJ.median(),dJ_p90=ok.dJ.quantile(.9),dJ_max=ok.dJ.max(),
                            replans_median=g.n_replans.median(),replans_max=g.n_replans.max(),
                            plan_calls=len(times),plan_s_median=times.median(),plan_s_p95=times.quantile(.95),plan_s_max=times.max()))
    frame = pd.DataFrame(summary)
    frame.to_csv(output / "summary.csv",index=False)
    table("Test: same task-014 tours, fixed validation-only parameters",frame)
    paired = paired_results(data)
    paired.to_csv(output / "paired_runs.csv",index=False)
    rows=[]
    for (prior,radius,method),g in paired.groupby(["prior","radius_m","method"],sort=False):
        d=g.loc[g.paired_success,"dJ_delta"]
        rows.append(dict(prior=prior,radius_m=radius,method=method,paired_completed=len(d),
                         baseline_completed_lost=int((g.success_baseline & ~g.success).sum()),
                         newly_completed=int((~g.success_baseline & g.success).sum()),
                         worsened=int((d>0).sum()),delta_median=d.median(),delta_p90=d.quantile(.9),delta_max=d.max()))
    report=pd.DataFrame(rows)
    report.to_csv(output / "paired_summary.csv",index=False)
    table("Paired dJ differences (new minus baseline); losses include all previously completed runs",report)
    old=audit_baseline(data,output)
    former=old[old.reason.eq("too_long")][KEY]
    details=data.merge(former,on=KEY,validate="many_to_one")
    cols=KEY+["method","success","reason","dJ","n_replans","lethal_cells"]
    details[cols].to_csv(output / "former_too_long.csv",index=False)
    table("Every formerly too_long tour: all methods",details[cols])
    return details


def figures(data, output):
    cases=data[data.prior.eq("stale")][KEY].drop_duplicates()
    preferred=cases[cases.patch.eq("08OC99_01733") & cases.radius_m.eq(10)]
    cases=pd.concat([preferred,cases]).drop_duplicates().head(3)
    for i,case in enumerate(cases.itertuples(),1):
        sc=build_real(case.patch,200,0,debris=case.prior=="stale",dataset="shizuoka_beach_las")
        with np.load(output / "traces" / (case.patch+".npz")) as traces:
            fig,axes=plt.subplots(1,4,figsize=(16,4))
            for ax,method in zip(axes,["baseline","A","B","A+B"]):
                ax.imshow(sc["tmap"].cost.T,origin="lower",extent=[-.25,199.75,-.25,199.75],cmap="YlOrBr")
                ax.contour(sc["tmap"].lethal.T,levels=[.5],colors=["gray"],linewidths=.25,extent=[-.25,199.75,-.25,199.75])
                path=traces[f'{case.prior.replace(" ","_")}_R{case.radius_m}_{method}']*RESOLUTION
                ax.plot(*path.T,lw=1)
                row=data[(data.patch==case.patch)&(data.radius_m==case.radius_m)&(data.prior==case.prior)&(data.method==method)].iloc[0]
                ax.set(title=f'{method}: {"complete" if row.success else row.reason}',xlabel="x [m]",ylabel="y [m]")
            fig.suptitle(f'{case.patch} / {case.prior} / R{case.radius_m}')
            fig.tight_layout();fig.savefig(output / f'former_failure_{i:02}.png',dpi=130);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase",choices=["all","validation","test"],default="all")
    parser.add_argument("--workers",type=int,default=4)
    parser.add_argument("--output",type=Path,default=OUT)
    parser.add_argument("--reuse-validation",action="store_true",help="re-score the saved complete validation sweep without rerunning planners")
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=True)
    capture=io.StringIO()
    with redirect_stdout(capture):
        if args.phase in ("all","validation"):
            selection=select_parameters(output,args.workers,reuse=args.reuse_validation)
        else:
            selection=json.loads((output/"selection.json").read_text())
        if selection["source_sha256"] != source_hashes():
            raise ValueError("planner/scenario changed after validation; rerun validation")
        print("Frozen parameters:",json.dumps({k:selection[k] for k in ("A","B")},sort_keys=True))
        if args.phase in ("all","test"):
            data,times=execute("test",variants(selection),[5,10,15],output,args.workers)
            details=summarize(data,times,output)
            figures(details,output)
    log=capture.getvalue()
    (output / ("validation_log.txt" if args.phase=="validation" else "online_deadend_log.txt")).write_text(log)
    print(log,end="")


if __name__=="__main__":
    main()
