#!/usr/bin/env python3
"""
Unity連携用TCP/IPサーバーノード
ROS2トピック → TCP/IP → Unity
"""

import socket
import threading
import time
import json
import logging
from typing import Optional, Dict, Any
from queue import Queue, Empty

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy

# ROS2メッセージ
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
    from bunker_3d_nav.unity_bridge.ros_to_unity_converter import RosToUnityConverter
except ImportError:
    # Fallback for development
    TerrainInfo = None
    VoxelGrid3D = None
    RosToUnityConverter = None


class UnityBridgeNode(Node):
    """
    Unity連携用TCP/IPサーバーノード
    
    機能:
    - ROS2トピック受信
    - TCP/IPサーバー
    - データ変換・送信
    - 接続管理
    """
    
    def __init__(self):
        super().__init__('unity_bridge')
        
        # パラメータ宣言
        self.declare_parameter('tcp_port', 10000)
        self.declare_parameter('tcp_host', '127.0.0.1')
        self.declare_parameter('max_connections', 5)
        self.declare_parameter('send_interval', 0.1)  # 10Hz
        
        # パラメータ取得
        self.tcp_port = self.get_parameter('tcp_port').value
        self.tcp_host = self.get_parameter('tcp_host').value
        self.max_connections = self.get_parameter('max_connections').value
        self.send_interval = self.get_parameter('send_interval').value
        
        # データ変換器
        if RosToUnityConverter is not None:
            self.converter = RosToUnityConverter(self.get_logger())
        else:
            self.converter = None
            self.get_logger().error('RosToUnityConverter not available')
        
        # ROS2サブスクライバー設定
        self._setup_subscribers()
        
        # TCP/IPサーバー設定
        self._setup_tcp_server()
        
        # データキュー
        self.data_queue = Queue(maxsize=100)
        
        # 接続管理
        self.connections = []
        self.connection_lock = threading.Lock()
        
        # 統計情報
        self.stats = {
            'messages_sent': 0,
            'connections_accepted': 0,
            'connections_lost': 0,
            'last_message_time': 0
        }
        
        # 送信スレッド開始
        self.send_thread = threading.Thread(target=self._send_data_loop)
        self.send_thread.daemon = True
        self.send_thread.start()
        
        self.get_logger().info(f'Unity Bridge initialized on {self.tcp_host}:{self.tcp_port}')
    
    def _setup_subscribers(self):
        """ROS2サブスクライバーを設定"""
        # QoS設定
        qos_profile = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
            depth=10
        )
        
        # TerrainInfoサブスクライバー
        if TerrainInfo is not None:
            self.terrain_sub = self.create_subscription(
                TerrainInfo,
                '/bunker/terrain_info',
                self.terrain_callback,
                qos_profile
            )
        else:
            self.terrain_sub = None
            self.get_logger().error('TerrainInfo not available')
        
        # VoxelGrid3Dサブスクライバー
        if VoxelGrid3D is not None:
            self.voxel_sub = self.create_subscription(
                VoxelGrid3D,
                '/bunker/voxel_grid',
                self.voxel_callback,
                qos_profile
            )
        else:
            self.voxel_sub = None
            self.get_logger().error('VoxelGrid3D not available')
    
    def _setup_tcp_server(self):
        """TCP/IPサーバーを設定"""
        try:
            self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server.bind((self.tcp_host, self.tcp_port))
            self.server.listen(self.max_connections)
            
            # 接続受付スレッド開始
            self.accept_thread = threading.Thread(target=self._accept_connections)
            self.accept_thread.daemon = True
            self.accept_thread.start()
            
            self.get_logger().info(f"TCP server listening on {self.tcp_host}:{self.tcp_port}")
            
        except Exception as e:
            self.get_logger().error(f'TCP server setup failed: {e}')
            self.server = None
    
    def terrain_callback(self, msg: TerrainInfo):
        """TerrainInfo受信 → Unity送信"""
        try:
            if self.converter is not None:
                json_data = self.converter.terrain_info_to_json(msg)
                self._queue_data(json_data, 'terrain_info')
                
                self.stats['last_message_time'] = time.time()
                
        except Exception as e:
            self.get_logger().error(f'TerrainInfo callback error: {e}')
    
    def voxel_callback(self, msg: VoxelGrid3D):
        """VoxelGrid3D受信 → Unity送信"""
        try:
            if self.converter is not None:
                json_data = self.converter.voxel_grid_to_json(msg)
                self._queue_data(json_data, 'voxel_grid')
                
        except Exception as e:
            self.get_logger().error(f'VoxelGrid3D callback error: {e}')
    
    def _queue_data(self, data: str, data_type: str):
        """データをキューに追加"""
        try:
            if not self.data_queue.full():
                self.data_queue.put({
                    'data': data,
                    'type': data_type,
                    'timestamp': time.time()
                })
            else:
                self.get_logger().warn('Data queue is full, dropping message')
                
        except Exception as e:
            self.get_logger().error(f'Data queuing error: {e}')
    
    def _accept_connections(self):
        """接続受付ループ"""
        while rclpy.ok():
            try:
                if self.server is not None:
                    client_socket, address = self.server.accept()
                    
                    with self.connection_lock:
                        self.connections.append({
                            'socket': client_socket,
                            'address': address,
                            'connected_time': time.time()
                        })
                    
                    self.stats['connections_accepted'] += 1
                    self.get_logger().info(f'Unity client connected from {address}')
                    
                    # 接続確認メッセージ送信
                    status_msg = self.converter.create_status_message('connected', 'Welcome to Unity Bridge!')
                    self._send_to_client(client_socket, status_msg)
                    
            except Exception as e:
                if rclpy.ok():
                    self.get_logger().error(f'Connection accept error: {e}')
                break
    
    def _send_data_loop(self):
        """データ送信ループ"""
        while rclpy.ok():
            try:
                # キューからデータ取得
                try:
                    queued_data = self.data_queue.get(timeout=0.1)
                except Empty:
                    continue
                
                # 全接続にデータ送信
                self._broadcast_data(queued_data)
                
                # 送信間隔制御
                time.sleep(self.send_interval)
                
            except Exception as e:
                self.get_logger().error(f'Data send loop error: {e}')
                time.sleep(0.1)
    
    def _broadcast_data(self, data: Dict[str, Any]):
        """全接続にデータをブロードキャスト"""
        with self.connection_lock:
            active_connections = []
            
            for conn in self.connections:
                try:
                    self._send_to_client(conn['socket'], data['data'])
                    active_connections.append(conn)
                    self.stats['messages_sent'] += 1
                    
                except Exception as e:
                    self.get_logger().warn(f'Failed to send to {conn["address"]}: {e}')
                    try:
                        conn['socket'].close()
                    except:
                        pass
                    self.stats['connections_lost'] += 1
            
            self.connections = active_connections
    
    def _send_to_client(self, client_socket: socket.socket, data: str):
        """クライアントにデータを送信"""
        try:
            # データ長を先頭に付加（4バイト）
            data_bytes = data.encode('utf-8')
            length = len(data_bytes)
            length_bytes = length.to_bytes(4, byteorder='big')
            
            # 送信
            client_socket.send(length_bytes + data_bytes)
            
        except Exception as e:
            raise Exception(f'Send error: {e}')
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """接続統計情報を取得"""
        with self.connection_lock:
            return {
                'active_connections': len(self.connections),
                'total_accepted': self.stats['connections_accepted'],
                'total_lost': self.stats['connections_lost'],
                'messages_sent': self.stats['messages_sent'],
                'last_message_time': self.stats['last_message_time'],
                'server_info': {
                    'host': self.tcp_host,
                    'port': self.tcp_port,
                    'max_connections': self.max_connections
                }
            }
    
    def send_status_to_all(self, status: str, message: str = ""):
        """全接続にステータスメッセージを送信"""
        if self.converter is not None:
            status_data = self.converter.create_status_message(status, message)
            self._queue_data(status_data, 'status')
    
    def cleanup(self):
        """リソースのクリーンアップ"""
        try:
            # 全接続を閉じる
            with self.connection_lock:
                for conn in self.connections:
                    try:
                        conn['socket'].close()
                    except:
                        pass
                self.connections.clear()
            
            # サーバーソケットを閉じる
            if self.server is not None:
                self.server.close()
            
            self.get_logger().info('Unity Bridge cleanup completed')
            
        except Exception as e:
            self.get_logger().error(f'Cleanup error: {e}')


def main(args=None):
    """メイン関数"""
    rclpy.init(args=args)
    
    try:
        node = UnityBridgeNode()
        
        # 定期的な統計情報出力
        def log_stats():
            while rclpy.ok():
                stats = node.get_connection_stats()
                node.get_logger().info(
                    f"Unity Bridge Stats: "
                    f"Connections={stats['active_connections']}, "
                    f"Messages={stats['messages_sent']}, "
                    f"Accepted={stats['total_accepted']}, "
                    f"Lost={stats['total_lost']}"
                )
                time.sleep(30)  # 30秒間隔
        
        stats_thread = threading.Thread(target=log_stats)
        stats_thread.daemon = True
        stats_thread.start()
        
        # ノード実行
        rclpy.spin(node)
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f'Unity Bridge error: {e}')
    finally:
        if 'node' in locals():
            node.cleanup()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
