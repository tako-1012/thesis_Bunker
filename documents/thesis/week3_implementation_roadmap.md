# Week 3実装ロードマップ

## 1. 概要

Week 3でのA* 3D経路計画実装の詳細なロードマップ。4日間の実装計画と各日の具体的なタスクを定義する。

## 2. 全体スケジュール

### 2.1 実装期間
- **開始日**: 2025-10-13 (月)
- **終了日**: 2025-10-16 (木)
- **総実装時間**: 20-28時間
- **目標**: A* 3D経路計画の完全実装

### 2.2 マイルストーン
- **Day 9**: A* 3D基本実装完了
- **Day 10**: コスト関数統合完了
- **Day 11**: 経路平滑化実装完了
- **Day 12**: Unity統合・Week 3完了

## 3. Day 9: A* 3D基本実装

### 3.1 目標
- Node3Dクラスの実装
- AStarPlanner3Dクラスの基本構造
- 26近傍探索の実装
- 基本的なヒューリスティック関数

### 3.2 実装タスク

#### タスク1: Node3Dクラス実装
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/node_3d.py`

**実装内容**:
```python
"""
3D空間のノードクラス
A*アルゴリズムで使用
"""
from typing import Tuple, Optional
from dataclasses import dataclass, field

@dataclass
class Node3D:
    """3D空間のノード"""
    
    # 位置（ボクセルグリッドのインデックス）
    position: Tuple[int, int, int]
    
    # コスト
    g_cost: float = float('inf')  # スタートからのコスト
    h_cost: float = 0.0           # ゴールまでの推定コスト
    
    # 親ノード
    parent: Optional['Node3D'] = None
    
    @property
    def f_cost(self) -> float:
        """総コスト = g + h"""
        return self.g_cost + self.h_cost
    
    def __eq__(self, other):
        """位置が同じなら同一ノード"""
        return self.position == other.position
    
    def __hash__(self):
        """ハッシュ値（dictのキーとして使用）"""
        return hash(self.position)
    
    def __lt__(self, other):
        """優先度キューでの比較（f_costで比較）"""
        return self.f_cost < other.f_cost
```

**推定時間**: 1-2時間

#### タスク2: AStarPlanner3Dクラス基本実装
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/astar_planner_3d.py`

