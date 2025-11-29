"""
代表的地形マップ生成器

5つの地形タイプを高品質で設計し、
各地形内でランダムにスタート/ゴールを配置

方針：ランダム地形生成ではなく、
      数個の高品質地形マップを設計し、
      各マップ内でスタート/ゴールをランダム化

利点：地形品質の保証、再現性、統計的有意性
"""

import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Dict
from dataclasses import dataclass
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

@dataclass
class TerrainMap:
    """地形マップ"""
    name: str
    description: str
    size: float  # マップサイズ [m]
    terrain_type: str
    height_map: np.ndarray  # 高さマップ
    obstacle_map: np.ndarray  # 障害物マップ（True=障害物）
    max_slope: float  # 最大勾配 [度]

class RepresentativeTerrainGenerator:
    """代表的地形生成器"""
    
    def __init__(self, map_size=50.0, resolution=0.5):
        """
        Args:
            map_size: マップの一辺 [m]
            resolution: グリッド解像度 [m]
        """
        self.map_size = map_size
        self.resolution = resolution
        self.grid_size = int(map_size / resolution)
        
        print(f"Map size: {map_size}m × {map_size}m")
        print(f"Grid size: {self.grid_size} × {self.grid_size}")
    
    def generate_flat_agricultural_field(self) -> TerrainMap:
        """
        平坦地形マップ（農地）
        
        特徴：
        - ほぼ平坦（勾配0-5度）
        - 障害物なし
        - 最も簡単
        """
        height_map = np.zeros((self.grid_size, self.grid_size))
        
        # わずかな起伏を追加（リアルさのため）
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                # 緩やかな波
                height_map[i, j] = 0.1 * np.sin(i * 0.1) * np.cos(j * 0.1)
        
        # 障害物なし
        obstacle_map = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        
        return TerrainMap(
            name="Flat Agricultural Field",
            description="平坦な農地。障害物なし、勾配0-5度",
            size=self.map_size,
            terrain_type="Flat Terrain",
            height_map=height_map,
            obstacle_map=obstacle_map,
            max_slope=5.0
        )
    
    def generate_gentle_hills(self) -> TerrainMap:
        """
        緩傾斜地形（丘陵）
        
        特徴：
        - 緩やかな丘（勾配5-15度）
        - 少ない障害物
        - 中程度の難易度
        """
        height_map = np.zeros((self.grid_size, self.grid_size))
        
        # 複数の丘を配置
        num_hills = 3
        np.random.seed(42)  # 再現性のため
        for _ in range(num_hills):
            center_x = np.random.randint(20, self.grid_size - 20)
            center_y = np.random.randint(20, self.grid_size - 20)
            radius = np.random.uniform(15, 25)
            peak_height = np.random.uniform(2.0, 4.0)
            
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    dist = np.sqrt((i - center_x)**2 + (j - center_y)**2)
                    if dist < radius:
                        height = peak_height * (1 - (dist / radius)**2)
                        height_map[i, j] += height
        
        # 少ない障害物（木など）
        obstacle_map = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        num_obstacles = 20
        np.random.seed(43)  # 再現性のため
        for _ in range(num_obstacles):
            x = np.random.randint(0, self.grid_size)
            y = np.random.randint(0, self.grid_size)
            obstacle_map[x, y] = True
        
        return TerrainMap(
            name="Gentle Hills",
            description="緩やかな丘陵地。勾配5-15度、少ない障害物",
            size=self.map_size,
            terrain_type="Gentle Slope",
            height_map=height_map,
            obstacle_map=obstacle_map,
            max_slope=15.0
        )
    
    def generate_steep_terrain(self) -> TerrainMap:
        """
        急傾斜地形（山地）
        
        特徴：
        - 急な勾配（15-30度）
        - 中程度の障害物
        - 難易度高
        """
        height_map = np.zeros((self.grid_size, self.grid_size))
        
        # 中央に急峻な山を配置
        center_x = self.grid_size // 2
        center_y = self.grid_size // 2
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                dist = np.sqrt((i - center_x)**2 + (j - center_y)**2)
                max_dist = self.grid_size / 2
                
                if dist < max_dist:
                    # 急峻な山（指数関数的に高くなる）
                    height = 8.0 * (1 - (dist / max_dist)**0.5)
                    height_map[i, j] = max(0, height)
        
        # 中程度の障害物（岩など）
        obstacle_map = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        num_obstacles = 50
        np.random.seed(44)  # 再現性のため
        for _ in range(num_obstacles):
            x = np.random.randint(0, self.grid_size)
            y = np.random.randint(0, self.grid_size)
            # 山の中腹に多く配置
            dist = np.sqrt((x - center_x)**2 + (y - center_y)**2)
            if dist < max_dist * 0.7:
                obstacle_map[x, y] = True
        
        return TerrainMap(
            name="Steep Terrain",
            description="急峻な山地。勾配15-30度、中程度の障害物",
            size=self.map_size,
            terrain_type="Steep Slope",
            height_map=height_map,
            obstacle_map=obstacle_map,
            max_slope=30.0
        )
    
    def generate_complex_obstacles(self) -> TerrainMap:
        """
        複雑地形（障害物多数）
        
        特徴：
        - 変化に富む地形
        - 多数の障害物（瓦礫、建物）
        - 難易度非常に高
        """
        height_map = np.zeros((self.grid_size, self.grid_size))
        
        # ランダムな凹凸
        np.random.seed(45)  # 再現性のため
        for _ in range(20):
            x = np.random.randint(5, self.grid_size - 5)
            y = np.random.randint(5, self.grid_size - 5)
            radius = np.random.uniform(3, 8)
            height_change = np.random.uniform(-2, 3)
            
            for i in range(max(0, x-10), min(self.grid_size, x+10)):
                for j in range(max(0, y-10), min(self.grid_size, y+10)):
                    dist = np.sqrt((i - x)**2 + (j - y)**2)
                    if dist < radius:
                        height_map[i, j] += height_change * (1 - dist/radius)
        
        # 多数の障害物（瓦礫、建物）
        obstacle_map = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        
        # 建物群（5×5のブロック）
        num_buildings = 10
        np.random.seed(46)  # 再現性のため
        for _ in range(num_buildings):
            x = np.random.randint(0, self.grid_size - 5)
            y = np.random.randint(0, self.grid_size - 5)
            obstacle_map[x:x+5, y:y+5] = True
        
        # ランダムな瓦礫
        num_debris = 100
        np.random.seed(47)  # 再現性のため
        for _ in range(num_debris):
            x = np.random.randint(0, self.grid_size)
            y = np.random.randint(0, self.grid_size)
            obstacle_map[x, y] = True
        
        return TerrainMap(
            name="Complex Obstacles",
            description="複雑な障害物地形。瓦礫、建物多数",
            size=self.map_size,
            terrain_type="Obstacle Field",
            height_map=height_map,
            obstacle_map=obstacle_map,
            max_slope=20.0
        )
    
    def generate_extreme_hazards(self) -> TerrainMap:
        """
        極端地形（崖・峡谷）
        
        特徴：
        - 非常に急な勾配（30-45度）
        - 崖、峡谷
        - 最高難易度
        """
        height_map = np.zeros((self.grid_size, self.grid_size))
        
        # 中央に峡谷を作成
        canyon_center = self.grid_size // 2
        
        for i in range(self.grid_size):
            dist_from_canyon = abs(i - canyon_center)
            
            if dist_from_canyon < 10:
                # 峡谷の底（低い）
                height = -3.0
            elif dist_from_canyon < 20:
                # 急峻な崖（急勾配）
                height = -3.0 + (dist_from_canyon - 10) * 0.8
            else:
                # 平坦な上部
                height = 5.0
            
            height_map[i, :] = height
        
        # 崖に沿って障害物
        obstacle_map = np.zeros((self.grid_size, self.grid_size), dtype=bool)
        np.random.seed(48)  # 再現性のため
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                dist_from_canyon = abs(i - canyon_center)
                if 8 < dist_from_canyon < 22:
                    if np.random.random() < 0.3:
                        obstacle_map[i, j] = True
        
        return TerrainMap(
            name="Extreme Hazards",
            description="極端地形。崖、峡谷、勾配30-45度",
            size=self.map_size,
            terrain_type="Extreme Terrain",
            height_map=height_map,
            obstacle_map=obstacle_map,
            max_slope=45.0
        )
    
    def generate_random_start_goal(self, terrain_map: TerrainMap, 
                                   num_scenarios: int = 20) -> List[Dict]:
        """
        指定された地形マップ内でランダムにスタート/ゴールを生成
        
        Args:
            terrain_map: 地形マップ
            num_scenarios: 生成するシナリオ数
        
        Returns:
            シナリオのリスト
        """
        scenarios = []
        half_size = terrain_map.size / 2
        
        np.random.seed(100)  # 再現性のため
        
        for i in range(num_scenarios):
            # 有効な位置を見つけるまでループ
            max_attempts = 100
            for attempt in range(max_attempts):
                # ランダムな位置
                start_x = np.random.uniform(-half_size + 2, half_size - 2)
                start_y = np.random.uniform(-half_size + 2, half_size - 2)
                
                goal_x = np.random.uniform(-half_size + 2, half_size - 2)
                goal_y = np.random.uniform(-half_size + 2, half_size - 2)
                
                # スタート-ゴール間の距離をチェック
                distance = np.sqrt((goal_x - start_x)**2 + (goal_y - start_y)**2)
                
                # 最低距離（マップサイズの30%以上）
                min_distance = terrain_map.size * 0.3
                
                if distance >= min_distance:
                    # 高さを地形から取得
                    start_z = self._get_height(terrain_map, start_x, start_y) + 0.2
                    goal_z = self._get_height(terrain_map, goal_x, goal_y) + 0.2
                    
                    scenario = {
                        'scenario_id': i,
                        'terrain_name': terrain_map.name,
                        'terrain_type': terrain_map.terrain_type,
                        'map_size': terrain_map.size,
                        'start': [start_x, start_y, start_z],
                        'goal': [goal_x, goal_y, goal_z],
                        'distance': distance,
                        'max_slope': terrain_map.max_slope
                    }
                    
                    scenarios.append(scenario)
                    break
            
            if len(scenarios) <= i:
                print(f"Warning: Could not generate scenario {i}")
        
        return scenarios
    
    def _get_height(self, terrain_map: TerrainMap, x: float, y: float) -> float:
        """指定座標の高さを取得"""
        half_size = terrain_map.size / 2
        grid_x = int((x + half_size) / self.resolution)
        grid_y = int((y + half_size) / self.resolution)
        
        grid_x = np.clip(grid_x, 0, self.grid_size - 1)
        grid_y = np.clip(grid_y, 0, self.grid_size - 1)
        
        return terrain_map.height_map[grid_x, grid_y]
    
    def visualize_terrain(self, terrain_map: TerrainMap, save_path: str = None):
        """地形を可視化"""
        fig = plt.figure(figsize=(15, 5))
        
        # 高さマップ
        ax1 = fig.add_subplot(131)
        im1 = ax1.imshow(terrain_map.height_map, cmap='terrain', origin='lower')
        ax1.set_title(f'{terrain_map.name}\nHeight Map')
        ax1.set_xlabel('X [grid]')
        ax1.set_ylabel('Y [grid]')
        plt.colorbar(im1, ax=ax1, label='Height [m]')
        
        # 障害物マップ
        ax2 = fig.add_subplot(132)
        im2 = ax2.imshow(terrain_map.obstacle_map, cmap='Reds', origin='lower')
        ax2.set_title(f'{terrain_map.name}\nObstacle Map')
        ax2.set_xlabel('X [grid]')
        ax2.set_ylabel('Y [grid]')
        plt.colorbar(im2, ax=ax2, label='Obstacle')
        
        # 3D表示
        ax3 = fig.add_subplot(133, projection='3d')
        x = np.arange(self.grid_size)
        y = np.arange(self.grid_size)
        X, Y = np.meshgrid(x, y)
        Z = terrain_map.height_map
        
        # 障害物を赤で表示
        obstacle_mask = terrain_map.obstacle_map
        ax3.plot_surface(X, Y, Z, alpha=0.7, cmap='terrain')
        
        # 障害物を赤い点で表示
        obstacle_x, obstacle_y = np.where(obstacle_mask)
        if len(obstacle_x) > 0:
            obstacle_z = terrain_map.height_map[obstacle_x, obstacle_y]
            ax3.scatter(obstacle_x, obstacle_y, obstacle_z, c='red', s=1)
        
        ax3.set_title(f'{terrain_map.name}\n3D View')
        ax3.set_xlabel('X [grid]')
        ax3.set_ylabel('Y [grid]')
        ax3.set_zlabel('Height [m]')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Visualization saved to: {save_path}")
        
        plt.show()
    
    def save_terrain_map(self, terrain_map: TerrainMap, output_dir: str):
        """地形マップを保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 高さマップ
        np.save(output_path / f"{terrain_map.name.lower().replace(' ', '_')}_height.npy", 
                terrain_map.height_map)
        
        # 障害物マップ
        np.save(output_path / f"{terrain_map.name.lower().replace(' ', '_')}_obstacles.npy", 
                terrain_map.obstacle_map)
        
        # メタデータ
        metadata = {
            'name': terrain_map.name,
            'description': terrain_map.description,
            'size': terrain_map.size,
            'terrain_type': terrain_map.terrain_type,
            'max_slope': terrain_map.max_slope,
            'grid_size': self.grid_size,
            'resolution': self.resolution
        }
        
        with open(output_path / f"{terrain_map.name.lower().replace(' ', '_')}_meta.json", 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"Saved terrain map: {terrain_map.name}")

def generate_all_representative_terrains():
    """全ての代表的地形を生成"""
    generator = RepresentativeTerrainGenerator(map_size=50.0, resolution=0.5)
    
    # 5つの地形を生成
    terrains = [
        generator.generate_flat_agricultural_field(),
        generator.generate_gentle_hills(),
        generator.generate_steep_terrain(),
        generator.generate_complex_obstacles(),
        generator.generate_extreme_hazards()
    ]
    
    # 各地形で20シナリオ生成
    all_scenarios = []
    output_dir = '../scenarios/representative'
    
    for terrain in terrains:
        # 地形マップを保存
        terrain_dir = output_dir + '/' + terrain.name.lower().replace(' ', '_')
        generator.save_terrain_map(terrain, terrain_dir)
        
        # 可視化
        viz_path = terrain_dir + f"/{terrain.name.lower().replace(' ', '_')}_visualization.png"
        generator.visualize_terrain(terrain, viz_path)
        
        # シナリオ生成
        scenarios = generator.generate_random_start_goal(terrain, num_scenarios=20)
        
        # シナリオを保存
        for scenario in scenarios:
            filename = f"scenario_{scenario['scenario_id']:03d}.json"
            filepath = Path(terrain_dir) / filename
            
            with open(filepath, 'w') as f:
                json.dump(scenario, f, indent=2)
        
        all_scenarios.extend(scenarios)
        print(f"Generated {len(scenarios)} scenarios for {terrain.name}")
    
    # 全シナリオの統計
    print(f"\n✅ Total: {len(all_scenarios)} scenarios across 5 terrains")
    print(f"   Saved to: {output_dir}")
    
    # 統計情報
    terrain_counts = {}
    for scenario in all_scenarios:
        terrain_type = scenario['terrain_type']
        terrain_counts[terrain_type] = terrain_counts.get(terrain_type, 0) + 1
    
    print("\n📊 Scenario Distribution:")
    for terrain_type, count in terrain_counts.items():
        print(f"   {terrain_type}: {count} scenarios")
    
    # 距離統計
    distances = [s['distance'] for s in all_scenarios]
    print(f"\n📏 Distance Statistics:")
    print(f"   Min: {min(distances):.2f}m")
    print(f"   Max: {max(distances):.2f}m")
    print(f"   Mean: {np.mean(distances):.2f}m")
    print(f"   Std: {np.std(distances):.2f}m")

if __name__ == '__main__':
    generate_all_representative_terrains()


