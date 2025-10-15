#!/bin/bash
CURRENT_DIR=$(pwd)
cd docker

xhost +local:root  # ← ホスト側で実行

docker run --rm -it \
  --net=host \
  --device=/dev/bus/usb \
  --privileged \
  --runtime nvidia \
  --name ros2-humble-nvidia \
  --user $(id -u):$(id -g) \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $HOME/.Xauthority:/root/.Xauthority:ro \
  -v $HOME/.Xauthority:/home/admin/.Xauthority:ro \
  -v /usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu/tegra:ro \
  -v /dev:/dev \
  -v /run/udev:/run/udev:ro \
  -v /sys:/sys:ro \
  -v $CURRENT_DIR:/root/autonomous \
  -e DISPLAY=$DISPLAY \
  -e XAUTHORITY=/home/admin/.Xauthority \
  --user 0 \
  --device /dev/bus/usb \
  --device /dev/dri \
  --device /dev/video \
  --device /dev/hidraw \
  --group-add $(getent group video  | cut -d: -f3) \
  --group-add $(getent group render | cut -d: -f3) \
  --group-add $(getent group plugdev| cut -d: -f3) \
  ros2-humble-nvidia \
  bash -c "cd /root/autonomous && exec bash"

xhost -local:root  # ← ホスト側で実行

cd ..

