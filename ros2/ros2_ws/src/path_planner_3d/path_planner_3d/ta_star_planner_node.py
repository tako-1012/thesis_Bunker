#!/usr/bin/env python3
"""
TA* Planner Node
地形データを統合してTA*経路計画を実行し、結果をUnity可視化向けに出力するノード
"""

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.duration import Duration

from geometry_msgs.msg import PoseStamped, Point
from nav_msgs.msg import Path
from visualization_msgs.msg import MarkerArray, Marker
from std_msgs.msg import Header, ColorRGBA
from sensor_msgs.msg import PointCloud2

# Custom messages
try:
    from bunker_3d_nav.msg import TerrainInfo, VoxelGrid3D
except ImportError:
    # Fallback: use None if custom messages not available
    TerrainInfo = None
    VoxelGrid3D = None

import numpy as np
import time
import logging
from typing import Optional, List, Tuple, Dict, Any

# TA* implementation
from .terrain_aware_astar_advanced import TerrainAwareAStar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TAStarPlannerNode(Node):
    """
    TA* (Terrain-Aware A*) 経路計画ノード
    
    地形データを統合し、リアルタイムに経路を計画してUnityに送信
    
    サブスクライブ:
    - /bunker/voxel_grid (VoxelGrid3D): 地形のボクセル表現
    - /bunker/terrain_info (TerrainInfo): 地形統計情報
    - /goal_pose (PoseStamped): 目標位置
    - /current_pose (PoseStamped): 現在位置
    
    パブリッシュ:
    - /path_3d (Path): TA*により計画された3D経路
    - /path_visualization (MarkerArray): RViz用可視化
    - /ta_star/stats (std_msgs/String): 統計情報 (JSON)
    """
    
    def __init__(self):
        super().__init__('ta_star_planner_node')
        
        # パラメータ宣言
        self._declare_parameters()
        
        # TA*プランナー初期化
        self.planner = None
        self._initialize_planner()
        
        # QoS設定
        qos_profile = QoSProfile(
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            history=QoSHistoryPolicy.KEEP_LAST,
            depth=10
        )
        
        # サブスクライバー
        self.voxel_grid_sub = self.create_subscription(
            VoxelGrid3D if VoxelGrid3D is not None else PointCloud2,
            '/bunker/voxel_grid',
            self.voxel_grid_callback,
            qos_profile
        )
        
        self.terrain_info_sub = self.create_subscription(
            TerrainInfo if TerrainInfo is not None else PointCloud2,
            '/bunker/terrain_info',
            self.terrain_info_callback,
            qos_profile
        )
        
        self.goal_sub = self.create_subscription(
            PoseStamped,
            '/goal_pose',
            self.goal_callback,
            qos_profile
        )
        
        self.current_pose_sub = self.create_subscription(
            PoseStamped,
            '/current_pose',
            self.current_pose_callback,
            qos_profile
        )
        
        # パブリッシャー
        self.path_pub = self.create_publisher(
            Path,
            '/path_3d',
            10
        )
        
        self.visualization_pub = self.create_publisher(
            MarkerArray,
            '/path_visualization',
            10
        )
        
        # 状態変数
        self.current_voxel_grid: Optional[np.ndarray] = None
        self.current_terrain_data: Optional[Dict[str, Any]] = None
        self.current_pose: Optional[PoseStamped] = None
        self.current_goal: Optional[PoseStamped] = None
        self.last_planned_path: Optional[Path] = None
        
        # 統計
        self.planning_count = 0
        self.total_planning_time = 0.0
        
        # タイマー：定期的に経路再計画
        self.planning_timer = self.create_timer(
            self.get_parameter('planning_interval').value,
            self.periodic_planning_callback
        )
        
        self.get_logger().info('✅ TA* Planner Node initialized')
        self.get_logger().info(f'   Voxel size: {self.get_parameter("voxel_size").value}m')
        self.get_logger().info(f'   Grid size: {self.get_parameter("grid_size_x").value} × '
                              f'{self.get_parameter("grid_size_y").value} × '
                              f'{self.get_parameter("grid_size_z").value}')
        self.get_logger().info(f'   Planning interval: {self.get_parameter("planning_interval").value}s')
    
    def _declare_parameters(self):
        """ROSパラメータ宣言"""
        # TA*パラメータ
        self.declare_parameter('voxel_size', 0.2)
        self.declare_parameter('grid_size_x', 200)
        self.declare_parameter('grid_size_y', 200)
        self.declare_parameter('grid_size_z', 50)
        self.declare_parameter('terrain_analysis_radius', 5)
        self.declare_parameter('enable_online_learning', True)
        self.declare_parameter('learning_rate', 0.1)
        
        # 経路計画動作パラメータ
        self.declare_parameter('planning_interval', 2.0)  # 秒
        self.declare_parameter('auto_replan', True)
        self.declare_parameter('enable_visualization', True)
        
        # マップ境界（デフォルト: 対称）
        self.declare_parameter('map_x_min', -20.0)
        self.declare_parameter('map_x_max', 20.0)
        self.declare_parameter('map_y_min', -20.0)
        self.declare_parameter('map_y_max', 20.0)
        self.declare_parameter('map_z_min', 0.0)
        self.declare_parameter('map_z_max', 10.0)
    
    def _initialize_planner(self):
        """TA*プランナー初期化"""
        grid_size = (
            self.get_parameter('grid_size_x').value,
            self.get_parameter('grid_size_y').value,
            self.get_parameter('grid_size_z').value
        )
        
        map_bounds = {
            'x_min': self.get_parameter('map_x_min').value,
            'x_max': self.get_parameter('map_x_max').value,
            'y_min': self.get_parameter('map_y_min').value,
            'y_max': self.get_parameter('map_y_max').value,
            'z_min': self.get_parameter('map_z_min').value,
            'z_max': self.get_parameter('map_z_max').value,
        }
        
        self.planner = TerrainAwareAStar(
            voxel_size=self.get_parameter('voxel_size').value,
            grid_size=grid_size,
            map_bounds=map_bounds,
            terrain_analysis_radius=self.get_parameter('terrain_analysis_radius').value,
            enable_online_learning=self.get_parameter('enable_online_learning').value,
            learning_rate=self.get_parameter('learning_rate').value,
        )
        
        self.get_logger().info('TA* planner initialized')
    
    def voxel_grid_callback(self, msg):
        """ボクセルグリッドを受信してTA*に設定"""
        try:
            # VoxelGrid3D → numpy変換
            # TODO: 実際のメッセージフォーマットに合わせて変換処理を実装
            
            # 仮実装: メッセージ構造を確認後に実装
            self.get_logger().debug('Received voxel grid')
            
            # 暫定: ダミーデータで代用（開発フェーズ）
            if self.current_voxel_grid is None:
                self.get_logger().info('Creating dummy voxel grid for development')
                self.current_voxel_grid = self._create_dummy_voxel_grid()
            
        except Exception as e:
            self.get_logger().error(f'Error processing voxel grid: {e}')
    
    def terrain_info_callback(self, msg):
        """地形情報を受信"""
        try:
            # TerrainInfo → dict変換
            # TODO: 実際のメッセージフォーマットに合わせて変換処理を実装
            
            self.get_logger().debug('Received terrain info')
            
            # 暫定: ダミーデータで代用
            if self.current_terrain_data is None:
                self.get_logger().info('Creating dummy terrain data for development')
                self.current_terrain_data = self._create_dummy_terrain_data()
            
        except Exception as e:
            self.get_logger().error(f'Error processing terrain info: {e}')
    
    def goal_callback(self, msg: PoseStamped):
        """目標位置を受信して経路計画をトリガー"""
        self.current_goal = msg
        self.get_logger().info(f'🎯 New goal received: '
                              f'({msg.pose.position.x:.2f}, '
                              f'{msg.pose.position.y:.2f}, '
                              f'{msg.pose.position.z:.2f})')
        
        # 即座に経路計画実行
        self._plan_path()
    
    def current_pose_callback(self, msg: PoseStamped):
        """現在位置を更新"""
        self.current_pose = msg
    
    def periodic_planning_callback(self):
        """定期的な経路再計画"""
        if not self.get_parameter('auto_replan').value:
            return
        
        if self.current_goal is not None and self.current_pose is not None:
            self.get_logger().debug('Periodic replanning triggered')
            self._plan_path()
    
    def _plan_path(self):
        """TA*による経路計画実行"""
        if self.current_pose is None or self.current_goal is None:
            self.get_logger().warn('⚠️ Cannot plan: pose or goal is None')
            return

        if self.planner is None:
            self.get_logger().error('❌ TA* planner not initialized')
            return

        try:
            # 地形データを必ずセット（ダミー含む）
            if self.current_voxel_grid is not None and self.current_terrain_data is not None:
                if self.planner.voxel_grid is None:
                    self.get_logger().info('Setting terrain data to TA*')
                    self.planner.set_terrain_data(
                        self.current_voxel_grid,
                        self.current_terrain_data
                    )
            else:
                self.get_logger().warn('⚠️ No terrain data available, forcibly setting dummy flat terrain')
                self._setup_dummy_terrain()
                self.get_logger().info('Dummy terrain set: grid shape = ' + str(self.planner.voxel_grid.shape if self.planner.voxel_grid is not None else 'None'))
            
            # 開始・目標座標を抽出
            start = (
                self.current_pose.pose.position.x,
                self.current_pose.pose.position.y,
                self.current_pose.pose.position.z
            )
            
            goal = (
                self.current_goal.pose.position.x,
                self.current_goal.pose.position.y,
                self.current_goal.pose.position.z
            )
            
            self.get_logger().info(f'🚀 Planning path: {start} → {goal}')
            
            # TA*実行
            start_time = time.time()
            path_points = self.planner.plan_path(start, goal)
            planning_time = time.time() - start_time
            
            # 統計更新
            self.planning_count += 1
            self.total_planning_time += planning_time
            
            if path_points is None:
                self.get_logger().error('❌ TA* failed to find path')
                return
            
            # Path メッセージ作成
            path_msg = self._create_path_message(path_points)
            self.path_pub.publish(path_msg)
            self.last_planned_path = path_msg
            
            # 統計情報をログ
            stats = self.planner.last_search_stats
            self.get_logger().info(
                f'✅ Path found! '
                f'Nodes: {stats["nodes_explored"]}, '
                f'Time: {planning_time:.3f}s, '
                f'Length: {len(path_points)} waypoints, '
                f'Strategy switches: {stats["strategy_switches"]}'
            )
            
            # 可視化
            if self.get_parameter('enable_visualization').value:
                self._publish_visualization(path_points, stats)
            
        except Exception as e:
            self.get_logger().error(f'❌ Error in path planning: {e}')
            import traceback
            self.get_logger().error(traceback.format_exc())
    
    def _create_path_message(self, path_points: List[Tuple[float, float, float]]) -> Path:
        """経路ポイントからPathメッセージを作成"""
        path_msg = Path()
        path_msg.header = Header()
        path_msg.header.stamp = self.get_clock().now().to_msg()
        path_msg.header.frame_id = 'map'
        
        for point in path_points:
            pose_stamped = PoseStamped()
            pose_stamped.header = path_msg.header
            pose_stamped.pose.position.x = point[0]
            pose_stamped.pose.position.y = point[1]
            pose_stamped.pose.position.z = point[2]
            pose_stamped.pose.orientation.w = 1.0  # 正規化されたクォータニオン
            
            path_msg.poses.append(pose_stamped)
        
        return path_msg
    
    def _publish_visualization(self, path_points: List[Tuple[float, float, float]], stats: Dict[str, Any]):
        """RViz用の可視化マーカーを作成・パブリッシュ"""
        marker_array = MarkerArray()
        
        # 経路ラインストリップ
        line_marker = Marker()
        line_marker.header.frame_id = 'map'
        line_marker.header.stamp = self.get_clock().now().to_msg()
        line_marker.ns = 'ta_star_path'
        line_marker.id = 0
        line_marker.type = Marker.LINE_STRIP
        line_marker.action = Marker.ADD
        line_marker.scale.x = 0.1  # ライン幅
        line_marker.color = ColorRGBA(r=0.0, g=1.0, b=0.0, a=1.0)  # 緑色
        
        for point in path_points:
            p = Point()
            p.x = point[0]
            p.y = point[1]
            p.z = point[2]
            line_marker.points.append(p)
        
        marker_array.markers.append(line_marker)
        
        # ウェイポイント球体
        for i, point in enumerate(path_points):
            sphere = Marker()
            sphere.header = line_marker.header
            sphere.ns = 'ta_star_waypoints'
            sphere.id = i
            sphere.type = Marker.SPHERE
            sphere.action = Marker.ADD
            sphere.pose.position.x = point[0]
            sphere.pose.position.y = point[1]
            sphere.pose.position.z = point[2]
            sphere.pose.orientation.w = 1.0
            sphere.scale.x = 0.2
            sphere.scale.y = 0.2
            sphere.scale.z = 0.2
            sphere.color = ColorRGBA(r=1.0, g=0.5, b=0.0, a=0.8)  # オレンジ色
            marker_array.markers.append(sphere)
        
        self.visualization_pub.publish(marker_array)
    
    def _create_dummy_voxel_grid(self) -> np.ndarray:
        """開発用ダミーボクセルグリッド生成（平坦地形）"""
        grid_size = (
            self.get_parameter('grid_size_x').value,
            self.get_parameter('grid_size_y').value,
            self.get_parameter('grid_size_z').value
        )
        
        voxel_grid = np.zeros(grid_size, dtype=np.float32)
        
        # 地面レイヤー（z=0）を占有
        voxel_grid[:, :, 0] = 1.0
        
        # ランダムに障害物を追加（10%）
        obstacle_mask = np.random.rand(grid_size[0], grid_size[1]) < 0.1
        voxel_grid[obstacle_mask, :, 1:5] = 1.0  # 高さ1-4に障害物
        
        return voxel_grid
    
    def _create_dummy_terrain_data(self) -> Dict[str, Any]:
        """開発用ダミー地形データ生成"""
        return {
            'slopes': np.zeros((
                self.get_parameter('grid_size_x').value,
                self.get_parameter('grid_size_y').value
            ), dtype=np.float32),
            'roughness': np.random.rand(
                self.get_parameter('grid_size_x').value,
                self.get_parameter('grid_size_y').value
            ) * 0.1,
            'metadata': {
                'resolution': self.get_parameter('voxel_size').value,
                'source': 'dummy'
            }
        }
    
    def _setup_dummy_terrain(self):
        """ダミー地形データをTA*に設定"""
        if self.current_voxel_grid is None:
            self.current_voxel_grid = self._create_dummy_voxel_grid()
        if self.current_terrain_data is None:
            self.current_terrain_data = self._create_dummy_terrain_data()
        
        self.planner.set_terrain_data(
            self.current_voxel_grid,
            self.current_terrain_data
        )
        self.get_logger().info('Dummy terrain data set to TA*')


def main(args=None):
    rclpy.init(args=args)
    node = TAStarPlannerNode()
    
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info('Shutting down TA* Planner Node')
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
