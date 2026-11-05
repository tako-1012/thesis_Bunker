"""Distinguish first entry into a lethal cell from later contact with the same cell."""

import argparse
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tapp.config import RESOLUTION
from tapp.real_beach import build_real


def audit(folder):
    folder=Path(folder)
    data=pd.read_csv(folder/"missions.csv")
    rows=[]
    scenarios={}
    for run in data[data.lethal_cells>0].itertuples():
        key=(run.patch,run.prior)
        if key not in scenarios:
            scenarios[key]=build_real(run.patch,int(run.side_m),int(run.seed),debris=run.prior=="stale",dataset="shizuoka_beach_las")
        sc=scenarios[key];tm=sc["tmap"]
        cases=json.loads((folder/"contact_details"/(run.patch+".json")).read_text())
        events=cases[run.prior.replace(" ","_")+"__"+run.sensor.replace(" ","_")]
        first={}
        for event in events:
            first.setdefault(tuple(event["cell"]),event)
        if len(first)!=run.lethal_cells:
            raise AssertionError("first-contact cells differ from the trajectory audit")
        for (x,y),event in first.items():
            assert tm.lethal[x,y]
            rows.append(dict(patch=run.patch,prior=run.prior,sensor=run.sensor,cause=event["cause"],
                             cell_x=x,cell_y=y,x_m=x*RESOLUTION,y_m=y*RESOLUTION,known_before=event["known_before"],
                             visible_last=event["visible_last"],sensor_cell=json.dumps(event["sensor_cell"]),
                             slope_deg=float(tm.slope[x,y]),steep=bool(tm.steep[x,y]),
                             obstacle_buffer=bool(tm.rock[x,y]),water=bool(sc["water"][x,y]),nodata=bool(sc["nodata"][x,y])))
    frame=pd.DataFrame(rows,columns=["patch","prior","sensor","cause","cell_x","cell_y","x_m","y_m","known_before","visible_last","sensor_cell","slope_deg","steep","obstacle_buffer","water","nodata"])
    frame.to_csv(folder/"first_contacts.csv",index=False)
    counts=frame.groupby(["prior","sensor","cause"]).agg(contact_runs=("patch","nunique"),unique_contact_cells=("patch","size")).reset_index()
    counts.to_csv(folder/"first_contact_causes.csv",index=False)
    stream=io.StringIO()
    with redirect_stdout(stream):
        print("First entry of each lethal cell per run; later exits/repeated touches are excluded.")
        print(counts.to_string(index=False))
        print("\nFirst-contact cell coordinates and observation state")
        print(frame.to_string(index=False))
    log=stream.getvalue();(folder/"first_contacts_log.txt").write_text(log);print(log,end="")
    sources=[folder/"missions.csv"]+sorted((folder/"contact_details").glob("*.json"))
    (folder/"contact_audit_sha256.json").write_text(json.dumps(dict(
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        inputs={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+"\n")
    return frame,counts


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder",type=Path,nargs="?",default=ROOT/"results/online_visibility")
    audit(parser.parse_args().folder)
