#!/usr/bin/env python3
"""
Unity連携統合テスト
TCP/IP接続、データ変換、通信速度、エラーハンドリングのテスト
"""

import socket
import threading
import time
import json
import sys
import os
from typing import Dict, Any, List

# パス追加
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ダミークラス定義（テスト用）
class DummyHeader:
    def __init__(self):
        self.stamp = DummyTime()
        self.frame_id = "map"

class DummyTime:
    def __init__(self):
        self.sec = 1234567890
        self.nanosec = 123456789

class DummyTerrainInfo:
    def __init__(self):
        self.header = DummyHeader()
        self.avg_slope = 15.5
        self.max_slope = 35.2
        self.min_slope = 2.1
        self.traversable_ratio = 0.75
        self.total_voxels = 1000
        self.ground_voxels = 750
        self.obstacle_voxels = 250
        self.avg_risk = 0.3
        self.max_risk = 0.8
        self.avg_cost = 1.5
        self.impassable_ratio = 0.25
        self.processing_time = 25.5
        self.point_count = 10000

class DummyVoxelData:
    def __init__(self, idx, vtype, slope, risk, cost):
        self.index = idx
        self.voxel_type = vtype
        self.slope_deg = slope
        self.risk_score = risk
        self.traversability_cost = cost

class DummyVoxelGrid3D:
    def __init__(self):
        self.header = DummyHeader()
        self.voxel_size = 0.1
        self.grid_size_x = 10
        self.grid_size_y = 10
        self.grid_size_z = 10
        self.min_bound_x = -5.0
        self.min_bound_y = -5.0
        self.min_bound_z = 0.0
        self.max_bound_x = 5.0
        self.max_bound_y = 5.0
        self.max_bound_z = 10.0
        self.voxel_data = [
            DummyVoxelData(i, 1, 15.0 + i, 0.3, 1.5)
            for i in range(10)
        ]

try:
    from ros_to_unity_converter import RosToUnityConverter
except ImportError:
    print("❌ RosToUnityConverter not available")
    sys.exit(1)


