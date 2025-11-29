#!/bin/bash

echo "Phase 2 健全性チェック"
echo "===================="

# プロセス確認
if ps aux | grep -v grep | grep run_representative_terrain_experiment > /dev/null; then
    PID=$(ps aux | grep -v grep | grep run_representative_terrain_experiment | awk '{print $2}')
    echo "✅ プロセス実行中: PID $PID"
    
    # CPU使用率
    CPU=$(ps aux | grep -v grep | grep run_representative_terrain_experiment | awk '{print $3}')
    echo "   CPU使用率: ${CPU}%"
    
    if (( $(echo "$CPU > 50" | bc -l) )); then
        echo "   → 正常に計算中"
    else
        echo "   ⚠️ CPU使用率が低い（待機状態の可能性）"
    fi
else
    echo "❌ プロセスが実行されていません"
    exit 1
fi

# ログファイル確認
if [ -f "phase2_experiment.log" ] || [ -f "phase2_experiment_fixed.log" ]; then
    LOG_FILE=$([ -f "phase2_experiment.log" ] && echo "phase2_experiment.log" || echo "phase2_experiment_fixed.log")
    
    # 最終更新時刻
    LAST_MOD=$(stat -c %Y "$LOG_FILE")
    CURRENT=$(date +%s)
    DIFF=$((CURRENT - LAST_MOD))
    
    echo "ログファイル: $LOG_FILE"
    echo "   最終更新: ${DIFF}秒前"
    
    if [ $DIFF -lt 300 ]; then
        echo "   → 正常に更新中"
    else
        echo "   ⚠️ 5分以上更新されていません"
    fi
    
    # 最新のログ内容
    echo ""
    echo "最新ログ（最新5行）:"
    tail -5 "$LOG_FILE"
else
    echo "❌ ログファイルが見つかりません"
fi

echo ""
echo "===================="



