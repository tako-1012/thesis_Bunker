"""
シナリオの到達可能性検証

目的：物理的に到達不可能なシナリオを事前に検出・除外
方法：A*で事前チェック（最も信頼性が高い）
"""
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple
import logging
import sys
import os

# パス設定
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'path_planner_3d'))

from astar_planner_3d_fixed import AStarPlanner3D

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ReachabilityValidator:
    """到達可能性検証器"""
    
    def __init__(self, map_bounds=None, voxel_size=0.2):
        """
        Args:
            map_bounds: マップ範囲
            voxel_size: ボクセルサイズ
        """
        if map_bounds is None:
            map_bounds = ([-25, -25, 0], [25, 25, 5])
        
        # A*を検証用に使用（最も信頼性が高い）
        self.validator = AStarPlanner3D(
            voxel_size=voxel_size,
            map_bounds=map_bounds
        )
        
        # 検証用のタイムアウト（短め）
        self.validation_timeout = 300  # 5分
        
        logger.info("Reachability Validator initialized")
    
    def validate_scenario(self, scenario: Dict) -> Tuple[bool, str]:
        """
        シナリオの到達可能性を検証
        
        Args:
            scenario: シナリオ辞書
        
        Returns:
            (到達可能?, 理由)
        """
        start = scenario['start']
        goal = scenario['goal']
        
        logger.info(f"Validating scenario {scenario.get('scenario_id', '?')}")
        logger.info(f"  Start: {start}")
        logger.info(f"  Goal: {goal}")
        
        # 1. 基本的な妥当性チェック
        if not self._is_valid_position(start):
            return False, f"Invalid start position: out of bounds"
        
        if not self._is_valid_position(goal):
            return False, f"Invalid goal position: out of bounds"
        
        # 2. 直線距離チェック
        direct_distance = np.linalg.norm(
            np.array(goal) - np.array(start)
        )
        
        if direct_distance < 1.0:
            return False, f"Start and goal too close: {direct_distance:.2f}m"
        
        # 3. A*で経路探索を試行
        try:
            result = self.validator.plan_path(start=start, goal=goal, terrain_data=None, timeout=self.validation_timeout)
            
            if result.success and len(result.path) > 0:
                logger.info(f"  ✅ Reachable (path length: {result.path_length:.2f}m)")
                return True, "Reachable"
            else:
                # A*でも到達できない = 物理的に不可能
                logger.warning(f"  ❌ Unreachable: {result.error_message}")
                return False, f"Unreachable: {result.error_message}"
        
        except Exception as e:
            logger.error(f"  ❌ Validation error: {str(e)}")
            return False, f"Validation error: {str(e)}"
    
    def _is_valid_position(self, pos):
        """位置の妥当性チェック"""
        min_bound = self.validator.min_bound
        max_bound = self.validator.max_bound
        
        return (min_bound[0] <= pos[0] <= max_bound[0] and
                min_bound[1] <= pos[1] <= max_bound[1] and
                min_bound[2] <= pos[2] <= max_bound[2])
    
    def validate_all_scenarios(self, scenario_dir: str) -> Dict:
        """
        ディレクトリ内の全シナリオを検証
        
        Args:
            scenario_dir: シナリオディレクトリ
        
        Returns:
            検証結果の辞書
        """
        scenario_path = Path(scenario_dir)
        scenario_files = sorted(scenario_path.glob('scenario_*.json'))
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Validating {len(scenario_files)} scenarios in {scenario_dir}")
        logger.info(f"{'='*70}")
        
        results = {
            'total': len(scenario_files),
            'reachable': 0,
            'unreachable': 0,
            'error': 0,
            'scenarios': []
        }
        
        for scenario_file in scenario_files:
            with open(scenario_file) as f:
                scenario = json.load(f)
            
            is_reachable, reason = self.validate_scenario(scenario)
            
            scenario_result = {
                'scenario_id': scenario['scenario_id'],
                'file': str(scenario_file),
                'reachable': is_reachable,
                'reason': reason,
                'start': scenario['start'],
                'goal': scenario['goal'],
                'distance': scenario.get('distance', 0)
            }
            
            results['scenarios'].append(scenario_result)
            
            if is_reachable:
                results['reachable'] += 1
            elif 'error' in reason.lower():
                results['error'] += 1
            else:
                results['unreachable'] += 1
        
        # サマリー
        logger.info(f"\n{'='*70}")
        logger.info("Validation Summary")
        logger.info(f"{'='*70}")
        logger.info(f"Total scenarios:      {results['total']}")
        logger.info(f"Reachable:            {results['reachable']} ({results['reachable']/results['total']*100:.1f}%)")
        logger.info(f"Unreachable:          {results['unreachable']} ({results['unreachable']/results['total']*100:.1f}%)")
        logger.info(f"Validation errors:    {results['error']}")
        
        return results
    
    def filter_reachable_scenarios(self, scenario_dir: str, output_dir: str):
        """
        到達可能なシナリオのみをフィルタリング
        
        Args:
            scenario_dir: 入力ディレクトリ
            output_dir: 出力ディレクトリ
        """
        results = self.validate_all_scenarios(scenario_dir)
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 到達可能なシナリオのみをコピー
        reachable_count = 0
        
        for scenario_result in results['scenarios']:
            if scenario_result['reachable']:
                # 元のファイルを読み込み
                with open(scenario_result['file']) as f:
                    scenario = json.load(f)
                
                # 新しいIDで保存
                new_filename = f"scenario_{reachable_count:03d}.json"
                output_file = output_path / new_filename
                
                scenario['scenario_id'] = reachable_count
                scenario['validation'] = {
                    'reachable': True,
                    'validated_at': scenario_result['reason']
                }
                
                with open(output_file, 'w') as f:
                    json.dump(scenario, f, indent=2)
                
                reachable_count += 1
        
        logger.info(f"\n✅ Filtered {reachable_count} reachable scenarios")
        logger.info(f"   Saved to: {output_dir}")
        
        # 検証レポートを保存
        report_file = output_path / 'validation_report.json'
        with open(report_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"   Validation report: {report_file}")

