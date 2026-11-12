#!/usr/bin/env bash
# Task027 B0b, one run via the unchanged run_lidar_checks.sh (A2 forwards THESIS_FINE_PROTOCOL / THESIS_ONLY_PATCH).
# run_b0b.sh lidar_real|lidar_real+depth2 NAME. Fine defaults: 0.3x, stale 1.0 s, software rendering. Domain 62.
SENSORS="${1:?}"; NAME="${2:?}"
WT=/home/kotaro/thesis_Bunker_rtf/conference; R=$WT/results/real_sensors/b0b; RUN="$R/$NAME"
cd "$WT" || exit 1
[ -z "$(docker ps -q)" ] || { echo "containers already running"; exit 2; }
[ -z "$(pgrep -x ruby)$(pgrep -f 'gz sim')" ] || { echo "another Gazebo is running"; exit 2; }
[ ! -e "$RUN" ] || { echo "output exists; not overwriting"; exit 2; }
mkdir -p "$RUN"
python3 "$R/resource_sampler.py" "$RUN/resources.csv" "$RUN/sampler.stop" 5 &
{ echo "started=$(date -Is)"; echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git branch --show-current)"
  echo "tracked_changes=$(git status --short | grep -v '^??' | wc -l)"
  echo "sensors=$SENSORS patch=08OB86_-0205 map=fine rtf=default(0.3) stale=default(1.0) software_rendering=default(1) ros_domain_id=62"
  docker image inspect thesis/jazzy-gz:1 --format 'image_id={{.Id}}'; } > "$RUN/run_conditions.txt" 2>&1
THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH=08OB86_-0205 THESIS_ROS_DOMAIN_ID=62 \
  timeout -k 60 2400 bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$RUN/physical_1" --patch-count 3 --map fine --sensors "$SENSORS" \
  > "$RUN/console.log" 2>&1
code=$?
echo "$code" > "$RUN/exit.txt"
touch "$RUN/sampler.stop"; sleep 6
echo "finished=$(date -Is) exit=$code" >> "$RUN/run_conditions.txt"
