#!/usr/bin/env python3
"""
失敗シナリオの詳細分析
各アルゴリズムがどのシナリオで失敗したか、その理由を特定
"""
import json
import sys
import os

def analyze_failures():
    # 結果ファイル読み込み
    results_file = '../results/algorithm_comparison/comparison_results.json'
    
    if not os.path.exists(results_file):
        print(f"❌ 結果ファイルが見つかりません: {results_file}")
        return
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    print("🔍 失敗シナリオの詳細分析")
    print("=" * 60)
    
    # 各アルゴリズムの失敗シナリオを分析
    for algo_name, algo_results in results.items():
        print(f"\n{'='*60}")
        print(f"Algorithm: {algo_name}")
        print(f"{'='*60}")
        
        failures = []
        successes = []
        
        for result in algo_results:
            if not result['success']:
                failures.append(result)
            else:
                successes.append(result)
        
        print(f"Total scenarios: {len(algo_results)}")
        print(f"Successes: {len(successes)}")
        print(f"Failures: {len(failures)}")
        print(f"Success rate: {len(successes) / len(algo_results) * 100:.1f}%")
        
        if failures:
            print(f"\n❌ Failed scenarios:")
            for failure in failures:
                print(f"  - Scenario {failure['scenario_id']:03d}")
                print(f"    Terrain: {failure.get('terrain_type', 'Unknown')}")
                print(f"    Error: {failure.get('error_message', 'No error message')}")
                print(f"    Computation time: {failure.get('computation_time', 0):.2f}s")
                print(f"    Nodes explored: {failure.get('nodes_explored', 0)}")
                print()
        else:
            print(f"\n✅ All scenarios succeeded!")
        
        if successes:
            print(f"\n✅ Successful scenarios:")
            avg_time = sum(s['computation_time'] for s in successes) / len(successes)
            avg_length = sum(s['path_length'] for s in successes) / len(successes)
            avg_nodes = sum(s['nodes_explored'] for s in successes) / len(successes)
            
            print(f"  Average computation time: {avg_time:.2f}s")
            print(f"  Average path length: {avg_length:.2f}m")
            print(f"  Average nodes explored: {avg_nodes:.0f}")
    
    # 失敗パターンの分析
    print(f"\n{'='*60}")
    print("FAILURE PATTERN ANALYSIS")
    print(f"{'='*60}")
    
    # 全アルゴリズムで失敗したシナリオ
    all_failed_scenarios = set()
    algorithm_failures = {}
    
    for algo_name, algo_results in results.items():
        failed_scenarios = set()
        for result in algo_results:
            if not result['success']:
                failed_scenarios.add(result['scenario_id'])
                all_failed_scenarios.add(result['scenario_id'])
        algorithm_failures[algo_name] = failed_scenarios
    
    print(f"Scenarios that failed in ALL algorithms: {sorted(all_failed_scenarios)}")
    
    # アルゴリズム別の失敗シナリオ
    for algo_name, failed_scenarios in algorithm_failures.items():
        print(f"{algo_name}: {sorted(failed_scenarios)}")
    
    # エラーメッセージの分析
    print(f"\n{'='*60}")
    print("ERROR MESSAGE ANALYSIS")
    print("=" * 60)
    
    error_counts = {}
    for algo_name, algo_results in results.items():
        error_counts[algo_name] = {}
        for result in algo_results:
            if not result['success']:
                error_msg = result.get('error_message', 'Unknown error')
                error_counts[algo_name][error_msg] = error_counts[algo_name].get(error_msg, 0) + 1
    
    for algo_name, errors in error_counts.items():
        if errors:
            print(f"\n{algo_name} error types:")
            for error_msg, count in errors.items():
                print(f"  - {error_msg}: {count} times")
        else:
            print(f"\n{algo_name}: No errors")

if __name__ == '__main__':
    analyze_failures()
