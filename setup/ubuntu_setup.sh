#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_APT_CODENAME="${ROS_APT_CODENAME:-jammy}"
LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION:-v1.2.4}"
LIBTORCH_VERSION="${LIBTORCH_VERSION:-2.4.1}"
LIBTORCH_VARIANT="${LIBTORCH_VARIANT:-cu121}"
LIBTORCH_INSTALL_DIR="${LIBTORCH_INSTALL_DIR:-/opt/libtorch}"
ACADOS_VERSION="${ACADOS_VERSION:-v0.5.3}"
ACADOS_TERA_RENDERER_VERSION="${ACADOS_TERA_RENDERER_VERSION:-v0.2.0}"
CUDA_VERSION="${CUDA_VERSION:-12.8}"
INSTALL_CUDA="${INSTALL_CUDA:-0}"
INSTALL_NVIDIA_CONTAINER_TOOLKIT="${INSTALL_NVIDIA_CONTAINER_TOOLKIT:-0}"
INSTALL_DOCKER="${INSTALL_DOCKER:-0}"
INSTALL_NVIDIA_SMI="${INSTALL_NVIDIA_SMI:-0}"
INSTALL_NVIDIA_DRIVER="${INSTALL_NVIDIA_DRIVER:-0}"
INSTALL_IBUS_MOZC="${INSTALL_IBUS_MOZC:-1}"
INSTALL_UV="${INSTALL_UV:-1}"
INSTALL_YOLO_CUDA_VENV="${INSTALL_YOLO_CUDA_VENV:-0}"
SKIP_LIBREALSENSE="${SKIP_LIBREALSENSE:-0}"
SKIP_LIVOX_SDK2="${SKIP_LIVOX_SDK2:-0}"
SKIP_LIBTORCH="${SKIP_LIBTORCH:-0}"
SKIP_ACADOS="${SKIP_ACADOS:-0}"
YOLO_CUDA_TORCH_VERSION="${YOLO_CUDA_TORCH_VERSION:-2.11.0+cu128}"
YOLO_CUDA_TORCHVISION_VERSION="${YOLO_CUDA_TORCHVISION_VERSION:-0.26.0+cu128}"
YOLO_CUDA_TORCH_INDEX_URL="${YOLO_CUDA_TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"
YOLO_ULTRALYTICS_VERSION="${YOLO_ULTRALYTICS_VERSION:-8.4.6}"

