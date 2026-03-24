#!/usr/bin/env python3
"""
96シナリオベンチマーク - FieldD*Hybrid用スクリプト

既存の96シナリオ（TA*, AHA*, Theta*）と同じマップを使用してFieldD*Hybridをテスト
"""

import os
import sys
import json
import time
import numpy as np
from pathlib import Path

# パスの設定
ROOT = Path(__file__).parent.parent
SRC_ROOT = ROOT.parent
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Ensure package/module paths are available (same pattern as other runners)
PACKAGE_ROOT = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d'
MODULE_DIR = '/home/hayashi/thesis_work/ros2/ros2_ws/src/path_planner_3d/path_planner_3d'
if PACKAGE_ROOT not in sys.path:
    sys.path.insert(0, PACKAGE_ROOT)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

# インポート
try:
    from path_planner_3d.field_d_star_hybrid import FieldDStarHybrid
    from path_planner_3d.config import PlannerConfig
except ImportError as e:
    print(f"⚠️ インポートエラー: {e}")
    print("代替実装を使用します")
    FieldDStarHybrid = None


def make_cost_map(seed, grid_size):
    """テラインコストマップを生成"""
    np.random.seed(seed)
    base = 0.1 if grid_size <= 100 else (0.12 if grid_size <= 500 else 0.35)
    noise = np.random.normal(0, 0.02, (grid_size, grid_size))
    cmap = np.clip(
        np.ones((grid_size, grid_size), dtype=np.float32) * base + noise, 
        0.0, 1.0
    )
    return cmap


def sample_start_goal(world_size, min_distance, rng):
    """スタート/ゴール地点をサンプリング"""
    while True:
        s = np.array([
            rng.uniform(0.1 * world_size, 0.9 * world_size),
            rng.uniform(0.1 * world_size, 0.9 * world_size),
            0.0
        ])
        g = np.array([
            rng.uniform(0.1 * world_size, 0.9 * world_size),
            rng.uniform(0.1 * world_size, 0.9 * world_size),
            0.0
        ])
        if np.linalg.norm(s - g) >= min_distance:
            return s, g


def generate_96_scenarios():
    """96シナリオを生成（既存ベンチマークと同じ仕様）"""
    specs = [
        ('SMALL', 100, 10.0, 3.0, 30),
        ('MEDIUM', 500, 50.0, 15.0, 48),
        ('LARGE', 1000, 100.0, 30.0, 18),
    ]
    scenarios = []
    rng = np.random.default_rng(12345)  # 同じシード
    
    for name, grid_size, world_size, min_dist, count in specs:
        for i in range(count):
            seed = (hash(f"{name}_{i}") % 100000)
            cmap = make_cost_map(seed, grid_size)
            s, g = sample_start_goal(world_size, min_dist, rng)
            bounds = ((0.0, world_size), (0.0, world_size), (0.0, 2.0))
            
            scenarios.append({
                'id': f'{name}_{i+1}',
                'name': name,
                'start': s.tolist(),
                'goal': g.tolist(),
                'bounds': bounds,
                'terrain_cost_map': cmap,
                'map_size': name,
                'grid_size': grid_size,
                'world_size': world_size,
            })
    
    return scenarios


