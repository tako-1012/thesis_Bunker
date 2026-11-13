#!/bin/bash
cd ~/thesis_Bunker_rtf/conference
L=$PWD/results/eval_ground_endpoint/tests_log
export MPLBACKEND=Agg
: > $L/summary.txt
for f in tests/test_*.py; do
  n=$(basename $f .py)
  ~/.venvs/thesis-python/bin/python -m tests.$n > $L/$n.log 2>&1
  echo "tests.$n $?" >> $L/summary.txt
done
date > $L/finished.txt
