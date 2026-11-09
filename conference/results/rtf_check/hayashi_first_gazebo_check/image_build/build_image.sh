#!/usr/bin/env bash
# Build thesis/jazzy-gz:1 with the documented command; keep log and exit code.
cd /home/kotaro/thesis_Bunker
d=conference/results/hayashi_first_gazebo_check/image_build
{ date -Is; git rev-parse HEAD; git status --short | head -5; docker --version; sha256sum conference/ros2_jazzy/gz_checks/Dockerfile; } > "$d/build_conditions.txt"
timeout 3600 docker build -t thesis/jazzy-gz:1 -f conference/ros2_jazzy/gz_checks/Dockerfile conference/ros2_jazzy/gz_checks > "$d/build.log" 2>&1
code=$?
echo "$code" > "$d/exit_code.txt"
{ date -Is; docker image inspect thesis/jazzy-gz:1 --format "id={{.Id}} size={{.Size}} created={{.Created}}" 2>&1; docker image inspect osrf/ros:jazzy-desktop-full --format "base_digests={{.RepoDigests}}" 2>&1; } >> "$d/build_conditions.txt"
