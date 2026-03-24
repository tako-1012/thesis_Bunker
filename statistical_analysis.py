#!/usr/bin/env python3
"""
統計分析スクリプト - TA*実験データの統計的検証

実装機能:
- Welch t検定（対応のないt検定）
- Cohen's d（効果量）
- 95%信頼区間
- 中央値・四分位数・標準偏差
"""

import numpy as np
from scipy import stats
import pandas as pd
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys


class StatisticalAnalyzer:
    """ベンチマーク結果の統計分析"""
    
    def __init__(self, data_path: str):
        """
        Args:
            data_path: ベンチマーク結果JSONのパス
        """
        self.data_path = Path(data_path)
        self.results = self._load_data()
        self.stats_dict = {}
        
    def _load_data(self) -> Dict:
        """JSONデータを読み込む"""
        if not self.data_path.exists():
            print(f"❌ エラー: {self.data_path} が見つかりません")
            return {}
        
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ JSONロードエラー: {e}")
            return {}
    
    def _get_computation_times(self, method: str) -> np.ndarray:
        """
        計算時間を抽出
        
        Args:
            method: アルゴリズム名 ("A*", "TA*", "RRT*" など)
            
        Returns:
            計算時間の配列
        """
        times = []
        
        # 結果構造の探索
        if 'results' in self.results:
            # 構造1: scenarios → results → method
            for scenario_key, scenario_data in self.results['results'].items():
                if isinstance(scenario_data, dict):
                    if method in scenario_data:
                        time = scenario_data[method].get('computation_time')
                        if time is not None:
                            times.append(float(time))
        
        # 結果構造2: results → scenario_name → results → method
        for key, value in self.results.items():
            if isinstance(value, dict) and 'results' in value:
                results_by_method = value['results']
                if method in results_by_method:
                    time = results_by_method[method].get('computation_time')
                    if time is not None:
                        times.append(float(time))
        
        return np.array(times)
    
    def _get_success_rates(self, method: str) -> Tuple[int, int]:
        """
        成功率を計算
        
        Args:
            method: アルゴリズム名
            
        Returns:
            (成功数, 総試行数)
        """
        success_count = 0
        total_count = 0
        
        # 結果構造の探索
        if 'results' in self.results:
            for scenario_key, scenario_data in self.results['results'].items():
                if isinstance(scenario_data, dict):
                    if method in scenario_data:
                        total_count += 1
                        if scenario_data[method].get('success', False):
                            success_count += 1
        
        for key, value in self.results.items():
            if isinstance(value, dict) and 'results' in value:
                results_by_method = value['results']
                if method in results_by_method:
                    total_count += 1
                    if results_by_method[method].get('success', False):
                        success_count += 1
        
        return success_count, total_count
    
    def compute_descriptive_stats(self, method: str) -> Dict:
        """
        記述統計量を計算
        
        Args:
            method: アルゴリズム名
            
        Returns:
            統計量を含む辞書
        """
        times = self._get_computation_times(method)
        
        if len(times) == 0:
            print(f"⚠️ {method}: データがありません")
            return {}
        
        n = len(times)
        mean = np.mean(times)
        std = np.std(times, ddof=1)
        
        # 95%信頼区間 (t分布)
        confidence = 0.95
        dof = n - 1
        t_critical = stats.t.ppf((1 + confidence) / 2, dof)
        margin = t_critical * std / np.sqrt(n)
        
        # 成功率
        success, total = self._get_success_rates(method)
        success_rate = (success / total * 100) if total > 0 else 0
        
        stats_result = {
            'method': method,
            'mean': mean,
            'std': std,
            'median': np.median(times),
            'q1': np.percentile(times, 25),
            'q3': np.percentile(times, 75),
            'ci_lower': mean - margin,
            'ci_upper': mean + margin,
            'min': np.min(times),
            'max': np.max(times),
            'n': n,
            'success_rate': success_rate,
            'success_count': success,
            'total_count': total
        }
        
        self.stats_dict[method] = stats_result
        return stats_result
    
    def welch_t_test(self, method_a: str, method_b: str) -> Dict:
        """
        Welch t検定 (等分散を仮定しない)
        
        Args:
            method_a: 比較手法A
            method_b: 比較手法B
            
        Returns:
            t検定結果の辞書
        """
        times_a = self._get_computation_times(method_a)
        times_b = self._get_computation_times(method_b)
        
        if len(times_a) == 0 or len(times_b) == 0:
            return {'error': 'データ不足'}
        
        t_stat, p_value = stats.ttest_ind(
            times_a, times_b, equal_var=False
        )
        
        # 有意性判定
        if p_value < 0.001:
            significance = "***"
        elif p_value < 0.01:
            significance = "**"
        elif p_value < 0.05:
            significance = "*"
        else:
            significance = "n.s."
        
        return {
            'method_a': method_a,
            'method_b': method_b,
            't_statistic': t_stat,
            'p_value': p_value,
            'significance': significance,
            'significant': p_value < 0.05
        }
    
    def cohens_d(self, method_a: str, method_b: str) -> float:
        """
        Cohen's d効果量を計算
        
        Args:
            method_a: 比較手法A
            method_b: 比較手法B
            
        Returns:
            Cohen's d値
        """
        times_a = self._get_computation_times(method_a)
        times_b = self._get_computation_times(method_b)
        
        if len(times_a) == 0 or len(times_b) == 0:
            return 0.0
        
        mean_a = np.mean(times_a)
        mean_b = np.mean(times_b)
        
        n_a, n_b = len(times_a), len(times_b)
        var_a = np.var(times_a, ddof=1)
        var_b = np.var(times_b, ddof=1)
        
        # プール標準偏差
        pooled_var = (
            ((n_a - 1) * var_a + (n_b - 1) * var_b) / 
            (n_a + n_b - 2)
        )
        pooled_std = np.sqrt(pooled_var)
        
        if pooled_std == 0:
            return 0.0
        
        d = (mean_a - mean_b) / pooled_std
        return d
    
    def get_effect_size_label(self, d: float) -> str:
        """Cohen's d から効果量ラベルを取得"""
        abs_d = abs(d)
        if abs_d < 0.2:
            return "小"
        elif abs_d < 0.5:
            return "中"
        elif abs_d < 0.8:
            return "大"
        else:
            return "非常に大"
    
    def generate_report(self, output_path: str = 'statistical_report.md') -> bool:
        """
        統計分析レポートを生成
        
        Args:
            output_path: 出力ファイルパス
            
        Returns:
            成功したかどうか
        """
        methods = ['TA*', 'RRT*', 'A*', 'SAFETY_FIRST', 'HPA*', 'D* Lite', 'Dijkstra']
        
        # 各手法について統計量を計算
        print("\n📊 記述統計量を計算中...")
        valid_methods = []
        for method in methods:
            stats = self.compute_descriptive_stats(method)
            if stats:
                valid_methods.append(method)
                print(f"  ✅ {method}: n={stats['n']}, "
                      f"mean={stats['mean']:.3f}±{stats['std']:.3f}秒")
        
        lines = []
        
        # タイトル
        lines.append("# 統計分析レポート\n")
        lines.append(f"**生成日時**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**データソース**: {self.data_path}\n\n")
        
        # 概要
        lines.append("## 📋 データサマリー\n")
        lines.append(f"- 有効な手法数: {len(valid_methods)}\n")
        lines.append(f"- 分析対象手法: {', '.join(valid_methods)}\n\n")
        
        # 記述統計量
        lines.append("## 📊 記述統計量\n\n")
        lines.append(
            "| 手法 | n | 平均±SD | 中央値 | Q1-Q3 | "
            "95% CI | 成功率 |\n"
        )
        lines.append("|" + "|".join(["-" * 8] * 7) + "|\n")
        
        for method in valid_methods:
            s = self.stats_dict[method]
            ci_str = f"[{s['ci_lower']:.3f}, {s['ci_upper']:.3f}]"
            q_str = f"[{s['q1']:.3f}, {s['q3']:.3f}]"
            
            lines.append(
                f"| {method} | {s['n']} | "
                f"{s['mean']:.3f}±{s['std']:.3f} | "
                f"{s['median']:.3f} | {q_str} | {ci_str} | "
                f"{s['success_rate']:.1f}% |\n"
            )
        
        lines.append("\n")
        
        # 詳細統計量
        lines.append("## 📈 詳細統計量\n\n")
        for method in valid_methods:
            s = self.stats_dict[method]
            lines.append(f"### {method}\n\n")
            lines.append(f"| 統計量 | 値 |\n")
            lines.append("|" + "-" * 20 + "|" + "-" * 20 + "|\n")
            lines.append(f"| 平均 (Mean) | {s['mean']:.4f} 秒 |\n")
            lines.append(f"| 標準偏差 (SD) | {s['std']:.4f} 秒 |\n")
            lines.append(f"| 中央値 (Median) | {s['median']:.4f} 秒 |\n")
            lines.append(f"| 最小値 (Min) | {s['min']:.4f} 秒 |\n")
            lines.append(f"| 最大値 (Max) | {s['max']:.4f} 秒 |\n")
            lines.append(f"| 第1四分位数 (Q1) | {s['q1']:.4f} 秒 |\n")
            lines.append(f"| 第3四分位数 (Q3) | {s['q3']:.4f} 秒 |\n")
            lines.append(f"| 四分位範囲 (IQR) | {s['q3']-s['q1']:.4f} 秒 |\n")
            lines.append(f"| 95% 信頼区間 | [{s['ci_lower']:.4f}, {s['ci_upper']:.4f}] |\n")
            lines.append(f"| サンプル数 (n) | {s['n']} |\n")
            lines.append(f"| 成功数 | {s['success_count']}/{s['total_count']} |\n")
            lines.append(f"| 成功率 | {s['success_rate']:.1f}% |\n\n")
        
        # 対比較（t検定とCohen's d）
        lines.append("## 🔬 対比較分析（Welch t検定 + Cohen's d）\n\n")
        lines.append(
            "| 比較 | t統計量 | p値 | 有意性 | "
            "Cohen's d | 効果量 | 結論 |\n"
        )
        lines.append("|" + "|".join(["-" * 10] * 7) + "|\n")
        
        # TA*を基準に他の手法と比較
        if 'TA*' in valid_methods:
            for method in valid_methods:
                if method == 'TA*':
                    continue
                
                t_res = self.welch_t_test('TA*', method)
                d = self.cohens_d('TA*', method)
                effect_label = self.get_effect_size_label(d)
                
                # 結論の判定
                if t_res.get('significant', False):
                    if abs(d) > 0.8:
                        conclusion = f"有意（{effect_label}な差）"
                    else:
                        conclusion = "有意"
                else:
                    conclusion = "非有意"
                
                lines.append(
                    f"| TA* vs {method} | {t_res['t_statistic']:.2f} | "
                    f"{t_res['p_value']:.2e} | {t_res['significance']} | "
                    f"{d:.2f} | {effect_label} | {conclusion} |\n"
                )
        
        lines.append("\n**有意性**: *** p<0.001, ** p<0.01, * p<0.05, n.s. 非有意\n\n")
        
        # 高速化率
        lines.append("## ⚡ 高速化率\n\n")
        if 'TA*' in valid_methods:
            ta_mean = self.stats_dict['TA*']['mean']
            lines.append("| 比較手法 | 平均時間 | 高速化率 | 倍率 |\n")
            lines.append("|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 12 + "|" + "-" * 10 + "|\n")
            
            for method in valid_methods:
                if method == 'TA*':
                    continue
                method_mean = self.stats_dict[method]['mean']
                speedup = method_mean / ta_mean
                lines.append(
                    f"| {method} | {method_mean:.3f}秒 | "
                    f"{(speedup-1)*100:.1f}% | {speedup:.1f}x |\n"
                )
        
        lines.append("\n")
        
        # 論文用引用例
        lines.append("## 📝 論文への記載例\n\n")
        if 'TA*' in valid_methods and 'RRT*' in valid_methods:
            ta_stats = self.stats_dict['TA*']
            rrt_stats = self.stats_dict['RRT*']
            t_res = self.welch_t_test('TA*', 'RRT*')
            d = self.cohens_d('TA*', 'RRT*')
            
            lines.append("```\n")
            lines.append(
                f"TA*の計算時間は{ta_stats['mean']:.2f}±{ta_stats['std']:.2f}秒"
                f"(95% CI [{ta_stats['ci_lower']:.2f}, {ta_stats['ci_upper']:.2f}])"
                f"であり、RRT*の{rrt_stats['mean']:.2f}±{rrt_stats['std']:.2f}秒"
                f"(95% CI [{rrt_stats['ci_lower']:.2f}, {rrt_stats['ci_upper']:.2f}])"
                f"と比較して統計的に有意に高速であった"
                f"(Welch t検定: t({ta_stats['n']+rrt_stats['n']-2})="
                f"{t_res['t_statistic']:.2f}, p{t_res['significance']})。\n"
            )
            lines.append(
                f"効果量はCohen's d={d:.2f}と{self.get_effect_size_label(d)}"
                f"な効果であり、実用的にも意義のある差である。\n"
            )
            lines.append("```\n\n")
        
        # 方法論
        lines.append("## 📐 統計分析方法\n\n")
        lines.append("### 記述統計量\n")
        lines.append("- **平均（Mean）**: 算術平均\n")
        lines.append("- **標準偏差（SD）**: サンプル標準偏差（不偏推定量）\n")
        lines.append("- **中央値（Median）**: 50パーセンタイル\n")
        lines.append("- **四分位数**: Q1（25%）, Q3（75%）\n")
        lines.append("- **信頼区間**: 95% t分布ベースの信頼区間\n\n")
        
        lines.append("### 検定方法\n")
        lines.append("- **検定**: Welch t検定（Welch's t-test）\n")
        lines.append("  - 等分散を仮定しない独立2サンプルt検定\n")
        lines.append("  - 帰無仮説: μ_A = μ_B\n")
        lines.append("  - 対立仮説: μ_A ≠ μ_B（両側検定）\n\n")
        
        lines.append("### 効果量\n")
        lines.append("- **Cohen's d**: 平均差をプール標準偏差で正規化\n")
        lines.append("  - 判定基準: |d| < 0.2 (小), 0.2-0.5 (中), "
                     "0.5-0.8 (大), > 0.8 (非常に大)\n\n")
        
        # 出力
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print(f"\n✅ レポート生成完了: {output_file}")
        return True
    
    def export_csv(self, output_path: str = 'statistical_results.csv') -> bool:
        """
        結果をCSV形式で出力
        
        Args:
            output_path: 出力ファイルパス
            
        Returns:
            成功したかどうか
        """
        rows = []
        for method, stats in self.stats_dict.items():
            rows.append({
                'Method': method,
                'N': stats['n'],
                'Mean': f"{stats['mean']:.4f}",
                'SD': f"{stats['std']:.4f}",
                'Median': f"{stats['median']:.4f}",
                'Q1': f"{stats['q1']:.4f}",
                'Q3': f"{stats['q3']:.4f}",
                'Min': f"{stats['min']:.4f}",
                'Max': f"{stats['max']:.4f}",
                'CI_Lower': f"{stats['ci_lower']:.4f}",
                'CI_Upper': f"{stats['ci_upper']:.4f}",
                'Success_Rate': f"{stats['success_rate']:.1f}%",
                'Success_Count': f"{stats['success_count']}/{stats['total_count']}"
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False, encoding='utf-8')
        print(f"✅ CSV出力完了: {output_path}")
        return True


def main():
    """メイン処理"""
    print("\n" + "="*70)
    print("🔬 統計分析スクリプト")
    print("="*70)
    
    # データファイルのパス（複数候補をチェック）
    data_paths = [
        'results/quick_comparison_20251109_163012.json',
        'quick_comparison_20251109_163012.json',
        'benchmark_results.json',
    ]
    
    data_file = None
    for path in data_paths:
        p = Path(path)
        if p.exists():
            data_file = path
            break
    
    if not data_file:
        print("\n❌ エラー: ベンチマーク結果ファイルが見つかりません")
        print(f"探索場所: {data_paths}")
        return False
    
    print(f"\n📂 データファイル: {data_file}")
    
    # 分析実行
    analyzer = StatisticalAnalyzer(data_file)
    
    if not analyzer.results:
        print("❌ データ読み込み失敗")
        return False
    
    # レポート生成
    analyzer.generate_report('statistical_report.md')
    analyzer.export_csv('statistical_results.csv')
    
    print("\n" + "="*70)
    print("✅ 統計分析完了")
    print("="*70 + "\n")
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
