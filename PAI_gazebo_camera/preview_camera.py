#!/usr/bin/env python3
"""Gazeboカメラから最初に受信したROS画像をPPMで保存する。PillowがあればPNGも保存する。"""
import argparse
from pathlib import Path
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


def rgb_bytes(msg):
    enc = msg.encoding.lower()
    formats = {'rgb8': (3,(0,1,2)), 'bgr8':(3,(2,1,0)),
               'rgba8':(4,(0,1,2)), 'bgra8':(4,(2,1,0)),
               '8uc3':(3,(0,1,2)), '8uc4':(4,(0,1,2))}
    if enc not in formats: raise ValueError(f'Unsupported encoding {enc}')
    channels, order = formats[enc]
    w,h,step = int(msg.width),int(msg.height),int(msg.step)
    if step < w*channels or len(msg.data) < h*step: raise ValueError('Invalid camera image')
    data = bytearray(w*h*3); k = 0
    for y in range(h):
        for x in range(w):
            off = y*step+x*channels
            for j in order:
                data[k] = msg.data[off+j]; k+=1
    return w,h,bytes(data)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/workspace/camera_snapshot.ppm')
    parser.add_argument('--timeout', type=float, default=15)
    args=parser.parse_args()
    rclpy.init()
    node=Node('pai_camera_snapshot')
    capture=[None]
    sub=node.create_subscription(Image,'/pai/camera/image',
                                 lambda msg: capture.__setitem__(0,msg),qos_profile_sensor_data)
    try:
        limit=time.monotonic()+args.timeout
        while rclpy.ok() and capture[0] is None and time.monotonic()<limit:
            rclpy.spin_once(node,timeout_sec=0.25)
        if capture[0] is None:
            raise RuntimeError('No ROS camera frames; check Gazebo Sensors plugin, camera model, and bridge')
        w,h,data=rgb_bytes(capture[0]); p=Path(args.output)
        p.write_bytes(f'P6\n{w} {h}\n255\n'.encode()+data)
        print(f'Wrote actual Gazebo camera frame: {p} [{w}x{h}] encoding={capture[0].encoding}')
        try:
            from PIL import Image as PilImage
            png=p.with_suffix('.png'); PilImage.frombytes('RGB',(w,h),data).save(png)
            print('PNG:',png)
        except ImportError:
            print('PNG optional: apt install python3-pil; PPM already saved')
    finally:
        node.destroy_node(); rclpy.shutdown()

if __name__=='__main__':
    main()
