#!/usr/bin/env python3
"""Gazeboのカメラ画像を分類し、判定結果を一度送信する。

/pai/camera/imageを購読し、中央領域で赤または青の画素が十分な割合を占めるか確認する。
その平均RGB値をGaussianColorClassifierで分類し、/pai/sort_commandへ配信する。
ai_guided_replay_v2.pyが判定を受信し、青なら待機、赤なら軌道再生を行う。"""
import argparse
import collections
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image
from std_msgs.msg import String
from classifier_core import GaussianColorClassifier


def measure_color(msg, min_fraction=0.06):
    encoding = msg.encoding.lower()
    formats = {
        'rgb8': (3, (0, 1, 2)), 'bgr8': (3, (2, 1, 0)),
        'rgba8': (4, (0, 1, 2)), 'bgra8': (4, (2, 1, 0)),
        '8uc3': (3, (0, 1, 2)), '8uc4': (4, (0, 1, 2))
    }
    if encoding not in formats:
        raise ValueError(f'Unsupported ROS image encoding: {msg.encoding}')
    channels, order = formats[encoding]
    w, h, stride = int(msg.width), int(msg.height), int(msg.step)
    if not w or not h or stride < w * channels or len(msg.data) < h * stride:
        raise ValueError('Truncated / invalid Image data')
    # 背景やロボットアームの影響を抑えるため、縦横とも中央50%の領域を使用する。
    buf = msg.data
    counts = {'red': 0, 'blue': 0}
    sums = {'red': [0, 0, 0], 'blue': [0, 0, 0]}
    total = 0
    for y in range(h // 4, 3*h // 4, 3):
        for x in range(w // 4, 3*w // 4, 3):
            off = y*stride + x*channels
            r, g, b = [int(buf[off+j]) for j in order]
            red = r >= 85 and r >= 1.5 * max(g, b)
            blue = b >= 85 and b >= 1.5 * max(r, g)
            label = 'red' if red else 'blue' if blue else None
            if label:
                counts[label] += 1
                for k, v in enumerate((r, g, b)):
                    sums[label][k] += v
            total += 1
    label = max(counts, key=counts.get)
    other = 'red' if label == 'blue' else 'blue'
    coverage = counts[label] / max(total, 1)
    if coverage < min_fraction or counts[label] < 30:
        raise ValueError(f'Insufficient saturated target: red={counts["red"]}, blue={counts["blue"]}, coverage={coverage:.1%}')
    if counts[other] > counts[label] * 0.4:
        raise ValueError(f'Ambiguous red/blue targets: red={counts["red"]}, blue={counts["blue"]}')
    rgb = tuple(int(s / counts[label]) for s in sums[label])
    return label, rgb, coverage


class GazeboCameraAI(Node):
    def __init__(self, args):
        super().__init__('pai_gazebo_camera_ai')
        self.args = args
        self.model = GaussianColorClassifier()
        self.pub = self.create_publisher(String, '/pai/sort_command', 10)
        self.sub = self.create_subscription(Image, '/pai/camera/image', self.on_image, qos_profile_sensor_data)
        self.last_labels = collections.deque(maxlen=args.stable_frames)
        self.last_error = None
        self.frame_count = 0
        self.completed = False
        self.get_logger().info('Waiting for real Gazebo camera frames: /pai/camera/image')

    def on_image(self, msg):
        if self.completed:
            return
        self.frame_count += 1
        try:
            region_label, rgb, coverage = measure_color(msg, self.args.min_coverage)
            label, score = self.model.predict(rgb)
            if label != region_label:
                raise ValueError(f'Foreground color {region_label} conflicts with model result {label}')
            if score < self.args.min_score:
                raise ValueError(f'Low classifier score {score:.2f}')
        except ValueError as exc:
            if self.frame_count == 1 or self.frame_count % 12 == 0:
                self.get_logger().warning(f'Camera frame rejected: {exc}')
            self.last_error = str(exc)
            self.last_labels.clear()
            return
        self.last_error = None
        self.last_labels.append(label)
        if self.frame_count % 3 == 0:
            self.get_logger().info(f'Camera RGB={rgb}, foreground={coverage:.1%}, AI={label}, score={score:.3f}')
        if len(self.last_labels) < self.args.stable_frames or len(set(self.last_labels)) != 1:
            return
        self.get_logger().info(f'CAMERA-BASED DECISION: {label.upper()} (from Gazebo sensor, not manual RGB)')
        message = String(); message.data = label
        self.completed = True
        for _ in range(6):
            self.pub.publish(message)
            time.sleep(0.15)
        self.get_logger().info(f'Published /pai/sort_command: {label}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stable-frames', type=int, default=3)
    parser.add_argument('--min-coverage', type=float, default=0.06)
    parser.add_argument('--min-score', type=float, default=0.9)
    parser.add_argument('--timeout', type=float, default=30.0)
    args = parser.parse_args()
    if args.stable_frames < 1 or not 0 < args.min_coverage <= 1:
        parser.error('Invalid classification threshold')
    rclpy.init()
    node = GazeboCameraAI(args)
    try:
        deadline = time.monotonic() + args.timeout
        while rclpy.ok() and not node.completed and time.monotonic() < deadline:
            rclpy.spin_once(node, timeout_sec=0.25)
        if not node.completed:
            print('ERROR: No valid Gazebo camera classification; inspect sensor bridge and camera image', flush=True)
            return 2
        return 0
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    raise SystemExit(main())
