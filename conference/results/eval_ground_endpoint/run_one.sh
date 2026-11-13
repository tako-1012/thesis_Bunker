#!/usr/bin/env bash
# Task030, one run via the unchanged run_lidar_checks.sh: run_one.sh PATCH C0|C1|C2 REP [LIMIT_S].
# Fine defaults (0.3x, stale 1.0 s, software rendering), default 0.8 m LiDAR, --diagnostics always. Domain 63.
PATCH="${1:?}"; COND="${2:?}"; REP="${3:?}"; LIMIT_S="${4:-4500}"
case "$COND" in
  C0) ARGS=(--ground-estimate all_returns --endpoint-policy none) ;;
  C1) ARGS=(--ground-estimate non_obstacle --endpoint-policy none) ;;
  C2) ARGS=(--ground-estimate non_obstacle --endpoint-policy escape_component) ;;
  *) echo "unknown condition"; exit 2 ;;
esac
WT=/home/kotaro/thesis_Bunker_rtf/conference; R=$WT/results/eval_ground_endpoint; RUN="$R/runs/${PATCH}/${COND}_r${REP}"
cd "$WT" || exit 1
[ -z "$(docker ps -q)" ] || { echo "containers already running"; exit 2; }
[ -z "$(pgrep -x ruby)$(pgrep -f 'gz sim')" ] || { echo "another Gazebo is running"; exit 2; }
[ ! -e "$RUN" ] || { echo "output exists; not overwriting"; exit 3; }
mkdir -p "$RUN"
python3 "$R/resource_sampler.py" "$RUN/resources.csv" "$RUN/sampler.stop" 10 &
{ echo "started=$(date -Is)"; echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git branch --show-current)"
  echo "tracked_changes=$(git status --short | grep -v '^??' | wc -l)"
  echo "patch=$PATCH condition=$COND rep=$REP args=${ARGS[*]} --diagnostics --map fine sensors=default rtf=default(0.3) stale=default(1.0) software_rendering=default(1) ros_domain_id=63 limit_s=$LIMIT_S"
  docker image inspect thesis/jazzy-gz:1 --format 'image_id={{.Id}}'; } > "$RUN/run_conditions.txt" 2>&1
THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$PATCH" THESIS_ROS_DOMAIN_ID=63 \
  timeout -k 60 "$LIMIT_S" bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$RUN/physical_1" --patch-count 3 --map fine "${ARGS[@]}" --diagnostics \
  > "$RUN/console.log" 2>&1
code=$?
echo "$code" > "$RUN/exit.txt"
if [ "$code" = 124 ] || [ "$code" = 137 ]; then
  ids=$(docker ps -q --filter ancestor=thesis/jazzy-gz:1); [ -n "$ids" ] && docker stop $ids >> "$RUN/console.log" 2>&1
  docker run --rm --pull=never --user 0 -v "$RUN/physical_1:/output" thesis/jazzy-gz:1 chown -R "$(id -u):$(id -g)" /output >> "$RUN/console.log" 2>&1
fi
touch "$RUN/sampler.stop"; sleep 11
echo "finished=$(date -Is) exit=$code" >> "$RUN/run_conditions.txt"
