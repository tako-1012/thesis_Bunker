import json
import math
import random
from collections import deque
from pathlib import Path

import numpy as np


SIZE_MAP = {
    'SMALL': 64,
    'MEDIUM': 128,
    'LARGE': 192,
}


def smooth(arr, iterations=3):
    a = arr.copy()
    for _ in range(iterations):
        a = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1) + a) / 5.0
    return a


def compute_slope_degrees(height):
    gy, gx = np.gradient(height)
    grad = np.sqrt(gx * gx + gy * gy)
    slope_deg = np.degrees(np.arctan(grad))
    return slope_deg


def is_reachable(obst, start, goal):
    h, w = obst.shape
    visited = np.zeros_like(obst, dtype=bool)
    dq = deque()
    dq.append(tuple(start))
    visited[start[1], start[0]] = True
    dirs = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]
    while dq:
        x, y = dq.popleft()
        if (x, y) == tuple(goal):
            return True
        for dx, dy in dirs:
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not visited[ny, nx] and obst[ny, nx]==0:
                visited[ny, nx] = True
                dq.append((nx, ny))
    return False


class AdvancedScenarioGenerator:
    def __init__(self, seed=12345):
        self.rng = random.Random(seed)
        np.random.seed(seed)

    def _make_height_map(self, size_px, target_mean_slope_deg=None, max_slope_deg=None):
        # base noise
        a = np.random.rand(size_px, size_px) - 0.5
        a = smooth(a, iterations=4)
        amp = 1.0
        for _ in range(20):
            h = a * amp
            sdeg = compute_slope_degrees(h)
            mean_s = float(np.mean(sdeg))
            max_s = float(np.max(sdeg))
            if target_mean_slope_deg is None:
                break
            # adjust amplitude to approach target mean slope
            if mean_s < target_mean_slope_deg:
                amp *= 1.25
            elif mean_s > target_mean_slope_deg and amp>1e-6:
                amp *= 0.8
            else:
                break
            # clamp max
            if max_slope_deg and max_s > max_slope_deg:
                amp *= 0.8
        h = smooth(a * amp, iterations=3)
        # normalize 0..1
        h = (h - h.min()) / (h.max() - h.min() + 1e-9)
        return h

    def _place_start_goal(self, obst_map, min_separation_ratio=0.5, tries=500):
        h, w = obst_map.shape
        min_sep = int(min(w, h) * min_separation_ratio)
        for _ in range(tries):
            sx = self.rng.randrange(0, w)
            sy = self.rng.randrange(0, h)
            gx = self.rng.randrange(0, w)
            gy = self.rng.randrange(0, h)
            if obst_map[sy, sx] != 0 or obst_map[gy, gx] != 0:
                continue
            if abs(sx - gx) + abs(sy - gy) < min_sep:
                continue
            if is_reachable(obst_map, (sx, sy), (gx, gy)):
                return (sx, sy), (gx, gy)
        # fallback: brute-force nearest free cells
        free = np.argwhere(obst_map==0)
        if len(free) < 2:
            return (0,0), (w-1,h-1)
        i = self.rng.randrange(len(free))
        j = (i+len(free)//2) % len(free)
        sy, sx = free[i]
        gy, gx = free[j]
        return (int(sx), int(sy)), (int(gx), int(gy))

    def generate_steep_terrain(self, size, count):
        size_px = SIZE_MAP[size]
        scenarios = []
        for i in range(count):
            # aim for mean slope 20-30, max <=35
            target = self.rng.uniform(20, 30)
            hm = self._make_height_map(size_px, target_mean_slope_deg=target, max_slope_deg=35)
            # low obstacle density
            obst = np.zeros_like(hm, dtype=np.uint8)
            # carve a few random rocks
            for _ in range(int(size_px*0.1)):
                x = self.rng.randrange(0, size_px)
                y = self.rng.randrange(0, size_px)
                w = max(1, self.rng.randrange(1, max(2, size_px//16)))
                h = max(1, self.rng.randrange(1, max(2, size_px//16)))
                obst[y:y+h, x:x+w] = 1
            start, goal = self._place_start_goal(obst)
            slope_stats = compute_slope_degrees(hm)
            scenarios.append({
                'id': f'steep_{size}_{i:03d}',
                'env': size,
                'map_size': size_px,
                'height_map': hm.tolist(),
                'obstacle_map': obst.tolist(),
                'start': list(start),
                'goal': list(goal),
                'metadata': {
                    'mean_slope_deg': float(np.mean(slope_stats)),
                    'max_slope_deg': float(np.max(slope_stats)),
                    'obstacle_density': float(obst.mean()),
                }
            })
        return scenarios

    def generate_dense_obstacles(self, size, count):
        size_px = SIZE_MAP[size]
        scenarios = []
        for i in range(count):
            hm = self._make_height_map(size_px, target_mean_slope_deg=7)
            # high obstacle density 30-40%
            density = self.rng.uniform(0.30, 0.40)
            obst = (np.random.rand(size_px, size_px) < density).astype(np.uint8)
            # carve narrow corridors: perform random walks to ensure some passages
            for _ in range(4):
                x = self.rng.randrange(0, size_px)
                y = self.rng.randrange(0, size_px)
                length = int(size_px * self.rng.uniform(0.5, 1.0))
                for _ in range(length):
                    for dx in range(-1,2):
                        for dy in range(-1,2):
                            nx, ny = x+dx, y+dy
                            if 0<=nx<size_px and 0<=ny<size_px:
                                obst[ny,nx]=0
                    x += self.rng.choice([-1,0,1])
                    y += self.rng.choice([-1,0,1])
                    x = max(0, min(size_px-1, x)); y = max(0, min(size_px-1, y))
            start, goal = self._place_start_goal(obst)
            slope_stats = compute_slope_degrees(hm)
            scenarios.append({
                'id': f'dense_{size}_{i:03d}',
                'env': size,
                'map_size': size_px,
                'height_map': hm.tolist(),
                'obstacle_map': obst.tolist(),
                'start': list(start),
                'goal': list(goal),
                'metadata': {
                    'mean_slope_deg': float(np.mean(slope_stats)),
                    'max_slope_deg': float(np.max(slope_stats)),
                    'obstacle_density': float(obst.mean()),
                }
            })
        return scenarios

    def generate_complex_mixed(self, size, count):
        size_px = SIZE_MAP[size]
        scenarios = []
        for i in range(count):
            # mixed: moderate slopes and obstacles
            hm = self._make_height_map(size_px, target_mean_slope_deg=self.rng.uniform(8,18))
            density = self.rng.uniform(0.12, 0.30)
            obst = (np.random.rand(size_px, size_px) < density).astype(np.uint8)
            # add some larger obstacles
            for _ in range(int(size_px*0.05)):
                x = self.rng.randrange(0, size_px)
                y = self.rng.randrange(0, size_px)
                w = self.rng.randrange(2, max(3, size_px//12))
                h = self.rng.randrange(2, max(3, size_px//12))
                obst[y:y+h, x:x+w] = 1
            # carve a few winding corridors
            x = self.rng.randrange(0, size_px); y = self.rng.randrange(0, size_px)
            for _ in range(int(size_px*1.2)):
                for dx in range(-1,2):
                    for dy in range(-1,2):
                        nx, ny = x+dx, y+dy
                        if 0<=nx<size_px and 0<=ny<size_px:
                            obst[ny,nx]=0
                x += self.rng.choice([-1,0,1])
                y += self.rng.choice([-1,0,1])
                x = max(0, min(size_px-1, x)); y = max(0, min(size_px-1, y))
            start, goal = self._place_start_goal(obst)
            slope_stats = compute_slope_degrees(hm)
            scenarios.append({
                'id': f'complex_{size}_{i:03d}',
                'env': size,
                'map_size': size_px,
                'height_map': hm.tolist(),
                'obstacle_map': obst.tolist(),
                'start': list(start),
                'goal': list(goal),
                'metadata': {
                    'mean_slope_deg': float(np.mean(slope_stats)),
                    'max_slope_deg': float(np.max(slope_stats)),
                    'obstacle_density': float(obst.mean()),
                }
            })
        return scenarios


def save_scenarios(path, scenarios):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('w') as f:
        json.dump(scenarios, f)
    print(f'Wrote {len(scenarios)} scenarios to {path}')


def validate_scenarios(scenarios):
    total = len(scenarios)
    solvable = 0
    slope_means = []
    densities = []
    for s in scenarios:
        obst = np.array(s['obstacle_map'], dtype=np.uint8)
        start = tuple(s['start'])
        goal = tuple(s['goal'])
        ok = is_reachable(obst, start, goal)
        if ok:
            solvable += 1
        slope_means.append(s['metadata'].get('mean_slope_deg', 0.0))
        densities.append(s['metadata'].get('obstacle_density', 0.0))
    print(f'Scenarios: {total}, solvable: {solvable}, solvable_ratio: {solvable/total:.3f}')
    print(f'mean slope across scenarios: {float(np.mean(slope_means)):.2f} deg')
    print(f'mean obstacle density: {float(np.mean(densities)):.3f}')
    return {'total': total, 'solvable': solvable}


def main():
    gen = AdvancedScenarioGenerator()
    scenarios = []
    # Steep
    scenarios.extend(gen.generate_steep_terrain('SMALL', 16))
    scenarios.extend(gen.generate_steep_terrain('MEDIUM', 24))
    scenarios.extend(gen.generate_steep_terrain('LARGE', 8))
    # Dense
    scenarios.extend(gen.generate_dense_obstacles('SMALL', 16))
    scenarios.extend(gen.generate_dense_obstacles('MEDIUM', 24))
    scenarios.extend(gen.generate_dense_obstacles('LARGE', 8))
    # Complex
    scenarios.extend(gen.generate_complex_mixed('SMALL', 16))
    scenarios.extend(gen.generate_complex_mixed('MEDIUM', 24))
    scenarios.extend(gen.generate_complex_mixed('LARGE', 8))

    save_scenarios('dataset2_scenarios.json', scenarios)
    validate_scenarios(scenarios)


if __name__ == '__main__':
    main()
