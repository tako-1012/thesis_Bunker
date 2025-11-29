#!/usr/bin/env python3
"""
Lazy TA-A* (Lazy Terrain-Aware A*)

地形評価を遅延させることで高速化を実現

アルゴリズムの流れ:
1. Phase 1: 距離のみで高速探索（地形無視）
2. Phase 2: 見つかった経路の地形評価
3. Phase 3: 問題があれば地形コストを加えて再探索

完全に独立した実装 - 他のファイルに依存しない
"""
import heapq
import time
import math
from typing import List, Tuple, Optional, Dict, Set
from dataclasses import dataclass

@dataclass
class Node:
    """3Dノード"""
    x: float
    y: float
    z: float
    g: float = float('inf')  # スタートからのコスト
    h: float = 0.0           # ゴールまでの推定コスト
    parent: Optional['Node'] = None
    
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
    algorithm_name: str = "Lazy TA-A*"
    phase_used: int = 1  # どのPhaseで成功したか
    error_message: str = ""

class LazyTAstar:
    """
    Lazy Terrain-Aware A*
    
    3つのPhaseで段階的に探索：
    - Phase 1: 地形無視（超高速）
    - Phase 2: 地形評価
    - Phase 3: 地形考慮の再探索
    """
    
    def __init__(self, voxel_size: float = 0.5, 
                 map_size: float = 50.0,
                 goal_threshold: float = 1.0):
        """
        初期化
        
        Args:
            voxel_size: ボクセルサイズ[m]
            map_size: マップサイズ[m]
            goal_threshold: ゴール判定の閾値[m]
        """
        self.voxel_size = voxel_size
        self.map_size = map_size
        self.goal_threshold = goal_threshold
        
        # 探索範囲
        self.min_pos = -map_size / 2
        self.max_pos = map_size / 2
        
        print(f"Lazy TA-A* initialized:")
        print(f"  voxel_size: {voxel_size}m")
        print(f"  map_size: {map_size}m")
        print(f"  goal_threshold: {goal_threshold}m")
    
    def plan_path(self, start: List[float], goal: List[float],
                  timeout: float = 300.0) -> PlanningResult:
        """
        経路計画（3-Phase Lazy評価）
        
        Args:
            start: スタート位置 [x, y, z]
            goal: ゴール位置 [x, y, z]
            timeout: タイムアウト[秒]
        
        Returns:
            PlanningResult
        """
        start_time = time.time()
        
        print(f"\n{'='*70}")
        print(f"Lazy TA-A* Planning")
        print(f"  Start: {start}")
        print(f"  Goal:  {goal}")
        print(f"  Timeout: {timeout}s")
        print(f"{'='*70}")
        
        # Phase 1: 地形無視の高速探索
        print("\n[Phase 1] Fast search without terrain...")
        result = self._phase1_fast_search(start, goal, timeout, start_time)
        
        if not result.success:
            print(f"  Phase 1 failed: {result.error_message}")
            return result
        
        print(f"  Phase 1 success: {result.computation_time:.2f}s, {len(result.path)} waypoints")
        
        # Phase 2: 経路の地形評価
        print("\n[Phase 2] Evaluating terrain safety...")
        terrain_issues = self._phase2_evaluate_terrain(result.path)
        
        if not terrain_issues:
            print("  Phase 2: Path is safe! (no terrain issues)")
            result.phase_used = 2
            return result
        
        print(f"  Phase 2: Found {len(terrain_issues)} terrain issues")
        
        # Phase 3: 地形考慮の再探索
        print("\n[Phase 3] Replanning with terrain awareness...")
        remaining_time = timeout - (time.time() - start_time)
        
        if remaining_time <= 0:
            result.success = False
            result.error_message = "Timeout before Phase 3"
            return result
        
        result = self._phase3_terrain_aware_search(
            start, goal, terrain_issues, remaining_time, start_time
        )
        
        if result.success:
            print(f"  Phase 3 success: {result.computation_time:.2f}s")
            result.phase_used = 3
        else:
            print(f"  Phase 3 failed: {result.error_message}")
        
        return result
    
    def _phase1_fast_search(self, start, goal, timeout, start_time) -> PlanningResult:
        """Phase 1: 地形無視の高速探索"""
        start_node = Node(start[0], start[1], start[2], 
                         g=0, h=self._distance(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set: Set[Tuple] = set()
        g_scores: Dict[Tuple, float] = {start_node.position: 0}
        nodes_explored = 0
        
        while open_set:
            if time.time() - start_time > timeout:
                return PlanningResult(
                    success=False,
                    path=[],
                    computation_time=time.time() - start_time,
                    path_length=0,
                    nodes_explored=nodes_explored,
                    error_message="Phase 1 timeout"
                )
            
            _, _, current = heapq.heappop(open_set)
            
            if current.position in closed_set:
                continue
            
            nodes_explored += 1
            
            # ゴール判定
            if self._is_goal(current.position, goal):
                path = self._reconstruct_path(current)
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=self._path_length(path),
                    nodes_explored=nodes_explored,
                    phase_used=1
                )
            
            closed_set.add(current.position)
            
            # 近傍展開（地形コストなし）
            for neighbor in self._get_neighbors_phase1(current, goal):
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
            error_message="Phase 1: No path found"
        )
    
    def _get_neighbors_phase1(self, node: Node, goal: List[float]) -> List[Node]:
        """Phase 1の近傍ノード生成（地形コストなし）"""
        neighbors = []
        
        # 26近傍
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                for dz in [-1, 0, 1]:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    
                    nx = node.x + dx * self.voxel_size
                    ny = node.y + dy * self.voxel_size
                    nz = node.z + dz * self.voxel_size
                    
                    # 境界チェック
                    if not self._is_valid_position(nx, ny, nz):
                        continue
                    
                    # コスト = 距離のみ（地形無視）
                    distance = math.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
                    
                    g = node.g + distance
                    h = self._distance((nx, ny, nz), goal)
                    
                    neighbor = Node(nx, ny, nz, g=g, h=h, parent=node)
                    neighbors.append(neighbor)
        
        return neighbors
    
    def _phase2_evaluate_terrain(self, path: List[Tuple]) -> List[Tuple]:
        """
        Phase 2: 経路の地形評価
        
        Returns:
            問題のある位置のリスト
        """
        issues = []
        
        for i, pos in enumerate(path):
            x, y, z = pos
            
            # 地形評価（簡易版）
            # 実際の実装では詳細な地形データを使用
            
            # 1. 高度チェック
            if z < 0.0:
                issues.append(pos)
                continue
            
            if z > 2.0:
                issues.append(pos)
                continue
            
            # 2. 急な傾斜チェック
            if i > 0:
                prev_z = path[i-1][2]
                slope = abs(z - prev_z)
                
                if slope > 0.5:  # 0.5m以上の高度変化
                    issues.append(pos)
        
        return issues
    
    def _phase3_terrain_aware_search(self, start, goal, terrain_issues,
                                     timeout, start_time) -> PlanningResult:
        """Phase 3: 地形考慮の再探索"""
        # 問題のある位置を避けるようにコストを設定
        forbidden_positions = set(terrain_issues)
        
        start_node = Node(start[0], start[1], start[2],
                         g=0, h=self._distance(start, goal))
        
        open_set = [(start_node.f, id(start_node), start_node)]
        closed_set: Set[Tuple] = set()
        g_scores: Dict[Tuple, float] = {start_node.position: 0}
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
            
            # ゴール判定
            if self._is_goal(current.position, goal):
                path = self._reconstruct_path(current)
                return PlanningResult(
                    success=True,
                    path=path,
                    computation_time=time.time() - start_time,
                    path_length=self._path_length(path),
                    nodes_explored=nodes_explored,
                    phase_used=3
                )
            
            closed_set.add(current.position)
            
            # 近傍展開（地形コスト考慮）
            for neighbor in self._get_neighbors_phase3(current, goal, forbidden_positions):
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
            error_message="Phase 3: No path found"
        )
    
    def _get_neighbors_phase3(self, node: Node, goal: List[float],
                              forbidden: Set[Tuple]) -> List[Node]:
        """Phase 3の近傍ノード生成（地形コスト考慮）"""
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
                    
                    # 基本距離コスト
                    distance = math.sqrt(dx*dx + dy*dy + dz*dz) * self.voxel_size
                    
                    # 地形コスト
                    terrain_cost = 0.0
                    
                    # 問題のある位置は高コスト
                    if pos in forbidden:
                        terrain_cost = 10.0
                    
                    # 高度コスト
                    if nz > 1.0:
                        terrain_cost += abs(nz - 0.2) * 0.5
                    
                    # 傾斜コスト
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
        if x < self.min_pos or x > self.max_pos:
            return False
        if y < self.min_pos or y > self.max_pos:
            return False
        if z < -0.5 or z > 3.0:
            return False
        return True
    
    def _is_goal(self, pos: Tuple, goal: List[float]) -> bool:
        """ゴール判定"""
        distance = self._distance(pos, goal)
        return distance <= self.goal_threshold
    
    def _distance(self, pos1, pos2) -> float:
        """ユークリッド距離"""
        return math.sqrt(
            (pos1[0] - pos2[0])**2 +
            (pos1[1] - pos2[1])**2 +
            (pos1[2] - pos2[2])**2
        )
    
    def _reconstruct_path(self, node: Node) -> List[Tuple]:
        """経路を再構築"""
        path = []
        current = node
        while current is not None:
            path.append(current.position)
            current = current.parent
        return list(reversed(path))
    
    def _path_length(self, path: List[Tuple]) -> float:
        """経路長を計算"""
        if len(path) < 2:
            return 0.0
        
        length = 0.0
        for i in range(len(path) - 1):
            length += self._distance(path[i], path[i+1])
        
        return length

