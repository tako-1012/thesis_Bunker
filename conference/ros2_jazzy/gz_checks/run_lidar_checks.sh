#!/usr/bin/env bash
# Standard Docker, headless ogre2, transient world/maps; first three then ten.
# Usage: run_lidar_checks.sh OUTPUT [--edge-margin-m 0|10] [--waypoint-check none|substitute] [other options]
# For --ground-near-obstacle exclude also pass --map fine --ground-estimate non_obstacle.
# --steep-clearance distance requires --map fine.
set -euo pipefail
conference_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-${conference_dir}/results/gazebo_lidar/physical_3}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
if [[ -e "$output_dir/manifest.json" ]]; then
  echo '既存記録は上書きしません。新しい保存先を指定してください。' >&2
  exit 2
fi
lidar_map_method=coarse
lidar_extra_args=("${@:2}")
for ((lidar_arg_index=0; lidar_arg_index<${#lidar_extra_args[@]}; lidar_arg_index++)); do
  if [[ "${lidar_extra_args[$lidar_arg_index]}" == --map ]] && ((lidar_arg_index+1<${#lidar_extra_args[@]})); then
    lidar_map_method="${lidar_extra_args[$((lidar_arg_index+1))]}"
  elif [[ "${lidar_extra_args[$lidar_arg_index]}" == --map=* ]]; then
    lidar_map_method="${lidar_extra_args[$lidar_arg_index]#--map=}"
  fi
done
lidar_real_time_factor="${THESIS_REAL_TIME_FACTOR:-1}"
lidar_stale_timeout="${THESIS_STALE_TIMEOUT_S:-0.5}"
if [[ "$lidar_map_method" == fine ]]; then
  lidar_real_time_factor="${THESIS_REAL_TIME_FACTOR:-0.3}"
  lidar_stale_timeout="${THESIS_STALE_TIMEOUT_S:-1.0}"
fi
lidar_protocol_env=()
if [[ -n "${THESIS_FINE_PROTOCOL+x}" ]]; then
  lidar_protocol_env+=(-e "THESIS_FINE_PROTOCOL=$THESIS_FINE_PROTOCOL")
fi
if [[ -n "${THESIS_ONLY_PATCH+x}" ]]; then
  lidar_protocol_env+=(-e "THESIS_ONLY_PATCH=$THESIS_ONLY_PATCH")
fi
lidar_render_setup=
case "${THESIS_RENDER-cpu}" in
  cpu) lidar_render_args=(-e "LIBGL_ALWAYS_SOFTWARE=${THESIS_SOFTWARE_RENDERING:-1}") ;;
  gpu)
    lidar_egl_vendor=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
    if [[ ! -f "$lidar_egl_vendor" || ! -r "$lidar_egl_vendor" ]]; then
      printf 'THESIS_RENDER=gpu requires a readable NVIDIA EGL vendor file on the host: %s\n' "$lidar_egl_vendor" >&2
      exit 2
    fi
    lidar_render_args=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all -e THESIS_RENDER=gpu
      -v "$lidar_egl_vendor:$lidar_egl_vendor:ro" -e "__EGL_VENDOR_LIBRARY_FILENAMES=$lidar_egl_vendor")
    lidar_render_setup=$'    unset LIBGL_ALWAYS_SOFTWARE DISPLAY WAYLAND_DISPLAY\n'
    ;;
  *) printf '%s\n' 'THESIS_RENDER must be cpu or gpu.' >&2; exit 2 ;;
esac
docker run --rm --pull=never --network host \
  "${lidar_protocol_env[@]}" \
  -e ROS_DOMAIN_ID="${THESIS_ROS_DOMAIN_ID:-50}" \
  -e THESIS_REAL_TIME_FACTOR="$lidar_real_time_factor" \
  -e THESIS_STALE_TIMEOUT_S="$lidar_stale_timeout" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log -e PYTHONPATH=/conference \
  -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -e QT_QPA_PLATFORM=offscreen "${lidar_render_args[@]}" \
  -e THESIS_ROS_IMAGE="${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}" \
  -v "$conference_dir:/conference:ro" -v "$output_dir:/output" \
  -w /tmp "${THESIS_ROS_IMAGE:-thesis/jazzy-gz:1}" bash -lc "${lidar_render_setup}"'
    set -e
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    python3 -c "import numpy,scipy,matplotlib,pandas"
    gz sim --versions
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
    source /tmp/thesis-install/setup.bash
    python3 /conference/ros2_jazzy/gz_checks/lidar_checks.py --output /output "$@"
  ' bash "${@:2}" || {
    lidar_run_status=$?
    if [[ "${THESIS_RENDER-cpu}" == gpu ]]; then
      printf '%s\n' 'GPU run failed. If Docker cannot select an NVIDIA device, check NVIDIA Container Toolkit and docker run --gpus all with nvidia-smi. See the error above.' >&2
    fi
    exit "$lidar_run_status"
  }
# Task027 opt-in: pass --map fine --sensors lidar_real or lidar_real+depth2.
# Task039 opt-in: pass --map fine --real-time-factor 1.0 (fine default: 0.3).
# Options are forwarded unchanged; the Python CLI takes precedence over the environment.
# Task041 opt-in: pass --map fine --obstacle-clearance overlap.
# Task052 opt-in: pass --map fine --obstacle-clearance overlap_goal.
# Task055 opt-in: pass --map fine --steep-near-obstacle no_inflate.
# Task043 opt-in: pass --tracking corner_slow to the follower.
# Task045 opt-in: THESIS_RENDER=gpu enables NVIDIA headless EGL rendering.
# Task047 opt-in: pass --map fine --terrain-source prior.
# Task048 opt-in: pass --map fine --terrain-source prior_veto.
# Task051 opt-in: pass --save-plan-maps to record the maps used for online searches.
# Task058 opt-in: pass --pose-trace to record pose receipts, follower ticks and CPU load.
# Task060 opt-in: --map fine --obstacle-clearance distance [--clearance-soft-m 1.5].
# Task063 opt-in: --goal-region ring with --endpoint-policy none (the defaults are none).
