#!/usr/bin/env python3
"""
経路計画アルゴリズムのベンチマーク実験
シミュレーション環境で4つのアルゴリズムを比較評価

使用方法:
    python3 benchmark_path_planners.py
    python3 benchmark_path_planners.py --scenario scenarios.json
    python3 benchmark_path_planners.py --output results/benchmark_20231107.json
"""

import sys
import json
import time
import argparse
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

# ROS2パッケージをインポート
import importlib
import importlib.util
import os
sys.path.append('/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/path_planner_3d')
try:
    from terrain_aware_astar_advanced import TerrainAwareAStar
    from hierarchical_astar_3d import HierarchicalAStar3D
    from dstar_lite_3d import DStarLite3D
    from rrt_star_planner_3d import RRTStarPlanner3D
except ImportError:
    # パッケージ形式でのimportも試す
    try:
        from bunker_ros2.path_planner_3d.terrain_aware_astar_advanced import TerrainAwareAStar
        from bunker_ros2.path_planner_3d.hierarchical_astar_3d import HierarchicalAStar3D
        from bunker_ros2.path_planner_3d.dstar_lite_3d import DStarLite3D
    except ImportError:
        # 直接ファイルパスからimport
        spec = importlib.util.spec_from_file_location(
            "terrain_aware_astar_advanced",
            os.path.join(os.path.dirname(__file__), "../ros2/ros2_ws/src/bunker_ros2/path_planner_3d/terrain_aware_astar_advanced.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        TerrainAwareAStar = module.TerrainAwareAStar
        # 階層型A*も同様にimport
        spec2 = importlib.util.spec_from_file_location(
            "hierarchical_astar_3d",
            os.path.join(os.path.dirname(__file__), "../ros2/ros2_ws/src/bunker_ros2/path_planner_3d/hierarchical_astar_3d.py")
        )
        module2 = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(module2)
        HierarchicalAStar3D = module2.HierarchicalAStar3D
        # D* Liteも同様にimport
        spec3 = importlib.util.spec_from_file_location(
            "dstar_lite_3d",
            os.path.join(os.path.dirname(__file__), "../ros2/ros2_ws/src/bunker_ros2/path_planner_3d/dstar_lite_3d.py")
        )
        module3 = importlib.util.module_from_spec(spec3)
        spec3.loader.exec_module(module3)
        DStarLite3D = module3.DStarLite3D
        # RRT*も同様にimport
        spec4 = importlib.util.spec_from_file_location(
            "rrt_star_planner_3d",
            os.path.join(os.path.dirname(__file__), "../ros2/ros2_ws/src/bunker_ros2/path_planner_3d/rrt_star_planner_3d.py")
        )
        module4 = importlib.util.module_from_spec(spec4)
        spec4.loader.exec_module(module4)
        RRTStarPlanner3D = module4.RRTStarPlanner3D


class BenchmarkRunner:
    """ベンチマーク実験実行クラス"""
    
    def __init__(
        self,
        voxel_size: float = 0.1,
        grid_size: Tuple[int, int, int] = (200, 200, 50),
        output_dir: str = None,
        quick: bool = False
    ):
        """
        Args:
            voxel_size: ボクセルサイズ [m]
            grid_size: グリッドサイズ (x, y, z)
            output_dir: 結果出力ディレクトリ
        """
        self.voxel_size = voxel_size
        self.grid_size = grid_size
        self.results = {}
        self.quick = quick
        
        # 出力ディレクトリ設定
        if output_dir is None:
            self.output_dir = Path('/home/hayashi/thesis_work/results')
        else:
            self.output_dir = Path(output_dir)
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 70)
        print("経路計画アルゴリズム ベンチマーク実験システム")
        print("=" * 70)
        print(f"ボクセルサイズ: {voxel_size}m")
        print(f"グリッドサイズ: {grid_size}")
        print(f"出力先: {self.output_dir}")
        print("=" * 70)
    
    def create_default_scenarios(self) -> List[Dict]:
        """デフォルトのテストシナリオを作成"""
        scenarios = [
            {
                'name': 'flat_short',
                'description': '平地・短距離（5m）',
                'start': [0.0, 0.0, 0.0],
                'goal': [5.0, 0.0, 0.0],
                'terrain_type': 'flat',
                'difficulty': 'easy'
            },
            {
                'name': 'flat_medium',
                'description': '平地・中距離（10m）',
                'start': [0.0, 0.0, 0.0],
                'goal': [7.0, 7.0, 0.0],
                'terrain_type': 'flat',
                'difficulty': 'easy'
            },
            {
                'name': 'flat_long',
                'description': '平地・長距離（20m）',
                'start': [0.0, 0.0, 0.0],
                'goal': [15.0, 15.0, 0.0],
                'terrain_type': 'flat',
                'difficulty': 'medium'
            },
            {
                'name': 'slope_gentle',
                'description': '緩やかな傾斜（10度）',
                'start': [0.0, 0.0, 0.0],
                'goal': [10.0, 0.0, 2.0],
                'terrain_type': 'slope',
                'difficulty': 'medium'
            },
            {
                'name': 'slope_moderate',
                'description': '中程度の傾斜（20度）',
                'start': [0.0, 0.0, 0.0],
                'goal': [10.0, 0.0, 3.5],
                'terrain_type': 'slope',
                'difficulty': 'medium'
            },
            {
                'name': 'slope_steep',
                'description': '急傾斜（25度）',
                'start': [0.0, 0.0, 0.0],
                'goal': [10.0, 0.0, 4.5],
                'terrain_type': 'slope',
                'difficulty': 'hard'
            },
            {
                'name': 'diagonal_climb',
                'description': '斜め上昇',
                'start': [0.0, 0.0, 0.0],
                'goal': [8.0, 8.0, 3.0],
                'terrain_type': 'slope',
                'difficulty': 'medium'
            },
            {
                'name': 'complex_3d',
                'description': '複雑な3D経路',
                'start': [-5.0, -5.0, 0.0],
                'goal': [5.0, 5.0, 3.0],
                'terrain_type': 'complex',
                'difficulty': 'hard'
            }
        ]
        return scenarios

    def create_quick_scenarios(self) -> List[Dict]:
        """クイック実行用の最小シナリオセット（<10秒想定）"""
        return [
            {
                'name': 'quick_short',
                'description': '短距離（5m, 平地）',
                'start': [0.0, 0.0, 0.0],
                'goal': [5.0, 0.0, 0.0],
                'terrain_type': 'flat',
                'difficulty': 'easy'
            },
            {
                'name': 'quick_diag',
                'description': '斜め移動（約10m, 平地）',
                'start': [0.0, 0.0, 0.0],
                'goal': [7.0, 7.0, 0.0],
                'terrain_type': 'flat',
                'difficulty': 'easy'
            }
        ]
    
    def load_scenarios_from_file(self, filepath: str) -> List[Dict]:
        """JSONファイルからシナリオをロード"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def initialize_planners(self) -> Dict:
        """プランナーを初期化"""
        print("\nプランナーを初期化中...")
        
        # map_boundsを計算
        half_x = (self.grid_size[0] * self.voxel_size) / 2.0
        half_y = (self.grid_size[1] * self.voxel_size) / 2.0
        z_max = self.grid_size[2] * self.voxel_size
        
        map_bounds = {
            'x_min': -half_x,
            'x_max': half_x,
            'y_min': -half_y,
            'y_max': half_y,
            'z_min': 0.0,
            'z_max': z_max
        }
        
        # 通常モード: 既存の全プランナー
        planners = {}

        # 他アルゴリズムは除外し、TA*（提案手法）のみをベンチマーク対象に

        # TA*（提案手法）のみをベンチマーク対象に
        planners = {}
        planners['TA* (提案手法)'] = TerrainAwareAStar(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            use_cost_calculator=False,
            map_bounds=map_bounds,
            terrain_analysis_radius=5,
            enable_online_learning=True
        )
        planners['ARA* (Anytime Repairing A*)'] = self._try_import_ara_star(map_bounds)
        planners['階層型A* (HPA*)'] = HierarchicalAStar3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            coarse_factor=5
        )
        planners['D* Lite'] = DStarLite3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size
        )
        planners['RRT*'] = RRTStarPlanner3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size
        )
        print(f"✓ {len(planners)} 個のプランナーを初期化しました")
        return planners

    def _try_import_ara_star(self, map_bounds):
        try:
            from ara_star_planner_3d import ARAStarPlanner3D
        except ImportError:
            from bunker_ros2.path_planner_3d.ara_star_planner_3d import ARAStarPlanner3D
        return ARAStarPlanner3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            max_slope=30.0,
            map_bounds=((map_bounds['x_min'], map_bounds['y_min'], map_bounds['z_min']),
                       (map_bounds['x_max'], map_bounds['y_max'], map_bounds['z_max'])),
            timeout=300.0
        )
        print(f"✓ {len(planners)} 個のプランナーを初期化しました")
        return planners
    
    def run_benchmark(
        self,
        scenarios: Optional[List[Dict]] = None,
        voxel_grid: Optional[np.ndarray] = None,
        terrain_data: Optional[any] = None
    ):
        """
        ベンチマーク実行
        
        Args:
            scenarios: テストシナリオリスト（Noneならデフォルト使用）
            voxel_grid: ボクセルグリッド（Noneならダミー作成）
            terrain_data: 地形データ
        """
        start_time = time.time()
        
        # シナリオ設定
        if scenarios is None:
            scenarios = self.create_quick_scenarios() if self.quick else self.create_default_scenarios()
        
        # ダミーのボクセルグリッド作成（実際はUnityから受信）
        if voxel_grid is None:
            voxel_grid = np.zeros(self.grid_size)
            print("\n注意: ダミーのボクセルグリッドを使用します")
        
        # プランナー初期化
        planners = self.initialize_planners()
        
        # 地形データを設定（A*系プランナー）
        for planner_name, planner in planners.items():
            if hasattr(planner, 'set_terrain_data'):
                planner.set_terrain_data(voxel_grid, terrain_data)
                print(f"  ✓ {planner_name}: 地形データ設定完了")
        
        print(f"\n実行するシナリオ: {len(scenarios)} 個")
        print("=" * 70)
        
        # シナリオごとに実行
        for i, scenario in enumerate(scenarios, 1):
            print(f"\n[{i}/{len(scenarios)}] シナリオ: {scenario['name']}")
            print(f"説明: {scenario['description']}")
            print(f"スタート: {scenario['start']} → ゴール: {scenario['goal']}")
            print("-" * 70)
            
            scenario_results = {}
            
            for planner_name, planner in planners.items():
                print(f"  {planner_name:25s} ", end='', flush=True)
                
                try:
                    # A*系プランナー用の特別処理
                    if planner_name in ['A*', 'AHA*', 'TA* (提案手法)']:
                        path = planner.plan_path(
                            tuple(scenario['start']),
                            tuple(scenario['goal'])
                        )
                        stats = planner.get_search_stats()
                        # pathが空リスト([])なら失敗扱い、grid bounds失敗文言は出さない
                        if path is not None and len(path) > 0:
                            path_distance = self._calculate_path_distance(path)
                            result = {
                                'success': True,
                                'path_length': len(path),
                                'path_distance': path_distance,
                                'nodes_explored': stats.get('nodes_explored', 0),
                                'computation_time': stats.get('computation_time', 0.0)
                            }
                            # AHA*の追加情報
                            if planner_name == 'AHA*':
                                result['phase_transitions'] = len(stats.get('phase_transitions', []))
                                result['terrain_complexity'] = stats.get('terrain_complexity', 0.0)
                            # TA*の追加情報
                            if planner_name == 'TA* (提案手法)':
                                result['strategy_switches'] = stats.get('strategy_switches', 0)
                                result['terrain_types_encountered'] = len(stats.get('terrain_types_encountered', set()))
                                result['average_complexity'] = stats.get('average_complexity', 0.0)
                            print(f"✓ 成功 ({stats['computation_time']:.3f}秒, "
                                  f"{stats['nodes_explored']}ノード, "
                                  f"距離{path_distance:.2f}m)")
                        else:
                            result = {
                                'success': False,
                                'nodes_explored': stats.get('nodes_explored', 0),
                                'computation_time': stats.get('computation_time', 0.0)
                            }
                            print("✗ 失敗")
                    
                    # 他のプランナー（PlanningResult形式）
                    else:
                        result_obj = planner.plan_path(
                            scenario['start'],
                            scenario['goal'],
                            terrain_data=terrain_data,
                            timeout=300  # 5分
                        )
                        
                        if result_obj.success:
                            result = {
                                'success': True,
                                'path_length': len(result_obj.path),
                                'path_distance': result_obj.path_length,
                                'nodes_explored': result_obj.nodes_explored,
                                'computation_time': result_obj.computation_time
                            }
                            
                            print(f"✓ 成功 ({result_obj.computation_time:.3f}秒, "
                                  f"{result_obj.nodes_explored}ノード, "
                                  f"距離{result_obj.path_length:.2f}m)")
                        else:
                            result = {
                                'success': False,
                                'nodes_explored': result_obj.nodes_explored,
                                'computation_time': result_obj.computation_time,
                                'error_message': result_obj.error_message
                            }
                            print(f"✗ 失敗 ({result_obj.error_message})")
                    
                    scenario_results[planner_name] = result
                
                except Exception as e:
                    print(f"✗ エラー: {e}")
                    scenario_results[planner_name] = {
                        'success': False,
                        'error': str(e),
                        'computation_time': 0.0,
                        'nodes_explored': 0
                    }
            
            self.results[scenario['name']] = {
                'scenario': scenario,
                'results': scenario_results
            }
        
        total_time = time.time() - start_time
        
        # 結果サマリー表示
        self._print_summary()
        
        # 結果保存
        self._save_results()
        
        print(f"\n総実行時間: {total_time:.2f}秒")
        print("=" * 70)
    
    def _calculate_path_distance(self, path: List[Tuple[float, float, float]]) -> float:
        """経路の総距離を計算"""
        if len(path) < 2:
            return 0.0
        
        distance = 0.0
        for i in range(len(path) - 1):
            p1 = np.array(path[i])
            p2 = np.array(path[i + 1])
            distance += np.linalg.norm(p2 - p1)
        return distance
    
    def _print_summary(self):
        """結果サマリーを表示"""
        print("\n" + "=" * 70)
        print("ベンチマーク結果サマリー")
        print("=" * 70)
        
        # 実行したプランナー名を結果から動的に取得
        planner_names_set = set()
        for _, data in self.results.items():
            planner_names_set.update(list(data['results'].keys()))
        planner_names = sorted(planner_names_set)
        
        for planner_name in planner_names:
            success_count = 0
            total_time = 0.0
            total_nodes = 0
            total_distance = 0.0
            count = 0
            
            for scenario_name, data in self.results.items():
                result = data['results'].get(planner_name, {})
                if result.get('success'):
                    success_count += 1
                    total_time += result.get('computation_time', 0.0)
                    total_nodes += result.get('nodes_explored', 0)
                    total_distance += result.get('path_distance', 0.0)
                    count += 1
            
            print(f"\n【{planner_name}】")
            print(f"  成功率: {success_count}/{len(self.results)} "
                  f"({100*success_count/len(self.results):.1f}%)")
            
            if count > 0:
                print(f"  平均計算時間: {total_time/count:.3f}秒")
                print(f"  平均探索ノード数: {total_nodes/count:.0f}ノード")
                print(f"  平均経路長: {total_distance/count:.2f}m")
    
    def _save_results(self):
        """結果をJSONファイルに保存"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f'benchmark_results_{timestamp}.json'
        
        # メタデータ追加
        output_data = {
            'metadata': {
                'timestamp': timestamp,
                'voxel_size': self.voxel_size,
                'grid_size': list(self.grid_size),
                'total_scenarios': len(self.results)
            },
            'results': self.results
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n結果を保存しました: {output_path}")


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='経路計画アルゴリズムのベンチマーク実験'
    )
    parser.add_argument(
        '--scenario',
        type=str,
        help='シナリオ定義JSONファイルのパス'
    )
    parser.add_argument(
        '--output',
        type=str,
        help='結果出力ディレクトリ'
    )
    parser.add_argument(
        '--voxel-size',
        type=float,
        default=0.1,
        help='ボクセルサイズ [m] (デフォルト: 0.1)'
    )
    parser.add_argument(
        '--quick',
        action='store_true',
        help='クイック実行（シナリオ2件、A*/Weighted A*のみ）'
    )
    
    args = parser.parse_args()
    
    # ベンチマーク実行
    runner = BenchmarkRunner(
        voxel_size=args.voxel_size,
        output_dir=args.output,
        quick=args.quick
    )
    
    # シナリオロード
    scenarios = None
    if args.scenario:
        scenarios = runner.load_scenarios_from_file(args.scenario)
        print(f"シナリオファイルをロードしました: {args.scenario}")
    
    # 実行
    runner.run_benchmark(scenarios=scenarios)


if __name__ == '__main__':
    main()
