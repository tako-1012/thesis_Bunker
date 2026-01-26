#!/usr/bin/env python3
import os
import json
import math
import numpy as np
import importlib.util

ROOT = os.getcwd()
SCEN = os.path.join(ROOT, 'dataset3_scenarios.json')
OUT_VAL = os.path.join(ROOT, 'benchmark_results', 'dataset3_validation_report.json')
OUT_COMP = os.path.join(ROOT, 'benchmark_results', 'dataset3_complexity_preview.json')

# load complexity_methods module from scripts/complexity_methods.py
cm_path = os.path.join(ROOT, 'scripts', 'complexity_methods.py')
spec = importlib.util.spec_from_file_location('complexity_methods', cm_path)
cm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cm)

with open(SCEN,'r') as f:
    scenarios = json.load(f)

# group by type (env field)
groups = {}
for s in scenarios:
    t = s.get('env') or s.get('environment') or s.get('type')
    groups.setdefault(t, []).append(s)

report = {}
comp_preview = {'per_scenario': []}

for t, lst in groups.items():
    obs = []
    sizes = []
    slopes = []
    sg_dists = []
    complexities = { 'Method1_Slope': [], 'Method2_Obstacle': [], 'Method3_Balanced': [], 'Method4_Statistical': [] }
    for sc in lst:
        sizes.append(int(sc.get('map_size')) if sc.get('map_size') else None)
        obs_ratio = sc.get('obstacle_ratio')
        if obs_ratio is None:
            # compute from obstacle_map
            om = np.array(sc.get('obstacle_map', []))
            if om.size>0:
                obs_ratio = float(np.mean(om))
            else:
                obs_ratio = None
        obs.append(obs_ratio)
        # start-goal distance
        sxy = sc.get('start'); gxy = sc.get('goal')
        try:
            d = math.hypot(float(sxy[0])-float(gxy[0]), float(sxy[1])-float(gxy[1]))
        except Exception:
            d = None
        sg_dists.append(d)
        # slope mean for height_map if present
        hm = sc.get('height_map')
        if hm is not None:
            ha = np.array(hm)
            if ha.size>0:
                gx = np.gradient(ha, axis=1)
                gy = np.gradient(ha, axis=0)
                slopes_arr = np.degrees(np.arctan(np.sqrt(gx**2+gy**2))).flatten()
                slopes.append(float(np.nanmean(slopes_arr)))
        # complexity methods
        try:
            res = cm.evaluate_all_methods(sc)
            for k,v in res.items():
                complexities[k].append(float(v.get('complexity', float('nan')))
                                       if isinstance(v, dict) and 'complexity' in v else float('nan'))
            comp_preview['per_scenario'].append({'scenario_id': sc.get('id'), 'env': t, 'methods': res})
        except Exception:
            # fallback: skip
            pass

    def stats(arr):
        arr_n = [a for a in arr if a is not None and (not isinstance(a,float) or not math.isnan(a))]
        if not arr_n:
            return {'count':0,'min':None,'max':None,'mean':None,'median':None}
        a = np.array(arr_n, dtype=float)
        return {'count': int(len(a)), 'min': float(np.min(a)), 'max': float(np.max(a)), 'mean': float(np.mean(a)), 'median': float(np.median(a))}

    comp_stats = {k: stats(v) for k,v in complexities.items()}

    report[t] = {
        'scenario_count': len(lst),
        'map_size_stats': stats(sizes),
        'obstacle_ratio_stats': stats(obs),
        'slope_mean_stats': stats(slopes),
        'start_goal_distance_stats': stats(sg_dists),
        'complexity_method_stats': comp_stats
    }

# save
os.makedirs(os.path.join(ROOT,'benchmark_results'), exist_ok=True)
with open(OUT_VAL,'w') as f:
    json.dump(report, f, indent=2)
with open(OUT_COMP,'w') as f:
    json.dump(comp_preview, f, indent=2)

print('Saved:', OUT_VAL, OUT_COMP)
