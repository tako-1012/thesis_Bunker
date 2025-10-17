#!/bin/bash

# 色付き出力
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}A* 3D クイックテスト（Day 10）${NC}"
echo ""

cd ~/thesis_work/ros2/ros2_ws/src/bunker_ros2/path_planner_3d

# 基本テストのみ実行
echo -e "${YELLOW}基本テスト実行中...${NC}"
python3 test_node_3d.py && python3 test_astar_basic.py && python3 test_cost_calculator.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ クイックテスト成功！${NC}"
else
    echo ""
    echo -e "${RED}❌ テスト失敗${NC}"
fi
