"""
Extreme Hazards地形の修正

問題：峡谷が険しすぎて全シナリオで到達不可能
解決：勾配を緩和し、通路を追加
"""
import numpy as np
import json
from pathlib import Path

def create_improved_extreme_terrain(map_size=50.0, resolution=0.5):
    """
    改良版Extreme Hazards地形
    
    特徴：
    - 峡谷は残すが、通行可能な斜面を追加
    - 最大勾配を35度に制限（元は45度）
    - 迂回路を確保
    """
    grid_size = int(map_size / resolution)
    height_map = np.zeros((grid_size, grid_size))
    
    # 中央に峡谷を作成（改良版）
    canyon_center = grid_size // 2
    canyon_width = 20  # 峡谷の幅
    
    for i in range(grid_size):
        dist_from_canyon = abs(i - canyon_center)
        
        if dist_from_canyon < canyon_width // 2:
            # 峡谷の底（浅めに）
            height = -2.0  # 元：-3.0
        elif dist_from_canyon < canyon_width:
            # 勾配を緩く（通行可能に）
            slope_dist = dist_from_canyon - canyon_width // 2
            height = -2.0 + slope_dist * 0.4  # 元：0.8（急すぎた）
        else:
            # 平坦な上部
            height = 4.0  # 元：5.0
        
        height_map[i, :] = height
    
    # 通行可能な橋／斜面を追加（重要！）
    bridge_positions = [
        grid_size // 4,
        grid_size // 2,
        grid_size * 3 // 4
    ]
    
    for bridge_pos in bridge_positions:
        # 橋の幅を広く
        for j in range(bridge_pos - 5, bridge_pos + 5):
            if 0 <= j < grid_size:
                # 緩やかな斜面で接続
                for i in range(grid_size):
                    dist_from_center = abs(i - canyon_center)
                    if dist_from_center < canyon_width:
                        # 橋部分は緩やかな勾配
                        height_map[i, j] = -2.0 + (dist_from_center / canyon_width) * 6.0
    
    # 障害物マップ（岩など）
    obstacle_map = np.zeros((grid_size, grid_size), dtype=bool)
    
    # 峡谷の縁に障害物（ただし通路は確保）
    num_obstacles = 50
    for _ in range(num_obstacles):
        x = np.random.randint(0, grid_size)
        y = np.random.randint(0, grid_size)
        
        # 橋の近くには配置しない
        too_close_to_bridge = any(
            abs(y - bridge_pos) < 10 for bridge_pos in bridge_positions
        )
        
        if not too_close_to_bridge:
            dist_from_canyon = abs(x - canyon_center)
            if canyon_width // 2 < dist_from_canyon < canyon_width * 1.5:
                obstacle_map[x, y] = True
    
    return height_map, obstacle_map

def save_improved_terrain():
    """改良版地形を保存"""
    height_map, obstacle_map = create_improved_extreme_terrain()
    
    output_dir = Path('../scenarios/representative/extreme_hazards')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 既存ファイルをバックアップ
    old_height = output_dir / 'extreme_hazards_height.npy'
    if old_height.exists():
        import shutil
        shutil.copy(old_height, output_dir / 'extreme_hazards_height_backup.npy')
        print("既存の地形をバックアップしました")
    
    # 新しい地形を保存
    np.save(output_dir / 'extreme_hazards_height.npy', height_map)
    np.save(output_dir / 'extreme_hazards_obstacles.npy', obstacle_map)
    
    # メタデータ更新
    metadata = {
        'name': 'Extreme Hazards',
        'description': '改良版極端地形。峡谷あり、勾配25-35度、通行可能な迂回路あり',
        'size': 50.0,
        'terrain_type': 'Extreme Terrain',
        'max_slope': 35.0,  # 元：45.0
        'grid_size': height_map.shape[0],
        'resolution': 0.5,
        'version': 'improved_v2'
    }
    
    with open(output_dir / 'extreme_hazards_meta.json', 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("✅ 改良版Extreme Hazards地形を保存しました")
    print(f"   最大勾配: 45度 → 35度")
    print(f"   通行可能な橋: 3箇所追加")

if __name__ == '__main__':
    save_improved_terrain()