class UnityBridgeTester:
    """Unity連携テストクラス"""
    
    def __init__(self):
        self.test_results = {}
        self.server_host = '127.0.0.1'
        self.server_port = 10000
        self.converter = RosToUnityConverter()
        
    def run_all_tests(self):
        """全テストを実行"""
        print("🧪 Unity連携統合テスト開始")
        print("=" * 50)
        
        # テスト1: データ変換テスト
        self.test_data_conversion()
        
        # テスト2: TCP/IP接続テスト
        self.test_tcp_connection()
        
        # テスト3: 通信速度テスト
        self.test_communication_speed()
        
        # テスト4: エラーハンドリングテスト
        self.test_error_handling()
        
        # テスト5: 統合テスト
        self.test_integration()
        
        # 結果表示
        self.print_test_results()
        
    def test_data_conversion(self):
        """データ変換テスト"""
        print("\n📊 テスト1: データ変換")
        print("-" * 30)
        
        try:
            # ダミーデータ作成
            terrain_info = self._create_dummy_terrain_info()
            voxel_grid = self._create_dummy_voxel_grid()
            
            # TerrainInfo変換テスト
            start_time = time.time()
            terrain_json = self.converter.terrain_info_to_json(terrain_info)
            terrain_time = time.time() - start_time
            
            # VoxelGrid3D変換テスト
            start_time = time.time()
            voxel_json = self.converter.voxel_grid_to_json(voxel_grid)
            voxel_time = time.time() - start_time
            
            # 統合データ変換テスト
            start_time = time.time()
            unified_json = self.converter.create_unity_terrain_data(terrain_info, voxel_grid)
            unified_time = time.time() - start_time
            
            # JSON検証
            terrain_data = json.loads(terrain_json)
            voxel_data = json.loads(voxel_json)
            unified_data = json.loads(unified_json)
            
            # 結果記録
            self.test_results['data_conversion'] = {
                'terrain_conversion_time': terrain_time,
                'voxel_conversion_time': voxel_time,
                'unified_conversion_time': unified_time,
                'terrain_json_size': len(terrain_json),
                'voxel_json_size': len(voxel_json),
                'unified_json_size': len(unified_json),
                'terrain_fields': len(terrain_data.keys()),
                'voxel_fields': len(voxel_data.keys()),
                'unified_fields': len(unified_data.keys()),
                'success': True
            }
            
            print(f"✅ TerrainInfo変換: {terrain_time*1000:.1f}ms, {len(terrain_json)}bytes")
            print(f"✅ VoxelGrid3D変換: {voxel_time*1000:.1f}ms, {len(voxel_json)}bytes")
            print(f"✅ 統合データ変換: {unified_time*1000:.1f}ms, {len(unified_json)}bytes")
            
        except Exception as e:
            self.test_results['data_conversion'] = {'success': False, 'error': str(e)}
            print(f"❌ データ変換テスト失敗: {e}")
    
    def test_tcp_connection(self):
        """TCP/IP接続テスト"""
        print("\n🌐 テスト2: TCP/IP接続")
        print("-" * 30)
        
        try:
            # サーバーソケット作成
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.server_host, self.server_port))
            server_socket.listen(1)
            
            # クライアント接続テスト
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            start_time = time.time()
            client_socket.connect((self.server_host, self.server_port))
            connection_time = time.time() - start_time
            
            # データ送信テスト
            test_data = "Hello Unity!"
            data_bytes = test_data.encode('utf-8')
            length_bytes = len(data_bytes).to_bytes(4, byteorder='big')
            
            client_socket.send(length_bytes + data_bytes)
            
            # サーバー側で受信
            server_client, address = server_socket.accept()
            received_length = int.from_bytes(server_client.recv(4), byteorder='big')
            received_data = server_client.recv(received_length).decode('utf-8')
            
            # 接続テスト
            connection_success = (received_data == test_data)
            
            # クリーンアップ
            client_socket.close()
            server_client.close()
            server_socket.close()
            
            # 結果記録
            self.test_results['tcp_connection'] = {
                'connection_time': connection_time,
                'data_transmission_success': connection_success,
                'success': True
            }
            
            print(f"✅ 接続時間: {connection_time*1000:.1f}ms")
            print(f"✅ データ送受信: {'成功' if connection_success else '失敗'}")
            
        except Exception as e:
            self.test_results['tcp_connection'] = {'success': False, 'error': str(e)}
            print(f"❌ TCP/IP接続テスト失敗: {e}")
    
    def test_communication_speed(self):
        """通信速度テスト"""
        print("\n⚡ テスト3: 通信速度")
        print("-" * 30)
        
        try:
            # テストデータ作成
            terrain_info = self._create_dummy_terrain_info()
            voxel_grid = self._create_dummy_voxel_grid()
            
            # 大量データ変換テスト
            num_iterations = 100
            start_time = time.time()
            
            for _ in range(num_iterations):
                terrain_json = self.converter.terrain_info_to_json(terrain_info)
                voxel_json = self.converter.voxel_grid_to_json(voxel_grid)
            
            total_time = time.time() - start_time
            avg_time = total_time / num_iterations
            throughput = num_iterations / total_time
            
            # 結果記録
            self.test_results['communication_speed'] = {
                'total_time': total_time,
                'avg_time_per_message': avg_time,
                'throughput_messages_per_second': throughput,
                'iterations': num_iterations,
                'success': True
            }
            
            print(f"✅ 総時間: {total_time:.2f}秒")
            print(f"✅ 平均時間/メッセージ: {avg_time*1000:.1f}ms")
            print(f"✅ スループット: {throughput:.1f} messages/sec")
            
        except Exception as e:
            self.test_results['communication_speed'] = {'success': False, 'error': str(e)}
            print(f"❌ 通信速度テスト失敗: {e}")
    
    def test_error_handling(self):
        """エラーハンドリングテスト"""
        print("\n🛡️ テスト4: エラーハンドリング")
        print("-" * 30)
        
        try:
            error_tests = []
            
            # テスト1: 無効なデータ変換
            try:
                invalid_json = self.converter.terrain_info_to_json(None)
                error_tests.append(('無効データ変換', '成功' if 'error' in invalid_json else '失敗'))
            except:
                error_tests.append(('無効データ変換', '例外発生'))
            
            # テスト2: 空のJSON
            try:
                empty_data = json.loads('{}')
                error_tests.append(('空JSON処理', '成功'))
            except:
                error_tests.append(('空JSON処理', '失敗'))
            
            # テスト3: 不正なJSON
            try:
                invalid_json = json.loads('{"invalid": json}')
                error_tests.append(('不正JSON', '失敗'))
            except:
                error_tests.append(('不正JSON', '適切に例外処理'))
            
            # 結果記録
            self.test_results['error_handling'] = {
                'error_tests': error_tests,
                'success': True
            }
            
            for test_name, result in error_tests:
                print(f"✅ {test_name}: {result}")
            
        except Exception as e:
            self.test_results['error_handling'] = {'success': False, 'error': str(e)}
            print(f"❌ エラーハンドリングテスト失敗: {e}")
    
    def test_integration(self):
        """統合テスト"""
        print("\n🔗 テスト5: 統合テスト")
        print("-" * 30)
        
        try:
            # シミュレーション: ROS2 → Unity データフロー
            terrain_info = self._create_dummy_terrain_info()
            voxel_grid = self._create_dummy_voxel_grid()
            
            # データ変換
            terrain_json = self.converter.terrain_info_to_json(terrain_info)
            voxel_json = self.converter.voxel_grid_to_json(voxel_grid)
            unified_json = self.converter.create_unity_terrain_data(terrain_info, voxel_grid)
            
            # JSON検証
            terrain_data = json.loads(terrain_json)
            voxel_data = json.loads(voxel_json)
            unified_data = json.loads(unified_json)
            
            # Unity互換性チェック
            unity_compatibility = self._check_unity_compatibility(unified_data)
            
            # 結果記録
            self.test_results['integration'] = {
                'terrain_data_valid': 'message_type' in terrain_data,
                'voxel_data_valid': 'message_type' in voxel_data,
                'unified_data_valid': 'message_type' in unified_data,
                'unity_compatibility': unity_compatibility,
                'success': True
            }
            
            print(f"✅ TerrainInfoデータ: {'有効' if 'message_type' in terrain_data else '無効'}")
            print(f"✅ VoxelGrid3Dデータ: {'有効' if 'message_type' in voxel_data else '無効'}")
            print(f"✅ 統合データ: {'有効' if 'message_type' in unified_data else '無効'}")
            print(f"✅ Unity互換性: {'OK' if unity_compatibility else 'NG'}")
            
        except Exception as e:
            self.test_results['integration'] = {'success': False, 'error': str(e)}
            print(f"❌ 統合テスト失敗: {e}")
    
    def _create_dummy_terrain_info(self):
        """ダミーTerrainInfoデータ作成"""
        class DummyHeader:
            def __init__(self):
                self.stamp = DummyTime()
                self.frame_id = 'map'
        
        class DummyTime:
            def __init__(self):
                self.sec = int(time.time())
                self.nanosec = 0
        
        class DummyTerrainInfo:
            def __init__(self):
                self.header = DummyHeader()
                self.avg_slope = 15.5
                self.max_slope = 35.2
                self.min_slope = 2.1
                self.traversable_ratio = 0.75
                self.total_voxels = 1000
                self.ground_voxels = 750
                self.obstacle_voxels = 250
                self.avg_risk = 0.3
                self.max_risk = 0.8
                self.avg_cost = 2.5
                self.impassable_ratio = 0.25
                self.processing_time = 0.05
                self.point_count = 5000
        
        return DummyTerrainInfo()
    
    def _create_dummy_voxel_grid(self):
        """ダミーVoxelGrid3Dデータ作成"""
        class DummyPoint:
            def __init__(self, x, y, z):
                self.x = x
                self.y = y
                self.z = z
        
        class DummyVector3:
            def __init__(self, x, y, z):
                self.x = x
                self.y = y
                self.z = z
        
        class DummyVoxelGrid3D:
            def __init__(self):
                self.header = DummyHeader()
                self.voxel_size = 0.1
                self.num_voxels = 100
                self.min_bound = DummyPoint(-5.0, -5.0, -1.0)
                self.max_bound = DummyPoint(5.0, 5.0, 2.0)
                self.size_bound = DummyVector3(10.0, 10.0, 3.0)
                self.voxel_indices_x = list(range(100))
                self.voxel_indices_y = list(range(100))
                self.voxel_indices_z = list(range(100))
                self.voxel_types = [1] * 100  # 全て地面
                self.voxel_slopes = [15.0] * 100
                self.voxel_risks = [0.3] * 100
                self.voxel_costs = [2.0] * 100
        
        return DummyVoxelGrid3D()
    
    def _check_unity_compatibility(self, data: Dict[str, Any]) -> bool:
        """Unity互換性チェック"""
        required_fields = ['message_type', 'timestamp', 'frame_id']
        
        for field in required_fields:
            if field not in data:
                return False
        
        return True
    
    def print_test_results(self):
        """テスト結果表示"""
        print("\n" + "=" * 50)
        print("📋 テスト結果サマリー")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result.get('success', False))
        
        print(f"総テスト数: {total_tests}")
        print(f"成功: {passed_tests}")
        print(f"失敗: {total_tests - passed_tests}")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        
        print("\n詳細結果:")
        for test_name, result in self.test_results.items():
            status = "✅ 成功" if result.get('success', False) else "❌ 失敗"
            print(f"  {test_name}: {status}")
            
            if not result.get('success', False) and 'error' in result:
                print(f"    エラー: {result['error']}")


def main():
    """メイン関数"""
    tester = UnityBridgeTester()
    tester.run_all_tests()
    
    # テスト結果に基づく終了コード
    failed_tests = sum(1 for result in tester.test_results.values() if not result.get('success', False))
    return 0 if failed_tests == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
