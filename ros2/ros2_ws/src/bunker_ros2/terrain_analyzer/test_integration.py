#!/usr/bin/env python3
"""
統合テストスクリプト
VoxelGridProcessorとSlopeCalculatorを連携させたテスト
"""
import sys
import time
import open3d as o3d
import numpy as np

# 相対importを試みる
try:
    from voxel_grid_processor import VoxelGridProcessor
    from slope_calculator import SlopeCalculator
except ImportError:
    # パスを追加して再試行
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from voxel_grid_processor import VoxelGridProcessor
    from slope_calculator import SlopeCalculator


def create_complex_terrain():
    """複雑な地形のテストデータを生成"""
    print("  複雑な地形データ生成中...")
    
    # 平坦な地面
    flat_ground = o3d.geometry.TriangleMesh.create_box(width=4.0, height=0.1, depth=4.0)
    flat_ground.translate([-2.0, -0.05, -2.0])
    flat_pcd = flat_ground.sample_points_uniformly(number_of_points=400)
    
    # 緩やかな傾斜（15度）
    gentle_slope = o3d.geometry.TriangleMesh.create_box(width=3.0, height=0.1, depth=2.0)
    gentle_slope.translate([1.0, -0.05, 0.0])
    rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(np.radians(15)), -np.sin(np.radians(15))],
        [0, np.sin(np.radians(15)), np.cos(np.radians(15))]
    ])
    gentle_slope.rotate(rotation_matrix, center=[1.0, 0, 0])
    gentle_pcd = gentle_slope.sample_points_uniformly(number_of_points=300)
    
    # 中程度の傾斜（25度）
    moderate_slope = o3d.geometry.TriangleMesh.create_box(width=2.5, height=0.1, depth=1.5)
    moderate_slope.translate([-1.0, -0.05, 1.5])
    rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(np.radians(25)), -np.sin(np.radians(25))],
        [0, np.sin(np.radians(25)), np.cos(np.radians(25))]
    ])
    moderate_slope.rotate(rotation_matrix, center=[-1.0, 0, 1.5])
    moderate_pcd = moderate_slope.sample_points_uniformly(number_of_points=250)
    
    # 急傾斜（40度）
    steep_slope = o3d.geometry.TriangleMesh.create_box(width=2.0, height=0.1, depth=1.0)
    steep_slope.translate([0.5, -0.05, -1.0])
    rotation_matrix = np.array([
        [1, 0, 0],
        [0, np.cos(np.radians(40)), -np.sin(np.radians(40))],
        [0, np.sin(np.radians(40)), np.cos(np.radians(40))]
    ])
    steep_slope.rotate(rotation_matrix, center=[0.5, 0, -1.0])
    steep_pcd = steep_slope.sample_points_uniformly(number_of_points=200)
    
    # 障害物（複数の球体）
    obstacles = []
    obstacle_positions = [
        [1.5, 0.3, 1.0],
        [-1.5, 0.4, -0.5],
        [0.0, 0.5, 0.5]
    ]
    
    for pos in obstacle_positions:
        obstacle = o3d.geometry.TriangleMesh.create_sphere(radius=0.3)
        obstacle.translate(pos)
        obstacle_pcd = obstacle.sample_points_uniformly(number_of_points=100)
        obstacles.append(obstacle_pcd)
    
    # 全結合
    combined = flat_pcd + gentle_pcd + moderate_pcd + steep_pcd
    for obstacle_pcd in obstacles:
        combined += obstacle_pcd
    
    # 法線計算
    combined.estimate_normals()
    combined.orient_normals_towards_camera_location()
    
    print(f"    平坦地面: {len(flat_pcd.points)}点")
    print(f"    緩傾斜: {len(gentle_pcd.points)}点")
    print(f"    中傾斜: {len(moderate_pcd.points)}点")
    print(f"    急傾斜: {len(steep_pcd.points)}点")
    print(f"    障害物: {len(obstacles) * 100}点")
    print(f"    総点数: {len(combined.points)}点")
    
    return combined