def validate_all_representative_terrains():
    """全ての代表的地形シナリオを検証"""
    validator = ReachabilityValidator(
        map_bounds=([-25, -25, 0], [25, 25, 5]),
        voxel_size=0.2
    )
    
    terrain_types = [
        'flat_agricultural_field',
        'gentle_hills',
        'steep_terrain',
        'complex_obstacles',
        'extreme_hazards'
    ]
    
    overall_stats = {
        'total': 0,
        'reachable': 0,
        'unreachable': 0
    }
    
    for terrain_type in terrain_types:
        logger.info(f"\n\n{'#'*70}")
        logger.info(f"# {terrain_type.upper()}")
        logger.info(f"{'#'*70}")
        
        input_dir = f'../scenarios/representative/{terrain_type}'
        output_dir = f'../scenarios/validated/{terrain_type}'
        
        validator.filter_reachable_scenarios(input_dir, output_dir)
        
        # 統計を更新
        report_file = Path(output_dir) / 'validation_report.json'
        if report_file.exists():
            with open(report_file) as f:
                results = json.load(f)
                overall_stats['total'] += results['total']
                overall_stats['reachable'] += results['reachable']
                overall_stats['unreachable'] += results['unreachable']
    
    # 全体サマリー
    logger.info(f"\n\n{'='*70}")
    logger.info("OVERALL VALIDATION SUMMARY")
    logger.info(f"{'='*70}")
    logger.info(f"Total scenarios:      {overall_stats['total']}")
    logger.info(f"Reachable:            {overall_stats['reachable']} ({overall_stats['reachable']/overall_stats['total']*100:.1f}%)")
    logger.info(f"Unreachable:          {overall_stats['unreachable']} ({overall_stats['unreachable']/overall_stats['total']*100:.1f}%)")
    logger.info(f"\n✅ Validated scenarios saved to: ../scenarios/validated/")

if __name__ == '__main__':
    validate_all_representative_terrains()
