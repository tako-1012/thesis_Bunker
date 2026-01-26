#!/usr/bin/env python3
"""Generate paper figures from dataset3 results (6 planners).

Produces:
 - figures/computation_time_comparison.png
 - figures/path_length_comparison.png
 - figures/computation_time_heatmap.png
 - figures/path_improvement_histogram.png
 - figures/path_improvement_by_type.png

Usage: python3 generate_paper_figures.py
"""
import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import math

ROOT = Path(__file__).resolve().parents[1]
RESULTS_FILE = ROOT / 'benchmark_results' / 'dataset3_8planners_results.json'
OUT_DIR = ROOT / 'figures'
OUT_DIR.mkdir(parents=True, exist_ok=True)

PLANNERS = ['D*Lite','RRT*','HPA*','SAFETY','FieldD*Hybrid','TA*']

# Load results list
with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
    raw = json.load(f)

# Build mapping: scenario_id -> {map_size, results: {planner: entry}}
scenarios = {}
for rec in raw:
    sid = rec.get('scenario_id') or rec.get('scenario_name')
    if sid is None:
        continue
    if sid not in scenarios:
        scenarios[sid] = {'map_size': rec.get('map_size'), 'results': {}}
    scenarios[sid]['results'][rec.get('planner')] = rec

scenario_ids = sorted(scenarios.keys())

# Helper to get value per planner per scenario
def get_metric(sid, planner, key, success_key='success'):
    rec = scenarios[sid]['results'].get(planner)
    if not rec:
        return float('nan')
    ok = rec.get(success_key, False)
    if not ok:
        return float('nan')
    # support different key names
    if key in rec:
        return rec.get(key)
    # fallback names
    if key == 'computation_time':
        return rec.get('computation_time')
    if key == 'path_length':
        return rec.get('path_length_meters') or rec.get('path_length') or rec.get('path_length_m')
    if key == 'nodes_explored':
        return rec.get('nodes_explored')
    return float('nan')

# 1) Computation time comparison (grouped bar per scenario)
print('Creating computation_time_comparison.png...')
plt.figure(figsize=(16,8))
x = np.arange(len(scenario_ids))
width = 0.13
for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'computation_time') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    plt.bar(x + width*(i - 2.5), vals, width, label=planner)
plt.xlabel('Scenario')
plt.ylabel('Computation time (s)')
plt.title('Computation Time Comparison (6 planners)')
plt.xticks(x, scenario_ids, rotation=90, fontsize=6)
plt.legend()
plt.tight_layout()
plt.savefig(OUT_DIR / 'computation_time_comparison.png', dpi=300)
plt.close()

# 2) Path length comparison
print('Creating path_length_comparison.png...')
plt.figure(figsize=(16,8))
x = np.arange(len(scenario_ids))
for i, planner in enumerate(PLANNERS):
    vals = [get_metric(sid, planner, 'path_length') for sid in scenario_ids]
    vals = [float(v) if (v is not None and not (isinstance(v, float) and math.isnan(v))) else np.nan for v in vals]
    plt.bar(x + width*(i - 2.5), vals, width, label=planner)
plt.xlabel('Scenario')
plt.ylabel('Path length (m)')
plt.title('Path Length Comparison (6 planners)')
plt.xticks(x, scenario_ids, rotation=90, fontsize=6)
plt.legend()
plt.tight_layout()
plt.savefig(OUT_DIR / 'path_length_comparison.png', dpi=300)
plt.close()

# 3) Computation time heatmap (scenarios x planners)
print('Creating computation_time_heatmap.png...')
heat = np.full((len(scenario_ids), len(PLANNERS)), np.nan)
for i, sid in enumerate(scenario_ids):
    for j, planner in enumerate(PLANNERS):
        v = get_metric(sid, planner, 'computation_time')
        heat[i, j] = v if v is not None else np.nan

# Replace nan with a large value for visualization or mask
mask = np.isnan(heat)
plt.figure(figsize=(8, max(6, len(scenario_ids)*0.08)))
sns.heatmap(np.log1p(np.nan_to_num(heat, nan=0.0)), cmap='viridis', yticklabels=scenario_ids, xticklabels=PLANNERS)
plt.title('Log(1+Computation time) Heatmap')
plt.xticks(rotation=45)
plt.yticks(fontsize=6)
plt.tight_layout()
plt.savefig(OUT_DIR / 'computation_time_heatmap.png', dpi=300)
plt.close()

# 4) Path improvement histogram (FieldD*Hybrid vs D*Lite)
print('Creating path_improvement_histogram.png...')
impr = []
for sid in scenario_ids:
    a = get_metric(sid, 'D*Lite', 'path_length')
    b = get_metric(sid, 'FieldD*Hybrid', 'path_length')
    if a is None or b is None:
        continue
    if isinstance(a, float) and math.isnan(a):
        continue
    if isinstance(b, float) and math.isnan(b):
        continue
    if a == 0:
        continue
    imp = (a - b) / a * 100.0
    impr.append(imp)

plt.figure(figsize=(6,4))
if impr:
    plt.hist(impr, bins=30, color='C2', alpha=0.8)
    plt.xlabel('Path length improvement (%) (D*Lite -> FieldD*Hybrid)')
    plt.ylabel('Count')
    plt.title('Path improvement histogram')
else:
    plt.text(0.5, 0.5, 'No matching successful pairs', ha='center')
plt.tight_layout()
plt.savefig(OUT_DIR / 'path_improvement_histogram.png', dpi=300)
plt.close()

# 5) Path improvement by type (map_size)
print('Creating path_improvement_by_type.png...')
by_size = {}
map_sizes = []
for sid in scenario_ids:
    size = scenarios[sid].get('map_size')
    map_sizes.append(size)
unique_sizes = sorted(list({s for s in map_sizes if s is not None}))
for us in unique_sizes:
    by_size[us] = []
for sid in scenario_ids:
    size = scenarios[sid].get('map_size')
    a = get_metric(sid, 'D*Lite', 'path_length')
    b = get_metric(sid, 'FieldD*Hybrid', 'path_length')
    if size is None or a is None or b is None:
        continue
    if isinstance(a, float) and math.isnan(a):
        continue
    if isinstance(b, float) and math.isnan(b):
        continue
    if a == 0:
        continue
    imp = (a - b) / a * 100.0
    by_size[size].append(imp)

plt.figure(figsize=(6,4))
labels = []
data = []
for us in unique_sizes:
    labels.append(str(us))
    data.append(by_size.get(us, []))
if any(len(d)>0 for d in data):
    plt.boxplot(data, labels=labels, showmeans=True)
    plt.xlabel('Map size')
    plt.ylabel('Improvement (%)')
    plt.title('Path improvement by map size')
else:
    plt.text(0.5, 0.5, 'No data available', ha='center')
plt.tight_layout()
plt.savefig(OUT_DIR / 'path_improvement_by_type.png', dpi=300)
plt.close()

print('All figures saved to', OUT_DIR)
