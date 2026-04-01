#!/bin/bash
set -eEuo pipefail

pause_on_error() {
    local status=$?
    if [[ ${status} -ne 0 ]]; then
        echo
        echo "[ERROR] run_gui.sh failed with exit code ${status}."
        if [[ -t 0 && -t 1 && "${AMARANTHUS_NO_ERROR_PAUSE:-0}" != "1" ]]; then
            read -r -p "Press Enter to close..." _
        fi
    fi
}

trap pause_on_error EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DATA_SOURCE="${DATA_SOURCE:-ros2}"
UI_CONFIG="${UI_CONFIG:-${SCRIPT_DIR}/config/ui.yaml}"
ROS_SCAN_TOPIC="${ROS_SCAN_TOPIC:-/scan}"
ROS_LANE_TOPIC="${ROS_LANE_TOPIC:-/livox/lane_detection/scan}"
ROS_OBJECTS_TOPIC="${ROS_OBJECTS_TOPIC:-/livox/lane_detection/objects}"
ROS_SPEED_TOPIC="${ROS_SPEED_TOPIC:-/vehicle/speed_kmh}"
ROS_MODE_TOPIC="${ROS_MODE_TOPIC:-/vehicle/mode}"
ROS_GPS_TOPIC="${ROS_GPS_TOPIC:-/vehicle/gps_status}"

if [[ -f "${WORKSPACE_DIR}/install/setup.bash" ]]; then
    # shellcheck disable=SC1091
    source "${WORKSPACE_DIR}/install/setup.bash"
fi

cd "${SCRIPT_DIR}"

exec uv run main.py \
    --data-source "${DATA_SOURCE}" \
    --ui-config "${UI_CONFIG}" \
    --ros-scan-topic "${ROS_SCAN_TOPIC}" \
    --ros-lane-topic "${ROS_LANE_TOPIC}" \
    --ros-objects-topic "${ROS_OBJECTS_TOPIC}" \
    --ros-speed-topic "${ROS_SPEED_TOPIC}" \
    --ros-mode-topic "${ROS_MODE_TOPIC}" \
    --ros-gps-topic "${ROS_GPS_TOPIC}" \
    "$@"
