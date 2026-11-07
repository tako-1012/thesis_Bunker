#!/usr/bin/env bash
# One run of task 026 stage 3: run_one.sh R1|R2 NAME [LIMIT_S]. Worktree code, read-only; one beach only.
# R1 software rendering, RTF 0.3; R2 GPU rendering, RTF 1.0; stale 1.0 s for both.
# No set -e: a failure at any stage must not skip saving, sampler stop or status recording.
COND="${1:?R1 or R2}"; NAME="${2:?run name}"; LIMIT_S="${3:-2400}"
WT=/home/kotaro/thesis_Bunker_rtf/conference
R=$WT/results/rtf_check/divergence
RUN="$R/$NAME"; OUT="$RUN/physical_1"
PATCH=08OB87_-0706
DOMAIN=61
case "$COND" in
  R1) T=0.3; GPU_ARGS=(); SOFT=1 ;;
  R2) T=1.0; GPU_ARGS=(--gpus all -e NVIDIA_DRIVER_CAPABILITIES=all); SOFT=0 ;;
  *) echo "unknown condition"; exit 2 ;;
esac
cd "$WT" || exit 1
[ -z "$(docker ps -q)" ] || { echo "containers already running"; exit 2; }
[ -z "$(pgrep -x ruby)$(pgrep -f 'gz sim')" ] || { echo "another Gazebo is running"; exit 2; }
[ ! -e "$RUN" ] || { echo "output exists; not overwriting"; exit 2; }
mkdir -p "$OUT"; OUT=$(cd "$OUT" && pwd)
python3 "$R/resource_sampler.py" "$RUN/resources.csv" "$RUN/sampler.stop" 5 &
{
  echo "started=$(date -Is)"; echo "host=$(hostname)"; echo "kernel=$(uname -r)"
  echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git branch --show-current)"
  echo "tracked_changes=$(git status --short | grep -v '^??' | wc -l)"
  echo "condition=$COND patch=$PATCH target_rtf=$T stale_timeout_s=1.0 software_rendering=$SOFT ros_domain_id=$DOMAIN time_limit_s=$LIMIT_S"
  docker image inspect thesis/jazzy-gz:1 --format 'image_id={{.Id}}'
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
} > "$RUN/run_conditions.txt" 2>&1
( sleep 60; nvidia-smi > "$RUN/nvidia_smi_60s.txt" 2>&1 ) &
timeout -k 60 "$LIMIT_S" docker run --rm --pull=never --network host "${GPU_ARGS[@]}" \
  -e ROS_DOMAIN_ID="$DOMAIN" -e THESIS_REAL_TIME_FACTOR="$T" -e THESIS_STALE_TIMEOUT_S=1.0 \
  -e THESIS_FINE_PROTOCOL=rtf_check -e THESIS_ONLY_PATCH="$PATCH" \
  -e THESIS_OUTPUT_UID="$(id -u)" -e THESIS_OUTPUT_GID="$(id -g)" \
  -e ROS_LOG_DIR=/tmp/thesis-ros-log -e PYTHONPATH=/conference \
  -e MPLCONFIGDIR=/tmp/thesis-mpl -e XDG_CACHE_HOME=/tmp/thesis-cache \
  -e OPENBLAS_NUM_THREADS=1 -e THESIS_CONFERENCE_DIR=/conference \
  -e QT_QPA_PLATFORM=offscreen -e LIBGL_ALWAYS_SOFTWARE="$SOFT" \
  -e THESIS_ROS_IMAGE=thesis/jazzy-gz:1 \
  -v "$WT:/conference:ro" -v "$OUT:/output" -v "$R/probe.py:/probe.py:ro" \
  -w /tmp thesis/jazzy-gz:1 bash -lc '
    finish_output() { chown -R "${THESIS_OUTPUT_UID}:${THESIS_OUTPUT_GID}" /output; }
    trap finish_output EXIT
    source /opt/ros/jazzy/setup.bash
    python3 -c "import numpy,scipy,matplotlib,pandas" || exit 90
    gz sim --versions
    colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install || exit 91
    source /tmp/thesis-install/setup.bash
    python3 /probe.py /output/probe.csv > /output/probe_stdout.txt 2>&1 &
    ( until f=$(ls /tmp/thesis-lidar-worlds-*/*/world.sdf 2>/dev/null | head -1); [ -n "$f" ]; do sleep 1; done
      sleep 2; grep -nE "max_step_size|real_time_factor|update_rate|render_engine" "$f" > /output/world_audit.txt
      while true; do date +%s.%N >> /output/gz_stats.txt; timeout 5 gz topic -e -t /stats -n 1 >> /output/gz_stats.txt 2>&1; sleep 15; done ) &
    python3 /conference/ros2_jazzy/gz_checks/lidar_checks.py --output /output --patch-count 3 --map fine
    code=$?
    echo "$code" > /output/lidar_checks_exit.txt
    exit 0
  ' > "$RUN/console.log" 2>&1
code=$?
echo "$code" > "$RUN/docker_exit.txt"
if [ "$code" = 124 ] || [ "$code" = 137 ]; then
  ids=$(docker ps -q --filter ancestor=thesis/jazzy-gz:1)
  [ -n "$ids" ] && docker stop $ids >> "$RUN/console.log" 2>&1
  docker run --rm --pull=never --user 0 -v "$OUT:/output" thesis/jazzy-gz:1 chown -R "$(id -u):$(id -g)" /output >> "$RUN/console.log" 2>&1
fi
touch "$RUN/sampler.stop"
sleep 6
echo "finished=$(date -Is) docker_exit=$code" >> "$RUN/run_conditions.txt"
python3 "$R/finalize_status.py" "$RUN" > "$RUN/finalize.log" 2>&1
echo "$?" > "$RUN/finalize_exit.txt"
