#!/usr/bin/env bash
# R1 and R2 alternate, five runs each, so drift of the machine falls on both. A failed run never stops the rest.
R=/home/kotaro/thesis_Bunker_rtf/conference/results/rtf_check/divergence
date -Is > "$R/stage3_started.txt"
for i in 01 02 03 04 05; do
  for c in R1 R2; do
    echo "$(date -Is) start ${c}_$i"
    bash "$R/run_one.sh" "$c" "${c}_$i"
    echo "$(date -Is) end ${c}_$i status=$?"
    sleep 10
  done
done
date -Is > "$R/stage3_done.txt"
