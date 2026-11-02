#!/usr/bin/env python3
"""Gazebo上でCRANE+ V2の保存済み計画軌道を再生する（ROS 2 Humble）。

入力は/display_planned_pathから抽出したpick_place_trajectories.jsonである。
ros2_controlへ直接指令を送信し、衝突を考慮した経路再計画は行わない。
Gazeboを記録時の初期状態に戻してから実行する。"""
import argparse
import json
import sys
import time
from pathlib import Path

import rclpy
from action_msgs.msg import GoalStatus
from builtin_interfaces.msg import Duration
from control_msgs.action import FollowJointTrajectory
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectoryPoint


def wait_future(node, future, limit, label):
    rclpy.spin_until_future_complete(node, future, timeout_sec=limit)
    if not future.done():
        raise TimeoutError(f"{label}: no response within {limit:.0f}s")
    if future.exception():
        raise RuntimeError(f"{label}: {future.exception()}")
    return future.result()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="/workspace/pick_place_trajectories.json")
    parser.add_argument("--through", type=int, default=0,
                        help="Replay trajectories 1..N. Default 0 just lists them.")
    args = parser.parse_args()

    records = json.loads(Path(args.file).read_text())
    if not records:
        raise SystemExit("No trajectories in JSON")
    for i, record in enumerate(records, 1):
        print(f"{i:02d}: {', '.join(record['joint_names'])}, "
              f"{len(record['points'])} points, "
              f"{record['points'][-1]['time_ns']/1e9:.2f}s", flush=True)
    if args.through == 0:
        print("No motion sent. Specify --through 13 to replay all trajectories.")
        return
    if not 1 <= args.through <= len(records):
        raise SystemExit(f"--through must be 1..{len(records)}")

    rclpy.init()
    node = Node("pai_recorded_trajectory_player")
    state = [None]
    subscription = node.create_subscription(
        JointState, "/joint_states", lambda message: state.__setitem__(0, message),
        qos_profile_sensor_data)
    arm = ActionClient(node, FollowJointTrajectory,
                       "/crane_plus_arm_controller/follow_joint_trajectory")
    gripper = ActionClient(node, FollowJointTrajectory,
                           "/crane_plus_gripper_controller/follow_joint_trajectory")
    try:
        if not arm.wait_for_server(timeout_sec=8.0):
            raise RuntimeError("Arm FollowJointTrajectory action not available")
        if not gripper.wait_for_server(timeout_sec=8.0):
            raise RuntimeError("Gripper FollowJointTrajectory action not available")
        cutoff = time.monotonic() + 10.0
        while state[0] is None and time.monotonic() < cutoff:
            rclpy.spin_once(node, timeout_sec=0.2)
        if state[0] is None:
            raise RuntimeError("No /joint_states received")

        for i, record in enumerate(records[:args.through], 1):
            names = record["joint_names"]
            planned_start = record["points"][0]["positions"]
            actual = dict(zip(state[0].name, state[0].position))
            missing = [name for name in names if name not in actual]
            if missing:
                raise RuntimeError(f"Segment {i}: missing actual joints {missing}")
            deltas = [abs(actual[name] - ref) for name, ref in zip(names, planned_start)]
            if max(deltas) > 0.12:
                raise RuntimeError(
                    f"Segment {i}: starting joints differ from recording "
                    f"(max difference {max(deltas):.3f} rad). "
                    "Reset Gazebo and stop other robot commands before retrying."
                )

            goal = FollowJointTrajectory.Goal()
            goal.trajectory.joint_names = list(names)
            for point in record["points"]:
                msg = JointTrajectoryPoint()
                msg.positions = list(point["positions"])
                for field in ("velocities", "accelerations"):
                    values = point.get(field, [])
                    if len(values) == len(names):
                        setattr(msg, field, list(values))
                ns = int(point["time_ns"])
                msg.time_from_start = Duration(sec=ns // 1_000_000_000,
                                               nanosec=ns % 1_000_000_000)
                goal.trajectory.points.append(msg)

            client = gripper if len(names) == 1 and names[0] == "crane_plus_joint_hand" else arm
            print(f"Executing {i:02d}/{args.through} ...", flush=True)
            handle = wait_future(node, client.send_goal_async(goal), 10, f"Segment {i} acceptance")
            if not handle.accepted:
                raise RuntimeError(f"Segment {i}: action goal rejected")
            expected_duration = record["points"][-1]["time_ns"] / 1e9
            response = wait_future(node, handle.get_result_async(),
                                   max(30, expected_duration * 5 + 10),
                                   f"Segment {i} execution")
            if (response.status != GoalStatus.STATUS_SUCCEEDED or
                    response.result.error_code != FollowJointTrajectory.Result.SUCCESSFUL):
                raise RuntimeError(
                    f"Segment {i}: status={response.status}, "
                    f"code={response.result.error_code}, "
                    f"message={response.result.error_string!r}")
            # 次の区間の開始姿勢を確認する前に、現在の関節状態を更新する。
            rclpy.spin_once(node, timeout_sec=0.3)
            print(f"Completed {i:02d}", flush=True)
        print("Replay completed successfully.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"ERROR: {exc}")
