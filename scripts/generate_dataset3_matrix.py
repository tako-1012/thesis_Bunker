#!/usr/bin/env python3
"""
Generate Dataset3 as 3 sizes x 3 complexities (9 types x 10 = 90 scenarios)
Outputs:
 - dataset3_scenarios.json
 - dataset3_matrix_design.json
 - dataset3_visualization_grid.png
 - sample images dataset3_type{i}-{j}_sample.png (9 files)
Designed for robot grid resolution 0.2m, min passage width = 8 grids.
"""
import json, random
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy import ndimage
from collections import deque

OUT = Path('.')
RESULTS = OUT / 'benchmark_results'
RESULTS.mkdir(exist_ok=True)

random_seed = 20251227
random.seed(random_seed)
np.random.seed(random_seed)

GRID_RES = 0.2
ROBOT_SPEC = {'width':0.8,'length':1.0,'min_passage_width':1.6,'max_slope':30}
MIN_PASSAGE_GRIDS = int(round(ROBOT_SPEC['min_passage_width']/GRID_RES))
BUFFER_RADIUS = MIN_PASSAGE_GRIDS//2

# matrix design
matrix = {
    'groups':{
        '1':{'meters':30,'grid':150},
        '2':{'meters':50,'grid':250},
        '3':{'meters':80,'grid':400}
    },
    # densities per group/complexity as specified in the design
    'complexities':{
        '1':{'name':'low','density_range':[0.10,0.30]},   # small low
        '2':{'name':'mid','density_range':[0.40,0.60]},   # small mid
        '3':{'name':'high','density_range':[0.65,0.80]}   # small high
    },
    'per_type':10
}

SCEN_PER_TYPE = matrix['per_type']

# densities per group (group->complexity->[min,max]) as requested
densities_by_group = {
    '1':{'1':[0.10,0.30],'2':[0.40,0.60],'3':[0.65,0.80]},
    '2':{'1':[0.05,0.20],'2':[0.35,0.55],'3':[0.60,0.75]},
    '3':{'1':[0.05,0.15],'2':[0.30,0.50],'3':[0.55,0.70]}
}

# bfs
def bfs_path(grid,start,goal):
    h,w = grid.shape
    sx,sy = start
    gx,gy = goal
    if not (0<=sx<w and 0<=sy<h and 0<=gx<w and 0<=gy<h):
        return None
    if grid[sy,sx]==1 or grid[gy,gx]==1:
        return None
    q=deque([(sx,sy)])
    parent={(sx,sy):None}
    dirs=[(1,0),(-1,0),(0,1),(0,-1)]
    while q:
        x,y = q.popleft()
        if (x,y)==(gx,gy):
            path=[]
            cur=(gx,gy)
            while cur:
                path.append(cur)
                cur=parent[cur]
            return list(reversed(path))
        for dx,dy in dirs:
            nx,ny = x+dx,y+dy
            if 0<=nx<w and 0<=ny<h and grid[ny,nx]==0 and (nx,ny) not in parent:
                parent[(nx,ny)]=(x,y)
                q.append((nx,ny))
    return None

# helper: place random obstacles uniformly until target density
def place_random_obstacles(grid, target_density):
    h,w = grid.shape
    target = int(h*w*target_density)
    free_idxs = np.where(grid.ravel()==0)[0]
    if target <= 0:
        return
    # choose random unique indices
    pick = np.random.choice(free_idxs, size=min(len(free_idxs), target), replace=False)
    grid.ravel()[pick] = 1


