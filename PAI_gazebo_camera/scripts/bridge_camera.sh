#!/usr/bin/env bash
set -euo pipefail
set +u
source /opt/ros/humble/setup.bash
set -u
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=1
# Fortressの画像ブリッジではignition.msgs.Image型を使用する。
exec ros2 run ros_gz_bridge parameter_bridge \
  '/pai/camera/image@sensor_msgs/msg/Image[ignition.msgs.Image'
