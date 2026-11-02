# デモの実行・録画手順

青の標識で待機を確認し、その後赤に切り替えて箱を搬送する。以下はすべてnoVNC上のUbuntu / Terminatorで実行。

## ターミナルの役割と共通設定

| ターミナル | 役割 | 実行中の扱い |
|---|---|---|
| A | カメラ対応のGazebo・MoveIt 2 | 起動したまま |
| B | AI判定を受けてロボットを制御 | 赤の搬送完了まで待受 |
| C | Gazebo画像をROS 2へブリッジ | 起動したまま |
| D | 標識の切り替え・画像確認・分類 | 各手順で操作 |

A〜Dの各ターミナルで最初に実行。

```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=1
```

## 1. A：初期状態のGazeboを起動

以前のGazebo起動プロセスはCtrl+Cで終了する。公式`pick_and_place`やテレオペなど、他のロボット制御プロセスも終了しておく。

```bash
unset IGN_GAZEBO_SERVER_CONFIG_PATH
ros2 launch /workspace/PAI_gazebo_camera/crane_plus_camera.launch.py
```

この起動方法はSensors設定を含む`table_camera.sdf`を使用する。起動後、Dで確認。

```bash
ros2 control list_controllers
ros2 topic echo /joint_states --once
```

`joint_state_broadcaster`、`crane_plus_arm_controller`、`crane_plus_gripper_controller`が`active`になり、関節状態が届くことを確認。

## 2. C：画像ブリッジを起動

```bash
bash /workspace/PAI_gazebo_camera/scripts/bridge_camera.sh
```

## 3. D：青の標識とカメラを準備

```bash
bash /workspace/pai_record_color.sh blue
python3 /workspace/PAI_gazebo_camera/preview_camera.py
xdg-open /workspace/camera_snapshot.png
```

画像の中央付近に青い標識が見えることを確認。PNGはPillowが利用できる場合に保存。PNGが生成されない場合は`camera_snapshot.ppm`を開く。

必要に応じて、共通設定を読み込んだ追加ターミナルで画像ビューアを起動し、`/pai/camera/image`を選択。

```bash
ros2 run rqt_image_view rqt_image_view
```

## 4. B：ロボット制御を待受状態にする

```bash
python3 /workspace/ai_guided_replay_v2.py --timeout 900
```

`waiting_for_ai | BLUE = HOLD, RED = PICK_AND_PLACE`が表示されることを確認する。赤判定を待つ制限時間は900秒である。

## 5. D：青を分類

```bash
python3 /workspace/PAI_gazebo_camera/camera_ai.py --timeout 12
```

Dに`CAMERA-BASED DECISION: BLUE`、Bに`classified_blue`と`held_blue_no_motion`が表示され、ロボットは待機する。

## 6. D：赤へ切り替えて分類

```bash
bash /workspace/pai_record_color.sh red
python3 /workspace/PAI_gazebo_camera/preview_camera.py
xdg-open /workspace/camera_snapshot.png
```

保存画像が赤になったことを確認してから分類。

```bash
python3 /workspace/PAI_gazebo_camera/camera_ai.py --timeout 12
```

Dに`CAMERA-BASED DECISION: RED`、Bに`classified_red`、`executing_red`、成功時に`completed_red_motion`が表示される。Gazebo画面で箱が把持・搬送・配置されることも確認する。完了イベントは軌道Actionの完了を表し、箱の配置の成否は画面で確認する。

## 録画と再実行

録画では「青い画像 → BLUE判定 → 待機 → 赤い画像 → RED判定 → 箱搬送 → 完了ログ」の順。色標識と搬送する箱が別物であること、保存済み軌道を使用していることを説明。

イベントは`/workspace/pai_demo_events.jsonl`へ追記。赤の搬送後はBが終了する。再実行するときはAを終了・再起動して箱とアームを初期状態に戻し、手順2以降を繰り返す。Cが動作中なら継続して使用。