usage() {
  cat <<'EOF'
Usage: ./setup/ubuntu_setup.sh [options]

Reproduces the Docker development environment on an Ubuntu host as closely as possible.

Options:
  --with-cuda                       Install NVIDIA CUDA Toolkit packages.
  --with-nvidia-smi                Install an available nvidia-utils package.
  --with-nvidia-driver            Install NVIDIA driver kernel modules for current kernel.
  --with-nvidia-container-toolkit  Install NVIDIA Container Toolkit for Docker GPU passthrough.
  --install-docker                 Install Docker Engine using the official convenience script.
  --skip-ibus-mozc                 Skip ibus / mozc installation and shell setup.
  --skip-uv                        Skip uv installation.
  --with-yolo-cuda-venv            Install CUDA-enabled Python deps for yolo_ros under Data/venvs.
                                   Also installs the lightweight LEAD inference deps used by e2e_transfuser.
  --libtorch-variant <cpu|cu118|cu121>
                                   Select the libtorch package variant to install. Default: cu121.
  --libtorch-install-dir <path>    Install libtorch into this directory. Default: /opt/libtorch.
  --skip-libtorch                  Skip libtorch installation.
  --skip-acados                    Skip acados source build.
  --skip-librealsense              Skip librealsense source build.
  --skip-livox-sdk2                Skip Livox-SDK2 source build.
  -h, --help                       Show this help.

Environment variables:
  ROS_DISTRO, ROS_APT_CODENAME, LIBREALSENSE_VERSION, LIVOX_SDK2_VERSION,
  LIBTORCH_VERSION, LIBTORCH_VARIANT, LIBTORCH_INSTALL_DIR,
  ACADOS_VERSION, ACADOS_TERA_RENDERER_VERSION,
  CUDA_VERSION,
  INSTALL_CUDA, INSTALL_NVIDIA_CONTAINER_TOOLKIT,
  INSTALL_DOCKER, INSTALL_NVIDIA_SMI, INSTALL_NVIDIA_DRIVER, INSTALL_IBUS_MOZC, INSTALL_UV,
  INSTALL_YOLO_CUDA_VENV,
  SKIP_LIBREALSENSE, SKIP_LIVOX_SDK2, SKIP_LIBTORCH, SKIP_ACADOS

Examples:
  ./setup/ubuntu_setup.sh
  ./setup/ubuntu_setup.sh --with-cuda --libtorch-variant cu121
  ./setup/ubuntu_setup.sh --install-docker --with-nvidia-container-toolkit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-cuda)
      INSTALL_CUDA=1
      ;;
    --with-nvidia-smi)
      INSTALL_NVIDIA_SMI=1
      ;;
    --with-nvidia-driver)
      INSTALL_NVIDIA_DRIVER=1
      ;;
    --with-nvidia-container-toolkit)
      INSTALL_NVIDIA_CONTAINER_TOOLKIT=1
      ;;
    --install-docker)
      INSTALL_DOCKER=1
      ;;
    --skip-ibus-mozc)
      INSTALL_IBUS_MOZC=0
      ;;
    --skip-uv)
      INSTALL_UV=0
      ;;
    --with-yolo-cuda-venv)
      INSTALL_YOLO_CUDA_VENV=1
      ;;
    --libtorch-variant)
      shift
      LIBTORCH_VARIANT="${1:-}"
      ;;
    --libtorch-install-dir)
      shift
      LIBTORCH_INSTALL_DIR="${1:-}"
      ;;
    --skip-libtorch)
      SKIP_LIBTORCH=1
      ;;
    --skip-acados)
      SKIP_ACADOS=1
      ;;
    --skip-librealsense)
      SKIP_LIBREALSENSE=1
      ;;
    --skip-livox-sdk2)
      SKIP_LIVOX_SDK2=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

