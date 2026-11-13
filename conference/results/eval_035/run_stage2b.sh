#!/usr/bin/env bash
# Stage 2b (only after S2 is judged to keep up): S3, S4, S5 once each.
R=/home/kotaro/thesis_Bunker_rtf/conference/results/eval_035
for c in S3 S4 S5; do [ -e "$R/runs/08OB86_-0205/${c}_r1" ] && continue; echo "$(date -Is) start $c"; bash "$R/run_one.sh" 08OB86_-0205 $c 1; s=$?; echo "$(date -Is) end $c status=$s"; [ "$s" = 2 ] && exit 2; sleep 10; done
date -Is > "$R/stage2b_done.txt"
