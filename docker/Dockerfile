# ROS 2 Humble + Ubuntu 22.04 (Jammy)
FROM ros:humble-ros-base-jammy

ENV DEBIAN_FRONTEND=noninteractive
ENV LD_LIBRARY_PATH=/usr/local/lib:${LD_LIBRARY_PATH}
ENV ROS_DISTRO=humble
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV RCUTILS_LOGGING_USE_STDOUT=1
ENV RCUTILS_LOGGING_BUFFERED_STREAM=1
ENV RCUTILS_COLORIZED_OUTPUT=1

ARG UID=1000
ARG GID=1000
ARG USERNAME=admin

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
    libx11-dev \
    libxi-dev \
    libxt-dev \
    && rm -rf /var/lib/apt/lists/*

# 一般ユーザーを追加（ホストUID/GIDに合わせやすくする）
RUN groupadd -g ${GID} ${USERNAME} && \
    useradd -m -s /bin/bash -u ${UID} -g ${GID} ${USERNAME} && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# ROS 2 パッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-desktop \
    ros-humble-cv-bridge \
    ros-humble-pcl-conversions \
    ros-humble-teleop-twist-keyboard \
    ros-humble-diagnostic-updater \
    ros-humble-rmw-cyclonedds-cpp \
    ros-humble-rtabmap \
    ros-humble-rtabmap-ros \
    && rm -rf /var/lib/apt/lists/*

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
RUN git clone https://github.com/IntelRealSense/librealsense.git && \
    cd librealsense && \
    git checkout v2.55.1 && \
    mkdir -p build && cd build && \
    cmake .. \
      -DBUILD_EXAMPLES=true \
      -DBUILD_GRAPHICAL_EXAMPLES=true && \
    make -j"$(nproc)" && \
    make install && \
    ldconfig

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
RUN echo "source /opt/ros/humble/setup.bash" >> /home/${USERNAME}/.bashrc && \
    echo "if [ -f /home/${USERNAME}/autonomous/install/setup.bash ]; then source /home/${USERNAME}/autonomous/install/setup.bash; fi" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_LOGGING_USE_STDOUT=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_LOGGING_BUFFERED_STREAM=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RCUTILS_COLORIZED_OUTPUT=1" >> /home/${USERNAME}/.bashrc && \
    echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> /home/${USERNAME}/.bashrc && \
    echo "export CYCLONEDDS_URI=file:///etc/cyclonedds/cyclonedds.xml" >> /home/${USERNAME}/.bashrc

USER ${USERNAME}
SHELL ["/bin/bash", "-c"]

CMD ["bash"]