if [[ "${EUID}" -eq 0 && -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
  TARGET_USER="${SUDO_USER}"
else
  TARGET_USER="${USER}"
fi

TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"

log() {
  echo "[INFO] $*"
}

warn() {
  echo "[WARN] $*" >&2
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "[ERROR] Required command not found: $1" >&2
    exit 1
  fi
}

apt_install() {
  ${SUDO} apt-get install -y --no-install-recommends "$@"
}

run_as_target_user() {
  if [[ "${EUID}" -eq 0 && "${TARGET_USER}" != "root" ]]; then
    sudo -u "${TARGET_USER}" "$@"
  else
    "$@"
  fi
}

sync_submodules() {
  if [[ ! -f "${REPO_ROOT}/.gitmodules" ]]; then
    return
  fi

  log "Initializing and updating git submodules"
  git -C "${REPO_ROOT}" submodule update --init --recursive
}

detect_ubuntu() {
  if [[ ! -f /etc/os-release ]]; then
    echo "[ERROR] /etc/os-release not found. This script only supports Ubuntu." >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source /etc/os-release

  if [[ "${ID:-}" != "ubuntu" ]]; then
    echo "[ERROR] Unsupported OS: ${ID:-unknown}. This script targets Ubuntu." >&2
    exit 1
  fi

  if [[ "${VERSION_CODENAME:-}" != "${ROS_APT_CODENAME}" ]]; then
    warn "Detected Ubuntu ${VERSION_CODENAME:-unknown}, but ROS ${ROS_DISTRO} binary packages target ${ROS_APT_CODENAME}."
    warn "The setup may still work partially, but Ubuntu 22.04 (${ROS_APT_CODENAME}) is the intended target."
  fi
}

install_base_packages() {
  log "Installing base development packages"
  ${SUDO} apt-get update
  apt_install \
    sudo \
    bash-completion \
    build-essential \
    cmake \
    git \
    curl \
    wget \
    gnupg2 \
    lsb-release \
    ca-certificates \
    software-properties-common \
    pkg-config \
    nano \
    vim \
    less \
    unzip \
    zip \
    iproute2 \
    iputils-ping \
    net-tools \
    dnsutils \
    traceroute \
    tcpdump \
    nmap \
    arp-scan \
    ethtool \
    usbutils \
    pciutils \
    udev \
    x11-apps \
    mesa-utils \
    python3-pip \
    python3-dev \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-rosdep \
    python3-venv \
    python3-vcstool \
    dbus-x11 \
    ibus \
    ibus-mozc \
    im-config \
    libusb-1.0-0-dev \
    libgtk-3-dev \
    libglfw3-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libssl-dev \
    libudev-dev \
    libapr1-dev \
    libx11-dev \
    libxi-dev \
    libxt-dev \
    libcgal-dev \
    libcpprest-dev \
    libcrypto++-dev \
    libeigen3-dev \
    liblttng-ust-dev \
    libnl-genl-3-dev \
    libpcl-dev \
    libpng++-dev \
    libpugixml-dev \
    librange-v3-dev \
    python3-flask \
    python3-jsonschema \
    python3-pandas \
    python3-torch \
    chrony \
    sysstat
}

install_repository_prerequisites() {
  log "Installing apt repository prerequisites"
  fix_docker_apt_signed_by_conflict
  ${SUDO} apt-get update
  apt_install \
    ca-certificates \
    curl \
    gnupg2 \
    lsb-release \
    software-properties-common
}

fix_docker_apt_signed_by_conflict() {
  local docker_list="/etc/apt/sources.list.d/docker.list"

  if [[ ! -f "${docker_list}" ]]; then
    return
  fi

  if ! grep -Fq "download.docker.com/linux/ubuntu" "${docker_list}"; then
    return
  fi

  if ! grep -Fq "docker.asc" "${docker_list}" || ! grep -Fq "docker.gpg" "${docker_list}"; then
    return
  fi

  warn "Docker apt repository has conflicting Signed-By entries; keeping docker.asc and backing up ${docker_list}"
  ${SUDO} cp "${docker_list}" "${docker_list}.bak-$(date +%Y%m%d%H%M%S)"
  awk '
    /download\.docker\.com\/linux\/ubuntu/ && /docker\.gpg/ { next }
    { print }
  ' "${docker_list}" | ${SUDO} tee "${docker_list}" >/dev/null
}

configure_ros2_repository() {
  if [[ -f /etc/apt/sources.list.d/ros2.list ]]; then
    log "ROS 2 apt repository already configured"
    return
  fi

  log "Configuring ROS 2 apt repository"
  ${SUDO} curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
    -o /usr/share/keyrings/ros-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu ${ROS_APT_CODENAME} main" \
    | ${SUDO} tee /etc/apt/sources.list.d/ros2.list >/dev/null
}

install_ros_packages() {
  log "Installing ROS 2 ${ROS_DISTRO} packages"
  ${SUDO} apt-get update
  apt_install \
    "ros-${ROS_DISTRO}-desktop" \
    "ros-${ROS_DISTRO}-cv-bridge" \
    "ros-${ROS_DISTRO}-gazebo-ros-pkgs" \
    "ros-${ROS_DISTRO}-laser-geometry" \
    "ros-${ROS_DISTRO}-message-filters" \
    "ros-${ROS_DISTRO}-pcl-conversions" \
    "ros-${ROS_DISTRO}-pcl-ros" \
    "ros-${ROS_DISTRO}-rosbag2" \
    "ros-${ROS_DISTRO}-std-srvs" \
    "ros-${ROS_DISTRO}-tf2-geometry-msgs" \
    "ros-${ROS_DISTRO}-tf2-sensor-msgs" \
    "ros-${ROS_DISTRO}-tf2-msgs" \
    "ros-${ROS_DISTRO}-teleop-twist-keyboard" \
    "ros-${ROS_DISTRO}-diagnostic-updater" \
    "ros-${ROS_DISTRO}-diagnostic-aggregator" \
    "ros-${ROS_DISTRO}-robot-localization" \
    "ros-${ROS_DISTRO}-imu-filter-madgwick" \
    "ros-${ROS_DISTRO}-ament-clang-format" \
    "ros-${ROS_DISTRO}-aruco" \
    "ros-${ROS_DISTRO}-can-msgs" \
    "ros-${ROS_DISTRO}-generate-parameter-library" \
    "ros-${ROS_DISTRO}-geodesy" \
    "ros-${ROS_DISTRO}-geographic-info" \
    "ros-${ROS_DISTRO}-geometric-shapes" \
    "ros-${ROS_DISTRO}-grid-map-costmap-2d" \
    "ros-${ROS_DISTRO}-grid-map-pcl" \
    "ros-${ROS_DISTRO}-grid-map-rviz-plugin" \
    "ros-${ROS_DISTRO}-lanelet2-core" \
    "ros-${ROS_DISTRO}-lanelet2-io" \
    "ros-${ROS_DISTRO}-lanelet2-maps" \
    "ros-${ROS_DISTRO}-lanelet2-projection" \
    "ros-${ROS_DISTRO}-lanelet2-python" \
    "ros-${ROS_DISTRO}-lanelet2-routing" \
    "ros-${ROS_DISTRO}-lanelet2-traffic-rules" \
    "ros-${ROS_DISTRO}-lanelet2-validation" \
    "ros-${ROS_DISTRO}-magic-enum" \
    "ros-${ROS_DISTRO}-nmea-msgs" \
    "ros-${ROS_DISTRO}-osqp-vendor" \
    "ros-${ROS_DISTRO}-point-cloud-msg-wrapper" \
    "ros-${ROS_DISTRO}-pointcloud-to-laserscan" \
    "ros-${ROS_DISTRO}-proxsuite" \
    "ros-${ROS_DISTRO}-radar-msgs" \
    "ros-${ROS_DISTRO}-rclpy-message-converter" \
    "ros-${ROS_DISTRO}-ros-testing" \
    "ros-${ROS_DISTRO}-rosbag2-storage-mcap" \
    "ros-${ROS_DISTRO}-rqt-robot-monitor" \
    "ros-${ROS_DISTRO}-rqt-runtime-monitor" \
    "ros-${ROS_DISTRO}-rmw-cyclonedds-cpp" \
    "ros-${ROS_DISTRO}-rtabmap" \
    "ros-${ROS_DISTRO}-rtabmap-ros" \
    "ros-${ROS_DISTRO}-septentrio-gnss-driver" \
    "ros-${ROS_DISTRO}-sophus" \
    "ros-${ROS_DISTRO}-tensorrt-cmake-module" \
    "ros-${ROS_DISTRO}-tf-transformations" \
    "ros-${ROS_DISTRO}-tl-expected" \
    "ros-${ROS_DISTRO}-topic-tools" \
    "ros-${ROS_DISTRO}-ublox-msgs" \
    "ros-${ROS_DISTRO}-udp-msgs" \
    "ros-${ROS_DISTRO}-xacro"
}

install_cuda_packages() {
  if [[ "${INSTALL_CUDA}" != "1" ]]; then
    return
  fi

  local cuda_arch cuda_version_dash
  case "$(uname -m)" in
    x86_64)
      cuda_arch="x86_64"
      ;;
    aarch64|arm64)
      cuda_arch="sbsa"
      ;;
    *)
      warn "Unsupported architecture for NVIDIA CUDA apt repository: $(uname -m). Skipping CUDA install."
      return
      ;;
  esac
  cuda_version_dash="${CUDA_VERSION//./-}"

  log "Configuring NVIDIA CUDA apt repository for CUDA ${CUDA_VERSION}"
  ${SUDO} rm -f /etc/apt/sources.list.d/cuda.list
  wget -O /tmp/cuda-keyring_1.1-1_all.deb \
    "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/${cuda_arch}/cuda-keyring_1.1-1_all.deb"
  ${SUDO} dpkg -i /tmp/cuda-keyring_1.1-1_all.deb
  rm -f /tmp/cuda-keyring_1.1-1_all.deb

  log "Installing NVIDIA CUDA ${CUDA_VERSION} development packages"
  ${SUDO} apt-get update
  apt_install \
    "cuda-command-line-tools-${cuda_version_dash}" \
    "cuda-minimal-build-${cuda_version_dash}" \
    "libcusparse-dev-${cuda_version_dash}" \
    "libcublas-dev-${cuda_version_dash}" \
    "libcurand-dev-${cuda_version_dash}" \
    "cuda-nvml-dev-${cuda_version_dash}" \
    "cuda-nvrtc-dev-${cuda_version_dash}" \
    "libnpp-dev-${cuda_version_dash}" \
    "libnvjpeg-dev-${cuda_version_dash}"

  if [[ "${cuda_arch}" == "x86_64" ]]; then
    apt_install "cuda-nvprof-${cuda_version_dash}" || true
  fi
}

