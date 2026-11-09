#!/usr/bin/env bash
# Target 1.0 first, then the 0.3 control with identical instrumentation; analysis always runs.
R=/home/kotaro/thesis_Bunker/conference/results/hayashi_rtf1_check
bash "$R/run_rtf.sh" 1
sleep 10
bash "$R/run_rtf.sh" 0.3
python3 "$R/analyze_rtf.py" "$R" rtf_1 rtf_0.3 > "$R/analysis.log" 2>&1
echo "$?" > "$R/analysis_exit.txt"
date -Is > "$R/all_done.txt"
