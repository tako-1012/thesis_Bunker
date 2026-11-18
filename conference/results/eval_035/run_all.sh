#!/usr/bin/env bash
# Stage 1: 5 beaches x P1 x 3 (beach by beach). Stage 2: 08OB86_-0205 S1, S2, then STOP for the S2 compute check
# (S3-S5 are started separately by run_stage2b.sh only if S2 keeps up). Existing run folders are skipped.
R=/home/kotaro/thesis_Bunker_rtf/conference/results/eval_035
[ -e "$R/stage1_started.txt" ] || date -Is > "$R/stage1_started.txt"
run() { [ -e "$R/runs/$1/$2_r$3" ] && return 0; echo "$(date -Is) start $1 $2 r$3"; bash "$R/run_one.sh" "$1" "$2" "$3"; s=$?
        echo "$(date -Is) end $1 $2 r$3 status=$s"; [ "$s" = 2 ] && { echo "precondition failed; stopping"; exit 2; }; sleep 10; }
for p in 08OB87_-0706 08OB88_-1417 08OB88_-0167 08OB89_-0347 08OB89_-0847; do for k in 1 2 3; do run $p P1 $k; done; done
date -Is > "$R/stage1_done.txt"
run 08OB86_-0205 S1 1
run 08OB86_-0205 S2 1
date -Is > "$R/stage2a_done.txt"
