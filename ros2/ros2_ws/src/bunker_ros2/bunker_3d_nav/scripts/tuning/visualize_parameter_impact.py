#!/usr/bin/env python3
"""
パラメータ変化の影響を可視化
ヒートマップ生成によるパラメータ感度分析
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import sys
import os
import json
from typing import Dict, List, Tuple, Any
import warnings
warnings.filterwarnings('ignore')

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))


class ParameterVisualizer:
    """パラメータの影響を可視化するクラス"""
    
    def __init__(self, output_dir: str = './tuning_results'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # 可視化の設定
        plt.style.use('seaborn-v0_8')
        sns.set_palette("husl")
        
        # 評価指標
        self.metrics = [
            'path_length',
            'max_slope',
            'computation_time',
            'success_rate',
            'total_cost'
        ]
        
        # パラメータ
        self.parameters = [
            'voxel_size',
            'distance_weight',
            'slope_weight',
            'obstacle_weight',
            'stability_weight',
            'max_slope_angle',
            'stability_threshold'
        ]
    
    def load_results(self, filename: str = None) -> pd.DataFrame:
        """結果を読み込み"""
        if filename is None:
            filename = os.path.join(self.output_dir, 'parameter_sweep_results.csv')
        
        if not os.path.exists(filename):
            raise FileNotFoundError(f"Results file not found: {filename}")
        
        df = pd.read_csv(filename)
        print(f"Loaded {len(df)} parameter combinations")
        
        return df
    
    def create_heatmap(self, df: pd.DataFrame, param1: str, param2: str, 
                      metric: str, output_filename: str = None) -> None:
        """2つのパラメータの影響をヒートマップで可視化"""
        if param1 not in df.columns or param2 not in df.columns:
            raise ValueError(f"Parameters {param1} or {param2} not found in data")
        
        if metric not in df.columns:
            raise ValueError(f"Metric {metric} not found in data")
        
        # ピボットテーブルを作成
        pivot_table = df.pivot_table(
            values=metric,
            index=param1,
            columns=param2,
            aggfunc='mean',
            fill_value=np.nan
        )
        
        # ヒートマップを作成
        plt.figure(figsize=(10, 8))
        sns.heatmap(
            pivot_table,
            annot=True,
            fmt='.2f',
            cmap='viridis',
            cbar_kws={'label': metric}
        )
        
        plt.title(f'{metric} vs {param1} and {param2}')
        plt.xlabel(param2)
        plt.ylabel(param1)
        
        # 保存
        if output_filename is None:
            output_filename = os.path.join(
                self.output_dir, 
                f'heatmap_{param1}_{param2}_{metric}.png'
            )
        
        plt.savefig(output_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Heatmap saved: {output_filename}")
    
    def create_parameter_impact_plot(self, df: pd.DataFrame, 
                                   output_filename: str = None) -> None:
        """パラメータの影響を可視化"""
        # 成功した組み合わせのみを対象
        successful_df = df[df['success_rate'] > 0].copy()
        
        if len(successful_df) == 0:
            print("No successful combinations found")
            return
        
        # 相関行列を計算
        param_cols = [col for col in self.parameters if col in successful_df.columns]
        metric_cols = [col for col in self.metrics if col in successful_df.columns]
        
        correlation_data = successful_df[param_cols + metric_cols].corr()
        
        # パラメータとメトリクスの相関のみを抽出
        param_metric_corr = correlation_data.loc[param_cols, metric_cols]
        
        # ヒートマップを作成
        plt.figure(figsize=(12, 8))
        sns.heatmap(
            param_metric_corr,
            annot=True,
            fmt='.3f',
            cmap='RdBu_r',
            center=0,
            cbar_kws={'label': 'Correlation'}
        )
        
        plt.title('Parameter Impact on Metrics')
        plt.xlabel('Metrics')
        plt.ylabel('Parameters')
        
        # 保存
        if output_filename is None:
            output_filename = os.path.join(self.output_dir, 'parameter_impact.png')
        
        plt.savefig(output_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Parameter impact plot saved: {output_filename}")
    
    def create_metric_distribution_plot(self, df: pd.DataFrame, 
                                     output_filename: str = None) -> None:
        """メトリクスの分布を可視化"""
        # 成功した組み合わせのみを対象
        successful_df = df[df['success_rate'] > 0].copy()
        
        if len(successful_df) == 0:
            print("No successful combinations found")
            return
        
        # メトリクスの分布をプロット
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.ravel()
        
        for i, metric in enumerate(self.metrics):
            if metric in successful_df.columns:
                axes[i].hist(successful_df[metric], bins=30, alpha=0.7, edgecolor='black')
                axes[i].set_title(f'{metric} Distribution')
                axes[i].set_xlabel(metric)
                axes[i].set_ylabel('Frequency')
                
                # 統計情報を表示
                mean_val = successful_df[metric].mean()
                std_val = successful_df[metric].std()
                axes[i].axvline(mean_val, color='red', linestyle='--', 
                              label=f'Mean: {mean_val:.2f}')
                axes[i].axvline(mean_val + std_val, color='orange', linestyle='--', 
                              label=f'+1σ: {mean_val + std_val:.2f}')
                axes[i].axvline(mean_val - std_val, color='orange', linestyle='--', 
                              label=f'-1σ: {mean_val - std_val:.2f}')
                axes[i].legend()
        
        # 最後のサブプロットを削除
        if len(self.metrics) < len(axes):
            fig.delaxes(axes[-1])
        
        plt.tight_layout()
        
        # 保存
        if output_filename is None:
            output_filename = os.path.join(self.output_dir, 'metric_distribution.png')
        
        plt.savefig(output_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Metric distribution plot saved: {output_filename}")
    
    def create_parameter_sensitivity_plot(self, df: pd.DataFrame, 
                                        output_filename: str = None) -> None:
        """パラメータの感度を可視化"""
        # 成功した組み合わせのみを対象
        successful_df = df[df['success_rate'] > 0].copy()
        
        if len(successful_df) == 0:
            print("No successful combinations found")
            return
        
        # パラメータごとの感度を計算
        sensitivity_data = []
        
        for param in self.parameters:
            if param in successful_df.columns:
                # パラメータの範囲を取得
                param_min = successful_df[param].min()
                param_max = successful_df[param].max()
                
                # パラメータを3つの範囲に分割
                param_low = successful_df[successful_df[param] <= param_min + (param_max - param_min) / 3]
                param_mid = successful_df[
                    (successful_df[param] > param_min + (param_max - param_min) / 3) &
                    (successful_df[param] <= param_min + 2 * (param_max - param_min) / 3)
                ]
                param_high = successful_df[successful_df[param] > param_min + 2 * (param_max - param_min) / 3]
                
                # 各範囲でのメトリクスの平均を計算
                for metric in self.metrics:
                    if metric in successful_df.columns:
                        sensitivity_data.append({
                            'parameter': param,
                            'metric': metric,
                            'range': 'Low',
                            'value': param_low[metric].mean() if len(param_low) > 0 else np.nan
                        })
                        sensitivity_data.append({
                            'parameter': param,
                            'metric': metric,
                            'range': 'Mid',
                            'value': param_mid[metric].mean() if len(param_mid) > 0 else np.nan
                        })
                        sensitivity_data.append({
                            'parameter': param,
                            'metric': metric,
                            'range': 'High',
                            'value': param_high[metric].mean() if len(param_high) > 0 else np.nan
                        })
        
        sensitivity_df = pd.DataFrame(sensitivity_data)
        
        # 感度プロットを作成
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        axes = axes.ravel()
        
        for i, metric in enumerate(self.metrics):
            if metric in sensitivity_df['metric'].values:
                metric_data = sensitivity_df[sensitivity_df['metric'] == metric]
                
                # パラメータごとの感度をプロット
                for param in self.parameters:
                    if param in metric_data['parameter'].values:
                        param_data = metric_data[metric_data['parameter'] == param]
                        
                        axes[i].plot(
                            param_data['range'],
                            param_data['value'],
                            marker='o',
                            label=param,
                            linewidth=2
                        )
                
                axes[i].set_title(f'{metric} Sensitivity')
                axes[i].set_xlabel('Parameter Range')
                axes[i].set_ylabel(metric)
                axes[i].legend()
                axes[i].grid(True, alpha=0.3)
        
        # 最後のサブプロットを削除
        if len(self.metrics) < len(axes):
            fig.delaxes(axes[-1])
        
        plt.tight_layout()
        
        # 保存
        if output_filename is None:
            output_filename = os.path.join(self.output_dir, 'parameter_sensitivity.png')
        
        plt.savefig(output_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Parameter sensitivity plot saved: {output_filename}")
    
    def create_optimization_landscape(self, df: pd.DataFrame, 
                                    output_filename: str = None) -> None:
        """最適化の風景を可視化"""
        # 成功した組み合わせのみを対象
        successful_df = df[df['success_rate'] > 0].copy()
        
        if len(successful_df) == 0:
            print("No successful combinations found")
            return
        
        # 2つの主要なパラメータを選択
        param1 = 'slope_weight'
        param2 = 'obstacle_weight'
        
        if param1 not in successful_df.columns or param2 not in successful_df.columns:
            print(f"Parameters {param1} or {param2} not found in data")
            return
        
        # 3D散布図を作成
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # データをプロット
        scatter = ax.scatter(
            successful_df[param1],
            successful_df[param2],
            successful_df['total_cost'],
            c=successful_df['total_cost'],
            cmap='viridis',
            s=50,
            alpha=0.7
        )
        
        ax.set_xlabel(param1)
        ax.set_ylabel(param2)
        ax.set_zlabel('Total Cost')
        ax.set_title('Optimization Landscape')
        
        # カラーバーを追加
        plt.colorbar(scatter, ax=ax, shrink=0.5, aspect=5)
        
        # 保存
        if output_filename is None:
            output_filename = os.path.join(self.output_dir, 'optimization_landscape.png')
        
        plt.savefig(output_filename, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"Optimization landscape saved: {output_filename}")
    
    def generate_all_visualizations(self, df: pd.DataFrame) -> None:
        """すべての可視化を生成"""
        print("Generating all visualizations...")
        
        # パラメータの影響プロット
        self.create_parameter_impact_plot(df)
        
        # メトリクスの分布プロット
        self.create_metric_distribution_plot(df)
        
        # パラメータの感度プロット
        self.create_parameter_sensitivity_plot(df)
        
        # 最適化の風景
        self.create_optimization_landscape(df)
        
        # 主要なパラメータの組み合わせのヒートマップ
        important_pairs = [
            ('slope_weight', 'obstacle_weight', 'total_cost'),
            ('voxel_size', 'computation_time', 'computation_time'),
            ('max_slope_angle', 'stability_threshold', 'max_slope'),
            ('distance_weight', 'slope_weight', 'path_length')
        ]
        
        for param1, param2, metric in important_pairs:
            if (param1 in df.columns and param2 in df.columns and 
                metric in df.columns):
                self.create_heatmap(df, param1, param2, metric)
        
        print("All visualizations generated!")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Visualize parameter impact')
    parser.add_argument('--input-file', type=str, default=None,
                       help='Input CSV file with results')
    parser.add_argument('--output-dir', type=str, default='./tuning_results',
                       help='Output directory for visualizations')
    parser.add_argument('--param1', type=str, default='slope_weight',
                       help='First parameter for heatmap')
    parser.add_argument('--param2', type=str, default='obstacle_weight',
                       help='Second parameter for heatmap')
    parser.add_argument('--metric', type=str, default='total_cost',
                       help='Metric for heatmap')
    parser.add_argument('--all', action='store_true',
                       help='Generate all visualizations')
    
    args = parser.parse_args()
    
    # 可視化器を作成
    visualizer = ParameterVisualizer(output_dir=args.output_dir)
    
    try:
        # 結果を読み込み
        df = visualizer.load_results(args.input_file)
        
        if args.all:
            # すべての可視化を生成
            visualizer.generate_all_visualizations(df)
        else:
            # 特定のヒートマップを生成
            visualizer.create_heatmap(df, args.param1, args.param2, args.metric)
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == '__main__':
    main()
