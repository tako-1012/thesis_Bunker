#!/usr/bin/env python3
"""
統計分析スクリプト - TA*実験データの統計的検証 (修正版)

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
        self.data = self._load_data()
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
        指定した手法の計算時間を抽出
        
        Args:
            method: 手法名
            
        Returns:
            計算時間の配列
        """
        times = []
        
        # JSON構造: results -> scenario_name -> results -> method -> computation_time
        if 'results' not in self.data:
            return np.array([])
        
        for scenario_name, scenario_data in self.data['results'].items():
            if isinstance(scenario_data, dict) and 'results' in scenario_data:
                method_results = scenario_data['results']
                if isinstance(method_results, dict) and method in method_results:
                    method_data = method_results[method]
                    if isinstance(method_data, dict) and 'computation_time' in method_data:
                        times.append(float(method_data['computation_time']))
        
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
        
        if 'results' not in self.data:
            return 0, 0
        
        for scenario_name, scenario_data in self.data['results'].items():
            if isinstance(scenario_data, dict) and 'results' in scenario_data:
                method_results = scenario_data['results']
                if method in method_results:
                    total_count += 1
                    if method_results[method].get('success', False):
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
        if dof > 0:
            t_critical = stats.t.ppf((1 + confidence) / 2, dof)
            margin = t_critical * std / np.sqrt(n)
        else:
            margin = 0
        
        # 成功率
        success, total = self._get_success_rates(method)
        success_rate = (success / total * 100) if total > 0 else 0
        
        stats_result = {
            'method': method,
            'n': n,
            'mean': mean,
            'std': std,
            'median': np.median(times),
            'q1': np.percentile(times, 25),
            'q3': np.percentile(times, 75),
            'ci_lower': max(0, mean - margin),  # 時間は0未満にはならない
            'ci_upper': mean + margin,
            'min': np.min(times),
            'max': np.max(times),
            'success_rate': success_rate,
            'success_count': success,
            'total_count': total
        }
        
        self.stats_dict[method] = stats_result
        return stats_result
    
    def welch_t_test(self, method_a: str, method_b: str) -> Dict:
        """
        Welchのt検定を実施
        
        Args:
            method_a: 比較手法A
            method_b: 比較手法B
            
        Returns:
            t統計量、p値、効果量を含む辞書
        """
        times_a = self._get_computation_times(method_a)
        times_b = self._get_computation_times(method_b)
        
        if len(times_a) == 0 or len(times_b) == 0:
            print(f"⚠️ {method_a} vs {method_b}: データが不足しています")
            return {}
        
        # Welch t検定 (等分散を仮定しない)
        t_stat, p_value = stats.ttest_ind(times_a, times_b, equal_var=False)
        
        # Cohen's d効果量
        cohens_d = self.cohens_d(method_a, method_b)
        
        # 効果量の解釈
        if abs(cohens_d) < 0.2:
            effect_interpretation = "negligible (無視できる)"
        elif abs(cohens_d) < 0.5:
            effect_interpretation = "small (小)"
        elif abs(cohens_d) < 0.8:
            effect_interpretation = "medium (中)"
        else:
            effect_interpretation = "large (大)"
        
        # p値の解釈
        if p_value < 0.001:
            p_interpretation = "highly significant (非常に有意)"
        elif p_value < 0.01:
            p_interpretation = "very significant (非常に有意)"
        elif p_value < 0.05:
            p_interpretation = "significant (有意)"
        else:
            p_interpretation = "not significant (有意でない)"
        
        result = {
            'method_a': method_a,
            'method_b': method_b,
            't_statistic': t_stat,
            'p_value': p_value,
            'cohens_d': cohens_d,
            'effect_size': effect_interpretation,
            'p_interpretation': p_interpretation,
            'mean_diff': np.mean(times_a) - np.mean(times_b),
            'n_a': len(times_a),
            'n_b': len(times_b)
        }
        
        return result
    
    def cohens_d(self, method_a: str, method_b: str) -> float:
        """
        Cohen's dを計算（効果量）
        
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
        
        n1, n2 = len(times_a), len(times_b)
        mean1, mean2 = np.mean(times_a), np.mean(times_b)
        std1, std2 = np.std(times_a, ddof=1), np.std(times_b, ddof=1)
        
        # プール標準偏差
        pooled_std = np.sqrt(((n1-1)*std1**2 + (n2-1)*std2**2) / (n1+n2-2))
        
        if pooled_std == 0:
            return 0.0
        
        cohens_d = (mean1 - mean2) / pooled_std
        return cohens_d
    
    def generate_report(self, output_path: str = "statistical_report.md") -> bool:
        """
        統計レポートをマークダウン形式で生成
        
        Args:
            output_path: 出力ファイルパス
            
        Returns:
            成功したかどうか
        """
        try:
            report = []
            report.append("# 統計分析レポート\n")
            report.append(f"**生成日時**: 2026年1月29日\n")
            report.append(f"**データソース**: {self.data_path}\n\n")
            
            # メタデータ
            if 'metadata' in self.data:
                meta = self.data['metadata']
                report.append("## メタデータ\n")
                report.append(f"- **タイムスタンプ**: {meta.get('timestamp', 'N/A')}\n")
                report.append(f"- **シナリオ数**: {meta.get('scenarios', 'N/A')}\n")
                report.append(f"- **手法数**: {meta.get('planners', 'N/A')}\n\n")
            
            # 全手法の検出
            all_methods = set()
            if 'results' in self.data:
                for scenario_data in self.data['results'].values():
                    if 'results' in scenario_data:
                        all_methods.update(scenario_data['results'].keys())
            
            # 記述統計
            report.append("## 記述統計量\n\n")
            report.append("| 手法 | 平均 (秒) | 標準偏差 | 中央値 | 95%信頼区間 | 成功率 |\n")
            report.append("|------|----------|--------|--------|-----------|--------|\n")
            
            for method in sorted(all_methods):
                stats = self.compute_descriptive_stats(method)
                if stats:
                    report.append(
                        f"| {method} | "
                        f"{stats['mean']:.4f} | "
                        f"{stats['std']:.4f} | "
                        f"{stats['median']:.4f} | "
                        f"[{stats['ci_lower']:.4f}, {stats['ci_upper']:.4f}] | "
                        f"{stats['success_rate']:.1f}% |\n"
                    )
            
            report.append("\n## Welch t検定結果\n\n")
            report.append("### TA*と他手法の比較\n\n")
            
            methods_list = sorted(all_methods)
            if 'TA*' in methods_list:
                report.append("| 比較 | t統計量 | p値 | Cohen's d | 効果量 | 結論 |\n")
                report.append("|------|---------|------|-----------|--------|------|\n")
                
                for method in methods_list:
                    if method != 'TA*':
                        t_result = self.welch_t_test('TA*', method)
                        if t_result:
                            conclusion = "有意" if t_result['p_value'] < 0.05 else "有意でない"
                            report.append(
                                f"| TA* vs {method} | "
                                f"{t_result['t_statistic']:.3f} | "
                                f"{t_result['p_value']:.4f} | "
                                f"{t_result['cohens_d']:.3f} | "
                                f"{t_result['effect_size']} | "
                                f"{conclusion} |\n"
                            )
            
            # 解釈ガイド
            report.append("\n## 統計的解釈ガイド\n\n")
            report.append("### Cohen's d（効果量）の解釈\n")
            report.append("- **< 0.2**: 無視できる効果\n")
            report.append("- **0.2-0.5**: 小さい効果\n")
            report.append("- **0.5-0.8**: 中程度の効果\n")
            report.append("- **> 0.8**: 大きい効果\n\n")
            
            report.append("### p値の解釈\n")
            report.append("- **p < 0.001**: 非常に有意（証拠が非常に強い）\n")
            report.append("- **0.001 ≤ p < 0.01**: 非常に有意（証拠が強い）\n")
            report.append("- **0.01 ≤ p < 0.05**: 有意（証拠がある）\n")
            report.append("- **p ≥ 0.05**: 有意でない（証拠が不十分）\n\n")
            
            # 論文への引用例
            report.append("## 論文への引用例\n\n")
            report.append("### 例1: 単純な平均値比較\n")
            report.append("```\n")
            report.append("TA*の平均計算時間は X.XXX秒（SD=X.XXX, n=XX）であり、\n")
            report.append("RRT*の Y.YYY秒（SD=Y.YYY, n=YY）と比較して\n")
            report.append("有意に高速であった [t(XX)=ZZ.ZZ, p<0.001, d=D.DD]。\n")
            report.append("```\n\n")
            
            report.append("### 例2: 信頼区間を含む報告\n")
            report.append("```\n")
            report.append("TA*の平均計算時間は X.XXX秒 [95%CI: X.XXX-X.XXX]（n=XX）、\n")
            report.append("RRT*は Y.YYY秒 [95%CI: Y.YYY-Y.YYY]（n=YY）であった。\n")
            report.append("```\n\n")
            
            # ファイルに書き込み
            with open(output_path, 'w', encoding='utf-8') as f:
                f.writelines(report)
            
            print(f"✅ レポート生成完了: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ レポート生成エラー: {e}")
            return False
    
    def export_csv(self, output_path: str = "statistical_results.csv") -> bool:
        """
        統計結果をCSVで出力
        
        Args:
            output_path: 出力ファイルパス
            
        Returns:
            成功したかどうか
        """
        try:
            # 全手法を検出
            all_methods = set()
            if 'results' in self.data:
                for scenario_data in self.data['results'].values():
                    if 'results' in scenario_data:
                        all_methods.update(scenario_data['results'].keys())
            
            # 統計量を計算
            data_rows = []
            for method in sorted(all_methods):
                stats = self.compute_descriptive_stats(method)
                if stats:
                    data_rows.append(stats)
            
            df = pd.DataFrame(data_rows)
            df.to_csv(output_path, index=False, encoding='utf-8')
            print(f"✅ CSV出力完了: {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ CSV出力エラー: {e}")
            return False


def main():
    """メイン処理"""
    print("=" * 60)
    print("🔬 統計分析スクリプト")
    print("=" * 60)
    
    # データファイルを探索
    possible_paths = [
        "results/quick_comparison_20251109_163012.json",
        "results/quick_comparison_20251117.json",
        "benchmark_results/latest_results.json"
    ]
    
    data_path = None
    for path in possible_paths:
        if Path(path).exists():
            data_path = path
            break
    
    if not data_path:
        print("❌ ベンチマークデータが見つかりません")
        print(f"確認対象: {possible_paths}")
        return 1
    
    print(f"📂 データファイル: {data_path}\n")
    
    # 分析実行
    analyzer = StatisticalAnalyzer(data_path)
    
    print("📊 記述統計量を計算中...")
    analyzer.generate_report()
    
    print("📊 CSVに出力中...")
    analyzer.export_csv()
    
    print("\n" + "=" * 60)
    print("✅ 統計分析完了")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
