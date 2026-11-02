#!/usr/bin/env bash
# 赤・青の標識を保持し、配置を変えてカメラに映る色を切り替える。
set -eo pipefail
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=1

MODE="${1:-}"
if [[ "$MODE" != blue && "$MODE" != red ]]; then
  echo 'Usage: bash /workspace/pai_record_color.sh blue|red' >&2
  exit 2
fi

if ! ign service -l | grep -q '^/world/default/set_pose$'; then
  echo 'Gazebo /world/default/set_pose is unavailable. Check terminal A.' >&2
  exit 1
fi

ensure_model() {
  local name="$1" sdf="$2"
  if ! ign model -m "$name" --pose 2>/dev/null | grep -q "Name: $name"; then
    echo "Spawning $name"
    ros2 run ros_gz_sim create -world default -file "$sdf" -name "$name"
    sleep 2
  fi
}

set_model_pose() {
  local name="$1" x="$2" y="$3" z="$4" qx="$5" qy="$6" qz="$7" qw="$8"
  local response
  response="$(ign service -s /world/default/set_pose \
    --reqtype ignition.msgs.Pose \
    --reptype ignition.msgs.Boolean \
    --timeout 5000 \
    --req "name: \"$name\" position: {x: $x, y: $y, z: $z} orientation: {x: $qx, y: $qy, z: $qz, w: $qw}")"
  echo "$name: $response"
  if ! grep -q 'data: true' <<< "$response"; then
    echo "Failed to position $name" >&2
    exit 1
  fi
}

ROOT=/workspace/PAI_gazebo_camera/models
ensure_model pai_overhead_camera "$ROOT/overhead_camera.sdf"
ensure_model pai_blue_overlay "$ROOT/blue_marker.sdf"
ensure_model pai_red_overlay "$ROOT/red_marker.sdf"

# カメラの+X方向の光軸を下向きに回転する。
set_model_pose pai_overhead_camera 0.38 -0.30 1.85 0 0.70710678 0 0.70710678

if [[ "$MODE" == blue ]]; then
  set_model_pose pai_red_overlay 3 3 1.35 0 0 0 1
  set_model_pose pai_blue_overlay 0.38 -0.30 1.35 0 0 0 1
else
  set_model_pose pai_blue_overlay 3 3 1.35 0 0 0 1
  set_model_pose pai_red_overlay 0.38 -0.30 1.35 0 0 0 1
fi

if ! ign topic -l | grep -qF '/pai/camera/image'; then
  echo 'Warning: Gazebo /pai/camera/image topic not found. Check Sensors plugin.' >&2
  exit 1
fi

echo "Gazebo marker set to: ${MODE^^}"
