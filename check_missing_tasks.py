import json

with open('benchmark_results/dataset2_6planners_results.json', 'r') as f:
    results = json.load(f)

completed = set()
for r in results:
    key = (r.get('planner'), r.get('scenario_id'))
    completed.add(key)

with open('dataset2_scenarios.json', 'r') as f:
    scenarios = json.load(f)

planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']

missing = []
for planner in planners:
    for scenario in scenarios:
        key = (planner, scenario.get('id'))
        if key not in completed:
            missing.append({
                'planner': planner,
                'scenario_id': scenario.get('id'),
                'environment': scenario.get('env', scenario.get('environment_type', 'Unknown'))
            })

print(f"Missing tasks: {len(missing)}")

for planner in planners:
    p_missing = [m for m in missing if m['planner'] == planner]
    if p_missing:
        print(f"  {planner}: {len(p_missing)} missing")

with open('benchmark_results/missing_tasks.json', 'w') as f:
    json.dump(missing, f, indent=2)

print('\nSaved: benchmark_results/missing_tasks.json')
