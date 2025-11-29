"""
リアルタイムベンチマーク

厳しい時間制約下での性能評価
"""
import time
import numpy as np
from typing import Dict, List
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))

from path_planner_3d.terrain_aware_astar_fast import TerrainAwareAStarFast
from path_planner_3d.astar_planner import AStarPlanner3D
from path_planner_3d.config import PlannerConfig

class RealtimeBenchmark:
    """リアルタイムベンチマーククラス"""
    
    def __init__(self):
        """初期化"""
        self.config = PlannerConfig.medium_scale()
        self.time_budgets = [0.1, 0.5, 1.0, 2.0, 5.0]  # 秒
    
    def run_benchmark(self) -> Dict:
        """
        リアルタイムベンチマークを実行
        
        異なる時間制約での性能を評価
        
        Returns:
            Dict: ベンチマーク結果
        """
        print("="*70)
        print("リアルタイムベンチマーク")
        print("="*70)
        
        algorithms = {
            'A*': AStarPlanner3D(self.config),
            'TA-A* Fast': TerrainAwareAStarFast(self.config)
        }
        
        results = {}
        
        for algo_name, planner in algorithms.items():
            print(f"\n{algo_name}:")
            results[algo_name] = {}
            
            for time_budget in self.time_budgets:
                print(f"  時間制約: {time_budget}s")
                
                budget_results = self._evaluate_time_budget(
                    planner,
                    time_budget
                )
                
                results[algo_name][f'{time_budget}s'] = budget_results
                
                print(f"    成功率: {budget_results['success_rate']:.1f}%")
                print(f"    平均時間: {budget_results['avg_time']:.3f}s")
        
        # 結果を保存
        output_file = Path('../results/realtime_benchmark.json')
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✅ リアルタイムベンチマーク完了: {output_file}")
        
        return results
    
    def _evaluate_time_budget(self, planner, time_budget: float) -> Dict:
        """特定の時間制約での評価"""
        scenarios = self._generate_scenarios(num=50)
        
        successes = 0
        times = []
        
        for scenario in scenarios:
            result = planner.plan_path(
                scenario['start'],
                scenario['goal'],
                timeout=time_budget
            )
            
            if result.success:
                successes += 1
                times.append(result.computation_time)
        
        return {
            'success_count': successes,
            'total': len(scenarios),
            'success_rate': successes / len(scenarios) * 100,
            'avg_time': np.mean(times) if times else 0,
            'max_time': np.max(times) if times else 0,
            'within_budget': sum(1 for t in times if t < time_budget)
        }
    
    def _generate_scenarios(self, num: int) -> List[Dict]:
        """テストシナリオ生成"""
        scenarios = []
        np.random.seed(42)
        
        for i in range(num):
            start = [
                np.random.uniform(-20, 20),
                np.random.uniform(-20, 20),
                0.2
            ]
            goal = [
                np.random.uniform(-20, 20),
                np.random.uniform(-20, 20),
                0.2
            ]
            scenarios.append({'start': start, 'goal': goal})
        
        return scenarios
    
    def analyze_anytime_behavior(self) -> Dict:
        """
        Anytime特性の分析
        
        時間経過とともに解が改善されるかを評価
        
        Returns:
            Dict: 分析結果
        """
        print("\n" + "="*70)
        print("Anytime特性分析")
        print("="*70)
        
        # 長時間実行して解の質の変化を観察
        planner = TerrainAwareAStarFast(self.config)
        
        scenario = {
            'start': [-20, -20, 0.2],
            'goal': [20, 20, 0.2]
        }
        
        time_checkpoints = [0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
        solutions = []
        
        for checkpoint in time_checkpoints:
            result = planner.plan_path(
                scenario['start'],
                scenario['goal'],
                timeout=checkpoint
            )
            
            solutions.append({
                'time_budget': checkpoint,
                'success': result.success,
                'actual_time': result.computation_time,
                'path_length': result.path_length if result.success else None,
                'quality': self._evaluate_solution_quality(result) if result.success else 0
            })
            
            print(f"時間: {checkpoint:4.1f}s -> "
                  f"{'成功' if result.success else '失敗'}, "
                  f"品質: {solutions[-1]['quality']:.3f}")
        
        return {
            'solutions': solutions,
            'conclusion': self._analyze_improvement(solutions)
        }
    
    def _evaluate_solution_quality(self, result) -> float:
        """
        解の質を評価
        
        経路長、滑らかさなどを総合評価
        """
        if not result.success:
            return 0.0
        
        # 簡易版：経路長の逆数
        quality = 1.0 / (result.path_length + 1.0)
        
        return quality
    
    def _analyze_improvement(self, solutions: List[Dict]) -> str:
        """解の改善を分析"""
        qualities = [s['quality'] for s in solutions if s['success']]
        
        if not qualities or len(qualities) < 2:
            return "Anytime特性なし（早期に最良解発見）"
        
        # 品質が向上しているか
        improving = all(
            qualities[i] <= qualities[i+1] 
            for i in range(len(qualities)-1)
        )
        
        if improving:
            return "Anytime特性あり（時間とともに改善）"
        else:
            return "Anytime特性なし（初期解が最良）"
    
    def benchmark_worst_case(self) -> Dict:
        """
        ワーストケース性能
        
        最も困難なシナリオでの性能
        
        Returns:
            Dict: ワーストケース結果
        """
        print("\n" + "="*70)
        print("ワーストケースベンチマーク")
        print("="*70)
        
        # 最も困難なシナリオ
        worst_scenarios = [
            {
                'name': 'Long distance',
                'start': [-25, -25, 0.2],
                'goal': [25, 25, 0.2]
            },
            {
                'name': 'Narrow passage',
                'start': [0, -10, 0.2],
                'goal': [0, 10, 0.2]
            },
            {
                'name': 'Complex terrain',
                'start': [-15, -15, 0.2],
                'goal': [15, 15, 0.2]
            }
        ]
        
        algorithms = {
            'A*': AStarPlanner3D(self.config),
            'TA-A* Fast': TerrainAwareAStarFast(self.config)
        }
        
        results = {}
        
        for scenario in worst_scenarios:
            print(f"\n{scenario['name']}:")
            results[scenario['name']] = {}
            
            for algo_name, planner in algorithms.items():
                result = planner.plan_path(
                    scenario['start'],
                    scenario['goal'],
                    timeout=30
                )
                
                results[scenario['name']][algo_name] = {
                    'success': result.success,
                    'time': result.computation_time,
                    'length': result.path_length if result.success else None
                }
                
                print(f"  {algo_name:15s}: "
                      f"{'成功' if result.success else '失敗'} "
                      f"({result.computation_time:.2f}s)")
        
        return results

if __name__ == '__main__':
    benchmark = RealtimeBenchmark()
    
    # リアルタイムベンチマーク
    realtime_results = benchmark.run_benchmark()
    
    # Anytime特性分析
    anytime_results = benchmark.analyze_anytime_behavior()
    
    # ワーストケース
    worst_case_results = benchmark.benchmark_worst_case()
    
    print("\n" + "="*70)
    print("🎉 全ベンチマーク完了！")
    print("="*70)


