#!/usr/bin/env python3
"""
Algorithm Comparison System
複数の経路計画アルゴリズムを比較評価するシステム
"""

import os
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Tuple
import logging
from pathlib import Path
import psutil
import gc

# 統計分析用
from scipy import stats
from statsmodels.stats.multicomp import pairwise_tukeyhsd
from statsmodels.stats.anova import anova_lm
from statsmodels.formula.api import ols

# アルゴリズムインポート
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dijkstra_planner_3d_improved import DijkstraPlanner3D
from weighted_astar_planner_3d import WeightedAStarPlanner3D
from rrt_star_planner_3d import RRTStarPlanner3D
from astar_planner_3d import AStarPlanner3D
from terrain_aware_astar_planner_3d import TerrainAwareAStarPlanner3D

class AlgorithmComparison:
    """
    複数のアルゴリズムを比較評価
    """
    
    def __init__(self, results_dir: str = None):
        """
        初期化
        
        Args:
            results_dir: 結果保存ディレクトリ
        """
        if results_dir is None:
            self.results_dir = Path(__file__).parent.parent / "results" / "algorithm_comparison"
        else:
            self.results_dir = Path(results_dir)
        
        # ディレクトリ作成
        self.results_dir.mkdir(parents=True, exist_ok=True)
        (self.results_dir / "figures").mkdir(exist_ok=True)
        (self.results_dir / "tables").mkdir(exist_ok=True)
        
        # アルゴリズム初期化
        # 元のA*と同じパラメータ
        self.grid_size = (100, 100, 30)  # 元のA*と同じ
        self.voxel_size = 0.1
        self.max_slope = 30.0
        
        self.algorithms = {
            'Dijkstra': DijkstraPlanner3D(self.grid_size, self.voxel_size, self.max_slope),
            'A*': AStarPlanner3D(self.grid_size, self.voxel_size, self.max_slope),
            'Weighted A*': WeightedAStarPlanner3D(self.grid_size, self.voxel_size, self.max_slope, epsilon=1.5),
            'RRT*': RRTStarPlanner3D(self.grid_size, self.voxel_size, self.max_slope, max_iterations=5000),
            'TA-A* (Proposed)': TerrainAwareAStarPlanner3D(self.grid_size, self.voxel_size, self.max_slope)
        }
        
        # 結果格納
        self.results = {algo_name: [] for algo_name in self.algorithms.keys()}
        
        # ログ設定
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # 統計分析結果
        self.statistical_results = {}
    
    def run_comparison(self, scenarios: List[Dict[str, Any]]) -> None:
        """
        全アルゴリズムで全シナリオを実行
        
        Args:
            scenarios: シナリオリスト
        """
        self.logger.info(f"Starting algorithm comparison with {len(scenarios)} scenarios")
        self.logger.info(f"Total experiments: {len(scenarios)} × {len(self.algorithms)} = {len(scenarios) * len(self.algorithms)}")
        
        total_experiments = len(scenarios) * len(self.algorithms)
        completed = 0
        
        for algo_name, planner in self.algorithms.items():
            self.logger.info(f"Running {algo_name}...")
            
            for i, scenario in enumerate(scenarios):
                try:
                    result = self.run_single_test(planner, scenario, algo_name)
                    self.results[algo_name].append(result)
                    
                    completed += 1
                    if completed % 50 == 0:
                        self.logger.info(f"Progress: {completed}/{total_experiments} ({completed/total_experiments*100:.1f}%)")
                
                except Exception as e:
                    self.logger.error(f"Error in {algo_name} scenario {i}: {e}")
                    # エラー結果を記録
                    error_result = {
                        'algorithm': algo_name,
                        'scenario_id': scenario.get('scenario_id', i),
                        'success': False,
                        'computation_time': 0.0,
                        'path_length': 0.0,
                        'nodes_explored': 0,
                        'memory_usage': 0.0,
                        'error_message': str(e)
                    }
                    self.results[algo_name].append(error_result)
                    completed += 1
        
        self.logger.info("All experiments completed!")
        
        # 結果保存
        self.save_results()
        
        # 統計分析
        self.analyze_results()
        
        # 可視化（一時的に無効化）
        # self.visualize_results()
    
    def run_single_test(self, planner: Any, scenario: Dict[str, Any], 
                       algo_name: str) -> Dict[str, Any]:
        """
        単一テスト実行
        
        Args:
            planner: プランナーインスタンス
            scenario: シナリオデータ
            algo_name: アルゴリズム名
            
        Returns:
            結果辞書
        """
        # メモリ使用量計測開始
        process = psutil.Process()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # 地形データ生成
        terrain_data = self.generate_terrain_data(scenario)
        
        # スタート・ゴール位置
        start = scenario['start_position']
        goal = scenario['goal_position']
        
        # 経路計画実行
        if algo_name == 'A*':
            # A*はterrain_dataを期待しない、リストを返す
            path = planner.plan_path(start, goal)
            if path is not None:
                result = {
                    'success': True,
                    'path': path,
                    'computation_time': planner.last_search_stats['computation_time'],
                    'path_length': len(path),
                    'nodes_explored': planner.last_search_stats['nodes_explored'],
                    'error_message': ''
                }
            else:
                result = {
                    'success': False,
                    'path': [],
                    'computation_time': planner.last_search_stats['computation_time'],
                    'path_length': 0,
                    'nodes_explored': planner.last_search_stats['nodes_explored'],
                    'error_message': 'No path found'
                }
        elif algo_name == 'TA-A* (Proposed)':
            # TA-A*の特別な結果処理（辞書形式で返される）
            result = planner.plan_path(start, goal, terrain_data)
            # 辞書形式なのでそのまま使用
        else:
            # 他のアルゴリズムはterrain_dataが必要
            result = planner.plan_path(start, goal, terrain_data)
        
        # メモリ使用量計測終了
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_usage = memory_after - memory_before
        
        # 結果に追加情報を付与
        result['algorithm'] = algo_name
        result['scenario_id'] = scenario.get('scenario_id', 0)
        result['scenario_name'] = scenario.get('name', 'unknown')
        result['terrain_type'] = scenario.get('terrain_params', {}).get('terrain_type', 'unknown')
        result['memory_usage'] = memory_usage
        
        # 経路の滑らかさ計算
        if result['success'] and len(result['path']) > 2:
            result['path_smoothness'] = self.calculate_path_smoothness(result['path'])
        else:
            result['path_smoothness'] = 0.0
        
        # 安全性スコア計算
        result['safety_score'] = self.calculate_safety_score(result, terrain_data)
        
        # ガベージコレクション
        gc.collect()
        
        return result
    
    def generate_terrain_data(self, scenario: Dict[str, Any]) -> np.ndarray:
        """
        シナリオから地形データを生成
        
        Args:
            scenario: シナリオデータ
            
        Returns:
            3D地形データ
        """
        terrain_data = np.zeros(self.grid_size, dtype=int)
        
        # 地形タイプに応じて障害物を配置
        terrain_params = scenario.get('terrain_params', {})
        terrain_type = terrain_params.get('terrain_type', 'flat_terrain')
        
        if terrain_type == 'obstacle_field':
            # 障害物フィールド
            obstacle_density = terrain_params.get('obstacle_density', 0.1)
            self.add_random_obstacles(terrain_data, obstacle_density)
        
        elif terrain_type == 'narrow_passage':
            # 狭い通路
            self.add_narrow_passage_obstacles(terrain_data)
        
        elif terrain_type == 'complex_3d':
            # 複雑な3D地形
            self.add_complex_3d_obstacles(terrain_data)
        
        return terrain_data
    
    def add_random_obstacles(self, terrain_data: np.ndarray, density: float):
        """ランダム障害物を追加"""
        num_obstacles = int(np.prod(self.grid_size) * density)
        
        for _ in range(num_obstacles):
            x = np.random.randint(0, self.grid_size[0])
            y = np.random.randint(0, self.grid_size[1])
            z = np.random.randint(0, self.grid_size[2])
            
            # 障害物サイズ
            size = np.random.randint(2, 5)
            for dx in range(size):
                for dy in range(size):
                    for dz in range(size):
                        nx, ny, nz = x + dx, y + dy, z + dz
                        if (0 <= nx < self.grid_size[0] and 
                            0 <= ny < self.grid_size[1] and 
                            0 <= nz < self.grid_size[2]):
                            terrain_data[nx, ny, nz] = 2
    
    def add_narrow_passage_obstacles(self, terrain_data: np.ndarray):
        """狭い通路の障害物を追加"""
        # 壁を作成
        wall_thickness = 3
        passage_width = 5
        
        # 左の壁
        terrain_data[:wall_thickness, :, :] = 2
        
        # 右の壁
        terrain_data[-wall_thickness:, :, :] = 2
        
        # 中央にランダム障害物
        center_x = self.grid_size[0] // 2
        for _ in range(20):
            x = center_x + np.random.randint(-passage_width//2, passage_width//2)
            y = np.random.randint(0, self.grid_size[1])
            z = np.random.randint(0, self.grid_size[2])
            
            if 0 <= x < self.grid_size[0]:
                terrain_data[x, y, z] = 2
    
    def add_complex_3d_obstacles(self, terrain_data: np.ndarray):
        """複雑な3D障害物を追加"""
        # 複数の高さの障害物
        heights = [10, 20, 30]
        
        for height in heights:
            for _ in range(10):
                x = np.random.randint(0, self.grid_size[0])
                y = np.random.randint(0, self.grid_size[1])
                z = np.random.randint(0, self.grid_size[2] - height)
                
                # 円柱状の障害物
                radius = np.random.randint(2, 4)
                for dx in range(-radius, radius + 1):
                    for dy in range(-radius, radius + 1):
                        for dz in range(height):
                            nx, ny, nz = x + dx, y + dy, z + dz
                            if (0 <= nx < self.grid_size[0] and 
                                0 <= ny < self.grid_size[1] and 
                                0 <= nz < self.grid_size[2] and
                                dx*dx + dy*dy <= radius*radius):
                                terrain_data[nx, ny, nz] = 2
    
    def calculate_path_smoothness(self, path: List[Tuple[float, float, float]]) -> float:
        """経路の滑らかさを計算"""
        if len(path) < 3:
            return 1.0
        
        total_angle_change = 0.0
        for i in range(1, len(path) - 1):
            p1, p2, p3 = path[i-1], path[i], path[i+1]
            
            # ベクトル計算
            v1 = np.array([p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]])
            v2 = np.array([p3[0] - p2[0], p3[1] - p2[1], p3[2] - p2[2]])
            
            # 角度変化
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)
            angle_change = np.arccos(cos_angle)
            
            total_angle_change += angle_change
        
        # 滑らかさスコア（0-1、1が最も滑らか）
        max_angle_change = np.pi * (len(path) - 2)
        smoothness = 1.0 - (total_angle_change / max_angle_change)
        
        return max(0.0, min(1.0, smoothness))
    
    def calculate_safety_score(self, result: Dict[str, Any], terrain_data: np.ndarray) -> float:
        """安全性スコアを計算"""
        if not result['success'] or len(result['path']) < 2:
            return 0.0
        
        safety_score = 1.0
        
        # 経路長による安全性（短いほど安全）
        max_expected_length = 20.0  # 最大期待経路長
        length_penalty = min(1.0, result['path_length'] / max_expected_length)
        safety_score *= (1.0 - length_penalty * 0.3)
        
        # 計算時間による安全性（短いほど安全）
        max_expected_time = 60.0  # 最大期待計算時間
        time_penalty = min(1.0, result['computation_time'] / max_expected_time)
        safety_score *= (1.0 - time_penalty * 0.2)
        
        # 経路の滑らかさによる安全性
        safety_score *= result['path_smoothness']
        
        return max(0.0, min(1.0, safety_score))
    
    def save_results(self) -> None:
        """結果を保存"""
        # JSON形式で保存
        results_file = self.results_dir / "comparison_results.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.logger.info(f"Results saved to {results_file}")
    
    def analyze_results(self) -> None:
        """統計分析を実行"""
        self.logger.info("Performing statistical analysis...")
        
        # 簡略化された統計分析
        stats_summary = {}
        
        for algo_name, results in self.results.items():
            successful_results = [r for r in results if r['success']]
            
            if successful_results:
                stats_summary[algo_name] = {
                    'total_tests': len(results),
                    'successful_tests': len(successful_results),
                    'success_rate': len(successful_results) / len(results) * 100,
                    'avg_computation_time': sum(r['computation_time'] for r in successful_results) / len(successful_results),
                    'std_computation_time': np.std([r['computation_time'] for r in successful_results]),
                    'avg_path_length': sum(r['path_length'] for r in successful_results) / len(successful_results),
                    'std_path_length': np.std([r['path_length'] for r in successful_results]),
                    'avg_nodes_explored': sum(r['nodes_explored'] for r in successful_results) / len(successful_results),
                    'avg_memory_usage': sum(r['memory_usage'] for r in successful_results) / len(successful_results),
                    'avg_path_smoothness': sum(r['path_smoothness'] for r in successful_results) / len(successful_results),
                    'avg_safety_score': sum(r['safety_score'] for r in successful_results) / len(successful_results)
                }
                
                # TA-A*の特別な指標
                if algo_name == 'TA-A* (Proposed)':
                    stats_summary[algo_name].update({
                        'avg_risk_score': sum(r.get('risk_score', 0) for r in successful_results) / len(successful_results),
                        'avg_terrain_adaptations': sum(r.get('terrain_adaptations', 0) for r in successful_results) / len(successful_results),
                        'std_risk_score': np.std([r.get('risk_score', 0) for r in successful_results]),
                        'std_terrain_adaptations': np.std([r.get('terrain_adaptations', 0) for r in successful_results])
                    })
            else:
                stats_summary[algo_name] = {
                    'total_tests': len(results),
                    'successful_tests': 0,
                    'success_rate': 0.0,
                    'avg_computation_time': 0.0,
                    'std_computation_time': 0.0,
                    'avg_path_length': 0.0,
                    'std_path_length': 0.0,
                    'avg_nodes_explored': 0.0,
                    'avg_memory_usage': 0.0,
                    'avg_path_smoothness': 0.0,
                    'avg_safety_score': 0.0
                }
        
        self.statistical_results = stats_summary
        
        # 統計結果を保存
        stats_file = self.results_dir / "statistical_analysis.json"
        
        with open(stats_file, 'w') as f:
            json.dump(stats_summary, f, indent=2)
        
        self.logger.info(f"Statistical analysis saved to {stats_file}")
    
    def visualize_results(self) -> None:
        """結果を可視化"""
        self.logger.info("Generating visualization plots...")
        
        # データフレーム作成
        df_data = []
        for algo_name, results in self.results.items():
            for result in results:
                df_data.append({
                    'algorithm': algo_name,
                    'scenario_id': result['scenario_id'],
                    'terrain_type': result['terrain_type'],
                    'success': result['success'],
                    'computation_time': result['computation_time'],
                    'path_length': result['path_length'],
                    'nodes_explored': result['nodes_explored'],
                    'memory_usage': result['memory_usage'],
                    'path_smoothness': result['path_smoothness'],
                    'safety_score': result['safety_score']
                })
        
        df = pd.DataFrame(df_data)
        
        # スタイル設定
        try:
            plt.style.use('seaborn-v0_8')
        except:
            try:
                plt.style.use('seaborn')
            except:
                plt.style.use('default')
        sns.set_palette("husl")
        
        # 図1: 計算時間の箱ひげ図
        self.plot_computation_time_comparison(df)
        
        # 図2: 経路長の箱ひげ図
        self.plot_path_length_comparison(df)
        
        # 図3: 成功率の棒グラフ
        self.plot_success_rate_comparison(df)
        
        # 図4: 探索ノード数の比較
        self.plot_nodes_explored_comparison(df)
        
        # 図5: メモリ使用量の比較
        self.plot_memory_usage_comparison(df)
        
        # 図6: 地形タイプ別の性能
        self.plot_terrain_type_performance(df)
        
        self.logger.info("All visualization plots generated!")
    
    def plot_computation_time_comparison(self, df: pd.DataFrame):
        """計算時間の箱ひげ図"""
        plt.figure(figsize=(10, 6))
        
        successful_df = df[df['success'] == True]
        if len(successful_df) > 0:
            sns.boxplot(data=successful_df, x='algorithm', y='computation_time')
            plt.title('Computation Time Comparison', fontsize=16, fontweight='bold')
            plt.xlabel('Algorithm', fontsize=12)
            plt.ylabel('Computation Time (seconds)', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            
            # A*を強調
            ax = plt.gca()
            for i, label in enumerate(ax.get_xticklabels()):
                if label.get_text() == 'A*':
                    ax.get_children()[i].set_color('red')
                    ax.get_children()[i].set_linewidth(2)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "computation_time_comparison.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_path_length_comparison(self, df: pd.DataFrame):
        """経路長の箱ひげ図"""
        plt.figure(figsize=(10, 6))
        
        successful_df = df[df['success'] == True]
        if len(successful_df) > 0:
            sns.boxplot(data=successful_df, x='algorithm', y='path_length')
            plt.title('Path Length Comparison', fontsize=16, fontweight='bold')
            plt.xlabel('Algorithm', fontsize=12)
            plt.ylabel('Path Length (meters)', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "path_length_comparison.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_success_rate_comparison(self, df: pd.DataFrame):
        """成功率の棒グラフ"""
        plt.figure(figsize=(10, 6))
        
        success_rates = df.groupby('algorithm')['success'].mean() * 100
        
        bars = plt.bar(success_rates.index, success_rates.values, 
                      color=['skyblue', 'red', 'lightgreen', 'orange'])
        
        # A*を強調
        bars[1].set_color('red')
        bars[1].set_edgecolor('darkred')
        bars[1].set_linewidth(2)
        
        plt.title('Success Rate Comparison', fontsize=16, fontweight='bold')
        plt.xlabel('Algorithm', fontsize=12)
        plt.ylabel('Success Rate (%)', fontsize=12)
        plt.xticks(rotation=45)
        plt.ylim(0, 105)
        plt.grid(True, alpha=0.3, axis='y')
        
        # 値をバーの上に表示
        for bar, value in zip(bars, success_rates.values):
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                    f'{value:.1f}%', ha='center', va='bottom', fontweight='bold')
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "success_rate_comparison.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_nodes_explored_comparison(self, df: pd.DataFrame):
        """探索ノード数の比較"""
        plt.figure(figsize=(10, 6))
        
        successful_df = df[df['success'] == True]
        if len(successful_df) > 0:
            sns.boxplot(data=successful_df, x='algorithm', y='nodes_explored')
            plt.title('Nodes Explored Comparison', fontsize=16, fontweight='bold')
            plt.xlabel('Algorithm', fontsize=12)
            plt.ylabel('Nodes Explored', fontsize=12)
            plt.xticks(rotation=45)
            plt.yscale('log')  # 対数スケール
            plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "nodes_explored_comparison.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_memory_usage_comparison(self, df: pd.DataFrame):
        """メモリ使用量の比較"""
        plt.figure(figsize=(10, 6))
        
        successful_df = df[df['success'] == True]
        if len(successful_df) > 0:
            sns.boxplot(data=successful_df, x='algorithm', y='memory_usage')
            plt.title('Memory Usage Comparison', fontsize=16, fontweight='bold')
            plt.xlabel('Algorithm', fontsize=12)
            plt.ylabel('Memory Usage (MB)', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "memory_usage_comparison.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def plot_terrain_type_performance(self, df: pd.DataFrame):
        """地形タイプ別の性能"""
        plt.figure(figsize=(12, 8))
        
        # 計算時間を地形タイプ別に比較
        successful_df = df[df['success'] == True]
        if len(successful_df) > 0:
            sns.boxplot(data=successful_df, x='terrain_type', y='computation_time', hue='algorithm')
            plt.title('Terrain Type Performance Comparison', fontsize=16, fontweight='bold')
            plt.xlabel('Terrain Type', fontsize=12)
            plt.ylabel('Computation Time (seconds)', fontsize=12)
            plt.xticks(rotation=45)
            plt.legend(title='Algorithm', bbox_to_anchor=(1.05, 1), loc='upper left')
            plt.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(self.results_dir / "figures" / "terrain_type_performance_all.png", 
                   dpi=300, bbox_inches='tight')
        plt.close()
    
    def generate_latex_tables(self) -> None:
        """LaTeX形式のテーブルを生成"""
        latex_content = self._create_latex_tables()
        
        latex_file = self.results_dir / "tables" / "latex_tables.tex"
        with open(latex_file, 'w') as f:
            f.write(latex_content)
        
        self.logger.info(f"LaTeX tables saved to {latex_file}")
    
    def _create_latex_tables(self) -> str:
        """LaTeXテーブルを作成"""
        latex = r"""
\begin{table}[h]
\centering
\caption{Algorithm Performance Comparison}
\label{tab:algorithm_comparison}
\begin{tabular}{lccccc}
\hline
Algorithm & Time (s) & Path Length (m) & Success Rate & Nodes & Memory (MB) \\
\hline
"""
        
        # 各アルゴリズムの統計を計算
        for algo_name, results in self.results.items():
            successful_results = [r for r in results if r['success']]
            
            if successful_results:
                avg_time = np.mean([r['computation_time'] for r in successful_results])
                std_time = np.std([r['computation_time'] for r in successful_results])
                avg_length = np.mean([r['path_length'] for r in successful_results])
                std_length = np.std([r['path_length'] for r in successful_results])
                success_rate = len(successful_results) / len(results) * 100
                avg_nodes = np.mean([r['nodes_explored'] for r in successful_results])
                avg_memory = np.mean([r['memory_usage'] for r in successful_results])
                
                # A*を強調
                if algo_name == 'A*':
                    latex += f"\\textbf{{{algo_name}}} & \\textbf{{{avg_time:.1f} ± {std_time:.1f}}} & \\textbf{{{avg_length:.1f} ± {std_length:.1f}}} & \\textbf{{{success_rate:.0f}\\%}} & \\textbf{{{avg_nodes:.0f}}} & \\textbf{{{avg_memory:.1f}}} \\\\\n"
                else:
                    latex += f"{algo_name} & {avg_time:.1f} ± {std_time:.1f} & {avg_length:.1f} ± {std_length:.1f} & {success_rate:.0f}\\% & {avg_nodes:.0f} & {avg_memory:.1f} \\\\\n"
        
        latex += r"""
\hline
\end{tabular}
\end{table}
"""
        
        return latex

def main():
    """メイン関数"""
    # テスト用シナリオ生成
    scenarios = []
    for i in range(10):  # テスト用に10シナリオ
        scenario = {
            'scenario_id': i,
            'name': f'test_scenario_{i:03d}',
            'start_position': (0.0, 0.0, 0.0),
            'goal_position': (5.0, 5.0, 2.0),
            'terrain_params': {
                'terrain_type': 'obstacle_field',
                'obstacle_density': 0.1
            }
        }
        scenarios.append(scenario)
    
    # 比較実行
    comparison = AlgorithmComparison()
    comparison.run_comparison(scenarios)
    
    # LaTeXテーブル生成
    comparison.generate_latex_tables()
    
    print("Algorithm comparison completed!")
    print(f"Results saved to: {comparison.results_dir}")

if __name__ == "__main__":
    main()
