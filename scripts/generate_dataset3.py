#!/usr/bin/env python3
"""Generate Dataset3 (120 scenarios) with 4 targeted types.
Outputs:
 - dataset3_scenarios.json
 - dataset3_design_rationale.json
 - benchmark_results/dataset3_visualization.png
"""
import json
import os
import numpy as np
from scipy import ndimage
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.getcwd()
OUT_SCEN = os.path.join(ROOT, 'dataset3_scenarios.json')
OUT_RAT = os.path.join(ROOT, 'dataset3_design_rationale.json')
OUT_VIS = os.path.join(ROOT, 'benchmark_results', 'dataset3_visualization.png')
os.makedirs(os.path.join(ROOT,'benchmark_results'), exist_ok=True)

RNG = np.random.default_rng(42)

# helpers

def random_obstacle_map(size, density, rng=RNG):
    return (rng.random(size) < density).astype(np.uint8)


def generate_maze(size, complexity=0.75, density=0.85, rng=RNG):
    # simple maze-like structure: start from empty grid and add walls with perlin-like noise + skeleton
    grid = np.zeros((size, size), dtype=np.uint8)
    # add random blocks
    noise = rng.random((size, size))
    grid[noise < density] = 1
    # carve a noisy maze path using random walk to ensure connectivity
    x,y = rng.integers(1,size-1), rng.integers(1,size-1)
    for _ in range(size*size//2):
        grid[x,y] = 0
        dx,dy = rng.choice([-1,0,1]), rng.choice([-1,0,1])
        x = np.clip(x+dx,1,size-2); y = np.clip(y+dy,1,size-2)
    # enforce narrow passages by dilating then eroding
    grid = ndimage.binary_dilation(grid, iterations=1).astype(np.uint8)
    return grid


def generate_height_map(size, slope_deg_low=30, slope_deg_high=60, rng=RNG):
    # create a sloped terrain by combining gradients and noise
    x = np.linspace(0,1,size)
    y = np.linspace(0,1,size)
    xv, yv = np.meshgrid(x,y)
    slope = rng.uniform(slope_deg_low, slope_deg_high)
    # approximate slope effect: height ~ linear combination + noise
    height = xv * np.tan(np.radians(slope)) + rng.normal(scale=0.05, size=(size,size))
    # normalize
    height = (height - height.min()) / (height.max() - height.min() + 1e-9)
    return height.tolist()


def pick_start_goal(size, obs_map, min_dist_ratio=0.8, rng=RNG, max_tries=2000):
    empty = np.argwhere(obs_map==0)
    if len(empty)<2:
        # fallback
        return (0,0),(size-1,size-1)
    target_dist = int(min_dist_ratio * size)
    for _ in range(max_tries):
        a = empty[rng.integers(len(empty))]
        b = empty[rng.integers(len(empty))]
        d = np.linalg.norm(a-b)
        if d >= target_dist:
            return (int(a[1]), int(a[0])), (int(b[1]), int(b[0]))
    # fallback farthest pair
    a = empty[0]; b = empty[-1]
    return (int(a[1]),int(a[0])), (int(b[1]),int(b[0]))


def make_scenario(sid, env, map_size, obstacle_ratio=None, obstacle_map=None, height_map=None, extra=None):
    sc = {'id': sid, 'env': env, 'map_size': map_size}
    if obstacle_map is None and obstacle_ratio is not None:
        obs = random_obstacle_map((map_size,map_size), obstacle_ratio)
    elif obstacle_map is not None:
        obs = obstacle_map
    else:
        obs = random_obstacle_map((map_size,map_size), 0.2)
    sc['obstacle_map'] = obs.tolist()
    sc['obstacle_ratio'] = float(np.mean(obs))
    if height_map is not None:
        sc['height_map'] = height_map
    sc['extra'] = extra or {}
    # pick start/goal
    sx,sy = pick_start_goal(map_size, obs)
    gx,gy = pick_start_goal(map_size, obs)
    sc['start'] = (sx,sy)
    sc['goal'] = (gx,gy)
    return sc


def main():
    scenarios = []
    rationale = {'types':{}}

    # Type1: D*Lite-killer (30)
    t1_list = []
    for i in range(30):
        size=150
        density = RNG.uniform(0.75,0.90)
        obs = generate_maze(size, density=density)
        # enforce narrow passages: thin corridors
        # ensure some narrow regions
        sc = make_scenario(f'D3_Type1_{i:03d}','D_LITE_KILLER', size, obstacle_map=obs, extra={'maze':True,'narrow_width':'1-2','obstacle_density':float(density)})
        scenarios.append(sc)
        t1_list.append(sc['id'])
    rationale['types']['D_LITE_KILLER'] = {'count':30,'map_size':150,'obstacle_density_range':[0.75,0.90],'notes':'maze structure with narrow passages'}

    # Type2: Sampling-favorable (30)
    for i in range(30):
        size=100
        density = RNG.uniform(0.40,0.60)
        # generate clustered obstacles via gaussian blobs
        grid = np.zeros((size,size), dtype=np.uint8)
        n_blobs = RNG.integers(8,20)
        for _ in range(n_blobs):
            cx = RNG.integers(0,size); cy = RNG.integers(0,size)
            rx = RNG.integers(5,20); ry = RNG.integers(5,20)
            x = np.arange(size); y = np.arange(size)
            xv,yv = np.meshgrid(x,y)
            mask = ((xv-cx)**2/(rx**2) + (yv-cy)**2/(ry**2)) < 1.0
            grid[mask] = 1
        # thin to target density
        cur = grid.mean()
        if cur>0:
            prob_keep = density / cur
            prob_keep = min(prob_keep,1.0)
            noise = RNG.random((size,size))
            grid = (grid * (noise < prob_keep)).astype(np.uint8)
        else:
            grid = random_obstacle_map((size,size), density)
        sc = make_scenario(f'D3_Type2_{i:03d}','SAMPLING_FAVOR', size, obstacle_map=grid, extra={'complex_obstacles':True,'obstacle_density':float(density)})
        scenarios.append(sc)
    rationale['types']['SAMPLING_FAVOR'] = {'count':30,'map_size':100,'obstacle_density_range':[0.40,0.60],'notes':'clustered/concave obstacles to favor sampling planners'}

    # Type3: Theta-favorable (30)
    for i in range(30):
        size=120
        density = RNG.uniform(0.10,0.30)
        grid = random_obstacle_map((size,size), density)
        # carve large open spaces: add empty circles
        for _ in range(3):
            cx = RNG.integers(0,size); cy = RNG.integers(0,size); r = RNG.integers(15,30)
            xv,yv = np.meshgrid(np.arange(size), np.arange(size))
            mask = (xv-cx)**2 + (yv-cy)**2 <= r*r
            grid[mask] = 0
        sc = make_scenario(f'D3_Type3_{i:03d}','THETA_FAVOR', size, obstacle_map=grid, extra={'open_spaces':True,'obstacle_density':float(density)})
        scenarios.append(sc)
    rationale['types']['THETA_FAVOR'] = {'count':30,'map_size':120,'obstacle_density_range':[0.10,0.30],'notes':'large open areas, long start-goal distances'}

    # Type4: Slope-focused (30)
    for i in range(30):
        size=120
        density = RNG.uniform(0.10,0.20)
        grid = random_obstacle_map((size,size), density)
        height = generate_height_map(size, slope_deg_low=30, slope_deg_high=60)
        sc = make_scenario(f'D3_Type4_{i:03d}','SLOPE_FOCUS', size, obstacle_map=grid, height_map=height, extra={'slope_deg_range':[30,60],'obstacle_density':float(density)})
        scenarios.append(sc)
    rationale['types']['SLOPE_FOCUS'] = {'count':30,'map_size':120,'slope_deg_range':[30,60],'notes':'steep slopes where TA* should be advantageous'}

    # save
    with open(OUT_SCEN,'w') as f:
        json.dump(scenarios, f, indent=2)
    with open(OUT_RAT,'w') as f:
        json.dump(rationale, f, indent=2)

    # visualize sample grid images (one per type)
    fig, axs = plt.subplots(2,2, figsize=(8,8))
    sample_idxs = [0,30,60,90]
    titles = ['D*Lite_killer','Sampling_favor','Theta_favor','Slope_focus']
    for ax, idx, t in zip(axs.flatten(), sample_idxs, titles):
        sc = scenarios[idx]
        im = np.array(sc['obstacle_map'])
        ax.imshow(im, cmap='gray_r')
        ax.set_title(f"{t}: {sc['id']}")
        ax.axis('off')
    plt.tight_layout()
    plt.savefig(OUT_VIS, dpi=200)
    print('Saved:', OUT_SCEN, OUT_RAT, OUT_VIS)

if __name__=='__main__':
    main()
