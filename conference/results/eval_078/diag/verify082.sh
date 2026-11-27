#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
root="$PWD/results/eval_078/diag"
loc="$PWD/.venv-localization/bin/python"
standard="$HOME/.venvs/thesis-python/bin/python"
pin=cc9b42f477555470dcba7adbb44fd0b46aa0a678
test "$(git rev-parse HEAD)" = "$pin"
test "$(git branch --show-current)" = claude/082-frame-check
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.
while tmux has-session -t =compare-082 2>/dev/null; do sleep 4; done
test "$(cat "$root/compare_exit.txt")" = 0
test "$(awk '$2=="START" {n++} END {print n+0}' "$root/compare_log.txt")" -eq 2
test "$(awk '$2=="END" {n++} END {print n+0}' "$root/compare_log.txt")" -eq 2

rc=0
"$loc" -u "$root/diagnose082.py" 2 > "$root/diagnose_log.txt" 2>&1 || rc=$?
echo "$rc" > "$root/diagnose_exit.txt"
(
    cd "$root"
    find confirmations -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > confirmation_sha256.txt
    sha256sum -c --quiet confirmation_sha256.txt
)
checkout=$(mktemp -d /tmp/thesis082-clean.XXXXXXXX)
git -c checkout.workers=1 worktree add --detach "$checkout" "$pin"
test -z "$(git -C "$checkout" status --porcelain)"
tests="$root/tests"
mkdir "$tests"
exec > "$tests/session_log.txt" 2>&1
trap 'rc=$?; printf "%s\n" "$rc" > "$tests/suite_exit.txt"; date -Is' EXIT
printf '%s\n' "$pin" > "$tests/commit.txt"
printf '%s\n' "$checkout" > "$tests/checkout.txt"
date -Is > "$tests/started.txt"
export MPLCONFIGDIR="$checkout/.matplotlib"
"$loc" -m pip freeze > "$tests/localization_pip_freeze.txt"
"$standard" -m pip freeze | awk '!/ @ / && !/^[-]e /' > "$tests/standard_pip_freeze.txt"

cd "$checkout/conference"
git ls-files 'tests/test_*.py' > "$tests/files.txt"
test -s "$tests/files.txt"
"$standard" - "$loc" "$tests" <<'PYTEST'
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import subprocess
import sys

localization, destination = map(Path, sys.argv[1:])
loc_site = subprocess.check_output(
    [localization, "-c", "import site; print(site.getsitepackages()[0])"], text=True).strip()
modules = [path.removesuffix(".py").replace("/", ".")
           for path in (destination / "files.txt").read_text().splitlines()]
isolated = {"tests.test_offline_localization", "tests.test_recording_bridge"}
mixed = {"tests.test_localizability_scan", "tests.test_drone_map_localizability"}


def run_test(module):
    if module in mixed:
        dispatch = "import runpy,sys;sys.path.append(sys.argv[1]);runpy.run_module(sys.argv[2],run_name='__main__')"
        command = [sys.executable, "-u", "-c", dispatch, loc_site, module]
    else:
        executable = localization if module in isolated else sys.executable
        command = [executable, "-u", "-m", module]
    with (destination / f"{module}.txt").open("x") as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    return module, result.returncode


with ThreadPoolExecutor(max_workers=2) as pool, (destination / "summary.txt").open("x") as summary:
    for finished in as_completed([pool.submit(run_test, module) for module in modules]):
        module, code = finished.result()
        summary.write(f"{module} {code}\n")
        summary.flush()
        print(f"{datetime.now().astimezone().isoformat(timespec='seconds')} TEST {module} {code}", flush=True)
PYTEST
LC_ALL=C sort "$tests/summary.txt" -o "$tests/summary.txt"
sed 's/\.py$//;s#/#.#g;s/$/ 0/' "$tests/files.txt" | LC_ALL=C sort | cmp - "$tests/summary.txt"
for module in tests.test_offline_localization tests.test_recording_bridge; do
    grep -E '^Ran [1-9][0-9]* tests? in ' "$tests/$module.txt"
    grep -qx 'OK' "$tests/$module.txt"
    if grep -iE '(SKIP:|skipped)' "$tests/$module.txt"; then exit 2; fi
done
grep -q '2 PASS: plane' "$tests/tests.test_localizability_scan.txt"
grep -q '2 PASS: landmarks' "$tests/tests.test_localizability_scan.txt"
grep -q '3 PASS: rough' "$tests/tests.test_drone_map_localizability.txt"
test -z "$(git status --short --untracked-files=no)"
date -Is > "$tests/finished.txt"
echo "TESTS_PASSED $(wc -l < "$tests/summary.txt")"
