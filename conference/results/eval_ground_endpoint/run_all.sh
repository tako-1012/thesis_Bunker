#!/usr/bin/env bash
# 5 beaches x (C0, C1, C2) x 3 rounds, beach by beach; existing run folders are skipped (resume-safe).
R=/home/kotaro/thesis_Bunker_rtf/conference/results/eval_ground_endpoint
[ -e "$R/all_started.txt" ] || date -Is > "$R/all_started.txt"
for p in 08OB87_-0706 08OB88_-1417 08OB88_-0167 08OB89_-0347 08OB89_-0847; do
  for k in 1 2 3; do
    for c in C0 C1 C2; do
      [ -e "$R/runs/$p/${c}_r$k" ] && continue
      echo "$(date -Is) start $p $c r$k"
      bash "$R/run_one.sh" "$p" "$c" "$k"; s=$?
      echo "$(date -Is) end $p $c r$k status=$s"
      [ "$s" = 2 ] && { echo "precondition failed; stopping"; exit 2; }
      sleep 10
    done
  done
done
date -Is > "$R/all_done.txt"
