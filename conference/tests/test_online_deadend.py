"""Safeguard semantics, exact disabled parity and real-LAS tour contact audits."""

import json
from pathlib import Path
import numpy as np
from experiments.online_mission import scenarios
from experiments.online_deadend import variants, source_hashes
from tapp.config import RESOLUTION, CostWeights
from tapp.collision import path_lethal_cells
from tapp.online_deadend import DeadendPlanner, run_deadend_mission
from tapp.online_mission import ordered_tour, run_online_mission
from tapp.prior import PriorMap
from tapp.real_beach import list_patches

ROOT=Path(__file__).resolve().parents[1]


def test_memory_and_switch():
    cost=np.full((21,21),.2); lethal=np.zeros(cost.shape,bool)
    lethal[10,5]=True
    p=DeadendPlanner(cost,lethal,CostWeights(),r_A=2,k_A=4,N_B=0)
    seen=np.zeros(cost.shape,bool);seen[2,10]=True
    truth=lethal.copy();truth[8,10]=True
    p.observe(seen,cost,truth);p.start_leg((2,10),(18,10))
    seen[8,10]=True
    p.observe(seen,cost,truth)
    event=p.update(np.array([3,10])*RESOLUTION,distance_m=.5)
    assert event["replanned"] and p.memory_events==1 and p.hard_switches==1
    hard,mult=p.planning_maps()
    assert hard[10,5] and hard[8,10] and p.memory[8,11]
    assert mult[8,11]==1+p.w*.2*4
    assert mult[2,10]==1+p.w*.2
    assert np.array_equal(p.prior_cost,cost)
    p.start_leg((3,10),(18,10))
    assert p.mode=="soft" and p.leg_replans==0 and p.memory[8,11]
    print("safeguards: unknown-only memory, known truth precedence, strict N_B threshold and per-leg reset passed",flush=True)


def test_real_tours():
    selection=json.loads((ROOT/"results/online_deadend/selection.json").read_text())
    assert selection["test_data_used"] is False and selection["source_sha256"]==source_hashes()
    assert selection["validation_patches"]==[r["name"] for r in list_patches("validation",dataset="shizuoka_beach_las")]
    for row in list_patches("test",dataset="shizuoka_beach_las")[:3]:
        clean,stale,points=scenarios(row)
        prior=PriorMap(clean["tmap"].cost,clean["tmap"].lethal,RESOLUTION)
        tour=ordered_tour(clean["tmap"],stale["start"],points["stale"])
        args=(stale["tmap"],prior,stale["start"],tour["stops"])
        original=run_online_mission(*args,radius_m=10)
        disabled=run_deadend_mission(*args,radius_m=10)
        assert np.array_equal(original["traj"],disabled["traj"])
        assert original["n_plans"]==disabled["n_plans"] and original["n_replans"]==disabled["n_replans"]
        assert original["legs"]==disabled["legs"]
        assert [e["reason"] for e in original["events"]]==[e["reason"] for e in disabled["events"]]
        for method,config in variants(selection).items():
            if method=="baseline":continue
            result=run_deadend_mission(*args,radius_m=10,**config)
            assert len(path_lethal_cells(result["traj"],stale["tmap"].lethal))==0,(row["name"],method)
        print(row["name"]+": disabled trajectory/count parity and A/B/A+B stale five-point contacts=0",flush=True)


def test_reported_deadend():
    selection=json.loads((ROOT/"results/online_deadend/selection.json").read_text())
    row=next(r for r in list_patches("test",dataset="shizuoka_beach_las") if r["name"]=="08OC99_01733")
    clean,stale,points=scenarios(row)
    prior=PriorMap(clean["tmap"].cost,clean["tmap"].lethal,RESOLUTION)
    tour=ordered_tour(clean["tmap"],stale["start"],points["stale"])
    result=run_deadend_mission(stale["tmap"],prior,stale["start"],tour["stops"],radius_m=10,**selection["B"])
    assert result["success"],result["reason"]
    assert len(path_lethal_cells(result["traj"],stale["tmap"].lethal))==0
    print("08OC99_01733 stale R10: validation-frozen B completed without contact",flush=True)


if __name__=="__main__":
    test_memory_and_switch()
    test_real_tours()
    test_reported_deadend()
    print("all online dead-end tests passed",flush=True)
