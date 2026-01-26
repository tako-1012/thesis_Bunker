import json
import os

result_file = 'benchmark_results/dataset2_6planners_results.json'

if os.path.exists(result_file):
    try:
        with open(result_file, 'r') as f:
            results = json.load(f)
    except Exception:
        results = []

    total_expected = 6 * 144
    completed = len(results)

    print(f"Progress: {completed}/{total_expected} ({completed/total_expected*100:.1f}%)")

    planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']
    for planner in planners:
        planner_results = [r for r in results if r.get('planner') == planner]
        print(f"  {planner}: {len(planner_results)}/144")
else:
    print('Benchmark not started yet')
