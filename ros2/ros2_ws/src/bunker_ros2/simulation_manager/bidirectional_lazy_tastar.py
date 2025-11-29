#!/usr/bin/env python3
"""
Bidirectional Lazy TA-A*

スタートとゴールから同時に探索することで高速化

アルゴリズムの流れ:
1. スタートから前方探索
2. ゴールから後方探索
3. 両者が出会ったら経路を統合
4. 地形評価（Lazy TA-A*と同様）

完全に独立した実装
"""
import heapq
import time
import math
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass
from enum import Enum

class SearchDirection(Enum):
    """探索方向"""
    FORWARD = 1   # スタートから
    BACKWARD = 2  # ゴールから

@dataclass
class Node:
    """3Dノード"""
    x: float
    y: float
    z: float
    g: float = float('inf')
    h: float = 0.0
    parent: Optional['Node'] = None
    direction: SearchDirection = SearchDirection.FORWARD
    
    @property
    def position(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)
    
    @property
    def f(self) -> float:
        return self.g + self.h
    
    def __lt__(self, other):
        return self.f < other.f

@dataclass
class PlanningResult:
    """経路計画結果"""
    success: bool
    path: List[Tuple[float, float, float]]
    computation_time: float
    path_length: float
    nodes_explored: int
    algorithm_name: str = "Bidirectional Lazy TA-A*"
    forward_nodes: int = 0
    backward_nodes: int = 0
    meeting_point: Optional[Tuple] = None
    error_message: str = ""