**実装内容**:
```python
"""
A* 3D経路計画クラス
"""
import heapq
from typing import List, Tuple, Optional, Set
import numpy as np
from node_3d import Node3D

class AStarPlanner3D:
    """A* 3D経路計画"""
    
    def __init__(self, voxel_size: float = 0.1):
        self.voxel_size = voxel_size
        self.voxel_grid = None
        self.terrain_data = None
    
    def set_terrain_data(self, voxel_grid, terrain_data):
        """地形データを設定"""
        self.voxel_grid = voxel_grid
        self.terrain_data = terrain_data
    
    def plan_path(
        self,
        start: Tuple[float, float, float],
        goal: Tuple[float, float, float]
    ) -> Optional[List[Tuple[float, float, float]]]:
        """
        経路計画のメイン関数
        
        Args:
            start: 開始位置（ワールド座標）
            goal: 目標位置（ワールド座標）
        
        Returns:
            経路（ワールド座標のリスト）、失敗時はNone
        """
        # ワールド座標 → ボクセルインデックス変換
        start_idx = self._world_to_voxel(start)
        goal_idx = self._world_to_voxel(goal)
        
        # A*アルゴリズム実行
        path_indices = self._astar_search(start_idx, goal_idx)
        
        if path_indices is None:
            return None
        
        # ボクセルインデックス → ワールド座標変換
        path_world = [self._voxel_to_world(idx) for idx in path_indices]
        
        return path_world
    
    def _astar_search(
        self,
        start: Tuple[int, int, int],
        goal: Tuple[int, int, int]
    ) -> Optional[List[Tuple[int, int, int]]]:
        """A*探索アルゴリズム"""
        
        # 開始ノード作成
        start_node = Node3D(position=start, g_cost=0.0)
        start_node.h_cost = self._heuristic(start, goal)
        
        # オープンリスト（優先度キュー）
        open_list = []
        heapq.heappush(open_list, start_node)
        
        # クローズドセット
        closed_set: Set[Tuple[int, int, int]] = set()
        
        # ノードの記録（位置 → ノード）
        all_nodes = {start: start_node}
        
        while open_list:
            # f_costが最小のノードを取り出し
            current = heapq.heappop(open_list)
            
            # ゴール到達チェック
            if current.position == goal:
                return self._reconstruct_path(current)
            
            # クローズドセットに追加
            closed_set.add(current.position)
            
            # 近傍ノードを探索
            for neighbor_pos in self._get_neighbors(current.position):
                # クローズド済みならスキップ
                if neighbor_pos in closed_set:
                    continue
                
                # 障害物チェック
                if not self._is_traversable(neighbor_pos):
                    continue
                
                # 移動コスト計算
                move_cost = self._calculate_move_cost(
                    current.position, neighbor_pos
                )
                tentative_g = current.g_cost + move_cost
                
                # 近傍ノードを取得または作成
                if neighbor_pos not in all_nodes:
                    neighbor = Node3D(position=neighbor_pos)
                    neighbor.h_cost = self._heuristic(neighbor_pos, goal)
                    all_nodes[neighbor_pos] = neighbor
                else:
                    neighbor = all_nodes[neighbor_pos]
                
                # より良い経路が見つかった場合
                if tentative_g < neighbor.g_cost:
                    neighbor.parent = current
                    neighbor.g_cost = tentative_g
                    
                    # オープンリストに追加
                    if neighbor not in open_list:
                        heapq.heappush(open_list, neighbor)
        
        # 経路が見つからなかった
        return None
    
    def _heuristic(
        self,
        pos: Tuple[int, int, int],
        goal: Tuple[int, int, int]
    ) -> float:
        """ヒューリスティック関数（ユークリッド距離）"""
        dx = pos[0] - goal[0]
        dy = pos[1] - goal[1]
        dz = pos[2] - goal[2]
        return np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
    
    def _get_neighbors(
        self,
        pos: Tuple[int, int, int]
    ) -> List[Tuple[int, int, int]]:
        """26近傍を取得"""
        x, y, z = pos
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    # 自分自身はスキップ
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    neighbor = (x + dx, y + dy, z + dz)
                    
                    # グリッド範囲内チェック
                    if self._is_in_grid(neighbor):
                        neighbors.append(neighbor)
        
        return neighbors
    
    def _calculate_move_cost(
        self,
        from_pos: Tuple[int, int, int],
        to_pos: Tuple[int, int, int]
    ) -> float:
        """移動コスト計算（基本距離、後でコスト関数を統合）"""
        dx = from_pos[0] - to_pos[0]
        dy = from_pos[1] - to_pos[1]
        dz = from_pos[2] - to_pos[2]
        
        # ユークリッド距離
        distance = np.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
        
        return distance
    
    def _is_traversable(self, pos: Tuple[int, int, int]) -> bool:
        """走行可能チェック（仮実装）"""
        # TODO: 実際の地形データでチェック
        return True
    
    def _is_in_grid(self, pos: Tuple[int, int, int]) -> bool:
        """グリッド範囲内チェック（仮実装）"""
        # TODO: 実際のグリッドサイズでチェック
        return True
    
    def _reconstruct_path(
        self,
        node: Node3D
    ) -> List[Tuple[int, int, int]]:
        """経路を復元"""
        path = []
        current = node
        
        while current is not None:
            path.append(current.position)
            current = current.parent
        
        # 逆順なので反転
        path.reverse()
        return path
    
    def _world_to_voxel(
        self,
        pos: Tuple[float, float, float]
    ) -> Tuple[int, int, int]:
        """ワールド座標 → ボクセルインデックス"""
        # TODO: 実装
        return (0, 0, 0)
    
    def _voxel_to_world(
        self,
        idx: Tuple[int, int, int]
    ) -> Tuple[float, float, float]:
        """ボクセルインデックス → ワールド座標"""
        # TODO: 実装
        return (0.0, 0.0, 0.0)
```

**推定時間**: 4-6時間

#### タスク3: 基本テストコード
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/test_astar_basic.py`

**テスト内容**:
- Node3Dクラスのテスト
- ヒューリスティック関数のテスト
- 26近傍取得のテスト
- 経路復元のテスト
- 簡単な経路探索テスト

**推定時間**: 1-2時間

### 3.3 完了基準
- [ ] Node3Dクラスが正常動作
- [ ] AStarPlanner3Dクラスが正常動作
- [ ] 26近傍探索が正常動作
- [ ] 基本的な経路探索が成功
- [ ] 単体テストが100%パス

### 3.4 推定所要時間
**合計**: 6-10時間

## 4. Day 10: コスト関数統合

### 4.1 目標
- CostCalculatorクラスの実装
- 傾斜コストの統合
- 障害物コストの統合
- 転倒リスクコストの統合

### 4.2 実装タスク

#### タスク1: CostCalculatorクラス実装
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/cost_calculator.py`

