import json
import numpy as np

print("="*60)
print("FINAL BENCHMARK RESULTS")
print("="*60)

with open('benchmark_results/dataset2_6planners_results.json', 'r') as f:
    results = json.load(f)

total_expected = 864
total_completed = len(results)
total_success = sum(1 for r in results if r.get('success', False))

print(f"\nTotal tasks: {total_completed}/{total_expected} ({(total_completed/total_expected*100) if total_expected>0 else 0:.1f}%)")
if total_completed>0:
    print(f"Overall success: {total_success}/{total_completed} ({(total_success/total_completed*100):.1f}%)")
else:
    print("Overall success: 0/0")

print("\n" + "="*60)
print("BY PLANNER")
print("="*60)

planners = ['TA*', 'Theta*', 'RRT*', 'D*Lite', 'HPA*', 'SAFETY']

summary_data = []

for planner in planners:
    p_results = [r for r in results if r.get('planner') == planner]
    if not p_results:
        continue
    p_success = [r for r in p_results if r.get('success', False)]
    times = [r.get('computation_time', 0) for r in p_success]
    paths = [r.get('path_length_meters', 0) for r in p_success]

    print(f"\n{planner}:")
    print(f"  Completed: {len(p_results)}/144")
    print(f"  Success: {len(p_success)}/{len(p_results)} ({(len(p_success)/len(p_results)*100) if len(p_results)>0 else 0:.1f}%)")

    if times:
        print(f"  Time (avg): {np.mean(times):.3f}s")
        print(f"  Time (min): {np.min(times):.3f}s")
        print(f"  Time (max): {np.max(times):.3f}s")
        print(f"  Time (median): {np.median(times):.3f}s")

    if paths:
        print(f"  Path (avg): {np.mean(paths):.1f}m")

    summary_data.append({
        'planner': planner,
        'completed': len(p_results),
        'success': len(p_success),
        'success_rate': (len(p_success)/len(p_results)) if p_results else 0,
        'avg_time': float(np.mean(times)) if times else 0,
        'avg_path': float(np.mean(paths)) if paths else 0
    })

print("\n" + "="*60)
print("BY ENVIRONMENT")
print("="*60)

env_types = ['steep', 'dense', 'complex']

for env_type in env_types:
    env_results = [r for r in results if env_type.lower() in r.get('scenario_id', '').lower()]
    if not env_results:
        continue
    env_success = sum(1 for r in env_results if r.get('success', False))
    print(f"\n{env_type.upper()}:")
    print(f"  Total: {len(env_results)}")
    print(f"  Success: {env_success}/{len(env_results)} ({(env_success/len(env_results)*100):.1f}%)")

import csv
outdir = 'benchmark_results'
with open(outdir + '/dataset2_final_summary.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['planner', 'completed', 'success', 'success_rate', 'avg_time', 'avg_path'])
    writer.writeheader()
    writer.writerows(summary_data)

print("\n" + "="*60)
print(f"Summary saved: {outdir}/dataset2_final_summary.csv")
print("="*60)

print("\n" + "="*60)
print("ASSESSMENT")
print("="*60)

if total_completed >= 850:
    print(f"\n✓ SUFFICIENT DATA\n  {total_completed} tasks completed\n  Ready to proceed to analysis phase")
else:
    print(f"\n⚠ INCOMPLETE\n  Only {total_completed} tasks completed\n  May need to investigate failures")
