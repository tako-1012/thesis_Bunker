#!/usr/bin/env python3
"""
パラメータスイープの自動実行
グリッドサーチによる最適パラメータの探索
"""

import numpy as np
import pandas as pd
import itertools
import argparse
import sys
import os
import json
import time
from typing import Dict, List, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator


class ParameterSweep:
    """パラメータスイープを実行するクラス"""
    
    def __init__(self, output_dir: str = './tuning_results'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # パラメータ範囲の定義
        self.parameter_ranges = {
            'voxel_size': [0.05, 0.1, 0.2],
            'distance_weight': [0.5, 1.0, 2.0],
            'slope_weight': [1.0, 3.0, 5.0],
            'obstacle_weight': [3.0, 5.0, 8.0],
            'stability_weight': [2.0, 4.0, 6.0],
            'max_slope_angle': [20.0, 30.0, 40.0],
            'stability_threshold': [15.0, 20.0, 25.0]
        }
        
        # 評価指標
        self.metrics = [
            'path_length',
            'max_slope',
            'computation_time',
            'success_rate',
            'total_cost'
        ]
    
    def generate_parameter_combinations(self) -> List[Dict[str, float]]:
        """パラメータの組み合わせを生成"""
        # パラメータ名と値のリストを取得
        param_names = list(self.parameter_ranges.keys())
        param_values = list(self.parameter_ranges.values())
        
        # 全組み合わせを生成
        combinations = []
        for combination in itertools.product(*param_values):
            param_dict = dict(zip(param_names, combination))
            combinations.append(param_dict)
        
        return combinations
    
    def evaluate_parameters(self, params: Dict[str, float], 
                           terrain_data: Dict[str, Any]) -> Dict[str, float]:
        """パラメータの組み合わせを評価"""
        try:
            # コスト関数を作成
            weights = {
                'distance': params['distance_weight'],
                'slope': params['slope_weight'],
                'obstacle': params['obstacle_weight'],
                'stability': params['stability_weight']
            }
            
            safety_params = {
                'min_obstacle_distance': 0.5,
                'max_roll_angle': params['stability_threshold'],
                'max_pitch_angle': params['stability_threshold']
            }
            
            cost_function = CostFunction(weights, safety_params)
            
            # A*プランナーを作成
            astar_planner = AStar3D(voxel_size=params['voxel_size'])
            
            # 経路計画を実行
            start_pos = (0, 0, 0)
            goal_pos = (9, 9, 5)
            
            start_time = time.time()
            path = astar_planner.plan_path(
                start_pos, goal_pos, 
                terrain_data['voxel_grid'], 
                cost_function
            )
            computation_time = time.time() - start_time
            
            # 評価指標を計算
            if path is not None:
                path_length = self._calculate_path_length(path)
                max_slope = self._calculate_max_slope(path, terrain_data)
                total_cost = self._calculate_total_cost(path, cost_function, terrain_data)
                success_rate = 1.0
            else:
                path_length = float('inf')
                max_slope = float('inf')
                total_cost = float('inf')
                success_rate = 0.0
            
            return {
                'path_length': path_length,
                'max_slope': max_slope,
                'computation_time': computation_time,
                'success_rate': success_rate,
                'total_cost': total_cost
            }
            
        except Exception as e:
            print(f"Error evaluating parameters {params}: {e}")
            return {
                'path_length': float('inf'),
                'max_slope': float('inf'),
                'computation_time': float('inf'),
                'success_rate': 0.0,
                'total_cost': float('inf')
            }
    
    def _calculate_path_length(self, path: List[Tuple[int, int, int]]) -> float:
        """経路長を計算"""
        if len(path) < 2:
            return 0.0
        
        total_length = 0.0
        for i in range(1, len(path)):
            dx = path[i][0] - path[i-1][0]
            dy = path[i][1] - path[i-1][1]
            dz = path[i][2] - path[i-1][2]
            total_length += np.sqrt(dx**2 + dy**2 + dz**2)
        
        return total_length
    
    def _calculate_max_slope(self, path: List[Tuple[int, int, int]], 
                            terrain_data: Dict[str, Any]) -> float:
        """最大傾斜角を計算"""
        if len(path) < 2:
            return 0.0
        
        max_slope = 0.0
        for i in range(1, len(path)):
            dx = path[i][0] - path[i-1][0]
            dy = path[i][1] - path[i-1][1]
            dz = path[i][2] - path[i-1][2]
            
            horizontal_distance = np.sqrt(dx**2 + dy**2)
            if horizontal_distance > 0:
                slope_angle = np.degrees(np.arctan(abs(dz) / horizontal_distance))
                max_slope = max(max_slope, slope_angle)
        
        return max_slope
    
    def _calculate_total_cost(self, path: List[Tuple[int, int, int]], 
                            cost_function: CostFunction, 
                            terrain_data: Dict[str, Any]) -> float:
        """総コストを計算"""
        if len(path) < 2:
            return 0.0
        
        total_cost = 0.0
        for i in range(1, len(path)):
            from_pos = (float(path[i-1][0]), float(path[i-1][1]), float(path[i-1][2]))
            to_pos = (float(path[i][0]), float(path[i][1]), float(path[i][2]))
            
            cost = cost_function.calculate_total_cost(from_pos, to_pos, terrain_data)
            total_cost += cost
        
        return total_cost
    
    def run_sweep(self, terrain_data: Dict[str, Any], 
                  max_workers: int = None) -> pd.DataFrame:
        """パラメータスイープを実行"""
        if max_workers is None:
            max_workers = mp.cpu_count()
        
        # パラメータの組み合わせを生成
        combinations = self.generate_parameter_combinations()
        print(f"Total parameter combinations: {len(combinations)}")
        
        # 結果を格納するリスト
        results = []
        
        # 並列処理でパラメータを評価
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # タスクを送信
            future_to_params = {
                executor.submit(self.evaluate_parameters, params, terrain_data): params
                for params in combinations
            }
            
            # 結果を収集
            for i, future in enumerate(as_completed(future_to_params)):
                params = future_to_params[future]
                try:
                    metrics = future.result()
                    
                    # 結果を統合
                    result = {**params, **metrics}
                    results.append(result)
                    
                    print(f"Completed {i+1}/{len(combinations)}: {params}")
                    
                except Exception as e:
                    print(f"Error processing {params}: {e}")
        
        # DataFrameに変換
        df = pd.DataFrame(results)
        
        # 結果を保存
        self._save_results(df)
        
        return df
    
    def _save_results(self, df: pd.DataFrame) -> None:
        """結果を保存"""
        # CSV形式で保存
        csv_filename = os.path.join(self.output_dir, 'parameter_sweep_results.csv')
        df.to_csv(csv_filename, index=False)
        
        # JSON形式で保存
        json_filename = os.path.join(self.output_dir, 'parameter_sweep_results.json')
        df.to_json(json_filename, orient='records', indent=2)
        
        # 統計情報を保存
        stats_filename = os.path.join(self.output_dir, 'parameter_sweep_stats.json')
        stats = {
            'total_combinations': len(df),
            'successful_combinations': len(df[df['success_rate'] > 0]),
            'best_parameters': self._find_best_parameters(df),
            'parameter_ranges': self.parameter_ranges
        }
        
        with open(stats_filename, 'w') as f:
            json.dump(stats, f, indent=2)
        
        print(f"Results saved to {self.output_dir}")
    
    def _find_best_parameters(self, df: pd.DataFrame) -> Dict[str, Any]:
        """最適パラメータを見つける"""
        # 成功した組み合わせのみを対象
        successful_df = df[df['success_rate'] > 0]
        
        if len(successful_df) == 0:
            return {}
        
        # 複数の評価指標を考慮したスコアを計算
        # 正規化して重み付き平均を計算
        normalized_df = successful_df.copy()
        
        for metric in self.metrics:
            if metric in normalized_df.columns:
                # 0-1の範囲に正規化
                min_val = normalized_df[metric].min()
                max_val = normalized_df[metric].max()
                if max_val > min_val:
                    normalized_df[metric] = (normalized_df[metric] - min_val) / (max_val - min_val)
                else:
                    normalized_df[metric] = 0.0
        
        # スコアを計算（低い値が良い指標は1から引く）
        score_weights = {
            'path_length': 0.2,
            'max_slope': 0.2,
            'computation_time': 0.2,
            'success_rate': 0.2,  # 高い値が良い
            'total_cost': 0.2
        }
        
        scores = []
        for _, row in normalized_df.iterrows():
            score = 0.0
            for metric, weight in score_weights.items():
                if metric in row:
                    if metric == 'success_rate':
                        score += weight * row[metric]
                    else:
                        score += weight * (1.0 - row[metric])
            scores.append(score)
        
        normalized_df['score'] = scores
        
        # 最高スコアのパラメータを取得
        best_idx = normalized_df['score'].idxmax()
        best_params = successful_df.loc[best_idx].to_dict()
        
        return best_params
    
    def analyze_results(self, df: pd.DataFrame) -> None:
        """結果を分析"""
        print("\n=== Parameter Sweep Analysis ===")
        
        # 基本統計
        print(f"Total combinations: {len(df)}")
        print(f"Successful combinations: {len(df[df['success_rate'] > 0])}")
        print(f"Success rate: {len(df[df['success_rate'] > 0]) / len(df) * 100:.1f}%")
        
        # 最適パラメータ
        best_params = self._find_best_parameters(df)
        if best_params:
            print("\nBest parameters:")
            for param, value in best_params.items():
                if param in self.parameter_ranges:
                    print(f"  {param}: {value}")
        
        # パラメータの影響分析
        print("\nParameter impact analysis:")
        for param in self.parameter_ranges.keys():
            if param in df.columns:
                correlation = df[param].corr(df['total_cost'])
                print(f"  {param}: correlation = {correlation:.3f}")


def create_sample_terrain_data() -> Dict[str, Any]:
    """サンプル地形データを作成"""
    # 10x10x10のボクセルグリッドを作成
    voxel_grid = np.zeros((10, 10, 10), dtype=np.uint8)
    
    # 地面を設定
    voxel_grid[:, :, 0] = 1
    
    # 障害物を追加
    voxel_grid[5, 5, :] = 2
    voxel_grid[3:7, 3:7, 5] = 2
    
    # 地形データ
    terrain_data = {
        'voxel_grid': voxel_grid,
        'slopes': np.random.uniform(0, 30, 100),
        'metadata': {'resolution': 0.1}
    }
    
    return terrain_data


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(description='Parameter sweep for 3D path planning')
    parser.add_argument('--output-dir', type=str, default='./tuning_results',
                       help='Output directory for results')
    parser.add_argument('--max-workers', type=int, default=None,
                       help='Maximum number of worker processes')
    parser.add_argument('--analyze', action='store_true',
                       help='Analyze existing results')
    
    args = parser.parse_args()
    
    # パラメータスイープを作成
    sweep = ParameterSweep(output_dir=args.output_dir)
    
    if args.analyze:
        # 既存の結果を分析
        csv_filename = os.path.join(args.output_dir, 'parameter_sweep_results.csv')
        if os.path.exists(csv_filename):
            df = pd.read_csv(csv_filename)
            sweep.analyze_results(df)
        else:
            print(f"Results file not found: {csv_filename}")
    else:
        # パラメータスイープを実行
        print("Creating sample terrain data...")
        terrain_data = create_sample_terrain_data()
        
        print("Starting parameter sweep...")
        df = sweep.run_sweep(terrain_data, max_workers=args.max_workers)
        
        print("Analyzing results...")
        sweep.analyze_results(df)


if __name__ == '__main__':
    main()
