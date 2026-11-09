#!/usr/bin/env bash
# B0: depth2 first (the camera checks), then lidar_real. One at a time; a failure never stops the second.
R=/home/kotaro/thesis_Bunker_rtf/conference/results/real_sensors/b0
date -Is > "$R/b0_started.txt"
for s in lidar_real+depth2 lidar_real; do
  n=$( [ "$s" = lidar_real ] && echo lidar_real || echo lidar_real_depth2 )
  echo "$(date -Is) start $n"; bash "$R/run_b0.sh" "$s" "$n"; echo "$(date -Is) end $n status=$?"; sleep 10
done
date -Is > "$R/b0_done.txt"
