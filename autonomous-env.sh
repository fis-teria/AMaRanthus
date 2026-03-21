#!/bin/bash
set -e

CURRENT_DIR="$(pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKER_DIR="${SCRIPT_DIR}/docker"

cd "${DOCKER_DIR}"

# X11許可
xhost +local:root

# 環境判定
IS_JETSON=false

# Jetson判定:
# 1) /etc/nv_tegra_release がある
# 2) aarch64 かつ tegra向けライブラリがある
if [[ -f /etc/nv_tegra_release ]]; then
    IS_JETSON=true
elif [[ "$(uname -m)" == "aarch64" && -d /usr/lib/aarch64-linux-gnu/tegra ]]; then
    IS_JETSON=true
fi

echo "[INFO] Current dir: ${CURRENT_DIR}"

COMMON_ARGS=(
  --rm -it
  --net=host
  --privileged
  --name ros2-humble-nvidia
  -v /tmp/.X11-unix:/tmp/.X11-unix
  -v "$HOME/.Xauthority:/root/.Xauthority:ro"
  -v /dev:/dev
  -v /run/udev:/run/udev:ro
  -v /sys:/sys:ro
  -v "${CURRENT_DIR}:/root/autonomous"
  -e DISPLAY="${DISPLAY}"
  -e XAUTHORITY=/root/.Xauthority
  --user 0
  --device /dev/bus/usb
)

# 存在するデバイスだけ追加
[[ -e /dev/dri ]]    && COMMON_ARGS+=(--device /dev/dri)
[[ -e /dev/video0 ]] && COMMON_ARGS+=(--device /dev/video0)
[[ -e /dev/hidraw0 ]] && COMMON_ARGS+=(--device /dev/hidraw0)

# グループが存在する場合のみ追加
VIDEO_GID="$(getent group video 2>/dev/null | cut -d: -f3 || true)"
RENDER_GID="$(getent group render 2>/dev/null | cut -d: -f3 || true)"
PLUGDEV_GID="$(getent group plugdev 2>/dev/null | cut -d: -f3 || true)"

[[ -n "${VIDEO_GID}" ]]  && COMMON_ARGS+=(--group-add "${VIDEO_GID}")
[[ -n "${RENDER_GID}" ]] && COMMON_ARGS+=(--group-add "${RENDER_GID}")
[[ -n "${PLUGDEV_GID}" ]] && COMMON_ARGS+=(--group-add "${PLUGDEV_GID}")

if [[ "${IS_JETSON}" == true ]]; then
    echo "[INFO] Jetson環境を検出しました。Jetson向けオプションで起動します。"

    JETSON_ARGS=(
      --runtime nvidia
      -v /usr/lib/aarch64-linux-gnu/tegra:/usr/lib/aarch64-linux-gnu/tegra:ro
    )

    docker run \
      "${COMMON_ARGS[@]}" \
      "${JETSON_ARGS[@]}" \
      ros2-humble-nvidia \
      bash -c "cd /root/autonomous && exec bash"

else
    echo "[INFO] 通常のUbuntu環境を検出しました。Ubuntu向けオプションで起動します。"

    UBUNTU_ARGS=()

    # NVIDIA Container Toolkit が使えるなら runtime を追加
    if docker info 2>/dev/null | grep -qi "nvidia"; then
        echo "[INFO] NVIDIA runtime を検出しました。GPUオプションを有効化します。"
        UBUNTU_ARGS+=(--gpus all)
    else
        echo "[INFO] NVIDIA runtime は未検出です。GPUオプションなしで起動します。"
    fi

    docker run \
      "${COMMON_ARGS[@]}" \
      "${UBUNTU_ARGS[@]}" \
      ros2-humble \
      bash -c "cd /root/autonomous && exec bash"
fi

xhost -local:root

cd "${SCRIPT_DIR}"