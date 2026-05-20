#!/usr/bin/env bash
set -euo pipefail

PORT="${PHONE_LOCATION_BRIDGE_PORT:-${1:-8765}}"
WAIT_TIMEOUT_SEC="${PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC:-30}"

SCRIPT_PATH="$(readlink -f "$0")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"

ADB_BIN="${ADB_BIN:-}"
if [[ -z "${ADB_BIN}" ]]; then
    for candidate in \
        "$(command -v adb || true)" \
        "${PWD}/Data/tools/platform-tools/adb" \
        "${PWD}/../Data/tools/platform-tools/adb" \
        "${SCRIPT_DIR}/../../../../../Data/tools/platform-tools/adb" \
        "/home/graneple/Helianthus/Data/tools/platform-tools/adb" \
        "/home/graneple/git/Helianthus/Data/tools/platform-tools/adb"
    do
        if [[ -n "${candidate}" && -x "${candidate}" ]]; then
            ADB_BIN="${candidate}"
            break
        fi
    done
fi

if [[ -z "${ADB_BIN}" ]]; then
    echo "[ERROR] adb is not installed. Install Android platform-tools or set ADB_BIN." >&2
    exit 1
fi

echo "[INFO] Starting adb server with ${ADB_BIN}"
"${ADB_BIN}" start-server

echo "[INFO] Waiting for Android device for up to ${WAIT_TIMEOUT_SEC}s"
if ! timeout "${WAIT_TIMEOUT_SEC}" "${ADB_BIN}" wait-for-device; then
    echo "[ERROR] adb device did not appear before timeout." >&2
    exit 1
fi

devices_output="$("${ADB_BIN}" devices)"
echo "${devices_output}"

device_state="$(printf '%s\n' "${devices_output}" | awk 'NR > 1 && NF >= 2 {print $2; exit}')"
if [[ "${device_state}" != "device" ]]; then
    cat >&2 <<EOF
[ERROR] adb can see the phone, but it is not authorized yet: ${device_state:-not_found}
[HINT] Enable USB debugging and allow this PC on the phone screen.
EOF
    exit 1
fi

echo "[INFO] Applying adb reverse tcp:${PORT} -> tcp:${PORT}"
"${ADB_BIN}" reverse "tcp:${PORT}" "tcp:${PORT}"

cat <<EOF
[INFO] adb reverse is active.
[INFO] Open this URL on the Android phone:

  http://localhost:${PORT}/
EOF