install_nvidia_smi() {
  local packages=(
    nvidia-utils-595
    nvidia-utils-590
    nvidia-utils-580
    nvidia-utils-570
    nvidia-utils-550
    nvidia-utils-545
    nvidia-utils-535
  )

  if [[ "${INSTALL_NVIDIA_SMI}" != "1" ]]; then
    return
  fi

  log "Installing an available nvidia-utils package"
  ${SUDO} apt-get update
  for package in "${packages[@]}"; do
    if apt-cache show "${package}" >/dev/null 2>&1; then
      apt_install "${package}"
      return
    fi
  done

  warn "No supported nvidia-utils package was found in apt repositories"
}

install_nvidia_driver() {
  if [[ "${INSTALL_NVIDIA_DRIVER}" != "1" ]]; then
    return
  fi

  local kernel_version
  kernel_version=$(uname -r)
  local kernel_flavor="${kernel_version##*-}"
  local kernel_base="${kernel_version%-${kernel_flavor}}"
  local driver_versions=(595 590 580 570 550 545 535)
  local driver_variants=("-open" "" "-server-open" "-server")

  log "Installing NVIDIA driver kernel modules for kernel ${kernel_version}"
  ${SUDO} apt-get update

  for version in "${driver_versions[@]}"; do
    for variant in "${driver_variants[@]}"; do
      local package="linux-modules-nvidia-${version}${variant}-${kernel_base}-${kernel_flavor}"
      if apt-cache show "${package}" >/dev/null 2>&1; then
        apt_install "${package}" "nvidia-utils-${version}"
        log "Loading NVIDIA kernel module"
        ${SUDO} modprobe nvidia
        return
      fi
    done
  done

  warn "No supported NVIDIA kernel modules found for kernel ${kernel_version}"
}

