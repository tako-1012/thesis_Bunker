#!/usr/bin/env python3
"""
visualizer.py
シミュレーション結果の可視化

機能:
- 地形別性能グラフ
- 難易度別比較
- 計算時間分布ヒストグラム
- 箱ひげ図
- 散布図（相関）
- ヒートマップ
"""

import json
import numpy as np
import matplotlib
matplotlib.use('Agg')  # GUIなし環境対応
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from typing import Dict, List
from collections import defaultdict

from statistics_analyzer import StatisticsAnalyzer

class ResultVisualizer:
    """結果可視化クラス"""
    
    def __init__(self):
        self.analyzer = StatisticsAnalyzer()
        self.output_dir = Path("results/figures")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # スタイル設定
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (10, 6)
        plt.rcParams['font.size'] = 10
    
    def load_data(self):
        """データ読み込み"""
        self.analyzer.load_data()
    
    def plot_terrain_type_performance(self):
        """地形タイプ別性能グラフ"""
        terrain_analysis = self.analyzer.analyze_by_terrain_type()
        
        terrain_types = list(terrain_analysis.keys())
        success_rates = [terrain_analysis[t]['success_rate'] for t in terrain_types]
        avg_times = [terrain_analysis[t]['avg_computation_time'] for t in terrain_types]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 成功率
        ax1.bar(terrain_types, success_rates, color='skyblue', edgecolor='navy')
        ax1.set_ylabel('Success Rate (%)', fontsize=12)
        ax1.set_title('Success Rate by Terrain Type', fontsize=14, fontweight='bold')
        ax1.set_ylim([0, 105])
        ax1.tick_params(axis='x', rotation=45)
        
        # 計算時間
        ax2.bar(terrain_types, avg_times, color='lightcoral', edgecolor='darkred')
        ax2.set_ylabel('Avg Computation Time (s)', fontsize=12)
        ax2.set_title('Computation Time by Terrain Type', fontsize=14, fontweight='bold')
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'terrain_type_performance.png', dpi=300)
        plt.close()
        
        print("✅ 地形タイプ別性能グラフ保存")
    
    def plot_computation_time_distribution(self):
        """計算時間分布ヒストグラム"""
        times = [r.computation_time for r in self.analyzer.results]
        
        plt.figure(figsize=(10, 6))
        plt.hist(times, bins=30, color='steelblue', edgecolor='black', alpha=0.7)
        plt.axvline(np.mean(times), color='red', linestyle='--', linewidth=2, label=f'Mean: {np.mean(times):.2f}s')
        plt.axvline(np.median(times), color='green', linestyle='--', linewidth=2, label=f'Median: {np.median(times):.2f}s')
        plt.xlabel('Computation Time (s)', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title('Distribution of Computation Time', fontsize=14, fontweight='bold')
        plt.legend()
        plt.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'computation_time_distribution.png', dpi=300)
        plt.close()
        
        print("✅ 計算時間分布ヒストグラム保存")
    
    def plot_boxplot_by_terrain(self):
        """地形タイプ別箱ひげ図"""
        data_by_terrain = defaultdict(list)
        
        for result in self.analyzer.results:
            terrain_info = self.analyzer.terrain_type_map.get(result.scenario_id)
            if terrain_info:
                data_by_terrain[terrain_info['terrain_type']].append(result.computation_time)
        
        terrain_types = list(data_by_terrain.keys())
        data = [data_by_terrain[t] for t in terrain_types]
        
        plt.figure(figsize=(12, 6))
        bp = plt.boxplot(data, labels=terrain_types, patch_artist=True)
        
        for patch in bp['boxes']:
            patch.set_facecolor('lightblue')
            patch.set_edgecolor('navy')
        
        plt.ylabel('Computation Time (s)', fontsize=12)
        plt.title('Computation Time Distribution by Terrain Type', fontsize=14, fontweight='bold')
        plt.xticks(rotation=45)
        plt.grid(axis='y', alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'boxplot_by_terrain.png', dpi=300)
        plt.close()
        
        print("✅ 箱ひげ図保存")
    
    def plot_correlation_scatter(self):
        """相関散布図"""
        max_slopes = []
        obstacle_densities = []
        computation_times = []
        
        for result in self.analyzer.results:
            terrain_info = self.analyzer.terrain_type_map.get(result.scenario_id)
            if terrain_info:
                max_slopes.append(terrain_info['max_slope'])
                obstacle_densities.append(terrain_info['obstacle_density'])
                computation_times.append(result.computation_time)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
        
        # 最大勾配 vs 計算時間
        ax1.scatter(max_slopes, computation_times, alpha=0.6, color='blue')
        ax1.set_xlabel('Max Slope (degrees)', fontsize=12)
        ax1.set_ylabel('Computation Time (s)', fontsize=12)
        ax1.set_title('Max Slope vs Computation Time', fontsize=14, fontweight='bold')
        ax1.grid(alpha=0.3)
        
        # 障害物密度 vs 計算時間
        ax2.scatter(obstacle_densities, computation_times, alpha=0.6, color='red')
        ax2.set_xlabel('Obstacle Density', fontsize=12)
        ax2.set_ylabel('Computation Time (s)', fontsize=12)
        ax2.set_title('Obstacle Density vs Computation Time', fontsize=14, fontweight='bold')
        ax2.grid(alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'correlation_scatter.png', dpi=300)
        plt.close()
        
        print("✅ 相関散布図保存")
    
    def plot_difficulty_comparison(self):
        """難易度別比較"""
        difficulty_analysis = self.analyzer.analyze_by_difficulty()
        
        difficulties = ['easy', 'medium', 'hard']
        success_rates = [difficulty_analysis.get(d, {}).get('success_rate', 0) for d in difficulties]
        avg_times = [difficulty_analysis.get(d, {}).get('avg_computation_time', 0) for d in difficulties]
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # 成功率
        colors = ['green', 'orange', 'red']
        ax1.bar(difficulties, success_rates, color=colors, edgecolor='black')
        ax1.set_ylabel('Success Rate (%)', fontsize=12)
        ax1.set_title('Success Rate by Difficulty', fontsize=14, fontweight='bold')
        ax1.set_ylim([0, 105])
        
        # 計算時間
        ax2.bar(difficulties, avg_times, color=colors, edgecolor='black')
        ax2.set_ylabel('Avg Computation Time (s)', fontsize=12)
        ax2.set_title('Computation Time by Difficulty', fontsize=14, fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.output_dir / 'difficulty_comparison.png', dpi=300)
        plt.close()
        
        print("✅ 難易度別比較グラフ保存")
    
    def generate_all_figures(self):
        """全グラフ生成"""
        print("\n📊 可視化開始...")
        
        self.plot_terrain_type_performance()
        self.plot_computation_time_distribution()
        self.plot_boxplot_by_terrain()
        self.plot_correlation_scatter()
        self.plot_difficulty_comparison()
        
        print(f"\n✅ 全グラフ保存完了: {self.output_dir}/")

def main():
    """メイン実行"""
    visualizer = ResultVisualizer()
    visualizer.load_data()
    visualizer.generate_all_figures()

if __name__ == "__main__":
    main()


