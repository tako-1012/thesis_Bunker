"""Task035 stage 2: robot distance at first map insertion of obstacle fine cells, per triggering sensor (from pointcloud_map.npz.sensors.json)."""
import json, sys
from pathlib import Path
import numpy as np
for run in sorted(Path(__file__).resolve().parent.glob("runs/08OB86_-0205/S*_r1")):
    f = next((run/"physical_1/raw").iterdir())/"pointcloud_map.npz.sensors.json"
    if not f.exists():
        print(run.name, "no sensors json"); continue
    d = json.loads(f.read_text())
    print(run.name, "counters first_detected_cells:", {k: v.get("first_detected_cells") for k, v in d["counters"].items()})
    for s in ("lidar", "camera1", "camera2"):
        x = np.array([r["robot_distance_xy_m"] for r in d["first_detections"] if r["triggering_sensor"] == s])
        if len(x):
            print(f"  {s}: n={len(x)} distance_m min/median/max = {x.min():.2f}/{np.median(x):.2f}/{x.max():.2f}")
        else:
            print(f"  {s}: n=0")
