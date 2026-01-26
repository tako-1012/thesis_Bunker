#!/usr/bin/env python3
"""Generate 3 terrain test scenarios (hill_detour, roughness_avoidance, combined_terrain)
Saves metadata JSON and NPZ data under `terrain_test_scenarios/`.
"""
import os
import json
import numpy as np

OUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'terrain_test_scenarios')
os.makedirs(OUT_DIR, exist_ok=True)


def create_hill_detour_scenario():
    grid_size = (100, 100, 20)
    voxel_size = 0.2

    elevation = np.zeros(grid_size, dtype=np.float32)
    roughness = np.ones(grid_size, dtype=np.float32) * 0.3
    density = np.ones(grid_size, dtype=np.float32) * 0.7

    cx = grid_size[0] / 2.0
    cy = grid_size[1] / 2.0
    for x in range(grid_size[0]):
        for y in range(grid_size[1]):
            dx = x - cx
            dy = y - cy
            dist = np.sqrt(dx * dx + dy * dy)
            if dist < 25:
                # hill height up to ~10m center
                height = 10.0 * np.exp(-(dist ** 2) / (2 * (10 ** 2)))
            else:
                height = 0.0
            for z in range(grid_size[2]):
                elevation[x, y, z] = height

    voxel_grid = np.zeros(grid_size, dtype=np.uint8)

    start = (-8.0, -8.0, 0.5)
    goal = (8.0, 8.0, 0.5)

    return {
        'name': 'hill_detour',
        'grid_size': grid_size,
        'voxel_size': voxel_size,
        'voxel_grid': voxel_grid,
        'terrain_data': {
            'elevation': elevation,
            'roughness': roughness,
            'density': density
        },
        'start': start,
        'goal': goal,
        'description': 'Hill in center, detour routes on sides'
    }


def create_roughness_avoidance_scenario(seed=0):
    np.random.seed(seed)
    grid_size = (100, 100, 20)
    voxel_size = 0.2

    elevation = np.zeros(grid_size, dtype=np.float32)
    roughness = np.ones(grid_size, dtype=np.float32) * 0.2
    density = np.ones(grid_size, dtype=np.float32) * 0.7

    for x in range(grid_size[0]):
        for y in range(grid_size[1]):
            if 35 <= x <= 65:
                roughness[x, y, :] = 0.8

    # No obstacles for simplified scenario
    voxel_grid = np.zeros(grid_size, dtype=np.uint8)

    # Move along Y-axis to create left/right detour choices
    start = (0.0, -8.0, 0.5)
    goal = (0.0, 8.0, 0.5)

    return {
        'name': 'roughness_avoidance',
        'grid_size': grid_size,
        'voxel_size': voxel_size,
        'voxel_grid': voxel_grid,
        'terrain_data': {
            'elevation': elevation,
            'roughness': roughness,
            'density': density
        },
        'start': start,
        'goal': goal,
        'description': 'Rough terrain in center, smooth on sides'
    }


def create_combined_terrain_scenario(seed=1):
    np.random.seed(seed)
    grid_size = (120, 120, 20)
    voxel_size = 0.2

    elevation = np.zeros(grid_size, dtype=np.float32)
    roughness = np.ones(grid_size, dtype=np.float32) * 0.3
    density = np.ones(grid_size, dtype=np.float32) * 0.7

    # Area 1 (left)
    for x in range(40):
        elevation[x, :, :] = 0.0
        roughness[x, :, :] = 0.2
        density[x, :, :] = 0.9

    # Area 2 (center)
    for x in range(40, 80):
        for y in range(grid_size[1]):
            slope = (x - 40) / 40.0 * 3.0
            elevation[x, y, :] = slope
            roughness[x, y, :] = 0.3
            density[x, y, :] = 0.8

    # Area 3 (right)
    for x in range(80, 120):
        elevation[x, :, :] = 3.0
        roughness[x, :, :] = 0.7
        density[x, :, :] = 0.3

    # No obstacles for simplified combined scenario
    voxel_grid = np.zeros(grid_size, dtype=np.uint8)

    start = (-10.0, 0.0, 0.5)
    goal = (10.0, 0.0, 0.5)

    return {
        'name': 'combined_terrain',
        'grid_size': grid_size,
        'voxel_size': voxel_size,
        'voxel_grid': voxel_grid,
        'terrain_data': {
            'elevation': elevation,
            'roughness': roughness,
            'density': density
        },
        'start': start,
        'goal': goal,
        'description': 'Combined terrain with slope, roughness, and density variations'
    }


if __name__ == '__main__':
    generators = [create_hill_detour_scenario, create_roughness_avoidance_scenario, create_combined_terrain_scenario]
    for gen in generators:
        scen = gen()
        name = scen['name']
        meta = {
            'name': name,
            'grid_size': scen['grid_size'],
            'voxel_size': scen['voxel_size'],
            'start': scen['start'],
            'goal': scen['goal'],
            'description': scen['description']
        }
        meta_path = os.path.join(OUT_DIR, f"{name}_meta.json")
        data_path = os.path.join(OUT_DIR, f"{name}_data.npz")
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)
        np.savez(data_path,
                 voxel_grid=scen['voxel_grid'],
                 elevation=scen['terrain_data']['elevation'],
                 roughness=scen['terrain_data']['roughness'],
                 density=scen['terrain_data']['density'])
        print('Saved', meta_path, data_path)