# carve a straight corridor of given width (in grid cells) between start and goal
def carve_corridor(grid, start, goal, width):
    h, w = grid.shape
    sx, sy = int(start[0]), int(start[1])
    gx, gy = int(goal[0]), int(goal[1])
    dx = gx - sx
    dy = gy - sy
    steps = max(abs(dx), abs(dy), 1)
    r = max(1, width // 2)
    for i in range(steps + 1):
        t = i / steps
        cx = int(round(sx + dx * t))
        cy = int(round(sy + dy * t))
        # clear disk of radius r around (cx,cy)
        y0 = max(0, cy - r)
        y1 = min(h - 1, cy + r)
        x0 = max(0, cx - r)
        x1 = min(w - 1, cx + r)
        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    grid[yy, xx] = 0


# helper: pick a random free position, optionally enforce min straight distance from other
def random_free_position(grid, min_dist_from=None, min_dist=0, max_tries=2000):
    h,w = grid.shape
    free = np.argwhere(grid==0)
    if free.size==0:
        return None
    attempts = 0
    while attempts < max_tries:
        attempts += 1
        idx = random.randrange(len(free))
        y,x = free[idx]
        if min_dist_from is not None:
            dx = x - min_dist_from[0]
            dy = y - min_dist_from[1]
            d = (dx*dx+dy*dy)**0.5
            if d < min_dist:
                continue
        return (int(x), int(y))
    return None


# simple A* on 4-neighbour grid
import heapq
def simple_astar(grid, start, goal):
    h,w = grid.shape
    sx,sy = start
    gx,gy = goal
    if not (0<=sx<w and 0<=sy<h and 0<=gx<w and 0<=gy<h):
        return None
    if grid[sy,sx]==1 or grid[gy,gx]==1:
        return None
    def hcost(a,b):
        return abs(a[0]-b[0]) + abs(a[1]-b[1])
    open_heap = []
    heapq.heappush(open_heap, (0+hcost(start,goal), 0, start, None))
    came = {}
    gscore = {start:0}
    dirs=[(1,0),(-1,0),(0,1),(0,-1)]
    while open_heap:
        f, g, cur, parent = heapq.heappop(open_heap)
        if cur in came:
            continue
        came[cur]=parent
        if cur==(gx,gy):
            # reconstruct
            path=[]
            node=cur
            while node is not None:
                path.append(node)
                node=came[node]
            return list(reversed(path))
        x,y = cur
        for dx,dy in dirs:
            nx,ny = x+dx, y+dy
            if 0<=nx<w and 0<=ny<h and grid[ny,nx]==0:
                neigh=(nx,ny)
                ng = g+1
                if neigh in gscore and ng>=gscore[neigh]:
                    continue
                gscore[neigh]=ng
                heapq.heappush(open_heap, (ng + hcost(neigh, (gx,gy)), ng, neigh, cur))
    return None


# generate single scenario using simple random-obstacles + A* connectivity check
def gen_scenario(grid_size, density_min, density_max, max_attempts=30, min_frac=0.7, max_frac=0.8):
    w=h=grid_size
    # adjust density ranges per group/complexity if needed (caller may pass correct ranges)
    for attempt in range(max_attempts):
        grid = np.zeros((h,w), dtype=np.uint8)
        target_density = random.uniform(density_min, density_max)
        place_random_obstacles(grid, target_density)
        # pick start/goal with distance constraints: straight distance 50-80% of max_dim
        max_dim = max(w,h)
        # use adjusted distance fractions (min_frac, max_frac)
        min_d = min_frac * max_dim
        max_d = max_frac * max_dim
        start = random_free_position(grid)
        if start is None:
            continue
        goal = random_free_position(grid, min_dist_from=start, min_dist=min_d, max_tries=2000)
        if goal is None:
            # try random goal without constraint then check distance
            goal = random_free_position(grid, max_tries=2000)
            if goal is None:
                continue
        straight = ((start[0]-goal[0])**2 + (start[1]-goal[1])**2)**0.5
        if not (min_d <= straight <= max_d):
            # try again
            continue
        # A* connectivity check with 60s not required here; simple_astar is fast
        path = simple_astar(grid, start, goal)
        if path is None:
            continue
        meta = {
            'type_group': None,
            'type_sub': None,
            'map_size':[w,h],
            'grid_resolution':GRID_RES,
            'robot_specification':ROBOT_SPEC,
            'start':[int(start[0]),int(start[1])],
            'goal':[int(goal[0]),int(goal[1])],
            'obstacle_ratio_actual':float(grid.sum()/(w*h)),
            'slope_mean':0.0,
            'grid':grid.tolist()
        }
        return meta
    # if normal attempts fail, perform fallback: allocate start/goal and carve a straight corridor
    for fallback_try in range(20):
        grid = np.zeros((h, w), dtype=np.uint8)
        target_density = random.uniform(density_min, density_max)
        place_random_obstacles(grid, target_density)
        # pick arbitrary start/goal and carve corridor
        sx = random.randrange(w)
        sy = random.randrange(h)
        gx = random.randrange(w)
        gy = random.randrange(h)
        # enforce distance if possible
        straight = ((sx-gx)**2 + (sy-gy)**2)**0.5
        min_d = min_frac * max_dim
        max_d = max_frac * max_dim
        if not (min_d <= straight <= max_d):
            # allow relaxed distance for fallback: accept 0.3..max_frac if strict fails
            if straight < 0.3 * max_dim or straight > max_d:
                continue
        # carve corridor of width MIN_PASSAGE_GRIDS
        carve_corridor(grid, (sx, sy), (gx, gy), MIN_PASSAGE_GRIDS)
        path = simple_astar(grid, (sx, sy), (gx, gy))
        if path is not None:
            meta = {
                'type_group': None,
                'type_sub': None,
                'map_size':[w,h],
                'grid_resolution':GRID_RES,
                'robot_specification':ROBOT_SPEC,
                'start':[int(sx),int(sy)],
                'goal':[int(gx),int(gy)],
                'obstacle_ratio_actual':float(grid.sum()/(w*h)),
                'slope_mean':0.0,
                'grid':grid.tolist()
            }
            return meta
    return None

# generate all
scenarios=[]
design = {'matrix':matrix}
for gk, gv in matrix['groups'].items():
    for ck, cv in matrix['complexities'].items():
        for i in range(SCEN_PER_TYPE):
            sid = f"dataset3_{gk}_{ck}_{i+1}"
            dr = densities_by_group[gk][ck]
            res = gen_scenario(gv['grid'], dr[0], dr[1])
            if res is None:
                print('Failed generate', sid)
                continue
            res['id']=sid
            res['type_group']=int(gk)
            res['type_sub']=int(ck)
            scenarios.append(res)
            # save sample image for first
            if i==0:
                grid = np.array(res['grid'])
                fig,ax = plt.subplots(figsize=(6,6))
                ax.imshow(grid, cmap='Greys', origin='lower')
                s,g = res['start'], res['goal']
                ax.scatter([s[0]],[s[1]], c='green', s=20)
                ax.scatter([g[0]],[g[1]], c='red', s=20)
                ax.axis('off')
                pth = RESULTS / f"dataset3_type{gk}-{ck}_sample.png"
                fig.savefig(pth, dpi=150)
                plt.close(fig)

# save outputs
with open('dataset3_scenarios.json','w') as f:
    json.dump(scenarios, f, indent=2)
with open('dataset3_matrix_design.json','w') as f:
    json.dump(design, f, indent=2)

# visualization 3x3
fig,axes = plt.subplots(3,3, figsize=(9,9))
for gi, gk in enumerate(['1','2','3']):
    for ci, ck in enumerate(['1','2','3']):
        fn = RESULTS / f"dataset3_type{gk}-{ck}_sample.png"
        ax = axes[gi,ci]
        if fn.exists():
            img = plt.imread(str(fn))
            ax.imshow(img)
        else:
            ax.text(0.5,0.5,'missing',ha='center',va='center')
        ax.set_title(f"{gk}-{ck}")
        ax.axis('off')
plt.tight_layout()
fig.savefig(RESULTS / 'dataset3_visualization_grid.png', dpi=150)

print('Wrote dataset3_scenarios.json and dataset3_matrix_design.json and samples')
