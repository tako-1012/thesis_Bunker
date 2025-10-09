#!/usr/bin/env python3
"""
VoxelGridProcessorのテストスクリプト
"""
import sys
import time
import open3d as o3d
import numpy as np

# 相対importを試みる
try:
    from voxel_grid_processor import VoxelGridProcessor
except ImportError:
    # パスを追加して再試行
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from voxel_grid_processor import VoxelGridProcessor


def create_test_data():
    """テスト用の点群データを生成"""
    print("  テストデータ生成中...")
    
    # 地面（平面）
    ground = o3d.geometry.TriangleMesh.create_box(width=5.0, height=0.1, depth=5.0)
    ground.translate([-2.5, -0.05, -2.5])
    ground_pcd = ground.sample_points_uniformly(number_of_points=500)
    
    # 障害物（球体）
    obstacle = o3d.geometry.TriangleMesh.create_sphere(radius=0.5)
    obstacle.translate([1.0, 0.5, 1.0])
    obstacle_pcd = obstacle.sample_points_uniformly(number_of_points=300)
    
    # 結合
    combined = ground_pcd + obstacle_pcd
    
    print(f"    地面点数: {len(ground_pcd.points)}")
    print(f"    障害物点数: {len(obstacle_pcd.points)}")
    print(f"    総点数: {len(combined.points)}")
    
    return combined, ground_pcd, obstacle_pcd


def test_basic_processing():
    """Phase 1: 基本処理のテスト"""
    print("=" * 60)
    print("Test 1: 基本処理（Phase 1）")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, _, _ = create_test_data()
        
        # プロセッサ初期化
        print("\n2. VoxelGridProcessor初期化...")
        processor = VoxelGridProcessor(voxel_size=0.2)
        print(f"   ボクセルサイズ: {processor.voxel_size}m")
        
        # 処理実行
        print("\n3. 点群処理...")
        start_time = time.time()
        result = processor.process_pointcloud(pcd)
        elapsed = time.time() - start_time
        
        print(f"   処理時間: {elapsed:.3f}秒")
        print(f"   ボクセル数: {result['num_voxels']}")
        print(f"   境界: {result['bounds']}")
        
        # ボクセル中心取得
        print("\n4. ボクセル中心座標取得...")
        centers = processor.get_voxel_centers(result['voxel_grid'])
        print(f"   中心点数: {len(centers)}")
        print(f"   中心座標範囲: X[{centers[:, 0].min():.2f}, {centers[:, 0].max():.2f}], "
              f"Y[{centers[:, 1].min():.2f}, {centers[:, 1].max():.2f}], "
              f"Z[{centers[:, 2].min():.2f}, {centers[:, 2].max():.2f}]")
        
        print("\n✅ Phase 1テスト完了\n")
        return processor, pcd, result
        
    except Exception as e:
        print(f"\n❌ Phase 1テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return None, None, None


def test_ground_detection():
    """Phase 2: 地面検出のテスト"""
    print("=" * 60)
    print("Test 2: 地面検出（Phase 2）")
    print("=" * 60)
    
    try:
        # データ生成
        print("\n1. テストデータ生成...")
        pcd, ground_pcd, obstacle_pcd = create_test_data()
        
        # プロセッサ初期化
        print("\n2. VoxelGridProcessor初期化...")
        processor = VoxelGridProcessor(voxel_size=0.2)
        
        # 法線計算
        print("\n3. 法線ベクトル計算...")
        start_time = time.time()
        processor._calculate_normals(pcd)
        elapsed = time.time() - start_time
        print(f"   計算時間: {elapsed:.3f}秒")
        print(f"   法線計算完了: {pcd.has_normals()}")
        
        # 地面検出
        print("\n4. 地面点検出...")
        start_time = time.time()
        ground_indices = processor.detect_ground_voxels(pcd)
        elapsed = time.time() - start_time
        
        print(f"   検出時間: {elapsed:.3f}秒")
        print(f"   検出された地面点: {len(ground_indices)}")
        print(f"   地面点割合: {len(ground_indices)/len(pcd.points)*100:.1f}%")
        
        # ボクセル分類
        print("\n5. ボクセル分類...")
        result = processor.process_pointcloud(pcd)
        classification = processor.classify_voxels(pcd, result['voxel_grid'])
        
        print(f"   総ボクセル数: {len(result['voxel_grid'].get_voxels())}")
        print(f"   地面ボクセル: {len(classification['ground_indices'])}")
        print(f"   障害物ボクセル: {len(classification['obstacle_indices'])}")
        print(f"   地面割合: {classification['ground_ratio']*100:.1f}%")
        
        print("\n✅ Phase 2テスト完了\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Phase 2テスト失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト"""
    print("\n" + "=" * 60)
    print("VoxelGridProcessor 統合テスト")
    print("=" * 60 + "\n")
    
    success_count = 0
    total_tests = 2
    
    try:
        # Phase 1テスト
        processor, pcd, result = test_basic_processing()
        if processor is not None:
            success_count += 1
        
        # Phase 2テスト
        if test_ground_detection():
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
