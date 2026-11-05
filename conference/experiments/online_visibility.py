"""Compare radius sensing and three assumed sensor heights on fixed task-014 tours."""

import argparse
from contextlib import redirect_stdout
import io
import hashlib
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

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from experiments.online_mission import scenarios,table
from experiments.beach_terrain import metrics
from tapp.collision import path_lethal_cells
from tapp.config import RESOLUTION
from tapp.online_mission import ordered_tour,run_online_mission
from tapp.prior import PriorMap,coarse_prior,coarse_elevation
from tapp.real_beach import list_patches,build_real
from tapp.traversability import TraversabilityMap
from tapp.visibility import run_visibility_mission

OUT=ROOT/"results/online_visibility"
SENSORS=[("radius",False,.8),("LOS h0.5",True,.5),("LOS h0.8",True,.8),("LOS h1.2",True,1.2)]


def run_patch(row):
    clean,stale,points=scenarios(row)
    coarse=coarse_prior(clean["tmap"],10)
    coarse_tm=TraversabilityMap(coarse_elevation(clean["tmap"],10),np.zeros(clean["tmap"].shape,bool),clean["tmap"].robot,clean["tmap"].weights)
    refs={}
    for name,sc in [("clean",clean),("stale",stale)]:
        tm=sc["tmap"];tour=ordered_tour(tm,sc["start"],points[name])
        r=run_online_mission(tm,PriorMap(tm.cost,tm.lethal,RESOLUTION),sc["start"],tour["stops"],radius_m=10,prior_lethal_mode="hard")
        if not r["success"]:raise RuntimeError("truth oracle failed: "+row["name"])
        refs[name]=metrics(r["traj"],tm)["J"]
    rows,times,traces,observations,contacts=[],[],{},{},{}
    for prior_name in ("coarse c10","stale"):
        sc=stale if prior_name=="stale" else clean
        truth=sc["tmap"];ptm=clean["tmap"] if prior_name=="stale" else coarse_tm
        prior=PriorMap(ptm.cost,ptm.lethal,RESOLUTION) if prior_name=="stale" else coarse
        tour=ordered_tour(ptm,sc["start"],points["stale" if prior_name=="stale" else "clean"])
        oracle=refs["stale" if prior_name=="stale" else "clean"]
        for sensor,los,height in SENSORS:
            result=run_visibility_mission(truth,prior,sc["start"],tour["stops"],radius_m=10,los=los,
                                         sensor_height_m=height,rock_mask=sc["terrain"]["driftwood"],obstacle_height_m=.3)
            key=dict(patch=row["name"],side_m=200,seed=0,prior=prior_name,radius_m=10,sensor=sensor)
            row_out=dict(key,success=result["success"],reason=result["reason"],n_plans=result["n_plans"],n_replans=result["n_replans"],
                         lethal_cells=len(path_lethal_cells(result["traj"],truth.lethal)),
                         debris_cells=len(path_lethal_cells(result["traj"],truth.rock & ~clean["tmap"].rock)),oracle_J=oracle,
                         visible_fraction_median=float(np.median(result["visible_fractions"])),observations=len(result["visible_fractions"]))
            if result["success"]:
                value=metrics(result["traj"],truth)["J"]
                row_out.update(J=value,dJ=100*(value/oracle-1))
            rows.append(row_out)
            times.extend(dict(key,call=i,seconds=t) for i,t in enumerate(result["plan_times"]))
            name=prior_name.replace(" ","_")+"__"+sensor.replace(" ","_")
            traces[name]=np.asarray(result["traj"],float)
            observations[name]=np.asarray(result["visible_fractions"],float)
            contacts[name]=result["contact_events"]
    return row["name"],rows,times,traces,observations,contacts


