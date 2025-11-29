#!/bin/bash

echo "========================================="
echo "🚀 バンカー3D可視化システム起動"
echo "========================================="
echo ""

# Updated project path to restored Unity visualization project
PROJECT_PATH="/home/hayashi/thesis_work/unity/PathPlanningVisualization"
SCENE_PATH="Assets/Scenes/PathPlanningVisualization.unity"

# Unity Hubのパスを検索
UNITY_HUB="/usr/bin/unity-hub"
UNITY_EDITOR=$(find ~/.local/share/Unity/Hub/Editor -name "Unity" -type f 2>/dev/null | head -n 1)

if [ -z "$UNITY_EDITOR" ]; then
    echo "❌ Unity Editorが見つかりません"
    echo "Unity Hubから手動で起動してください"
    exit 1
fi

echo "✅ Unity Editor 検出: $UNITY_EDITOR"
echo "✅ プロジェクト: $PROJECT_PATH"
echo ""
echo "🎬 Unity起動中..."
echo ""

# Unityを起動
"$UNITY_EDITOR" -projectPath "$PROJECT_PATH" &

echo ""
echo "========================================="
echo "次のステップ:"
echo "1. Unity が起動するまで待つ（1-2分）"
echo "2. メニューから PathPlanning > 🚀 完全自動セットアップ を実行"
echo "3. Playボタンを押す"
echo "========================================="
