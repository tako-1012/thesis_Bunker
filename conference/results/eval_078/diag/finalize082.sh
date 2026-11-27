#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../.."
root="$PWD/results/eval_078/diag"
py="$PWD/.venv-localization/bin/python"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.
while tmux has-session -t =analysis-082 2>/dev/null; do sleep 4; done
test "$(cat "$root/tests/suite_exit.txt")" = 0
test "$(cat "$root/diagnose_exit.txt")" = 0
test ! -e "$root/REPORT_ja.md"
"$py" -u "$root/check_stream082.py" > "$root/check_stream082_log.txt" 2>&1
for mode in off on; do
    cp "$root/confirmations/$mode/process_usage.csv" "$root/process_usage_$mode.csv"
done
"$py" - "$root/render082.py" "$root/REPORT_ja.md" <<'PYMD'
from pathlib import Path
import subprocess
import sys
report = subprocess.check_output([sys.executable, sys.argv[1]], text=True)
with Path(sys.argv[2]).open("x") as stream:
    stream.write(report.rstrip() + "\n")
PYMD
{
    printf '%s\n' '研究 PC hayashi の生の記録'         '/home/kotaro/thesis_Bunker_rtf/conference/results/eval_078/runs/'         '/home/kotaro/thesis_Bunker_rtf/conference/results/eval_078/diag/confirmations/'         '' '確認走行 2 回のファイルは confirmation_sha256.txt に相対パスと SHA-256 を保存。'         '研究 PC の diag ディレクトリで sha256sum -c --quiet confirmation_sha256.txt により全件照合した。'
    cd "$root"
    sha256sum confirmation_sha256.txt
    wc -l confirmation_sha256.txt
} > "$root/not_committed.txt"
date -Is
