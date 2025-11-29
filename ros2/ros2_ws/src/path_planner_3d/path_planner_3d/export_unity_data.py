import json
import numpy as np
import time
from benchmark_planners import PlannerBenchmark, TestScenario

# プランナーは benchmark_planners.py の中で使われている方法を踏襲
# 直接インポートではなく、benchmark内のメソッドを利用

class UnityDataExporter:
    def __init__(self, output_dir: str = "./unity_data"):
        self.output_dir = output_dir
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # ベンチマーククラスを初期化
        self.benchmark = PlannerBenchmark()
    
    def export_scenario_with_paths(self, scenario: TestScenario, scenario_id: str):
        """
        1つのシナリオで全プランナーを実行し、Unity用データとして出力
        """
        print(f"Exporting scenario: {scenario_id}")
        
        # 地形データ
        terrain_data = {
            'gridSize': list(scenario.terrain_cost_map.shape),
            'resolution': 0.1,
            'bounds': {
                'xMin': float(scenario.bounds[0][0]),
                'xMax': float(scenario.bounds[0][1]),
                'yMin': float(scenario.bounds[1][0]),
                'yMax': float(scenario.bounds[1][1]),
                'zMin': float(scenario.bounds[2][0]),
                'zMax': float(scenario.bounds[2][1])
            },
            'costMap': scenario.terrain_cost_map.tolist(),
            'start': scenario.start.tolist(),
            'goal': scenario.goal.tolist()
        }
        
        # 各プランナーで経路計画（benchmark の既存メソッドを使用）
        planners_info = {
            'ADAPTIVE': ('adaptive', '#2ecc71'),
            'RRT_STAR': ('rrt_star', '#e74c3c'),
            'SAFETY_FIRST': ('safety_first', '#3498db'),
            'HPA_STAR': ('hpa_star', '#f39c12'),
            'DSTAR_LITE': ('dstar_lite', '#9b59b6')
        }
        
        paths_data = {}
        
        for planner_name, (method_suffix, color) in planners_info.items():
            print(f"  Running {planner_name}...", end=" ")
            
            # benchmark のメソッドを直接呼び出し
            method_name = f"_run_{method_suffix}_planner"
            if hasattr(self.benchmark, method_name):
                method = getattr(self.benchmark, method_name)
                result = method(scenario)
                
                # 経路を再計算して取得（結果には経路座標が含まれていない）
                path = self._get_path_from_planner(scenario, planner_name)
                
                if path is not None and len(path) > 1:
                    paths_data[planner_name] = {
                        'path': [p.tolist() for p in path],
                        'computationTime': result.computation_time,
                        'pathLength': result.path_length,
                        'numWaypoints': len(path),
                        'success': result.success,
                        'color': color
                    }
                    print(f"✓ ({result.computation_time:.2f}s, {len(path)} points)")
                else:
                    paths_data[planner_name] = {
                        'path': [],
                        'computationTime': result.computation_time if result else 0.0,
                        'pathLength': 0.0,
                        'numWaypoints': 0,
                        'success': False,
                        'color': color
                    }
                    print("✗ (failed)")
        
        # 統合データ
        unity_data = {
            'scenarioId': scenario_id,
            'scenarioName': scenario.name,
            'complexity': scenario.complexity,
            'mapSize': scenario.map_size,
            'terrain': terrain_data,
            'paths': paths_data
        }
        
        # JSON出力
        output_file = f"{self.output_dir}/{scenario_id}.json"
        with open(output_file, 'w') as f:
            json.dump(unity_data, f, indent=2)
        
        print(f"Saved: {output_file}\n")
        return output_file
    
    def _get_path_from_planner(self, scenario: TestScenario, planner_name: str):
        """
        プランナーを実行して経路を取得
        """
        try:
            if planner_name == 'ADAPTIVE':
                from adaptive_terrain_planner import AdaptiveTerrainPlanner
                planner = AdaptiveTerrainPlanner(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1
                )
                return planner.plan(timeout=30.0)
            
            elif planner_name == 'RRT_STAR':
                from rrt_star_planner import RRTStarPlanner
                planner = RRTStarPlanner(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1,
                    max_iterations=3000,
                    goal_sample_rate=0.1,
                    step_size=0.5
                )
                return planner.plan(timeout=30.0)
            
            elif planner_name == 'SAFETY_FIRST':
                from safety_first_planner import SafetyFirstPlanner
                planner = SafetyFirstPlanner(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1,
                    max_slope=10.0,
                    max_height_diff=0.15,
                    safety_margin=1.2
                )
                return planner.plan()
            
            elif planner_name == 'HPA_STAR':
                from hpa_star_planner import HPAStarPlanner
                planner = HPAStarPlanner(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1,
                    cluster_size=10
                )
                return planner.plan()
            
            elif planner_name == 'DSTAR_LITE':
                from dstar_lite_planner import DStarLitePlanner
                planner = DStarLitePlanner(
                    start=scenario.start,
                    goal=scenario.goal,
                    bounds=scenario.bounds,
                    terrain_cost_map=scenario.terrain_cost_map,
                    resolution=0.1
                )
                return planner.plan()
        
        except ImportError as e:
            print(f"  Import error for {planner_name}: {e}")
            return None
        except Exception as e:
            print(f"  Error: {e}")
            return None
        
        return None


if __name__ == '__main__':
    print("="*60)
    print("Unity Data Export")
    print("="*60)
    
    # シナリオ生成
    print("\n[1/2] Generating demo scenarios...")
    benchmark = PlannerBenchmark()
    
    # デモ用シナリオを3つ選択（SMALL, MEDIUM, LARGEから各1つ）
    all_scenarios = benchmark.generate_test_scenarios({
        "SMALL": 3,    # SIMPLE, MODERATE, COMPLEX各1個
        "MEDIUM": 3,
        "LARGE": 3
    })
    
    # 各サイズから1つずつ選択（MODERATE優先）
    demo_scenarios = []
    for map_size in ["SMALL", "MEDIUM", "LARGE"]:
        size_scenarios = [s for s in all_scenarios if s.map_size == map_size]
        # MODERATEがあれば優先、なければ最初のもの
        moderate = [s for s in size_scenarios if s.complexity == "MODERATE"]
        demo_scenarios.append(moderate[0] if moderate else size_scenarios[0])
    
    print(f"  Selected {len(demo_scenarios)} demo scenarios")
    
    # エクスポート
    print("\n[2/2] Exporting data for Unity...")
    exporter = UnityDataExporter()
    
    # 各シナリオをエクスポート
    exported_files = []
    for scenario in demo_scenarios:
        scenario_id = f"demo_{scenario.map_size.lower()}_{scenario.complexity.lower()}"
        output_file = exporter.export_scenario_with_paths(scenario, scenario_id)
        exported_files.append(output_file)
    
    print("\n" + "="*60)
    print("Unity Data Export Complete!")
    print("="*60)
    print(f"\nExported {len(exported_files)} scenarios to unity_data/:")
    for f in exported_files:
        print(f"  - {f}")
    
    print("\n次のステップ:")
    print("1. Unity プロジェクトの Assets フォルダに Resources/PathData フォルダを作成")
    print("2. unity_data/*.json ファイルを Resources/PathData にコピー")
    print("3. Unity で可視化スクリプトを実装")
