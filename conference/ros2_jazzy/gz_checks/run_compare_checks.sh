#!/usr/bin/env bash
# Disposable Jazzy build/runtime; source checkout stays read-only.
set -euo pipefail
conference_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-${conference_dir}/results/gazebo_compare}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
image="${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}"
if [[ -z "${THESIS_ROS_IMAGE:-}" ]] && ! docker image inspect "$image" >/dev/null 2>&1; then
  docker build -t "$image" -f "$conference_dir/ros2_jazzy/gz_checks/Dockerfile" "$conference_dir/ros2_jazzy/gz_checks"
fi
docker run --rm --network host \
  -e ROS_DOMAIN_ID="${THESIS_ROS_DOMAIN_ID:-49}" \
  -e THESIS_ROS_IMAGE="$image" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log -e PYTHONPATH=/conference \
  -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -v "$conference_dir:/conference:ro" -v "$output_dir:/output" -w /tmp \
  "$image" bash -lc '
    set -e
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    python3 -c "import numpy,scipy,matplotlib,pandas"
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
    source /tmp/thesis-install/setup.bash
    python3 /conference/ros2_jazzy/gz_checks/compare_checks.py --output /output
  '
