#!/bin/bash

# 色付き出力
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

clear
echo "======================================================================"
echo "Phase 2 実験監視ダッシュボード"
echo "======================================================================"
echo ""

# プロセス確認
if ps aux | grep -v grep | grep run_representative_terrain_experiment > /dev/null; then
    echo -e "${GREEN}✅ Phase 2実験: 実行中${NC}"
    PID=$(ps aux | grep -v grep | grep run_representative_terrain_experiment | awk '{print $2}')
    echo "   PID: $PID"
else
    echo -e "${RED}❌ Phase 2実験: 実行されていません${NC}"
    exit 1
fi

echo ""

# 結果ファイル確認
if [ -f "../results/representative_terrain_results.json" ]; then
    echo -e "${GREEN}結果ファイル: 存在${NC}"
    
    python3 << 'PYEOF'
import json
import time
from pathlib import Path

results_file = Path("../results/representative_terrain_results.json")
with open(results_file) as f:
    data = json.load(f)

if 'statistics' in data:
    stats = data['statistics']
    total = stats.get('total_experiments', 0)
    completed = stats.get('completed_experiments', 0)
    failed = stats.get('failed_experiments', 0)
    
    if total > 0:
        progress = completed / total * 100
        print(f"\n進捗: {completed}/{total} ({progress:.1f}%)")
        print(f"成功: {completed - failed}")
        print(f"失敗: {failed}")
        
        # プログレスバー
        bar_length = 50
        filled = int(bar_length * completed / total)
        bar = '█' * filled + '░' * (bar_length - filled)
        print(f"\n[{bar}]")
        
        if stats.get('start_time'):
            elapsed = time.time() - stats['start_time']
            print(f"\n経過時間: {elapsed/3600:.2f}時間")
            
            if completed > 0:
                avg_time = elapsed / completed
                remaining = (total - completed) * avg_time
                print(f"推定残り時間: {remaining/3600:.2f}時間")
                
                estimated_finish = time.time() + remaining
                finish_time = time.strftime('%H:%M', time.localtime(estimated_finish))
                print(f"推定完了時刻: {finish_time}")

# 地形別進捗
if 'results' in data:
    print("\n\n地形別進捗:")
    print("-" * 70)
    terrain_names = {
        'flat_agricultural_field': 'Flat Agricultural Field',
        'gentle_hills': 'Gentle Hills',
        'steep_terrain': 'Steep Terrain',
        'complex_obstacles': 'Complex Obstacles',
        'extreme_hazards': 'Extreme Hazards'
    }
    
    for terrain, terrain_results in data['results'].items():
        name = terrain_names.get(terrain, terrain)
        if terrain_results:
            algo_count = len(terrain_results)
            first_algo = list(terrain_results.keys())[0]
            scenario_count = len(terrain_results[first_algo])
            total_for_terrain = scenario_count * algo_count
            print(f"{name:30s}: {total_for_terrain:3d} 実験完了")
        else:
            print(f"{name:30s}: 実験待機中")
PYEOF
else
    echo -e "${YELLOW}結果ファイル: まだ作成されていません${NC}"
fi

echo ""
echo "======================================================================"
echo "リアルタイムログ（Ctrl+Cで終了）:"
echo "======================================================================"
tail -f phase2_experiment.log 2>/dev/null || tail -f phase2_experiment_fixed.log



