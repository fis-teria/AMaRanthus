#!/usr/bin/env bash
set -euo pipefail

PORT="${1:-8765}"

SCRIPT_PATH="$(readlink -f "$0")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"

ADB_BIN="${ADB_BIN:-}"
if [[ -z "${ADB_BIN}" ]]; then
    for candidate in \
        "$(command -v adb || true)" \
        "${PWD}/Data/tools/platform-tools/adb" \
        "${PWD}/../Data/tools/platform-tools/adb" \
        "${SCRIPT_DIR}/../../../../../Data/tools/platform-tools/adb" \
        "/home/graneple/Helianthus/Data/tools/platform-tools/adb"
    do
        if [[ -n "${candidate}" && -x "${candidate}" ]]; then
            ADB_BIN="${candidate}"
            break
        fi
    done
fi

if [[ -z "${ADB_BIN}" ]]; then
    echo "[ERROR] adb is not installed." >&2
    echo "[ERROR] Install Android platform-tools or set ADB_BIN=/path/to/adb." >&2
    exit 1
fi

devices_output="$("${ADB_BIN}" devices)"
echo "${devices_output}"

device_state="$(printf '%s\n' "${devices_output}" | awk 'NR > 1 && NF >= 2 {print $2; exit}')"
if [[ -z "${device_state}" ]]; then
    cat >&2 <<EOF
[ERROR] No Android device is visible to adb.
[HINT] Enable Developer options -> USB debugging on the phone, reconnect USB, and accept the RSA prompt.
[HINT] If the prompt does not appear, switch the USB mode to File transfer once and run this command again.
EOF
    exit 1
fi
if [[ "${device_state}" != "device" ]]; then
    cat >&2 <<EOF
[ERROR] adb can see the phone, but it is not authorized yet: ${device_state}
[HINT] Check the phone screen and allow USB debugging for this PC.
EOF
    exit 1
fi

"${ADB_BIN}" reverse "tcp:${PORT}" "tcp:${PORT}"

cat <<EOF
[INFO] adb reverse is active.
[INFO] Open this URL on the Android phone:

  http://localhost:${PORT}/

[INFO] Android Chrome treats localhost as a secure context, so geolocation can work without HTTPS.
EOF