**実装内容**:
```python
"""
経路計画用のコスト計算クラス
"""
import numpy as np
from typing import Tuple

class CostCalculator:
    """統合コスト計算"""
    
    def __init__(
        self,
        weight_slope: float = 2.0,
        weight_obstacle: float = 5.0,
        weight_risk: float = 3.0,
        weight_smoothness: float = 1.0
    ):
        """
        Args:
            weight_slope: 傾斜コストの重み
            weight_obstacle: 障害物コストの重み
            weight_risk: 転倒リスクコストの重み
            weight_smoothness: 平滑化コストの重み
        """
        self.weight_slope = weight_slope
        self.weight_obstacle = weight_obstacle
        self.weight_risk = weight_risk
        self.weight_smoothness = weight_smoothness
    
    def calculate_total_cost(
        self,
        base_cost: float,
        slope_deg: float,
        is_obstacle: bool,
        risk_score: float,
        turn_angle: float = 0.0
    ) -> float:
        """
        統合コスト計算
        
        Args:
            base_cost: 基本移動コスト（距離）
            slope_deg: 傾斜角度
            is_obstacle: 障害物フラグ
            risk_score: 転倒リスクスコア（0-1）
            turn_angle: 旋回角度（ラジアン）
        
        Returns:
            総コスト
        """
        total = base_cost
        total += self._slope_cost(slope_deg) * self.weight_slope
        total += self._obstacle_cost(is_obstacle) * self.weight_obstacle
        total += self._risk_cost(risk_score) * self.weight_risk
        total += self._smoothness_cost(turn_angle) * self.weight_smoothness
        
        return total
    
    def _slope_cost(self, slope_deg: float) -> float:
        """傾斜コスト（指数関数的に増加）"""
        if slope_deg < 15.0:
            return 0.0
        elif slope_deg < 25.0:
            return (slope_deg - 15.0) / 10.0  # 0-1
        elif slope_deg < 35.0:
            return 1.0 + (slope_deg - 25.0) / 5.0  # 1-3
        else:
            return 1000.0  # 実質走行不可
    
    def _obstacle_cost(self, is_obstacle: bool) -> float:
        """障害物コスト"""
        return 1000.0 if is_obstacle else 0.0
    
    def _risk_cost(self, risk_score: float) -> float:
        """転倒リスクコスト"""
        return risk_score * 10.0
    
    def _smoothness_cost(self, turn_angle: float) -> float:
        """平滑化コスト（急旋回ペナルティ）"""
        return abs(turn_angle)
```

**推定時間**: 2-3時間

#### タスク2: AStarPlanner3Dへのコスト関数統合
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/astar_planner_3d.py`（更新）

**更新内容**:
- CostCalculatorの統合
- `_calculate_move_cost()`の詳細実装
- 地形データの活用
- `_is_traversable()`の実装

**推定時間**: 3-4時間

#### タスク3: テストコード
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/test_cost_calculator.py`

**テスト内容**:
- 傾斜コストのテスト
- 障害物コストのテスト
- リスクコストのテスト
- 統合コストのテスト

**推定時間**: 1-2時間

### 4.3 完了基準
- [ ] CostCalculatorクラスが正常動作
- [ ] 傾斜コストが正常計算
- [ ] 障害物コストが正常計算
- [ ] 転倒リスクコストが正常計算
- [ ] A*アルゴリズムにコスト関数が統合
- [ ] 単体テストが100%パス

### 4.4 推定所要時間
**合計**: 6-9時間

## 5. Day 11: 経路平滑化実装

### 5.1 目標
- PathSmootherクラスの実装
- Cubic spline補間の実装
- 制約チェック機能
- A*への統合

### 5.2 実装タスク

#### タスク1: PathSmootherクラス実装
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/path_smoother.py`

**実装内容**:
```python
"""
経路平滑化クラス
"""
import numpy as np
from scipy.interpolate import CubicSpline
from typing import List, Tuple

