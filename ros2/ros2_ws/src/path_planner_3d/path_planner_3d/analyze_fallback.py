import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from typing import Dict, List

class FallbackAnalyzer:
    def __init__(self, results_file: str):
        """
        Args:
            results_file: ベンチマーク結果JSONファイル
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def analyze_planner_usage(self):
        """
        ADAPTIVEプランナーがどのプランナーを選択したかを分析
        
        注: 現在の実装ではプランナー選択情報が記録されていないため、
        地形複雑度から推測する
        """
        print("="*60)
        print("Fallback Analysis")
        print("="*60)
        
        # 地形複雑度別にADAPTIVEの結果を集計
        by_complexity = defaultdict(lambda: {'count': 0, 'avg_time': []})
        
        for result in self.results:
            if result['planner_name'] == 'ADAPTIVE' and result['success']:
                complexity = result['complexity']
                by_complexity[complexity]['count'] += 1
                by_complexity[complexity]['avg_time'].append(result['computation_time'])
        
        print("\n[1] ADAPTIVE Performance by Terrain Complexity")
        print("-" * 60)
        for complexity in ['SIMPLE', 'MODERATE', 'COMPLEX']:
            data = by_complexity[complexity]
            if data['count'] > 0:
                avg_time = np.mean(data['avg_time'])
                std_time = np.std(data['avg_time'])
                print(f"{complexity:12s}: {data['count']:3d} scenarios, "
                      f"avg time: {avg_time:6.2f}s ± {std_time:5.2f}s")
        
        # 推定されるプランナー使用頻度
        print("\n[2] Estimated Planner Selection")
        print("-" * 60)
        print("Based on terrain complexity thresholds:")
        print("  SIMPLE   (< 0.15): A* variant (D* Lite)")
        print("  MODERATE (< 0.55): RRT*")
        print("  COMPLEX  (≥ 0.55): SAFETY_FIRST")
        
        # 実際のデータから推定
        total_scenarios = sum(data['count'] for data in by_complexity.values())
        print(f"\nEstimated usage across {total_scenarios} scenarios:")
        for complexity in ['SIMPLE', 'MODERATE', 'COMPLEX']:
            count = by_complexity[complexity]['count']
            percentage = (count / total_scenarios * 100) if total_scenarios > 0 else 0
            print(f"  {complexity:12s}: {count:3d} scenarios ({percentage:5.1f}%)")
    
    def compare_with_baseline(self):
        """
        ADAPTIVEと他手法の計算時間を比較
        """
        print("\n[3] Performance Comparison")
        print("-" * 60)
        
        # マップサイズ別に集計
        by_planner_size = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                # scenario_name から map_size を抽出
                scenario_name = result['scenario_name']
                map_size = scenario_name.split('_')[1].upper()
                
                by_planner_size[planner][map_size].append(result['computation_time'])
        
        # 比較表を作成
        for map_size in ['SMALL', 'MEDIUM', 'LARGE']:
            print(f"\n{map_size} ({['10m', '50m', '100m'][['SMALL', 'MEDIUM', 'LARGE'].index(map_size)]}):")
            
            adaptive_time = np.mean(by_planner_size['ADAPTIVE'][map_size])
            
            for planner in ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']:
                times = by_planner_size[planner][map_size]
                if times:
                    avg_time = np.mean(times)
                    speedup = avg_time / adaptive_time if adaptive_time > 0 else 0
                    print(f"  {planner:15s}: {avg_time:7.2f}s  (x{speedup:5.1f})")
    
    def generate_plots(self):
        """
        可視化用のグラフを生成
        """
        print("\n[4] Generating visualization...")
        
        # データ集計
        planner_times = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            if result['success']:
                planner = result['planner_name']
                scenario_name = result['scenario_name']
                map_size = scenario_name.split('_')[1].upper()
                planner_times[planner][map_size].append(result['computation_time'])
        
        # グラフ作成
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        map_sizes = ['SMALL', 'MEDIUM', 'LARGE']
        map_labels = ['SMALL\n(10m×10m)', 'MEDIUM\n(50m×50m)', 'LARGE\n(100m×100m)']
        
        planners = ['ADAPTIVE', 'RRT_STAR', 'SAFETY_FIRST', 'HPA_STAR', 'DSTAR_LITE']
        colors = ['#2ecc71', '#e74c3c', '#3498db', '#f39c12', '#9b59b6']
        
        for idx, (map_size, label) in enumerate(zip(map_sizes, map_labels)):
            ax = axes[idx]
            
            means = []
            stds = []
            for planner in planners:
                times = planner_times[planner][map_size]
                means.append(np.mean(times) if times else 0)
                stds.append(np.std(times) if times else 0)
            
            x_pos = np.arange(len(planners))
            bars = ax.bar(x_pos, means, yerr=stds, capsize=5, color=colors, alpha=0.7)
            
            ax.set_ylabel('Computation Time (s)', fontsize=12)
            ax.set_title(label, fontsize=14, fontweight='bold')
            ax.set_xticks(x_pos)
            ax.set_xticklabels([p.replace('_', '\n') for p in planners], 
                               rotation=0, fontsize=9)
            ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('fallback_analysis_comparison.png', dpi=300, bbox_inches='tight')
        print("  Saved: fallback_analysis_comparison.png")
        
        plt.close()
        
        print("\n" + "="*60)
        print("Fallback Analysis Complete!")
        print("="*60)


if __name__ == '__main__':
    analyzer = FallbackAnalyzer('benchmark_results/full_benchmark_results.json')
    
    analyzer.analyze_planner_usage()
    analyzer.compare_with_baseline()
    analyzer.generate_plots()
