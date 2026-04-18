# ROS 2 Humble + Ubuntu 22.04 (Jammy)
FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/usr/local/lib:${LD_LIBRARY_PATH:-}
ENV ROS_DISTRO=humble
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV RCUTILS_LOGGING_USE_STDOUT=1
ENV RCUTILS_LOGGING_BUFFERED_STREAM=1
ENV RCUTILS_COLORIZED_OUTPUT=1

ARG UID=1000
ARG GID=1000
ARG USERNAME=admin
ARG INSTALL_CUDA=1
ARG INSTALL_NVIDIA_SMI=1
ARG LIBREALSENSE_VERSION=v2.55.1
ARG LIVOX_SDK2_VERSION=v1.2.4
ARG LIBTORCH_VERSION=2.4.1
ARG LIBTORCH_VARIANT=cpu

# 基本ツール、開発ツール、ネットワーク確認ツール、便利ツール
RUN apt-get update && apt-get install -y --no-install-recommends \
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
    && rm -rf /var/lib/apt/lists/*

# CUDA Toolkit は通常 Ubuntu イメージでも任意で入れられるようにしておく。
RUN if [ "${INSTALL_CUDA}" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends nvidia-cuda-toolkit && \
      rm -rf /var/lib/apt/lists/*; \
    fi

# nvidia-smi はドライバ系ユーザー空間パッケージに含まれる。Ubuntu の利用可能版から順に試す。
RUN if [ "${INSTALL_NVIDIA_SMI}" = "1" ]; then \
      apt-get update && \
      for pkg in nvidia-utils-590 nvidia-utils-580 nvidia-utils-570 nvidia-utils-550 nvidia-utils-545 nvidia-utils-535; do \
        if apt-get install -y --no-install-recommends "${pkg}"; then \
          break; \
        fi; \
      done && \
      rm -rf /var/lib/apt/lists/*; \
    fi

ENV CUDA_HOME=/usr
ENV CUDAToolkit_ROOT=/usr
ENV PATH=/usr/local/cuda/bin:${PATH}
ENV LD_LIBRARY_PATH=/usr/local/cuda/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}
ENV NVIDIA_VISIBLE_DEVICES=all
ENV NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics

# 一般ユーザーを追加（ホストUID/GIDに合わせやすくする）
RUN groupadd -g ${GID} ${USERNAME} && \
    useradd -m -s /bin/bash -u ${UID} -g ${GID} ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ROS 2 パッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-desktop \
    ros-humble-cv-bridge \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-laser-geometry \
    ros-humble-message-filters \
    ros-humble-pcl-conversions \
    ros-humble-pcl-ros \
    ros-humble-rosbag2 \
    ros-humble-std-srvs \
    ros-humble-tf2-geometry-msgs \
    ros-humble-tf2-sensor-msgs \
    ros-humble-tf2-msgs \
    ros-humble-teleop-twist-keyboard \
    ros-humble-diagnostic-updater \
    ros-humble-robot-localization \
    ros-humble-imu-filter-madgwick \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-rtabmap \
    ros-humble-rtabmap-ros \
    libeigen3-dev \
    libpcl-dev \
    && rm -rf /var/lib/apt/lists/*

# distro 付属の Torch/Caffe2 CMake 設定に依存せず、公式配布の libtorch を固定パスへ導入する。
RUN case "${LIBTORCH_VARIANT}" in \
      cpu) LIBTORCH_ARCHIVE="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcpu.zip" ;; \
      cu118) LIBTORCH_ARCHIVE="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcu118.zip" ;; \
      cu121) LIBTORCH_ARCHIVE="libtorch-cxx11-abi-shared-with-deps-${LIBTORCH_VERSION}%2Bcu121.zip" ;; \
      *) echo "Unsupported LIBTORCH_VARIANT: ${LIBTORCH_VARIANT}" >&2; exit 1 ;; \
    esac && \
    wget -O /tmp/libtorch.zip "https://download.pytorch.org/libtorch/${LIBTORCH_VARIANT}/${LIBTORCH_ARCHIVE}" && \
    rm -rf /opt/libtorch && \
    unzip -q /tmp/libtorch.zip -d /opt && \
    rm -f /tmp/libtorch.zip && \
    test -f /opt/libtorch/share/cmake/Torch/TorchConfig.cmake

ENV Torch_DIR=/opt/libtorch/share/cmake/Torch
ENV CMAKE_PREFIX_PATH=/opt/libtorch:${CMAKE_PREFIX_PATH:-}
ENV LD_LIBRARY_PATH=/opt/libtorch/lib:/usr/local/cuda/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}

# rosdep 初期化
RUN rosdep init || true && \
    rosdep update --rosdistro ${ROS_DISTRO}

# colcon mixin / metadata
RUN colcon mixin add default \
      https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml || true && \
    colcon mixin update && \
    colcon metadata add default \
      https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml || true && \
    colcon metadata update

# librealsense ビルド
WORKDIR /opt
RUN git clone --depth 1 --branch ${LIBREALSENSE_VERSION} https://github.com/IntelRealSense/librealsense.git /tmp/librealsense && \
    cmake -S /tmp/librealsense -B /tmp/librealsense/build \
      -DBUILD_EXAMPLES=true \
      -DBUILD_GRAPHICAL_EXAMPLES=true && \
    cmake --build /tmp/librealsense/build -j"$(nproc)" && \
    cmake --install /tmp/librealsense/build && \
    ldconfig && \
    rm -rf /tmp/librealsense

# Livox-SDK2 を /usr/local に導入して livox_ros_driver2 がそのままビルドできるようにする
RUN git clone --depth 1 --branch ${LIVOX_SDK2_VERSION} https://github.com/Livox-SDK/Livox-SDK2.git /tmp/Livox-SDK2 && \
    cmake -S /tmp/Livox-SDK2 -B /tmp/Livox-SDK2/build -DCMAKE_BUILD_TYPE=Release && \
    cmake --build /tmp/Livox-SDK2/build -j"$(nproc)" && \
    cmake --install /tmp/Livox-SDK2/build && \
    ldconfig && \
    rm -rf /tmp/Livox-SDK2

# CycloneDDS 設定ファイル
RUN mkdir -p /etc/cyclonedds
RUN printf '%s\n' \
'<?xml version="1.0" encoding="UTF-8" ?>' \
'<CycloneDDS xmlns="https://cdds.io/config">' \
'  <Domain id="any">' \
'    <General>' \
'      <Interfaces>' \
'        <NetworkInterface autodetermine="true" />' \
'      </Interfaces>' \
'      <AllowMulticast>true</AllowMulticast>' \
'    </General>' \
'  </Domain>' \
'</CycloneDDS>' \
> /etc/cyclonedds/cyclonedds.xml

ENV CYCLONEDDS_URI=file:///etc/cyclonedds/cyclonedds.xml

# ワークスペース
WORKDIR /home/${USERNAME}/autonomous
RUN chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# bashrc 設定
RUN echo "source /opt/ros/humble/setup.sh" >> /home/${USERNAME}/.bashrc && \
    echo "if [ -f /home/${USERNAME}/autonomous/install/setup.sh ]; then source /home/${USERNAME}/autonomous/install/setup.sh; fi" >> /home/${USERNAME}/.bashrc && \
    echo "export Torch_DIR=/opt/libtorch/share/cmake/Torch" >> /home/${USERNAME}/.bashrc && \
    echo "export CMAKE_PREFIX_PATH=/opt/libtorch:\${CMAKE_PREFIX_PATH}" >> /home/${USERNAME}/.bashrc && \
    echo "export LD_LIBRARY_PATH=/opt/libtorch/lib:/usr/local/cuda/lib64:/usr/local/lib:\${LD_LIBRARY_PATH}" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_LOGGING_USE_STDOUT=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_LOGGING_BUFFERED_STREAM=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_COLORIZED_OUTPUT=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /home/${USERNAME}/.bashrc && \
    echo "export CYCLONEDDS_URI=file:///etc/cyclonedds/cyclonedds.xml" >> /home/${USERNAME}/.bashrc

USER ${USERNAME}
SHELL ["/bin/bash", "-c"]

CMD ["bash"]