class PathSmoother:
    """経路平滑化"""
    
    def __init__(
        self,
        num_points: int = 100,
        max_slope_deg: float = 35.0,
        min_curve_radius: float = 0.5
    ):
        """
        Args:
            num_points: 補間後の点数
            max_slope_deg: 最大傾斜（制約）
            min_curve_radius: 最小曲率半径（制約）
        """
        self.num_points = num_points
        self.max_slope_deg = max_slope_deg
        self.min_curve_radius = min_curve_radius
    
    def smooth_path(
        self,
        path: List[Tuple[float, float, float]]
    ) -> List[Tuple[float, float, float]]:
        """
        経路平滑化
        
        Args:
            path: 元の経路（ワールド座標）
        
        Returns:
            平滑化された経路
        """
        if len(path) < 3:
            return path
        
        # numpy配列に変換
        path_array = np.array(path)
        
        # パラメータt（経路長に沿ったパラメータ）
        t = self._calculate_path_parameter(path_array)
        
        # Cubic spline補間
        cs_x = CubicSpline(t, path_array[:, 0])
        cs_y = CubicSpline(t, path_array[:, 1])
        cs_z = CubicSpline(t, path_array[:, 2])
        
        # 補間
        t_new = np.linspace(t[0], t[-1], self.num_points)
        x_new = cs_x(t_new)
        y_new = cs_y(t_new)
        z_new = cs_z(t_new)
        
        # リストに変換
        smoothed_path = list(zip(x_new, y_new, z_new))
        
        # 制約チェック（オプション）
        if self._check_constraints(smoothed_path):
            return smoothed_path
        else:
            # 制約違反の場合は元の経路を返す
            return path
    
    def _calculate_path_parameter(
        self,
        path: np.ndarray
    ) -> np.ndarray:
        """経路長パラメータ計算"""
        # 各点間の距離
        diff = np.diff(path, axis=0)
        segment_lengths = np.sqrt(np.sum(diff**2, axis=1))
        
        # 累積距離
        t = np.zeros(len(path))
        t[1:] = np.cumsum(segment_lengths)
        
        return t
    
    def _check_constraints(
        self,
        path: List[Tuple[float, float, float]]
    ) -> bool:
        """制約チェック"""
        # TODO: 傾斜・曲率のチェック
        return True
```

**推定時間**: 2-3時間

#### タスク2: AStarPlanner3Dへの統合
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/astar_planner_3d.py`（更新）

**更新内容**:
- PathSmootherの統合
- `plan_path()`メソッドに平滑化オプション追加

**推定時間**: 1-2時間

#### タスク3: テストコード
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/path_planner_3d/test_path_smoother.py`

**テスト内容**:
- 直線経路の平滑化
- ジグザグ経路の平滑化
- 3D経路の平滑化

**推定時間**: 1-2時間

### 5.3 完了基準
- [ ] PathSmootherクラスが正常動作
- [ ] Cubic spline補間が正常動作
- [ ] 制約チェックが正常動作
- [ ] A*アルゴリズムに平滑化が統合
- [ ] 単体テストが100%パス

### 5.4 推定所要時間
**合計**: 4-7時間

## 6. Day 12: Unity統合とWeek 3完了

### 6.1 目標
- 経路データのUnity送信機能
- Unity用C#スクリプト更新
- ROS2カスタムメッセージ定義
- Week 3完了レポート

### 6.2 実装タスク

#### タスク1: 経路データのUnity送信機能
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/unity_bridge/path_sender.py`