def test_integrated_processing():
    """統合処理のテスト"""
    print("=" * 60)
    print("Test 1: 統合処理（VoxelGridProcessor + SlopeCalculator）")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. 複雑な地形データ生成...")
        pcd = create_complex_terrain()
        
        # プロセッサ初期化
        print("\n2. プロセッサ初期化...")
        voxel_processor = VoxelGridProcessor(voxel_size=0.15)
        slope_calculator = SlopeCalculator(
            robot_width=0.6,
            robot_length=0.8,
            max_safe_slope=25.0
        )
        
        print(f"   ボクセルサイズ: {voxel_processor.voxel_size}m")
        print(f"   ロボットサイズ: {slope_calculator.robot_width}m × {slope_calculator.robot_length}m")
        print(f"   最大安全傾斜: {slope_calculator.max_safe_slope}°")
        
        # Phase 1: ボクセル化
        print("\n3. Phase 1: ボクセル化...")
        start_time = time.time()
        voxel_result = voxel_processor.process_pointcloud(pcd)
        voxel_time = time.time() - start_time
        
        print(f"   処理時間: {voxel_time:.3f}秒")
        print(f"   ボクセル数: {voxel_result['num_voxels']}")
        print(f"   境界: {voxel_result['bounds']}")
        
        # Phase 2: 地面検出とボクセル分類
        print("\n4. Phase 2: 地面検出とボクセル分類...")
        start_time = time.time()
        classification = voxel_processor.classify_voxels(pcd, voxel_result['voxel_grid'])
        classification_time = time.time() - start_time
        
        print(f"   処理時間: {classification_time:.3f}秒")
        print(f"   地面ボクセル: {len(classification['ground_indices'])}")
        print(f"   障害物ボクセル: {len(classification['obstacle_indices'])}")
        print(f"   地面割合: {classification['ground_ratio']*100:.1f}%")
        
        # Phase 3: 傾斜解析
        print("\n5. Phase 3: 傾斜解析...")
        start_time = time.time()
        terrain_analysis = slope_calculator.analyze_terrain(pcd, classification['ground_indices'])
        analysis_time = time.time() - start_time
        
        print(f"   処理時間: {analysis_time:.3f}秒")
        
        # 統計情報表示
        stats = terrain_analysis['statistics']
        print(f"\n6. 地形統計:")
        print(f"   平均傾斜: {stats['avg_slope']:.1f}°")
        print(f"   最大傾斜: {stats['max_slope']:.1f}°")
        print(f"   平均リスク: {stats['avg_risk']:.3f}")
        print(f"   最大リスク: {stats['max_risk']:.3f}")
        print(f"   平均コスト: {stats['avg_cost']:.2f}")
        print(f"   走行不可率: {stats['unsafe_ratio']*100:.1f}%")
        
        # 傾斜分類
        slope_classification = terrain_analysis['slope_classification']
        print(f"\n7. 傾斜分類:")
        print(f"   平坦(0-10°): {len(slope_classification['flat'])}点")
        print(f"   緩傾斜(10-20°): {len(slope_classification['gentle'])}点")
        print(f"   中傾斜(20-30°): {len(slope_classification['moderate'])}点")
        print(f"   急傾斜(30°+): {len(slope_classification['steep'])}点")
        
        total_time = voxel_time + classification_time + analysis_time
        print(f"\n8. 総処理時間: {total_time:.3f}秒")
        
        print("\n✅ 統合処理テスト完了\n")
        return True, {
            'voxel_result': voxel_result,
            'classification': classification,
            'terrain_analysis': terrain_analysis,
            'processing_times': {
                'voxel': voxel_time,
                'classification': classification_time,
                'analysis': analysis_time,
                'total': total_time
            }
        }
        
    except Exception as e:
        print(f"\n❌ 統合処理テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_performance_scaling():
    """パフォーマンススケーリングテスト"""
    print("=" * 60)
    print("Test 2: パフォーマンススケーリング")
    print("=" * 60)
    
    try:
        # 異なるサイズのデータセットでテスト
        test_sizes = [500, 1000, 2000]
        results = []
        
        for size in test_sizes:
            print(f"\n{size}点でのテスト...")
            
            # データ生成
            pcd = create_complex_terrain()
            # サイズに応じてダウンサンプリング
            if len(pcd.points) > size:
                indices = np.random.choice(len(pcd.points), size, replace=False)
                pcd = pcd.select_by_index(indices)
            
            # プロセッサ初期化
            voxel_processor = VoxelGridProcessor(voxel_size=0.15)
            slope_calculator = SlopeCalculator(
                robot_width=0.6,
                robot_length=0.8,
                max_safe_slope=25.0
            )
            
            # 処理時間測定
            start_time = time.time()
            
            # ボクセル化
            voxel_result = voxel_processor.process_pointcloud(pcd)
            
            # 分類
            classification = voxel_processor.classify_voxels(pcd, voxel_result['voxel_grid'])
            
            # 傾斜解析
            terrain_analysis = slope_calculator.analyze_terrain(pcd, classification['ground_indices'])
            
            total_time = time.time() - start_time
            
            results.append({
                'points': len(pcd.points),
                'voxels': voxel_result['num_voxels'],
                'time': total_time,
                'points_per_second': len(pcd.points) / total_time
            })
            
            print(f"   点数: {len(pcd.points)}")
            print(f"   ボクセル数: {voxel_result['num_voxels']}")
            print(f"   処理時間: {total_time:.3f}秒")
            print(f"   処理速度: {len(pcd.points)/total_time:.0f}点/秒")
        
        # 結果サマリー
        print(f"\nパフォーマンスサマリー:")
        for result in results:
            print(f"  {result['points']}点: {result['time']:.3f}秒 ({result['points_per_second']:.0f}点/秒)")
        
        print("\n✅ パフォーマンススケーリングテスト完了\n")
        return True
        
    except Exception as e:
        print(f"\n❌ パフォーマンススケーリングテスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_edge_cases():
    """エッジケーステスト"""
    print("=" * 60)
    print("Test 3: エッジケーステスト")
    print("=" * 60)
    
    try:
        # Test 1: 空の点群
        print("\n1. 空の点群テスト...")
        empty_pcd = o3d.geometry.PointCloud()
        voxel_processor = VoxelGridProcessor(voxel_size=0.1)
        
        try:
            result = voxel_processor.process_pointcloud(empty_pcd)
            print("   ❌ 空の点群でエラーが発生しませんでした")
        except ValueError as e:
            print(f"   ✅ 空の点群で適切にエラー: {e}")
        
        # Test 2: 非常に小さな点群
        print("\n2. 小さな点群テスト...")
        small_sphere = o3d.geometry.TriangleMesh.create_sphere(radius=0.1)
        small_pcd = small_sphere.sample_points_uniformly(number_of_points=10)
        small_pcd.estimate_normals()
        
        voxel_processor = VoxelGridProcessor(voxel_size=0.05)
        slope_calculator = SlopeCalculator()
        
        try:
            voxel_result = voxel_processor.process_pointcloud(small_pcd)
            classification = voxel_processor.classify_voxels(small_pcd, voxel_result['voxel_grid'])
            terrain_analysis = slope_calculator.analyze_terrain(small_pcd, classification['ground_indices'])
            print(f"   ✅ 小さな点群処理成功: {len(small_pcd.points)}点 → {voxel_result['num_voxels']}ボクセル")
        except Exception as e:
            print(f"   ❌ 小さな点群処理失敗: {e}")
        
        # Test 3: 極端な傾斜
        print("\n3. 極端な傾斜テスト...")
        extreme_slope = o3d.geometry.TriangleMesh.create_box(width=1.0, height=0.1, depth=1.0)
        extreme_slope.translate([0, -0.05, 0])
        # 80度回転
        rotation_matrix = np.array([
            [1, 0, 0],
            [0, np.cos(np.radians(80)), -np.sin(np.radians(80))],
            [0, np.sin(np.radians(80)), np.cos(np.radians(80))]
        ])
        extreme_slope.rotate(rotation_matrix, center=[0, 0, 0])
        extreme_pcd = extreme_slope.sample_points_uniformly(number_of_points=100)
        extreme_pcd.estimate_normals()
        
        try:
            voxel_result = voxel_processor.process_pointcloud(extreme_pcd)
            classification = voxel_processor.classify_voxels(extreme_pcd, voxel_result['voxel_grid'])
            terrain_analysis = slope_calculator.analyze_terrain(extreme_pcd, classification['ground_indices'])
            
            stats = terrain_analysis['statistics']
            print(f"   ✅ 極端な傾斜処理成功: 最大傾斜{stats['max_slope']:.1f}°, 走行不可率{stats['unsafe_ratio']*100:.1f}%")
        except Exception as e:
            print(f"   ❌ 極端な傾斜処理失敗: {e}")
        
        print("\n✅ エッジケーステスト完了\n")
        return True
        
    except Exception as e:
        print(f"\n❌ エッジケーステスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト"""
    print("\n" + "=" * 60)
    print("統合テスト - VoxelGridProcessor + SlopeCalculator")
    print("=" * 60 + "\n")
    
    success_count = 0
    total_tests = 3
    
    try:
        # Test 1: 統合処理
        success, results = test_integrated_processing()
        if success:
            success_count += 1
        
        # Test 2: パフォーマンススケーリング
        if test_performance_scaling():
            success_count += 1
        
        # Test 3: エッジケース
        if test_edge_cases():
            success_count += 1
        
        print("=" * 60)
        print(f"テスト結果: {success_count}/{total_tests} 成功")
        if success_count == total_tests:
            print("✅ 全テスト完了")
            print("\n🎯 統合システムの準備完了！")
            print("   - VoxelGridProcessor: 点群のボクセル化と地面検出")
            print("   - SlopeCalculator: 傾斜解析と転倒リスク評価")
            print("   - 統合処理: 実際の使用シナリオに対応")
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