install_docker_engine() {
  if [[ "${INSTALL_DOCKER}" != "1" ]]; then
    return
  fi

  if command -v docker >/dev/null 2>&1; then
    log "Docker is already installed"
  else
    log "Installing Docker Engine using the official convenience script"
    require_command curl
    curl -fsSL https://get.docker.com | ${SUDO} sh
  fi

  ${SUDO} systemctl enable --now docker
  if [[ -n "${SUDO}" ]]; then
    ${SUDO} usermod -aG docker "${TARGET_USER}" || true
  fi
}

install_nvidia_container_toolkit() {
  if [[ "${INSTALL_NVIDIA_CONTAINER_TOOLKIT}" != "1" ]]; then
    return
  fi

  if ! command -v docker >/dev/null 2>&1; then
    echo "[ERROR] Docker is required before installing NVIDIA Container Toolkit. Use --install-docker or install Docker first." >&2
    exit 1
  fi

  log "Configuring NVIDIA Container Toolkit apt repository"
  ${SUDO} mkdir -p /usr/share/keyrings
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | ${SUDO} gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | ${SUDO} tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

  log "Installing NVIDIA Container Toolkit"
  ${SUDO} apt-get update
  apt_install nvidia-container-toolkit

  log "Configuring Docker runtime for NVIDIA GPU containers"
  ${SUDO} nvidia-ctk runtime configure --runtime=docker
  ${SUDO} systemctl restart docker
}

