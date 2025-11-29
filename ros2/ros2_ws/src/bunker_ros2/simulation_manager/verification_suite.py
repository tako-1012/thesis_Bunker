#!/usr/bin/env python3
"""
verification_suite.py
システム全体の検証・妥当性確認スイート

検証項目:
1. 経路が障害物を回避しているか
2. 経路が勾配制約を守っているか
3. スタート・ゴールが正しいか
4. 計算時間が妥当か
5. 統計結果が正確か
"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple, Dict
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent / 'path_planner_3d'))
sys.path.insert(0, str(Path(__file__).parent))

from simulation_runner import SimulationResult, TerrainGenerator
from scenario_generator import ScenarioGenerator
from astar_planner_3d import AStarPlanner3D

class SystemVerifier:
    """システム検証クラス"""
    
    def __init__(self):
        self.grid_size = (100, 100, 30)
        self.voxel_size = 0.1
        self.min_bound = (-5.0, -5.0, 0.0)
        
        self.verification_results = {
            'path_validity': [],
            'obstacle_avoidance': [],
            'slope_constraints': [],
            'start_goal_correctness': [],
            'computation_time_sanity': [],
            'statistics_accuracy': []
        }
        
        print("🔍 システム検証スイート初期化完了")
    
    def verify_all(self, num_samples: int = 20):
        """全検証を実行"""
        print(f"\n{'='*60}")
        print(f"🔍 システム検証開始（{num_samples}サンプル）")
        print(f"{'='*60}\n")
        
        # 1. 経路の妥当性検証
        print("📍 Task 1: 経路の妥当性検証")
        self.verify_path_validity(num_samples)
        
        # 2. 障害物回避検証
        print("\n🚧 Task 2: 障害物回避検証")
        self.verify_obstacle_avoidance(num_samples)
        
        # 3. 勾配制約検証
        print("\n⛰️  Task 3: 勾配制約検証")
        self.verify_slope_constraints(num_samples)
        
        # 4. スタート・ゴール正確性検証
        print("\n🎯 Task 4: スタート・ゴール正確性検証")
        self.verify_start_goal_correctness(num_samples)
        
        # 5. 計算時間妥当性検証
        print("\n⏱️  Task 5: 計算時間妥当性検証")
        self.verify_computation_time_sanity()
        
        # 6. 統計結果の正確性検証
        print("\n📊 Task 6: 統計結果の正確性検証")
        self.verify_statistics_accuracy()
        
        # 検証レポート生成
        print("\n📝 検証レポート生成中...")
        self.generate_verification_report()
    
    def verify_path_validity(self, num_samples: int):
        """経路の妥当性を検証"""
        print("  検証中...", end='', flush=True)
        
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios("scenarios")
        
        # ランダムサンプリング
        sample_ids = np.random.choice(len(scenarios), min(num_samples, len(scenarios)), replace=False)
        
        passed = 0
        failed = 0
        
        for scenario_id in sample_ids:
            scenario = scenarios[scenario_id]
            
            # 経路を再計算
            path = self._recompute_path(scenario)
            
            if path is None or len(path) == 0:
                self.verification_results['path_validity'].append({
                    'scenario_id': scenario_id,
                    'status': 'FAIL',
                    'reason': 'No path generated'
                })
                failed += 1
                continue
            
            # 検証項目
            checks = []
            
            # 1. 経路が連続しているか
            is_continuous = self._check_path_continuity(path)
            checks.append(('continuity', is_continuous))
            
            # 2. 経路の長さが妥当か（最低でもユークリッド距離以上）
            euclidean_dist = self._euclidean_distance(path[0], path[-1])
            path_length = self._calculate_path_length(path)
            is_length_valid = path_length >= euclidean_dist * 0.95  # 5%の誤差許容
            checks.append(('length_valid', is_length_valid))
            
            # 3. グリッド範囲内か
            is_in_bounds = all(self._is_in_grid_bounds(p) for p in path)
            checks.append(('in_bounds', is_in_bounds))
            
            all_passed = all(check[1] for check in checks)
            
            if all_passed:
                passed += 1
                self.verification_results['path_validity'].append({
                    'scenario_id': scenario_id,
                    'status': 'PASS',
                    'checks': checks
                })
            else:
                failed += 1
                self.verification_results['path_validity'].append({
                    'scenario_id': scenario_id,
                    'status': 'FAIL',
                    'checks': checks,
                    'failed_checks': [c[0] for c in checks if not c[1]]
                })
        
        print(f" 完了")
        print(f"  ✅ 合格: {passed}/{num_samples}")
        print(f"  ❌ 不合格: {failed}/{num_samples}")
        
        if failed > 0:
            print(f"  ⚠️  警告: {failed}個の経路に問題があります")
    
    def verify_obstacle_avoidance(self, num_samples: int):
        """障害物回避を検証"""
        print("  検証中...", end='', flush=True)
        
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios("scenarios")
        
        sample_ids = np.random.choice(len(scenarios), min(num_samples, len(scenarios)), replace=False)
        
        passed = 0
        failed = 0
        collisions_found = 0
        
        for scenario_id in sample_ids:
            scenario = scenarios[scenario_id]
            
            # 経路と障害物グリッドを取得
            path = self._recompute_path(scenario)
            occupancy_grid = TerrainGenerator.generate_occupancy_grid(
                scenario, self.grid_size, self.voxel_size, self.min_bound
            )
            
            if path is None:
                continue
            
            # 各経路点で障害物との衝突をチェック
            collision_points = []
            for point in path:
                if occupancy_grid[point] == 1:
                    collision_points.append(point)
            
            if len(collision_points) == 0:
                passed += 1
                self.verification_results['obstacle_avoidance'].append({
                    'scenario_id': scenario_id,
                    'status': 'PASS',
                    'collision_points': 0
                })
            else:
                failed += 1
                collisions_found += len(collision_points)
                self.verification_results['obstacle_avoidance'].append({
                    'scenario_id': scenario_id,
                    'status': 'FAIL',
                    'collision_points': len(collision_points),
                    'total_waypoints': len(path),
                    'collision_percentage': len(collision_points) / len(path) * 100
                })
        
        print(f" 完了")
        print(f"  ✅ 合格: {passed}/{num_samples}")
        print(f"  ❌ 不合格: {failed}/{num_samples}")
        
        if collisions_found > 0:
            print(f"  ⚠️  警告: {collisions_found}個の衝突点が見つかりました")
    
    def verify_slope_constraints(self, num_samples: int):
        """勾配制約の遵守を検証"""
        print("  検証中...", end='', flush=True)
        
        max_allowed_slope = 30.0  # 度
        
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios("scenarios")
        
        sample_ids = np.random.choice(len(scenarios), min(num_samples, len(scenarios)), replace=False)
        
        passed = 0
        failed = 0
        
        for scenario_id in sample_ids:
            scenario = scenarios[scenario_id]
            path = self._recompute_path(scenario)
            
            if path is None or len(path) < 2:
                continue
            
            # 経路の各セグメントで勾配をチェック
            violations = []
            max_slope_found = 0.0
            
            for i in range(len(path) - 1):
                p1 = self._grid_to_world(path[i])
                p2 = self._grid_to_world(path[i + 1])
                
                horizontal_dist = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                vertical_dist = abs(p2[2] - p1[2])
                
                if horizontal_dist > 1e-6:
                    slope_deg = np.degrees(np.arctan(vertical_dist / horizontal_dist))
                    max_slope_found = max(max_slope_found, slope_deg)
                    
                    # 許容値に余裕を持たせる（1度の誤差許容）
                    if slope_deg > max_allowed_slope + 1.0:
                        violations.append({
                            'segment': i,
                            'slope': slope_deg,
                            'positions': (p1, p2)
                        })
            
            if len(violations) == 0:
                passed += 1
                self.verification_results['slope_constraints'].append({
                    'scenario_id': scenario_id,
                    'status': 'PASS',
                    'max_slope': max_slope_found
                })
            else:
                failed += 1
                self.verification_results['slope_constraints'].append({
                    'scenario_id': scenario_id,
                    'status': 'FAIL',
                    'violations': len(violations),
                    'max_slope': max_slope_found,
                    'max_allowed': max_allowed_slope
                })
        
        print(f" 完了")
        print(f"  ✅ 合格: {passed}/{num_samples}")
        print(f"  ❌ 不合格: {failed}/{num_samples}")
        
        if failed > 0:
            print(f"  ⚠️  警告: {failed}個の経路で勾配制約違反が見つかりました")
    
    def verify_start_goal_correctness(self, num_samples: int):
        """スタート・ゴールの正確性を検証"""
        print("  検証中...", end='', flush=True)
        
        generator = ScenarioGenerator()
        scenarios = generator.load_scenarios("scenarios")
        
        sample_ids = np.random.choice(len(scenarios), min(num_samples, len(scenarios)), replace=False)
        
        passed = 0
        failed = 0
        
        for scenario_id in sample_ids:
            scenario = scenarios[scenario_id]
            path = self._recompute_path(scenario)
            
            if path is None or len(path) == 0:
                continue
            
            # スタート地点の検証
            start_grid = self._world_to_grid(scenario.start_position)
            path_start = path[0]
            
            start_match = np.linalg.norm(np.array(start_grid) - np.array(path_start)) < 2.0
            
            # ゴール地点の検証
            goal_grid = self._world_to_grid(scenario.goal_position)
            path_goal = path[-1]
            
            goal_match = np.linalg.norm(np.array(goal_grid) - np.array(path_goal)) < 2.0
            
            if start_match and goal_match:
                passed += 1
                self.verification_results['start_goal_correctness'].append({
                    'scenario_id': scenario_id,
                    'status': 'PASS'
                })
            else:
                failed += 1
                self.verification_results['start_goal_correctness'].append({
                    'scenario_id': scenario_id,
                    'status': 'FAIL',
                    'start_match': start_match,
                    'goal_match': goal_match,
                    'start_distance': np.linalg.norm(np.array(start_grid) - np.array(path_start)),
                    'goal_distance': np.linalg.norm(np.array(goal_grid) - np.array(path_goal))
                })
        
        print(f" 完了")
        print(f"  ✅ 合格: {passed}/{num_samples}")
        print(f"  ❌ 不合格: {failed}/{num_samples}")
    
    def verify_computation_time_sanity(self):
        """計算時間の妥当性を検証"""
        print("  検証中...", end='', flush=True)
        
        with open("results/final_results.json", 'r') as f:
            results = json.load(f)
        
        times = [r['computation_time'] for r in results]
        
        # 異常値検出
        mean_time = np.mean(times)
        std_time = np.std(times)
        
        # 3σ法で外れ値を検出
        outliers = []
        for i, t in enumerate(times):
            if abs(t - mean_time) > 3 * std_time:
                outliers.append({
                    'scenario_id': results[i]['scenario_id'],
                    'time': t,
                    'deviation': abs(t - mean_time) / std_time
                })
        
        # 妥当性チェック
        checks = {
            'all_positive': all(t > 0 for t in times),
            'all_reasonable': all(t < 300 for t in times),  # 5分以内
            'mean_reasonable': 0.01 < mean_time < 120,  # 平均が10ms〜2分
            'few_outliers': len(outliers) < len(times) * 0.05  # 外れ値が5%未満
        }
        
        all_passed = all(checks.values())
        
        self.verification_results['computation_time_sanity'] = {
            'status': 'PASS' if all_passed else 'FAIL',
            'checks': checks,
            'mean': mean_time,
            'std': std_time,
            'outliers': outliers
        }
        
        print(f" 完了")
        if all_passed:
            print(f"  ✅ 計算時間は妥当です")
            print(f"     平均: {mean_time:.2f}秒, 標準偏差: {std_time:.2f}秒")
        else:
            print(f"  ⚠️  計算時間に異常があります")
            for check_name, result in checks.items():
                if not result:
                    print(f"     ❌ {check_name}")
    
    def verify_statistics_accuracy(self):
        """統計結果の正確性を検証"""
        print("  検証中...", end='', flush=True)
        
        # 結果を読み込んで再計算
        with open("results/final_results.json", 'r') as f:
            results = json.load(f)
        
        # 成功率を再計算
        total = len(results)
        successful = sum(1 for r in results if r['path_found'])
        calculated_success_rate = (successful / total) * 100
        
        # 平均計算時間を再計算
        times = [r['computation_time'] for r in results]
        calculated_mean_time = np.mean(times)
        calculated_std_time = np.std(times)
        
        # 保存された統計と比較
        with open("results/statistical_analysis.json", 'r') as f:
            saved_stats = json.load(f)
        
        saved_success_rate = saved_stats['basic_stats']['success_rate']
        saved_mean_time = saved_stats['descriptive_statistics']['computation_time']['mean']
        saved_std_time = saved_stats['descriptive_statistics']['computation_time']['std']
        
        # 許容誤差
        tolerance = 0.01
        
        checks = {
            'success_rate_match': abs(calculated_success_rate - saved_success_rate) < tolerance,
            'mean_time_match': abs(calculated_mean_time - saved_mean_time) < tolerance,
            'std_time_match': abs(calculated_std_time - saved_std_time) < tolerance
        }
        
        all_passed = all(checks.values())
        
        self.verification_results['statistics_accuracy'] = {
            'status': 'PASS' if all_passed else 'FAIL',
            'calculated': {
                'success_rate': calculated_success_rate,
                'mean_time': calculated_mean_time,
                'std_time': calculated_std_time
            },
            'saved': {
                'success_rate': saved_success_rate,
                'mean_time': saved_mean_time,
                'std_time': saved_std_time
            },
            'checks': checks
        }
        
        print(f" 完了")
        if all_passed:
            print(f"  ✅ 統計結果は正確です")
        else:
            print(f"  ⚠️  統計結果に不一致があります")
            for check_name, result in checks.items():
                if not result:
                    print(f"     ❌ {check_name}")
    
    def generate_verification_report(self):
        """検証レポート生成"""
        report_path = Path("results/verification_report.json")
        
        # サマリー計算
        summary = {}
        for category, results in self.verification_results.items():
            if isinstance(results, list):
                passed = sum(1 for r in results if r.get('status') == 'PASS')
                failed = sum(1 for r in results if r.get('status') == 'FAIL')
                summary[category] = {
                    'passed': passed,
                    'failed': failed,
                    'total': passed + failed,
                    'pass_rate': (passed / (passed + failed) * 100) if (passed + failed) > 0 else 0
                }
            else:
                summary[category] = {
                    'status': results.get('status', 'UNKNOWN')
                }
        
        report = {
            'verification_date': str(np.datetime64('now')),
            'summary': summary,
            'details': self.verification_results
        }
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 検証レポート保存: {report_path}")
        
        # サマリー表示
        print(f"\n{'='*60}")
        print("📊 検証サマリー")
        print(f"{'='*60}")
        
        for category, data in summary.items():
            category_name = category.replace('_', ' ').title()
            if 'pass_rate' in data:
                print(f"\n{category_name}:")
                print(f"  合格: {data['passed']}/{data['total']} ({data['pass_rate']:.1f}%)")
                if data['failed'] > 0:
                    print(f"  ⚠️  不合格: {data['failed']}")
            else:
                status_icon = '✅' if data['status'] == 'PASS' else '⚠️'
                print(f"\n{category_name}: {status_icon} {data['status']}")
        
        print(f"\n{'='*60}")
        
        # 全体判定
        all_categories_passed = all(
            (d.get('pass_rate', 0) == 100) or (d.get('status') == 'PASS')
            for d in summary.values()
        )
        
        if all_categories_passed:
            print("🎉 全ての検証が合格しました！")
        else:
            print("⚠️  一部の検証で問題が見つかりました。詳細を確認してください。")
        
        print(f"{'='*60}\n")
    
    # ヘルパーメソッド
    def _recompute_path(self, scenario):
        """経路を再計算"""
        from astar_planner_3d import AStarPlanner3D
        
        planner = AStarPlanner3D(
            voxel_size=self.voxel_size,
            grid_size=self.grid_size,
            min_bound=self.min_bound
        )
        
        occupancy_grid = TerrainGenerator.generate_occupancy_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        slope_grid = TerrainGenerator.generate_slope_grid(
            scenario, self.grid_size, self.voxel_size, self.min_bound
        )
        
        # 地形データを設定
        planner.set_terrain_data(occupancy_grid, slope_grid)
        
        # スタート・ゴール（ワールド座標）
        start_world = scenario.start_position
        goal_world = scenario.goal_position
        
        # 経路計画
        path_world = planner.plan_path(start_world, goal_world)
        
        if path_world:
            # ワールド座標をグリッド座標に変換
            path_grid = [self._world_to_grid(p) for p in path_world]
            return path_grid
        
        return None
    
    def _world_to_grid(self, world_pos):
        """ワールド→グリッド座標変換"""
        x = int((world_pos[0] - self.min_bound[0]) / self.voxel_size)
        y = int((world_pos[1] - self.min_bound[1]) / self.voxel_size)
        z = int((world_pos[2] - self.min_bound[2]) / self.voxel_size)
        
        x = max(0, min(x, self.grid_size[0] - 1))
        y = max(0, min(y, self.grid_size[1] - 1))
        z = max(0, min(z, self.grid_size[2] - 1))
        
        return (x, y, z)
    
    def _grid_to_world(self, grid_pos):
        """グリッド→ワールド座標変換"""
        x = grid_pos[0] * self.voxel_size + self.min_bound[0]
        y = grid_pos[1] * self.voxel_size + self.min_bound[1]
        z = grid_pos[2] * self.voxel_size + self.min_bound[2]
        return (x, y, z)
    
    def _check_path_continuity(self, path):
        """経路の連続性をチェック"""
        for i in range(len(path) - 1):
            dist = np.linalg.norm(np.array(path[i+1]) - np.array(path[i]))
            if dist > 2.0:  # 2グリッド以上離れている場合は不連続
                return False
        return True
    
    def _euclidean_distance(self, p1, p2):
        """ユークリッド距離計算"""
        p1_world = self._grid_to_world(p1)
        p2_world = self._grid_to_world(p2)
        return np.linalg.norm(np.array(p2_world) - np.array(p1_world))
    
    def _calculate_path_length(self, path):
        """経路長計算"""
        length = 0.0
        for i in range(len(path) - 1):
            p1 = self._grid_to_world(path[i])
            p2 = self._grid_to_world(path[i+1])
            length += np.linalg.norm(np.array(p2) - np.array(p1))
        return length
    
    def _is_in_grid_bounds(self, point):
        """グリッド範囲内かチェック"""
        return (0 <= point[0] < self.grid_size[0] and
                0 <= point[1] < self.grid_size[1] and
                0 <= point[2] < self.grid_size[2])

def main():
    """メイン実行"""
    verifier = SystemVerifier()
    
    # 20サンプルで検証
    verifier.verify_all(num_samples=20)

if __name__ == "__main__":
    main()
