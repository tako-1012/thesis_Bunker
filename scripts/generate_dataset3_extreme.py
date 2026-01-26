#!/usr/bin/env python3
import json
import os
import random
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from collections import deque

OUT_DIR = Path('.')
RESULTS_DIR = OUT_DIR / 'benchmark_results'
RESULTS_DIR.mkdir(exist_ok=True)

random_seed = 12345
random.seed(random_seed)
np.random.seed(random_seed)

NUM_PER_TYPE = 30
SIZE_DISTRIB = {'Small':10,'Medium':12,'Large':8}

scenarios = []
parameters = {}

def sample_map_size(t, size_label):
    if t==1:
        return random.choice([500,600,700])
    if t==2:
        return 200
    if t==3:
        return random.choice([200,300])
    if t==4:
        return 300
    return 200

# Simple complexity method implementations (placeholders consistent with prior scripts)
def complexity_method1_slope(slope_mean):
    # normalized to ~0-1 assuming slope_mean in [0,5]
    if slope_mean is None:
        return 0.0
    return float(min(1.0, slope_mean / 5.0))

def complexity_method2_obstacle(obstacle_ratio):
    # obstacle_ratio in [0,1]
    return float(obstacle_ratio)

def complexity_method3_balanced(obstacle_ratio, slope_mean, map_area):
    # combine normalized obstacle and slope and map area factor
    marea = min(1.0, map_area / (700*700))
    s = complexity_method1_slope(slope_mean)
    o = complexity_method2_obstacle(obstacle_ratio)
    return float(0.5*o + 0.4*s + 0.1*marea)

def complexity_method4_statistical(obstacle_grid):
    # use simple clusteriness: fraction of obstacles that are in large connected blocks
    # obstacle_grid: 2D numpy 0/1
    from scipy import ndimage
    labeled, n = ndimage.label(obstacle_grid)
    if n==0:
        return 0.0
    counts = np.bincount(labeled.ravel())[1:]
    large_frac = counts[counts > (0.01 * obstacle_grid.size)].sum() if counts.size>0 else 0
    return float(large_frac / obstacle_grid.size)

