#!/usr/bin/env python3
"""
論文用統計表の自動生成スクリプト

入力: benchmark_96_scenarios_combined.json
出力:
  - tables/table1_algorithm_comparison.{tex,md,csv}
  - tables/table2_statistical_tests.{tex,md,csv}
  - tables/table3_complexity_breakdown.{tex,md,csv}
"""

import json
import numpy as np
from pathlib import Path
from scipy import stats
import csv

class ThesisTableGenerator:
    def __init__(self, data_file):
        with open(data_file, 'r') as f:
            self.data = json.load(f)
        
        self.methods = self.data['metadata']['methods']
        self.output_dir = Path('tables')
        self.output_dir.mkdir(exist_ok=True)
    
    def extract_computation_times(self, method):
        """指定メソッドの計算時間を抽出"""
        times = []
        successes = []
        
        for scenario_id, scenario_data in self.data['results'].items():
            if method in scenario_data['results']:
                result = scenario_data['results'][method]
                if 'computation_time' in result:
                    times.append(result['computation_time'])
                    successes.append(result.get('success', True))
        
        return np.array(times), np.array(successes)
    
    def compute_stats(self, times):
        """統計量を計算"""
        return {
            'mean': np.mean(times),
            'std': np.std(times, ddof=1),
            'median': np.median(times),
            'q1': np.percentile(times, 25),
            'q3': np.percentile(times, 75),
            'min': np.min(times),
            'max': np.max(times),
            'n': len(times)
        }
    
    def confidence_interval(self, times, confidence=0.95):
        """95%信頼区間を計算"""
        n = len(times)
        mean = np.mean(times)
        se = stats.sem(times)
        h = se * stats.t.ppf((1 + confidence) / 2, n - 1)
        return mean - h, mean + h
    
    def welch_t_test(self, group1, group2):
        """Welch t-testを実行"""
        t_stat, p_val = stats.ttest_ind(group1, group2, equal_var=False)
        return t_stat, p_val
    
    def cohens_d(self, group1, group2):
        """Cohen's dを計算"""
        n1, n2 = len(group1), len(group2)
        var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
        pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
        return (np.mean(group1) - np.mean(group2)) / pooled_std
    
    def classify_complexity(self, scenario_id):
        """シナリオの複雑度を分類"""
        # SMALL/MEDIUM/LARGE からの推定
        if 'SMALL' in scenario_id:
            return 'Simple'
        elif 'MEDIUM' in scenario_id:
            return 'Medium'
        elif 'LARGE' in scenario_id:
            return 'Complex'
        return 'Medium'
    
    def generate_table1(self):
        """Table 1: アルゴリズム性能比較表"""
        print("📊 Table 1: アルゴリズム性能比較表を生成中...")
        
        # データ収集
        table_data = []
        for method in self.methods:
            times, successes = self.extract_computation_times(method)
            stats_dict = self.compute_stats(times)
            ci_low, ci_high = self.confidence_interval(times)
            success_rate = np.sum(successes) / len(successes) * 100
            
            table_data.append({
                'method': method,
                'mean': stats_dict['mean'],
                'std': stats_dict['std'],
                'median': stats_dict['median'],
                'ci_low': ci_low,
                'ci_high': ci_high,
                'success_rate': success_rate,
                'n': stats_dict['n']
            })
        
        # LaTeX出力
        latex_lines = [
            r'\begin{table}[htbp]',
            r'\centering',
            r'\caption{Performance Comparison of Four Path Planning Algorithms (n=96)}',
            r'\label{tab:algorithm_comparison}',
            r'\begin{tabular}{lcccccc}',
            r'\hline',
            r'Algorithm & Mean $\pm$ SD (s) & Median (s) & 95\% CI (s) & Success Rate (\%) & $n$ \\',
            r'\hline'
        ]
        
        for row in table_data:
            latex_lines.append(
                f"{row['method']} & "
                f"{row['mean']:.4f} $\\pm$ {row['std']:.4f} & "
                f"{row['median']:.4f} & "
                f"[{row['ci_low']:.2f}, {row['ci_high']:.2f}] & "
                f"{row['success_rate']:.1f} & "
                f"{int(row['n'])} \\\\"
            )
        
        latex_lines.extend([
            r'\hline',
            r'\end{tabular}',
            r'\end{table}'
        ])
        
        # Markdown出力
        md_lines = [
            '# Table 1: Algorithm Performance Comparison (n=96)',
            '',
            '| Algorithm | Mean ± SD (s) | Median (s) | 95% CI (s) | Success Rate (%) | n |',
            '|-----------|---------------|------------|------------|------------------|---|'
        ]
        
        for row in table_data:
            md_lines.append(
                f"| {row['method']} | "
                f"{row['mean']:.4f} ± {row['std']:.4f} | "
                f"{row['median']:.4f} | "
                f"[{row['ci_low']:.2f}, {row['ci_high']:.2f}] | "
                f"{row['success_rate']:.1f} | "
                f"{int(row['n'])} |"
            )
        
        # CSV出力
        csv_path = self.output_dir / 'table1_algorithm_comparison.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Algorithm', 'Mean', 'SD', 'Median', 'CI_Low', 'CI_High', 'Success_Rate', 'n'])
            for row in table_data:
                writer.writerow([
                    row['method'],
                    f"{row['mean']:.6f}",
                    f"{row['std']:.6f}",
                    f"{row['median']:.6f}",
                    f"{row['ci_low']:.6f}",
                    f"{row['ci_high']:.6f}",
                    f"{row['success_rate']:.2f}",
                    int(row['n'])
                ])
        
        # ファイル保存
        (self.output_dir / 'table1_algorithm_comparison.tex').write_text('\n'.join(latex_lines))
        (self.output_dir / 'table1_algorithm_comparison.md').write_text('\n'.join(md_lines))
        
        print(f"  ✅ table1_algorithm_comparison.tex")
        print(f"  ✅ table1_algorithm_comparison.md")
        print(f"  ✅ table1_algorithm_comparison.csv")
    
    def generate_table2(self):
        """Table 2: 統計検定結果（TA* vs 他手法）"""
        print("\n📊 Table 2: 統計検定結果を生成中...")
        
        # TA*のデータ取得
        ta_times, _ = self.extract_computation_times('TA*')
        
        # 他手法との比較
        table_data = []
        for method in self.methods:
            if method == 'TA*':
                continue
            
            other_times, _ = self.extract_computation_times(method)
            t_stat, p_val = self.welch_t_test(ta_times, other_times)
            d = self.cohens_d(ta_times, other_times)
            
            # 効果量の解釈
            if abs(d) < 0.2:
                effect = 'Negligible'
            elif abs(d) < 0.5:
                effect = 'Small'
            elif abs(d) < 0.8:
                effect = 'Medium'
            else:
                effect = 'Large'
            
            # p値の解釈
            if p_val < 0.001:
                sig = '***'
                p_str = '< 0.001'
            elif p_val < 0.01:
                sig = '**'
                p_str = f'{p_val:.3f}'
            elif p_val < 0.05:
                sig = '*'
                p_str = f'{p_val:.3f}'
            else:
                sig = 'n.s.'
                p_str = f'{p_val:.3f}'
            
            table_data.append({
                'comparison': f'TA* vs {method}',
                't_stat': t_stat,
                'p_val': p_val,
                'p_str': p_str,
                'sig': sig,
                'cohens_d': d,
                'effect': effect
            })
        
        # LaTeX出力
        latex_lines = [
            r'\begin{table}[htbp]',
            r'\centering',
            r'\caption{Statistical Test Results: TA* vs Other Algorithms}',
            r'\label{tab:statistical_tests}',
            r'\begin{tabular}{lccccc}',
            r'\hline',
            r'Comparison & $t$-statistic & $p$-value & Sig. & Cohen\'s $d$ & Effect Size \\',
            r'\hline'
        ]
        
        for row in table_data:
            latex_lines.append(
                f"{row['comparison']} & "
                f"{row['t_stat']:.3f} & "
                f"{row['p_str']} & "
                f"{row['sig']} & "
                f"{row['cohens_d']:.3f} & "
                f"{row['effect']} \\\\"
            )
        
        latex_lines.extend([
            r'\hline',
            r'\multicolumn{6}{l}{\footnotesize Note: *** $p < 0.001$, ** $p < 0.01$, * $p < 0.05$, n.s. not significant} \\',
            r'\end{tabular}',
            r'\end{table}'
        ])
        
        # Markdown出力
        md_lines = [
            '# Table 2: Statistical Test Results - TA* vs Other Algorithms',
            '',
            '| Comparison | t-statistic | p-value | Significance | Cohen\'s d | Effect Size |',
            '|------------|-------------|---------|--------------|-----------|-------------|'
        ]
        
        for row in table_data:
            md_lines.append(
                f"| {row['comparison']} | "
                f"{row['t_stat']:.3f} | "
                f"{row['p_str']} | "
                f"{row['sig']} | "
                f"{row['cohens_d']:.3f} | "
                f"{row['effect']} |"
            )
        
        md_lines.append('')
        md_lines.append('**Note**: *** p < 0.001, ** p < 0.01, * p < 0.05, n.s. not significant')
        
        # CSV出力
        csv_path = self.output_dir / 'table2_statistical_tests.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Comparison', 't_statistic', 'p_value', 'Significance', 'Cohens_d', 'Effect_Size'])
            for row in table_data:
                writer.writerow([
                    row['comparison'],
                    f"{row['t_stat']:.6f}",
                    f"{row['p_val']:.6f}",
                    row['sig'],
                    f"{row['cohens_d']:.6f}",
                    row['effect']
                ])
        
        # ファイル保存
        (self.output_dir / 'table2_statistical_tests.tex').write_text('\n'.join(latex_lines))
        (self.output_dir / 'table2_statistical_tests.md').write_text('\n'.join(md_lines))
        
        print(f"  ✅ table2_statistical_tests.tex")
        print(f"  ✅ table2_statistical_tests.md")
        print(f"  ✅ table2_statistical_tests.csv")
    
    def generate_table3(self):
        """Table 3: 地形複雑度別の計算時間"""
        print("\n📊 Table 3: 地形複雑度別性能比較表を生成中...")
        
        # 複雑度ごとにデータを分類
        complexity_data = {
            'Simple': {method: [] for method in self.methods},
            'Medium': {method: [] for method in self.methods},
            'Complex': {method: [] for method in self.methods}
        }
        
        for scenario_id, scenario_data in self.data['results'].items():
            complexity = self.classify_complexity(scenario_id)
            for method in self.methods:
                if method in scenario_data['results']:
                    time = scenario_data['results'][method].get('computation_time')
                    if time is not None:
                        complexity_data[complexity][method].append(time)
        
        # LaTeX出力
        latex_lines = [
            r'\begin{table}[htbp]',
            r'\centering',
            r'\caption{Computation Time by Terrain Complexity}',
            r'\label{tab:complexity_breakdown}',
            r'\begin{tabular}{lcccc}',
            r'\hline',
            r'Complexity & TA* (s) & AHA* (s) & Theta* (s) & FieldD* (s) \\',
            r'\hline'
        ]
        
        # Markdown出力
        md_lines = [
            '# Table 3: Computation Time by Terrain Complexity',
            '',
            '| Complexity | TA* (s) | AHA* (s) | Theta* (s) | FieldD*Hybrid (s) |',
            '|------------|---------|----------|-----------|-------------------|'
        ]
        
        # CSV用データ
        csv_data = []
        csv_data.append(['Complexity', 'TA*_Mean', 'TA*_SD', 'AHA*_Mean', 'AHA*_SD', 
                        'Theta*_Mean', 'Theta*_SD', 'FieldD*_Mean', 'FieldD*_SD', 'n'])
        
        for complexity in ['Simple', 'Medium', 'Complex']:
            row_latex = f"{complexity}"
            row_md = f"| {complexity}"
            row_csv = [complexity]
            
            for method in self.methods:
                times = complexity_data[complexity][method]
                if len(times) > 0:
                    mean = np.mean(times)
                    std = np.std(times, ddof=1)
                    row_latex += f" & {mean:.3f} $\\pm$ {std:.3f}"
                    row_md += f" | {mean:.3f} ± {std:.3f}"
                    row_csv.extend([f"{mean:.6f}", f"{std:.6f}"])
                else:
                    row_latex += " & N/A"
                    row_md += " | N/A"
                    row_csv.extend(['N/A', 'N/A'])
            
            n = len(complexity_data[complexity][self.methods[0]])
            row_csv.append(str(n))
            
            latex_lines.append(row_latex + r" \\")
            md_lines.append(row_md + " |")
            csv_data.append(row_csv)
        
        latex_lines.extend([
            r'\hline',
            r'\multicolumn{5}{l}{\footnotesize Values shown as Mean $\pm$ SD} \\',
            r'\end{tabular}',
            r'\end{table}'
        ])
        
        # CSV保存
        csv_path = self.output_dir / 'table3_complexity_breakdown.csv'
        with open(csv_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
        
        # ファイル保存
        (self.output_dir / 'table3_complexity_breakdown.tex').write_text('\n'.join(latex_lines))
        (self.output_dir / 'table3_complexity_breakdown.md').write_text('\n'.join(md_lines))
        
        print(f"  ✅ table3_complexity_breakdown.tex")
        print(f"  ✅ table3_complexity_breakdown.md")
        print(f"  ✅ table3_complexity_breakdown.csv")
    
    def generate_all_tables(self):
        """すべての表を生成"""
        print("=" * 60)
        print("📋 論文用統計表の生成開始")
        print("=" * 60)
        
        self.generate_table1()
        self.generate_table2()
        self.generate_table3()
        
        print("\n" + "=" * 60)
        print("✅ すべての統計表の生成完了")
        print("=" * 60)
        print(f"\n出力先: {self.output_dir}/")
        print("  - table1_algorithm_comparison.{tex,md,csv}")
        print("  - table2_statistical_tests.{tex,md,csv}")
        print("  - table3_complexity_breakdown.{tex,md,csv}")

if __name__ == '__main__':
    generator = ThesisTableGenerator('benchmark_96_scenarios_combined.json')
    generator.generate_all_tables()
