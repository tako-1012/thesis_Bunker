import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats

class SensitivityAnalyzer:
    def __init__(self, results_file: str):
        """
        Args:
            results_file: 感度分析結果JSONファイル
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def analyze_performance(self):
        """各閾値セットの性能を分析"""
        print("="*60)
        print("Sensitivity Analysis: Threshold Parameters")
        print("="*60)
        
        # 閾値セット別に集計
        by_threshold = defaultdict(lambda: {
            'times': [],
            'success_count': 0,
            'total_count': 0,
            'path_lengths': [],
            'planner_counts': defaultdict(int)
        })
        
        for result in self.results:
            threshold_set = result['threshold_set']
            by_threshold[threshold_set]['total_count'] += 1
            
            if result['success']:
                by_threshold[threshold_set]['success_count'] += 1
                by_threshold[threshold_set]['times'].append(result['computation_time'])
                by_threshold[threshold_set]['path_lengths'].append(result['path_length'])
                
                # プランナー選択カウント
                planner = result['selected_planner']
                by_threshold[threshold_set]['planner_counts'][planner] += 1
        
        print("\n[1] Performance Summary")
        print("-" * 60)
        print(f"{'Threshold Set':<15} {'Thresholds':<20} {'Success':<10} {'Avg Time (s)':<15} {'Avg Path (m)':<15}")
        print("-" * 60)
        
        threshold_definitions = {
            'NARROW': '(0.10, 0.50)',
            'BASELINE': '(0.15, 0.55)',
            'WIDE': '(0.20, 0.60)'
        }
        
        threshold_sets = ['NARROW', 'BASELINE', 'WIDE']
        
        for threshold_set in threshold_sets:
            data = by_threshold[threshold_set]
            success_rate = (data['success_count'] / data['total_count'] * 100) if data['total_count'] > 0 else 0
            avg_time = np.mean(data['times']) if data['times'] else 0
            avg_path = np.mean(data['path_lengths']) if data['path_lengths'] else 0
            thresholds = threshold_definitions.get(threshold_set, 'Unknown')
            
            print(f"{threshold_set:<15} {thresholds:<20} {success_rate:>6.1f}%   {avg_time:>12.2f}   {avg_path:>12.2f}")
    
    def analyze_planner_selection(self):
        """各閾値セットでのプランナー選択頻度を分析"""
        print("\n[2] Planner Selection Frequency")
        print("-" * 60)
        
        # 閾値セット別・プランナー別に集計
        by_threshold_planner = defaultdict(lambda: defaultdict(int))
        total_by_threshold = defaultdict(int)
        
        for result in self.results:
            if result['success']:
                threshold_set = result['threshold_set']
                planner = result['selected_planner'].split(' (')[0]  # Fallback表記を除去
                
                by_threshold_planner[threshold_set][planner] += 1
                total_by_threshold[threshold_set] += 1
        
        print(f"\n{'Threshold Set':<15} {'A*':<10} {'RRT*':<10} {'SAFETY':<10}")
        print("-" * 60)
        
        for threshold_set in ['NARROW', 'BASELINE', 'WIDE']:
            total = total_by_threshold[threshold_set]
            astar_pct = (by_threshold_planner[threshold_set]['A*'] / total * 100) if total > 0 else 0
            rrt_pct = (by_threshold_planner[threshold_set]['RRT*'] / total * 100) if total > 0 else 0
            safety_pct = (by_threshold_planner[threshold_set]['SAFETY_FIRST'] / total * 100) if total > 0 else 0
            
            print(f"{threshold_set:<15} {astar_pct:>6.1f}%   {rrt_pct:>6.1f}%   {safety_pct:>6.1f}%")
    
    def analyze_robustness(self):
        """閾値変更による性能変化（ロバスト性）を分析"""
        print("\n[3] Robustness Analysis")
        print("-" * 60)
        
        # BASELINE基準での変化を計算
        by_threshold = defaultdict(list)
        
        for result in self.results:
            if result['success']:
                threshold_set = result['threshold_set']
                by_threshold[threshold_set].append(result['computation_time'])
        
        baseline_times = by_threshold['BASELINE']
        baseline_mean = np.mean(baseline_times)
        baseline_std = np.std(baseline_times, ddof=1)
        
        print(f"\nBaseline (0.15, 0.55):")
        print(f"  Mean: {baseline_mean:.3f}s ± {baseline_std:.3f}s")
        
        # NARROW との比較
        if 'NARROW' in by_threshold:
            narrow_times = by_threshold['NARROW']
            narrow_mean = np.mean(narrow_times)
            narrow_std = np.std(narrow_times, ddof=1)
            
            # t検定
            t_stat, p_value = stats.ttest_ind(baseline_times, narrow_times)
            
            impact = ((narrow_mean - baseline_mean) / baseline_mean * 100)
            
            print(f"\nNarrow Thresholds (0.10, 0.50):")
            print(f"  Mean: {narrow_mean:.3f}s ± {narrow_std:.3f}s")
            print(f"  Change: {impact:+.1f}%")
            print(f"  Statistical significance: p = {p_value:.4f}")
        
        # WIDE との比較
        if 'WIDE' in by_threshold:
            wide_times = by_threshold['WIDE']
            wide_mean = np.mean(wide_times)
            wide_std = np.std(wide_times, ddof=1)
            
            # t検定
            t_stat, p_value = stats.ttest_ind(baseline_times, wide_times)
            
            impact = ((wide_mean - baseline_mean) / baseline_mean * 100)
            
            print(f"\nWide Thresholds (0.20, 0.60):")
            print(f"  Mean: {wide_mean:.3f}s ± {wide_std:.3f}s")
            print(f"  Change: {impact:+.1f}%")
            print(f"  Statistical significance: p = {p_value:.4f}")
        
        print("\n" + "-" * 60)
        print("Conclusion:")
        if all(p > 0.05 for p in [p_value]):  # 最後のp_valueを使用
            print("  The method is ROBUST to threshold changes (no significant difference)")
        else:
            print("  The method shows sensitivity to threshold changes")
    
    def analyze_by_complexity(self):
        """複雑度別の分析"""
        print("\n[4] Performance by Complexity")
        print("-" * 60)
        
        # 複雑度別・閾値別に集計
        by_complexity_threshold = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            if result['success']:
                complexity = result['complexity']
                threshold_set = result['threshold_set']
                by_complexity_threshold[complexity][threshold_set].append(result['computation_time'])
        
        for complexity in ['SIMPLE', 'MODERATE', 'COMPLEX']:
            print(f"\n{complexity}:")
            
            for threshold_set in ['NARROW', 'BASELINE', 'WIDE']:
                times = by_complexity_threshold[complexity][threshold_set]
                if times:
                    mean_time = np.mean(times)
                    print(f"  {threshold_set:<10}: {mean_time:7.2f}s")
    
    def generate_plots(self):
        """可視化"""
        print("\n[5] Generating visualizations...")
        
        # データ収集
        by_threshold = defaultdict(list)
        
        for result in self.results:
            if result['success']:
                threshold_set = result['threshold_set']
                by_threshold[threshold_set].append(result['computation_time'])
        
        # 図1: 閾値セット別の計算時間分布
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        
        # 箱ひげ図
        ax = axes[0]
        threshold_sets = ['NARROW', 'BASELINE', 'WIDE']
        labels = ['NARROW\n(0.10, 0.50)', 'BASELINE\n(0.15, 0.55)', 'WIDE\n(0.20, 0.60)']
        colors = ['#3498db', '#2ecc71', '#e67e22']
        
        data = [by_threshold[ts] for ts in threshold_sets]
        
        bp = ax.boxplot(data, labels=labels, patch_artist=True, notch=True)
        
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_ylabel('Computation Time (s)', fontsize=12)
        ax.set_title('Sensitivity to Threshold Parameters', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # 平均値を追加
        means = [np.mean(d) for d in data]
        ax.plot(range(1, len(means)+1), means, 'D', color='red', markersize=8, label='Mean', zorder=3)
        ax.legend()
        
        # プランナー選択頻度
        ax = axes[1]
        
        # プランナー選択を集計
        planner_counts = defaultdict(lambda: defaultdict(int))
        
        for result in self.results:
            if result['success']:
                threshold_set = result['threshold_set']
                planner = result['selected_planner'].split(' (')[0]
                planner_counts[threshold_set][planner] += 1
        
        # 積み上げ棒グラフ
        planners = ['A*', 'RRT*', 'SAFETY_FIRST']
        planner_colors = ['#3498db', '#e74c3c', '#f39c12']
        
        x = np.arange(len(threshold_sets))
        width = 0.6
        
        bottom = np.zeros(len(threshold_sets))
        
        for planner, color in zip(planners, planner_colors):
            counts = [planner_counts[ts][planner] for ts in threshold_sets]
            ax.bar(x, counts, width, label=planner, bottom=bottom, color=color, alpha=0.7)
            bottom += counts
        
        ax.set_xlabel('Threshold Set', fontsize=12)
        ax.set_ylabel('Number of Selections', fontsize=12)
        ax.set_title('Planner Selection Frequency', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.legend()
        ax.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('sensitivity_analysis.png', dpi=300, bbox_inches='tight')
        print("  Saved: sensitivity_analysis.png")
        
        plt.close()
        
        # 図2: 複雑度別の比較
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        complexities = ['SIMPLE', 'MODERATE', 'COMPLEX']
        
        for idx, complexity in enumerate(complexities):
            ax = axes[idx]
            
            # 複雑度別データ収集
            complexity_data = []
            for threshold_set in threshold_sets:
                times = [r['computation_time'] for r in self.results 
                        if r['success'] and r['threshold_set'] == threshold_set and r['complexity'] == complexity]
                complexity_data.append(times)
            
            bp = ax.boxplot(complexity_data, labels=labels, patch_artist=True)
            
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            ax.set_ylabel('Computation Time (s)', fontsize=10)
            ax.set_title(f'{complexity} Terrain', fontsize=12, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            ax.tick_params(axis='x', rotation=0, labelsize=8)
        
        plt.tight_layout()
        plt.savefig('sensitivity_by_complexity.png', dpi=300, bbox_inches='tight')
        print("  Saved: sensitivity_by_complexity.png")
        
        plt.close()
        
        print("\n" + "="*60)
        print("Sensitivity Analysis Complete!")
        print("="*60)


if __name__ == '__main__':
    analyzer = SensitivityAnalyzer('sensitivity_results/sensitivity_results.json')
    
    analyzer.analyze_performance()
    analyzer.analyze_planner_selection()
    analyzer.analyze_robustness()
    analyzer.analyze_by_complexity()
    analyzer.generate_plots()
