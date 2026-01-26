#!/usr/bin/env bash
# Run the single cost function test in an isolated environment
set -euo pipefail
# Ensure workspace source is on PYTHONPATH
export PYTHONPATH="/home/hayashi/thesis_work/ros2/ros2_ws/src:$PYTHONPATH"
# Disable pytest plugin autoload to avoid ROS launch-testing interfering
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
pytest -q /home/hayashi/thesis_work/ros2/ros2_ws/src/bunker_ros2/test/test_cost_function.py::TestCostFunction