install_ibus_mozc() {
  if [[ "${INSTALL_IBUS_MOZC}" != "1" ]]; then
    return
  fi

  log "Configuring IBus + Mozc for GUI input"
  ${SUDO} apt-get update
  apt_install dbus-x11 ibus ibus-mozc im-config
  run_as_target_user im-config -n ibus >/dev/null 2>&1 || true
}

install_uv() {
  if [[ "${INSTALL_UV}" != "1" ]]; then
    return
  fi

  if run_as_target_user bash -lc "command -v uv >/dev/null 2>&1"; then
    log "uv is already installed"
    return
  fi

  log "Installing uv with the official standalone installer"
  run_as_target_user env UV_NO_MODIFY_PATH=1 sh -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
}

install_yolo_cuda_venv() {
  local venv_dir="${REPO_ROOT}/Data/venvs/yolo_ros_cuda"

  if [[ "${INSTALL_YOLO_CUDA_VENV}" != "1" ]]; then
    return
  fi

  log "Installing CUDA-enabled YOLO Python environment into ${venv_dir}"
  run_as_target_user mkdir -p "${REPO_ROOT}/Data"
  run_as_target_user bash -lc "printf '%s\n' 'Generated runtime data is not part of the ROS workspace.' > '${REPO_ROOT}/Data/COLCON_IGNORE'"
  run_as_target_user python3 -m venv --system-site-packages "${venv_dir}"
  run_as_target_user "${venv_dir}/bin/python" -m pip install --upgrade pip "setuptools<82" wheel
  run_as_target_user "${venv_dir}/bin/python" -m pip install \
    --index-url "${YOLO_CUDA_TORCH_INDEX_URL}" \
    "torch==${YOLO_CUDA_TORCH_VERSION}" \
    "torchvision==${YOLO_CUDA_TORCHVISION_VERSION}"
  run_as_target_user "${venv_dir}/bin/python" -m pip install \
    "ultralytics==${YOLO_ULTRALYTICS_VERSION}" \
    "ultralytics-thop==2.0.19" \
    "lap>=0.5.12" \
    "opencv-python==4.11.0.86" \
    "polars==1.40.1" \
    "scipy==1.15.3" \
    "matplotlib==3.10.9" \
    "numpy==1.26.4" \
    "pillow==12.2.0" \
    "PyYAML==6.0.3" \
    "requests==2.28.1" \
    "psutil==7.2.2" \
    "beartype==0.21" \
    "jaxtyping==0.3.2" \
    "timm==1.0.19" \
    "omegaconf==2.3" \
    "easydict==1.13" \
    "dictor==0.1.12" \
    "diskcache==5.4" \
    "einops>=0.8.0" \
    "torchmetrics==0.11" \
    "numba==0.61.2"
  run_as_target_user "${venv_dir}/bin/python" - <<'PY'
import torch
import timm
import ultralytics

print(f"torch={torch.__version__} cuda_available={torch.cuda.is_available()} cuda={torch.version.cuda}")
print(f"timm={timm.__version__}")
print(f"ultralytics={ultralytics.__version__}")
if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available from the YOLO Python environment")
PY
}

