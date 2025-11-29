#!/usr/bin/env python3
"""
report_generator.py
統計レポート生成（Markdown/LaTeX）

機能:
- Markdown形式レポート
- LaTeX形式レポート（論文用）
- 表・図の自動挿入
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict

class ReportGenerator:
    """レポート生成クラス"""
    
    def __init__(self):
        self.output_dir = Path("results/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_analysis(self, analysis_path: str = "results/statistical_analysis.json") -> Dict:
        """統計解析結果読み込み"""
        with open(analysis_path, 'r') as f:
            return json.load(f)
    
    def generate_markdown_report(self, analysis: Dict) -> str:
        """Markdownレポート生成"""
        report = f"""# Week 4完了レポート: 大規模シミュレーション評価

**生成日時**: {datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')}

## 📊 実行サマリー

| 項目 | 値 |
|------|-----|
| 総シナリオ数 | {analysis['basic_stats']['total_scenarios']} |
| 成功シナリオ数 | {analysis['basic_stats']['successful_scenarios']} |
| **成功率** | **{analysis['basic_stats']['success_rate']:.1f}%** |

## 📈 記述統計

### 計算時間
| 統計量 | 値 (秒) |
|--------|---------|
| 平均 | {analysis['descriptive_statistics']['computation_time']['mean']:.2f} |
| 標準偏差 | {analysis['descriptive_statistics']['computation_time']['std']:.2f} |
| 最小値 | {analysis['descriptive_statistics']['computation_time']['min']:.2f} |
| 最大値 | {analysis['descriptive_statistics']['computation_time']['max']:.2f} |
| 中央値 | {analysis['descriptive_statistics']['computation_time']['median']:.2f} |

"""
        
        # 地形タイプ別結果
        report += "\n## 🏔️ 地形タイプ別性能\n\n"
        report += "| 地形タイプ | 成功率 | 平均計算時間 (秒) | 平均経路長 (m) |\n"
        report += "|------------|--------|-------------------|----------------|\n"
        
        for terrain, data in analysis['terrain_type_analysis'].items():
            report += f"| {terrain} | {data['success_rate']:.1f}% | {data['avg_computation_time']:.2f} | {data['avg_path_length']:.2f} |\n"
        
        # 相関分析
        report += "\n## 🔗 相関分析\n\n"
        report += "| パラメータペア | 相関係数 |\n"
        report += "|----------------|----------|\n"
        
        for key, value in analysis['correlations'].items():
            report += f"| {key} | {value:.3f} |\n"
        
        # ANOVA結果
        if analysis.get('anova'):
            report += "\n## 📊 ANOVA検定結果\n\n"
            report += f"- F統計量: {analysis['anova']['f_statistic']:.4f}\n"
            report += f"- p値: {analysis['anova']['p_value']:.6f}\n"
            report += f"- 結論: {analysis['anova']['interpretation']}\n"
        
        # グラフ
        report += "\n## 📈 可視化結果\n\n"
        report += "![地形タイプ別性能](../figures/terrain_type_performance.png)\n\n"
        report += "![計算時間分布](../figures/computation_time_distribution.png)\n\n"
        report += "![箱ひげ図](../figures/boxplot_by_terrain.png)\n\n"
        
        return report
    
    def save_markdown_report(self, report: str):
        """Markdownレポート保存"""
        output_file = self.output_dir / "week4_completion_report.md"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"💾 Markdownレポート保存: {output_file}")
    
    def generate_latex_summary(self, analysis: Dict) -> str:
        """LaTeX形式サマリー（論文用）"""
        latex = r"""\begin{table}[h]
\centering
\caption{Large-scale Simulation Results Summary}
\label{tab:simulation_results}
\begin{tabular}{lr}
\hline
\textbf{Metric} & \textbf{Value} \\
\hline
Total Scenarios & """ + f"{analysis['basic_stats']['total_scenarios']}" + r""" \\
Success Rate & """ + f"{analysis['basic_stats']['success_rate']:.1f}\%" + r""" \\
Avg. Computation Time & """ + f"{analysis['descriptive_statistics']['computation_time']['mean']:.2f}s" + r""" \\
Std. Computation Time & """ + f"{analysis['descriptive_statistics']['computation_time']['std']:.2f}s" + r""" \\
\hline
\end{tabular}
\end{table}
"""
        return latex
    
    def save_latex_summary(self, latex: str):
        """LaTeXサマリー保存"""
        output_file = self.output_dir / "latex_summary.tex"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(latex)
        
        print(f"💾 LaTeXサマリー保存: {output_file}")

def main():
    """メイン実行"""
    generator = ReportGenerator()
    
    # 統計解析結果読み込み
    analysis = generator.load_analysis()
    
    # Markdownレポート生成
    md_report = generator.generate_markdown_report(analysis)
    generator.save_markdown_report(md_report)
    
    # LaTeXサマリー生成
    latex_summary = generator.generate_latex_summary(analysis)
    generator.save_latex_summary(latex_summary)
    
    print("\n✅ レポート生成完了！")

if __name__ == "__main__":
    main()


