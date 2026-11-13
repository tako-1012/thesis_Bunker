#!/usr/bin/env bash
# Task035, one run via the unchanged run_lidar_checks.sh: run_one.sh PATCH P1|S1..S5 REP [LIMIT_S].
# Fine defaults (0.3x, stale 1.0 s, software rendering); --diagnostics always; ROS domain 63.
# While running, every new diag/periodic_*.npz is copied to diag_all/ (the runtime keeps only the newest 3; kept on hayashi only).
PATCH="${1:?}"; COND="${2:?}"; REP="${3:?}"; LIMIT_S="${4:-4500}"
BASE=(--ground-estimate non_obstacle --online-fixes v1)
REAL=(--sensors lidar_real+depth2)
case "$COND" in
  P1) ARGS=("${BASE[@]}") ;;
  S1) ARGS=("${REAL[@]}" "${BASE[@]}" --obstacle-reference prior) ;;
  S2) ARGS=("${REAL[@]}" "${BASE[@]}" --obstacle-reference local) ;;
  S3) ARGS=("${REAL[@]}" "${BASE[@]}" --obstacle-reference local --debris-box-height true) ;;
  S4) ARGS=("${REAL[@]}" "${BASE[@]}" --obstacle-reference local --prior-variant perturbed) ;;
  S5) ARGS=("${REAL[@]}" "${BASE[@]}" --obstacle-reference local --prior-variant none) ;;
  *) echo "unknown condition"; exit 2 ;;
esac
WT=/home/kotaro/thesis_Bunker_rtf/conference; R=$WT/results/eval_035; RUN="$R/runs/${PATCH}/${COND}_r${REP}"
cd "$WT" || exit 1
[ -z "$(docker ps -q)" ] || { echo "containers already running"; exit 2; }
[ -z "$(pgrep -x ruby)$(pgrep -f "gz sim")" ] || { echo "another Gazebo is running"; exit 2; }
[ ! -e "$RUN" ] || { echo "output exists; not overwriting"; exit 3; }
mkdir -p "$RUN/diag_all"
python3 "$R/resource_sampler.py" "$RUN/resources.csv" "$RUN/sampler.stop" 10 &
( while [ ! -e "$RUN/sampler.stop" ]; do for f in "$RUN"/physical_1/raw/*/diag/periodic_*.npz; do [ -e "$f" ] && [ ! -e "$RUN/diag_all/$(basename "$f")" ] && cp "$f" "$RUN/diag_all/" 2>/dev/null; done; sleep 2; done ) &
{ echo "started=$(date -Is)"; echo "commit=$(git rev-parse HEAD)"; echo "branch=$(git branch --show-current)"
  echo "tracked_changes=$(git status --short | grep -v "^??" | wc -l)"
  echo "patch=$PATCH condition=$COND rep=$REP args=${ARGS[*]} --diagnostics --map fine rtf=default(0.3) stale=default(1.0) software_rendering=default(1) ros_domain_id=63 limit_s=$LIMIT_S"
  docker image inspect thesis/jazzy-gz:1 --format "image_id={{.Id}}"; } > "$RUN/run_conditions.txt" 2>&1
THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$PATCH" THESIS_ROS_DOMAIN_ID=63 \
  timeout -k 60 "$LIMIT_S" bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$RUN/physical_1" --patch-count 3 --map fine "${ARGS[@]}" --diagnostics \
  > "$RUN/console.log" 2>&1
code=$?
echo "$code" > "$RUN/exit.txt"
if [ "$code" = 124 ] || [ "$code" = 137 ]; then
  ids=$(docker ps -q --filter ancestor=thesis/jazzy-gz:1); [ -n "$ids" ] && docker stop $ids >> "$RUN/console.log" 2>&1
  docker run --rm --pull=never --user 0 -v "$RUN/physical_1:/output" thesis/jazzy-gz:1 chown -R "$(id -u):$(id -g)" /output >> "$RUN/console.log" 2>&1
fi
for f in "$RUN"/physical_1/raw/*/diag/periodic_*.npz; do [ -e "$f" ] && cp -n "$f" "$RUN/diag_all/"; done
touch "$RUN/sampler.stop"; sleep 11
echo "finished=$(date -Is) exit=$code" >> "$RUN/run_conditions.txt"
