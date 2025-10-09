#!/usr/bin/env python3
"""
SlopeCalculatorのテストスクリプト
"""
import sys
import time
import open3d as o3d
import numpy as np

# 相対importを試みる
try:
    from slope_calculator import SlopeCalculator
except ImportError:
    # パスを追加して再試行
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from slope_calculator import SlopeCalculator


def create_test_data():
    """テスト用の点群データを生成"""
    print("  テストデータ生成中...")
    
    # 地面（平面）
    ground = o3d.geometry.TriangleMesh.create_box(width=5.0, height=0.1, depth=5.0)
    ground.translate([-2.5, -0.05, -2.5])
    ground_pcd = ground.sample_points_uniformly(number_of_points=500)
    
    # 傾斜した地面（20度の傾斜）
    slope_mesh = o3d.geometry.TriangleMesh.create_box(width=3.0, height=0.1, depth=2.0)
    slope_mesh.translate([1.0, -0.05, 0.0])
    # 20度回転
    rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(np.radians(20)), -np.sin(np.radians(20))],
        [0, np.sin(np.radians(20)), np.cos(np.radians(20))]
    ])
    slope_mesh.rotate(rotation_matrix, center=[1.0, 0, 0])
    slope_pcd = slope_mesh.sample_points_uniformly(number_of_points=300)
    
    # 急傾斜地面（35度の傾斜）
    steep_mesh = o3d.geometry.TriangleMesh.create_box(width=2.0, height=0.1, depth=1.5)
    steep_mesh.translate([-1.0, -0.05, 1.5])
    # 35度回転
    rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(np.radians(35)), -np.sin(np.radians(35))],
        [0, np.sin(np.radians(35)), np.cos(np.radians(35))]
    ])
    steep_mesh.rotate(rotation_matrix, center=[-1.0, 0, 1.5])
    steep_pcd = steep_mesh.sample_points_uniformly(number_of_points=200)
    
    # 結合
    combined = ground_pcd + slope_pcd + steep_pcd
    
    # 法線計算
    combined.estimate_normals()
    combined.orient_normals_towards_camera_location()
    
    print(f"    平坦地面点数: {len(ground_pcd.points)}")
    print(f"    緩傾斜点数: {len(slope_pcd.points)}")
    print(f"    急傾斜点数: {len(steep_pcd.points)}")
    print(f"    総点数: {len(combined.points)}")
    
    return combined, ground_pcd, slope_pcd, steep_pcd


