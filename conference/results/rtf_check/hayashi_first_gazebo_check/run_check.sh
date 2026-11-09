#!/usr/bin/env bash
# First Gazebo check on hayashi: existing run_lidar_checks.sh, fine map, first three beaches.
# Uses the documented defaults only. Keeps log, exit code, conditions; never overwrites a prior run.
S=/home/kotaro/thesis_Bunker/conference/results/hayashi_first_gazebo_check
OUT="$S/physical_3"
LIMIT_S=10800
cd /home/kotaro/thesis_Bunker/conference || exit 1
if [ -e "$OUT" ]; then echo "output exists; not overwriting" | tee "$S/run_refused.txt"; exit 2; fi
if [ "$(cat "$S/image_build/exit_code.txt" 2>/dev/null)" != 0 ]; then echo "image build not ok" | tee "$S/run_refused.txt"; exit 3; fi
if [ -n "$(docker ps -q)" ]; then echo "containers already running" | tee "$S/run_refused.txt"; exit 4; fi
{
  echo "started=$(date -Is)"; echo "host=$(hostname)"; echo "kernel=$(uname -r)"
  echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git branch --show-current)"
  echo "tracked_changes=$(git status --short | grep -v '^??' | wc -l)"
  git status --short
  echo "time_limit_s=$LIMIT_S"
  docker --version
  docker image inspect thesis/jazzy-gz:1 --format 'image_id={{.Id}} size={{.Size}}'
  docker image inspect osrf/ros:jazzy-desktop-full --format 'base_digests={{.RepoDigests}}'
  echo "host_gz=$(bash -c 'source /opt/ros/jazzy/setup.bash; gz sim --versions')"
  nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
  echo "command=timeout -k 60 $LIMIT_S bash ros2_jazzy/gz_checks/run_lidar_checks.sh $OUT --patch-count 3 --map fine"
} > "$S/run_conditions.txt" 2>&1
timeout -k 60 "$LIMIT_S" bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$OUT" --patch-count 3 --map fine > "$S/console.log" 2>&1
code=$?
if [ "$code" = 124 ] || [ "$code" = 137 ]; then
  ids=$(docker ps -q --filter ancestor=thesis/jazzy-gz:1)
  [ -n "$ids" ] && docker stop $ids >> "$S/console.log" 2>&1
fi
echo "$code" > "$S/exit_code.txt"
echo "finished=$(date -Is) exit=$code" >> "$S/run_conditions.txt"
