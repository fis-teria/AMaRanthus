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

source_setup() {
    local setup_file="$1"
    local source_log
    local status

    source_log="$(mktemp)"
    set +e +u
    # shellcheck disable=SC1090
    source "${setup_file}" >"${source_log}" 2>&1
    status=$?
    set -e -u

    if [[ ${status} -ne 0 ]]; then
        cat "${source_log}" >&2
        rm -f "${source_log}"
        return "${status}"
    fi

    grep -vE '^not found: ".*/(autoware_tensorrt_common|autoware_tensorrt_classifier|autoware_tensorrt_plugins|bevdet_vendor)/share/.*/local_setup\.bash"$' "${source_log}" >&2 || true
    rm -f "${source_log}"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AMARANTHUS_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HELIANTHUS_DIR="$(cd "${AMARANTHUS_DIR}/.." && pwd)"

DATA_SOURCE="${DATA_SOURCE:-ros2}"
UI_CONFIG="${UI_CONFIG:-${SCRIPT_DIR}/config/ui.yaml}"
GUI_THEME="${GUI_THEME:-dark}"
PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
ROS_CAMERA_IMAGE_TOPIC="${ROS_CAMERA_IMAGE_TOPIC:-/sensing/camera/camera0/image_rect_color}"
ROS_CAMERA_OVERLAY_TOPIC="${ROS_CAMERA_OVERLAY_TOPIC:-/shadow/e2e/overlay_image}"
ROS_CAMERA_OVERLAY_TIMEOUT_SEC="${ROS_CAMERA_OVERLAY_TIMEOUT_SEC:-1.0}"
ROS_CAMERA_DISPLAY_MAX_EDGE_PX="${ROS_CAMERA_DISPLAY_MAX_EDGE_PX:-1280}"
ROS_CAMERA_INFO_TOPIC="${ROS_CAMERA_INFO_TOPIC:-/sensing/camera/camera0/camera_info}"
ROS_POINTCLOUD_TOPIC="${ROS_POINTCLOUD_TOPIC:-/livox/lidar}"
ROS_SCAN_TOPIC="${ROS_SCAN_TOPIC:-/scan}"
ROS_LANE_TOPIC="${ROS_LANE_TOPIC:-/livox/lane_detection/scan}"
ROS_OBJECTS_TOPIC="${ROS_OBJECTS_TOPIC:-/livox/lane_detection/objects}"
ROS_SPEED_TOPIC="${ROS_SPEED_TOPIC:-/vehicle/speed_kmh}"
ROS_MODE_TOPIC="${ROS_MODE_TOPIC:-/vehicle/mode}"
ROS_GPS_TOPIC="${ROS_GPS_TOPIC:-/vehicle/gps_status}"
ROS_SHADOW_EGO_SPEED_TOPIC="${ROS_SHADOW_EGO_SPEED_TOPIC:-/shadow/ego/speed}"
ROS_SHADOW_EGO_YAW_RATE_TOPIC="${ROS_SHADOW_EGO_YAW_RATE_TOPIC:-/shadow/ego/yaw_rate}"
ROS_SHADOW_EGO_CURVATURE_TOPIC="${ROS_SHADOW_EGO_CURVATURE_TOPIC:-/shadow/ego/curvature}"
ROS_SHADOW_VIRTUAL_STEERING_TOPIC="${ROS_SHADOW_VIRTUAL_STEERING_TOPIC:-/shadow/virtual/steering_proxy}"
ROS_SHADOW_VIRTUAL_CURVATURE_TOPIC="${ROS_SHADOW_VIRTUAL_CURVATURE_TOPIC:-/shadow/virtual/curvature}"
ROS_SHADOW_VIRTUAL_WARNING_TOPIC="${ROS_SHADOW_VIRTUAL_WARNING_TOPIC:-/shadow/virtual/warning_score}"
ROS_SHADOW_DRIVER_STEERING_TOPIC="${ROS_SHADOW_DRIVER_STEERING_TOPIC:-/shadow/metrics/driver_steering_proxy}"
ROS_SHADOW_STEERING_DELTA_TOPIC="${ROS_SHADOW_STEERING_DELTA_TOPIC:-/shadow/metrics/steering_delta}"
ROS_SHADOW_CURVATURE_DELTA_TOPIC="${ROS_SHADOW_CURVATURE_DELTA_TOPIC:-/shadow/metrics/curvature_delta}"
ROS_SHADOW_INTERVENTION_SCORE_TOPIC="${ROS_SHADOW_INTERVENTION_SCORE_TOPIC:-/shadow/metrics/intervention_score}"
ROS_SHADOW_SUMMARY_TOPIC="${ROS_SHADOW_SUMMARY_TOPIC:-/shadow/metrics/summary}"
GPU_MONITOR_INTERVAL_SEC="${GPU_MONITOR_INTERVAL_SEC:-1.0}"
DISABLE_GPU_MONITOR="${DISABLE_GPU_MONITOR:-0}"

export PYTHONUNBUFFERED

for setup_file in \
    "${HELIANTHUS_DIR}/install/setup.bash" \
    "${AMARANTHUS_DIR}/install/setup.bash"
do
    if [[ -f "${setup_file}" ]]; then
        source_setup "${setup_file}"
    fi
done

cd "${SCRIPT_DIR}"

echo "[INFO] Launching AMaRanthus GUI (${DATA_SOURCE})..."

EXTRA_ARGS=()
if [[ "${DISABLE_GPU_MONITOR}" == "1" ]]; then
    EXTRA_ARGS+=(--disable-gpu-monitor)
fi

exec uv run main.py \
    --data-source "${DATA_SOURCE}" \
    --ui-config "${UI_CONFIG}" \
    --theme "${GUI_THEME}" \
    --ros-camera-image-topic "${ROS_CAMERA_IMAGE_TOPIC}" \
    --ros-camera-overlay-topic "${ROS_CAMERA_OVERLAY_TOPIC}" \
    --ros-camera-overlay-timeout-sec "${ROS_CAMERA_OVERLAY_TIMEOUT_SEC}" \
    --ros-camera-display-max-edge-px "${ROS_CAMERA_DISPLAY_MAX_EDGE_PX}" \
    --ros-camera-info-topic "${ROS_CAMERA_INFO_TOPIC}" \
    --ros-pointcloud-topic "${ROS_POINTCLOUD_TOPIC}" \
    --ros-scan-topic "${ROS_SCAN_TOPIC}" \
    --ros-lane-topic "${ROS_LANE_TOPIC}" \
    --ros-objects-topic "${ROS_OBJECTS_TOPIC}" \
    --ros-speed-topic "${ROS_SPEED_TOPIC}" \
    --ros-mode-topic "${ROS_MODE_TOPIC}" \
    --ros-gps-topic "${ROS_GPS_TOPIC}" \
    --ros-shadow-ego-speed-topic "${ROS_SHADOW_EGO_SPEED_TOPIC}" \
    --ros-shadow-ego-yaw-rate-topic "${ROS_SHADOW_EGO_YAW_RATE_TOPIC}" \
    --ros-shadow-ego-curvature-topic "${ROS_SHADOW_EGO_CURVATURE_TOPIC}" \
    --ros-shadow-virtual-steering-topic "${ROS_SHADOW_VIRTUAL_STEERING_TOPIC}" \
    --ros-shadow-virtual-curvature-topic "${ROS_SHADOW_VIRTUAL_CURVATURE_TOPIC}" \
    --ros-shadow-virtual-warning-topic "${ROS_SHADOW_VIRTUAL_WARNING_TOPIC}" \
    --ros-shadow-driver-steering-topic "${ROS_SHADOW_DRIVER_STEERING_TOPIC}" \
    --ros-shadow-steering-delta-topic "${ROS_SHADOW_STEERING_DELTA_TOPIC}" \
    --ros-shadow-curvature-delta-topic "${ROS_SHADOW_CURVATURE_DELTA_TOPIC}" \
    --ros-shadow-intervention-score-topic "${ROS_SHADOW_INTERVENTION_SCORE_TOPIC}" \
    --ros-shadow-summary-topic "${ROS_SHADOW_SUMMARY_TOPIC}" \
    --gpu-monitor-interval-sec "${GPU_MONITOR_INTERVAL_SEC}" \
    "${EXTRA_ARGS[@]}" \
    "$@"
