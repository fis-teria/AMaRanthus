#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

ROS_DISTRO="${ROS_DISTRO:-humble}"
ROS_APT_CODENAME="${ROS_APT_CODENAME:-jammy}"
LIBREALSENSE_VERSION="${LIBREALSENSE_VERSION:-v2.55.1}"
LIVOX_SDK2_VERSION="${LIVOX_SDK2_VERSION:-v1.2.4}"
LIBTORCH_VERSION="${LIBTORCH_VERSION:-2.4.1}"
LIBTORCH_VARIANT="${LIBTORCH_VARIANT:-cpu}"
INSTALL_CUDA="${INSTALL_CUDA:-0}"
INSTALL_NVIDIA_CONTAINER_TOOLKIT="${INSTALL_NVIDIA_CONTAINER_TOOLKIT:-0}"
INSTALL_DOCKER="${INSTALL_DOCKER:-0}"
INSTALL_NVIDIA_SMI="${INSTALL_NVIDIA_SMI:-0}"
INSTALL_NVIDIA_DRIVER="${INSTALL_NVIDIA_DRIVER:-0}"
INSTALL_IBUS_MOZC="${INSTALL_IBUS_MOZC:-1}"
INSTALL_UV="${INSTALL_UV:-1}"
SKIP_LIBREALSENSE="${SKIP_LIBREALSENSE:-0}"
SKIP_LIVOX_SDK2="${SKIP_LIVOX_SDK2:-0}"
SKIP_LIBTORCH="${SKIP_LIBTORCH:-0}"

usage() {
  cat <<'EOF'
Usage: ./setup/ubuntu_setup.sh [options]

Reproduces the Docker development environment on an Ubuntu host as closely as possible.

Options:
  --with-cuda                       Install Ubuntu's CUDA toolkit package.
  --with-nvidia-smi                Install an available nvidia-utils package.
  --with-nvidia-driver            Install NVIDIA driver kernel modules for current kernel.
  --with-nvidia-container-toolkit  Install NVIDIA Container Toolkit for Docker GPU passthrough.
  --install-docker                 Install Docker Engine using the official convenience script.
  --skip-ibus-mozc                 Skip ibus / mozc installation and shell setup.
  --skip-uv                        Skip uv installation.
  --libtorch-variant <cpu|cu118|cu121>
                                   Select the libtorch package variant to install.
  --skip-libtorch                  Skip libtorch installation.
  --skip-librealsense              Skip librealsense source build.
  --skip-livox-sdk2                Skip Livox-SDK2 source build.
  -h, --help                       Show this help.

Environment variables:
  ROS_DISTRO, ROS_APT_CODENAME, LIBREALSENSE_VERSION, LIVOX_SDK2_VERSION,
  LIBTORCH_VERSION, LIBTORCH_VARIANT, INSTALL_CUDA, INSTALL_NVIDIA_CONTAINER_TOOLKIT,
  INSTALL_DOCKER, INSTALL_NVIDIA_SMI, INSTALL_NVIDIA_DRIVER, INSTALL_IBUS_MOZC, INSTALL_UV,
  SKIP_LIBREALSENSE, SKIP_LIVOX_SDK2, SKIP_LIBTORCH

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
    --libtorch-variant)
      shift
      LIBTORCH_VARIANT="${1:-}"
      ;;
    --skip-libtorch)
      SKIP_LIBTORCH=1
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
    libeigen3-dev \
    libpcl-dev
}

install_repository_prerequisites() {
  log "Installing apt repository prerequisites"
  ${SUDO} apt-get update
  apt_install \
    ca-certificates \
    curl \
    gnupg2 \
    lsb-release \
    software-properties-common
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
    "ros-${ROS_DISTRO}-robot-localization" \
    "ros-${ROS_DISTRO}-imu-filter-madgwick" \
    "ros-${ROS_DISTRO}-rmw-cyclonedds-cpp" \
    "ros-${ROS_DISTRO}-rtabmap" \
    "ros-${ROS_DISTRO}-rtabmap-ros"
}

install_cuda_packages() {
  if [[ "${INSTALL_CUDA}" != "1" ]]; then
    return
  fi

  log "Installing Ubuntu CUDA toolkit package"
  ${SUDO} apt-get update
  apt_install nvidia-cuda-toolkit
}

install_nvidia_smi() {
  local packages=(
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
  local driver_versions=(590 580 570 550 545 535)

  log "Installing NVIDIA driver kernel modules for kernel ${kernel_version}"
  ${SUDO} apt-get update

  for version in "${driver_versions[@]}"; do
    local package="linux-modules-nvidia-${version}-${kernel_version}-generic"
    if apt-cache show "${package}" >/dev/null 2>&1; then
      apt_install "${package}"
      log "Loading NVIDIA kernel module"
      ${SUDO} modprobe nvidia
      return
    fi
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

install_libtorch() {
  local archive=""
  local download_url=""

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

  log "Installing libtorch ${LIBTORCH_VERSION} (${LIBTORCH_VARIANT}) into /opt/libtorch"
  wget -O /tmp/libtorch.zip "${download_url}"
  ${SUDO} rm -rf /opt/libtorch
  ${SUDO} unzip -q /tmp/libtorch.zip -d /opt
  rm -f /tmp/libtorch.zip

  if [[ ! -f /opt/libtorch/share/cmake/Torch/TorchConfig.cmake ]]; then
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
  install_libtorch
  install_livrealsense
  install_livox_sdk2
  setup_rosdep
  setup_colcon_metadata
  install_cyclonedds_config
  append_bashrc_block
  print_next_steps
}

main "$@"
