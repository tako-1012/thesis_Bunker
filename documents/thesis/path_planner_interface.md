# 3D経路計画インターフェース設計書

## 1. 概要

3D経路計画システムのインターフェース仕様を定義する。ROS2メッセージ、サービス、パラメータを含む。

## 2. 入力仕様

### 2.1 開始点・目標点
```python
# geometry_msgs/PoseStamped形式
start_pose: geometry_msgs.msg.PoseStamped
goal_pose: geometry_msgs.msg.PoseStamped

# 座標系: map座標系
# 位置: (x, y, z) [m]
# 姿勢: quaternion (x, y, z, w)
```

### 2.2 地形データ
```python
# ボクセルグリッドデータ
voxel_grid: bunker_3d_nav.msg.VoxelGrid3D

# 地形解析結果
terrain_info: bunker_3d_nav.msg.TerrainInfo

# 傾斜マップ（2D投影）
slope_map: nav_msgs.msg.OccupancyGrid
```

### 2.3 ロボット制約
```python
# ロボット物理パラメータ
robot_width: float = 0.6      # [m]
robot_length: float = 0.8     # [m]
robot_height: float = 0.4     # [m]
max_slope: float = 30.0       # [度]
min_clearance: float = 0.5    # [m]
```

## 3. 出力仕様

### 3.1 経路データ
```python
# 3D経路
path_3d: nav_msgs.msg.Path

# 経路統計情報
path_stats: bunker_3d_nav.msg.PathStats

# コスト情報
cost_info: bunker_3d_nav.msg.CostInfo
```

### 3.2 可視化データ
```python
# Rviz用マーカー
path_markers: visualization_msgs.msg.MarkerArray

# コストマップ可視化
cost_visualization: visualization_msgs.msg.MarkerArray

# 地形可視化
terrain_visualization: visualization_msgs.msg.MarkerArray
```

## 4. ROS2メッセージ定義

### 4.1 Path3D.msg
```msg
# 3D経路情報
Header header
geometry_msgs/Point[] points
float32[] costs
float32[] slopes
float32 total_length
float32 total_cost
float32 max_slope
float32 avg_slope
bool success
string error_message
```

### 4.2 PathStats.msg
```msg
# 経路統計情報
Header header
float32 path_length
float32 travel_time_estimate
float32 max_slope_deg
float32 avg_slope_deg
float32 energy_cost
float32 computation_time_ms
int32 num_waypoints
bool path_found
```

### 4.3 CostInfo.msg
```msg
# コスト情報
Header header
float32 base_cost
float32 slope_cost
float32 obstacle_cost
float32 risk_cost
float32 smoothness_cost
float32 total_cost
float32[] cost_breakdown
```

### 4.4 VoxelGrid3D.msg
```msg
# 3Dボクセルグリッド
Header header
float32 voxel_size
float32[] origin          # [x, y, z]
int32[] dimensions        # [width, height, depth]
int8[] voxels            # ボクセルデータ
string[] voxel_types      # タイプ名
```

### 4.5 TerrainInfo.msg
```msg
# 地形情報
Header header
float32 min_elevation
float32 max_elevation
float32 avg_slope_deg
float32 max_slope_deg
int32 num_obstacles
int32 num_traversable_voxels
float32[] slope_distribution
```

## 5. ROS2サービス定義

### 5.1 PlanPath3D.srv
```srv
# 3D経路計画サービス
geometry_msgs/PoseStamped start_pose
geometry_msgs/PoseStamped goal_pose
bunker_3d_nav/VoxelGrid3D terrain_data
bunker_3d_nav/PathPlannerParams params
---
bunker_3d_nav/Path3D path
bunker_3d_nav/PathStats stats
bunker_3d_nav/CostInfo cost_info
bool success
string error_message
```

### 5.2 PathPlannerParams.msg
```msg
# 経路計画パラメータ
float32 voxel_size
float32 max_slope_deg
float32 min_clearance
float32 weight_slope
float32 weight_obstacle
float32 weight_risk
float32 weight_smoothness
bool enable_smoothing
int32 max_iterations
float32 timeout_sec
```

## 6. ROS2ノードインターフェース

### 6.1 PathPlanner3DNode
```python
class PathPlanner3DNode(Node):
    """3D経路計画ROSノード"""
    
    def __init__(self):
        super().__init__('path_planner_3d')
        
        # パラメータ宣言
        self.declare_parameters()
        
        # Subscriber
        self.goal_sub = self.create_subscription(
            PoseStamped,
            '/goal_pose',
            self.goal_callback,
            10
        )
        
        # Publisher
        self.path_pub = self.create_publisher(
            Path,
            '/path_3d',
            10
        )
        
        # Service
        self.plan_service = self.create_service(
            PlanPath3D,
            '/plan_path_3d',
            self.plan_path_callback
        )
        
        # タイマー
        self.timer = self.create_timer(0.1, self.timer_callback)
    
    def declare_parameters(self):
        """パラメータ宣言"""
        self.declare_parameter('voxel_size', 0.1)
        self.declare_parameter('max_slope_deg', 30.0)
        self.declare_parameter('weight_slope', 3.0)
        self.declare_parameter('weight_obstacle', 5.0)
        self.declare_parameter('weight_risk', 4.0)
        self.declare_parameter('enable_smoothing', True)
        self.declare_parameter('max_iterations', 10000)
        self.declare_parameter('timeout_sec', 10.0)
    
    def goal_callback(self, msg: PoseStamped):
        """目標位置受信時のコールバック"""
        try:
            # 現在位置取得
            current_pose = self.get_current_pose()
            
            # 経路計画実行
            path = self.plan_path(current_pose, msg)
            
            if path is not None:
                # 経路パブリッシュ
                self.publish_path(path)
                
                # 統計情報パブリッシュ
                stats = self.calculate_path_stats(path)
                self.publish_stats(stats)
                
                self.get_logger().info('Path planned successfully')
            else:
                self.get_logger().warn('Path planning failed')
                
        except Exception as e:
            self.get_logger().error(f'Error in goal callback: {e}')
    
    def plan_path_callback(self, request, response):
        """経路計画サービスコールバック"""
        try:
            # パラメータ設定
            self.update_planner_params(request.params)
            
            # 経路計画実行
            path = self.plan_path(request.start_pose, request.goal_pose)
            
            if path is not None:
                response.path = path
                response.stats = self.calculate_path_stats(path)
                response.cost_info = self.calculate_cost_info(path)
                response.success = True
                response.error_message = ""
            else:
                response.success = False
                response.error_message = "Path planning failed"
                
        except Exception as e:
            response.success = False
            response.error_message = str(e)
            self.get_logger().error(f'Service error: {e}')
        
        return response
```

