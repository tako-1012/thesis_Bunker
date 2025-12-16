#!/usr/bin/env python3
"""
Run Phase2 scalability experiment and save to `results/phase2_scalability.json`.

This script dynamically loads the existing `benchmark_full.py` implementation
and runs it with parameters that match the user's requested counts.
"""
import os
import json
import importlib.util
from pathlib import Path


def load_module_from_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[2]
# Path to the benchmark implementation in the workspace
BENCHMARK_PY = ROOT / 'ros2' / 'ros2_ws' / 'src' / 'path_planner_3d' / 'path_planner_3d' / 'benchmark_full.py'


def main():
    os.makedirs('results', exist_ok=True)

    if not BENCHMARK_PY.exists():
        print(f"Cannot find benchmark implementation at: {BENCHMARK_PY}")
        return

    module = load_module_from_path('benchmark_full', str(BENCHMARK_PY))
    PlannerBenchmark = module.PlannerBenchmark

    benchmark = PlannerBenchmark(output_dir='./results')

    # The user's spec: for each size and complexity 20 scenarios -> 60 scenarios per size
    num_per_scale = {
        'SMALL': 60,
        'MEDIUM': 60,
        'LARGE': 60
    }

    print("[1/3] Generating scenarios...")
    scenarios = benchmark.generate_test_scenarios(num_per_scale)
    total_runs = len(scenarios) * 5
    print(f"  Total scenarios: {len(scenarios)}; Total runs (×5 planners): {total_runs}")

    print("[2/3] Running benchmark (this may take many hours)...")
    planners = ["ADAPTIVE", "RRT_STAR", "SAFETY_FIRST", "HPA_STAR", "DSTAR_LITE"]
    results = benchmark.run_benchmark(scenarios, planners)

    print("[3/3] Saving results to results/phase2_scalability.json")
    benchmark.save_results(results, filename='phase2_scalability.json')

    print("Done.")


if __name__ == '__main__':
    main()
