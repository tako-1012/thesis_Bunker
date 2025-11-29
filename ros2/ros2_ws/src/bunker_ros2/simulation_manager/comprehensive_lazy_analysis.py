#!/usr/bin/env python3
"""
Lazy TA-A* Comprehensive Performance Analysis

Lazy TA-A*の包括的な性能分析と他のアルゴリズムとの比較
"""
import sys
import time
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any

# パス設定
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Lazy TA-A*をインポート
from lazy_tastar_wrapper import LazyTAstarWrapper

def create_comprehensive_scenarios() -> List[Dict[str, Any]]:
    """包括的なテストシナリオを生成"""
    scenarios = []
    
    # 基本テストケース
    basic_tests = [
        {'name': 'Very Short', 'start': [0, 0, 0.2], 'goal': [2, 2, 0.2]},
        {'name': 'Short', 'start': [0, 0, 0.2], 'goal': [5, 5, 0.2]},
        {'name': 'Medium', 'start': [0, 0, 0.2], 'goal': [10, 10, 0.2]},
        {'name': 'Long', 'start': [-10, -10, 0.2], 'goal': [10, 10, 0.2]},
        {'name': 'Very Long', 'start': [-20, -20, 0.2], 'goal': [20, 20, 0.2]},
    ]
    
    # 高度変化テスト
    height_tests = [
        {'name': 'Low Height', 'start': [0, 0, 0.2], 'goal': [5, 5, 0.5]},
        {'name': 'Medium Height', 'start': [0, 0, 0.2], 'goal': [5, 5, 1.0]},
        {'name': 'High Height', 'start': [0, 0, 0.2], 'goal': [5, 5, 1.5]},
        {'name': 'Downward', 'start': [0, 0, 1.0], 'goal': [5, 5, 0.2]},
    ]
    
    # 複雑な経路テスト
    complex_tests = [
        {'name': 'Diagonal', 'start': [-5, -5, 0.2], 'goal': [5, 5, 0.2]},
        {'name': 'L-Shape', 'start': [0, 0, 0.2], 'goal': [10, 5, 0.2]},
        {'name': 'U-Shape', 'start': [-5, 0, 0.2], 'goal': [5, 0, 0.2]},
        {'name': 'Zigzag', 'start': [-5, -5, 0.2], 'goal': [5, 5, 0.2]},
    ]
    
    # 境界テスト
    boundary_tests = [
        {'name': 'Near Boundary', 'start': [-20, -20, 0.2], 'goal': [-15, -15, 0.2]},
        {'name': 'Corner to Corner', 'start': [-20, -20, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'Edge Case', 'start': [0, -20, 0.2], 'goal': [0, 20, 0.2]},
    ]
    
    # 全テストケースを結合
    all_tests = basic_tests + height_tests + complex_tests + boundary_tests
    
    for i, test in enumerate(all_tests):
        scenario = {
            'scenario_id': i,
            'name': test['name'],
            'start_position': test['start'],
            'goal_position': test['goal'],
            'category': 'basic' if test in basic_tests else 
                       'height' if test in height_tests else
                       'complex' if test in complex_tests else 'boundary',
            'terrain_params': {
                'terrain_type': 'flat_terrain',
                'obstacle_density': 0.0,
                'max_slope': 15.0,
                'roughness': 0.01
            }
        }
        scenarios.append(scenario)
    
    return scenarios

def analyze_performance(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """性能分析を実行"""
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    if not successful:
        return {
            'success_rate': 0.0,
            'avg_computation_time': 0.0,
            'avg_path_length': 0.0,
            'avg_nodes_explored': 0,
            'avg_phase_used': 0,
            'performance_grade': 'F'
        }
    
    # 基本統計
    success_rate = len(successful) / len(results) * 100
    avg_time = np.mean([r['computation_time'] for r in successful])
    avg_length = np.mean([r['path_length'] for r in successful])
    avg_nodes = np.mean([r['nodes_explored'] for r in successful])
    avg_phase = np.mean([r['phase_used'] for r in successful])
    
    # 時間統計
    min_time = np.min([r['computation_time'] for r in successful])
    max_time = np.max([r['computation_time'] for r in successful])
    std_time = np.std([r['computation_time'] for r in successful])
    
    # 経路長統計
    min_length = np.min([r['path_length'] for r in successful])
    max_length = np.max([r['path_length'] for r in successful])
    std_length = np.std([r['path_length'] for r in successful])
    
    # Phase別統計
    phase_counts = {}
    for r in successful:
        phase = r['phase_used']
        phase_counts[phase] = phase_counts.get(phase, 0) + 1
    
    # 性能グレード計算
    if success_rate >= 95 and avg_time <= 0.1:
        grade = 'A+'
    elif success_rate >= 90 and avg_time <= 0.2:
        grade = 'A'
    elif success_rate >= 80 and avg_time <= 0.5:
        grade = 'B'
    elif success_rate >= 70 and avg_time <= 1.0:
        grade = 'C'
    elif success_rate >= 60:
        grade = 'D'
    else:
        grade = 'F'
    
    return {
        'success_rate': success_rate,
        'total_tests': len(results),
        'successful_tests': len(successful),
        'failed_tests': len(failed),
        'avg_computation_time': avg_time,
        'min_computation_time': min_time,
        'max_computation_time': max_time,
        'std_computation_time': std_time,
        'avg_path_length': avg_length,
        'min_path_length': min_length,
        'max_path_length': max_length,
        'std_path_length': std_length,
        'avg_nodes_explored': avg_nodes,
        'avg_phase_used': avg_phase,
        'phase_distribution': phase_counts,
        'performance_grade': grade
    }

def test_lazy_tastar_comprehensive(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Lazy TA-A*の包括的テスト"""
    print("="*70)
    print("🚀 Lazy TA-A* Comprehensive Performance Test")
    print("="*70)
    
    # Lazy TA-A*を初期化
    planner = LazyTAstarWrapper(
        grid_size=(50, 50, 20),
        voxel_size=0.1,
        max_slope=30.0
    )
    
    results = []
    total_time = 0.0
    
    for i, scenario in enumerate(scenarios):
        print(f"\nTest {i+1}/{len(scenarios)}: {scenario['name']} ({scenario['category']})")
        print(f"  Start: {scenario['start_position']}")
        print(f"  Goal:  {scenario['goal_position']}")
        
        start_time = time.time()
        
        result = planner.plan_path(
            scenario['start_position'],
            scenario['goal_position'],
            timeout=120.0
        )
        
        test_time = time.time() - start_time
        total_time += test_time
        
        # 結果を記録
        test_result = {
            'scenario_id': scenario['scenario_id'],
            'scenario_name': scenario['name'],
            'category': scenario['category'],
            'success': result['success'],
            'computation_time': result['computation_time'],
            'path_length': result['path_length'],
            'nodes_explored': result['nodes_explored'],
            'phase_used': result.get('phase_used', 0),
            'terrain_adaptations': result.get('terrain_adaptations', 0),
            'error_message': result.get('error_message', ''),
            'test_time': test_time
        }
        
        results.append(test_result)
        
        if result['success']:
            print(f"  ✅ SUCCESS")
            print(f"    Phase: {result.get('phase_used', 0)}")
            print(f"    Time: {result['computation_time']:.3f}s")
            print(f"    Path length: {result['path_length']:.2f}m")
            print(f"    Nodes: {result['nodes_explored']}")
        else:
            print(f"  ❌ FAILED: {result.get('error_message', 'Unknown error')}")
    
    # 性能分析
    analysis = analyze_performance(results)
    
    return {
        'algorithm': 'Lazy TA-A*',
        'total_test_time': total_time,
        'analysis': analysis,
        'results': results
    }

def main():
    """メイン実行関数"""
    print("="*70)
    print("🔥 Lazy TA-A* Comprehensive Performance Analysis")
    print("="*70)
    
    # テストシナリオ生成
    scenarios = create_comprehensive_scenarios()
    print(f"Generated {len(scenarios)} comprehensive test scenarios")
    
    # テスト実行
    start_time = time.time()
    test_results = test_lazy_tastar_comprehensive(scenarios)
    total_time = time.time() - start_time
    
    analysis = test_results['analysis']
    
    # 結果表示
    print("\n" + "="*70)
    print("📊 Comprehensive Performance Analysis")
    print("="*70)
    
    print(f"\nAlgorithm: {test_results['algorithm']}")
    print(f"Performance Grade: {analysis['performance_grade']}")
    print(f"Success Rate: {analysis['success_rate']:.1f}% ({analysis['successful_tests']}/{analysis['total_tests']})")
    print(f"Total Test Time: {total_time:.2f}s")
    
    print(f"\n⏱️  Computation Time Analysis:")
    print(f"  Average: {analysis['avg_computation_time']:.3f}s")
    print(f"  Range: {analysis['min_computation_time']:.3f}s - {analysis['max_computation_time']:.3f}s")
    print(f"  Std Dev: {analysis['std_computation_time']:.3f}s")
    
    print(f"\n📏 Path Length Analysis:")
    print(f"  Average: {analysis['avg_path_length']:.2f}m")
    print(f"  Range: {analysis['min_path_length']:.2f}m - {analysis['max_path_length']:.2f}m")
    print(f"  Std Dev: {analysis['std_path_length']:.2f}m")
    
    print(f"\n🔍 Algorithm Behavior:")
    print(f"  Average Nodes Explored: {analysis['avg_nodes_explored']:.0f}")
    print(f"  Average Phase Used: {analysis['avg_phase_used']:.1f}")
    print(f"  Phase Distribution: {analysis['phase_distribution']}")
    
    # カテゴリ別分析
    print(f"\n📊 Category Analysis:")
    categories = {}
    for result in test_results['results']:
        cat = result['category']
        if cat not in categories:
            categories[cat] = {'total': 0, 'success': 0}
        categories[cat]['total'] += 1
        if result['success']:
            categories[cat]['success'] += 1
    
    for cat, stats in categories.items():
        success_rate = stats['success'] / stats['total'] * 100
        print(f"  {cat.capitalize()}: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
    
    # 結果保存
    results_dir = Path(__file__).parent / "results" / "comprehensive_analysis"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON形式で保存
    with open(results_dir / "lazy_tastar_comprehensive.json", 'w') as f:
        json.dump(test_results, f, indent=2)
    
    print(f"\n📁 Results saved to: {results_dir}")
    print(f"   - lazy_tastar_comprehensive.json")
    
    # 結論と推奨事項
    print(f"\n🎯 Performance Assessment:")
    
    if analysis['performance_grade'] in ['A+', 'A']:
        print(f"✅ EXCELLENT: Lazy TA-A* shows outstanding performance!")
        print(f"   - High success rate ({analysis['success_rate']:.1f}%)")
        print(f"   - Fast computation ({analysis['avg_computation_time']:.3f}s average)")
        print(f"   - Ready for production use")
    elif analysis['performance_grade'] == 'B':
        print(f"✅ GOOD: Lazy TA-A* shows good performance")
        print(f"   - Acceptable success rate ({analysis['success_rate']:.1f}%)")
        print(f"   - Reasonable computation time ({analysis['avg_computation_time']:.3f}s average)")
        print(f"   - Suitable for most applications")
    elif analysis['performance_grade'] == 'C':
        print(f"⚠️  FAIR: Lazy TA-A* shows acceptable performance")
        print(f"   - Moderate success rate ({analysis['success_rate']:.1f}%)")
        print(f"   - Higher computation time ({analysis['avg_computation_time']:.3f}s average)")
        print(f"   - May need optimization for complex scenarios")
    else:
        print(f"❌ POOR: Lazy TA-A* needs significant improvement")
        print(f"   - Low success rate ({analysis['success_rate']:.1f}%)")
        print(f"   - High computation time ({analysis['avg_computation_time']:.3f}s average)")
        print(f"   - Requires algorithm refinement")
    
    print(f"\n💡 Recommendations:")
    if analysis['avg_phase_used'] <= 2.1:
        print(f"   - Most paths complete in Phase 2 (terrain evaluation)")
        print(f"   - Lazy evaluation strategy is effective")
    else:
        print(f"   - Many paths require Phase 3 (terrain-aware replanning)")
        print(f"   - Consider improving Phase 1 terrain estimation")
    
    if analysis['std_computation_time'] > analysis['avg_computation_time'] * 0.5:
        print(f"   - High variance in computation time")
        print(f"   - Consider scenario-specific optimizations")
    
    print(f"\n{'='*70}")
    print("Comprehensive analysis completed!")
    print(f"{'='*70}")

if __name__ == "__main__":
    main()


