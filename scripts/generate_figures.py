#!/usr/bin/env python3
"""
論文用図表生成スクリプト

入力: benchmark_96_scenarios_combined.json
出力:
  - figures/fig1_boxplot.{png,pdf}
  - figures/fig2_ta_distribution.{png,pdf}
  - figures/fig3_complexity_comparison.{png,pdf}
  - figures/fig4_success_rate.{png,pdf}
"""

import json
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import matplotlib
matplotlib.use('Agg')  # GUI不要

# 日本語フォント設定
plt.rcParams['font.family'] = ['DejaVu Sans', 'sans-serif']
plt.rcParams['font.size'] = 10
plt.rcParams['axes.labelsize'] = 12
plt.rcParams['axes.titlesize'] = 14
plt.rcParams['xtick.labelsize'] = 10
plt.rcParams['ytick.labelsize'] = 10
plt.rcParams['legend.fontsize'] = 10
plt.rcParams['figure.titlesize'] = 16

# 高解像度設定
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'

class ThesisFigureGenerator:
    def __init__(self, data_file):
        with open(data_file, 'r') as f:
            self.data = json.load(f)
        
        self.methods = self.data['metadata']['methods']
        self.output_dir = Path('figures')
        self.output_dir.mkdir(exist_ok=True)
        
        # カラーパレット（論文品質）
        self.colors = {
            'TA*': '#E74C3C',          # Red
            'AHA*': '#3498DB',         # Blue
            'Theta*': '#2ECC71',       # Green
            'FieldD*Hybrid': '#F39C12' # Orange
        }
    
    def extract_all_data(self, method):
        """指定メソッドのすべてのデータを抽出"""
        times = []
        successes = []
        complexities = []
        
        for scenario_id, scenario_data in self.data['results'].items():
            if method in scenario_data['results']:
                result = scenario_data['results'][method]
                times.append(result.get('computation_time', 0))
                successes.append(result.get('success', True))
                
                # 複雑度分類
                if 'SMALL' in scenario_id:
                    complexities.append('Simple')
                elif 'MEDIUM' in scenario_id:
                    complexities.append('Medium')
                elif 'LARGE' in scenario_id:
                    complexities.append('Complex')
                else:
                    complexities.append('Medium')
        
        return np.array(times), np.array(successes), complexities
    
    def generate_fig1_boxplot(self):
        """図1: 4アルゴリズムの計算時間（箱ひげ図）"""
        print("📊 図1: 計算時間の箱ひげ図を生成中...")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # データ収集
        data_for_plot = []
        labels = []
        success_rates = []
        
        for method in self.methods:
            times, successes, _ = self.extract_all_data(method)
            data_for_plot.append(times)
            labels.append(method)
            success_rate = np.sum(successes) / len(successes) * 100
            success_rates.append(success_rate)
        
        # 箱ひげ図（対数スケール）
        bp = ax.boxplot(data_for_plot, labels=labels, patch_artist=True,
                       showmeans=True, meanprops=dict(marker='D', markerfacecolor='red', markersize=6))
        
        # 色設定
        for patch, method in zip(bp['boxes'], self.methods):
            patch.set_facecolor(self.colors[method])
            patch.set_alpha(0.7)
        
        # 対数スケール
        ax.set_yscale('log')
        ax.set_ylabel('Computation Time (s, log scale)', fontweight='bold')
        ax.set_xlabel('Algorithm', fontweight='bold')
        ax.set_title('Computation Time Comparison (n=96)', fontweight='bold', fontsize=16)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # 成功率を凡例として追加
        legend_text = [f"{method} (Success: {sr:.1f}%)" 
                      for method, sr in zip(labels, success_rates)]
        ax.legend(bp['boxes'], legend_text, loc='upper left', framealpha=0.9)
        
        # 保存
        plt.tight_layout()
        fig.savefig(self.output_dir / 'fig1_boxplot.png', dpi=300, bbox_inches='tight')
        fig.savefig(self.output_dir / 'fig1_boxplot.pdf', bbox_inches='tight')
        plt.close(fig)
        
        print(f"  ✅ fig1_boxplot.png, fig1_boxplot.pdf")
    
    def generate_fig2_ta_distribution(self):
        """図2: TA*の計算時間分布（ヒストグラム）"""
        print("\n📊 図2: TA*計算時間分布のヒストグラムを生成中...")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # TA*のデータ取得
        ta_times, _, _ = self.extract_all_data('TA*')
        
        # ヒストグラム
        n, bins, patches = ax.hist(ta_times, bins=30, alpha=0.7, 
                                   color=self.colors['TA*'], edgecolor='black', linewidth=0.5)
        
        # 統計値
        mean_val = np.mean(ta_times)
        median_val = np.median(ta_times)
        
        # 中央値と平均値の線
        ax.axvline(median_val, color='red', linestyle='--', linewidth=2.5, 
                  label=f'Median: {median_val:.2f}s')
        ax.axvline(mean_val, color='blue', linestyle='--', linewidth=2.5, 
                  label=f'Mean: {mean_val:.2f}s')
        
        ax.set_xlabel('Computation Time (s)', fontweight='bold')
        ax.set_ylabel('Frequency', fontweight='bold')
        ax.set_title('TA* Computation Time Distribution (n=96)', fontweight='bold', fontsize=16)
        ax.legend(loc='upper right', framealpha=0.9, fontsize=11)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 保存
        plt.tight_layout()
        fig.savefig(self.output_dir / 'fig2_ta_distribution.png', dpi=300, bbox_inches='tight')
        fig.savefig(self.output_dir / 'fig2_ta_distribution.pdf', bbox_inches='tight')
        plt.close(fig)
        
        print(f"  ✅ fig2_ta_distribution.png, fig2_ta_distribution.pdf")
    
    def generate_fig3_complexity_comparison(self):
        """図3: 地形複雑度別性能比較（グループ棒グラフ）"""
        print("\n📊 図3: 複雑度別性能比較のグループ棒グラフを生成中...")
        
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # 複雑度ごとのデータ収集
        complexity_levels = ['Simple', 'Medium', 'Complex']
        complexity_data = {level: {method: [] for method in self.methods} 
                          for level in complexity_levels}
        
        for method in self.methods:
            times, _, complexities = self.extract_all_data(method)
            for time, comp in zip(times, complexities):
                complexity_data[comp][method].append(time)
        
        # 棒グラフの準備
        x = np.arange(len(complexity_levels))
        width = 0.2
        
        for i, method in enumerate(self.methods):
            means = [np.mean(complexity_data[level][method]) if len(complexity_data[level][method]) > 0 else 0 
                    for level in complexity_levels]
            stds = [np.std(complexity_data[level][method], ddof=1) if len(complexity_data[level][method]) > 1 else 0 
                   for level in complexity_levels]
            
            offset = (i - 1.5) * width
            bars = ax.bar(x + offset, means, width, label=method, 
                         color=self.colors[method], alpha=0.8, 
                         yerr=stds, capsize=5, error_kw={'linewidth': 1.5})
        
        ax.set_xlabel('Terrain Complexity', fontweight='bold')
        ax.set_ylabel('Mean Computation Time (s)', fontweight='bold')
        ax.set_title('Performance by Terrain Complexity', fontweight='bold', fontsize=16)
        ax.set_xticks(x)
        ax.set_xticklabels(complexity_levels)
        ax.legend(loc='upper left', framealpha=0.9, ncol=2)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        ax.set_yscale('log')
        
        # 保存
        plt.tight_layout()
        fig.savefig(self.output_dir / 'fig3_complexity_comparison.png', dpi=300, bbox_inches='tight')
        fig.savefig(self.output_dir / 'fig3_complexity_comparison.pdf', bbox_inches='tight')
        plt.close(fig)
        
        print(f"  ✅ fig3_complexity_comparison.png, fig3_complexity_comparison.pdf")
    
    def generate_fig4_success_rate(self):
        """図4: 成功率比較（棒グラフ）"""
        print("\n📊 図4: 成功率比較の棒グラフを生成中...")
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # 成功率データ収集
        success_rates = []
        for method in self.methods:
            _, successes, _ = self.extract_all_data(method)
            success_rate = np.sum(successes) / len(successes) * 100
            success_rates.append(success_rate)
        
        # 棒グラフ
        x = np.arange(len(self.methods))
        bars = ax.bar(x, success_rates, color=[self.colors[m] for m in self.methods], 
                     alpha=0.8, edgecolor='black', linewidth=1.5)
        
        # 値をバーの上に表示
        for i, (bar, rate) in enumerate(zip(bars, success_rates)):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2., height + 0.5,
                   f'{rate:.1f}%', ha='center', va='bottom', fontweight='bold', fontsize=11)
        
        ax.set_xlabel('Algorithm', fontweight='bold')
        ax.set_ylabel('Success Rate (%)', fontweight='bold')
        ax.set_title('Success Rate Comparison (n=96)', fontweight='bold', fontsize=16)
        ax.set_xticks(x)
        ax.set_xticklabels(self.methods)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3, axis='y', linestyle='--')
        
        # 100%ラインを強調
        ax.axhline(100, color='red', linestyle='--', linewidth=2, alpha=0.7, label='100% Success Target')
        ax.legend(loc='lower right', framealpha=0.9)
        
        # 保存
        plt.tight_layout()
        fig.savefig(self.output_dir / 'fig4_success_rate.png', dpi=300, bbox_inches='tight')
        fig.savefig(self.output_dir / 'fig4_success_rate.pdf', bbox_inches='tight')
        plt.close(fig)
        
        print(f"  ✅ fig4_success_rate.png, fig4_success_rate.pdf")
    
    def generate_all_figures(self):
        """すべての図を生成"""
        print("=" * 60)
        print("📊 論文用図表の生成開始")
        print("=" * 60)
        
        self.generate_fig1_boxplot()
        self.generate_fig2_ta_distribution()
        self.generate_fig3_complexity_comparison()
        self.generate_fig4_success_rate()
        
        print("\n" + "=" * 60)
        print("✅ すべての図表の生成完了")
        print("=" * 60)
        print(f"\n出力先: {self.output_dir}/")
        print("  - fig1_boxplot.{png,pdf}")
        print("  - fig2_ta_distribution.{png,pdf}")
        print("  - fig3_complexity_comparison.{png,pdf}")
        print("  - fig4_success_rate.{png,pdf}")
        print("\n📋 論文品質:")
        print("  - 解像度: 300 DPI")
        print("  - フォーマット: PNG (プレビュー用), PDF (論文用)")
        print("  - カラー: 論文用配色")

if __name__ == '__main__':
    generator = ThesisFigureGenerator('benchmark_96_scenarios_combined.json')
    generator.generate_all_figures()
