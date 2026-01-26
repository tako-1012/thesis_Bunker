#!/usr/bin/env python3
"""Run a minimal AHA* benchmark (single SMALL scenario) to validate integration."""
import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(__file__))
# src_root is one level above the package directory (e.g. .../ros2_ws/src)
src_root = os.path.abspath(os.path.join(ROOT, '..'))
if src_root not in sys.path:
    sys.path.insert(0, src_root)
# Also ensure the package directory itself is importable as top-level modules
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Import via package so relative imports inside the library resolve correctly
BenchmarkModule = importlib.import_module('path_planner_3d.benchmark_planners')
PlannerBenchmark = getattr(BenchmarkModule, 'PlannerBenchmark')

def main():
    pb = PlannerBenchmark(output_dir='/tmp/aha_benchmark_test')
    scenarios = pb.generate_test_scenarios({'SMALL':1,'MEDIUM':0,'LARGE':0})
    results = pb.run_benchmark(scenarios, planners=['AHA_STAR'])
    for r in results:
        print(r)

if __name__ == '__main__':
    main()
