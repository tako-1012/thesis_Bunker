#!/usr/bin/env bash
# Run task 037 sequentially and summarize its retained records.
set -euo pipefail
cd "$(dirname "$0")/../.."
out="$PWD/results/real_sensors_compare"
py="$HOME/.venvs/thesis-python/bin/python"
export MPLBACKEND=Agg PYTHONDONTWRITEBYTECODE=1
if [[ ! -f "$out/tests_log/passed" ]]; then
  "$py" -m pip freeze > "$out/tests_log/pip_freeze.txt"
  while IFS= read -r pin; do
    grep -Fxi -- "$pin" "$out/tests_log/pip_freeze.txt"
  done < <(awk '/^[[:alnum:]]+==/' requirements-venv.txt)
  failed=0
  for test in tests/test_*.py; do
    module="tests.$(basename "$test" .py)"
    rc=0
    "$py" -m "$module" > "$out/tests_log/$module.log" 2>&1 || rc=$?
    echo "$module $rc" | tee -a "$out/tests_log/summary.txt"
    if ((rc)); then failed=1; fi
  done
  ((failed == 0))
  touch "$out/tests_log/passed"
fi
[[ "${1:-}" != test ]] || exit 0
exec 9>"$out/run.lock"
flock -n 9
[[ "$(git branch --show-current)" == claude/037-real-sensors ]]
[[ -z "$(git status --short -uno)" ]]
nvidia-smi > "$out/gpu.txt"
image=$(docker image inspect thesis/jazzy-gz:1 --format '{{.Id}}')
for patch in 08OB86_-0205 08OB88_-1417 08OB88_-0167 08OB88_00332 08OB89_-0847; do
  for rep in 1 2 3; do
    for condition in L LC; do
      run="$out/runs/$patch/${condition}_r$rep"
      [[ ! -e "$run" ]]
      [[ -z "$(docker ps -q)" ]]
      if pgrep -f '[g]z sim' || pgrep -x ruby; then exit 2; fi
      sensors=lidar_real
      if [[ "$condition" == LC ]]; then sensors=lidar_real+depth2; fi
      mkdir -p "$run/diag_all"
      args=(--patch-count 3 --map fine --ground-estimate non_obstacle --online-fixes v1
            --diagnostics --obstacle-reference prior --sensors "$sensors")
      {
        echo "started=$(date -Is)"
        echo "commit=$(git rev-parse HEAD) branch=$(git branch --show-current) tracked_changes=0"
        echo "image=$image patch=$patch condition=$condition rep=$rep rtf=0.3 software=1 domain=63"
        printf 'args=%s\n' "${args[*]}"
      } > "$run/run_conditions.txt"
      echo "$(date -Is) START $patch $condition $rep"
      copy_maps() {
        for file in "$run"/physical_1/raw/*/diag/periodic_*.npz; do
          if [[ -s "$file" && ! -e "$run/diag_all/$(basename "$file")" ]]; then
            if cp "$file" "$run/diag_all/.copy" && unzip -tqq "$run/diag_all/.copy"; then
              mv "$run/diag_all/.copy" "$run/diag_all/$(basename "$file")"
            fi
          fi
        done
      }
      rc=0
      THESIS_FINE_PROTOCOL=rtf_check THESIS_ONLY_PATCH="$patch" THESIS_ROS_DOMAIN_ID=63 \
        THESIS_REAL_TIME_FACTOR=0.3 THESIS_STALE_TIMEOUT_S=1.0 THESIS_SOFTWARE_RENDERING=1 \
        THESIS_ROS_IMAGE=thesis/jazzy-gz:1 \
        bash ros2_jazzy/gz_checks/run_lidar_checks.sh "$run/physical_1" "${args[@]}" \
        > "$run/console.log" 2>&1 &
      runner=$!
      while kill -0 "$runner" 2>/dev/null; do copy_maps; sleep 2; done
      wait "$runner" || rc=$?
      copy_maps
      echo "$rc" > "$run/exit.txt"
      echo "$(date -Is) END $patch $condition $rep exit=$rc bytes=$(du -sb "$run" | cut -f1)"
    done
  done
done
PYTHONPATH="$PWD" "$py" "$out/summarize037.py" | tee "$out/summary_log.txt"
date -Is > "$out/finished.txt"
