#!/bin/bash
echo "Phase 2 進捗確認"
echo "================"

if [ -f "../results/representative_terrain_results.json" ]; then
    python3 << 'EOF'
import json
from pathlib import Path

results_file = Path("../results/representative_terrain_results.json")
if results_file.exists():
    with open(results_file) as f:
        data = json.load(f)
    
    if 'statistics' in data:
        stats = data['statistics']
        total = stats.get('total_experiments', 0)
        completed = stats.get('completed_experiments', 0)
        failed = stats.get('failed_experiments', 0)
        
        if total > 0:
            progress = completed / total * 100
            print(f"進捗: {completed}/{total} ({progress:.1f}%)")
            print(f"失敗: {failed}")
            
            if stats.get('start_time'):
                import time
                elapsed = time.time() - stats['start_time']
                print(f"経過時間: {elapsed/3600:.2f}時間")
                
                if completed > 0:
                    remaining_time = (total - completed) * (elapsed / completed)
                    print(f"推定残り時間: {remaining_time/3600:.2f}時間")
        else:
            print("実験データがまだありません")
    
    # 地形別進捗
    if 'results' in data:
        print("\n地形別進捗:")
        for terrain, terrain_results in data['results'].items():
            if terrain_results:
                algo_count = len(terrain_results)
                print(f"  {terrain}: {algo_count} アルゴリズム完了")
else:
    print("結果ファイルがまだ作成されていません")
EOF
else
    echo "まだ実験が開始されていません"
fi



