import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats
from typing import Dict, List, Tuple

class StatisticalAnalyzer:
    def __init__(self, results_file: str):
        """
        Args:
            results_file: ベンチマーク結果JSONファイル
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def calculate_cohens_d(self, group1: List[float], group2: List[float]) -> float:
        """
        Cohen's d（効果量）を計算
        """
        mean1 = np.mean(group1)
        mean2 = np.mean(group2)
        std1 = np.std(group1, ddof=1)
        std2 = np.std(group2, ddof=1)
        n1 = len(group1)
        n2 = len(group2)
        pooled_std = np.sqrt(((n1 - 1) * std1**2 + (n2 - 1) * std2**2) / (n1 + n2 - 2))
        if pooled_std == 0:
            return 0.0
        d = (mean1 - mean2) / pooled_std
        return abs(d)
    
    def perform_t_tests(self):
        """
        ADAPTIVEと各手法のt検定を実施
        """
        print("="*60)
        print("Statistical Analysis")
        print("="*60)
        by_planner = defaultdict(list)
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                by_planner[planner].append(result['computation_time'])
        adaptive_times = by_planner['ADAPTIVE']
        print(f"\n[1] Sample Statistics")
        print("-" * 60)
        print(f"{'Planner':<15} {'n':<6} {'Mean (s)':<12} {'Std (s)':<12} {'95% CI':<20}")
        print("-" * 60)
        stats_data = {}
        for planner in ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            times = by_planner[planner]
            n = len(times)
            mean = np.mean(times)
            std = np.std(times, ddof=1)
            ci = stats.t.interval(0.95, n-1, loc=mean, scale=std/np.sqrt(n))
            stats_data[planner] = {
                'n': n,
                'mean': mean,
                'std': std,
                'ci': ci
            }
            print(f"{planner:<15} {n:<6} {mean:<12.3f} {std:<12.3f} [{ci[0]:.3f}, {ci[1]:.3f}]")
        print(f"\n[2] T-test Results (ADAPTIVE vs Others)")
        print("-" * 60)
        print("{:<30} {:<15} {:<12} {:<12} {:<15}".format('Comparison', 't-statistic', 'p-value', "Cohen's d", 'Effect'))
        print("-" * 60)
        for planner in ['RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            other_times = by_planner[planner]
            t_stat, p_value = stats.ttest_ind(adaptive_times, other_times)
            cohens_d = self.calculate_cohens_d(adaptive_times, other_times)
            if cohens_d < 0.2:
                effect = "Small"
            elif cohens_d < 0.5:
                effect = "Medium"
            elif cohens_d < 0.8:
                effect = "Large"
            else:
                effect = "Very Large"
            significance = "***" if p_value < 0.001 else "**" if p_value < 0.01 else "*" if p_value < 0.05 else "ns"
            comparison = f"ADAPTIVE vs {planner}"
            print(f"{comparison:<30} {t_stat:<15.3f} {p_value:<12.6f} {cohens_d:<12.3f} {effect:<15}")
        print("\n[3] Statistical Significance")
        print("-" * 60)
        print("Significance levels: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant")
        print("\nConclusion:")
        significant_comparisons = []
        for planner in ['RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
            other_times = by_planner[planner]
            t_stat, p_value = stats.ttest_ind(adaptive_times, other_times)
            if p_value < 0.001:
                adaptive_mean = np.mean(adaptive_times)
                other_mean = np.mean(other_times)
                if adaptive_mean < other_mean:
                    significant_comparisons.append(
                        f"  - ADAPTIVE is significantly faster than {planner} (p < 0.001)"
                    )
        for comp in significant_comparisons:
            print(comp)
        print("\n[4] Effect Size Interpretation")
        print("-" * 60)
        print("Cohen's d interpretation:")
        print("  d < 0.2  : Small effect")
        print("  0.2 ≤ d < 0.5 : Medium effect")
        print("  0.5 ≤ d < 0.8 : Large effect")
        print("  d ≥ 0.8  : Very large effect")
    
    def analyze_by_map_size(self):
        """
        マップサイズ別の統計分析
        """
        print(f"\n[5] Statistical Analysis by Map Size")
        print("-" * 60)
        for map_size in ['SMALL', 'MEDIUM', 'LARGE']:
            print(f"\n{map_size} ({['10m', '50m', '100m'][['SMALL', 'MEDIUM', 'LARGE'].index(map_size)]}):")
            by_planner = defaultdict(list)
            for result in self.results:
                if result['success']:
                    scenario_name = result['scenario_name']
                    size = scenario_name.split('_')[1].upper()
                    if size == map_size:
                        planner = result['planner_name']
                        by_planner[planner].append(result['computation_time'])
            adaptive_times = by_planner['ADAPTIVE']
            if 'RRT_STAR' in by_planner:
                rrt_times = by_planner['RRT_STAR']
                t_stat, p_value = stats.ttest_ind(adaptive_times, rrt_times)
                cohens_d = self.calculate_cohens_d(adaptive_times, rrt_times)
                adaptive_mean = np.mean(adaptive_times)
                rrt_mean = np.mean(rrt_times)
                speedup = rrt_mean / adaptive_mean if adaptive_mean > 0 else 0
                print(f"  ADAPTIVE vs RRT*:")
                print(f"    Mean time: {adaptive_mean:.3f}s vs {rrt_mean:.3f}s")
                print(f"    Speedup: {speedup:.1f}x")
                print(f"    p-value: {p_value:.6f}")
                print(f"    Cohen's d: {cohens_d:.3f}")
    
    def generate_plots(self):
        """
        統計分析の可視化
        """
        print(f"\n[6] Generating visualization...")
        by_planner = defaultdict(list)
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                by_planner[planner].append(result['computation_time'])
        fig, ax = plt.subplots(figsize=(10, 6))
        planners = ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']
        colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12', '#9b59b6']
        means = []
        ci_lower = []
        ci_upper = []
        for planner in planners:
            times = by_planner[planner]
            n = len(times)
            mean = np.mean(times)
            std = np.std(times, ddof=1)
            ci = stats.t.interval(0.95, n-1, loc=mean, scale=std/np.sqrt(n))
            means.append(mean)
            ci_lower.append(mean - ci[0])
            ci_upper.append(ci[1] - mean)
        x_pos = np.arange(len(planners))
        bars = ax.bar(x_pos, means, color=colors, alpha=0.7, edgecolor='black')
        ax.errorbar(x_pos, means, yerr=[ci_lower, ci_upper], fmt='none', 
                   ecolor='black', capsize=5, capthick=2)
        ax.set_ylabel('Computation Time (s)', fontsize=12)
        ax.set_title('Mean Computation Time with 95% Confidence Intervals', 
                    fontsize=14, fontweight='bold')
        ax.set_xticks(x_pos)
        ax.set_xticklabels([p.replace('_', '\n') for p in planners])
        ax.grid(axis='y', alpha=0.3)
        plt.tight_layout()
        plt.savefig('statistical_analysis.png', dpi=300, bbox_inches='tight')
        print("  Saved: statistical_analysis.png")
        plt.close()
        print("\n" + "="*60)
        print("Statistical Analysis Complete!")
        print("="*60)

if __name__ == '__main__':
    analyzer = StatisticalAnalyzer('benchmark_results/full_benchmark_results.json')
    analyzer.perform_t_tests()
    analyzer.analyze_by_map_size()
    analyzer.generate_plots()
