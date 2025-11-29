#!/bin/bash

# ROS2ワークスペースのパス
WORKSPACE_DIR="$HOME/thesis_work/ros2/ros2_ws"
SETUP_CMD="cd $WORKSPACE_DIR && source install/setup.bash"

# Terminatorの設定ファイルを作成
create_terminator_config() {
    mkdir -p ~/.config/terminator
    cat > ~/.config/terminator/ros2_layout.config << 'EOF'
[global_config]
  suppress_multiple_term_dialog = True
  title_font = Sans 10

[keybindings]

[profiles]
  [[default]]
    background_darkness = 0.85
    cursor_color = "#aaaaaa"
    font = Monospace 10
    scrollback_infinite = True
    use_system_font = False

[layouts]
  [[ros2_workspace]]
    [[[window0]]]
      type = Window
      parent = ""
      title = ROS2 Workspace
      size = 1400, 900
    [[[child1]]]
      type = VPaned
      parent = window0
      ratio = 0.5
    [[[child2]]]
      type = HPaned
      parent = child1
      ratio = 0.5
    [[[child3]]]
      type = HPaned
      parent = child1
      ratio = 0.5
    [[[child4]]]
      type = HPaned
      parent = child3
      ratio = 0.5
    [[[terminal1]]]
      type = Terminal
      parent = child2
      profile = default
      directory = ~/thesis_work/ros2/ros2_ws
      command = bash -c "cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash && echo '=== Terminal 1: Ready ===' && exec bash"
    [[[terminal2]]]
      type = Terminal
      parent = child2
      profile = default
      directory = ~/thesis_work/ros2/ros2_ws
      command = bash -c "cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash && echo '=== Terminal 2: Ready ===' && exec bash"
    [[[terminal3]]]
      type = Terminal
      parent = child4
      profile = default
      directory = ~/thesis_work/ros2/ros2_ws
      command = bash -c "cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash && echo '=== Terminal 3: Ready ===' && exec bash"
    [[[terminal4]]]
      type = Terminal
      parent = child4
      profile = default
      directory = ~/thesis_work/ros2/ros2_ws
      command = bash -c "cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash && echo '=== Terminal 4: Ready ===' && exec bash"
    [[[terminal5]]]
      type = Terminal
      parent = child3
      profile = default
      directory = ~/thesis_work/ros2/ros2_ws
      command = bash -c "cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash && echo '=== Terminal 5: Ready ===' && exec bash"

[plugins]
EOF

    echo "Terminator設定ファイルを作成しました: ~/.config/terminator/ros2_layout.config"
}

# 別の方法：terminatorのコマンドラインオプションで直接分割する
launch_with_splits() {
    # Terminatorを起動して分割コマンドを送信
    terminator --maximize \
        --command="bash -c 'cd $WORKSPACE_DIR && source install/setup.bash && exec bash'" \
        --execute "bash -c '
            sleep 1
            # 右に分割 (Ctrl+Shift+E)
            xdotool key ctrl+shift+e
            sleep 0.5
            # 下に分割 (Ctrl+Shift+O)
            xdotool key ctrl+shift+o
            sleep 0.5
            # 左のペインに移動
            xdotool key alt+Left
            sleep 0.5
            # 下に分割
            xdotool key ctrl+shift+o
            sleep 0.5
            # 右上のペインに移動
            xdotool key alt+Up
            xdotool key alt+Right
            sleep 0.5
            # 下に分割
            xdotool key ctrl+shift+o
        '" &
}

# メイン処理
echo "ROS2ワークスペース用のTerminatorを起動します..."

# 方法1: 設定ファイルを使用（推奨）
if [ "$1" == "--config" ] || [ -z "$1" ]; then
    # 設定ファイルを作成
    create_terminator_config
    
    # 設定ファイルを使用してTerminatorを起動
    echo "分割レイアウトでTerminatorを起動しています..."
    terminator --config ~/.config/terminator/ros2_layout.config --layout ros2_workspace
    
# 方法2: xdotoolを使用した自動分割（要xdotoolインストール）
elif [ "$1" == "--auto" ]; then
    # xdotoolがインストールされているか確認
    if ! command -v xdotool &> /dev/null; then
        echo "xdotoolがインストールされていません。"
        echo "インストールするには: sudo apt-get install xdotool"
        exit 1
    fi
    launch_with_splits
    
# 方法3: 手動分割用のスクリプト
elif [ "$1" == "--manual" ]; then
    cat << 'MANUAL_INSTRUCTIONS'
====================================
Terminatorを起動後、以下の手順で分割してください：

1. Terminatorを起動
2. Ctrl+Shift+E : 縦に分割（右に新しいペイン）
3. Ctrl+Shift+O : 横に分割（下に新しいペイン）
4. Alt+矢印キー : ペイン間を移動
5. 必要に応じて分割を繰り返す

レイアウト例（5つのペイン）:
┌─────────┬─────────┐
│    1    │    2    │
├─────────┼────┬────┤
│    3    │ 4  │ 5  │
└─────────┴────┴────┘

各ペインで以下を実行:
cd ~/thesis_work/ros2/ros2_ws && source install/setup.bash
====================================
MANUAL_INSTRUCTIONS
    
    # 基本的なterminatorを起動
    terminator --working-directory="$WORKSPACE_DIR" \
        --command="bash -c 'cd $WORKSPACE_DIR && source install/setup.bash && exec bash'"
fi

echo ""
echo "使い方:"
echo "  $0          # 設定ファイルを使用（推奨）"
echo "  $0 --config # 設定ファイルを使用"
echo "  $0 --auto   # xdotoolで自動分割（要xdotoolインストール）"
echo "  $0 --manual # 手動分割の説明を表示"