# テスト
if __name__ == '__main__':
    print("="*70)
    print("Lazy TA-A* Test")
    print("="*70)
    
    planner = LazyTAstar(voxel_size=0.5, map_size=50.0, goal_threshold=1.0)
    
    test_cases = [
        {
            'name': 'Short distance',
            'start': [0, 0, 0.2],
            'goal': [10, 10, 0.2]
        },
        {
            'name': 'Medium distance',
            'start': [0, 0, 0.2],
            'goal': [20, 20, 0.2]
        },
        {
            'name': 'Long distance',
            'start': [-20, -20, 0.2],
            'goal': [20, 20, 0.2]
        }
    ]
    
    for test in test_cases:
        print(f"\n{'='*70}")
        print(f"Test: {test['name']}")
        print(f"{'='*70}")
        
        result = planner.plan_path(test['start'], test['goal'], timeout=60)
        
        if result.success:
            print(f"\n✅ SUCCESS")
            print(f"  Phase: {result.phase_used}")
            print(f"  Time: {result.computation_time:.2f}s")
            print(f"  Path length: {result.path_length:.2f}m")
            print(f"  Nodes explored: {result.nodes_explored}")
            print(f"  Waypoints: {len(result.path)}")
        else:
            print(f"\n❌ FAILED")
            print(f"  Error: {result.error_message}")
            print(f"  Time: {result.computation_time:.2f}s")
    
    print(f"\n{'='*70}")
    print("Test complete!")
    print(f"{'='*70}")