def summarize(data,timings,fractions,output):
    rows=[]
    for (prior,sensor),g in data.groupby(["prior","sensor"],sort=False):
        t=timings[(timings.prior==prior)&(timings.sensor==sensor)].seconds
        ok=g[g.success]
        rows.append(dict(prior=prior,sensor=sensor,runs=len(g),completed=int(g.success.sum()),too_long=int(g.reason.eq("too_long").sum()),
                         touching=int((g.lethal_cells>0).sum()),debris_touching=int((g.debris_cells>0).sum()),
                         dJ_median=ok.dJ.median(),dJ_p90=ok.dJ.quantile(.9),dJ_max=ok.dJ.max(),
                         replans_median=g.n_replans.median(),replans_max=g.n_replans.max(),plan_calls=len(t),
                         plan_s_median=t.median(),plan_s_p95=t.quantile(.95),plan_s_max=t.max(),
                         visible_fraction_median=float(np.median(np.concatenate(fractions[prior,sensor])))))
    summary=pd.DataFrame(rows);summary.to_csv(output/"summary.csv",index=False)
    table("Test: task-014 tours, R10; sensor/obstacle heights are assumptions",summary)
    base=data[data.sensor=="radius"][["patch","prior","success","dJ","n_plans","n_replans","lethal_cells"]]
    old=pd.read_csv(ROOT/"results/online_mission/missions.csv")
    old=old[(old.radius_m==10)&old["mode"].eq("online")&old.prior.isin(["stale","coarse c10"])]
    paired=base.merge(old,on=["patch","prior"],how="outer",validate="one_to_one",suffixes=("","_014"),indicator=True)
    assert paired._merge.eq("both").all()
    for col in ["success","n_plans","n_replans","lethal_cells"]:assert paired[col].eq(paired[col+"_014"]).all(),col
    assert np.allclose(paired.dJ,paired.dJ_014,atol=1e-10,rtol=1e-12,equal_nan=True)
    print("Radius control: scenario identities, outcomes, plan/replan/contact counts and dJ match task 014.")
    paired=data[data.sensor!="radius"].merge(base,on=["patch","prior"],validate="many_to_one",suffixes=("","_radius"))
    paired["dJ_delta"]=np.where(paired.success&paired.success_radius,paired.dJ-paired.dJ_radius,np.nan)
    paired.to_csv(output/"paired_runs.csv",index=False)
    differences=[]
    for (prior,sensor),g in paired.groupby(["prior","sensor"],sort=False):
        d=g.dJ_delta.dropna()
        differences.append(dict(prior=prior,sensor=sensor,paired_completed=len(d),completed_lost=int((g.success_radius&~g.success).sum()),
                                newly_completed=int((~g.success_radius&g.success).sum()),delta_median=d.median(),delta_p90=d.quantile(.9),delta_max=d.max()))
    effects=pd.DataFrame(differences);effects.to_csv(output/"paired_summary.csv",index=False)
    table("LOS minus radius-control dJ; paired completed runs only, completion losses reported separately",effects)
    contacts=data[data.lethal_cells>0]
    contacts.to_csv(output/"contacts.csv",index=False)
    table("Contact cases (includes failed tours)",contacts)
    reasons=[]
    for row in contacts.itertuples():
        archive=json.loads((output/"contact_details"/(row.patch+".json")).read_text())
        events=archive[row.prior.replace(" ","_")+"__"+row.sensor.replace(" ","_")]
        unique=np.unique(np.array([e["cell"] for e in events]),axis=0)
        assert len(unique)==row.lethal_cells
        for cause in sorted({e["cause"] for e in events}):
            cells=np.unique(np.array([e["cell"] for e in events if e["cause"]==cause]),axis=0)
            reasons.append(dict(patch=row.patch,prior=row.prior,sensor=row.sensor,cause=cause,unique_cells=len(cells)))
    reason_frame=pd.DataFrame(reasons,columns=["patch","prior","sensor","cause","unique_cells"])
    reason_frame.to_csv(output/"contact_reasons.csv",index=False)
    table("Contact cause at the last observation (cell counts may overlap across causes)",reason_frame)
    for i,row in enumerate(contacts.head(3).itertuples(),1):
        sc=build_real(row.patch,200,0,debris=row.prior=="stale",dataset="shizuoka_beach_las")
        with np.load(output/"traces"/(row.patch+".npz")) as archive:
            trajectory=archive[row.prior.replace(" ","_")+"__"+row.sensor.replace(" ","_")]
        hits=path_lethal_cells(trajectory,sc["tmap"].lethal)*RESOLUTION
        fig,ax=plt.subplots(figsize=(7,7));ax.imshow(sc["tmap"].elev.T,origin="lower",extent=[-.25,199.75,-.25,199.75],cmap="terrain")
        ax.plot(*(trajectory*RESOLUTION).T,label="executed");ax.scatter(*hits.T,c="red",marker="x",label="lethal contacts")
        details=json.loads((output/"contact_details"/(row.patch+".json")).read_text())
        first=details[row.prior.replace(" ","_")+"__"+row.sensor.replace(" ","_")][0]
        sensor=np.asarray(first["sensor_cell"])*RESOLUTION
        ax.scatter(*sensor,marker="o",c="cyan",label="last observation / "+first["cause"])
        ax.set(title=f'{row.patch} / {row.prior} / {row.sensor}',xlabel="x [m]",ylabel="y [m]");ax.legend();fig.tight_layout()
        fig.savefig(output/f'contact_{i:02}.png',dpi=130);plt.close(fig)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--workers",type=int,default=4);parser.add_argument("--output",type=Path,default=OUT)
    args=parser.parse_args();output=args.output;output.mkdir(parents=True,exist_ok=True)
    source_files=["tapp/visibility.py","tapp/online_mission.py","tapp/real_beach.py","tapp/config.py",
                  "experiments/online_visibility.py","experiments/online_mission.py","data/shizuoka_beach_las/index.json"]
    (output/"protocol.json").write_text(json.dumps(dict(dataset="shizuoka_beach_las",split="test",side_m=200,seed=0,
        radius_m=10,sensors=SENSORS,assumed_driftwood_height_m=.3,
        boulder_height="already embedded in build_real elevation; not added twice",
        python=sys.version,numpy=np.__version__,workers=args.workers,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in source_files}),indent=2)+"\n")
    for name in ("traces","observations","contact_details"):(output/name).mkdir(exist_ok=True)
    records,plans,fractions=[],[],{}
    start=time.perf_counter();patches=list_patches("test",dataset="shizuoka_beach_las")
    with Pool(args.workers) as pool:
        for i,(name,rows,times,traces,observations,contacts) in enumerate(pool.imap(run_patch,patches),1):
            records.extend(rows);plans.extend(times)
            np.savez_compressed(output/"traces"/(name+".npz"),**traces)
            np.savez_compressed(output/"observations"/(name+".npz"),**observations)
            (output/"contact_details"/(name+".json")).write_text(json.dumps(contacts,indent=2)+"\n")
            for row in rows:
                key=row["prior"],row["sensor"];archive_key=key[0].replace(" ","_")+"__"+key[1].replace(" ","_")
                fractions.setdefault(key,[]).append(observations[archive_key])
            print(f'{i}/{len(patches)} {name} ({time.perf_counter()-start:.1f}s)',file=sys.stderr,flush=True)
    data,timings=pd.DataFrame(records),pd.DataFrame(plans);data.to_csv(output/"missions.csv",index=False)
    for (prior,sensor),g in timings.groupby(["prior","sensor"]):
        g.to_csv(output/("plan_times_"+prior.replace(" ","_")+"_"+sensor.replace(" ","_")+".csv"),index=False)
    (output/"runtime.json").write_text(json.dumps(dict(wall_s=time.perf_counter()-start,workers=args.workers),indent=2)+"\n")
    capture=io.StringIO()
    with redirect_stdout(capture):summarize(data,timings,fractions,output)
    log=capture.getvalue();(output/"online_visibility_log.txt").write_text(log);print(log,end="")


if __name__=="__main__":main()