def test_slope_calculation():
    """傾斜角度計算のテスト"""
    print("=" * 60)
    print("Test 1: 傾斜角度計算")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, ground_pcd, slope_pcd, steep_pcd = create_test_data()
        
        # SlopeCalculator初期化
        print("\n2. SlopeCalculator初期化...")
        calculator = SlopeCalculator(
            robot_width=0.6,
            robot_length=0.8,
            max_safe_slope=25.0
        )
        print(f"   ロボットサイズ: {calculator.robot_width}m × {calculator.robot_length}m")
        print(f"   最大安全傾斜: {calculator.max_safe_slope}°")
        
        # 全点を地面点として処理
        ground_indices = np.arange(len(pcd.points))
        
        # 傾斜角度計算
        print("\n3. 傾斜角度計算...")
        start_time = time.time()
        slope_angles = calculator.calculate_slope_angles(pcd, ground_indices)
        elapsed = time.time() - start_time
        
        print(f"   計算時間: {elapsed:.3f}秒")
        print(f"   平均傾斜: {np.mean(slope_angles):.1f}°")
        print(f"   最大傾斜: {np.max(slope_angles):.1f}°")
        print(f"   最小傾斜: {np.min(slope_angles):.1f}°")
        print(f"   標準偏差: {np.std(slope_angles):.1f}°")
        
        print("\n✅ 傾斜角度計算テスト完了\n")
        return calculator, pcd, ground_indices, slope_angles
        
    except Exception as e:
        print(f"\n❌ 傾斜角度計算テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None, None


def test_risk_assessment():
    """転倒リスク評価のテスト"""
    print("=" * 60)
    print("Test 2: 転倒リスク評価")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, _, _, _ = create_test_data()
        ground_indices = np.arange(len(pcd.points))
        
        # SlopeCalculator初期化
        print("\n2. SlopeCalculator初期化...")
        calculator = SlopeCalculator(
            robot_width=0.6,
            robot_length=0.8,
            max_safe_slope=25.0
        )
        
        # 傾斜角度計算
        slope_angles = calculator.calculate_slope_angles(pcd, ground_indices)
        
        # 転倒リスク計算
        print("\n3. 転倒リスク計算...")
        start_time = time.time()
        risk_scores = calculator.calculate_stability_risk(pcd, ground_indices, slope_angles)
        elapsed = time.time() - start_time
        
        print(f"   計算時間: {elapsed:.3f}秒")
        print(f"   平均リスク: {np.mean(risk_scores):.3f}")
        print(f"   最大リスク: {np.max(risk_scores):.3f}")
        print(f"   最小リスク: {np.min(risk_scores):.3f}")
        print(f"   標準偏差: {np.std(risk_scores):.3f}")
        
        # リスクレベル別の統計
        low_risk = np.sum(risk_scores < 0.3)
        medium_risk = np.sum((risk_scores >= 0.3) & (risk_scores < 0.7))
        high_risk = np.sum(risk_scores >= 0.7)
        
        print(f"   低リスク(<0.3): {low_risk}点 ({low_risk/len(risk_scores)*100:.1f}%)")
        print(f"   中リスク(0.3-0.7): {medium_risk}点 ({medium_risk/len(risk_scores)*100:.1f}%)")
        print(f"   高リスク(≥0.7): {high_risk}点 ({high_risk/len(risk_scores)*100:.1f}%)")
        
        print("\n✅ 転倒リスク評価テスト完了\n")
        return risk_scores
        
    except Exception as e:
        print(f"\n❌ 転倒リスク評価テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_traversability():
    """走行コスト計算のテスト"""
    print("=" * 60)
    print("Test 3: 走行コスト計算")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, _, _, _ = create_test_data()
        ground_indices = np.arange(len(pcd.points))
        
        # SlopeCalculator初期化
        print("\n2. SlopeCalculator初期化...")
        calculator = SlopeCalculator(
            robot_width=0.6,
            robot_length=0.8,
            max_safe_slope=25.0
        )
        
        # 傾斜角度とリスク計算
        slope_angles = calculator.calculate_slope_angles(pcd, ground_indices)
        risk_scores = calculator.calculate_stability_risk(pcd, ground_indices, slope_angles)
        
        # 走行コスト計算
        print("\n3. 走行コスト計算...")
        start_time = time.time()
        costs = calculator.get_traversability_cost(slope_angles, risk_scores)
        elapsed = time.time() - start_time
        
        print(f"   計算時間: {elapsed:.3f}秒")
        
        # 安全な点のみの統計
        safe_costs = costs[costs != np.inf]
        unsafe_count = np.sum(costs == np.inf)
        
        print(f"   平均コスト: {np.mean(safe_costs):.2f}")
        print(f"   最大コスト: {np.max(safe_costs):.2f}")
        print(f"   最小コスト: {np.min(safe_costs):.2f}")
        print(f"   標準偏差: {np.std(safe_costs):.2f}")
        print(f"   走行不可点: {unsafe_count}")
        print(f"   走行不可率: {unsafe_count/len(costs)*100:.1f}%")
        
        # コストレベル別の統計
        low_cost = np.sum((safe_costs >= 1.0) & (safe_costs < 2.0))
        medium_cost = np.sum((safe_costs >= 2.0) & (safe_costs < 5.0))
        high_cost = np.sum(safe_costs >= 5.0)
        
        print(f"   低コスト(1-2): {low_cost}点 ({low_cost/len(safe_costs)*100:.1f}%)")
        print(f"   中コスト(2-5): {medium_cost}点 ({medium_cost/len(safe_costs)*100:.1f}%)")
        print(f"   高コスト(≥5): {high_cost}点 ({high_cost/len(safe_costs)*100:.1f}%)")
        
        print("\n✅ 走行コスト計算テスト完了\n")
        return costs
        
    except Exception as e:
        print(f"\n❌ 走行コスト計算テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_terrain_analysis():
    """地形の総合分析テスト"""
    print("=" * 60)
    print("Test 4: 地形総合分析")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, _, _, _ = create_test_data()
        ground_indices = np.arange(len(pcd.points))
        
        # SlopeCalculator初期化
        print("\n2. SlopeCalculator初期化...")
        calculator = SlopeCalculator(
            robot_width=0.6,
            robot_length=0.8,
            max_safe_slope=25.0
        )
        
        # 総合分析
        print("\n3. 地形総合分析...")
        start_time = time.time()
        analysis = calculator.analyze_terrain(pcd, ground_indices)
        elapsed = time.time() - start_time
        
        print(f"   分析時間: {elapsed:.3f}秒")
        
        # 結果表示
        stats = analysis['statistics']
        print(f"\n4. 分析結果:")
        print(f"   平均傾斜: {stats['avg_slope']:.1f}°")
        print(f"   最大傾斜: {stats['max_slope']:.1f}°")
        print(f"   最小傾斜: {stats['min_slope']:.1f}°")
        print(f"   平均リスク: {stats['avg_risk']:.3f}")
        print(f"   最大リスク: {stats['max_risk']:.3f}")
        print(f"   平均コスト: {stats['avg_cost']:.2f}")
        print(f"   走行不可率: {stats['unsafe_ratio']*100:.1f}%")
        print(f"   総点数: {stats['total_points']}")
        
        # 傾斜分類
        classification = analysis['slope_classification']
        print(f"\n5. 傾斜分類:")
        print(f"   平坦(0-10°): {len(classification['flat'])}点 ({len(classification['flat'])/stats['total_points']*100:.1f}%)")
        print(f"   緩傾斜(10-20°): {len(classification['gentle'])}点 ({len(classification['gentle'])/stats['total_points']*100:.1f}%)")
        print(f"   中傾斜(20-30°): {len(classification['moderate'])}点 ({len(classification['moderate'])/stats['total_points']*100:.1f}%)")
        print(f"   急傾斜(30°+): {len(classification['steep'])}点 ({len(classification['steep'])/stats['total_points']*100:.1f}%)")
        
        print("\n✅ 地形総合分析テスト完了\n")
        return analysis
        
    except Exception as e:
        print(f"\n❌ 地形総合分析テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """メインテスト"""
    print("\n" + "=" * 60)
    print("SlopeCalculator 統合テスト")
    print("=" * 60 + "\n")
    
    success_count = 0
    total_tests = 4
    
    try:
        # Test 1: 傾斜角度計算
        calculator, pcd, ground_indices, slope_angles = test_slope_calculation()
        if calculator is not None:
            success_count += 1
        
        # Test 2: 転倒リスク評価
        if test_risk_assessment() is not None:
            success_count += 1
        
        # Test 3: 走行コスト計算
        if test_traversability() is not None:
            success_count += 1
        
        # Test 4: 地形総合分析
        if test_terrain_analysis() is not None:
            success_count += 1
        
        print("=" * 60)
        print(f"テスト結果: {success_count}/{total_tests} 成功")
        if success_count == total_tests:
            print("✅ 全テスト完了")
        else:
            print("❌ 一部テストが失敗しました")
        print("=" * 60)
        
        return 0 if success_count == total_tests else 1
        
    except Exception as e:
        print(f"\n❌ 予期しないエラー発生: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
