#!/usr/bin/env bash
# The source checkout is read-only inside the official Jazzy image.
set -euo pipefail
conference_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-${conference_dir}/ros2_jazzy/gz_checks/results}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if docker run --rm --network host \
  -e ROS_DOMAIN_ID="${THESIS_ROS_DOMAIN_ID:-47}" \
  -e THESIS_ROS_IMAGE="${THESIS_ROS_IMAGE:-osrf/ros:jazzy-desktop-full}" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log \
  -e PYTHONPATH=/conference -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -v "$conference_dir:/conference:ro" -v "$output_dir:/output" \
  -w /tmp "${THESIS_ROS_IMAGE:-osrf/ros:jazzy-desktop-full}" bash -lc '
    set -e
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    python3 -c "import numpy, scipy, matplotlib"
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
    source /tmp/thesis-install/setup.bash
    python3 /conference/ros2_jazzy/gz_checks/checks.py --output /output
  '; then
  exit 0
else
  docker_status=$?
  python3 - "$output_dir" "$docker_status" <<'LAUNCH_FAILURE_JSON'
import json,sys
from pathlib import Path
output=Path(sys.argv[1])
(output/'launcher_failure.json').write_text(json.dumps(dict(status='command_failed',exit_code=int(sys.argv[2]),message='Docker/build/check command failed; inspect environment and results/logs. No measurements were fabricated.'),indent=2)+'\n')
LAUNCH_FAILURE_JSON
  exit "$docker_status"
fi
