#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  play_livox_bag_rviz.sh <rosbag_path> [rviz_config_path]

Description:
  指定した rosbag2 をループ再生しながら RViz2 で表示します。

Examples:
  play_livox_bag_rviz.sh Data/rosbag/livox_sensor_bag
  play_livox_bag_rviz.sh Data/rosbag/livox_sensor_bag /path/to/custom.rviz
EOF
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
DEFAULT_RVIZ_CONFIG="${WORKSPACE_ROOT}/src/drivers/livox_ros_driver2/config/display_point_cloud_ROS2.rviz"

BAG_PATH_INPUT="$1"
RVIZ_CONFIG="${2:-${DEFAULT_RVIZ_CONFIG}}"

if [[ "${BAG_PATH_INPUT}" = /* ]]; then
  BAG_PATH="${BAG_PATH_INPUT}"
else
  BAG_PATH="${WORKSPACE_ROOT}/${BAG_PATH_INPUT}"
fi

if [[ ! -d "${BAG_PATH}" ]]; then
  echo "rosbag directory not found: ${BAG_PATH}" >&2
  exit 1
fi

if [[ ! -f "${RVIZ_CONFIG}" ]]; then
  echo "rviz config not found: ${RVIZ_CONFIG}" >&2
  exit 1
fi

if [[ -f "${WORKSPACE_ROOT}/install/setup.bash" ]]; then
  # Reuse the current workspace overlay when it has already been built.
  restore_nounset=0
  if [[ $- == *u* ]]; then
    restore_nounset=1
    set +u
  fi
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/install/setup.bash"
  if [[ ${restore_nounset} -eq 1 ]]; then
    set -u
  fi
fi

cleanup() {
  local exit_code=$?

  if [[ -n "${BAG_PID:-}" ]] && kill -0 "${BAG_PID}" 2>/dev/null; then
    kill "${BAG_PID}" 2>/dev/null || true
    wait "${BAG_PID}" 2>/dev/null || true
  fi

  if [[ -n "${RVIZ_PID:-}" ]] && kill -0 "${RVIZ_PID}" 2>/dev/null; then
    kill "${RVIZ_PID}" 2>/dev/null || true
    wait "${RVIZ_PID}" 2>/dev/null || true
  fi

  exit "${exit_code}"
}

trap cleanup EXIT INT TERM

echo "rosbag: ${BAG_PATH}"
echo "rviz config: ${RVIZ_CONFIG}"

ros2 bag play --loop "${BAG_PATH}" &
BAG_PID=$!

rviz2 --display-config "${RVIZ_CONFIG}" &
RVIZ_PID=$!

wait "${RVIZ_PID}"
