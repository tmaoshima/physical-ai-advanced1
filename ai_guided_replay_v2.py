#!/usr/bin/env python3
"""ROS 2の分類結果に応じて、青なら待機、赤なら箱の搬送を行う。

camera_ai.pyが配信する/pai/sort_command（std_msgs/String）を受信する。
画像の取得・分類はカメラ側が担当し、このノードは動作を選択する。

赤判定では、搬送を確認済みの13区間の計画軌道を再生する。
ros2_controlへ直接指令を送るため、MoveItによる実行時の衝突計画は行わない。
Gazeboを元の初期状態に戻し、他の動作ノードを停止してから使用する。"""

import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class DecisionDemo(Node):
    def __init__(self, event_file):
        super().__init__('pai_ai_guided_replay')
        self.queue = deque()
        self.last_decision = None
        self.event_file = event_file
        self.status_pub = self.create_publisher(String, '/pai/sort_status', 10)
        self.subscription = self.create_subscription(
            String, '/pai/sort_command', self.on_decision, 10
        )

    def announce(self, event, description):
        text = f'{event} | {description}'
        self.get_logger().info(text)
        print('\n' + '=' * 54 + '\n' + text + '\n' + '=' * 54, flush=True)
        message = String()
        message.data = event
        self.status_pub.publish(message)
        if self.event_file is not None:
            entry = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                     'event': event, 'description': description}
            try:
                with self.event_file.open('a', encoding='utf-8') as stream:
                    stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
            except OSError as exc:
                self.get_logger().warning(f'Cannot write optional event log: {exc}')
                self.event_file = None

    def on_decision(self, message):
        color = message.data.strip().lower()
        if color not in ('red', 'blue'):
            self.get_logger().warning(f'Unsupported classification: {color!r}')
            return
        # カメラ側は同じ判定を繰り返し送信するため、連続する重複を除外する。
        if color == self.last_decision:
            return
        self.last_decision = color
        self.queue.append(color)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--red-file', default='/workspace/pick_place_trajectories.json')
    parser.add_argument('--replay', default='/workspace/replay_pick_place.py')
    parser.add_argument('--events-file', default='/workspace/pai_demo_events.jsonl')
    parser.add_argument('--timeout', type=float, default=300.0,
                        help='Seconds to wait for a red decision (default 300)')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    red_file = Path(args.red_file)
    replay = Path(args.replay)
    if not red_file.is_file() or not replay.is_file():
        print('Missing verified trajectory JSON or replay_pick_place.py', file=sys.stderr)
        return 2
    try:
        trajectories = json.loads(red_file.read_text(encoding='utf-8'))
        if len(trajectories) != 13:
            raise ValueError('Expected exactly 13 validated trajectories')
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f'Trajectory preflight check failed: {exc}', file=sys.stderr)
        return 2

    rclpy.init()
    node = DecisionDemo(Path(args.events_file) if args.events_file else None)
    try:
        node.announce('waiting_for_ai', 'BLUE = HOLD, RED = PICK_AND_PLACE')
        deadline = time.monotonic() + args.timeout
        while rclpy.ok() and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)
            while node.queue:
                decision = node.queue.popleft()
                if decision == 'blue':
                    node.announce('classified_blue', 'AI classified BLUE')
                    node.announce('held_blue_no_motion',
                                  'HOLD: no trajectory sent to robot')
                    continue  # 待受を継続し、同じ実行中に赤判定も処理する。

                node.announce('classified_red', 'AI classified RED')
                node.announce('executing_red',
                              'PICK_AND_PLACE: sending 13 validated trajectories')
                if args.dry_run:
                    node.announce('dry_run_red', 'No motion sent')
                    return 0
                result = subprocess.run(
                    [sys.executable, str(replay), '--file', str(red_file), '--through', '13'],
                    check=False,
                )
                if result.returncode != 0:
                    node.announce('failed_red_motion',
                                  f'Replay returned exit code {result.returncode}')
                    return result.returncode or 1
                node.announce('completed_red_motion',
                              'All 13 trajectory actions completed')
                return 0
        node.announce('timeout_no_red', 'No RED decision received within time limit')
        return 2
    except KeyboardInterrupt:
        node.announce('interrupted', 'Demo was stopped by operator')
        return 130
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
