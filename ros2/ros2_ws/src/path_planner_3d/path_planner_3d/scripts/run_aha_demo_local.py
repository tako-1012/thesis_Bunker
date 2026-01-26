#!/usr/bin/env python3
"""
Local runner that adjusts sys.path so modules in this package can be imported
as top-level modules (convenience for quick demos).
"""
import sys
import os

root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
pkg_dir = root
repo_src = os.path.abspath(os.path.join(root, '..'))

sys.path.insert(0, pkg_dir)
sys.path.insert(0, repo_src)

from benchmark_planners import PlannerBenchmark

def main():
    bench = PlannerBenchmark(output_dir='./benchmark_results_demo')
    scenarios = bench.generate_test_scenarios({'SMALL':1,'MEDIUM':0,'LARGE':0})
    results = bench.run_benchmark(scenarios, planners=['AHA_STAR'])
    for r in results:
        print(r)

if __name__ == '__main__':
    main()
