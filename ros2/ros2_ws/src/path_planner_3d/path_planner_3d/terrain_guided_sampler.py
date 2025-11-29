import numpy as np
from typing import Tuple, Optional
import random

class TerrainGuidedSampler:
    """
    地形コストマップに基づき、通行しやすいエリアにバイアスをかけてサンプリングするクラス。
    RRT*の探索効率向上を目的とする。
    """
    def __init__(
        self,
        bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
        terrain_cost_map: Optional[np.ndarray] = None,
        resolution: float = 0.1,
        bias_strength: float = 0.7,
        goal_bias_prob: float = 0.1
    ) -> None:
        """
        Args:
            bounds: サンプリング範囲 ((x_min, x_max), (y_min, y_max), (z_min, z_max))
            terrain_cost_map: 2D地形コストマップ (Noneなら完全ランダム)
            resolution: グリッド解像度 [meter/cell]
            bias_strength: バイアス強度 (0.0=完全ランダム, 1.0=完全バイアス)
            goal_bias_prob: ゴール付近をサンプリングする確率
        """
        self.bounds = bounds
        self.terrain_cost_map = terrain_cost_map
        self.resolution = resolution
        self.bias_strength = bias_strength
        self.goal_bias_prob = goal_bias_prob

    def sample(self, goal: Optional[np.ndarray] = None) -> np.ndarray:
        """
        地形コストに基づくバイアス付きサンプリング
        Args:
            goal: ゴール位置 [x, y, z]（goal_biasに使用）
        Returns:
            サンプル点 [x, y, z]
        """
        if goal is not None and random.random() < self.goal_bias_prob:
            return self._sample_near_goal(goal)
        if self.terrain_cost_map is not None:
            return self._sample_with_terrain_bias()
        return self._sample_uniform()

    def _sample_with_terrain_bias(self) -> np.ndarray:
        """
        地形コストマップに基づくバイアス付きサンプリング
        Returns:
            サンプル点 [x, y, z]
        """
        prob_map = self.compute_probability_map()
        flat_idx = np.random.choice(prob_map.size, p=prob_map.ravel())
        grid_y, grid_x = np.unravel_index(flat_idx, prob_map.shape)
        # セル内でランダムな位置
        x, y, _ = self.grid_to_world(grid_x, grid_y)
        x += (random.random() - 0.5) * self.resolution
        y += (random.random() - 0.5) * self.resolution
        z = random.uniform(self.bounds[2][0], self.bounds[2][1])
        # クリップ
        x = np.clip(x, self.bounds[0][0], self.bounds[0][1])
        y = np.clip(y, self.bounds[1][0], self.bounds[1][1])
        z = np.clip(z, self.bounds[2][0], self.bounds[2][1])
        return np.array([x, y, z], dtype=np.float32)

    def _sample_near_goal(self, goal: np.ndarray, radius: float = 1.0) -> np.ndarray:
        """
        ゴール付近をサンプリング
        Args:
            goal: ゴール位置 [x, y, z]
            radius: サンプリング半径 [meter]
        Returns:
            ゴール付近のサンプル点 [x, y, z]
        """
        theta = random.uniform(0, 2 * np.pi)
        r = random.uniform(0, radius)
        dx = r * np.cos(theta)
        dy = r * np.sin(theta)
        dz = random.uniform(-radius/2, radius/2)
        x = np.clip(goal[0] + dx, self.bounds[0][0], self.bounds[0][1])
        y = np.clip(goal[1] + dy, self.bounds[1][0], self.bounds[1][1])
        z = np.clip(goal[2] + dz, self.bounds[2][0], self.bounds[2][1])
        return np.array([x, y, z], dtype=np.float32)

    def _sample_uniform(self) -> np.ndarray:
        """
        完全ランダムサンプリング（terrain_cost_map が None の時）
        Returns:
            ランダムサンプル点 [x, y, z]
        """
        x = random.uniform(self.bounds[0][0], self.bounds[0][1])
        y = random.uniform(self.bounds[1][0], self.bounds[1][1])
        z = random.uniform(self.bounds[2][0], self.bounds[2][1])
        return np.array([x, y, z], dtype=np.float32)

    def compute_probability_map(self) -> np.ndarray:
        """
        地形コストマップを確率分布に変換
        Returns:
            確率マップ (shape: (height, width), sum = 1.0)
        """
        if self.terrain_cost_map is None:
            raise ValueError("terrain_cost_map is None")
        cost_map = np.clip(self.terrain_cost_map, 0.0, 1.0)
        probability = 1.0 / (1.0 + cost_map)
        uniform = np.ones_like(probability) / probability.size
        biased_prob = (1 - self.bias_strength) * uniform + self.bias_strength * probability
        biased_prob = np.clip(biased_prob, 1e-8, None)  # ゼロ除算防止
        biased_prob /= biased_prob.sum()
        return biased_prob

    def set_terrain_cost_map(self, cost_map: np.ndarray) -> None:
        """
        地形コストマップを更新
        Args:
            cost_map: 新しい地形コストマップ
        """
        self.terrain_cost_map = cost_map

    def world_to_grid(self, world_pos: np.ndarray) -> Tuple[int, int]:
        """
        世界座標 -> グリッドインデックス変換
        Args:
            world_pos: [x, y, z]
        Returns:
            (grid_x, grid_y)
        """
        x_idx = int((world_pos[0] - self.bounds[0][0]) / self.resolution)
        y_idx = int((world_pos[1] - self.bounds[1][0]) / self.resolution)
        return x_idx, y_idx

    def grid_to_world(self, grid_x: int, grid_y: int) -> np.ndarray:
        """
        グリッドインデックス -> 世界座標変換
        Args:
            grid_x, grid_y: グリッドインデックス
        Returns:
            [x, y, 0.0]  (z=0, 高さは後で調整)
        """
        x = self.bounds[0][0] + grid_x * self.resolution
        y = self.bounds[1][0] + grid_y * self.resolution
        return np.array([x, y, 0.0], dtype=np.float32)

if __name__ == '__main__':
    # ダミー地形コストマップ（中央が低コスト）
    cost_map = np.ones((100, 100), dtype=np.float32) * 0.8
    cost_map[40:60, 40:60] = 0.2  # 中央は通りやすい

    sampler = TerrainGuidedSampler(
        bounds=((-5.0, 5.0), (-5.0, 5.0), (0.0, 2.0)),
        terrain_cost_map=cost_map,
        resolution=0.1,
        bias_strength=0.7,
        goal_bias_prob=0.1
    )

    goal = np.array([4.0, 4.0, 0.5])

    # 100回サンプリングして分布を確認
    samples = []
    for _ in range(100):
        sample = sampler.sample(goal)
        samples.append(sample)
        print(f"Sample: {sample}")

    samples = np.array(samples)
    print(f"\nSample distribution:")
    print(f"  X: mean={samples[:, 0].mean():.2f}, std={samples[:, 0].std():.2f}")
    print(f"  Y: mean={samples[:, 1].mean():.2f}, std={samples[:, 1].std():.2f}")
    print(f"  Z: mean={samples[:, 2].mean():.2f}, std={samples[:, 2].std():.2f}")
