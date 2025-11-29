#!/bin/bash

echo "Phase 2完了待機中..."
echo "完了したら自動的にPhase 3-5を開始します"
echo ""

# Phase 2の結果ファイルを監視
RESULTS_FILE="../results/efficient_terrain_results.json"

while true; do
    if [ -f "$RESULTS_FILE" ]; then
        # 統計情報を確認
        COMPLETED=$(python3 -c "
import json
try:
    with open('$RESULTS_FILE') as f:
        data = json.load(f)
    if 'statistics' in data:
        print(data['statistics'].get('completed_experiments', 0))
    else:
        print(0)
except:
    print(0)
")
        
        TOTAL=$(python3 -c "
import json
try:
    with open('$RESULTS_FILE') as f:
        data = json.load(f)
    if 'statistics' in data:
        print(data['statistics'].get('total_experiments', 200))
    else:
        print(200)
except:
    print(200)
")
        
        if [ "$COMPLETED" -eq "$TOTAL" ] && [ "$TOTAL" -gt 0 ]; then
            echo ""
            echo "✅ Phase 2完了検出！"
            echo "   完了: $COMPLETED/$TOTAL"
            echo ""
            echo "Phase 3-5を自動開始します..."
            sleep 2
            ./auto_run_remaining_phases.sh
            break
        else
            PROGRESS=$(echo "scale=1; $COMPLETED * 100 / $TOTAL" | bc)
            echo -ne "\rPhase 2進捗: $COMPLETED/$TOTAL ($PROGRESS%)   "
        fi
    fi
    
    sleep 30  # 30秒ごとにチェック
done



