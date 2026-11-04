#!/usr/bin/env bash
set -euo pipefail
runtime_root=/tmp/task020-oci/rootfs
conference_source=/workspace/thesis-020/conference
output_path=/workspace/thesis-020/conference/results/footprint_steep/gazebo_inflate
mkdir -p "$output_path"
python3 - <<'TASK019_PROVENANCE_4A3'
import json
from pathlib import Path
source=json.loads(Path('/tmp/task020-oci/source.json').read_text())
source['runtime']='temporary root filesystem in an unprivileged user/mount namespace; default image flattened after SHA-256 verification'
Path('/workspace/thesis-020/conference/results/footprint_steep/gazebo_inflate/runtime_source.json').write_text(json.dumps(source,indent=2)+'\n')
TASK019_PROVENANCE_4A3
unshare --user --map-root-user --mount bash -s -- "$runtime_root" "$conference_source" "$output_path" <<'TASK019_NAMESPACE_BODY_5E2'
set -euo pipefail
runtime_root="$1"
conference_source="$2"
output_path="$3"
mount --make-rprivate /
mkdir -p "$runtime_root/conference" "$runtime_root/output" "$runtime_root/proc" "$runtime_root/dev" "$runtime_root/sys"
mount --bind "$conference_source" "$runtime_root/conference"
mount -o remount,bind,ro "$runtime_root/conference"
mount --bind "$output_path" "$runtime_root/output"
mount --rbind /dev "$runtime_root/dev"
mount --bind /proc "$runtime_root/proc"
mount --rbind /sys "$runtime_root/sys"
mount -o remount,bind,ro "$runtime_root/sys"
mount --bind /etc/hosts "$runtime_root/etc/hosts"
mount -o remount,bind,ro "$runtime_root/etc/hosts"
mount --bind /etc/resolv.conf "$runtime_root/etc/resolv.conf"
mount -o remount,bind,ro "$runtime_root/etc/resolv.conf"
export ROS_DOMAIN_ID=49
export THESIS_ROS_IMAGE="osrf/ros:jazzy-desktop-full@sha256:ae7ad3ac243da1dfd8bd402a2fa08e149ffbf7a385013bd8ef798d0800accdc8"
export ROS_LOG_DIR=/tmp/thesis-ros-log PYTHONPATH=/conference MPLCONFIGDIR=/tmp/thesis-mpl XDG_CACHE_HOME=/tmp/thesis-cache
export OPENBLAS_NUM_THREADS=1 THESIS_CONFERENCE_DIR=/conference QT_QPA_PLATFORM=offscreen LIBGL_ALWAYS_SOFTWARE=1
chroot "$runtime_root" /bin/bash -s <<'TASK019_CHROOT_BODY_8D4'
set -eo pipefail
# These changes only affect the disposable extracted image, as in gz_checks/Dockerfile.
rm -f /etc/apt/sources.list.d/ros2*.list /etc/apt/sources.list.d/ros2.sources
apt-get -o APT::Sandbox::User=root update
DEBIAN_FRONTEND=noninteractive apt-get -o APT::Sandbox::User=root install -y --no-install-recommends python3-pandas python3-numpy python3-scipy python3-matplotlib
source /opt/ros/jazzy/setup.bash
python3 -c 'import sys,numpy,scipy,matplotlib,pandas; print(sys.version); print("numpy",numpy.__version__,"scipy",scipy.__version__,"matplotlib",matplotlib.__version__,"pandas",pandas.__version__)'
gz sim --versions
cd /tmp
colcon --log-base /tmp/thesis-colcon-log build --base-paths /conference/ros2_jazzy/src --build-base /tmp/thesis-build --install-base /tmp/thesis-install
source /tmp/thesis-install/setup.bash
python3 /conference/ros2_jazzy/gz_checks/compare_checks.py --output /output --planners "TA*-S+inflate"
TASK019_CHROOT_BODY_8D4
TASK019_NAMESPACE_BODY_5E2