install_libtorch() {
  local archive=""
  local download_url=""
  local install_dir="${LIBTORCH_INSTALL_DIR}"
  local install_parent=""
  local install_parent_parent=""
  local use_sudo=0
  local tmp_extract=""

  if [[ "${SKIP_LIBTORCH}" == "1" ]]; then
    return
  fi

  case "${LIBTORCH_VARIANT}" in
    cpu)
      archive="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip"
      ;;
    cu118)
      archive="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcu118.zip"
      ;;
    cu121)
      archive="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcu121.zip"
      ;;
    *)
      echo "[ERROR] Unsupported LIBTORCH_VARIANT: ${LIBTORCH_VARIANT}" >&2
      exit 1
      ;;
  esac

  download_url="https://download.pytorch.org/libtorch/${LIBTORCH_VARIANT}/${archive}"

  install_dir="$(readlink -m "${install_dir}")"
  install_parent="$(dirname "${install_dir}")"
  install_parent_parent="$(dirname "${install_parent}")"

  if [[ -d "${install_parent}" ]]; then
    if [[ ! -w "${install_parent}" ]]; then
      use_sudo=1
    fi
  elif [[ ! -d "${install_parent_parent}" || ! -w "${install_parent_parent}" ]]; then
    use_sudo=1
  fi

  tmp_extract="$(mktemp -d)"

  log "Installing libtorch ${LIBTORCH_VERSION} (${LIBTORCH_VARIANT}) into ${install_dir}"
  wget -O /tmp/libtorch.zip "${download_url}"
  unzip -q /tmp/libtorch.zip -d "${tmp_extract}"
  if [[ "${use_sudo}" == "1" ]]; then
    ${SUDO} mkdir -p "${install_parent}"
    ${SUDO} rm -rf "${install_dir}"
    ${SUDO} mv "${tmp_extract}/libtorch" "${install_dir}"
  else
    mkdir -p "${install_parent}"
    rm -rf "${install_dir}"
    mv "${tmp_extract}/libtorch" "${install_dir}"
  fi
  rm -rf "${tmp_extract}"
  rm -f /tmp/libtorch.zip

  if [[ ! -f "${install_dir}/share/cmake/Torch/TorchConfig.cmake" ]]; then
    echo "[ERROR] libtorch installation completed, but TorchConfig.cmake was not found" >&2
    exit 1
  fi
}

install_livrealsense() {
  if [[ "${SKIP_LIBREALSENSE}" == "1" ]]; then
    return
  fi

  log "Building librealsense ${LIBREALSENSE_VERSION} from source"
  rm -rf /tmp/librealsense
  git clone --depth 1 --branch "${LIBREALSENSE_VERSION}" https://github.com/IntelRealSense/librealsense.git /tmp/librealsense
  cmake -S /tmp/librealsense -B /tmp/librealsense/build \
    -DBUILD_EXAMPLES=true \
    -DBUILD_GRAPHICAL_EXAMPLES=true
  cmake --build /tmp/librealsense/build -j"$(nproc)"
  ${SUDO} cmake --install /tmp/librealsense/build
  ${SUDO} ldconfig
  rm -rf /tmp/librealsense
}

install_livox_sdk2() {
  if [[ "${SKIP_LIVOX_SDK2}" == "1" ]]; then
    return
  fi

  log "Building Livox-SDK2 ${LIVOX_SDK2_VERSION} from source"
  rm -rf /tmp/Livox-SDK2
  git clone --depth 1 --branch "${LIVOX_SDK2_VERSION}" https://github.com/Livox-SDK/Livox-SDK2.git /tmp/Livox-SDK2
  cmake -S /tmp/Livox-SDK2 -B /tmp/Livox-SDK2/build -DCMAKE_BUILD_TYPE=Release
  cmake --build /tmp/Livox-SDK2/build -j"$(nproc)"
  ${SUDO} cmake --install /tmp/Livox-SDK2/build
  ${SUDO} ldconfig
  rm -rf /tmp/Livox-SDK2
}

