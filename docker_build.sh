#!/bin/bash
#cd docker

#docker build --build-arg UID=$(id -u) --build-arg GID=$(id -g) -t ros2-humble .

#cd ..

set -eEuo pipefail

pause_on_error() {
  local status=$?
  if [[ ${status} -ne 0 ]]; then
    echo
    echo "[ERROR] docker_build.sh failed with exit code ${status}."
    if [[ -t 0 && -t 1 && "${AMARANTHUS_NO_ERROR_PAUSE:-0}" != "1" ]]; then
      read -r -p "Press Enter to close..." _
    fi
  fi
}

trap pause_on_error EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/docker"
cd "${SCRIPT_DIR}"
pwd

die(){ echo "[ERROR] $*" >&2; exit 1; }
need(){ command -v "$1" >/dev/null || die "command not found: $1"; }
has_buildx(){ docker buildx version >/dev/null 2>&1; }

is_jetson() {
  [[ "$(uname -m)" == "aarch64" ]] && {
    [[ -f /etc/nv_tegra_release ]] || \
    grep -qi 'jetson' /proc/device-tree/model 2>/dev/null || \
    dpkg -l 2>/dev/null | grep -q 'nvidia-l4t-core'
  }
}

need docker

# 使う build コマンド（buildx があれば優先）
if has_buildx; then
  BUILD=(docker buildx build)
else
  BUILD=(docker build)
fi

if is_jetson; then
  echo "[INFO] Jetson/JetPack を検出しました。ros-humble-nvidia をビルドします。"
  LRS_VERSION="${LRS_VERSION:-2.56.4}"
  LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION:-v1.2.4}"

  # Jetson 用は「現在のディレクトリ」に Dockerfile がある前提（なければエラー）
  JETSON_CTX="${SCRIPT_DIR}"
  [[ -f "${JETSON_CTX}/Dockerfile.nvidia" ]] || die "Jetson用 Dockerfile が ${JETSON_CTX}/Dockerfile に見つかりません。"

  "${BUILD[@]}" \
    -f "${JETSON_CTX}/Dockerfile.nvidia" \
    --network=host \
    --build-arg BUILD_LRS_VIEWER=1 \
    --build-arg LRS_VERSION="${LRS_VERSION}" \
    --build-arg LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION}" \
    -t ros2-humble-nvidia \
    "${JETSON_CTX}"

else
  echo "[INFO] 通常の Ubuntu 環境と判断しました。ros2-humble をビルドします。"
  INSTALL_CUDA="${INSTALL_CUDA:-1}"
  LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION:-v1.2.4}"

  UBUNTU_CTX="${SCRIPT_DIR}"
  [[ -d "${UBUNTU_CTX}" ]] || die "docker ディレクトリが見つかりません（${UBUNTU_CTX}）"
  [[ -f "${UBUNTU_CTX}/Dockerfile" ]] || die "Dockerfile が ${UBUNTU_CTX}/Dockerfile に見つかりません。"

  "${BUILD[@]}" \
    --network=host \
    --build-arg UID="$(id -u)" \
    --build-arg GID="$(id -g)" \
    --build-arg INSTALL_CUDA="${INSTALL_CUDA}" \
    --build-arg LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION}" \
    -t ros2-humble \
    "${UBUNTU_CTX}"
fi

cd ..
