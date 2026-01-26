#!/usr/bin/env python3
import json
from pathlib import Path

p_par = Path('dataset3_extreme_parameters.json')
sc_p = Path('dataset3_scenarios.json')
out = Path('benchmark_results')
out.mkdir(exist_ok=True)

with p_par.open() as f:
    params = json.load(f)
with sc_p.open() as f:
    sc = json.load(f)

type2 = {}
type4 = {}
for s in sc:
    sid = s['id']
    p = params.get(sid, {})
    if s['type']==2:
        v = p.get('verification',{})
        type2[sid] = {'obstacle_ratio': s.get('obstacle_ratio_actual', None), 'verification': v}
    if s['type']==4:
        v = p.get('verification',{})
        type4[sid] = {'obstacle_ratio': s.get('obstacle_ratio_actual', None), 'verification': v}

with open(out / 'dataset3_type2_verification.json','w') as f:
    json.dump(type2, f, indent=2)
with open(out / 'dataset3_type4_verification.json','w') as f:
    json.dump(type4, f, indent=2)

print('Wrote verification JSONs to', out)