install_acados() {
  if [[ "${SKIP_ACADOS}" == "1" ]]; then
    return
  fi

  local tera_arch
  case "$(uname -m)" in
    x86_64)
      tera_arch="amd64"
      ;;
    aarch64|arm64)
      tera_arch="arm64"
      ;;
    *)
      warn "Unsupported architecture for acados tera renderer: $(uname -m). Skipping acados install."
      return
      ;;
  esac

  log "Building acados ${ACADOS_VERSION} into /opt/acados"
  ${SUDO} rm -rf /opt/acados
  ${SUDO} git clone \
    --depth 1 \
    --branch "${ACADOS_VERSION}" \
    --recursive \
    --shallow-submodules \
    https://github.com/acados/acados.git \
    /opt/acados

  ${SUDO} cmake -S /opt/acados -B /opt/acados/build \
    -DACADOS_WITH_QPOASES=ON \
    -DCMAKE_POSITION_INDEPENDENT_CODE=ON
  ${SUDO} cmake --build /opt/acados/build --target install -j"$(nproc)"

  ${SUDO} mkdir -p /opt/acados/bin
  ${SUDO} curl -fsSL \
    "https://github.com/acados/tera_renderer/releases/download/${ACADOS_TERA_RENDERER_VERSION}/t_renderer-${ACADOS_TERA_RENDERER_VERSION}-linux-${tera_arch}" \
    -o /opt/acados/bin/t_renderer
  ${SUDO} chmod 0755 /opt/acados/bin/t_renderer

  ${SUDO} python3 -m venv /opt/acados/.venv
  ${SUDO} /opt/acados/.venv/bin/pip install --upgrade pip
  ${SUDO} /opt/acados/.venv/bin/pip install casadi sympy
  ${SUDO} /opt/acados/.venv/bin/pip install -e /opt/acados/interfaces/acados_template

  ${SUDO} ldconfig
}

setup_rosdep() {
  log "Initializing rosdep"
  ${SUDO} rosdep init >/dev/null 2>&1 || true
  run_as_target_user rosdep update --rosdistro "${ROS_DISTRO}"
}

setup_colcon_metadata() {
  log "Updating colcon mixin and metadata"
  run_as_target_user colcon mixin add default \
    https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml >/dev/null 2>&1 || true
  run_as_target_user colcon mixin update
  run_as_target_user colcon metadata add default \
    https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml >/dev/null 2>&1 || true
  run_as_target_user colcon metadata update
}

install_cyclonedds_config() {
  log "Installing CycloneDDS configuration"
  ${SUDO} mkdir -p /etc/cyclonedds
  ${SUDO} install -m 0644 "${SCRIPT_DIR}/cyclonedds.xml" /etc/cyclonedds/cyclonedds.xml
}

append_bashrc_block() {
  local bashrc="${TARGET_HOME}/.bashrc"
  local marker_begin="# >>> AMaRanthus setup >>>"
  local marker_end="# <<< AMaRanthus setup <<<"

  touch "${bashrc}"
  if grep -Fq "${marker_begin}" "${bashrc}"; then
    log "AMaRanthus shell block already present in ${bashrc}"
    return
  fi

  log "Appending AMaRanthus environment block to ${bashrc}"
  cat >>"${bashrc}" <<EOF
${marker_begin}
if [ -f "${REPO_ROOT}/setup/ubuntu_env.sh" ]; then
  source "${REPO_ROOT}/setup/ubuntu_env.sh"
fi
${marker_end}
EOF
}

print_next_steps() {
  cat <<EOF

[DONE] Ubuntu host setup completed.

Next steps:
  1. Open a new shell or run: source "${REPO_ROOT}/setup/ubuntu_env.sh"
  2. In the workspace root, install package dependencies if needed:
       rosdep install --from-paths src --ignore-src -r -y
  3. Build the workspace:
       ./build.sh

Optional GPU checks:
  - Host GPU visibility: nvidia-smi
  - Docker GPU visibility:
      docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
EOF
}

main() {
  detect_ubuntu

  sync_submodules
  install_repository_prerequisites
  require_command curl
  configure_ros2_repository
  install_base_packages
  require_command git
  require_command cmake
  require_command wget
  require_command unzip
  install_ros_packages
  install_cuda_packages
  install_nvidia_smi
  install_nvidia_driver
  install_docker_engine
  install_nvidia_container_toolkit
  install_ibus_mozc
  install_uv
  install_yolo_cuda_venv
  install_libtorch
  install_livrealsense
  install_livox_sdk2
  install_acados
  setup_rosdep
  setup_colcon_metadata
  install_cyclonedds_config
  append_bashrc_block
  print_next_steps
}

main "$@"
