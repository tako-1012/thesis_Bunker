#!/usr/bin/env python3
"""
Add terrain data (height_map) to all 90 scenarios in Dataset3.

Dataset3 currently has height_map=None for all scenarios.
This script generates terrain with varying complexity:
- Type 1 (dataset3_1_*): Basic terrain (5-10m elevation, 5-15° slopes)
- Type 2 (dataset3_2_*): Moderate terrain (10-20m elevation, 15-30° slopes)
- Type 3 (dataset3_3_*): Complex terrain (20-40m elevation, 30-45° slopes)

Terrain generation uses fractal noise with controllable parameters.
"""
import json
import numpy as np
import os
from pathlib import Path
import time
from scipy.ndimage import zoom


def generate_fractal_noise_2d(shape, octaves=4, persistence=0.5, rng=None):
    """Generate 2D fractal noise (multi-octave random noise)
    
    Args:
        shape: (height, width) of output array
        octaves: Number of noise layers to combine
        persistence: Amplitude decay between octaves
        rng: Random number generator
    
    Returns:
        2D numpy array with values in [0, 1]
    """
    if rng is None:
        rng = np.random.default_rng()
    
    height, width = shape
    noise = np.zeros((height, width))
    amplitude = 1.0
    frequency = 1.0
    max_value = 0.0
    
    for octave in range(octaves):
        # Generate random noise at this frequency
        octave_height = max(2, int(height / frequency))
        octave_width = max(2, int(width / frequency))
        
        # Random noise at lower resolution
        small_noise = rng.random((octave_height, octave_width))
        
        # Upsample to full resolution using bilinear interpolation
        zoom_factors = (height/octave_height, width/octave_width)
        large_noise = zoom(small_noise, zoom_factors, order=1)
        
        # Ensure exact size (zoom might create off-by-one errors)
        large_noise = large_noise[:height, :width]
        
        # Pad if necessary
        if large_noise.shape[0] < height or large_noise.shape[1] < width:
            pad_h = height - large_noise.shape[0]
            pad_w = width - large_noise.shape[1]
            large_noise = np.pad(large_noise, ((0, pad_h), (0, pad_w)), mode='edge')
        
        noise += large_noise * amplitude
        max_value += amplitude
        
        amplitude *= persistence
        frequency *= 2.0
    
    # Normalize to [0, 1]
    if max_value > 0:
        noise = noise / max_value
    
    return noise


def generate_terrain_basic(size, max_height=10.0, roughness=0.3, rng=None):
    """Generate basic terrain with gentle rolling hills
    
    Args:
        size: Grid size (assumes square grid)
        max_height: Maximum elevation in meters
        roughness: Terrain roughness [0-1], higher = more variation
        rng: Random number generator
    
    Returns:
        2D numpy array of height values
    """
    if rng is None:
        rng = np.random.default_rng()
    
    # Multi-scale fractal noise for natural terrain
    terrain = generate_fractal_noise_2d((size, size), octaves=3, persistence=0.5, rng=rng)
    
    # Add random tilt/slope
    x, y = np.meshgrid(np.linspace(0, 1, size), np.linspace(0, 1, size))
    tilt_angle = rng.uniform(5, 15)  # degrees
    tilt_dir = rng.uniform(0, 2*np.pi)
    tilt = (x * np.cos(tilt_dir) + y * np.sin(tilt_dir)) * np.tan(np.radians(tilt_angle))
    
    terrain = terrain + tilt * roughness
    
    # Normalize and scale
    terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min() + 1e-9)
    terrain = terrain * max_height
    
    return terrain


def generate_terrain_moderate(size, max_height=20.0, roughness=0.5, rng=None):
    """Generate moderate terrain with hills and valleys
    
    Args:
        size: Grid size
        max_height: Maximum elevation in meters
        roughness: Terrain roughness [0-1]
        rng: Random number generator
    
    Returns:
        2D numpy array of height values
    """
    if rng is None:
        rng = np.random.default_rng()
    
    # Multi-scale fractal noise with more detail
    terrain = generate_fractal_noise_2d((size, size), octaves=4, persistence=0.55, rng=rng)
    
    # Add some hills (Gaussian bumps)
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    num_hills = rng.integers(3, 8)
    for _ in range(num_hills):
        cx, cy = rng.integers(0, size, 2)
        sigma = rng.uniform(size/8, size/4)
        amplitude = rng.uniform(0.3, 0.7)
        hill = amplitude * np.exp(-((x-cx)**2 + (y-cy)**2) / (2*sigma**2))
        terrain += hill
    
    # Add valleys (negative bumps)
    num_valleys = rng.integers(2, 5)
    for _ in range(num_valleys):
        cx, cy = rng.integers(0, size, 2)
        sigma = rng.uniform(size/10, size/5)
        amplitude = rng.uniform(0.2, 0.4)
        valley = -amplitude * np.exp(-((x-cx)**2 + (y-cy)**2) / (2*sigma**2))
        terrain += valley
    
    # Normalize and scale
    terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min() + 1e-9)
    terrain = terrain * max_height
    
    return terrain


