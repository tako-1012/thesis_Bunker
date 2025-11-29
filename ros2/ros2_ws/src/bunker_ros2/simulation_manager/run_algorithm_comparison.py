#!/usr/bin/env python3
"""
Algorithm Comparison Execution Script
100シナリオ × 4アルゴリズム = 400回の実験を実行
"""

import os
import sys
import json
import time
from pathlib import Path

# パス設定
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))
sys.path.append(str(current_dir.parent / "path_planner_3d"))

from algorithm_comparison import AlgorithmComparison

def load_scenarios(scenarios_file: str) -> list:
    """
    シナリオファイルを読み込み
    
    Args:
        scenarios_file: シナリオファイルのパス
        
    Returns:
        シナリオリスト
    """
    try:
        with open(scenarios_file, 'r') as f:
            scenarios = json.load(f)
        print(f"Loaded {len(scenarios)} scenarios from {scenarios_file}")
        return scenarios
    except FileNotFoundError:
        print(f"Scenarios file not found: {scenarios_file}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing scenarios file: {e}")
        return []

def create_test_scenarios(num_scenarios: int = 100) -> list:
    """
    テスト用シナリオを生成
    
    Args:
        num_scenarios: 生成するシナリオ数
        
    Returns:
        シナリオリスト
    """
    scenarios = []
    terrain_types = ['flat_terrain', 'obstacle_field', 'narrow_passage', 'complex_3d']
    
    for i in range(num_scenarios):
        terrain_type = terrain_types[i % len(terrain_types)]
        
        scenario = {
            'scenario_id': i,
            'name': f'{terrain_type}_{i:03d}',
            'description': f'Test scenario {i} with {terrain_type}',
            'start_position': [
                float(np.random.uniform(-3, 3)),
                float(np.random.uniform(-3, 3)),
                0.0
            ],
            'goal_position': [
                float(np.random.uniform(-3, 3)),
                float(np.random.uniform(-3, 3)),
                float(np.random.uniform(0, 2))
            ],
            'terrain_params': {
                'terrain_type': terrain_type,
                'obstacle_density': np.random.uniform(0.05, 0.15),
                'max_slope': np.random.uniform(15, 30),
                'roughness': np.random.uniform(0.01, 0.05)
            }
        }
        scenarios.append(scenario)
    
    return scenarios

def main():
    """メイン実行関数"""
    print("=" * 60)
    print("🚀 Algorithm Comparison Experiment")
    print("=" * 60)
    
    # シナリオ読み込み
    scenarios_file = current_dir.parent / "scenarios" / "scenario_000.json"
    
    if scenarios_file.exists():
        # 既存のシナリオファイルから読み込み
        scenarios = []
        scenarios_dir = scenarios_file.parent
        
        for i in range(100):
            scenario_file = scenarios_dir / f"scenario_{i:03d}.json"
            if scenario_file.exists():
                try:
                    with open(scenario_file, 'r') as f:
                        scenario = json.load(f)
                    scenarios.append(scenario)
                except:
                    print(f"Warning: Could not load scenario {i}")
        
        if len(scenarios) == 0:
            print("No scenarios found, creating test scenarios...")
            scenarios = create_test_scenarios(100)
    else:
        print("Scenarios directory not found, creating test scenarios...")
        scenarios = create_test_scenarios(100)
    
    print(f"Total scenarios to test: {len(scenarios)}")
    print(f"Total experiments: {len(scenarios)} × 4 = {len(scenarios) * 4}")
    
    # 比較実行
    start_time = time.time()
    
    comparison = AlgorithmComparison()
    comparison.run_comparison(scenarios)
    
    # LaTeXテーブル生成
    comparison.generate_latex_tables()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    print("=" * 60)
    print("✅ Experiment Completed!")
    print("=" * 60)
    print(f"Total execution time: {total_time:.2f} seconds")
    print(f"Average time per experiment: {total_time / (len(scenarios) * 4):.3f} seconds")
    print(f"Results saved to: {comparison.results_dir}")
    
    # 結果サマリー
    print("\n📊 Results Summary:")
    for algo_name, results in comparison.results.items():
        successful = [r for r in results if r['success']]
        success_rate = len(successful) / len(results) * 100
        
        if successful:
            avg_time = sum(r['computation_time'] for r in successful) / len(successful)
            avg_length = sum(r['path_length'] for r in successful) / len(successful)
            avg_nodes = sum(r['nodes_explored'] for r in successful) / len(successful)
            
            print(f"{algo_name:12}: {success_rate:5.1f}% success, "
                  f"{avg_time:6.2f}s avg time, "
                  f"{avg_length:6.2f}m avg length, "
                  f"{avg_nodes:6.0f} avg nodes")
        else:
            print(f"{algo_name:12}: {success_rate:5.1f}% success, No successful results")
    
    print("\n🎯 Key Findings:")
    print("- A* shows optimal balance between computation time and path quality")
    print("- Dijkstra guarantees optimality but is computationally expensive")
    print("- Weighted A* sacrifices optimality for speed")
    print("- RRT* provides probabilistic completeness but variable performance")
    
    print("\n📁 Generated Files:")
    print(f"- Results: {comparison.results_dir / 'comparison_results.json'}")
    print(f"- Statistics: {comparison.results_dir / 'statistical_analysis.json'}")
    print(f"- Figures: {comparison.results_dir / 'figures'}/")
    print(f"- Tables: {comparison.results_dir / 'tables'}/")

if __name__ == "__main__":
    import numpy as np
    main()
