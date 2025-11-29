"""
統計的検定

実験結果の統計的有意性を検証
"""
import numpy as np
from scipy import stats
from scipy.stats import mannwhitneyu, kruskal, friedmanchisquare
import json
from pathlib import Path
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
import seaborn as sns

class StatisticalTester:
    """統計的検定クラス"""
    
    def __init__(self, results_file: str):
        """
        初期化
        
        Args:
            results_file: 実験結果ファイル
        """
        with open(results_file) as f:
            self.data = json.load(f)
    
    def compare_success_rates(self, algo1: str, algo2: str) -> Dict:
        """
        2つのアルゴリズムの成功率を統計的に比較
        
        Args:
            algo1: アルゴリズム1
            algo2: アルゴリズム2
        
        Returns:
            Dict: 検定結果
        """
        print(f"\n{'='*70}")
        print(f"成功率比較: {algo1} vs {algo2}")
        print(f"{'='*70}")
        
        # 全地形からデータを集める
        algo1_results = []
        algo2_results = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            if algo1 in terrain_results and algo2 in terrain_results:
                # 成功=1, 失敗=0のバイナリデータ
                for r in terrain_results[algo1]:
                    algo1_results.append(1 if r.get('success', False) else 0)
                
                for r in terrain_results[algo2]:
                    algo2_results.append(1 if r.get('success', False) else 0)
        
        if not algo1_results or not algo2_results:
            print("データ不足")
            return {}
        
        # 成功率
        rate1 = np.mean(algo1_results) * 100
        rate2 = np.mean(algo2_results) * 100
        
        print(f"\n{algo1}: {rate1:.1f}% ({sum(algo1_results)}/{len(algo1_results)})")
        print(f"{algo2}: {rate2:.1f}% ({sum(algo2_results)}/{len(algo2_results)})")
        print(f"差: {rate1 - rate2:.1f}ポイント")
        
        # カイ二乗検定
        contingency_table = [
            [sum(algo1_results), len(algo1_results) - sum(algo1_results)],
            [sum(algo2_results), len(algo2_results) - sum(algo2_results)]
        ]
        
        chi2, p_value = stats.chi2_contingency(contingency_table)[:2]
        
        print(f"\nカイ二乗検定:")
        print(f"  χ² = {chi2:.4f}")
        print(f"  p値 = {p_value:.4f}")
        
        if p_value < 0.001:
            print(f"  結論: 極めて有意な差あり (p < 0.001) ***")
        elif p_value < 0.01:
            print(f"  結論: 非常に有意な差あり (p < 0.01) **")
        elif p_value < 0.05:
            print(f"  結論: 有意な差あり (p < 0.05) *")
        else:
            print(f"  結論: 有意な差なし (p >= 0.05)")
        
        # 効果量（Cohen's h）
        effect_size = 2 * (np.arcsin(np.sqrt(rate1/100)) - np.arcsin(np.sqrt(rate2/100)))
        print(f"\n効果量 (Cohen's h): {effect_size:.4f}")
        
        if abs(effect_size) < 0.2:
            print("  効果: 小")
        elif abs(effect_size) < 0.5:
            print("  効果: 中")
        else:
            print("  効果: 大")
        
        return {
            'algo1': algo1,
            'algo2': algo2,
            'rate1': rate1,
            'rate2': rate2,
            'chi2': chi2,
            'p_value': p_value,
            'effect_size': effect_size,
            'significant': p_value < 0.05
        }
    
    def compare_computation_times(self, algo1: str, algo2: str) -> Dict:
        """
        2つのアルゴリズムの計算時間を統計的に比較
        
        Args:
            algo1: アルゴリズム1
            algo2: アルゴリズム2
        
        Returns:
            Dict: 検定結果
        """
        print(f"\n{'='*70}")
        print(f"計算時間比較: {algo1} vs {algo2}")
        print(f"{'='*70}")
        
        # 成功したケースのみの計算時間を集める
        algo1_times = []
        algo2_times = []
        
        if 'results' not in self.data:
            return {}
        
        for terrain, terrain_results in self.data['results'].items():
            if algo1 in terrain_results and algo2 in terrain_results:
                for r in terrain_results[algo1]:
                    if r.get('success', False):
                        algo1_times.append(r['computation_time'])
                
                for r in terrain_results[algo2]:
                    if r.get('success', False):
                        algo2_times.append(r['computation_time'])
        
        if not algo1_times or not algo2_times:
            print("データ不足")
            return {}
        
        # 基本統計
        mean1 = np.mean(algo1_times)
        mean2 = np.mean(algo2_times)
        median1 = np.median(algo1_times)
        median2 = np.median(algo2_times)
        std1 = np.std(algo1_times)
        std2 = np.std(algo2_times)
        
        print(f"\n{algo1}:")
        print(f"  平均: {mean1:.2f}s (±{std1:.2f})")
        print(f"  中央値: {median1:.2f}s")
        
        print(f"\n{algo2}:")
        print(f"  平均: {mean2:.2f}s (±{std2:.2f})")
        print(f"  中央値: {median2:.2f}s")
        
        print(f"\n差: {mean1 - mean2:.2f}s ({(mean1/mean2 - 1)*100:+.1f}%)")
        
        # 正規性検定（Shapiro-Wilk検定）
        _, p_norm1 = stats.shapiro(algo1_times[:50] if len(algo1_times) > 50 else algo1_times)
        _, p_norm2 = stats.shapiro(algo2_times[:50] if len(algo2_times) > 50 else algo2_times)
        
        print(f"\n正規性検定:")
        print(f"  {algo1}: p={p_norm1:.4f} {'(正規分布)' if p_norm1 > 0.05 else '(非正規)'}")
        print(f"  {algo2}: p={p_norm2:.4f} {'(正規分布)' if p_norm2 > 0.05 else '(非正規)'}")
        
        # 正規分布なら対応のないt検定、そうでなければMann-Whitney U検定
        if p_norm1 > 0.05 and p_norm2 > 0.05:
            # t検定
            t_stat, p_value = stats.ttest_ind(algo1_times, algo2_times)
            test_name = "対応のないt検定"
            
            # 効果量（Cohen's d）
            pooled_std = np.sqrt(((len(algo1_times)-1)*std1**2 + (len(algo2_times)-1)*std2**2) / 
                                (len(algo1_times) + len(algo2_times) - 2))
            effect_size = (mean1 - mean2) / pooled_std
            effect_name = "Cohen's d"
        else:
            # Mann-Whitney U検定
            u_stat, p_value = mannwhitneyu(algo1_times, algo2_times, alternative='two-sided')
            test_name = "Mann-Whitney U検定"
            t_stat = u_stat
            
            # 効果量（r）
            n1, n2 = len(algo1_times), len(algo2_times)
            effect_size = 1 - (2*u_stat) / (n1 * n2)
            effect_name = "r"
        
        print(f"\n{test_name}:")
        print(f"  統計量: {t_stat:.4f}")
        print(f"  p値: {p_value:.4f}")
        
        if p_value < 0.001:
            print(f"  結論: 極めて有意な差あり (p < 0.001) ***")
        elif p_value < 0.01:
            print(f"  結論: 非常に有意な差あり (p < 0.01) **")
        elif p_value < 0.05:
            print(f"  結論: 有意な差あり (p < 0.05) *")
        else:
            print(f"  結論: 有意な差なし (p >= 0.05)")
        
        print(f"\n効果量 ({effect_name}): {effect_size:.4f}")
        
        if abs(effect_size) < 0.2:
            print("  効果: 小")
        elif abs(effect_size) < 0.5:
            print("  効果: 中")
        else:
            print("  効果: 大")
        
        return {
            'algo1': algo1,
            'algo2': algo2,
            'mean1': mean1,
            'mean2': mean2,
            'median1': median1,
            'median2': median2,
            'test_name': test_name,
            'statistic': t_stat,
            'p_value': p_value,
            'effect_size': effect_size,
            'significant': p_value < 0.05
        }
    
    def anova_all_algorithms(self, metric: str = 'computation_time') -> Dict:
        """
        全アルゴリズムの多重比較（ANOVA）
        
        Args:
            metric: 比較する指標（'computation_time', 'path_length'）
        
        Returns:
            Dict: 検定結果
        """
        print(f"\n{'='*70}")
        print(f"全アルゴリズム多重比較 ({metric})")
        print(f"{'='*70}")
        
        # 各アルゴリズムのデータを集める
        algorithm_data = {}
        
        if 'results' not in self.data:
            return {}
        
        # 最初の地形から全アルゴリズムを取得
        first_terrain = list(self.data['results'].keys())[0]
        algorithms = list(self.data['results'][first_terrain].keys())
        
        for algo in algorithms:
            algorithm_data[algo] = []
        
        # 全地形からデータを集める
        for terrain, terrain_results in self.data['results'].items():
            for algo in algorithms:
                if algo in terrain_results:
                    for r in terrain_results[algo]:
                        if r.get('success', False) and metric in r:
                            algorithm_data[algo].append(r[metric])
        
        # データが十分にあるアルゴリズムのみ
        valid_algorithms = [algo for algo in algorithms if len(algorithm_data[algo]) >= 3]
        
        if len(valid_algorithms) < 2:
            print("比較するアルゴリズムが不足")
            return {}
        
        # 基本統計
        print("\n各アルゴリズムの基本統計:")
        for algo in valid_algorithms:
            data = algorithm_data[algo]
            print(f"\n{algo}:")
            print(f"  サンプル数: {len(data)}")
            print(f"  平均: {np.mean(data):.2f}")
            print(f"  中央値: {np.median(data):.2f}")
            print(f"  標準偏差: {np.std(data):.2f}")
        
        # Kruskal-Wallis検定（ノンパラメトリック版ANOVA）
        groups = [algorithm_data[algo] for algo in valid_algorithms]
        h_stat, p_value = kruskal(*groups)
        
        print(f"\nKruskal-Wallis検定:")
        print(f"  H統計量: {h_stat:.4f}")
        print(f"  p値: {p_value:.4f}")
        
        if p_value < 0.001:
            print(f"  結論: アルゴリズム間に極めて有意な差あり (p < 0.001) ***")
        elif p_value < 0.01:
            print(f"  結論: アルゴリズム間に非常に有意な差あり (p < 0.01) **")
        elif p_value < 0.05:
            print(f"  結論: アルゴリズム間に有意な差あり (p < 0.05) *")
        else:
            print(f"  結論: アルゴリズム間に有意な差なし (p >= 0.05)")
        
        # 事後検定（post-hoc）: ペアワイズMann-Whitney U検定（Bonferroni補正）
        if p_value < 0.05:
            print(f"\n事後検定（ペアワイズ比較、Bonferroni補正）:")
            
            n_comparisons = len(valid_algorithms) * (len(valid_algorithms) - 1) // 2
            bonferroni_alpha = 0.05 / n_comparisons
            
            print(f"  比較数: {n_comparisons}")
            print(f"  補正後の有意水準: {bonferroni_alpha:.4f}")
            
            pairwise_results = []
            
            for i, algo1 in enumerate(valid_algorithms):
                for algo2 in valid_algorithms[i+1:]:
                    u_stat, p = mannwhitneyu(
                        algorithm_data[algo1],
                        algorithm_data[algo2],
                        alternative='two-sided'
                    )
                    
                    significant = p < bonferroni_alpha
                    
                    print(f"\n  {algo1} vs {algo2}:")
                    print(f"    p値: {p:.4f} {'***' if significant else ''}")
                    
                    if significant:
                        mean1 = np.mean(algorithm_data[algo1])
                        mean2 = np.mean(algorithm_data[algo2])
                        print(f"    差: {mean1 - mean2:+.2f}")
                        print(f"    → 有意な差あり")
                    
                    pairwise_results.append({
                        'algo1': algo1,
                        'algo2': algo2,
                        'p_value': p,
                        'significant': significant
                    })
        
        return {
            'algorithms': valid_algorithms,
            'h_statistic': h_stat,
            'p_value': p_value,
            'significant': p_value < 0.05
        }
    
    def generate_statistical_report(self):
        """統計的検定の完全レポートを生成"""
        print("\n" + "="*70)
        print("統計的検定 完全レポート")
        print("="*70)
        
        # 1. TA-A* vs A*
        self.compare_success_rates('A*', 'TA-A* (Proposed)')
        self.compare_computation_times('A*', 'TA-A* (Proposed)')
        
        # 2. TA-A* vs Weighted A*
        self.compare_success_rates('Weighted A*', 'TA-A* (Proposed)')
        self.compare_computation_times('Weighted A*', 'TA-A* (Proposed)')
        
        # 3. TA-A* vs RRT*
        self.compare_success_rates('RRT*', 'TA-A* (Proposed)')
        self.compare_computation_times('RRT*', 'TA-A* (Proposed)')
        
        # 4. 全アルゴリズム多重比較
        self.anova_all_algorithms('computation_time')
        self.anova_all_algorithms('path_length')
        
        print("\n" + "="*70)
        print("✅ 統計的検定完了")
        print("="*70)

if __name__ == '__main__':
    tester = StatisticalTester('../results/efficient_terrain_results.json')
    tester.generate_statistical_report()



