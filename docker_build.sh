#!/bin/bash
cd docker

docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t ros2-humble .

cd ..
