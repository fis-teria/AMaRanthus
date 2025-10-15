# This is an auto generated Dockerfile for ros:ros-base
# generated from docker_images_ros2/create_ros_image.Dockerfile.em
FROM ros:humble-ros-core-jammy

# ライブラリパスを設定
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
ENV DEBIAN_FRONTEND=noninteractive

ARG UID=1000 # ホストのユーザーIDと一致させる
ARG GID=1000
 
#RUN apt-get update && apt-get install -y sudo
#
#RUN groupadd -g $GID admin && \
#    useradd -m -u $UID -g $GID -s /bin/bash admin && \
#    echo "admin ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers
#

# install bootstrap tools
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    git \
    python3-colcon-common-extensions \
    python3-colcon-mixin \
    python3-rosdep \
    python3-vcstool \
    x11-apps\
    cmake \
    libusb-1.0-0-dev \
    pkg-config \
    libgtk-3-dev \
    libglfw3-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libssl-dev \
    libudev-dev \
    libx11-dev \
    libxi-dev \
    libxt-dev \
    net-tools \
    arp-scan \
    && rm -rf /var/lib/apt/lists/*

# ROS2新しい公開鍵の設定
## 1. 必要なツールをインストール
#RUN apt-get update && apt-get install -y gnupg
#
## 古い ROS 鍵を削除（存在しない場合もあるので || true を付ける）
#RUN apt-key del F42ED6FBAB17C654 || true
#
## 2. ROS 公式の新しい GPG 鍵を取得して保存
#RUN curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
#    -o /usr/share/keyrings/ros-archive-keyring.gpg
#
## 3. ROS 2 Humble 用の APT リポジトリを追加
#RUN echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
#    http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
#    > /etc/apt/sources.list.d/ros2.list


# ROS2 packages
RUN apt-get update && apt-get install --no-install-recommends -y \  
      ros-humble-desktop \
      ros-humble-cv-bridge \
      ros-humble-pcl-conversions \
      ros-humble-teleop-twist-keyboard \
      ros-humble-diagnostic-updater \
      ros-humble-rtabmap* \
      ros-humble-rmw-cyclonedds-cpp


# bootstrap rosdep
RUN rosdep init || echo "rosdep already initialized" && \
  rosdep update --rosdistro $ROS_DISTRO

# setup colcon mixin and metadata
RUN colcon mixin add default \
      https://raw.githubusercontent.com/colcon/colcon-mixin-repository/master/index.yaml && \
    colcon mixin update && \
    colcon metadata add default \
      https://raw.githubusercontent.com/colcon/colcon-metadata-repository/master/index.yaml && \
    colcon metadata update

# librealsense クローンとビルド（Viewer付き）
RUN git clone https://github.com/IntelRealSense/librealsense.git /librealsense && \
    cd /librealsense && \
    git checkout v2.55.1 && \
    mkdir build && cd build && \
    cmake .. -DBUILD_EXAMPLES=true -DBUILD_GRAPHICAL_EXAMPLES=true && \
    make uninstall && \
    make clean && \
    make -j$(nproc) && \
    make install

# ~/.bashrc に記述。
RUN echo "source /opt/ros/humble/setup.sh" >> ~/.bashrc
RUN echo "source /root/autonomous/install/setup.bash" >> ~/.bashrc
RUN echo "export RCUTILS_LOGGING_USE_STDOUT=1" >> ~/.bashrc
RUN echo "export RCUTILS_LOGGING_BUFFERED_STREAM=1" >> ~/.bashrc
RUN echo "export RCUTILS_COLORIZED_OUTPUT=1" >> ~/.bashrc
RUN echo "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp" >> ~/.bashrc
RUN echo 'export CYCLONEDDS_URI="<Disc><DefaultMulticastAddress>0.0.0.0</DefaultMulticastAddress></Disc>"' >> ~/.bashrc

# install ros2 packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ros-humble-ros-base=0.10.0-1* \
    && rm -rf /var/lib/apt/lists/*