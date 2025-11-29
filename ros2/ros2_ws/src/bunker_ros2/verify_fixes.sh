#!/bin/bash

echo "======================================================================"
echo "🔍 修正確認テスト"
echo "======================================================================"

cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2

# 1. 簡易版統計テスト
echo -e "\n【テスト1: 統計的検定（簡易版）】"
python3 analysis/statistical_tests_simple.py

echo -e "\n" 
read -p "Enter キーを押して次へ..."

# 2. 高度な評価指標
echo -e "\n【テスト2: 高度な評価指標】"
python3 analysis/advanced_metrics_simple.py

echo -e "\n"
read -p "Enter キーを押して次へ..."

# 3. エラー分析
echo -e "\n【テスト3: エラー分析】"
python3 analysis/error_analysis_simple.py

echo -e "\n"
read -p "Enter キーを押して次へ..."

# 4. 新規性分析（既に成功）
echo -e "\n【テスト4: 新規性分析】"
if [ -f "analysis/novelty_analysis.py" ]; then
    python3 analysis/novelty_analysis.py | tail -30
else
    echo "⚠️ ファイルなし"
fi

echo -e "\n"
read -p "Enter キーを押して次へ..."

# 5. 理論的証明（既に成功）
echo -e "\n【テスト5: 理論的証明】"
if [ -f "../docs/theoretical_proof.tex" ]; then
    echo "✅ 理論的証明ファイル存在"
    echo "   場所: ../docs/theoretical_proof.tex"
    echo "   行数: $(wc -l < ../docs/theoretical_proof.tex) 行"
    echo ""
    echo "内容プレビュー:"
    head -20 ../docs/theoretical_proof.tex
else
    echo "⚠️ ファイルなし"
fi

echo -e "\n"
read -p "Enter キーを押して次へ..."

# 6. ベンチマーク（既に成功）
echo -e "\n【テスト6: 標準ベンチマーク】"
python3 << 'PYEOF'
import json
from pathlib import Path

benchmark_file = Path('../benchmarks/standard_benchmark_v1.0.json')
if benchmark_file.exists():
    with open(benchmark_file) as f:
        data = json.load(f)
    
    total = sum(len(scenarios) for scenarios in data['categories'].values())
    print(f"✅ ベンチマークシナリオ: {total}個")
    
    for category, scenarios in data['categories'].items():
        print(f"  {category}: {len(scenarios)}個")
else:
    print("❌ ベンチマークファイルなし")
PYEOF

echo -e "\n======================================================================"
echo "🎉 全テスト完了！"
echo "======================================================================"


