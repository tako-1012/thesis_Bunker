#!/usr/bin/env python3
"""
Visualize terrain samples from dataset3_with_terrain.json
"""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# Load data
with open('dataset3_with_terrain.json') as f:
    scenarios = json.load(f)

# Select representative samples (one from each type)
samples = {
    'basic': next(s for s in scenarios if s['terrain_metadata']['terrain_type'] == 'basic'),
    'moderate': next(s for s in scenarios if s['terrain_metadata']['terrain_type'] == 'moderate'),
    'complex': next(s for s in scenarios if s['terrain_metadata']['terrain_type'] == 'complex')
}

# Create visualization
fig = plt.figure(figsize=(15, 12))

for idx, (terrain_type, scenario) in enumerate(samples.items()):
    height_map = np.array(scenario['height_map'])
    meta = scenario['terrain_metadata']
    
    # 2D heatmap
    ax1 = plt.subplot(3, 3, idx*3 + 1)
    im = ax1.imshow(height_map, cmap='terrain', aspect='auto')
    ax1.set_title(f"{terrain_type.upper()}: {scenario['id']}\n2D Height Map")
    ax1.set_xlabel('X (grid)')
    ax1.set_ylabel('Y (grid)')
    plt.colorbar(im, ax=ax1, label='Elevation (m)')
    
    # 3D surface plot
    ax2 = fig.add_subplot(3, 3, idx*3 + 2, projection='3d')
    size = height_map.shape[0]
    x = np.arange(0, size)
    y = np.arange(0, size)
    X, Y = np.meshgrid(x, y)
    
    # Downsample for faster rendering (if size > 100)
    if size > 100:
        step = size // 50
        X = X[::step, ::step]
        Y = Y[::step, ::step]
        Z = height_map[::step, ::step]
    else:
        Z = height_map
    
    surf = ax2.plot_surface(X, Y, Z, cmap='terrain', alpha=0.8, 
                            linewidth=0, antialiased=True)
    ax2.set_title(f"3D Terrain View")
    ax2.set_xlabel('X')
    ax2.set_ylabel('Y')
    ax2.set_zlabel('Elevation (m)')
    ax2.view_init(elev=30, azim=45)
    
    # Slope histogram
    ax3 = plt.subplot(3, 3, idx*3 + 3)
    dy, dx = np.gradient(height_map)
    slope_rad = np.arctan(np.sqrt(dx**2 + dy**2))
    slope_deg = np.degrees(slope_rad)
    
    ax3.hist(slope_deg.flatten(), bins=50, edgecolor='black', alpha=0.7)
    ax3.axvline(meta['avg_slope_deg'], color='red', linestyle='--', 
                linewidth=2, label=f'Avg: {meta["avg_slope_deg"]:.1f}°')
    ax3.set_title(f"Slope Distribution")
    ax3.set_xlabel('Slope (degrees)')
    ax3.set_ylabel('Frequency')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Add metadata text
    info_text = (f"Elevation: {meta['min_elevation']:.1f} - {meta['max_elevation']:.1f}m\n"
                 f"Range: {meta['elevation_range']:.1f}m\n"
                 f"Avg Slope: {meta['avg_slope_deg']:.1f}°\n"
                 f"Max Slope: {meta['max_slope_deg']:.1f}°")
    ax3.text(0.98, 0.98, info_text, transform=ax3.transAxes,
             verticalalignment='top', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5),
             fontsize=8)

plt.tight_layout()
plt.savefig('benchmark_results/dataset3_terrain_visualization.png', dpi=200, bbox_inches='tight')
print("Saved visualization: benchmark_results/dataset3_terrain_visualization.png")

# Print summary
print("\n" + "="*70)
print("Terrain Visualization Complete")
print("="*70)
for terrain_type, scenario in samples.items():
    meta = scenario['terrain_metadata']
    print(f"\n{terrain_type.upper()}: {scenario['id']}")
    print(f"  Size: {scenario['map_size']}x{scenario['map_size']}")
    print(f"  Elevation: {meta['min_elevation']:.1f} - {meta['max_elevation']:.1f}m (range: {meta['elevation_range']:.1f}m)")
    print(f"  Slope: avg {meta['avg_slope_deg']:.1f}°, max {meta['max_slope_deg']:.1f}°")
