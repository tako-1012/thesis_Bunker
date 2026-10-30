FROM osrf/ros:jazzy-desktop-full
RUN rm -f /etc/apt/sources.list.d/ros2*.list /etc/apt/sources.list.d/ros2.sources 2>/dev/null; ls /etc/apt/sources.list.d/; apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3-pandas && rm -rf /var/lib/apt/lists/*