# Helper to generate obstacle grid given density and special features
def generate_obstacle_grid(w,h,density,large_clusters=False,maze=False,passage_width=1):
    # Two modes: maze (wall-based carving) or random/cluster placement
    if maze:
        # wall-based recursive backtracker on odd-cell grid to ensure walls dominate
        grid = np.ones((h, w), dtype=np.uint8)
        # use cell coordinates at odd indices
        def carve_maze(passage_w):
            # initialize visited set on cell coordinates
            cw = (w - 1) // 2
            ch = (h - 1) // 2
            visited = [[False]*cw for _ in range(ch)]
            stack = [(0,0)]
            visited[0][0] = True
            while stack:
                x,y = stack[-1]
                # carve current cell center
                cx = 1 + x*2
                cy = 1 + y*2
                # carve passage width around center
                half = passage_w//2
                xs = max(0, cx-half)
                xe = min(w, cx-half+passage_w)
                ys = max(0, cy-half)
                ye = min(h, cy-half+passage_w)
                grid[ys:ye, xs:xe] = 0
                # find unvisited neighbors
                neighbors = []
                for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                    nx,ny = x+dx, y+dy
                    if 0<=nx<cw and 0<=ny<ch and not visited[ny][nx]:
                        neighbors.append((nx,ny))
                if neighbors:
                    nx,ny = random.choice(neighbors)
                    # knock down wall between (x,y) and (nx,ny)
                    wx = 1 + (x+nx)
                    wy = 1 + (y+ny)
                    # convert to grid coords
                    gx = wx
                    gy = wy
                    # carve connecting corridor width
                    cx2 = gx
                    cy2 = gy
                    xs = max(0, cx2-half)
                    xe = min(w, cx2-half+passage_w)
                    ys = max(0, cy2-half)
                    ye = min(h, cy2-half+passage_w)
                    grid[ys:ye, xs:xe] = 0
                    visited[ny][nx] = True
                    stack.append((nx,ny))
                else:
                    stack.pop()

        carve_maze(passage_width)
        return grid

    # base random placement for other types
    grid = np.zeros((h,w), dtype=np.uint8)
    total = w*h
    n = int(total * density)
    if n>0:
        idx = np.random.choice(total, n, replace=False)
        grid.flat[idx] = 1

    if large_clusters:
        # add several large rectangular clusters
        for _ in range(random.randint(3,7)):
            rw = random.randint(w//10, w//4)
            rh = random.randint(h//10, h//4)
            x = random.randint(0, max(0,w-rw-1))
            y = random.randint(0, max(0,h-rh-1))
            grid[y:y+rh, x:x+rw] = 1
    return grid


def place_start_goal(w,h,min_dist_ratio=0.7,max_dist_ratio=0.9):
    # place start in one corner and goal near opposite corner at specified diagonal distance
    diag = (w**2 + h**2)**0.5
    target = random.uniform(min_dist_ratio, max_dist_ratio) * diag
    # pick start corner
    starts = [(0,0),(0,h-1),(w-1,0),(w-1,h-1)]
    sx,sy = random.choice(starts)
    # choose goal along circle at distance target from start, constrained inside grid
    # try random angles until within bounds
    for _ in range(2000):
        ang = random.random()*2*np.pi
        gx = int(round(sx + target * np.cos(ang)))
        gy = int(round(sy + target * np.sin(ang)))
        if 0<=gx<w and 0<=gy<h:
            return (sx,sy),(gx,gy),target
    # fallback opposite corner
    ox,oy = w-1-sx, h-1-sy
    dist = ((ox-sx)**2 + (oy-sy)**2)**0.5
    return (sx,sy),(ox,oy),dist


def make_scenarios():
    sid = 0
    stats = {1:[],2:[],3:[],4:[]}
    for t in range(1,5):
        for i in range(NUM_PER_TYPE):
            sid += 1
            # choose size label distribution
            size_label = random.choices(list(SIZE_DISTRIB.keys()), weights=[SIZE_DISTRIB[k] for k in SIZE_DISTRIB])[0]
            map_size = sample_map_size(t, size_label)
            w = map_size
            h = map_size
            if t==1:
                obstacle_density = random.uniform(0.3,0.5)
                large_clusters = True
                maze=False
                passage_width=None
                start_goal_min=0.7
                start_goal_max=0.9
            elif t==2:
                obstacle_density = 0.35  # base, but maze overrides
                large_clusters = False
                maze=True
                passage_width = random.choice([1,2])
                start_goal_min=0.0
                start_goal_max=1.0
            elif t==3:
                obstacle_density = random.uniform(0.0,0.05)
                large_clusters=False
                maze=False
                passage_width=None
                start_goal_min=0.8
                start_goal_max=1.0
            elif t==4:
                obstacle_density = random.uniform(0.02,0.08)
                large_clusters=False
                maze=False
                passage_width=None
                start_goal_min=0.5
                start_goal_max=1.0
            # map and obstacles
            if t==2:
                # maze generation with verification
                attempt = 0
                ok = False
                grid = None
                verification = {'attempts':[]}
                while attempt<3 and not ok:
                    attempt += 1
                    g = generate_obstacle_grid(w,h,0,large_clusters=False,maze=True,passage_width=passage_width)
                    actual_ratio = float(g.sum()/(w*h))
                    (sx,sy),(gx,gy),dist = place_start_goal(w,h,min_dist_ratio=0.9,max_dist_ratio=0.99)
                    def is_connected(grid,a,b):
                        if grid[a[1],a[0]]==1 or grid[b[1],b[0]]==1:
                            return False
                        q = deque([a])
                        seen = set([a])
                        while q:
                            x,y = q.popleft()
                            if (x,y)==b:
                                return True
                            for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                                nx,ny = x+dx, y+dy
                                if 0<=nx<w and 0<=ny<h and grid[ny,nx]==0 and (nx,ny) not in seen:
                                    seen.add((nx,ny))
                                    q.append((nx,ny))
                        return False
                    connected = is_connected(g,(sx,sy),(gx,gy))
                    verification['attempts'].append({'attempt':attempt,'obstacle_ratio':actual_ratio,'connected':connected})
                    if actual_ratio >= 0.7 and connected:
                        ok = True
                        grid = g
                verification['status'] = 'ok' if ok else 'failed'
                parameters[f"dataset3_extreme_{sid}"] = {'map_size':[w,h],'size_label':size_label,'maze':True,'passage_width':passage_width,'seed':int(random.getrandbits(31)),'verification':verification}
            elif t==4:
                attempt = 0
                ok = False
                grid = None
                verification = {'attempts':[]}
                while attempt<3 and not ok:
                    attempt += 1
                    layout = random.choice([(2,2),(3,3)])
                    rows,cols = layout
                    num_rooms = rows*cols
                    room_w = random.randint(60,80)
                    room_h = random.randint(60,80)
                    wall_thickness = random.randint(2,3)
                    corridor_w = random.randint(5,8)
                    g = np.ones((h,w), dtype=np.uint8)
                    total_w = cols*room_w + (cols-1)*corridor_w + 2*wall_thickness
                    total_h = rows*room_h + (rows-1)*corridor_w + 2*wall_thickness
                    ox = max(0, (w - total_w)//2)
                    oy = max(0, (h - total_h)//2)
                    room_positions = []
                    for r in range(rows):
                        for c in range(cols):
                            x0 = ox + c*(room_w + corridor_w)
                            y0 = oy + r*(room_h + corridor_w)
                            rx0 = x0
                            ry0 = y0
                            rx1 = x0 + room_w + 2*wall_thickness
                            ry1 = y0 + room_h + 2*wall_thickness
                            rx1 = min(rx1, w)
                            ry1 = min(ry1, h)
                            interior_x0 = rx0 + wall_thickness
                            interior_y0 = ry0 + wall_thickness
                            interior_x1 = min(interior_x0 + room_w, w)
                            interior_y1 = min(interior_y0 + room_h, h)
                            g[interior_y0:interior_y1, interior_x0:interior_x1] = 0
                            room_positions.append(((interior_x0,interior_y0),(interior_x1,interior_y1)))
                    for r in range(rows):
                        for c in range(cols):
                            idx = r*cols + c
                            (x0,y0),(x1,y1) = room_positions[idx]
                            cx = (x0+x1)//2
                            cy = (y0+y1)//2
                            if c+1<cols:
                                nidx = r*cols + (c+1)
                                (nx0,ny0),(nx1,ny1) = room_positions[nidx]
                                ncx = (nx0+nx1)//2
                                y_start = max(0, cy - corridor_w//2)
                                y_end = min(h, y_start + corridor_w)
                                x_start = min(cx, ncx)
                                x_end = max(cx, ncx)
                                g[y_start:y_end, x_start:x_end] = 0
                            if r+1<rows:
                                nidx = (r+1)*cols + c
                                (nx0,ny0),(nx1,ny1) = room_positions[nidx]
                                ncy = (ny0+ny1)//2
                                x_start = max(0, cx - corridor_w//2)
                                x_end = min(w, x_start + corridor_w)
                                y_start = min(cy, ncy)
                                y_end = max(cy, ncy)
                                g[y_start:y_end, x_start:x_end] = 0
                    actual_ratio = float(g.sum()/(w*h))
                    verification['attempts'].append({'attempt':attempt,'obstacle_ratio':actual_ratio,'layout':layout,'room_count':num_rooms})
                    if 0.12 <= actual_ratio <= 0.3:
                        ok = True
                        grid = g
                verification['status'] = 'ok' if ok else 'failed'
                parameters[f"dataset3_extreme_{sid}"] = {'map_size':[w,h],'size_label':size_label,'layout':layout,'room_size':[room_w,room_h],'wall_thickness':wall_thickness,'corridor_width':corridor_w,'seed':int(random.getrandbits(31)),'verification':verification}
            else:
                grid = generate_obstacle_grid(w,h,obstacle_density,large_clusters=large_clusters,maze=maze,passage_width=passage_width if passage_width else 1)
                (sx,sy),(gx,gy),dist = place_start_goal(w,h,min_dist_ratio=start_goal_min,max_dist_ratio=start_goal_max)
            # If generation failed (grid None), create a conservative fallback to ensure valid map
            if grid is None:
                if t==2:
                    # fallback: full walls with a single carved corridor between corners
                    g = np.ones((h,w), dtype=np.uint8)
                    # carve simple diagonal corridor of width passage_width
                    pw = passage_width if passage_width else 1
                    for k in range(min(w,h)):
                        cx = int(k * (w-1) / (min(w,h)-1))
                        cy = int(k * (h-1) / (min(w,h)-1))
                        xs = max(0, cx - pw//2)
                        xe = min(w, xs + pw)
                        ys = max(0, cy - pw//2)
                        ye = min(h, ys + pw)
                        g[ys:ye, xs:xe] = 0
                    grid = g
                    # mark fallback
                    if f"dataset3_extreme_{sid}" in parameters:
                        parameters[f"dataset3_extreme_{sid}"]['fallback']='diagonal_corridor'
                elif t==4:
                    # fallback: simple 2x2 rooms
                    g = np.ones((h,w), dtype=np.uint8)
                    rows,cols = 2,2
                    room_w = 60
                    room_h = 60
                    wall_thickness = 2
                    corridor_w = 5
                    total_w = cols*room_w + (cols-1)*corridor_w + 2*wall_thickness
                    total_h = rows*room_h + (rows-1)*corridor_w + 2*wall_thickness
                    ox = max(0, (w - total_w)//2)
                    oy = max(0, (h - total_h)//2)
                    room_positions = []
                    for r in range(rows):
                        for c in range(cols):
                            x0 = ox + c*(room_w + corridor_w)
                            y0 = oy + r*(room_h + corridor_w)
                            interior_x0 = x0 + wall_thickness
                            interior_y0 = y0 + wall_thickness
                            interior_x1 = min(interior_x0 + room_w, w)
                            interior_y1 = min(interior_y0 + room_h, h)
                            g[interior_y0:interior_y1, interior_x0:interior_x1] = 0
                            room_positions.append(((interior_x0,interior_y0),(interior_x1,interior_y1)))
                    # connect center corridors
                    for r in range(rows):
                        for c in range(cols):
                            idx = r*cols + c
                            (x0,y0),(x1,y1) = room_positions[idx]
                            cx = (x0+x1)//2
                            cy = (y0+y1)//2
                            if c+1<cols:
                                nidx = r*cols + (c+1)
                                (nx0,ny0),(nx1,ny1) = room_positions[nidx]
                                ncx = (nx0+nx1)//2
                                y_start = max(0, cy - corridor_w//2)
                                y_end = min(h, y_start + corridor_w)
                                x_start = min(cx, ncx)
                                x_end = max(cx, ncx)
                                g[y_start:y_end, x_start:x_end] = 0
                            if r+1<rows:
                                nidx = (r+1)*cols + c
                                (nx0,ny0),(nx1,ny1) = room_positions[nidx]
                                ncy = (ny0+ny1)//2
                                x_start = max(0, cx - corridor_w//2)
                                x_end = min(w, x_start + corridor_w)
                                y_start = min(cy, ncy)
                                y_end = max(cy, ncy)
                                g[y_start:y_end, x_start:x_end] = 0
                    grid = g
                    if f"dataset3_extreme_{sid}" in parameters:
                        parameters[f"dataset3_extreme_{sid}"]['fallback']='simple_rooms'
                else:
                    grid = generate_obstacle_grid(w,h,obstacle_density,large_clusters=large_clusters,maze=maze,passage_width=passage_width if passage_width else 1)
            # compute actual obstacle ratio
            actual_ob_ratio = float(grid.sum()/(w*h))
            # slope: only meaningful for SLOPE_FOCUS -> use small / None
            slope_mean = None
            m1 = complexity_method1_slope(slope_mean)
            m2 = complexity_method2_obstacle(actual_ob_ratio)
            # method4 requires obstacle grid -> try/except if scipy missing
            try:
                m4 = complexity_method4_statistical(grid)
            except Exception:
                m4 = float(min(1.0, (grid.sum()>0) * (grid.sum()/(w*h) * 0.5)))
            m3 = complexity_method3_balanced(actual_ob_ratio, slope_mean, w*h)

            scen = {
                'id': f"dataset3_extreme_{sid}",
                'type': t,
                'type_name': {1:'HUGE_OPEN_SAMPLING',2:'NARROW_MAZE',3:'OPEN_THETA',4:'MULTI_ROOM'}[t],
                'seed': int(random.getrandbits(31)),
                'map_size': [w,h],
                'size_label': size_label,
                'obstacle_density_requested': obstacle_density,
                'obstacle_ratio_actual': m2,
                'start': [int(sx),int(sy)],
                'goal': [int(gx),int(gy)],
                'start_goal_requested_ratio': None if t==2 else None,
                'slope_mean': slope_mean,
                'complexity': {
                    'Method1_Slope': m1,
                    'Method2_Obstacle': m2,
                    'Method3_Balanced': m3,
                    'Method4_Statistical': m4
                }
            }
            scenarios.append(scen)
            stats[t].append({'map_size':w,'obstacle_ratio':m2,'size_label':size_label})
            # merge with any existing detailed parameter entry created during generation
            param_entry = parameters.get(f"dataset3_extreme_{sid}", {})
            param_entry.update({'map_size':[w,h],'size_label':size_label,'obstacle_density_requested':obstacle_density if 'obstacle_density_requested' not in param_entry else param_entry.get('obstacle_density_requested'), 'seed':scen['seed']})
            parameters[scen['id']] = param_entry
    return scenarios,stats

if __name__=='__main__':
    scs, stats = make_scenarios()
    # overwrite dataset3_scenarios.json
    with open('dataset3_scenarios.json','w') as f:
        json.dump(scs, f, indent=2)
    with open('dataset3_extreme_parameters.json','w') as f:
        json.dump(parameters, f, indent=2)
    design = {
        'name':'Dataset3 Extreme Redesign',
        'num_scenarios': len(scs),
        'per_type': NUM_PER_TYPE,
        'size_distribution_per_type': SIZE_DISTRIB,
        'seed': random_seed,
        'rationale': 'Four environment types designed to stress different planner classes: huge sampling-favourable maps, narrow mazes, open spaces for any-angle planners, and multi-room hierarchical maps.'
    }
    with open('dataset3_extreme_design_rationale.json','w') as f:
        json.dump(design, f, indent=2)

    # write a summary stats file
    summary = {}
    for t in range(1,5):
        arr = stats[t]
        sizes = [a['map_size'] for a in arr]
        orats = [a['obstacle_ratio'] for a in arr]
        summary[t] = {
            'count': len(arr),
            'map_size_min': int(min(sizes)),
            'map_size_max': int(max(sizes)),
            'obstacle_ratio_mean': float(np.mean(orats)),
            'obstacle_ratio_median': float(np.median(orats))
        }
    with open('dataset3_extreme_design_summary.json','w') as f:
        json.dump(summary, f, indent=2)

    # create visualization: one sample per type plus overall thumbnail grid
    fig = plt.figure(figsize=(12,9))
    for t in range(1,5):
        # pick first scenario of type
        idx = next(i for i,s in enumerate(scs) if s['type']==t)
        s = scs[idx]
        grid_w,grid_h = s['map_size']
        # regenerate obstacles for visualization using stored parameters
        p = parameters.get(s['id'], {})
        od = p.get('obstacle_density_requested', 0.0)
        grid = generate_obstacle_grid(grid_w,grid_h,od,large_clusters=p.get('large_clusters', False),maze=p.get('maze', False),passage_width=p.get('passage_width', 1))
        ax = fig.add_subplot(2,2,t)
        ax.imshow(grid, cmap='Greys', origin='lower')
        ax.scatter([s['start'][0]],[s['start'][1]], c='green', s=10, label='start')
        ax.scatter([s['goal'][0]],[s['goal'][1]], c='red', s=10, label='goal')
        ax.set_title(f"Type {t}: {s['type_name']} ({s['map_size'][0]}x{s['map_size'][1]})")
        ax.axis('off')
    plt.tight_layout()
    viz_path = RESULTS_DIR / 'dataset3_extreme_visualization.png'
    fig.savefig(viz_path, dpi=150)

    # also save three individual sample images
    sample_paths = {}
    for t in range(1,5):
        idx = next(i for i,s in enumerate(scs) if s['type']==t)
        s = scs[idx]
        p = parameters.get(s['id'], {})
        od = p.get('obstacle_density_requested', 0.0)
        grid = generate_obstacle_grid(s['map_size'][0],s['map_size'][1],od,large_clusters=p.get('large_clusters', False),maze=p.get('maze', False),passage_width=p.get('passage_width', 1))
        fig,ax = plt.subplots(figsize=(6,6))
        ax.imshow(grid, cmap='Greys', origin='lower')
        ax.scatter([s['start'][0]],[s['start'][1]], c='green', s=20)
        ax.scatter([s['goal'][0]],[s['goal'][1]], c='red', s=20)
        ax.set_title(f"Type {t} sample")
        ax.axis('off')
        pth = RESULTS_DIR / f'dataset3_type{t}_sample.png'
        fig.savefig(pth, dpi=150)
        sample_paths[t]=str(pth)
        plt.close(fig)

    print('Wrote dataset3_scenarios.json, parameters, design rationale and visualizations')
