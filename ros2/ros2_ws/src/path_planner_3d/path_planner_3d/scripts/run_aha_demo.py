"""
Run a tiny benchmark that exercises AHA* once.
"""
from path_planner_3d.path_planner_3d.benchmark_planners import PlannerBenchmark

def main():
    bench = PlannerBenchmark(output_dir='./benchmark_results_demo')
    scenarios = bench.generate_test_scenarios({'SMALL':1,'MEDIUM':0,'LARGE':0})
    results = bench.run_benchmark(scenarios, planners=['AHA_STAR'])
    for r in results:
        print(r)

if __name__ == '__main__':
    main()
