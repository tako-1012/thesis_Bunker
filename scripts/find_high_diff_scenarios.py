#!/usr/bin/env python3
import json
from collections import defaultdict
import numpy as np

IN = 'ros2/ros2_ws/src/bunker_ros2/results/algorithm_comparison/comparison_results.json'

with open(IN,'r') as f:
    data = json.load(f)

# data is a dict mapping algorithm names to list of results (from earlier read)
# If it's a list, handle accordingly
entries = []
if isinstance(data, dict):
    # keys are algorithms
    for alg, lst in data.items():
        for item in lst:
            item['algorithm'] = alg
            entries.append(item)
elif isinstance(data, list):
    entries = data
else:
    raise RuntimeError('Unknown structure')

# Group by scenario_name or scenario_id
groups = defaultdict(list)
for e in entries:
    sid = e.get('scenario_name') or str(e.get('scenario_id')) or e.get('scenario')
    groups[sid].append(e)

candidates = []
for sid, lst in groups.items():
    # find TA* and A* entries
    ta_entry = None
    a_entry = None
    for e in lst:
        alg = e.get('algorithm','').lower()
        if 'ta' in alg or 'terrain' in alg:
            ta_entry = e
        if e.get('algorithm','').lower().startswith('a') or e.get('algorithm','').lower()=='astar' or e.get('algorithm','').lower()=='a*' or 'dijkstra' in e.get('algorithm','').lower():
            # heuristic: choose A* or Dijkstra as regular
            if a_entry is None:
                a_entry = e
    if ta_entry and a_entry:
        # compute max heights from path arrays
        try:
            ta_path = np.array(ta_entry.get('path',[]))
            a_path = np.array(a_entry.get('path',[]))
            if ta_path.size and a_path.size and ta_path.shape[1]>=3 and a_path.shape[1]>=3:
                ta_max = float(np.nanmax(ta_path[:,2]))
                a_max = float(np.nanmax(a_path[:,2]))
                height_diff = a_max - ta_max
                candidates.append({'scenario': sid, 'ta_max':ta_max, 'a_max':a_max, 'height_diff':height_diff, 'ta':ta_entry, 'a':a_entry})
        except Exception:
            pass

# filter by diff >=5
cands = [c for c in candidates if c['height_diff']>=5.0]
print('Found candidates with >=5m diff:', len(cands))
# sort
cands.sort(key=lambda x: x['height_diff'], reverse=True)
for i,c in enumerate(cands[:10],1):
    print(i, c['scenario'], 'diff=', c['height_diff'], 'ta_max=', c['ta_max'], 'a_max=', c['a_max'])

# Save candidates
with open('scripts/high_diff_candidates.json','w') as f:
    json.dump(cands, f, indent=2)
print('Wrote scripts/high_diff_candidates.json')
