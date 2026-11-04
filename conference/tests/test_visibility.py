"""DEM shadows, height monotonicity, sensing compatibility and unchanged radial control."""

import numpy as np
from tapp.config import RESOLUTION
from tapp.prior import PriorMap
from tapp.traversability import TraversabilityMap
from tapp.online_mission import virtual_sense,run_online_mission
from tapp.visibility import visible_cells,virtual_sense_los,run_visibility_mission
from tapp.collision import path_lethal_cells


def main():
    z=np.zeros((31,29));position=np.array([3,14]);radius=10
    coords=np.indices(z.shape)-position[:,None,None]
    disk=(coords**2).sum(axis=0)<=(radius/RESOLUTION)**2
    assert np.array_equal(visible_cells(z,position,radius),disk)
    assert visible_cells(z,position,0).sum()==1
    print("visibility: all cells in the physical radius visible on flat terrain, including clipped edges",flush=True)
    z[10,:]=5
    mask=visible_cells(z,position,radius)
    assert mask[8,14] and mask[10,14] and not mask[13,14]
    print("visibility: front and wall top visible, cells behind the wall occluded",flush=True)
    rng=np.random.default_rng(100)
    terrain=rng.normal(0,.1,(31,29));terrain[10,5:24]+=1
    previous=visible_cells(terrain,position,radius,.5)
    for height in (.8,1.2):
        current=visible_cells(terrain,position,radius,height)
        assert not (previous & ~current).any()
        previous=current
    print("visibility: raising the sensor 0.5 -> 0.8 -> 1.2m never loses a visible cell",flush=True)
    flat=TraversabilityMap(np.zeros(z.shape),np.zeros(z.shape,bool))
    plain=virtual_sense(flat,position,radius)
    los=virtual_sense_los(flat,position,radius)
    assert np.array_equal(plain[0],los[0]) and los[1] is plain[1] and los[2] is plain[2]
    obstacles=np.zeros(z.shape,bool);obstacles[10,:]=True
    shadow=virtual_sense_los(flat,position,radius,rock_mask=obstacles)[0]
    assert not shadow[13,14] and los[0][13,14]
    print("sensing: bool mask/cost/lethal tuple and explicit raw-obstacle assumed height passed",flush=True)
    rock=np.zeros((31,31),bool);rock[13:16,12:18]=True
    tm=TraversabilityMap(np.zeros(rock.shape),rock)
    prior=PriorMap(np.zeros(tm.shape),np.zeros(tm.shape,bool),RESOLUTION)
    args=(tm,prior,(3,15),[(26,15),(3,15)])
    old=run_online_mission(*args,radius_m=3)
    control=run_visibility_mission(*args,radius_m=3,los=False)
    assert np.array_equal(old["traj"],control["traj"])
    assert old["legs"]==control["legs"] and old["n_plans"]==control["n_plans"]
    assert all(f==1 for f in control["visible_fractions"])
    blind=run_visibility_mission(tm,prior,(3,15),[(26,15)],radius_m=0,los=False)
    hits=path_lethal_cells(blind["traj"],tm.lethal)
    observed=np.unique(np.array([e["cell"] for e in blind["contact_events"]]),axis=0)
    assert len(hits)>0 and np.array_equal(hits,observed)
    assert any(e["cause"]=="outside_last_radius" for e in blind["contact_events"])
    print("control: radial trajectory/count parity; contact diagnostics agree with exact trajectory audit",flush=True)
    print("all visibility tests passed",flush=True)


if __name__=="__main__":main()
