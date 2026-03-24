import json
import numpy as np

# Load scenarios
with open('dataset3_scenarios.json', 'r') as f:
    scenarios = json.load(f)

print(f'Total scenarios: {len(scenarios)}')

# Analyze each type group
best_examples = {}

for type_group in [1, 2, 3]:
    group_scenarios = [s for s in scenarios if s['type_group'] == type_group]
    print(f'\n=== Type Group {type_group} ({["Simple", "Medium", "Complex"][type_group-1]}) ===')
    print(f'Count: {len(group_scenarios)}')
    
    # Analyze terrain characteristics
    stats = []
    for s in group_scenarios:
        # Use height_map instead of terrain
        terrain = np.array(s['height_map'])
        height_range = terrain.max() - terrain.min()
        mean_height = terrain.mean()
        std_height = terrain.std()
        
        # Calculate roughness (local variation)
        dy = np.abs(np.diff(terrain, axis=0))
        dx = np.abs(np.diff(terrain, axis=1))
        roughness = (dy.mean() + dx.mean()) / 2
        
        # Calculate max slope
        max_slope = max(dy.max(), dx.max())
        
        stats.append({
            'id': s['id'],
            'height_range': height_range,
            'mean': mean_height,
            'std': std_height,
            'roughness': roughness,
            'max_slope': max_slope
        })
    
    # For Simple (type 1): pick the one with SMALLEST height_range and roughness
    # For Complex (type 3): pick the one with LARGEST height_range and roughness
    # For Medium (type 2): pick something in the middle
    
    if type_group == 1:
        # Want flattest, smoothest
        best = min(stats, key=lambda x: x['height_range'] + x['roughness'] * 10)
    elif type_group == 3:
        # Want most varied, roughest
        best = max(stats, key=lambda x: x['height_range'] + x['roughness'] * 10)
    else:
        # Medium: sort by combined metric and pick median
        stats_sorted = sorted(stats, key=lambda x: x['height_range'] + x['roughness'] * 10)
        best = stats_sorted[len(stats_sorted) // 2]
    
    best_examples[type_group] = best
    
    print(f'  Selected ID: {best["id"]}')
    print(f'    Height range: {best["height_range"]:.2f}')
    print(f'    Std dev: {best["std"]:.2f}')
    print(f'    Roughness: {best["roughness"]:.4f}')
    print(f'    Max slope: {best["max_slope"]:.4f}')

print('\n=== SELECTED EXAMPLES ===')
for tg in [1, 2, 3]:
    print(f'{["Simple", "Medium", "Complex"][tg-1]}: ID {best_examples[tg]["id"]}')