## 7. エラーハンドリング

### 7.1 エラーコード定義
```python
class PathPlannerError(Exception):
    """経路計画エラーベースクラス"""
    pass

class InvalidStartPoseError(PathPlannerError):
    """無効な開始位置"""
    pass

class InvalidGoalPoseError(PathPlannerError):
    """無効な目標位置"""
    pass

class NoPathFoundError(PathPlannerError):
    """経路が見つからない"""
    pass

class TerrainDataError(PathPlannerError):
    """地形データエラー"""
    pass

class TimeoutError(PathPlannerError):
    """タイムアウトエラー"""
    pass
```

### 7.2 エラーハンドリング戦略
```python
def plan_path(self, start, goal):
    """経路計画（エラーハンドリング付き）"""
    try:
        # 入力検証
        self.validate_inputs(start, goal)
        
        # 地形データチェック
        if not self.terrain_data_available():
            raise TerrainDataError("Terrain data not available")
        
        # 経路計画実行
        path = self.astar_planner.plan_path(start, goal)
        
        if path is None:
            raise NoPathFoundError("No path found to goal")
        
        return path
        
    except PathPlannerError as e:
        self.get_logger().error(f'Path planning error: {e}')
        return None
    except Exception as e:
        self.get_logger().error(f'Unexpected error: {e}')
        return None
```

## 8. パラメータ設定

### 8.1 パラメータファイル（planner_params.yaml）
```yaml
path_planner_3d:
  ros__parameters:
    # 基本設定
    voxel_size: 0.1
    max_slope_deg: 30.0
    min_clearance: 0.5
    
    # コスト重み
    weights:
      slope: 3.0
      obstacle: 5.0
      risk: 4.0
      smoothness: 1.0
    
    # アルゴリズム設定
    max_iterations: 10000
    timeout_sec: 10.0
    enable_smoothing: true
    
    # ロボット制約
    robot:
      width: 0.6
      length: 0.8
      height: 0.4
      max_roll: 20.0
      max_pitch: 25.0
    
    # パフォーマンス設定
    performance:
      max_memory_mb: 500
      max_cpu_percent: 80
      enable_early_termination: true
```

## 9. ログ・デバッグ

### 9.1 ログレベル設定
```python
# デバッグ情報
self.get_logger().debug('Detailed debug info')
self.get_logger().info('Normal operation info')
self.get_logger().warn('Warning message')
self.get_logger().error('Error occurred')
```

### 9.2 デバッグトピック
```python
# デバッグ用パブリッシャー
self.debug_pub = self.create_publisher(
    String,
    '/path_planner/debug',
    10
)

# デバッグ情報送信
debug_info = {
    'open_list_size': len(self.open_list),
    'closed_set_size': len(self.closed_set),
    'current_node': str(self.current_node),
    'iterations': self.iteration_count
}
self.debug_pub.publish(str(debug_info))
```

## 10. テスト・検証

### 10.1 単体テスト
```python
def test_path_planning():
    """経路計画テスト"""
    planner = AStarPlanner3D()
    
    # テストケース1: 直線経路
    start = (0.0, 0.0, 0.0)
    goal = (10.0, 0.0, 0.0)
    path = planner.plan_path(start, goal)
    assert path is not None
    assert len(path) > 0
    
    # テストケース2: 障害物回避
    # TODO: 障害物テスト
    
    # テストケース3: 傾斜地
    # TODO: 傾斜地テスト
```

### 10.2 統合テスト
```python
def test_ros_integration():
    """ROS統合テスト"""
    # ノード起動
    node = PathPlanner3DNode()
    
    # サービス呼び出し
    request = PlanPath3D.Request()
    request.start_pose = create_test_pose(0, 0, 0)
    request.goal_pose = create_test_pose(10, 10, 0)
    
    response = node.plan_path_callback(request, PlanPath3D.Response())
    
    assert response.success == True
    assert len(response.path.points) > 0
```

## 11. パフォーマンス要件

### 11.1 計算時間
- **小規模**: 100×100×10グリッド → 1秒以内
- **中規模**: 500×500×20グリッド → 5秒以内
- **大規模**: 1000×1000×50グリッド → 10秒以内

### 11.2 メモリ使用量
- **最大メモリ**: 500MB以内
- **平均メモリ**: 200MB以内
- **メモリリーク**: なし

### 11.3 精度要件
- **位置精度**: ±0.1m以内
- **角度精度**: ±1度以内
- **経路長精度**: ±5%以内

---

**作成日**: 2025-10-11  
**更新日**: 2025-10-11  
**作成者**: AI研究アシスタント


