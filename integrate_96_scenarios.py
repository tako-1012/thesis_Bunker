#!/usr/bin/env python3
"""
96シナリオの複合ベンチマークデータ統合スクリプト
複数の手法のデータを統合して分析用JSONを生成
"""

import json
from pathlib import Path

def integrate_96_scenario_data():
    """96シナリオのデータを統合"""
    
    base_path = Path('/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d/benchmark_results')
    
    # 各手法のファイルマッピング
    method_files = {
        'TA*': base_path / 'ta_star_smoothed_96_full_results.json',
        'AHA*': base_path / 'aha_star_96_optimized_results.json',
        'Theta*': base_path / 'theta_star_96_results.json'
    }
    
    # データを読み込む
    methods_data = {}
    for method, filepath in method_files.items():
        if filepath.exists():
            with open(filepath, 'r') as f:
                methods_data[method] = json.load(f)
                print(f"✅ {method}: {len(methods_data[method])} シナリオ読み込み")
        else:
            print(f"⚠️ {method}: ファイルなし ({filepath})")
    
    # 統合フォーマット: results -> scenario_name -> results -> method -> computation_time
    integrated_results = {}
    
    # TA*データをベースに使用
    if 'TA*' in methods_data:
        for idx, ta_result in enumerate(methods_data['TA*']):
            scenario_id = ta_result['scenario_id']
            
            integrated_results[scenario_id] = {
                'scenario': {
                    'scenario_id': scenario_id,
                    'map_size': ta_result.get('map_size', 'unknown'),
                },
                'results': {
                    'TA*': {
                        'success': ta_result.get('success', False),
                        'computation_time': ta_result.get('computation_time', 0),
                        'path_length': ta_result.get('path_length_meters', 0),
                        'nodes_explored': ta_result.get('nodes_explored', 0),
                        'path_smoothness': ta_result.get('path_smoothness', 0)
                    }
                }
            }
    
    # AHA*データを追加
    if 'AHA*' in methods_data:
        for idx, aha_result in enumerate(methods_data['AHA*']):
            scenario_id = aha_result['scenario_id']
            
            if scenario_id not in integrated_results:
                integrated_results[scenario_id] = {
                    'scenario': {
                        'scenario_id': scenario_id,
                        'map_size': aha_result.get('map_size', 'unknown'),
                    },
                    'results': {}
                }
            
            integrated_results[scenario_id]['results']['AHA*'] = {
                'success': aha_result.get('success', False),
                'computation_time': aha_result.get('computation_time', 0),
                'path_length': aha_result.get('path_length_meters', 0),
                'nodes_explored': aha_result.get('nodes_explored', 0),
                'path_smoothness': aha_result.get('path_smoothness', 0)
            }
    
    # Theta*データを追加
    if 'Theta*' in methods_data:
        for idx, theta_result in enumerate(methods_data['Theta*']):
            scenario_id = theta_result['scenario_id']
            
            if scenario_id not in integrated_results:
                integrated_results[scenario_id] = {
                    'scenario': {
                        'scenario_id': scenario_id,
                        'map_size': theta_result.get('map_size', 'unknown'),
                    },
                    'results': {}
                }
            
            integrated_results[scenario_id]['results']['Theta*'] = {
                'success': theta_result.get('success', False),
                'computation_time': theta_result.get('computation_time', 0),
                'path_length': theta_result.get('path_length_meters', 0),
                'nodes_explored': theta_result.get('nodes_explored', 0),
                'path_smoothness': theta_result.get('path_smoothness', 0)
            }
    
    # 統合データを保存
    output = {
        'metadata': {
            'total_scenarios': len(integrated_results),
            'methods': list(method_files.keys()),
            'timestamp': '2026-01-29'
        },
        'results': integrated_results
    }
    
    output_path = '/home/hayashi/thesis_work/benchmark_96_scenarios_combined.json'
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n✅ 統合完了: {output_path}")
    print(f"📊 シナリオ数: {len(integrated_results)}")
    print(f"📋 手法数: {len(method_files)}")
    
    return output_path


if __name__ == '__main__':
    integrate_96_scenario_data()
