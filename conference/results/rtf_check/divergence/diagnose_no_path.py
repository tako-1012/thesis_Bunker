"""Classify one failed LiDAR run from its saved final map (read-only on the run folder).

Rebuilds the planner's blocked mask as `seen & lethal`, plus nothing from the prior (soft mode:
unknown prior-lethal cells stay passable), then reruns the same A* from the final robot cell.
The saved map may hold a few scans newer than the failed plan, so `replay_success` is reported.
Class: goal_cell (goal lethal), start_cell (robot's own cell lethal; `replay_start_released_success` tells
whether the way ahead was still open), passage_closed (both free, A* fails),
not_reproduced (A* succeeds on the saved map).

Usage: python3 results/rtf_check/divergence/diagnose_no_path.py RAW_RUN [--figure out.png]
Run from conference/."""
import argparse, csv, json
from pathlib import Path
import numpy as np
from scipy.ndimage import label
from tapp.online_mission import astar
RES = .5

def diagnose(raw):
    raw = Path(raw)
    mission = json.loads((raw/'mission.json').read_text())
    state = mission.get('final_state') or {}
    m, ref = np.load(raw/'pointcloud_map.npz'), np.load(raw/'evaluation_reference.npz')
    lethal, seen = m['lethal'], m['seen']
    blocked = seen & lethal
    pose = state['pose'][:2]
    robot = tuple(int(round(v/RES)) for v in pose)
    rows = list(csv.DictReader((next(raw.glob('follower/*/replans.csv'))).open()))
    leg = int(rows[-1]['leg_index'])
    goal = tuple(mission['stops_cells'][leg])
    mult = np.ones(lethal.shape)
    replay = astar(blocked, robot, goal, mult)
    released = blocked.copy(); released[robot] = False
    relaxed = astar(released, robot, goal, mult)
    nb = blocked[max(robot[0]-1, 0):robot[0]+2, max(robot[1]-1, 0):robot[1]+2]
    region, _ = label(~blocked, structure=np.ones((3, 3)))
    same = region[robot] != 0 and region[robot] == region[goal]
    size = int((region == region[robot]).sum()) if region[robot] else 0
    ii, jj = np.indices(lethal.shape)
    near = lambda c, r: np.hypot(ii-c[0], jj-c[1]) <= r/RES
    false_all = blocked & ~ref['truth_lethal']
    out = dict(status=mission.get('status'), t=state.get('sim_time'), robot_xy=[round(v, 2) for v in pose], robot_cell=robot,
               leg=leg, goal_cell=goal, goal_lethal=bool(lethal[goal]), robot_cell_lethal=bool(lethal[robot]),
               lethal_1m_robot=int((near(robot, 1) & blocked).sum()), lethal_1m_goal=int((near(goal, 1) & blocked).sum()),
               false_lethal_1m_robot=int((near(robot, 1) & false_all).sum()), truth_lethal_1m_robot=int((near(robot, 1) & ref['truth_lethal']).sum()),
               false_lethal_seen_total=int(false_all.sum()), blocked_total=int(blocked.sum()),
               replay_success=bool(replay['success']), replay_start_released_success=bool(relaxed['success']),
               blocked_of_9_around_robot=int(nb.sum()), robot_goal_connected=bool(same), free_region_cells_at_robot=size)
    out['class'] = ('goal_cell' if out['goal_lethal'] else 'start_cell' if out['robot_cell_lethal']
                    else 'not_reproduced' if out['replay_success'] else 'passage_closed')
    return out, dict(blocked=blocked, seen=seen, truth=ref['truth_lethal'], rock=ref['truth_rock'],
                     track=np.array([[float(r['x']), float(r['y'])] for r in csv.DictReader((raw/'trajectory.csv').open())]),
                     robot=robot, goal=goal)

def figure(data, title, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5.4))
    code = np.zeros(data['blocked'].shape, int)
    code[~data['seen']] = 1
    code[data['truth']] = 2
    code[data['blocked'] & data['truth']] = 3
    code[data['blocked'] & ~data['truth']] = 4
    cmap = ListedColormap(['#fcfcfb', '#ecebe6', '#b9b8b2', '#52514e', '#eb6834'])
    for ax, centre, name in ((axes[0], data['robot'], 'Around the robot at failure'), (axes[1], data['goal'], 'Around the current goal')):
        ax.imshow(code.T, origin='lower', cmap=cmap, vmin=0, vmax=4, extent=(-.25, code.shape[0]*RES-.25, -.25, code.shape[1]*RES-.25), interpolation='nearest')
        ax.plot(*data['track'].T, color='#2a78d6', lw=2)
        ax.plot(data['robot'][0]*RES, data['robot'][1]*RES, 'o', ms=9, color='#2a78d6', mec='#fcfcfb', mew=2)
        ax.plot(data['goal'][0]*RES, data['goal'][1]*RES, '*', ms=15, color='#0b0b0b', mec='#fcfcfb', mew=1)
        ax.set_xlim(centre[0]*RES-8, centre[0]*RES+8); ax.set_ylim(centre[1]*RES-8, centre[1]*RES+8)
        ax.set_title(name, loc='left', fontsize=10); ax.set_xlabel('x [m]'); ax.set_ylabel('y [m]')
    fig.legend(handles=[Patch(color='#eb6834', label='Blocked in map, free in truth'), Patch(color='#52514e', label='Blocked in map and truth'),
                        Patch(color='#b9b8b2', label='Truth lethal, not blocked in map'), Patch(color='#ecebe6', label='Not seen'),
                        Line2D([], [], color='#2a78d6', lw=2, label='Trajectory'), Line2D([], [], marker='o', ls='', color='#2a78d6', label='Robot at end'),
                        Line2D([], [], marker='*', ls='', ms=11, color='#0b0b0b', label='Current goal')],
               loc='lower center', ncol=4, frameon=False, fontsize=9)
    fig.suptitle(title, x=.02, ha='left', fontsize=11)
    fig.tight_layout(rect=(0, .1, 1, .97)); fig.savefig(path, dpi=150)

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('run'); ap.add_argument('--figure')
    args = ap.parse_args()
    out, data = diagnose(args.run)
    print(json.dumps(out, default=str))
    if args.figure:
        figure(data, '08OB87_-0706 no_path on hayashi (software rendering, RTF 0.3)', args.figure)
