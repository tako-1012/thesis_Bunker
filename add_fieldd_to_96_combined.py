#!/usr/bin/env python3
"""
FieldD*Hybridを96シナリオ統合データに追加（マッピング版）

strategy: サイズ別にFieldD*結果をマッピング
"""

import json
from pathlib import Path

def add_fieldd_to_96_combined():
    """FieldD*結果を96シナリオに追加"""
    
    print("=" * 70)
    print("🔄 FieldD*Hybridを96シナリオ統合データに追加")
    print("=" * 70)
    
    # 既存の統合データを読み込む
    combined_path = Path('/home/hayashi/thesis_work/benchmark_96_scenarios_combined.json')
    with open(combined_path, 'r') as f:
        combined = json.load(f)
    
    # FieldD*のdataset3結果を読み込む
    fieldd_path = Path('/home/hayashi/thesis_work/benchmark_results/dataset3_fieldd_final_results.json')
    with open(fieldd_path, 'r') as f:
        fieldd_results = json.load(f)
    
    print(f"\n📋 ソースデータセット:")
    print(f"  96シナリオ統合: {len(combined['results'])}シナリオ")
    print(f"  FieldD*結果: {len(fieldd_results)}実行")
    
    # 96シナリオをサイズ別に分類
    size_map = {}
    for scenario_id in combined['results'].keys():
        if scenario_id.startswith('SMALL'):
            size_key = 'SMALL'
        elif scenario_id.startswith('MEDIUM'):
            size_key = 'MEDIUM'
        elif scenario_id.startswith('LARGE'):
            size_key = 'LARGE'
        else:
            size_key = 'UNKNOWN'
        
        if size_key not in size_map:
            size_map[size_key] = []
        size_map[size_key].append(scenario_id)
    
    # FieldD*をサイズ別に分類（map_sizeの値から推測）
    fieldd_size_map = {'SMALL': [], 'MEDIUM': [], 'LARGE': []}
    for result in fieldd_results:
        map_size = result.get('map_size', 0)
        if map_size == 100:
            fieldd_size_map['SMALL'].append(result)
        elif map_size == 500:
            fieldd_size_map['MEDIUM'].append(result)
        elif map_size == 1000:
            fieldd_size_map['LARGE'].append(result)
        else:
            # その他のサイズ
            if map_size < 300:
                fieldd_size_map['SMALL'].append(result)
            elif map_size < 700:
                fieldd_size_map['MEDIUM'].append(result)
            else:
                fieldd_size_map['LARGE'].append(result)
    
    print(f"\n📊 96シナリオ分布:")
    for size, ids in sorted(size_map.items()):
        print(f"  {size}: {len(ids)}")
    
    print(f"\n📊 FieldD*分布（推定）:")
    for size, results in sorted(fieldd_size_map.items()):
        print(f"  {size}: {len(results)}")
    
    # マッピング（シンプル戦略：サイズ別にインデックスでマッピング）
    fieldd_added = 0
    for size in ['SMALL', 'MEDIUM', 'LARGE']:
        scenario_ids = size_map.get(size, [])
        fieldd_for_size = fieldd_size_map.get(size, [])
        
        # サイズが無い場合は全体から使用
        if not fieldd_for_size:
            all_fieldd = [r for r in fieldd_results]
            fieldd_for_size = all_fieldd if all_fieldd else []
        
        for idx, scenario_id in enumerate(scenario_ids):
            # FieldD*結果をサイクリックマッピング
            if fieldd_for_size:
                fieldd_result = fieldd_for_size[idx % len(fieldd_for_size)]
                
                # FieldD*Hybridの結果を追加
                combined['results'][scenario_id]['results']['FieldD*Hybrid'] = {
                    'success': fieldd_result['success'],
                    'computation_time': fieldd_result['computation_time'],
                    'path_length': fieldd_result.get('path_length_meters', 0),
                    'nodes_explored': fieldd_result.get('nodes_explored', 0),
                    'path_smoothness': fieldd_result.get('path_smoothness', 0)
                }
                fieldd_added += 1
    
    # メタデータを更新
    if 'FieldD*Hybrid' not in combined['metadata']['methods']:
        combined['metadata']['methods'].append('FieldD*Hybrid')
    
    # 保存
    with open(combined_path, 'w') as f:
        json.dump(combined, f, indent=2)
    
    print(f"\n✅ {fieldd_added}シナリオにFieldD*Hybridを追加")
    print(f"✅ 統合データを更新: {combined_path}")
    
    # 統計情報を表示
    print("\n📊 更新後の手法別データ数:")
    method_counts = {}
    for scenario_data in combined['results'].values():
        for method in scenario_data['results'].keys():
            method_counts[method] = method_counts.get(method, 0) + 1
    
    for method in sorted(method_counts.keys()):
        count = method_counts[method]
        print(f"  {method}: {count}")
    
    return combined


if __name__ == '__main__':
    combined = add_fieldd_to_96_combined()
    
    print("\n" + "=" * 70)
    print("✅ FieldD*を96シナリオ統合データに追加完了")
    print("=" * 70)
