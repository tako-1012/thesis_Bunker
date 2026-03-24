#!/usr/bin/env python3
"""
Combine Regular A* results with existing 8-planner data

Strategy:
1. Load completed A* results from dataset3_9planners_results.json (90/90)
2. Load other planners from dataset3_8planners_results.json
3. Create combined dataset with 5 methods:
   - A* (from new benchmark)
   - D*Lite, RRT*, FieldD*Hybrid, TA* (from existing 8-planner data)
4. Generate figures

Output: benchmark_results/dataset3_5methods_combined_results.json
"""

import json
from pathlib import Path

# Load new A* results
print('Loading new A* results...')
with open('benchmark_results/dataset3_9planners_results.json') as f:
    new_results = json.load(f)

a_star_results = [r for r in new_results if r['planner'] == 'A*']
print(f'  A* results: {len(a_star_results)}/90')

# Load existing 8-planner results
print('Loading existing 8-planner results...')
with open('benchmark_results/dataset3_8planners_results.json') as f:
    existing_results = json.load(f)

# Extract needed planners
needed_planners = ['D*Lite', 'RRT*', 'FieldD*Hybrid', 'TA*']
extracted_results = []
for planner in needed_planners:
    planner_results = [r for r in existing_results if r['planner'] == planner]
    extracted_results.extend(planner_results)
    print(f'  {planner}: {len(planner_results)} results')

# Combine
combined_results = a_star_results + extracted_results
print(f'\nTotal combined results: {len(combined_results)}')

# Verify completeness
from collections import defaultdict
by_planner = defaultdict(int)
for r in combined_results:
    by_planner[r['planner']] += 1

print('\nResults by planner:')
for p in ['A*', 'D*Lite', 'RRT*', 'FieldD*Hybrid', 'TA*']:
    count = by_planner[p]
    print(f'  {p:20s}: {count:3d}/90')

# Save combined results
output_path = 'benchmark_results/dataset3_5methods_combined_results.json'
with open(output_path, 'w') as f:
    json.dump(combined_results, f, indent=2)

print(f'\n✓ Saved: {output_path}')
print('\nNow you can generate figures with:')
print('  python3 generate_5methods_figures.py')
