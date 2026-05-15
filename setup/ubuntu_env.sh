#!/usr/bin/env bash

if [[ -n "${BASH_SOURCE[0]:-}" ]]; then
  _amaranthus_setup_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  _amaranthus_setup_dir="$(pwd)/setup"
fi

_amaranthus_repo_root="$(cd "${_amaranthus_setup_dir}/.." && pwd)"

if [[ -d "${HOME}/.local/bin" && ":${PATH}:" != *":${HOME}/.local/bin:"* ]]; then
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if [[ -f /opt/ros/humble/setup.bash ]]; then
  _amaranthus_had_nounset=false
  if [[ $- == *u* ]]; then
    _amaranthus_had_nounset=true
    set +u
  fi
  # shellcheck disable=SC1091
  source /opt/ros/humble/setup.bash
  if [[ "${_amaranthus_had_nounset}" == true ]]; then
    set -u
  fi
  unset _amaranthus_had_nounset
fi

if [[ -f "${_amaranthus_repo_root}/install/setup.bash" ]]; then
  _amaranthus_had_nounset=false
  if [[ $- == *u* ]]; then
    _amaranthus_had_nounset=true
    set +u
  fi
  # shellcheck disable=SC1091
  source "${_amaranthus_repo_root}/install/setup.bash"
  if [[ "${_amaranthus_had_nounset}" == true ]]; then
    set -u
  fi
  unset _amaranthus_had_nounset
fi

export Torch_DIR=/opt/libtorch/share/cmake/Torch
if [[ -d /opt/acados ]]; then
  export ACADOS_SOURCE_DIR=/opt/acados
  export CMAKE_PREFIX_PATH=/opt/acados:/opt/libtorch:/usr/local:${CMAKE_PREFIX_PATH:-}
  export LD_LIBRARY_PATH=/opt/acados/lib:/opt/libtorch/lib:/usr/local/cuda/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}
else
  export CMAKE_PREFIX_PATH=/opt/libtorch:/usr/local:${CMAKE_PREFIX_PATH:-}
  export LD_LIBRARY_PATH=/opt/libtorch/lib:/usr/local/cuda/lib64:/usr/local/lib:${LD_LIBRARY_PATH:-}
fi
if [[ -d /usr/local/cuda ]]; then
  export CUDA_HOME=/usr/local/cuda
  export CUDAToolkit_ROOT=/usr/local/cuda
  export PATH=/usr/local/cuda/bin:${PATH}
else
  export CUDA_HOME=/usr
  export CUDAToolkit_ROOT=/usr
fi
export RCUTILS_LOGGING_USE_STDOUT=1
export RCUTILS_LOGGING_BUFFERED_STREAM=1
export RCUTILS_COLORIZED_OUTPUT=1
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=file:///etc/cyclonedds/cyclonedds.xml

_amaranthus_is_wsl=false
if grep -qiE "(microsoft|wsl)" /proc/version 2>/dev/null; then
  _amaranthus_is_wsl=true
fi

if [[ "${_amaranthus_is_wsl}" == true ]]; then
  export QT_IM_MODULE=ibus
  export GTK_IM_MODULE=ibus
  export XMODIFIERS=@im=ibus

  if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && command -v dbus-launch >/dev/null 2>&1; then
      eval "$(dbus-launch --sh-syntax)"
    fi

    if command -v pgrep >/dev/null 2>&1 && command -v ibus-daemon >/dev/null 2>&1; then
      if ! pgrep -u "${USER}" -x ibus-daemon >/dev/null 2>&1; then
        ibus-daemon -drx --panel=disable >/tmp/ibus-daemon.log 2>&1 &
      fi
    fi

    if command -v ibus >/dev/null 2>&1; then
      ibus engine mozc-jp >/dev/null 2>&1 || true
    fi
  fi
fi
