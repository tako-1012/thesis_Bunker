#!/usr/bin/env bash
# Standard Docker, headless ogre2, transient world/maps; first three then ten.
set -euo pipefail
conference_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-${conference_dir}/results/gazebo_lidar/physical_3}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if [[ -e "$output_dir/manifest.json" ]]; then
  echo '既存記録は上書きしません。新しい保存先を指定してください。' >&2
  exit 2
fi
docker run --rm --pull=never --network host \
  -e ROS_DOMAIN_ID="${THESIS_ROS_DOMAIN_ID:-50}" \
  -e THESIS_REAL_TIME_FACTOR="${THESIS_REAL_TIME_FACTOR:-1}" \
  -e THESIS_STALE_TIMEOUT_S="${THESIS_STALE_TIMEOUT_S:-0.5}" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log -e PYTHONPATH=/conference \
  -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -e QT_QPA_PLATFORM=offscreen -e LIBGL_ALWAYS_SOFTWARE="${THESIS_SOFTWARE_RENDERING:-1}" \
  -e THESIS_ROS_IMAGE="${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}" \
  -v "$conference_dir:/conference:ro" -v "$output_dir:/output" \
  -w /tmp "${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}" bash -lc '
    set -e
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    python3 -c "import numpy,scipy,matplotlib,pandas"
    gz sim --versions
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
    source /tmp/thesis-install/setup.bash
    python3 /conference/ros2_jazzy/gz_checks/lidar_checks.py --output /output "$@"
  ' bash "${@:2}"