def run_fieldd_benchmark_96():
    """96シナリオでFieldD*Hybridを実行"""
    
    print("=" * 70)
    print("🔬 96シナリオ FieldD*Hybrid ベンチマーク")
    print("=" * 70)
    
    # シナリオを生成
    print("\n📋 96シナリオを生成中...")
    scenarios = generate_96_scenarios()
    print(f"✅ {len(scenarios)}シナリオを生成")
    
    # 分布確認
    size_counts = {}
    for sc in scenarios:
        size = sc['map_size']
        size_counts[size] = size_counts.get(size, 0) + 1
    
    print("\n📊 シナリオサイズ分布:")
    for size, count in sorted(size_counts.items()):
        print(f"  {size}: {count}シナリオ")
    
    # FieldD*Hybridをインスタンス化
    print("\n⚙️ FieldD*Hybrid を初期化中...")
    
    if FieldDStarHybrid is None:
        print("❌ FieldD*Hybridのインポートに失敗しました")
        return None
    
    results = []
    successful = 0
    failed = 0
    
    print("\n🚀 ベンチマーク実行中...\n")
    start_time = time.time()
    
    for idx, scenario in enumerate(scenarios, 1):
        try:
            scenario_id = scenario['id']
            map_size = scenario['map_size']
            
            # FieldD*Hybridの実行
            planner = FieldDStarHybrid(
                bounds=scenario['bounds'],
                cost_map=scenario['terrain_cost_map'],
                cost_threshold=0.8
            )
            
            # パス計画実行
            plan_start = time.time()
            path, info = planner.plan(
                start=scenario['start'],
                goal=scenario['goal'],
                timeout=30.0
            )
            plan_time = time.time() - plan_start
            
            # 結果判定
            success = (path is not None and len(path) > 0)
            
            if success:
                successful += 1
                path_length = sum(
                    np.linalg.norm(
                        np.array(path[i+1]) - np.array(path[i])
                    )
                    for i in range(len(path) - 1)
                )
            else:
                failed += 1
                path_length = 0
            
            # 結果を保存
            result = {
                'planner': 'FieldD*Hybrid',
                'scenario_id': scenario_id,
                'map_size': map_size,
                'success': success,
                'computation_time': plan_time,
                'path_length_meters': path_length,
                'nodes_explored': info.get('nodes_explored', 0) if info else 0,
                'path_smoothness': info.get('path_smoothness', 0) if info else 0
            }
            results.append(result)
            
            # 進捗表示
            if idx % 10 == 0 or idx == len(scenarios):
                elapsed = time.time() - start_time
                rate = idx / elapsed if elapsed > 0 else 0
                eta = (len(scenarios) - idx) / rate if rate > 0 else 0
                
                status = "✅" if success else "❌"
                print(f"[{idx:3d}/{len(scenarios)}] {status} {scenario_id:15} "
                      f"Time: {plan_time:7.4f}s  "
                      f"({rate:.1f} scenarios/sec, ETA: {eta:.1f}s)")
        
        except Exception as e:
            print(f"❌ エラー: {scenario['id']} - {e}")
            failed += 1
    
    total_time = time.time() - start_time
    
    # 統計情報を計算
    print("\n" + "=" * 70)
    print("📊 結果サマリー")
    print("=" * 70)
    
    times = [r['computation_time'] for r in results]
    print(f"\n✅ 成功: {successful}/{len(results)}")
    print(f"❌ 失敗: {failed}/{len(results)}")
    print(f"⏱️  平均時間: {np.mean(times):.4f}秒")
    print(f"📊 標準偏差: {np.std(times, ddof=1):.4f}秒")
    print(f"📈 中央値: {np.median(times):.4f}秒")
    print(f"⏰ 総実行時間: {total_time:.1f}秒")
    
    # ファイルに保存
    output_dir = ROOT / 'benchmark_results'
    output_dir.mkdir(exist_ok=True)
    
    output_path = output_dir / 'fieldd_hybrid_96_results.json'
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ 結果を保存: {output_path}")
    
    return results


def create_combined_dataset():
    """全手法の96シナリオ結果を統合"""
    
    print("\n" + "=" * 70)
    print("🔄 全手法を統合データセットに結合中...")
    print("=" * 70)
    
    # 既存の統合データを読む
    combined_path = Path('/home/hayashi/thesis_work/benchmark_96_scenarios_combined.json')
    
    if combined_path.exists():
        with open(combined_path, 'r') as f:
            combined = json.load(f)
    else:
        combined = {
            'metadata': {
                'total_scenarios': 96,
                'methods': [],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            },
            'results': {}
        }
    
    # FieldD*Hybrid結果を読む
    fieldd_path = ROOT / 'benchmark_results' / 'fieldd_hybrid_96_results.json'
    
    if fieldd_path.exists():
        with open(fieldd_path, 'r') as f:
            fieldd_results = json.load(f)
        
        # 各シナリオの結果に FieldD*Hybrid を追加
        for result in fieldd_results:
            scenario_id = result['scenario_id']
            
            # シナリオがまだなければ作成
            if scenario_id not in combined['results']:
                combined['results'][scenario_id] = {
                    'scenario': {'scenario_id': scenario_id},
                    'results': {}
                }
            
            # FieldD*Hybridの結果を追加
            combined['results'][scenario_id]['results']['FieldD*Hybrid'] = {
                'success': result['success'],
                'computation_time': result['computation_time'],
                'path_length': result.get('path_length_meters', 0),
                'nodes_explored': result.get('nodes_explored', 0),
                'path_smoothness': result.get('path_smoothness', 0)
            }
        
        # メタデータを更新
        if 'FieldD*Hybrid' not in combined['metadata']['methods']:
            combined['metadata']['methods'].append('FieldD*Hybrid')
        
        # 保存
        with open(combined_path, 'w') as f:
            json.dump(combined, f, indent=2)
        
        print(f"✅ 統合完了: {combined_path}")
        print(f"📋 手法数: {len(combined['metadata']['methods'])}")
        print(f"📊 シナリオ数: {len(combined['results'])}")
        
        return combined
    else:
        print("❌ FieldD*Hybrid結果が見つかりません")
        return None


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("🔬 FieldD*Hybrid 96シナリオベンチマーク")
    print("=" * 70 + "\n")
    
    # FieldD*Hybridベンチマークを実行
    results = run_fieldd_benchmark_96()
    
    if results:
        # 統合データセットを作成
        combined = create_combined_dataset()
        
        print("\n" + "=" * 70)
        print("✅ ベンチマーク完了")
        print("=" * 70)
    else:
        print("\n❌ ベンチマーク実行に失敗しました")
