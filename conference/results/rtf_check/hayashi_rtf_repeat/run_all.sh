#!/usr/bin/env bash
# Fixed alternating order so slow drift of the machine does not line up with one RTF.
# A failed run never stops the rest; summaries always run.
R=/home/kotaro/thesis_Bunker/conference/results/hayashi_rtf_repeat
date -Is > "$R/all_started.txt"
for spec in "1 1" "0.3 1" "1 2" "0.3 2" "1 3" "0.3 3"; do
  set -- $spec
  echo "$(date -Is) start rtf=$1 rep=$2"
  bash "$R/run_one.sh" "$1" "$2"
  echo "$(date -Is) end rtf=$1 rep=$2 status=$?"
  sleep 10
done
python3 "$R/analyze_rtf.py" "$R" rtf_1_rep1 rtf_1_rep2 rtf_1_rep3 rtf_0.3_rep1 rtf_0.3_rep2 rtf_0.3_rep3 > "$R/analysis.log" 2>&1
echo "$?" > "$R/analysis_exit.txt"
python3 "$R/summarize_repeat.py" "$R" > "$R/summary.log" 2>&1
echo "$?" > "$R/summary_exit.txt"
date -Is > "$R/all_done.txt"
