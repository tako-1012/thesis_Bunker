import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats

class ScalabilityAnalyzer:
    def __init__(self, results_file: str):
        """
        Args:
            results_file: ベンチマーク結果JSONファイル
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def analyze_time_complexity(self):
        """
        マップサイズと計算時間の関係を分析
        """
        print("="*60)
        print("Scalability Analysis")
        print("="*60)
        by_planner_size = defaultdict(lambda: defaultdict(list))
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                scenario_name = result['scenario_name']
                map_size = scenario_name.split('_')[1].upper()
                by_planner_size[planner][map_size].append(result['computation_time'])
        print("\n[1] Computation Time by Map Size")
        print("-" * 60)
        map_sizes = ['SMALL', 'MEDIUM', 'LARGE']
        map_dimensions = [10, 50, 100]  # meters
        map_areas = [100, 2500, 10000]  # square meters
        print(f"{'Planner':<15} {'SMALL (10m)':<12} {'MEDIUM (50m)':<13} {'LARGE (100m)':<13}")
        print("-" * 60)
        for planner in ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            times = []
            for size in map_sizes:
                data = by_planner_size[planner][size]
                avg_time = np.mean(data) if data else 0.0
                times.append(avg_time)
            print(f"{planner:<15} {times[0]:>10.2f}s  {times[1]:>10.2f}s  {times[2]:>10.2f}s")
        print("\n[2] Scalability Factor (Time ratio: LARGE/SMALL)")
        print("-" * 60)
        for planner in ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            small_time = np.mean(by_planner_size[planner]['SMALL'])
            large_time = np.mean(by_planner_size[planner]['LARGE'])
            if small_time > 0:
                factor = large_time / small_time
                print(f"{planner:<15}: {factor:6.1f}x slower on LARGE vs SMALL")
        print("\n[3] Time Complexity Estimation")
        print("-" * 60)
        for planner in ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            times = []
            for size in map_sizes:
                data = by_planner_size[planner][size]
                times.append(np.mean(data) if data else 0.0)
            log_areas = np.log(map_areas)
            log_times = np.log([t if t > 0 else 0.001 for t in times])
            slope, intercept, r_value, p_value, std_err = stats.linregress(log_areas, log_times)
            complexity = "O(n^{:.1f})".format(slope)
            print(f"{planner:<15}: {complexity} (R² = {r_value**2:.3f})")
    
    def generate_plots(self):
        """
        スケーラビリティの可視化
        """
        print("\n[4] Generating visualization...")
        by_planner_size = defaultdict(lambda: defaultdict(list))
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                scenario_name = result['scenario_name']
                map_size = scenario_name.split('_')[1].upper()
                by_planner_size[planner][map_size].append(result['computation_time'])
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        map_sizes = ['SMALL', 'MEDIUM', 'LARGE']
        map_dimensions = [10, 50, 100]
        planners = ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']
        colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12', '#9b59b6']
        markers = ['o', 's', '^', 'D', 'v']
        for planner, color, marker in zip(planners, colors, markers):
            times = []
            for size in map_sizes:
                data = by_planner_size[planner][size]
                times.append(np.mean(data) if data else 0.0)
            ax1.plot(map_dimensions, times, marker=marker, color=color, 
                    linewidth=2, markersize=8, label=planner.replace('_', ' '))
        ax1.set_xlabel('Map Size (m)', fontsize=12)
        ax1.set_ylabel('Computation Time (s)', fontsize=12)
        ax1.set_title('Scalability: Linear Scale', fontsize=14, fontweight='bold')
        ax1.legend(fontsize=9)
        ax1.grid(True, alpha=0.3)
        for planner, color, marker in zip(planners, colors, markers):
            times = []
            for size in map_sizes:
                data = by_planner_size[planner][size]
                times.append(np.mean(data) if data else 0.001)
            ax2.plot(map_dimensions, times, marker=marker, color=color, 
                    linewidth=2, markersize=8, label=planner.replace('_', ' '))
        ax2.set_xlabel('Map Size (m)', fontsize=12)
        ax2.set_ylabel('Computation Time (s, log scale)', fontsize=12)
        ax2.set_title('Scalability: Log Scale', fontsize=14, fontweight='bold')
        ax2.set_yscale('log')
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3, which='both')
        plt.tight_layout()
        plt.savefig('scalability_analysis.png', dpi=300, bbox_inches='tight')
        print("  Saved: scalability_analysis.png")
        plt.close()
        print("\n" + "="*60)
        print("Scalability Analysis Complete!")
        print("="*60)

if __name__ == '__main__':
    analyzer = ScalabilityAnalyzer('benchmark_results/full_benchmark_results.json')
    analyzer.analyze_time_complexity()
    analyzer.generate_plots()