def generate_terrain_complex(size, max_height=40.0, roughness=0.7, rng=None):
    """Generate complex terrain with steep slopes, ridges, and valleys
    
    Args:
        size: Grid size
        max_height: Maximum elevation in meters
        roughness: Terrain roughness [0-1]
        rng: Random number generator
    
    Returns:
        2D numpy array of height values
    """
    if rng is None:
        rng = np.random.default_rng()
    
    # Multi-scale fractal noise with high detail
    terrain = generate_fractal_noise_2d((size, size), octaves=5, persistence=0.6, rng=rng)
    
    # Add ridges using ridge noise (absolute value creates sharp peaks)
    ridge_noise = generate_fractal_noise_2d((size, size), octaves=3, persistence=0.5, rng=rng)
    ridges = 1.0 - 2.0 * np.abs(ridge_noise - 0.5)  # Sharp ridges
    terrain = terrain + 0.3 * ridges
    
    # Add mountains (steep Gaussian bumps)
    x, y = np.meshgrid(np.arange(size), np.arange(size))
    num_mountains = rng.integers(5, 12)
    for _ in range(num_mountains):
        cx, cy = rng.integers(0, size, 2)
        sigma = rng.uniform(size/12, size/6)
        amplitude = rng.uniform(0.5, 1.2)
        mountain = amplitude * np.exp(-((x-cx)**2 + (y-cy)**2) / (2*sigma**2))
        terrain += mountain
    
    # Add deep valleys
    num_valleys = rng.integers(3, 7)
    for _ in range(num_valleys):
        cx, cy = rng.integers(0, size, 2)
        sigma = rng.uniform(size/15, size/8)
        amplitude = rng.uniform(0.4, 0.8)
        valley = -amplitude * np.exp(-((x-cx)**2 + (y-cy)**2) / (2*sigma**2))
        terrain += valley
    
    # Add some fractal detail
    fractal = generate_fractal_noise_2d((size, size), octaves=4, persistence=0.5, rng=rng)
    terrain = terrain + 0.1 * fractal
    
    # Normalize and scale
    terrain = (terrain - terrain.min()) / (terrain.max() - terrain.min() + 1e-9)
    terrain = terrain * max_height
    
    return terrain


def add_terrain_to_scenario(scenario, terrain_type='basic', rng=None):
    """Add height_map to a scenario based on its type
    
    Args:
        scenario: Scenario dictionary
        terrain_type: 'basic', 'moderate', or 'complex'
        rng: Random number generator
    
    Returns:
        Modified scenario with height_map added
    """
    if rng is None:
        rng = np.random.default_rng()
    
    # Handle map_size being either int or list
    map_size_raw = scenario['map_size']
    if isinstance(map_size_raw, (list, tuple)):
        size = int(max(map_size_raw))
    else:
        size = int(map_size_raw)
    
    # Generate terrain based on type
    if terrain_type == 'basic':
        # Type 1: Gentle terrain (5-10m, 5-15° slopes)
        max_height = rng.uniform(5, 10)
        roughness = rng.uniform(0.2, 0.4)
        height_map = generate_terrain_basic(size, max_height, roughness, rng)
        
    elif terrain_type == 'moderate':
        # Type 2: Moderate terrain (10-20m, 15-30° slopes)
        max_height = rng.uniform(10, 20)
        roughness = rng.uniform(0.4, 0.6)
        height_map = generate_terrain_moderate(size, max_height, roughness, rng)
        
    elif terrain_type == 'complex':
        # Type 3: Complex terrain (20-40m, 30-45° slopes)
        max_height = rng.uniform(20, 40)
        roughness = rng.uniform(0.6, 0.8)
        height_map = generate_terrain_complex(size, max_height, roughness, rng)
    
    else:
        raise ValueError(f"Unknown terrain type: {terrain_type}")
    
    # Add to scenario
    scenario['height_map'] = height_map.tolist()
    
    # Add terrain metadata
    if 'terrain_metadata' not in scenario:
        scenario['terrain_metadata'] = {}
    
    scenario['terrain_metadata']['terrain_type'] = terrain_type
    scenario['terrain_metadata']['max_elevation'] = float(height_map.max())
    scenario['terrain_metadata']['min_elevation'] = float(height_map.min())
    scenario['terrain_metadata']['elevation_range'] = float(height_map.max() - height_map.min())
    
    # Calculate average slope
    dy, dx = np.gradient(height_map)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    scenario['terrain_metadata']['avg_slope_deg'] = float(np.mean(slope_deg))
    scenario['terrain_metadata']['max_slope_deg'] = float(np.max(slope_deg))
    
    return scenario


