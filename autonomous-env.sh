#!/bin/bash
CURRENT_DIR=$(pwd)
cd docker

xhost +local:root  # ← ホスト側で実行

docker run --rm -it \
  --net=host \
  --device=/dev/bus/usb \
  --privileged \
  --name ros2-humble \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /dev/bus/*:/dev/bus/* \
  -v $CURRENT_DIR:/root/autonomous \
  --user 0 \
  ros2-humble \
  bash -c "cd /root/autonomous && exec bash"

xhost -local:root  # ← ホスト側で実行

cd ..

