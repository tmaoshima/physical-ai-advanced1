# 環境構築

- ローカル環境：M1 Mac
- コンテナ環境：Colima

既存のM1 Macでの作業記録を整理した手順である。Mac側でコンテナを用意し、ROS 2操作はnoVNC上のUbuntu / Terminatorで行う。

## 1. Colimaの確認（Mac）

```bash
colima status
colima ssh -- ls /proc/sys/fs/binfmt_misc/
```

既存の記録ではAMD64コンテナ用にRosettaを有効化。Colimaを使用し、`rosetta`が表示されない場合は、稼働中のコンテナが停止することを確認したうえで再起動。

```bash
colima stop
colima start --vm-type vz --vz-rosetta --cpus 4 --memory 4
```

## 2. コンテナの作成（Mac）

リポジトリのルートで実行する。`$PWD`をコンテナの`/workspace`にマウントする。

```bash
docker pull --platform linux/amd64 airobotbook/ros2-desktop-ai-robot-book-humble:latest
docker run -d \
  --platform linux/amd64 \
  --name ai_robot_book \
  --shm-size=1g \
  -p 127.0.0.1:6080:80 \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  -v "$PWD:/workspace" \
  airobotbook/ros2-desktop-ai-robot-book-humble:latest
```

既に`ai_robot_book`がある場合は`docker start ai_robot_book`で起動。

## 3. Ubuntu画面とROS 2の確認

Macのブラウザで[noVNC](http://localhost:6080/)を開き、UbuntuのTerminatorを起動。

```bash
source /opt/ros/humble/setup.bash
export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
export ROS_LOCALHOST_ONLY=1
echo "$ROS_DISTRO"
ros2 pkg list | grep crane_plus
```

`humble`と`crane_plus_gazebo`などの関連パッケージが表示されることを確認。
