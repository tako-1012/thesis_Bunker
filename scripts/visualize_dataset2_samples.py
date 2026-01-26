import json
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt


def main():
    p = Path('dataset2_scenarios.json')
    if not p.exists():
        print('dataset2_scenarios.json not found')
        return
    with p.open() as f:
        scenarios = json.load(f)

    outdir = Path('benchmark_results')
    outdir.mkdir(exist_ok=True)

    # representative samples: first of each block
    samples = {
        'Steep': scenarios[0],
        'Dense': scenarios[48],
        'Complex': scenarios[96]
    }

    plt.rcParams['figure.dpi'] = 150
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    for idx, (env_type, scenario) in enumerate(samples.items()):
        ax_height = axes[0, idx]
        height_map = np.array(scenario['height_map'])
        im = ax_height.imshow(height_map, cmap='terrain', interpolation='nearest')
        ax_height.set_title(f'{env_type} Terrain - Height Map')
        ax_height.set_xlabel('X')
        ax_height.set_ylabel('Y')
        plt.colorbar(im, ax=ax_height, fraction=0.046, pad=0.04)
        start = scenario['start']
        goal = scenario['goal']
        ax_height.plot(start[0], start[1], 'go', markersize=6, label='Start')
        ax_height.plot(goal[0], goal[1], 'ro', markersize=6, label='Goal')
        ax_height.legend()

        ax_obs = axes[1, idx]
        obstacle_map = np.array(scenario['obstacle_map'])
        ax_obs.imshow(obstacle_map, cmap='binary', interpolation='nearest')
        ax_obs.set_title(f'{env_type} Terrain - Obstacles')
        ax_obs.set_xlabel('X')
        ax_obs.set_ylabel('Y')
        ax_obs.plot(start[0], start[1], 'go', markersize=6)
        ax_obs.plot(goal[0], goal[1], 'ro', markersize=6)

    plt.tight_layout()
    figpath = outdir / 'dataset2_environment_samples.png'
    fig.savefig(figpath, dpi=300, bbox_inches='tight')
    print('Wrote', figpath)

    # characteristics scatter
    fig2, axes2 = plt.subplots(1, 3, figsize=(15, 5))
    for idx, env in enumerate(['Steep', 'Dense', 'Complex']):
        ax = axes2[idx]
        start_idx = idx * 48
        env_scenarios = scenarios[start_idx:start_idx+48]
        slopes = [s['metadata'].get('mean_slope_deg', 0.0) for s in env_scenarios]
        densities = [s['metadata'].get('obstacle_density', 0.0) for s in env_scenarios]
        ax.scatter(slopes, densities, alpha=0.6, s=30)
        ax.set_xlabel('Average Slope (deg)')
        ax.set_ylabel('Obstacle Density')
        ax.set_title(f'{env} Characteristics')
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    figpath2 = outdir / 'dataset2_characteristics.png'
    fig2.savefig(figpath2, dpi=300, bbox_inches='tight')
    print('Wrote', figpath2)


if __name__ == '__main__':
    main()
