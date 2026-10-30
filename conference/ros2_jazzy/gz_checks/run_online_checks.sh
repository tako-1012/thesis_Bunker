#!/usr/bin/env bash
# Build/run in disposable ROS2 Jazzy; preserve the source checkout read-only.
set -euo pipefail
conference_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-${conference_dir}/results/online_mission/gazebo}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if docker run --rm --network host \
  -e ROS_DOMAIN_ID="${THESIS_ROS_DOMAIN_ID:-48}" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log -e PYTHONPATH=/conference \
  -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -v "$conference_dir:/conference:ro" -v "$output_dir:/output" \
  -w /tmp "${THESIS_ROS_IMAGE:-ros:jazzy-ros-base}" bash -lc '
    set -e
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    if ! command -v gz >/dev/null || ! python3 -c "import numpy,scipy,matplotlib,pandas"; then
      for source_file in /etc/apt/sources.list.d/*; do
        sed -i "s|http://packages.ros.org|https://packages.ros.org|g" "$source_file"
      done
      apt-get update
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ros-jazzy-ros-gz python3-numpy python3-scipy python3-matplotlib python3-pandas python3-colcon-common-extensions
    fi
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
    source /tmp/thesis-install/setup.bash
    python3 /conference/ros2_jazzy/gz_checks/online_checks.py --output /output
  '; then
  exit 0
else
  docker_status=$?
  python3 - "$output_dir" "$docker_status" <<'LAUNCH_FAILURE_JSON'
import json,sys
from pathlib import Path
(Path(sys.argv[1])/'launcher_failure.json').write_text(json.dumps(dict(status='not_completed',exit_code=int(sys.argv[2]),message='Docker dependency/build/check command failed. Inspect logs; no physical measurements were fabricated.'),indent=2)+'\n')
LAUNCH_FAILURE_JSON
  exit "$docker_status"
fi