**実装内容**:
```python
"""
経路データのUnity送信機能
"""
import json
import socket
from typing import List, Tuple
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Path
from geometry_msgs.msg import Point

class PathSender(Node):
    """経路データをUnityに送信"""
    
    def __init__(self):
        super().__init__('path_sender')
        
        # Unity接続設定
        self.unity_host = '127.0.0.1'
        self.unity_port = 10000
        
        # 経路サブスクライバー
        self.path_sub = self.create_subscription(
            Path,
            '/path_3d',
            self.path_callback,
            10
        )
        
        # Unity接続
        self.socket = None
        self.connect_to_unity()
    
    def connect_to_unity(self):
        """Unityに接続"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.unity_host, self.unity_port))
            self.get_logger().info('Connected to Unity')
        except Exception as e:
            self.get_logger().error(f'Failed to connect to Unity: {e}')
    
    def path_callback(self, msg: Path):
        """経路データ受信時のコールバック"""
        try:
            # 経路データをJSON形式に変換
            path_data = self.convert_path_to_json(msg)
            
            # Unityに送信
            self.send_to_unity(path_data)
            
        except Exception as e:
            self.get_logger().error(f'Error in path callback: {e}')
    
    def convert_path_to_json(self, path_msg: Path) -> dict:
        """経路メッセージをJSON形式に変換"""
        path_data = {
            'header': {
                'stamp': {
                    'sec': path_msg.header.stamp.sec,
                    'nanosec': path_msg.header.stamp.nanosec
                },
                'frame_id': path_msg.header.frame_id
            },
            'poses': []
        }
        
        for pose_stamped in path_msg.poses:
            pose_data = {
                'position': {
                    'x': pose_stamped.pose.position.x,
                    'y': pose_stamped.pose.position.y,
                    'z': pose_stamped.pose.position.z
                },
                'orientation': {
                    'x': pose_stamped.pose.orientation.x,
                    'y': pose_stamped.pose.orientation.y,
                    'z': pose_stamped.pose.orientation.z,
                    'w': pose_stamped.pose.orientation.w
                }
            }
            path_data['poses'].append(pose_data)
        
        return path_data
    
    def send_to_unity(self, data: dict):
        """Unityにデータ送信"""
        if self.socket is None:
            return
        
        try:
            json_data = json.dumps(data)
            self.socket.send(json_data.encode('utf-8'))
            self.get_logger().debug('Sent path data to Unity')
        except Exception as e:
            self.get_logger().error(f'Failed to send data to Unity: {e}')
```

**推定時間**: 2-3時間

#### タスク2: Unity用C#スクリプト更新
**ファイル**: `~/thesis_work/documents/thesis/unity_scripts/PathVisualizer.cs`

**実装内容**:
```csharp
using UnityEngine;
using System.Collections.Generic;
using System.Net.Sockets;
using System.Text;
using Newtonsoft.Json;

public class PathVisualizer : MonoBehaviour
{
    [Header("Path Visualization")]
    public LineRenderer pathLineRenderer;
    public Material pathMaterial;
    public Color normalPathColor = Color.green;
    public Color steepPathColor = Color.red;
    
    [Header("Network Settings")]
    public string rosHost = "127.0.0.1";
    public int rosPort = 10000;
    
    private TcpClient tcpClient;
    private NetworkStream stream;
    private List<Vector3> currentPath = new List<Vector3>();
    
    void Start()
    {
        // LineRenderer設定
        if (pathLineRenderer == null)
        {
            pathLineRenderer = gameObject.AddComponent<LineRenderer>();
        }
        
        pathLineRenderer.material = pathMaterial;
        pathLineRenderer.startWidth = 0.1f;
        pathLineRenderer.endWidth = 0.1f;
        pathLineRenderer.useWorldSpace = true;
        
        // ROS接続
        ConnectToROS();
    }
    
    void Update()
    {
        // 経路データ受信
        ReceivePathData();
    }
    
    void ConnectToROS()
    {
        try
        {
            tcpClient = new TcpClient(rosHost, rosPort);
            stream = tcpClient.GetStream();
            Debug.Log("Connected to ROS2");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Failed to connect to ROS2: {e.Message}");
        }
    }
    
    void ReceivePathData()
    {
        if (stream == null || !stream.DataAvailable)
            return;
        
        try
        {
            byte[] buffer = new byte[4096];
            int bytesRead = stream.Read(buffer, 0, buffer.Length);
            
            if (bytesRead > 0)
            {
                string jsonData = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                ProcessPathData(jsonData);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Error receiving path data: {e.Message}");
        }
    }
    
    void ProcessPathData(string jsonData)
    {
        try
        {
            var pathData = JsonConvert.DeserializeObject<PathData>(jsonData);
            
            // 経路点をVector3に変換
            currentPath.Clear();
            foreach (var pose in pathData.poses)
            {
                Vector3 point = new Vector3(
                    (float)pose.position.x,
                    (float)pose.position.z, // UnityのY軸はROSのZ軸
                    (float)pose.position.y   // UnityのZ軸はROSのY軸
                );
                currentPath.Add(point);
            }
            
            // 経路を可視化
            VisualizePath();
        }
        catch (System.Exception e)
        {
            Debug.LogError($"Error processing path data: {e.Message}");
        }
    }
    
    void VisualizePath()
    {
        if (currentPath.Count < 2)
            return;
        
        // LineRendererに経路を設定
        pathLineRenderer.positionCount = currentPath.Count;
        pathLineRenderer.SetPositions(currentPath.ToArray());
        
        // 傾斜に応じて色を変更
        UpdatePathColor();
    }
    
    void UpdatePathColor()
    {
        // 傾斜計算（簡易版）
        float maxSlope = 0f;
        for (int i = 1; i < currentPath.Count; i++)
        {
            float slope = Mathf.Abs(currentPath[i].y - currentPath[i-1].y);
            maxSlope = Mathf.Max(maxSlope, slope);
        }
        
        // 傾斜に応じて色を補間
        Color pathColor = Color.Lerp(normalPathColor, steepPathColor, maxSlope);
        pathLineRenderer.material.color = pathColor;
    }
    
    void OnDestroy()
    {
        if (stream != null)
            stream.Close();
        if (tcpClient != null)
            tcpClient.Close();
    }
}

[System.Serializable]
public class PathData
{
    public HeaderData header;
    public List<PoseData> poses;
}

[System.Serializable]
public class HeaderData
{
    public StampData stamp;
    public string frame_id;
}

[System.Serializable]
public class StampData
{
    public int sec;
    public int nanosec;
}

[System.Serializable]
public class PoseData
{
    public PositionData position;
    public OrientationData orientation;
}

[System.Serializable]
public class PositionData
{
    public double x, y, z;
}

[System.Serializable]
public class OrientationData
{
    public double x, y, z, w;
}
```

