import json
import numpy as np
import matplotlib.pyplot as plt
from collections import defaultdict
from scipy import stats

class AblationAnalyzer:
    def __init__(self, results_file: str):
        """
        Args:
            results_file: アブレーション実験結果JSONファイル
        """
        with open(results_file, 'r') as f:
            self.results = json.load(f)
    
    def analyze_performance(self):
        """各バリエーションの性能を分析"""
        print("="*60)
        print("Ablation Study Analysis")
        print("="*60)
        
        # バリエーション別に集計
        by_variant = defaultdict(lambda: {
            'times': [],
            'success_count': 0,
            'total_count': 0,
            'path_lengths': []
        })
        
        for result in self.results:
            variant = result['variant_name']
            by_variant[variant]['total_count'] += 1
            
            if result['success']:
                by_variant[variant]['success_count'] += 1
                by_variant[variant]['times'].append(result['computation_time'])
                by_variant[variant]['path_lengths'].append(result['path_length'])
        
        print("\n[1] Performance Summary")
        print("-" * 60)
        print(f"{'Variant':<25} {'Success':<10} {'Avg Time (s)':<15} {'Avg Path (m)':<15}")
        print("-" * 60)
        
        variants = ['ADAPTIVE_FULL', 'ADAPTIVE_NO_FALLBACK', 'ADAPTIVE_FIXED_ASTAR', 'ADAPTIVE_FIXED_RRT']
        
        for variant in variants:
            data = by_variant[variant]
            success_rate = (data['success_count'] / data['total_count'] * 100) if data['total_count'] > 0 else 0
            avg_time = np.mean(data['times']) if data['times'] else 0
            avg_path = np.mean(data['path_lengths']) if data['path_lengths'] else 0
            
            print(f"{variant:<25} {success_rate:>6.1f}%   {avg_time:>12.2f}   {avg_path:>12.2f}")
    
    def analyze_feature_contribution(self):
        """各機能の貢献度を分析"""
        print("\n[2] Feature Contribution Analysis")
        print("-" * 60)
        
        # バリエーション別データ収集
        by_variant = defaultdict(list)
        
        for result in self.results:
            if result['success']:
                variant = result['variant_name']
                by_variant[variant].append(result['computation_time'])
        
        # ADAPTIVE_FULLを基準とする
        full_times = by_variant['ADAPTIVE_FULL']
        full_mean = np.mean(full_times)
        
        print(f"\nBaseline (ADAPTIVE_FULL): {full_mean:.3f}s")
        print("\nFeature Removal Impact:")
        
        # フォールバック機構の効果
        no_fallback_times = by_variant['ADAPTIVE_NO_FALLBACK']
        if no_fallback_times:
            no_fallback_mean = np.mean(no_fallback_times)
            impact = ((no_fallback_mean - full_mean) / full_mean * 100)
            
            # 統計的検定
            t_stat, p_value = stats.ttest_ind(full_times, no_fallback_times)
            
            print(f"\n  Fallback Mechanism:")
            print(f"    Without fallback: {no_fallback_mean:.3f}s ({impact:+.1f}%)")
            print(f"    Statistical significance: p = {p_value:.4f}")
        
        # 複雑度判定機構の効果（FIXED_ASTAR vs FULL）
        fixed_astar_times = by_variant['ADAPTIVE_FIXED_ASTAR']
        if fixed_astar_times:
            fixed_astar_mean = np.mean(fixed_astar_times)
            impact = ((fixed_astar_mean - full_mean) / full_mean * 100)
            
            t_stat, p_value = stats.ttest_ind(full_times, fixed_astar_times)
            
            print(f"\n  Adaptive Selection (vs Fixed A*):")
            print(f"    Fixed A*: {fixed_astar_mean:.3f}s ({impact:+.1f}%)")
            print(f"    Statistical significance: p = {p_value:.4f}")
        
        # RRT*固定との比較
        fixed_rrt_times = by_variant['ADAPTIVE_FIXED_RRT']
        if fixed_rrt_times:
            fixed_rrt_mean = np.mean(fixed_rrt_times)
            speedup = fixed_rrt_mean / full_mean
            
            t_stat, p_value = stats.ttest_ind(full_times, fixed_rrt_times)
            
            print(f"\n  Adaptive Selection (vs Fixed RRT*):")
            print(f"    Fixed RRT*: {fixed_rrt_mean:.3f}s ({speedup:.1f}x slower)")
            print(f"    Statistical significance: p = {p_value:.4f}")
    
    def analyze_by_complexity(self):
        """複雑度別の分析"""
        print("\n[3] Performance by Terrain Complexity")
        print("-" * 60)
        
        # 複雑度別・バリエーション別に集計
        by_complexity_variant = defaultdict(lambda: defaultdict(list))
        
        for result in self.results:
            if result['success']:
                complexity = result['complexity']
                variant = result['variant_name']
                by_complexity_variant[complexity][variant].append(result['computation_time'])
        
        for complexity in ['SIMPLE', 'MODERATE', 'COMPLEX']:
            print(f"\n{complexity}:")
            
            full_times = by_complexity_variant[complexity]['ADAPTIVE_FULL']
            fixed_rrt_times = by_complexity_variant[complexity]['ADAPTIVE_FIXED_RRT']
            
            if full_times and fixed_rrt_times:
                full_mean = np.mean(full_times)
                fixed_rrt_mean = np.mean(fixed_rrt_times)
                speedup = fixed_rrt_mean / full_mean
                
                print(f"  ADAPTIVE_FULL:     {full_mean:7.2f}s")
                print(f"  ADAPTIVE_FIXED_RRT: {fixed_rrt_mean:7.2f}s")
                print(f"  Speedup:           {speedup:7.1f}x")
    
    def generate_plots(self):
        """可視化"""
        print("\n[4] Generating visualization...")
        
        # データ収集
        by_variant = defaultdict(list)
        
        for result in self.results:
            if result['success']:
                variant = result['variant_name']
                by_variant[variant].append(result['computation_time'])
        
        # 箱ひげ図
        fig, ax = plt.subplots(figsize=(10, 6))
        
        variants = ['ADAPTIVE_FULL', 'ADAPTIVE_NO_FALLBACK', 'ADAPTIVE_FIXED_ASTAR', 'ADAPTIVE_FIXED_RRT']
        labels = ['FULL\n(Proposed)', 'No Fallback', 'Fixed A*', 'Fixed RRT*']
        colors = ['#2ecc71', '#e67e22', '#3498db', '#e74c3c']
        
        data = [by_variant[v] for v in variants]
        
        bp = ax.boxplot(data, labels=labels, patch_artist=True, notch=True)
        
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)
        
        ax.set_ylabel('Computation Time (s)', fontsize=12)
        ax.set_title('Ablation Study: Feature Contribution', fontsize=14, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
        
        # 平均値を追加
        means = [np.mean(d) for d in data]
        ax.plot(range(1, len(means)+1), means, 'D', color='red', markersize=8, label='Mean', zorder=3)
        ax.legend()
        
        plt.tight_layout()
        plt.savefig('ablation_analysis.png', dpi=300, bbox_inches='tight')
        print("  Saved: ablation_analysis.png")
        
        plt.close()
        
        # 複雑度別の比較
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        
        complexities = ['SIMPLE', 'MODERATE', 'COMPLEX']
        
        for idx, complexity in enumerate(complexities):
            ax = axes[idx]
            
            # 複雑度別データ収集
            complexity_data = []
            for variant in variants:
                times = [r['computation_time'] for r in self.results 
                        if r['success'] and r['variant_name'] == variant and r['complexity'] == complexity]
                complexity_data.append(times)
            
            bp = ax.boxplot(complexity_data, labels=labels, patch_artist=True)
            
            for patch, color in zip(bp['boxes'], colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            
            ax.set_ylabel('Computation Time (s)', fontsize=10)
            ax.set_title(f'{complexity} Terrain', fontsize=12, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            ax.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig('ablation_by_complexity.png', dpi=300, bbox_inches='tight')
        print("  Saved: ablation_by_complexity.png")
        
        plt.close()
        
        print("\n" + "="*60)
        print("Ablation Analysis Complete!")
        print("="*60)


if __name__ == '__main__':
    analyzer = AblationAnalyzer('ablation_results/ablation_results.json')
    
    analyzer.analyze_performance()
    analyzer.analyze_feature_contribution()
    analyzer.analyze_by_complexity()
    analyzer.generate_plots()