def main():
    print("="*70)
    print("Adding Terrain Data to Dataset3")
    print("="*70)
    
    # Load existing dataset3
    input_file = 'dataset3_scenarios.json'
    if not os.path.exists(input_file):
        print(f"ERROR: {input_file} not found!")
        return
    
    print(f"\nLoading {input_file}...")
    with open(input_file, 'r') as f:
        scenarios = json.load(f)
    
    print(f"Loaded {len(scenarios)} scenarios")
    
    # Create backup
    backup_file = 'dataset3_scenarios_backup.json'
    if not os.path.exists(backup_file):
        print(f"\nCreating backup: {backup_file}")
        with open(backup_file, 'w') as f:
            json.dump(scenarios, f)
        print("Backup created successfully")
    else:
        print(f"\nBackup already exists: {backup_file}")
    
    # Determine terrain type for each scenario based on ID
    rng = np.random.default_rng(42)  # Fixed seed for reproducibility
    
    print("\n" + "="*70)
    print("Generating terrain data...")
    print("="*70)
    
    modified_scenarios = []
    start_time = time.time()
    
    for i, scenario in enumerate(scenarios):
        sid = scenario['id']
        
        # Determine terrain type from scenario ID
        if '_1_' in sid:
            terrain_type = 'basic'
        elif '_2_' in sid:
            terrain_type = 'moderate'
        elif '_3_' in sid:
            terrain_type = 'complex'
        else:
            # Fallback to basic
            terrain_type = 'basic'
        
        # Add terrain
        modified_scenario = add_terrain_to_scenario(scenario, terrain_type, rng)
        modified_scenarios.append(modified_scenario)
        
        # Progress report
        if (i + 1) % 10 == 0 or (i + 1) == len(scenarios):
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            eta = (len(scenarios) - i - 1) / rate if rate > 0 else 0
            
            meta = modified_scenario['terrain_metadata']
            print(f"{i+1:2d}/90 | {sid:20s} | {terrain_type:8s} | "
                  f"Elev: {meta['elevation_range']:5.1f}m | "
                  f"Slope: {meta['avg_slope_deg']:4.1f}° | "
                  f"ETA: {eta:4.0f}s")
    
    total_time = time.time() - start_time
    print(f"\nTerrain generation completed in {total_time:.1f}s")
    
    # Save to new file
    output_file = 'dataset3_with_terrain.json'
    print(f"\nSaving to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump(modified_scenarios, f, indent=2)
    
    print(f"Saved successfully!")
    
    # Summary statistics
    print("\n" + "="*70)
    print("Summary Statistics")
    print("="*70)
    
    types = {'basic': [], 'moderate': [], 'complex': []}
    for sc in modified_scenarios:
        t = sc['terrain_metadata']['terrain_type']
        types[t].append(sc['terrain_metadata'])
    
    for terrain_type, metas in types.items():
        if not metas:
            continue
        
        elev_ranges = [m['elevation_range'] for m in metas]
        avg_slopes = [m['avg_slope_deg'] for m in metas]
        max_slopes = [m['max_slope_deg'] for m in metas]
        
        print(f"\n{terrain_type.upper()} ({len(metas)} scenarios):")
        print(f"  Elevation range: {np.min(elev_ranges):.1f} - {np.max(elev_ranges):.1f}m "
              f"(avg: {np.mean(elev_ranges):.1f}m)")
        print(f"  Average slope:   {np.min(avg_slopes):.1f} - {np.max(avg_slopes):.1f}° "
              f"(avg: {np.mean(avg_slopes):.1f}°)")
        print(f"  Maximum slope:   {np.min(max_slopes):.1f} - {np.max(max_slopes):.1f}° "
              f"(avg: {np.mean(max_slopes):.1f}°)")
    
    print("\n" + "="*70)
    print("Next Steps:")
    print("="*70)
    print("1. Review dataset3_with_terrain.json")
    print("2. Visualize terrain samples (optional)")
    print("3. Replace dataset3_scenarios.json with dataset3_with_terrain.json")
    print("4. Re-run benchmarks to test TA* with terrain data")
    print("\nTo replace the file:")
    print(f"  mv dataset3_scenarios.json dataset3_scenarios_old.json")
    print(f"  mv dataset3_with_terrain.json dataset3_scenarios.json")
    

if __name__ == '__main__':
    main()