class BidirectionalLazyTAstar:
    """
    Bidirectional Lazy TA-A*
    
    両方向探索でLazy TA-A*をさらに高速化
    """
    
    def __init__(self, voxel_size: float = 0.5,
                 map_size: float = 50.0,
                 goal_threshold: float = 1.0):
        """初期化"""
        self.voxel_size = voxel_size
        self.map_size = map_size
        self.goal_threshold = goal_threshold
        
        self.min_pos = -map_size / 2
        self.max_pos = map_size / 2
        
        print(f"Bidirectional Lazy TA-A* initialized:")
        print(f"  voxel_size: {voxel_size}m")
        print(f"  map_size: {map_size}m")
        print(f"  goal_threshold: {goal_threshold}m")
    
    def plan_path(self, start: List[float], goal: List[float],
                  timeout: float = 300.0) -> PlanningResult:
        """
        双方向経路計画
        
        Args:
            start: スタート位置
            goal: ゴール位置
            timeout: タイムアウト[秒]
        
        Returns:
            PlanningResult
        """
        start_time = time.time()
        
        print(f"\n{'='*70}")
        print(f"Bidirectional Lazy TA-A* Planning")
        print(f"  Start: {start}")
        print(f"  Goal:  {goal}")
        print(f"  Timeout: {timeout}s")
        print(f"{'='*70}")
        
        # Phase 1: 双方向探索
        print("\n[Phase 1] Bidirectional search...")
        result = self._bidirectional_search(start, goal, timeout, start_time)
        
        if not result.success:
            print(f"  Phase 1 failed: {result.error_message}")
            return result
        
        print(f"  Phase 1 success: {result.computation_time:.2f}s")
        print(f"    Forward nodes: {result.forward_nodes}")
        print(f"    Backward nodes: {result.backward_nodes}")
        print(f"    Meeting point: {result.meeting_point}")
        
        # Phase 2: 地形評価
        print("\n[Phase 2] Evaluating terrain safety...")
        terrain_issues = self._evaluate_terrain(result.path)
        
        if not terrain_issues:
            print("  Phase 2: Path is safe!")
            return result
        
        print(f"  Phase 2: Found {len(terrain_issues)} terrain issues")
        
        # Phase 3: 地形考慮の再探索
        print("\n[Phase 3] Replanning with terrain awareness...")
        remaining_time = timeout - (time.time() - start_time)
        
        if remaining_time <= 0:
            result.success = False
            result.error_message = "Timeout before Phase 3"
            return result
        
        result = self._terrain_aware_search(
            start, goal, terrain_issues, remaining_time, start_time
        )
        
        return result
    
    def _bidirectional_search(self, start, goal, timeout, start_time) -> PlanningResult:
        """双方向探索"""
        # 前方探索の初期化
        forward_start = Node(start[0], start[1], start[2],
                           g=0, h=self._distance(start, goal),
                           direction=SearchDirection.FORWARD)
        
        forward_open = [(forward_start.f, id(forward_start), forward_start)]
        forward_closed: Set[Tuple] = set()
        forward_g_scores: Dict[Tuple, float] = {forward_start.position: 0}
        forward_came_from: Dict[Tuple, Node] = {}
        
        # 後方探索の初期化
        backward_start = Node(goal[0], goal[1], goal[2],
                            g=0, h=self._distance(goal, start),
                            direction=SearchDirection.BACKWARD)
        
        backward_open = [(backward_start.f, id(backward_start), backward_start)]
        backward_closed: Set[Tuple] = set()
        backward_g_scores: Dict[Tuple, float] = {backward_start.position: 0}
        backward_came_from: Dict[Tuple, Node] = {}
        
        forward_nodes = 0
        backward_nodes = 0
        
        # 最短経路の長さ（上限）
        best_path_length = float('inf')
        meeting_node = None
        
        while forward_open and backward_open:
            if time.time() - start_time > timeout:
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=time.time() - start_time,
                    path_length=0,
                    nodes_explored=forward_nodes + backward_nodes,
                    error_message="Timeout"
                )
            
            # 前方探索を1ステップ
            if forward_open:
                _, _, forward_current = heapq.heappop(forward_open)
                
                if forward_current.position not in forward_closed:
                    forward_nodes += 1
                    forward_closed.add(forward_current.position)
                    forward_came_from[forward_current.position] = forward_current
                    
                    # 後方探索と接続チェック
                    if forward_current.position in backward_closed:
                        path_length = (forward_current.g +
                                     backward_g_scores[forward_current.position])
                        
                        if path_length < best_path_length:
                            best_path_length = path_length
                            meeting_node = forward_current.position
                    
                    # 前方展開
                    for neighbor in self._get_neighbors(forward_current, goal, SearchDirection.FORWARD):
                        if neighbor.position in forward_closed:
                            continue
                        
                        if (neighbor.position not in forward_g_scores or
                            neighbor.g < forward_g_scores[neighbor.position]):
                            forward_g_scores[neighbor.position] = neighbor.g
                            heapq.heappush(forward_open,
                                         (neighbor.f, id(neighbor), neighbor))
            
            # 後方探索を1ステップ
            if backward_open:
                _, _, backward_current = heapq.heappop(backward_open)
                
                if backward_current.position not in backward_closed:
                    backward_nodes += 1
                    backward_closed.add(backward_current.position)
                    backward_came_from[backward_current.position] = backward_current
                    
                    # 前方探索と接続チェック
                    if backward_current.position in forward_closed:
                        path_length = (backward_current.g +
                                     forward_g_scores[backward_current.position])
                        
                        if path_length < best_path_length:
                            best_path_length = path_length
                            meeting_node = backward_current.position
                    
                    # 後方展開
                    for neighbor in self._get_neighbors(backward_current, start, SearchDirection.BACKWARD):
                        if neighbor.position in backward_closed:
                            continue
                        
                        if (neighbor.position not in backward_g_scores or
                            neighbor.g < backward_g_scores[neighbor.position]):
                            backward_g_scores[neighbor.position] = neighbor.g
                            heapq.heappush(backward_open,
                                         (neighbor.f, id(neighbor), neighbor))
            
            # 両方向が接続した
            if meeting_node is not None:
                # 経路を構築
                path = self._construct_bidirectional_path(
                    meeting_node,
                    forward_came_from,
                    backward_came_from
                )
                
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=self._path_length(path),
                    nodes_explored=forward_nodes + backward_nodes,
                    forward_nodes=forward_nodes,
                    backward_nodes=backward_nodes,
                    meeting_point=meeting_node
                )
        
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=forward_nodes + backward_nodes,
            error_message="No path found"
        )
    
    def _construct_bidirectional_path(self, meeting_point: Tuple,
                                     forward_came_from: Dict,
                                     backward_came_from: Dict) -> List[Tuple]:
        """双方向探索の経路を構築"""
        # 前方の経路（スタート → ミーティングポイント）
        forward_path = []
        current_pos = meeting_point
        
        while current_pos in forward_came_from:
            node = forward_came_from[current_pos]
            forward_path.append(node.position)
            current_pos = node.parent.position if node.parent else None
            if current_pos is None:
                break
        
        forward_path.reverse()
        
        # 後方の経路（ミーティングポイント → ゴール）
        backward_path = []
        current_pos = meeting_point
        
        while current_pos in backward_came_from:
            node = backward_came_from[current_pos]
            if node.position != meeting_point:
                backward_path.append(node.position)
            current_pos = node.parent.position if node.parent else None
            if current_pos is None:
                break
        
        # 統合
        full_path = forward_path + [meeting_point] + backward_path
        
        return full_path
    
    def _get_neighbors(self, node: Node, target: List[float],
                      direction: SearchDirection) -> List[Node]:
        """近傍ノード生成"""
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    nx = node.x + dx * self.voxel_size
                    ny = node.y + dy * self.voxel_size
                    nz = node.z + dz * self.voxel_size
                    
                    if not self._is_valid_position(nx, ny, nz):
                        continue
                    
                    distance = math.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
                    
                    g = node.g + distance
                    h = self._distance((nx, ny, nz), target)
                    
                    neighbor = Node(nx, ny, nz, g=g, h=h, parent=node,
                                  direction=direction)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _evaluate_terrain(self, path: List[Tuple]) -> List[Tuple]:
        """地形評価"""
        issues = []
        
        for i, pos in enumerate(path):
            x, y, z = pos
            
            if z < 0.0 or z > 2.0:
                issues.append(pos)
                continue
            
            if i > 0:
                prev_z = path[i-1][2]
                slope = abs(z - prev_z)
                
                if slope > 0.5:
                    issues.append(pos)
        
        return issues
    
    def _terrain_aware_search(self, start, goal, terrain_issues,
                             timeout, start_time) -> PlanningResult:
        """地形考慮の探索（双方向）"""
        # 実装は通常のLazy TA-A*のPhase 3と同様
        # 簡略化のため省略（必要に応じて追加）
        forbidden = set(terrain_issues)
        
        # 単方向探索で実装（簡易版）
        start_node = Node(start[0], start[1], start[2],
                         g=0, h=self._distance(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set: Set[Tuple] = set()
        g_scores = {start_node.position: 0}
        nodes_explored = 0
        
        while open_set:
            if time.time() - start_time > timeout:
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=time.time() - start_time,
                    path_length=0,
                    nodes_explored=nodes_explored,
                    error_message="Phase 3 timeout"
                )
            
            _, _, current = heapq.heappop(open_set)
            
            if current.position in closed_set:
                continue
            
            nodes_explored += 1
            
            if self._is_goal(current.position, goal):
                path = self._reconstruct_path(current)
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=self._path_length(path),
                    nodes_explored=nodes_explored
                )
            
            closed_set.add(current.position)
            
            for neighbor in self._get_neighbors_terrain_aware(current, goal, forbidden):
                if neighbor.position in closed_set:
                    continue
                
                if (neighbor.position not in g_scores or
                    neighbor.g < g_scores[neighbor.position]):
                    g_scores[neighbor.position] = neighbor.g
                    heapq.heappush(open_set, (neighbor.f, id(neighbor), neighbor))
        
        return PlanningResult(
            success=False,
            path=[],
            computation_time=time.time() - start_time,
            path_length=0,
            nodes_explored=nodes_explored,
            error_message="No path found in Phase 3"
        )
    
    def _get_neighbors_terrain_aware(self, node: Node, goal: List[float],
                                    forbidden: Set[Tuple]) -> List[Node]:
        """地形考慮の近傍生成"""
        neighbors = []
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    nx = node.x + dx * self.voxel_size
                    ny = node.y + dy * self.voxel_size
                    nz = node.z + dz * self.voxel_size
                    
                    if not self._is_valid_position(nx, ny, nz):
                        continue
                    
                    pos = (nx, ny, nz)
                    
                    distance = math.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
                    terrain_cost = 10.0 if pos in forbidden else 0.0
                    
                    if nz > 1.0:
                        terrain_cost += abs(nz - 0.2) * 0.5
                    
                    slope = abs(nz - node.z)
                    if slope > 0.3:
                        terrain_cost += slope * 2.0
                    
                    total_cost = distance + terrain_cost
                    
                    g = node.g + total_cost
                    h = self._distance((nx, ny, nz), goal)
                    
                    neighbor = Node(nx, ny, nz, g=g, h=h, parent=node)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _is_valid_position(self, x: float, y: float, z: float) -> bool:
        """位置の妥当性チェック"""
        return (self.min_pos <= x <= self.max_pos and
                self.min_pos <= y <= self.max_pos and
                -0.5 <= z <= 3.0)
    
    def _is_goal(self, pos: Tuple, goal: List[float]) -> bool:
        """ゴール判定"""
        return self._distance(pos, goal) <= self.goal_threshold
    
    def _distance(self, pos1, pos2) -> float:
        """ユークリッド距離"""
        return math.sqrt(
            (pos1[0] - pos2[0])**2 +
            (pos1[1] - pos2[1])**2 +
            (pos1[2] - pos2[2])**2
        )
    
    def _reconstruct_path(self, node: Node) -> List[Tuple]:
        """経路再構築"""
        path = []
        current = node
        while current is not None:
            path.append(current.position)
            current = current.parent
        return list(reversed(path))
    
    def _path_length(self, path: List[Tuple]) -> float:
        """経路長計算"""
        if len(path) < 2:
            return 0.0
        
        length = 0.0
        for i in range(len(path) - 1):
            length += self._distance(path[i], path[i+1])
        
        return length

