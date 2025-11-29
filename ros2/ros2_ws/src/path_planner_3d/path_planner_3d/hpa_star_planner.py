import numpy as np
from typing import List, Optional, Tuple, Dict, Set
import heapq
from dataclasses import dataclass, field
import time
from collections import deque

@dataclass
class Cluster:
    """クラスタ（マップの部分領域）"""
    id: int
    x_min: int
    y_min: int
    x_max: int
    y_max: int
    entrances: List[Tuple[int, int, int]] = None

@dataclass
class AbstractNode:
    """抽象グラフのノード"""
    position: Tuple[int, int, int]
    cluster_id: int
    neighbors: Dict['AbstractNode', float] = field(default_factory=dict)
    
    def __hash__(self):
        return hash(self.position)
    
    def __eq__(self, other):
        return self.position == other.position

class HPAStarPlanner:
    def __init__(self,
                 start: np.ndarray,
                 goal: np.ndarray,
                 bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
                 terrain_cost_map: Optional[np.ndarray] = None,
                 resolution: float = 0.1,
                 cluster_size: int = 50):
        self.start = start
        self.goal = goal
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.cluster_size = cluster_size
    
    def plan(self) -> Optional[List[np.ndarray]]:
        """メイン経路計画関数"""
        clusters = self.build_clusters()
        # print(f"  [DEBUG] Clusters: {len(clusters)}")
        total_entrances = 0
        for cluster in clusters:
            cluster.entrances = self.find_entrances(cluster)
            total_entrances += len(cluster.entrances)
        # print(f"  [DEBUG] Total entrances: {total_entrances}")
        abstract_graph = self.build_abstract_graph(clusters)
        # print(f"  [DEBUG] Abstract graph nodes: {len(abstract_graph)}")
        total_edges = sum(len(node.neighbors) for node in abstract_graph.values()) // 2
        # print(f"  [DEBUG] Total edges in abstract graph: {total_edges}")
        start_grid = self.world_to_grid(self.start)
        goal_grid = self.world_to_grid(self.goal)
        start_node = self.add_temp_node(start_grid, clusters, abstract_graph)
        goal_node = self.add_temp_node(goal_grid, clusters, abstract_graph)
        if start_node is None or goal_node is None:
            return None
        # print(f"  [DEBUG] Start node connections: {len(start_node.neighbors)}")
        # print(f"  [DEBUG] Goal node connections: {len(goal_node.neighbors)}")
        abstract_path = self.abstract_search(start_node, goal_node, abstract_graph)
        if abstract_path is None:
            # print(f"  [DEBUG] No abstract path found.")
            # self._debug_connectivity(abstract_graph, start_node, goal_node)
            return None
        # print(f"  [DEBUG] Abstract path found: {len(abstract_path)} nodes")
        detailed_path = self.refine_path(abstract_path)
        path_world = [self.grid_to_world(p) for p in detailed_path]
        return path_world
    
    def build_clusters(self) -> List[Cluster]:
        """マップをクラスタに分割"""
        if self.terrain_cost_map is None:
            height, width = 100, 100
        else:
            height, width = self.terrain_cost_map.shape
        
        clusters = []
        cluster_id = 0
        
        for y in range(0, height, self.cluster_size):
            for x in range(0, width, self.cluster_size):
                x_max = min(x + self.cluster_size, width)
                y_max = min(y + self.cluster_size, height)
                
                cluster = Cluster(
                    id=cluster_id,
                    x_min=x,
                    y_min=y,
                    x_max=x_max,
                    y_max=y_max
                )
                clusters.append(cluster)
                cluster_id += 1
        
        return clusters
    
    def find_entrances(self, cluster: Cluster) -> List[Tuple[int, int, int]]:
        """クラスタの境界で通行可能なエントランスを抽出"""
        entrances = []
        
        if self.terrain_cost_map is None:
            return entrances
        
        height, width = self.terrain_cost_map.shape
        
        for x in range(cluster.x_min, cluster.x_max):
            if cluster.y_min > 0 and self.is_passable(x, cluster.y_min):
                entrances.append((x, cluster.y_min, 0))
            if cluster.y_max < height and self.is_passable(x, min(cluster.y_max - 1, height - 1)):
                entrances.append((x, min(cluster.y_max - 1, height - 1), 0))
        
        for y in range(cluster.y_min, cluster.y_max):
            if cluster.x_min > 0 and self.is_passable(cluster.x_min, y):
                entrances.append((cluster.x_min, y, 0))
            if cluster.x_max < width and self.is_passable(min(cluster.x_max - 1, width - 1), y):
                entrances.append((min(cluster.x_max - 1, width - 1), y, 0))
        
        return entrances
    
    def is_passable(self, x: int, y: int) -> bool:
        """通行可能かチェック"""
        if self.terrain_cost_map is None:
            return True
        
        height, width = self.terrain_cost_map.shape
        if not (0 <= x < width and 0 <= y < height):
            return False
        
        return self.terrain_cost_map[y, x] < 0.8
    
    def build_abstract_graph(self, clusters: List[Cluster]) -> Dict[Tuple[int, int, int], AbstractNode]:
        """抽象グラフを構築"""
        abstract_graph = {}
        
        for cluster in clusters:
            if cluster.entrances is None:
                continue
            for entrance in cluster.entrances:
                node = AbstractNode(
                    position=entrance,
                    cluster_id=cluster.id,
                    neighbors={}
                )
                abstract_graph[entrance] = node
        
        for cluster in clusters:
            if cluster.entrances is None or len(cluster.entrances) < 2:
                continue
            
            entrances = cluster.entrances
            for i, e1 in enumerate(entrances):
                for e2 in entrances[i+1:]:
                    cost = self.intra_cluster_cost(e1, e2)
                    if cost is not None and cost < float('inf'):
                        abstract_graph[e1].neighbors[abstract_graph[e2]] = cost
                        abstract_graph[e2].neighbors[abstract_graph[e1]] = cost
        
        self._connect_inter_cluster_entrances(clusters, abstract_graph)
        
        return abstract_graph
    
    def _connect_inter_cluster_entrances(self, clusters: List[Cluster], abstract_graph: Dict):
        """隣接クラスタ間のエントランスを接続"""
        inter_cluster_edges = 0
        for i, cluster1 in enumerate(clusters):
            for cluster2 in clusters[i+1:]:
                if not self._are_adjacent(cluster1, cluster2):
                    continue
                if cluster1.entrances is None or cluster2.entrances is None:
                    continue
                for e1 in cluster1.entrances:
                    for e2 in cluster2.entrances:
                        if self._are_boundary_neighbors(e1, e2, cluster1, cluster2):
                            x1, y1, _ = e1
                            x2, y2, _ = e2
                            distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2) * self.resolution
                            if distance < 5.0 * self.resolution:
                                cost = distance
                                if self.terrain_cost_map is not None:
                                    avg_cost = (self.terrain_cost_map[y1, x1] + self.terrain_cost_map[y2, x2]) / 2.0
                                    cost *= (1.0 + avg_cost)
                                abstract_graph[e1].neighbors[abstract_graph[e2]] = cost
                                abstract_graph[e2].neighbors[abstract_graph[e1]] = cost
                                inter_cluster_edges += 1
        # print(f"  [DEBUG] Inter-cluster edges added: {inter_cluster_edges}")
    
    def _are_adjacent(self, cluster1: Cluster, cluster2: Cluster) -> bool:
        """2つのクラスタが隣接しているか判定"""
        if (cluster1.x_max == cluster2.x_min or cluster2.x_max == cluster1.x_min):
            if not (cluster1.y_max <= cluster2.y_min or cluster2.y_max <= cluster1.y_min):
                return True
        
        if (cluster1.y_max == cluster2.y_min or cluster2.y_max == cluster1.y_min):
            if not (cluster1.x_max <= cluster2.x_min or cluster2.x_max <= cluster1.x_min):
                return True
        
        return False
    
    def _are_boundary_neighbors(self, e1: Tuple[int, int, int], e2: Tuple[int, int, int],
                                cluster1: Cluster, cluster2: Cluster) -> bool:
        """境界上で隣接しているか判定"""
        x1, y1, _ = e1
        x2, y2, _ = e2
        
        if cluster1.x_max == cluster2.x_min:
            if x1 == cluster1.x_max - 1 and x2 == cluster2.x_min and abs(y1 - y2) <= 3:
                return True
        
        if cluster2.x_max == cluster1.x_min:
            if x2 == cluster2.x_max - 1 and x1 == cluster1.x_min and abs(y1 - y2) <= 3:
                return True
        
        if cluster1.y_max == cluster2.y_min:
            if y1 == cluster1.y_max - 1 and y2 == cluster2.y_min and abs(x1 - x2) <= 3:
                return True
        
        if cluster2.y_max == cluster1.y_min:
            if y2 == cluster2.y_max - 1 and y1 == cluster1.y_min and abs(x1 - x2) <= 3:
                return True
        
        return False
    
    def intra_cluster_cost(self, pos1: Tuple[int, int, int], pos2: Tuple[int, int, int]) -> Optional[float]:
        """クラスタ内の移動コスト"""
        x1, y1, _ = pos1
        x2, y2, _ = pos2
        
        distance = np.sqrt((x2 - x1)**2 + (y2 - y1)**2) * self.resolution
        
        if self.terrain_cost_map is not None:
            avg_cost = (self.terrain_cost_map[y1, x1] + self.terrain_cost_map[y2, x2]) / 2.0
            return distance * (1.0 + avg_cost)
        else:
            return distance
    
    def abstract_search(self, start_node: AbstractNode, goal_node: AbstractNode, 
                       abstract_graph: Dict) -> Optional[List[AbstractNode]]:
        """
        抽象グラフでA*探索
        修正: heapqでの比較エラーを回避
        """
        counter = 0
        pq = [(0.0, counter, start_node)]
        visited = set()
        cost_so_far = {start_node: 0.0}
        came_from = {}
        while pq:
            current_cost, _, current = heapq.heappop(pq)
            if current in visited:
                continue
            visited.add(current)
            if current == goal_node:
                path = []
                node = goal_node
                while node in came_from:
                    path.append(node)
                    node = came_from[node]
                path.append(start_node)
                return list(reversed(path))
            for neighbor, edge_cost in current.neighbors.items():
                new_cost = current_cost + edge_cost
                if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = new_cost
                    h = np.linalg.norm(np.array(neighbor.position[:2]) - np.array(goal_node.position[:2])) * self.resolution
                    counter += 1
                    heapq.heappush(pq, (new_cost + h, counter, neighbor))
                    came_from[neighbor] = current
        return None
    
    def refine_path(self, abstract_path: List[AbstractNode]) -> List[Tuple[int, int, int]]:
        """抽象経路を詳細経路に変換"""
        return [node.position for node in abstract_path]
    
    def add_temp_node(self, position: Tuple[int, int, int], clusters: List[Cluster], 
                     abstract_graph: Dict) -> Optional[AbstractNode]:
        """一時ノード（始点・終点）を追加"""
        x, y, _ = position
        cluster_id = None
        for cluster in clusters:
            if (cluster.x_min <= x < cluster.x_max and cluster.y_min <= y < cluster.y_max):
                cluster_id = cluster.id
                break
        
        if cluster_id is None:
            return None
        
        temp_node = AbstractNode(position=position, cluster_id=cluster_id, neighbors={})
        
        for node_pos, node in abstract_graph.items():
            if node.cluster_id == cluster_id:
                cost = self.intra_cluster_cost(position, node_pos)
                if cost is not None:
                    temp_node.neighbors[node] = cost
                    node.neighbors[temp_node] = cost
        
        abstract_graph[position] = temp_node
        return temp_node
    
    def _debug_connectivity(self, abstract_graph: Dict, start_node: AbstractNode, goal_node: AbstractNode):
        """グラフの連結性をデバッグ"""
        visited = set()
        queue = deque([start_node])
        visited.add(start_node)
        
        while queue:
            node = queue.popleft()
            for neighbor in node.neighbors.keys():
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        
        print(f"  [DEBUG] Nodes reachable from start: {len(visited)}/{len(abstract_graph)}")
        print(f"  [DEBUG] Goal reachable from start: {goal_node in visited}")
    
    def world_to_grid(self, world_pos: np.ndarray) -> Tuple[int, int, int]:
        """世界座標 -> グリッド座標"""
        origin_x = self.bounds[0][0]
        origin_y = self.bounds[1][0]
        grid_x = int((world_pos[0] - origin_x) / self.resolution)
        grid_y = int((world_pos[1] - origin_y) / self.resolution)
        return (grid_x, grid_y, 0)
    
    def grid_to_world(self, grid_pos: Tuple[int, int, int]) -> np.ndarray:
        """グリッド座標 -> 世界座標"""
        origin_x = self.bounds[0][0]
        origin_y = self.bounds[1][0]
        world_x = grid_pos[0] * self.resolution + origin_x
        world_y = grid_pos[1] * self.resolution + origin_y
        return np.array([world_x, world_y, 0.0])


if __name__ == '__main__':
    cost_map = np.ones((200, 200), dtype=np.float32) * 0.3
    cost_map[80:120, 0:200] = 0.1
    
    start = np.array([2.0, 5.0, 0.0])
    goal = np.array([18.0, 15.0, 0.0])
    bounds = ((-1.0, 21.0), (-1.0, 21.0), (0.0, 2.0))
    
    planner = HPAStarPlanner(
        start=start, goal=goal, bounds=bounds,
        terrain_cost_map=cost_map, resolution=0.1, cluster_size=50
    )
    
    print("Planning with HPA*...")
    start_time = time.time()
    path = planner.plan()
    elapsed = time.time() - start_time
    
    if path:
        print(f"✓ Path found in {elapsed:.2f}s")
        print(f"  Waypoints: {len(path)}")
        total_dist = sum(np.linalg.norm(path[i+1] - path[i]) for i in range(len(path)-1))
        print(f"  Distance: {total_dist:.2f}m")
    else:
        print(f"✗ Path not found after {elapsed:.2f}s")
