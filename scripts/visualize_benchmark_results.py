#!/usr/bin/env python3
"""
ベンチマーク結果の可視化スクリプト

使用方法:
    python3 visualize_benchmark_results.py results/benchmark_results_20231107_120000.json
    python3 visualize_benchmark_results.py results/benchmark_results_*.json --output figures/
"""

import json
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
from typing import Dict, List
import seaborn as sns

# 日本語フォント設定
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans', 'IPAexGothic', 'Noto Sans CJK JP']
matplotlib.rcParams['axes.unicode_minus'] = False

# Seabornスタイル設定
sns.set_style("whitegrid")
sns.set_palette("husl")


class BenchmarkVisualizer:
    """ベンチマーク結果可視化クラス"""
    
    def __init__(self, result_file: str, output_dir: str = None):
        """
        Args:
            result_file: ベンチマーク結果JSONファイルのパス
            output_dir: 図の出力ディレクトリ
        """
        self.result_file = Path(result_file)
        
        if output_dir is None:
            self.output_dir = Path('/home/hayashi/thesis_work/figures')
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 結果をロード
        self.data = self._load_results()
        self.results = self.data['results']
        self.metadata = self.data.get('metadata', {})
        
        # プランナー名リスト
        self.planner_names = ['A*', 'Dijkstra', 'Weighted A* (ε=1.5)', 'RRT*', 'AHA*', 'TA* (提案手法)']
        
        # カラーマップ
        self.colors = {
            'A*': '#FF6B6B',
            'Dijkstra': '#4ECDC4',
            'Weighted A* (ε=1.5)': '#45B7D1',
            'RRT*': '#FFA07A',
            'AHA*': '#9B59B6',
            'TA* (提案手法)': '#2ECC71'  # 新アルゴリズムは緑色
        }
        
        print(f"結果ファイルをロードしました: {self.result_file}")
        print(f"シナリオ数: {len(self.results)}")
        print(f"出力先: {self.output_dir}")
    
    def _load_results(self) -> Dict:
        """結果をロード"""
        with open(self.result_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def plot_computation_time(self):
        """計算時間の比較グラフ"""
        print("\n計算時間比較グラフを作成中...")
        
        scenarios = list(self.results.keys())
        data = {planner: [] for planner in self.planner_names}
        
        for scenario in scenarios:
            for planner in self.planner_names:
                result = self.results[scenario]['results'].get(planner, {})
                time = result.get('computation_time', np.nan) if result.get('success') else np.nan
                data[planner].append(time)
        
        # グラフ描画
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(scenarios))
        width = 0.2
        
        for i, planner in enumerate(self.planner_names):
            offset = width * (i - 1.5)
            bars = ax.bar(
                x + offset,
                data[planner],
                width,
                label=planner,
                color=self.colors.get(planner, None),
                alpha=0.8
            )
            
            # 値ラベル
            for bar in bars:
                height = bar.get_height()
                if not np.isnan(height):
                    ax.text(
                        bar.get_x() + bar.get_width()/2.,
                        height,
                        f'{height:.2f}s',
                        ha='center',
                        va='bottom',
                        fontsize=8,
                        rotation=45
                    )
        
        ax.set_xlabel('シナリオ', fontsize=12)
        ax.set_ylabel('計算時間 (秒)', fontsize=12)
        ax.set_title('アルゴリズム別計算時間比較', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=45, ha='right')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = self.output_dir / 'computation_time_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def plot_nodes_explored(self):
        """探索ノード数の比較グラフ"""
        print("\n探索ノード数比較グラフを作成中...")
        
        scenarios = list(self.results.keys())
        data = {planner: [] for planner in self.planner_names}
        
        for scenario in scenarios:
            for planner in self.planner_names:
                result = self.results[scenario]['results'].get(planner, {})
                nodes = result.get('nodes_explored', 0) if result.get('success') else 0
                data[planner].append(nodes)
        
        # グラフ描画
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(scenarios))
        width = 0.2
        
        for i, planner in enumerate(self.planner_names):
            offset = width * (i - 1.5)
            ax.bar(
                x + offset,
                data[planner],
                width,
                label=planner,
                color=self.colors.get(planner, None),
                alpha=0.8
            )
        
        ax.set_xlabel('シナリオ', fontsize=12)
        ax.set_ylabel('探索ノード数', fontsize=12)
        ax.set_title('アルゴリズム別探索ノード数比較', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=45, ha='right')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.set_yscale('log')  # 対数スケール
        
        plt.tight_layout()
        output_path = self.output_dir / 'nodes_explored_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def plot_path_length(self):
        """経路長の比較グラフ"""
        print("\n経路長比較グラフを作成中...")
        
        scenarios = list(self.results.keys())
        data = {planner: [] for planner in self.planner_names}
        
        for scenario in scenarios:
            for planner in self.planner_names:
                result = self.results[scenario]['results'].get(planner, {})
                distance = result.get('path_distance', np.nan) if result.get('success') else np.nan
                data[planner].append(distance)
        
        # グラフ描画
        fig, ax = plt.subplots(figsize=(14, 6))
        
        x = np.arange(len(scenarios))
        width = 0.2
        
        for i, planner in enumerate(self.planner_names):
            offset = width * (i - 1.5)
            ax.bar(
                x + offset,
                data[planner],
                width,
                label=planner,
                color=self.colors.get(planner, None),
                alpha=0.8
            )
        
        ax.set_xlabel('シナリオ', fontsize=12)
        ax.set_ylabel('経路長 (m)', fontsize=12)
        ax.set_title('アルゴリズム別経路長比較', fontsize=14, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios, rotation=45, ha='right')
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = self.output_dir / 'path_length_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def plot_success_rate(self):
        """成功率の比較グラフ"""
        print("\n成功率比較グラフを作成中...")
        
        success_counts = {planner: 0 for planner in self.planner_names}
        total_scenarios = len(self.results)
        
        for scenario_name, data in self.results.items():
            for planner in self.planner_names:
                result = data['results'].get(planner, {})
                if result.get('success'):
                    success_counts[planner] += 1
        
        success_rates = {
            planner: (count / total_scenarios) * 100
            for planner, count in success_counts.items()
        }
        
        # グラフ描画
        fig, ax = plt.subplots(figsize=(10, 6))
        
        planners = list(success_rates.keys())
        rates = list(success_rates.values())
        colors_list = [self.colors.get(p, 'gray') for p in planners]
        
        bars = ax.bar(planners, rates, color=colors_list, alpha=0.8, edgecolor='black')
        
        # 値ラベル
        for bar, rate in zip(bars, rates):
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width()/2.,
                height,
                f'{rate:.1f}%',
                ha='center',
                va='bottom',
                fontsize=12,
                fontweight='bold'
            )
        
        ax.set_ylabel('成功率 (%)', fontsize=12)
        ax.set_title('アルゴリズム別成功率', fontsize=14, fontweight='bold')
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        output_path = self.output_dir / 'success_rate_comparison.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def plot_performance_radar(self):
        """性能レーダーチャート"""
        print("\n性能レーダーチャートを作成中...")
        
        # 各アルゴリズムの平均性能を計算
        metrics = {
            'computation_time': [],
            'nodes_explored': [],
            'path_distance': [],
            'success_rate': []
        }
        
        for planner in self.planner_names:
            times = []
            nodes = []
            distances = []
            successes = 0
            
            for scenario_name, data in self.results.items():
                result = data['results'].get(planner, {})
                if result.get('success'):
                    times.append(result.get('computation_time', 0))
                    nodes.append(result.get('nodes_explored', 0))
                    distances.append(result.get('path_distance', 0))
                    successes += 1
            
            # 正規化（0-1スケール、小さいほど良い→大きいほど良いに変換）
            avg_time = np.mean(times) if times else 0
            avg_nodes = np.mean(nodes) if nodes else 0
            avg_distance = np.mean(distances) if distances else 0
            success_rate = successes / len(self.results)
            
            metrics['computation_time'].append(avg_time)
            metrics['nodes_explored'].append(avg_nodes)
            metrics['path_distance'].append(avg_distance)
            metrics['success_rate'].append(success_rate)
        
        # 正規化（最大値で割る）
        max_time = max(metrics['computation_time']) if max(metrics['computation_time']) > 0 else 1
        max_nodes = max(metrics['nodes_explored']) if max(metrics['nodes_explored']) > 0 else 1
        max_distance = max(metrics['path_distance']) if max(metrics['path_distance']) > 0 else 1
        
        # 逆正規化（小さいほど良い指標を反転）
        normalized_metrics = []
        for i in range(len(self.planner_names)):
            normalized_metrics.append([
                1 - (metrics['computation_time'][i] / max_time),  # 高速性
                1 - (metrics['nodes_explored'][i] / max_nodes),   # 効率性
                1 - (metrics['path_distance'][i] / max_distance), # 経路最適性
                metrics['success_rate'][i]                        # 成功率
            ])
        
        # レーダーチャート描画
        categories = ['高速性', '効率性', '経路最適性', '成功率']
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        angles += angles[:1]
        
        for i, planner in enumerate(self.planner_names):
            values = normalized_metrics[i]
            values += values[:1]
            
            ax.plot(
                angles,
                values,
                'o-',
                linewidth=2,
                label=planner,
                color=self.colors.get(planner, None)
            )
            ax.fill(angles, values, alpha=0.15, color=self.colors.get(planner, None))
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=12)
        ax.set_ylim(0, 1)
        ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
        ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'])
        ax.set_title('アルゴリズム性能比較（レーダーチャート）', fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
        ax.grid(True)
        
        plt.tight_layout()
        output_path = self.output_dir / 'performance_radar.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def plot_time_vs_distance(self):
        """計算時間 vs 経路長の散布図"""
        print("\n計算時間vs経路長散布図を作成中...")
        
        fig, ax = plt.subplots(figsize=(10, 8))
        
        for planner in self.planner_names:
            times = []
            distances = []
            
            for scenario_name, data in self.results.items():
                result = data['results'].get(planner, {})
                if result.get('success'):
                    times.append(result.get('computation_time', 0))
                    distances.append(result.get('path_distance', 0))
            
            ax.scatter(
                times,
                distances,
                s=100,
                alpha=0.6,
                label=planner,
                color=self.colors.get(planner, None),
                edgecolors='black',
                linewidths=1
            )
        
        ax.set_xlabel('計算時間 (秒)', fontsize=12)
        ax.set_ylabel('経路長 (m)', fontsize=12)
        ax.set_title('計算時間 vs 経路長', fontsize=14, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        output_path = self.output_dir / 'time_vs_distance.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"✓ 保存: {output_path}")
        plt.close()
    
    def generate_all_plots(self):
        """すべてのグラフを生成"""
        print("\n" + "=" * 70)
        print("ベンチマーク結果可視化")
        print("=" * 70)
        
        self.plot_computation_time()
        self.plot_nodes_explored()
        self.plot_path_length()
        self.plot_success_rate()
        self.plot_performance_radar()
        self.plot_time_vs_distance()
        
        print("\n" + "=" * 70)
        print("すべてのグラフ生成が完了しました！")
        print(f"出力先: {self.output_dir}")
        print("=" * 70)


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='ベンチマーク結果の可視化'
    )
    parser.add_argument(
        'result_file',
        type=str,
        help='ベンチマーク結果JSONファイルのパス'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='図の出力ディレクトリ'
    )
    
    args = parser.parse_args()
    
    # 可視化実行
    visualizer = BenchmarkVisualizer(
        result_file=args.result_file,
        output_dir=args.output
    )
    visualizer.generate_all_plots()


if __name__ == '__main__':
    main()
