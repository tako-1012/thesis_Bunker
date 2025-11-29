#!/bin/bash

echo "╔════════════════════════════════════════╗"
echo "║  🤖 バンカー3D経路可視化システム      ║"
echo "║     ワンクリック起動                   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# 1. 環境チェック
echo "📋 Step 1/3: 環境チェック中..."
if [ ! -d "/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager/scenarios" ]; then
    echo "❌ シナリオディレクトリが見つかりません"
    exit 1
fi

if [ ! -f "/home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/simulation_manager/results/final_results.json" ]; then
    echo "❌ 実験結果ファイルが見つかりません"
    exit 1
fi

echo "✅ データファイル確認完了"
echo ""

# 2. Unity起動
echo "🎮 Step 2/3: Unity起動中..."
./scripts/launch_unity_visualization.sh

echo ""
echo "⏳ Unityの起動を待っています（30秒）..."
sleep 30

# 3. 使用方法表示
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  ✅ 起動完了！                         ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "📋 次の手順を実行してください："
echo ""
echo "  Unity エディタで："
echo "  ┌─────────────────────────────────┐"
echo "  │ 1. メニューバー > PathPlanning  │"
echo "  │    > 🚀 完全自動セットアップ    │"
echo "  │                                 │"
echo "  │ 2. OK をクリック                │"
echo "  │                                 │"
echo "  │ 3. 30秒待つ                     │"
echo "  │                                 │"
echo "  │ 4. ▶ Play ボタンをクリック      │"
echo "  └─────────────────────────────────┘"
echo ""
echo "  その後："
echo "  • UIから好きなシナリオを選択"
echo "  • Playボタンでバンカーが動く！"
echo "  • F9キーでデモ動画撮影"
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  人間の作業：合計3クリックだけ！      ║"
echo "╚════════════════════════════════════════╝"
