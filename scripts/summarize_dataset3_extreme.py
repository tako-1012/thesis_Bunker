#!/usr/bin/env python3
import json
from pathlib import Path
import numpy as np

p = Path('dataset3_scenarios.json')
out = Path('benchmark_results')
out.mkdir(exist_ok=True)
with p.open() as f:
    sc = json.load(f)

summary = {}
for t in [1,2,3,4]:
    entries = [s for s in sc if s['type']==t]
    if not entries:
        continue
    obs = [e['obstacle_ratio_actual'] for e in entries]
    m1 = [e['complexity']['Method1_Slope'] for e in entries]
    m2 = [e['complexity']['Method2_Obstacle'] for e in entries]
    m3 = [e['complexity']['Method3_Balanced'] for e in entries]
    m4 = [e['complexity']['Method4_Statistical'] for e in entries]
    sizes = [e['map_size'][0] for e in entries]
    summary[t] = {
        'count': len(entries),
        'map_size_values': sorted(list(set(sizes))),
        'obstacle_ratio_mean': float(np.mean(obs)),
        'obstacle_ratio_median': float(np.median(obs)),
        'Method1_mean': float(np.mean(m1)),
        'Method1_median': float(np.median(m1)),
        'Method2_mean': float(np.mean(m2)),
        'Method2_median': float(np.median(m2)),
        'Method3_mean': float(np.mean(m3)),
        'Method3_median': float(np.median(m3)),
        'Method4_mean': float(np.mean(m4)),
        'Method4_median': float(np.median(m4))
    }

with open(out / 'dataset3_extreme_complexity_summary.json','w') as f:
    json.dump(summary, f, indent=2)
print('Wrote summary to', out / 'dataset3_extreme_complexity_summary.json')
