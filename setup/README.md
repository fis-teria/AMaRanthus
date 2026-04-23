# Ubuntu Local Setup

`docker/Dockerfile` をもとに、Ubuntu ホスト上へできるだけ同じ開発環境を再現するためのセットアップです。ROS 2 Humble / librealsense / Livox-SDK2 / libtorch / CycloneDDS を揃え、必要に応じて CUDA と NVIDIA Container Toolkit も導入できます。

## 対象

- 推奨 OS: Ubuntu 22.04 (`jammy`)
- 想定用途:
  - Docker を使わずにホスト Ubuntu 上で直接ビルド・実行する
  - Docker 実行時にも `--gpus all` を使えるように NVIDIA Container Toolkit を入れる

## ファイル

- `setup/ubuntu_setup.sh`: 本体セットアップ
- `setup/ubuntu_env.sh`: ROS / Torch / CycloneDDS の環境変数を読み込む
- `setup/cyclonedds.xml`: CycloneDDS 設定

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

この最小構成には、`uv` の自動インストールと、WSL 上での `ibus` + `mozc` 自動設定も含まれます。

CUDA も含めてホスト実行用に揃える:

```bash
./setup/ubuntu_setup.sh --with-cuda --with-nvidia-smi --with-nvidia-driver --libtorch-variant cu121
```

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
  --install-docker \
  --with-nvidia-container-toolkit \
  --libtorch-variant cu121
```

`uv` や `ibus` を入れたくない場合:

```bash
./setup/ubuntu_setup.sh --skip-uv --skip-ibus-mozc
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
- `--with-cuda` は Ubuntu リポジトリの `nvidia-cuda-toolkit` を使います。ネイティブ CUDA 開発で厳密なバージョン固定が必要なら、必要に応じて NVIDIA 提供の CUDA パッケージへ置き換えてください。
- `--with-nvidia-driver` はカーネルアップデート後に NVIDIA driver が動作しなくなった場合に便利です。現在のカーネルバージョン用のカーネルモジュールパッケージを自動検出・インストールします。
- `--with-nvidia-container-toolkit` は Docker が必要です。未導入なら `--install-docker` を併用してください。
- `libtorch` の GPU バリアントは `cu118` と `cu121` を選べます。ホスト側 CUDA / ドライバとの整合は利用環境に合わせてください。
- `uv` は Astral の公式 standalone installer で導入し、PATH 変更は `ubuntu_env.sh` 側で管理します。
