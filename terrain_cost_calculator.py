#!/usr/bin/env python3
"""
Helper to compute actual cost (euclidean distance with terrain cost applied)
"""
import numpy as np
import math

def compute_actual_path_cost(path, terrain_data=None):
    """
    Compute the actual cost of a path considering terrain.
    
    Args:
        path: List of (x, y, z) world coordinates
        terrain_data: Dict with 'height_map' key
    
    Returns:
        (euclidean_distance, actual_cost)
    """
    if not path or len(path) < 2:
        return 0.0, 0.0
    
    euclidean_distance = 0.0
    actual_cost = 0.0
    
    for i in range(len(path) - 1):
        p1 = np.array(path[i], dtype=float)
        p2 = np.array(path[i + 1], dtype=float)
        segment_distance = np.linalg.norm(p2 - p1)
        euclidean_distance += segment_distance
        
        # Add terrain cost for segment
        if terrain_data and 'height_map' in terrain_data:
            # Use p2 as the endpoint for cost calculation
            x_idx = int(round(p2[0]))
            y_idx = int(round(p2[1]))
            height_map = terrain_data['height_map']
            
            # Clamp indices
            x_idx = min(max(x_idx, 0), height_map.shape[0] - 1)
            y_idx = min(max(y_idx, 0), height_map.shape[1] - 1)
            
            # Compute terrain cost at this point
            terrain_cost = compute_terrain_cost_at(x_idx, y_idx, height_map)
            actual_cost += segment_distance * terrain_cost
        else:
            actual_cost += segment_distance
    
    return euclidean_distance, actual_cost

def compute_terrain_cost_at(x, y, height_map):
    """Compute terrain cost at a specific voxel"""
    try:
        current_height = float(height_map[x, y])
        max_slope = 0.0
        
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < height_map.shape[0] and 0 <= ny < height_map.shape[1]:
                    neighbor_height = float(height_map[nx, ny])
                    slope = abs(neighbor_height - current_height)
                    max_slope = max(max_slope, slope)
        
        slope_degrees = np.degrees(np.arctan(max_slope))
        if slope_degrees < 15:
            cost = 1.0 + slope_degrees / 30.0
        elif slope_degrees < 30:
            cost = 1.5 + (slope_degrees - 15) / 15.0
        else:
            cost = min(2.5 + (slope_degrees - 30) / 30.0, 3.0)
        
        return float(cost)
    except Exception:
        return 1.0
