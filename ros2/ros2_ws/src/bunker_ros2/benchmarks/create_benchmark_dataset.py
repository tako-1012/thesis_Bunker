"""
標準ベンチマークデータセット作成

他の研究者が再現できるように
"""
import json
import numpy as np
from pathlib import Path

def create_benchmark_dataset():
    """
    標準ベンチマークを作成
    
    3つの難易度 × 50シナリオ = 150シナリオ
    """
    dataset = {
        'version': '1.0',
        'description': 'Standard benchmark for UGV path planning',
        'categories': {}
    }
    
    # Easy（簡単）
    dataset['categories']['easy'] = create_scenarios(
        difficulty='easy',
        num_scenarios=50,
        map_size=50.0,
        min_distance=10.0,
        max_distance=30.0
    )
    
    # Medium（中程度）
    dataset['categories']['medium'] = create_scenarios(
        difficulty='medium',
        num_scenarios=50,
        map_size=50.0,
        min_distance=20.0,
        max_distance=40.0
    )
    
    # Hard（困難）
    dataset['categories']['hard'] = create_scenarios(
        difficulty='hard',
        num_scenarios=50,
        map_size=50.0,
        min_distance=30.0,
        max_distance=50.0
    )
    
    # 保存
    output_file = Path('../benchmarks/standard_benchmark_v1.0.json')
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w') as f:
        json.dump(dataset, f, indent=2)
    
    print(f"✅ ベンチマークデータセット作成: {output_file}")
    print(f"   総シナリオ数: {sum(len(v) for v in dataset['categories'].values())}")
    
    return dataset

def create_scenarios(difficulty, num_scenarios, map_size, 
                    min_distance, max_distance):
    """シナリオ生成"""
    scenarios = []
    
    np.random.seed(42)  # 再現性
    
    for i in range(num_scenarios):
        while True:
            start = [
                np.random.uniform(-map_size/2 + 5, map_size/2 - 5),
                np.random.uniform(-map_size/2 + 5, map_size/2 - 5),
                0.2
            ]
            
            goal = [
                np.random.uniform(-map_size/2 + 5, map_size/2 - 5),
                np.random.uniform(-map_size/2 + 5, map_size/2 - 5),
                0.2
            ]
            
            distance = np.linalg.norm(np.array(goal) - np.array(start))
            
            if min_distance <= distance <= max_distance:
                break
        
        scenarios.append({
            'id': f'{difficulty}_{i:03d}',
            'start': start,
            'goal': goal,
            'distance': distance,
            'difficulty': difficulty
        })
    
    return scenarios

if __name__ == '__main__':
    create_benchmark_dataset()



