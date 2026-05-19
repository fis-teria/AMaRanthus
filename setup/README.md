# Ubuntu Local Setup

`docker/Dockerfile` をもとに、Ubuntu ホスト上へできるだけ同じ開発環境を再現するためのセットアップです。ROS 2 Humble / librealsense / Livox-SDK2 / libtorch / acados / CycloneDDS を揃え、Helianthus 直下の Autoware ビルドで必要になる ROS / apt 依存も導入します。必要に応じて CUDA と NVIDIA Container Toolkit も導入できます。

## 対象

- 推奨 OS: Ubuntu 22.04 (`jammy`)
- 想定用途:
  - Docker を使わずにホスト Ubuntu 上で直接ビルド・実行する
  - Docker 実行時にも `--gpus all` を使えるように NVIDIA Container Toolkit を入れる

## ファイル

- `setup/ubuntu_setup.sh`: 本体セットアップ
- `setup/ubuntu_env.sh`: ROS / Torch / CycloneDDS の環境変数を読み込む
- `setup/cyclonedds.xml`: CycloneDDS 設定

Autoware 関連では Lanelet2、GridMap、`generate_parameter_library`、`tensorrt_cmake_module` など、Helianthus 直下ビルドで不足しやすい apt パッケージも `ubuntu_setup.sh` でまとめて入れます。
`autoware_path_optimizer` が要求する `acados` は `/opt/acados` へソースビルドし、`ubuntu_env.sh` で `CMAKE_PREFIX_PATH` / `ACADOS_SOURCE_DIR` / `LD_LIBRARY_PATH` を設定します。

## 使い方

まずは submodule ごと clone するのを推奨します。

```bash
git clone --recurse-submodules git@github.com:fis-teria/AMaRanthus.git
```

通常の `git clone` を使った場合でも、`setup/ubuntu_setup.sh` が内部で `git submodule update --init --recursive` を実行するため、セットアップ時に補完されます。

最小構成:

```bash
./setup/ubuntu_setup.sh
```

この最小構成には、`uv` の自動インストール、WSL 上での `ibus` + `mozc` 自動設定、CUDA 12.1 版 libtorch (`cu121`) の導入も含まれます。
CPU 版 libtorch が必要な場合は `--libtorch-variant cpu` を指定してください。

CUDA も含めてホスト実行用に揃える:

```bash
./setup/ubuntu_setup.sh --with-cuda --with-nvidia-smi --with-nvidia-driver --with-yolo-cuda-venv --libtorch-variant cu121
```

`--with-cuda` は Autoware に合わせて NVIDIA apt repository から CUDA 12.8 系の開発パッケージを導入します。別バージョンを使う場合は `CUDA_VERSION=12.8` を上書きしてください。
`--with-yolo-cuda-venv` は `e2e_transfuser` / `camera_lidar_bringup` から参照する Python 環境を `Data/venvs/yolo_ros_cuda` に作成し、CUDA 対応の `torch` / `torchvision`、`ultralytics`、LEAD / TFv6 の推論に必要な軽量依存を導入します。
`--libtorch-install-dir /path/to/libtorch` か `LIBTORCH_INSTALL_DIR=/path/to/libtorch` を付けると、`/opt/libtorch` 以外へ libtorch を導入できます。開発機で `sudo` を使わずに置きたい場合は、Helianthus 直下から `./setup/ubuntu_setup.sh --libtorch-variant cu121 --libtorch-install-dir "$PWD/Data/libtorch"` のように指定します。

NVIDIA driver カーネルモジュールのみをインストール (GPU を使うが nvidia-utils は不要な場合):

```bash
./setup/ubuntu_setup.sh --with-nvidia-driver
```

Docker の GPU パススルーも使えるようにする:

```bash
./setup/ubuntu_setup.sh --install-docker --with-nvidia-container-toolkit
```

全部まとめて実行する例:

```bash
./setup/ubuntu_setup.sh \
  --with-cuda \
  --with-nvidia-smi \
  --with-nvidia-driver \
  --with-yolo-cuda-venv \
  --install-docker \
  --with-nvidia-container-toolkit \
  --libtorch-variant cu121
```

`uv`、`ibus`、`acados` を入れたくない場合:

```bash
./setup/ubuntu_setup.sh --skip-uv --skip-ibus-mozc --skip-acados
```

## セットアップ後

新しいシェルを開くか、次を実行します。

```bash
source ./setup/ubuntu_env.sh
```

`ubuntu_env.sh` は以下も行います。

- `/opt/ros/humble/setup.bash` の読み込み
- ワークスペースの `install/setup.bash` の読み込み
- `~/.local/bin` を `PATH` へ追加して `uv` を見えるようにする
- WSL 上では `ibus-daemon` の自動起動と `mozc-jp` エンジンの選択

依存関係を rosdep で補完する場合:

```bash
rosdep install --from-paths src --ignore-src -r -y
```

ワークスペースをビルド:

```bash
./build.sh
```

## GPU 動作確認

ホストで GPU を確認:

```bash
nvidia-smi
```

Docker から GPU を確認:

```bash
docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi
```

## 注意点

- ROS 2 Humble の apt バイナリ前提なので、Ubuntu 22.04 以外では一部ステップが失敗する可能性があります。
- `--with-cuda` は NVIDIA apt repository の CUDA パッケージを使います。Autoware の既定は CUDA 12.8 です。
- `--with-nvidia-driver` はカーネルアップデート後に NVIDIA driver が動作しなくなった場合に便利です。現在のカーネルバージョン用の `linux-modules-nvidia-<version>[-open]-<kernel>-<flavor>` パッケージを自動検出・インストールします。
- `--with-yolo-cuda-venv` は数 GB の PyTorch CUDA wheel を `Data/venvs/yolo_ros_cuda` に導入します。この `Data/` は git 管理外で、`COLCON_IGNORE` により colcon の探索対象から外れます。
- `--with-nvidia-container-toolkit` は Docker が必要です。未導入なら `--install-docker` を併用してください。
- `libtorch` の GPU バリアントは `cu118` と `cu121` を選べます。既定は `cu121` です。ホスト側 CUDA / ドライバとの整合は利用環境に合わせてください。
- `setup/ubuntu_env.sh` は `LIBTORCH_ROOT` が指定されていればそれを使い、未指定の場合は Helianthus 直下の `Data/libtorch`、AMaRanthus 直下の `Data/libtorch`、`/opt/libtorch` の順に参照します。
- `uv` は Astral の公式 standalone installer で導入し、PATH 変更は `ubuntu_env.sh` 側で管理します。
