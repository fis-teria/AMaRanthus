#!/bin/bash
set -eEuo pipefail

TTS_BACKEND_PID=""

cleanup_tts_backend() {
    if [[ -n "${TTS_BACKEND_PID}" ]]; then
        if kill -0 "${TTS_BACKEND_PID}" >/dev/null 2>&1; then
            echo "[INFO] Stopping Irodori-TTS-Lite backend (pid=${TTS_BACKEND_PID})..."
            kill "${TTS_BACKEND_PID}" >/dev/null 2>&1 || true
        fi
        wait "${TTS_BACKEND_PID}" >/dev/null 2>&1 || true
    fi
}

pause_on_error() {
    local status=$?
    cleanup_tts_backend
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
ROS_CAMERA_COMPRESSED_OVERLAY_TOPIC="${ROS_CAMERA_COMPRESSED_OVERLAY_TOPIC:-/shadow/e2e/overlay_image/compressed}"
ROS_CAMERA_OVERLAY_TIMEOUT_SEC="${ROS_CAMERA_OVERLAY_TIMEOUT_SEC:-1.0}"
ROS_CAMERA_RAW_OVERLAY_FALLBACK="${ROS_CAMERA_RAW_OVERLAY_FALLBACK:-0}"
ROS_CAMERA_RAW_FALLBACK="${ROS_CAMERA_RAW_FALLBACK:-0}"
ROS_CAMERA_DISPLAY_MAX_EDGE_PX="${ROS_CAMERA_DISPLAY_MAX_EDGE_PX:-1280}"
ROS_CAMERA_INFO_TOPIC="${ROS_CAMERA_INFO_TOPIC:-/sensing/camera/camera0/camera_info}"
ROS_POINTCLOUD_TOPIC="${ROS_POINTCLOUD_TOPIC:-/cloud_registered}"
ROS_POINTCLOUD_ODOM_TOPIC="${ROS_POINTCLOUD_ODOM_TOPIC:-/Odometry}"
ROS_POINTCLOUD_STABILIZE_WITH_ODOM="${ROS_POINTCLOUD_STABILIZE_WITH_ODOM:-1}"
ROS_POINTCLOUD_MAX_POINTS="${ROS_POINTCLOUD_MAX_POINTS:-2500}"
ROS_POINTCLOUD_MIN_UPDATE_INTERVAL_SEC="${ROS_POINTCLOUD_MIN_UPDATE_INTERVAL_SEC:-0.2}"
ROS_POINTCLOUD_MAX_RANGE_M="${ROS_POINTCLOUD_MAX_RANGE_M:-80.0}"
ROS_POINTCLOUD_Z_MIN_M="${ROS_POINTCLOUD_Z_MIN_M:--3.0}"
ROS_POINTCLOUD_Z_MAX_M="${ROS_POINTCLOUD_Z_MAX_M:-3.0}"
ROS_ROUTE_POINTCLOUD_TOPIC="${ROS_ROUTE_POINTCLOUD_TOPIC:-/shadow/route/pointcloud}"
ROS_ROUTE_POINTCLOUD_MAX_POINTS="${ROS_ROUTE_POINTCLOUD_MAX_POINTS:-1500}"
ROS_ROUTE_PATH_TOPIC="${ROS_ROUTE_PATH_TOPIC:-/shadow/route/gui_path}"
ROS_E2E_PATH_TOPIC="${ROS_E2E_PATH_TOPIC:-/shadow/e2e/path}"
ROS_SCAN_TOPIC="${ROS_SCAN_TOPIC:-/scan}"
ROS_LANE_TOPIC="${ROS_LANE_TOPIC:-/livox/lane_detection/scan}"
ROS_OBJECTS_TOPIC="${ROS_OBJECTS_TOPIC:-/livox/lane_detection/objects}"
ROS_SPEED_TOPIC="${ROS_SPEED_TOPIC:-/vehicle/speed_kmh}"
ROS_MODE_TOPIC="${ROS_MODE_TOPIC:-/vehicle/mode}"
ROS_GPS_TOPIC="${ROS_GPS_TOPIC:-/vehicle/gps_status}"
ROS_PHONE_FIX_TOPIC="${ROS_PHONE_FIX_TOPIC:-/phone/gps/fix}"
ROS_PHONE_GOAL_TOPIC="${ROS_PHONE_GOAL_TOPIC:-/phone/route/goal}"
ROS_PHONE_STATUS_TOPIC="${ROS_PHONE_STATUS_TOPIC:-/phone/location/status}"
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
ROSBAG_RECORD_DIR="${ROSBAG_RECORD_DIR:-${HELIANTHUS_DIR}/Data/gui_rosbags}"
ROSBAG_RECORD_EXTRA_TOPICS="${ROSBAG_RECORD_EXTRA_TOPICS:-}"
ROSBAG_RECORD_PRESET="${ROSBAG_RECORD_PRESET:-E2E input}"
GPU_MONITOR_INTERVAL_SEC="${GPU_MONITOR_INTERVAL_SEC:-1.0}"
DISABLE_GPU_MONITOR="${DISABLE_GPU_MONITOR:-0}"
ENABLE_IRODORI_TTS_BACKEND="${ENABLE_IRODORI_TTS_BACKEND:-1}"
IRODORI_TTS_LITE_DIR="${IRODORI_TTS_LITE_DIR:-${AMARANTHUS_DIR}/src/tts/irodori_tts_lite}"
IRODORI_TTS_BACKEND_HOST="${IRODORI_TTS_BACKEND_HOST:-127.0.0.1}"
IRODORI_TTS_BACKEND_PORT="${IRODORI_TTS_BACKEND_PORT:-8766}"
IRODORI_TTS_CONFIG="${IRODORI_TTS_CONFIG:-${IRODORI_TTS_LITE_DIR}/config.yaml}"
IRODORI_TTS_BACKEND_WAIT_SEC="${IRODORI_TTS_BACKEND_WAIT_SEC:-5}"
IRODORI_TTS_BACKEND_LOG_DIR="${IRODORI_TTS_BACKEND_LOG_DIR:-${IRODORI_TTS_LITE_DIR}/runtime/logs}"
ENABLE_ROUTE_VOICE_GUIDANCE="${ENABLE_ROUTE_VOICE_GUIDANCE:-1}"
ROUTE_VOICE_PREANNOUNCE_DISTANCE_M="${ROUTE_VOICE_PREANNOUNCE_DISTANCE_M:-300.0}"

export PYTHONUNBUFFERED

tts_backend_health_url() {
    printf 'http://%s:%s/health' "${IRODORI_TTS_BACKEND_HOST}" "${IRODORI_TTS_BACKEND_PORT}"
}

tts_backend_is_ready() {
    local health_url
    health_url="$(tts_backend_health_url)"
    python3 - "${health_url}" <<'PY' >/dev/null 2>&1
import json
import sys
from urllib.request import urlopen

try:
    with urlopen(sys.argv[1], timeout=0.5) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raise SystemExit(0 if payload.get("ok") else 1)
except Exception:
    raise SystemExit(1)
PY
}

wait_for_tts_backend() {
    local deadline
    deadline=$((SECONDS + IRODORI_TTS_BACKEND_WAIT_SEC))
    while (( SECONDS <= deadline )); do
        if tts_backend_is_ready; then
            return 0
        fi
        sleep 0.25
    done
    return 1
}

start_tts_backend() {
    if [[ "${ENABLE_IRODORI_TTS_BACKEND}" != "1" ]]; then
        echo "[INFO] Irodori-TTS-Lite backend auto-start is disabled."
        return 0
    fi

    if tts_backend_is_ready; then
        echo "[INFO] Irodori-TTS-Lite backend is already running at $(tts_backend_health_url)."
        return 0
    fi

    if [[ ! -x "${IRODORI_TTS_LITE_DIR}/run_backend_server.sh" ]]; then
        echo "[WARN] Irodori-TTS-Lite backend script was not found: ${IRODORI_TTS_LITE_DIR}/run_backend_server.sh" >&2
        return 0
    fi

    if [[ ! -x "${IRODORI_TTS_LITE_DIR}/.venv/bin/python" ]]; then
        echo "[WARN] Irodori-TTS-Lite uv environment is not ready: ${IRODORI_TTS_LITE_DIR}/.venv" >&2
        echo "[WARN] Run ${IRODORI_TTS_LITE_DIR}/setup.sh before using TTS synthesis." >&2
        return 0
    fi

    mkdir -p "${IRODORI_TTS_BACKEND_LOG_DIR}"
    local log_file
    log_file="${IRODORI_TTS_BACKEND_LOG_DIR}/backend.log"
    echo "[INFO] Starting Irodori-TTS-Lite backend at $(tts_backend_health_url)..."
    (
        cd "${IRODORI_TTS_LITE_DIR}"
        exec ./run_backend_server.sh \
            --config "${IRODORI_TTS_CONFIG}" \
            --host "${IRODORI_TTS_BACKEND_HOST}" \
            --port "${IRODORI_TTS_BACKEND_PORT}"
    ) >"${log_file}" 2>&1 &
    TTS_BACKEND_PID=$!

    if wait_for_tts_backend; then
        echo "[INFO] Irodori-TTS-Lite backend is ready (pid=${TTS_BACKEND_PID})."
    else
        echo "[WARN] Irodori-TTS-Lite backend did not become ready within ${IRODORI_TTS_BACKEND_WAIT_SEC}s." >&2
        echo "[WARN] Backend log: ${log_file}" >&2
    fi
}

for setup_file in \
    "${HELIANTHUS_DIR}/install/setup.bash" \
    "${AMARANTHUS_DIR}/install/setup.bash"
do
    if [[ -f "${setup_file}" ]]; then
        source_setup "${setup_file}"
    fi
done

cd "${SCRIPT_DIR}"

start_tts_backend

echo "[INFO] Launching AMaRanthus GUI (${DATA_SOURCE})..."

EXTRA_ARGS=()
if [[ "${DISABLE_GPU_MONITOR}" == "1" ]]; then
    EXTRA_ARGS+=(--disable-gpu-monitor)
fi
if [[ "${ROS_CAMERA_RAW_FALLBACK}" != "1" ]]; then
    EXTRA_ARGS+=(--no-ros-camera-raw-fallback)
fi
if [[ "${ROS_CAMERA_RAW_OVERLAY_FALLBACK}" != "1" ]]; then
    EXTRA_ARGS+=(--no-ros-camera-raw-overlay-fallback)
fi
if [[ "${ROS_POINTCLOUD_STABILIZE_WITH_ODOM}" != "1" ]]; then
    EXTRA_ARGS+=(--no-ros-pointcloud-stabilize-with-odom)
fi
if [[ "${ENABLE_ROUTE_VOICE_GUIDANCE}" != "1" ]]; then
    EXTRA_ARGS+=(--disable-route-voice-guidance)
fi
if [[ -n "${ROSBAG_RECORD_EXTRA_TOPICS}" ]]; then
    read -r -a rosbag_extra_topics <<< "${ROSBAG_RECORD_EXTRA_TOPICS}"
    for topic in "${rosbag_extra_topics[@]}"; do
        EXTRA_ARGS+=(--rosbag-record-topic "${topic}")
    done
fi

uv run main.py \
    --data-source "${DATA_SOURCE}" \
    --ui-config "${UI_CONFIG}" \
    --theme "${GUI_THEME}" \
    --ros-camera-image-topic "${ROS_CAMERA_IMAGE_TOPIC}" \
    --ros-camera-overlay-topic "${ROS_CAMERA_OVERLAY_TOPIC}" \
    --ros-camera-compressed-overlay-topic "${ROS_CAMERA_COMPRESSED_OVERLAY_TOPIC}" \
    --ros-camera-overlay-timeout-sec "${ROS_CAMERA_OVERLAY_TIMEOUT_SEC}" \
    --ros-camera-display-max-edge-px "${ROS_CAMERA_DISPLAY_MAX_EDGE_PX}" \
    --ros-camera-info-topic "${ROS_CAMERA_INFO_TOPIC}" \
    --ros-pointcloud-topic "${ROS_POINTCLOUD_TOPIC}" \
    --ros-pointcloud-odom-topic "${ROS_POINTCLOUD_ODOM_TOPIC}" \
    --ros-pointcloud-max-points "${ROS_POINTCLOUD_MAX_POINTS}" \
    --ros-pointcloud-min-update-interval-sec "${ROS_POINTCLOUD_MIN_UPDATE_INTERVAL_SEC}" \
    --ros-pointcloud-max-range-m "${ROS_POINTCLOUD_MAX_RANGE_M}" \
    --ros-pointcloud-z-min-m "${ROS_POINTCLOUD_Z_MIN_M}" \
    --ros-pointcloud-z-max-m "${ROS_POINTCLOUD_Z_MAX_M}" \
    --ros-route-pointcloud-topic "${ROS_ROUTE_POINTCLOUD_TOPIC}" \
    --ros-route-pointcloud-max-points "${ROS_ROUTE_POINTCLOUD_MAX_POINTS}" \
    --ros-route-path-topic "${ROS_ROUTE_PATH_TOPIC}" \
    --ros-e2e-path-topic "${ROS_E2E_PATH_TOPIC}" \
    --ros-scan-topic "${ROS_SCAN_TOPIC}" \
    --ros-lane-topic "${ROS_LANE_TOPIC}" \
    --ros-objects-topic "${ROS_OBJECTS_TOPIC}" \
    --ros-speed-topic "${ROS_SPEED_TOPIC}" \
    --ros-mode-topic "${ROS_MODE_TOPIC}" \
    --ros-gps-topic "${ROS_GPS_TOPIC}" \
    --ros-phone-fix-topic "${ROS_PHONE_FIX_TOPIC}" \
    --ros-phone-goal-topic "${ROS_PHONE_GOAL_TOPIC}" \
    --ros-phone-status-topic "${ROS_PHONE_STATUS_TOPIC}" \
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
    --rosbag-record-dir "${ROSBAG_RECORD_DIR}" \
    --rosbag-record-preset "${ROSBAG_RECORD_PRESET}" \
    --tts-backend-url "$(tts_backend_health_url | sed 's#/health$##')" \
    --route-voice-preannounce-distance-m "${ROUTE_VOICE_PREANNOUNCE_DISTANCE_M}" \
    --gpu-monitor-interval-sec "${GPU_MONITOR_INTERVAL_SEC}" \
    "${EXTRA_ARGS[@]}" \
    "$@"
