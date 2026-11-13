"""Task033 B: (1) does a truth TA*-S+inflate path to stop 5 exist on 08OB88_-0167, (2) cross-track deviation
from the followed path and truth slope under the robot in the last 10 s before each C2 rollover. Evaluation only."""
import sys, csv, json
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tapp.config import Robot, RESOLUTION
from tapp.traversability import slope_deg, inflate
from tapp.planners import astar
from tapp.pure_pursuit import prepare_path, path_distance
r = Robot(); print("max_slope_deg", r.max_slope_deg, "footprint_radius", r.footprint_radius)
B = Path(__file__).resolve().parents[1]/"eval_ground_endpoint/runs/08OB88_-0167"
ref = np.load(B/"C1_r1/physical_1/raw/08OB88_-0167/evaluation_reference.npz")
sl = slope_deg(ref["truth_elev"]); steep = sl > r.max_slope_deg
L = ref["truth_lethal"] | inflate(steep, r.footprint_radius)
for start in [(158, 280), (142, 281)]:
    res = astar(L, start, (137, 294))
    p = np.array(res["path"]) if res["success"] else None
    print("truth TA*-S+inflate", start, "-> (137,294) success", res["success"],
          "max truth slope on path", None if p is None else round(float(sl[tuple(p.T)].max()), 1))
g = (137, 294); print("goal truth slope", round(float(sl[g]), 1), "truth steep cells in 5x5 around goal", int(steep[g[0]-2:g[0]+3, g[1]-2:g[1]+3].sum()))
for run, tr in [("C2_r1", 355.5), ("C2_r2", 354.35), ("C2_r3", 357.2)]:
    R = B/run/"physical_1/raw/08OB88_-0167"
    revs = list(csv.DictReader(open(R/"path_revisions.csv")))
    T = np.array([[float(x[k]) for k in ("t", "x", "y", "roll", "pitch")] for x in csv.DictReader(open(R/"trajectory.csv"))])
    print(run)
    for t, x, y, roll, pitch in T[(T[:, 0] >= tr-10) & (T[:, 0] <= tr)][::20]:
        rv = [q for q in revs if float(q["t"]) <= t][-1]
        d = path_distance(np.array([x, y]), prepare_path(json.loads(rv["path"])))
        c = tuple(np.rint(np.array([x, y])/RESOLUTION).astype(int))
        print(f"  t={t:7.2f} rev={rv["t"]:>7s} deviation_m={d:5.2f} truth_slope={sl[c]:5.1f} roll={np.degrees(roll):6.1f} pitch={np.degrees(pitch):6.1f}")
