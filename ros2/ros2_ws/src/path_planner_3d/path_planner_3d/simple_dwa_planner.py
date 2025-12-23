"""
Simple DWA (Dynamic Window Approach) プロトタイプ実装

用途: Dijkstra のグローバル経路に沿った局所最適化の簡易実装

注意: 学術的に完全な実装ではなく、発表用の動作するプロトタイプを目的とする。
"""
import time
import math
import logging
from typing import List, Tuple, Optional, Dict

import numpy as np

logger = logging.getLogger(__name__)


class SimpleDWAPlanner:
    """簡易 DWA プランナー（プロトタイプ）

    入力の `terrain_map` は以下のいずれかを想定:
    - オブジェクトで `obstacle_map` (2D numpy bool array) と `size` (m) を持つ
    - 直接 2D numpy array（障害物マップ）
    """

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.max_velocity = cfg.get('max_velocity', 1.0)
        self.max_angular_velocity = cfg.get('max_angular_velocity', 1.0)
        self.velocity_samples = cfg.get('velocity_samples', 20)
        self.angular_samples = cfg.get('angular_samples', 20)
        self.time_horizon = cfg.get('time_horizon', 2.0)
        self.dt = cfg.get('dt', 0.1)
        self.max_accel = cfg.get('max_accel', 0.5)
        self.max_angular_accel = cfg.get('max_angular_accel', 0.5)
        self.weights = cfg.get('weights', {'goal': 0.5, 'obstacle': 0.3, 'velocity': 0.2})

        # 安全マージン（m） — 障害物との最小許容距離
        self.safe_distance = cfg.get('safe_distance', 0.2)

        # サンプリングで 0 を含めるための小値
        self.eps = 1e-6

        logger.info(f"SimpleDWA initialized: vmax={self.max_velocity}, w={self.weights}")

    def plan_path(self,
                  start: Tuple[float, float, float],
                  goal: Tuple[float, float, float],
                  terrain_map,
                  global_path: Optional[List[Tuple[float, float, float]]] = None,
                  timeout: Optional[float] = 60.0) -> Tuple[List[Tuple[float, float, float]], float]:
        """メインの経路最適化ルーチン（簡易実装）

        戻り値:
            optimized_path: list of (x,y,z)
            computation_time: 秒
        """
        t0 = time.time()

        # current state
        cur_x, cur_y, cur_z = start
        # 初期姿勢は global_path の最初のセグメント方向を利用（なければ 0）
        if global_path and len(global_path) >= 2:
            dx = global_path[1][0] - global_path[0][0]
            dy = global_path[1][1] - global_path[0][1]
            cur_yaw = math.atan2(dy, dx)
        else:
            cur_yaw = 0.0

        cur_v = 0.0

        optimized_path = [(cur_x, cur_y, cur_z)]

        max_iters = int( (timeout or 60.0) / max(self.dt, 0.01) )

        for it in range(max_iters):
            if time.time() - t0 > (timeout or 60.0):
                logger.warning('SimpleDWA: timeout during plan')
                break

            # 終了判定: ゴール到達
            dist_to_goal = math.hypot(goal[0] - cur_x, goal[1] - cur_y)
            if dist_to_goal < 0.5:
                optimized_path.append(goal)
                break

            # サンプル速度を生成
            samples = self._sample_velocities(cur_v)

            best = None
            best_cost = float('inf')
            best_traj = None

            for v, w in samples:
                traj = self._simulate_trajectory((v, w), (cur_x, cur_y, cur_z), cur_yaw, terrain_map)
                if traj is None:
                    # 衝突または不正
                    continue

                cost, min_obs = self._evaluate_trajectory(traj, goal, v, cur_v, terrain_map)
                if cost < best_cost:
                    best_cost = cost
                    best = (v, w)
                    best_traj = traj

            if best is None:
                # 有効な経路が見つからない -> 停止して global_path の次点を短く接近
                logger.warning('SimpleDWA: no valid velocity sample found, fallback')
                # 距離を少し進めるか global_path に沿って1ステップコピー
                if global_path and len(global_path) > 1:
                    # 次のグローバル点へスナップ
                    next_wp = global_path[1]
                    cur_x, cur_y, cur_z = next_wp
                    optimized_path.append((cur_x, cur_y, cur_z))
                    # update heading
                    if len(global_path) >= 3:
                        dx = global_path[2][0] - global_path[1][0]
                        dy = global_path[2][1] - global_path[1][1]
                        cur_yaw = math.atan2(dy, dx)
                    cur_v = 0.0
                    # shrink global_path to pop first
                    global_path = global_path[1:]
                    continue
                else:
                    break

            # best velocity を適用して1ステップ分だけ前進（短い時間 dt）
            v_sel, w_sel = best
            # advance by dt
            cur_x, cur_y, cur_z, cur_yaw = self._apply_motion((cur_x, cur_y, cur_z), cur_yaw, v_sel, w_sel, self.dt)
            optimized_path.append((cur_x, cur_y, cur_z))
            cur_v = v_sel

        comp_time = time.time() - t0
        return optimized_path, comp_time

    def _sample_velocities(self, current_velocity: float):
        """動的ウィンドウ内で速度を線形・角速度でサンプリングする簡易実装"""
        # 線速度は0..max_velocity、角速度は -max_angular..+max_angular
        vs = np.linspace(max(0.0, current_velocity - self.max_accel * self.dt),
                         min(self.max_velocity, current_velocity + self.max_accel * self.dt),
                         num=self.velocity_samples)

        ws = np.linspace(-self.max_angular_velocity, self.max_angular_velocity, num=self.angular_samples)

        samples = []
        for v in vs:
            for w in ws:
                samples.append((float(v), float(w)))
        return samples

    def _simulate_trajectory(self, velocity: Tuple[float, float], current_pos: Tuple[float, float, float],
                             current_heading: float, terrain_map) -> Optional[List[Tuple[float, float, float]]]:
        """与えられた (v,w) で time_horizon 分シミュレーションし、障害物衝突がなければ軌跡を返す"""
        v, w = velocity
        steps = int(max(1, math.ceil(self.time_horizon / self.dt)))
        x, y, z = current_pos
        theta = current_heading

        traj = []
        for _ in range(steps):
            # simple unicycle model
            x += v * math.cos(theta) * self.dt
            y += v * math.sin(theta) * self.dt
            theta += w * self.dt
            traj.append((x, y, z))

            # 衝突チェック: 最近接障害物距離が safe_distance 未満なら衝突
            d = self._nearest_obstacle_distance((x, y), terrain_map)
            if d is None:
                # 地図情報が不明なら安全側で続行
                continue
            if d < self.safe_distance:
                return None

        return traj

    def _evaluate_trajectory(self, trajectory: List[Tuple[float, float, float]], goal: Tuple[float, float, float],
                             v: float, current_velocity: float, terrain_map) -> Tuple[float, float]:
        """軌跡の評価値を計算する（小さい方が良い）

        返回: (cost, min_obstacle_distance)
        """
        # 最終点からゴールまでの距離
        if not trajectory:
            return float('inf'), 0.0

        fx, fy, fz = trajectory[-1]
        goal_dist = math.hypot(goal[0] - fx, goal[1] - fy)

        # 軌跡中の最小障害物距離
        min_obs = float('inf')
        for p in trajectory:
            d = self._nearest_obstacle_distance((p[0], p[1]), terrain_map)
            if d is not None:
                min_obs = min(min_obs, d)

        if min_obs == float('inf'):
            # 障害物情報がない場合は大きな値にする
            min_obs = 1e3

        # 速度コスト: 速度変化の割合
        vel_cost = abs(v - current_velocity) / (self.max_velocity + self.eps)

        cost = (self.weights['goal'] * goal_dist +
                self.weights['obstacle'] * (1.0 / (min_obs + self.eps)) +
                self.weights['velocity'] * vel_cost)

        return float(cost), float(min_obs)

    def _select_best_velocity(self, evaluated_velocities: List[Tuple[Tuple[float, float], float]]):
        """(v,w),cost のリストから最小コストの速度を選択"""
        if not evaluated_velocities:
            return None
        evaluated_velocities.sort(key=lambda x: x[1])
        return evaluated_velocities[0][0]

    def _nearest_obstacle_distance(self, xy: Tuple[float, float], terrain_map) -> Optional[float]:
        """シンプルな最近接障害物距離計算

        terrain_map がオブジェクトであれば `obstacle_map` (2D numpy bool) と `size` (m) を期待
        直接 numpy array が渡された場合は size を grid_size として扱う（解像度=1.0m）
        """
        try:
            if hasattr(terrain_map, 'obstacle_map'):
                obs = terrain_map.obstacle_map
                size = float(getattr(terrain_map, 'size', obs.shape[0]))
            elif isinstance(terrain_map, np.ndarray):
                obs = terrain_map
                size = float(obs.shape[0])
            else:
                return None

            if obs is None or obs.size == 0:
                return None

            # grid info
            grid_nx, grid_ny = obs.shape
            resolution = size / float(grid_nx)
            half = size / 2.0

            # convert world xy to grid indices
            gx = int((xy[0] + half) / resolution)
            gy = int((xy[1] + half) / resolution)
            gx = np.clip(gx, 0, grid_nx - 1)
            gy = np.clip(gy, 0, grid_ny - 1)

            # find nearest True cell (brute-force) — acceptable for prototype
            obs_indices = np.argwhere(obs)
            if obs_indices.size == 0:
                return float('inf')

            # compute distances in meters
            coords = (obs_indices[:, 0].astype(float), obs_indices[:, 1].astype(float))
            dx = (coords[0] - gx) * resolution
            dy = (coords[1] - gy) * resolution
            dists = np.hypot(dx, dy)
            min_dist = float(np.min(dists))
            return min_dist
        except Exception:
            return None

    def _apply_motion(self, pos, yaw, v, w, dt):
        x, y, z = pos
        x += v * math.cos(yaw) * dt
        y += v * math.sin(yaw) * dt
        yaw += w * dt
        return x, y, z, yaw
