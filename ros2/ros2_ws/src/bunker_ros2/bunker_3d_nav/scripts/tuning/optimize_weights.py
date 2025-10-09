#!/usr/bin/env python3
"""
コスト関数の重み最適化
ベイズ最適化による効率的なパラメータ探索
"""

import numpy as np
import pandas as pd
import argparse
import sys
import os
import json
import time
from typing import Dict, List, Tuple, Any, Optional
from scipy.optimize import minimize
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
import warnings
warnings.filterwarnings('ignore')

# Add package path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from bunker_3d_nav.path_planner_3d.cost_function import CostFunction
from bunker_3d_nav.path_planner_3d.astar_3d import AStar3D
from bunker_3d_nav.terrain_analyzer.voxel_grid_processor import VoxelGridProcessor
from bunker_3d_nav.terrain_analyzer.slope_calculator import SlopeCalculator


class BayesianOptimizer:
    """ベイズ最適化によるパラメータ最適化クラス"""
    
    def __init__(self, output_dir: str = './tuning_results'):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # パラメータの範囲
        self.parameter_bounds = {
            'distance_weight': (0.1, 5.0),
            'slope_weight': (0.1, 10.0),
            'obstacle_weight': (0.1, 15.0),
            'stability_weight': (0.1, 10.0),
            'voxel_size': (0.05, 0.3),
            'max_slope_angle': (15.0, 45.0),
            'stability_threshold': (10.0, 30.0)
        }
        
        # パラメータ名
        self.parameter_names = list(self.parameter_bounds.keys())
        
        # ガウス過程回帰器
        self.gp = GaussianProcessRegressor(
            kernel=Matern(length_scale=1.0, nu=2.5),
            alpha=1e-6,
            normalize_y=True,
            n_restarts_optimizer=10
        )
        
        # 評価履歴
        self.evaluation_history = []
        self.best_parameters = None
        self.best_score = float('inf')
    
    def objective_function(self, params: np.ndarray, 
                          terrain_data: Dict[str, Any]) -> float:
        """目的関数（最小化したい関数）"""
        try:
            # パラメータを辞書に変換
            param_dict = dict(zip(self.parameter_names, params))
            
            # コスト関数を作成
            weights = {
                'distance': param_dict['distance_weight'],
                'slope': param_dict['slope_weight'],
                'obstacle': param_dict['obstacle_weight'],
                'stability': param_dict['stability_weight']
            }
            
            safety_params = {
                'min_obstacle_distance': 0.5,
                'max_roll_angle': param_dict['stability_threshold'],
                'max_pitch_angle': param_dict['stability_threshold']
            }
            
            cost_function = CostFunction(weights, safety_params)
            
            # A*プランナーを作成
            astar_planner = AStar3D(voxel_size=param_dict['voxel_size'])
            
            # 複数のシナリオで評価
            scenarios = [
                ((0, 0, 0), (9, 9, 5)),  # 基本シナリオ
                ((0, 0, 0), (5, 5, 8)),  # 高高度シナリオ
                ((2, 2, 0), (8, 8, 3)),  # 中間シナリオ
            ]
            
            total_score = 0.0
            successful_scenarios = 0
            
            for start_pos, goal_pos in scenarios:
                try:
                    # 経路計画を実行
                    start_time = time.time()
                    path = astar_planner.plan_path(
                        start_pos, goal_pos, 
                        terrain_data['voxel_grid'], 
                        cost_function
                    )
                    computation_time = time.time() - start_time
                    
                    if path is not None:
                        # スコアを計算
                        path_length = self._calculate_path_length(path)
                        max_slope = self._calculate_max_slope(path, terrain_data)
                        total_cost = self._calculate_total_cost(path, cost_function, terrain_data)
                        
                        # 複合スコア（低い値が良い）
                        scenario_score = (
                            0.3 * path_length +
                            0.3 * max_slope +
                            0.2 * computation_time +
                            0.2 * total_cost
                        )
                        
                        total_score += scenario_score
                        successful_scenarios += 1
                    else:
                        # 経路が見つからない場合はペナルティ
                        total_score += 1000.0
                        
                except Exception as e:
                    # エラーの場合はペナルティ
                    total_score += 1000.0
            
            # 平均スコアを計算
            if successful_scenarios > 0:
                average_score = total_score / successful_scenarios
            else:
                average_score = 1000.0
            
            # 履歴に記録
            self.evaluation_history.append({
                'parameters': param_dict.copy(),
                'score': average_score,
                'successful_scenarios': successful_scenarios,
                'total_scenarios': len(scenarios)
            })
            
            # 最良のパラメータを更新
            if average_score < self.best_score:
                self.best_score = average_score
                self.best_parameters = param_dict.copy()
            
            return average_score
            
        except Exception as e:
            print(f"Error in objective function: {e}")
            return 1000.0
    
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
    
    def acquisition_function(self, x: np.ndarray) -> float:
        """獲得関数（Expected Improvement）"""
        if len(self.evaluation_history) < 2:
            return 0.0
        
        # 過去の評価結果からガウス過程を学習
        X = np.array([eval_data['parameters'][name] for eval_data in self.evaluation_history 
                     for name in self.parameter_names]).reshape(-1, len(self.parameter_names))
        y = np.array([eval_data['score'] for eval_data in self.evaluation_history])
        
        try:
            self.gp.fit(X, y)
            
            # 予測平均と分散を計算
            mean, std = self.gp.predict(x.reshape(1, -1), return_std=True)
            
            # Expected Improvementを計算
            improvement = self.best_score - mean[0]
            z = improvement / std[0] if std[0] > 0 else 0
            
            # 正規分布の累積分布関数と確率密度関数
            from scipy.stats import norm
            ei = improvement * norm.cdf(z) + std[0] * norm.pdf(z)
            
            return ei[0]
            
        except Exception as e:
            print(f"Error in acquisition function: {e}")
            return 0.0
    
    def optimize(self, terrain_data: Dict[str, Any], 
                n_iterations: int = 50, n_initial: int = 10) -> Dict[str, float]:
        """ベイズ最適化を実行"""
        print(f"Starting Bayesian optimization with {n_iterations} iterations...")
        
        # 初期サンプリング
        print("Performing initial sampling...")
        for i in range(n_initial):
            # ランダムにパラメータを生成
            params = []
            for param_name in self.parameter_names:
                bounds = self.parameter_bounds[param_name]
                param_value = np.random.uniform(bounds[0], bounds[1])
                params.append(param_value)
            
            params = np.array(params)
            score = self.objective_function(params, terrain_data)
            
            print(f"Initial sample {i+1}/{n_initial}: score = {score:.3f}")
        
        # ベイズ最適化のメインループ
        for iteration in range(n_iterations):
            print(f"\nIteration {iteration + 1}/{n_iterations}")
            
            # 獲得関数を最大化するパラメータを見つける
            best_x = None
            best_acquisition = -np.inf
            
            # 複数の初期点から最適化を開始
            for _ in range(10):
                # ランダムな初期点
                x0 = []
                for param_name in self.parameter_names:
                    bounds = self.parameter_bounds[param_name]
                    x0.append(np.random.uniform(bounds[0], bounds[1]))
                x0 = np.array(x0)
                
                # 獲得関数を最大化
                bounds_list = [self.parameter_bounds[name] for name in self.parameter_names]
                
                try:
                    result = minimize(
                        lambda x: -self.acquisition_function(x),
                        x0,
                        bounds=bounds_list,
                        method='L-BFGS-B'
                    )
                    
                    if result.success and -result.fun > best_acquisition:
                        best_acquisition = -result.fun
                        best_x = result.x
                        
                except Exception as e:
                    print(f"Optimization error: {e}")
                    continue
            
            if best_x is not None:
                # 最適なパラメータで評価
                score = self.objective_function(best_x, terrain_data)
                
                print(f"Best acquisition: {best_acquisition:.3f}")
                print(f"Score: {score:.3f}")
                print(f"Best parameters so far: {self.best_parameters}")
                print(f"Best score so far: {self.best_score:.3f}")
                
                # 結果を保存
                self._save_progress(iteration + 1)
        
        print(f"\nOptimization completed!")
        print(f"Best parameters: {self.best_parameters}")
        print(f"Best score: {self.best_score:.3f}")
        
        return self.best_parameters
    
    def _save_progress(self, iteration: int) -> None:
        """進捗を保存"""
        progress_data = {
            'iteration': iteration,
            'best_parameters': self.best_parameters,
            'best_score': self.best_score,
            'evaluation_history': self.evaluation_history
        }
        
        progress_filename = os.path.join(self.output_dir, 'optimization_progress.json')
        with open(progress_filename, 'w') as f:
            json.dump(progress_data, f, indent=2)
        
        # CSV形式でも保存
        if self.evaluation_history:
            df = pd.DataFrame(self.evaluation_history)
            csv_filename = os.path.join(self.output_dir, 'optimization_history.csv')
            df.to_csv(csv_filename, index=False)
    
    def load_progress(self, filename: str = None) -> bool:
        """進捗を読み込み"""
        if filename is None:
            filename = os.path.join(self.output_dir, 'optimization_progress.json')
        
        if not os.path.exists(filename):
            return False
        
        try:
            with open(filename, 'r') as f:
                progress_data = json.load(f)
            
            self.best_parameters = progress_data.get('best_parameters')
            self.best_score = progress_data.get('best_score', float('inf'))
            self.evaluation_history = progress_data.get('evaluation_history', [])
            
            print(f"Loaded progress: {len(self.evaluation_history)} evaluations")
            print(f"Best score: {self.best_score:.3f}")
            
            return True
            
        except Exception as e:
            print(f"Error loading progress: {e}")
            return False


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
    parser = argparse.ArgumentParser(description='Bayesian optimization for cost function weights')
    parser.add_argument('--output-dir', type=str, default='./tuning_results',
                       help='Output directory for results')
    parser.add_argument('--n-iterations', type=int, default=50,
                       help='Number of optimization iterations')
    parser.add_argument('--n-initial', type=int, default=10,
                       help='Number of initial random samples')
    parser.add_argument('--resume', action='store_true',
                       help='Resume from previous optimization')
    
    args = parser.parse_args()
    
    # 最適化器を作成
    optimizer = BayesianOptimizer(output_dir=args.output_dir)
    
    # 進捗を読み込み（resumeオプションが指定されている場合）
    if args.resume:
        if optimizer.load_progress():
            print("Resuming from previous optimization...")
        else:
            print("No previous optimization found, starting fresh...")
    
    # サンプル地形データを作成
    print("Creating sample terrain data...")
    terrain_data = create_sample_terrain_data()
    
    # 最適化を実行
    best_params = optimizer.optimize(
        terrain_data, 
        n_iterations=args.n_iterations,
        n_initial=args.n_initial
    )
    
    # 最終結果を保存
    final_result = {
        'best_parameters': best_params,
        'best_score': optimizer.best_score,
        'total_evaluations': len(optimizer.evaluation_history),
        'parameter_bounds': optimizer.parameter_bounds
    }
    
    result_filename = os.path.join(args.output_dir, 'optimization_result.json')
    with open(result_filename, 'w') as f:
        json.dump(final_result, f, indent=2)
    
    print(f"Final result saved to {result_filename}")


if __name__ == '__main__':
    main()