# テスト
if __name__ == '__main__':
    print("="*70)
    print("Bidirectional Lazy TA-A* Test")
    print("="*70)
    
    planner = BidirectionalLazyTAstar(voxel_size=0.5, map_size=50.0)
    
    test_cases = [
        {'name': 'Short', 'start': [0, 0, 0.2], 'goal': [10, 10, 0.2]},
        {'name': 'Medium', 'start': [0, 0, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'Long', 'start': [-20, -20, 0.2], 'goal': [20, 20, 0.2]},
        {'name': 'L-Shape', 'start': [0, 0, 0.2], 'goal': [0, 20, 0.2]},
    ]
    
    for test in test_cases:
        print(f"\n{'='*70}")
        print(f"Test: {test['name']}")
        
        result = planner.plan_path(test['start'], test['goal'], timeout=60)
        
        if result.success:
            print(f"✅ SUCCESS")
            print(f"  Time: {result.computation_time:.3f}s")
            print(f"  Path length: {result.path_length:.2f}m")
            print(f"  Nodes explored: {result.nodes_explored}")
            if result.forward_nodes > 0:
                print(f"    Forward: {result.forward_nodes}")
                print(f"    Backward: {result.backward_nodes}")
        else:
            print(f"❌ FAILED: {result.error_message}")