**推定時間**: 2-3時間

#### タスク3: ROS2カスタムメッセージ
**ファイル**: `~/thesis_work/ros2/ros2_ws/src/bunker_ros2/bunker_3d_nav/msg/Path3D.msg`

**内容**:
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

**推定時間**: 1時間

#### タスク4: Week 3完了レポート
**ファイル**: `~/thesis_work/documents/thesis/weekly_reports/week03.md`

**内容**:
- Week 3の達成内容
- 実装した機能リスト
- テスト結果
- パフォーマンス評価
- Week 4への展望

**推定時間**: 1-2時間

### 6.3 完了基準
- [ ] Unity統合が正常動作
- [ ] 経路可視化が正常動作
- [ ] ROS2カスタムメッセージが正常動作
- [ ] Week 3完了レポートが完成
- [ ] 統合テストが100%パス

### 6.4 推定所要時間
**合計**: 6-9時間

## 7. 全体進捗管理

### 7.1 進捗追跡
```python
# 進捗追跡スクリプト
def update_progress():
    progress = {
        'day9': {'status': 'completed', 'progress': 100},
        'day10': {'status': 'in_progress', 'progress': 0},
        'day11': {'status': 'pending', 'progress': 0},
        'day12': {'status': 'pending', 'progress': 0}
    }
    return progress
```

### 7.2 リスク管理
- **技術的リスク**: アルゴリズムの複雑さ
- **時間的リスク**: 実装時間の超過
- **統合リスク**: Unity連携の不具合

### 7.3 品質管理
- **コードレビュー**: 各タスク完了時に実施
- **テスト実行**: 継続的に実施
- **ドキュメント更新**: 実装と同時に更新

## 8. 成功指標

### 8.1 機能面
- [ ] A* 3Dアルゴリズムが正常動作
- [ ] コスト関数が正常動作
- [ ] 経路平滑化が正常動作
- [ ] Unity統合が正常動作

### 8.2 性能面
- [ ] 計算時間: 10秒以内
- [ ] メモリ使用量: 500MB以内
- [ ] 経路品質: 基準を満たす

### 8.3 統合面
- [ ] ROS2ノードとして動作
- [ ] Unity連携機能
- [ ] Rviz可視化対応

## 9. 次のステップ（Week 4）

### 9.1 Week 4の準備
- [ ] 実機テスト環境の準備
- [ ] パフォーマンス最適化
- [ ] ドキュメント整備
- [ ] 論文執筆準備

### 9.2 長期目標
- [ ] Month 1完了（Week 4終了時）
- [ ] 実機検証開始（Month 2）
- [ ] 論文執筆開始（Month 3）

---

**作成日**: 2025-10-11  
**更新日**: 2025-10-11  
**作成者**: AI研究アシスタント



