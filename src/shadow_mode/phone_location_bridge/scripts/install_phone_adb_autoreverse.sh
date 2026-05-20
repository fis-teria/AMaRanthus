#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=0
SKIP_UDEV="${PHONE_LOCATION_SKIP_UDEV:-0}"
for arg in "$@"; do
    case "${arg}" in
        --dry-run)
            DRY_RUN=1
            ;;
        --skip-udev|--user-only)
            SKIP_UDEV=1
            ;;
        -h|--help)
            cat <<EOF
Usage: install_phone_adb_autoreverse.sh [--dry-run] [--skip-udev]

Installs:
  - ~/.config/systemd/user/phone-location-adb-reverse.service
  - /etc/udev/rules.d/52-phone-location-adb-autoreverse.rules

Environment:
  PHONE_LOCATION_ADB_USER        target desktop user (default: current user)
  PHONE_LOCATION_ANDROID_VENDOR_ID Android USB vendor id (default: 0fce for Sony)
  PHONE_LOCATION_BRIDGE_PORT     phone_location_bridge HTTP port (default: 8765)
  PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC adb wait timeout (default: 30)
  PHONE_LOCATION_SKIP_UDEV       install only the user service (default: 0)
EOF
            exit 0
            ;;
        *)
            echo "[ERROR] Unknown argument: ${arg}" >&2
            exit 2
            ;;
    esac
done

SCRIPT_PATH="$(readlink -f "$0")"
SCRIPT_DIR="$(cd "$(dirname "${SCRIPT_PATH}")" && pwd)"
SOURCE_PACKAGE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
INSTALL_SHARE_DIR="$(cd "${SCRIPT_DIR}/../.." 2>/dev/null && pwd)/share/phone_location_bridge"

TARGET_USER="${PHONE_LOCATION_ADB_USER:-${SUDO_USER:-${USER}}}"
TARGET_UID="$(id -u "${TARGET_USER}")"
TARGET_GID="$(id -g "${TARGET_USER}")"
TARGET_GROUP="$(id -gn "${TARGET_USER}")"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"

ANDROID_VENDOR_ID="${PHONE_LOCATION_ANDROID_VENDOR_ID:-0fce}"
PHONE_LOCATION_BRIDGE_PORT="${PHONE_LOCATION_BRIDGE_PORT:-8765}"
PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC="${PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC:-30}"

AUTOREVERSE_SCRIPT="${SCRIPT_DIR}/phone_location_adb_autoreverse.sh"
SERVICE_TEMPLATE=""
UDEV_TEMPLATE=""
for candidate in \
    "${SOURCE_PACKAGE_DIR}/systemd/phone-location-adb-reverse.service.in" \
    "${INSTALL_SHARE_DIR}/systemd/phone-location-adb-reverse.service.in"
do
    if [[ -f "${candidate}" ]]; then
        SERVICE_TEMPLATE="${candidate}"
        break
    fi
done
for candidate in \
    "${SOURCE_PACKAGE_DIR}/udev/52-phone-location-adb-autoreverse.rules.in" \
    "${INSTALL_SHARE_DIR}/udev/52-phone-location-adb-autoreverse.rules.in"
do
    if [[ -f "${candidate}" ]]; then
        UDEV_TEMPLATE="${candidate}"
        break
    fi
done

SERVICE_DIR="${TARGET_HOME}/.config/systemd/user"
SERVICE_PATH="${SERVICE_DIR}/phone-location-adb-reverse.service"
UDEV_RULE_PATH="/etc/udev/rules.d/52-phone-location-adb-autoreverse.rules"

if [[ ! -x "${AUTOREVERSE_SCRIPT}" ]]; then
    echo "[ERROR] Missing executable: ${AUTOREVERSE_SCRIPT}" >&2
    exit 1
fi
if [[ -z "${SERVICE_TEMPLATE}" || -z "${UDEV_TEMPLATE}" ]]; then
    echo "[ERROR] Missing systemd/udev templates near ${SOURCE_PACKAGE_DIR} or ${INSTALL_SHARE_DIR}" >&2
    exit 1
fi

render_template() {
    local template="$1"
    sed \
        -e "s|@PHONE_LOCATION_ADB_AUTOREVERSE_SCRIPT@|${AUTOREVERSE_SCRIPT}|g" \
        -e "s|@PHONE_LOCATION_BRIDGE_PORT@|${PHONE_LOCATION_BRIDGE_PORT}|g" \
        -e "s|@PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC@|${PHONE_LOCATION_ADB_WAIT_TIMEOUT_SEC}|g" \
        -e "s|@ANDROID_VENDOR_ID@|${ANDROID_VENDOR_ID}|g" \
        -e "s|@TARGET_USER@|${TARGET_USER}|g" \
        -e "s|@TARGET_UID@|${TARGET_UID}|g" \
        "${template}"
}

as_root() {
    if [[ "${SKIP_UDEV}" == "1" ]]; then
        echo "[INFO] Skipping root command because SKIP_UDEV=1: $*"
        return 0
    fi
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '[DRY-RUN root] %q' "$@"
        printf '\n'
        return 0
    fi
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
        return
    fi
    if sudo -n true 2>/dev/null; then
        sudo "$@"
        return
    fi
    cat >&2 <<EOF
[ERROR] Root permission is required to install the udev rule.
[HINT] Re-run with sudo, or run this script from a terminal where sudo can prompt:

  sudo PHONE_LOCATION_ADB_USER=${TARGET_USER} PHONE_LOCATION_ANDROID_VENDOR_ID=${ANDROID_VENDOR_ID} ${SCRIPT_PATH}
EOF
    exit 1
}

run_as_target_user() {
    if [[ "${DRY_RUN}" == "1" ]]; then
        printf '[DRY-RUN user] %q' "$@"
        printf '\n'
        return 0
    fi
    if [[ "${EUID}" -eq "${TARGET_UID}" ]]; then
        "$@"
    else
        runuser -u "${TARGET_USER}" -- "$@"
    fi
}

service_tmp="$(mktemp)"
udev_tmp="$(mktemp)"
cleanup() {
    rm -f "${service_tmp}" "${udev_tmp}"
}
trap cleanup EXIT

render_template "${SERVICE_TEMPLATE}" > "${service_tmp}"
render_template "${UDEV_TEMPLATE}" > "${udev_tmp}"

cat <<EOF
[INFO] Target user: ${TARGET_USER} (${TARGET_UID}:${TARGET_GID})
[INFO] Android vendor id: ${ANDROID_VENDOR_ID}
[INFO] Bridge port: ${PHONE_LOCATION_BRIDGE_PORT}
[INFO] Service path: ${SERVICE_PATH}
[INFO] Udev rule path: ${UDEV_RULE_PATH}
EOF

if [[ "${DRY_RUN}" == "1" ]]; then
    echo
    echo "[DRY-RUN] systemd user service:"
    cat "${service_tmp}"
    echo
    echo "[DRY-RUN] udev rule:"
    cat "${udev_tmp}"
    exit 0
fi

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${SERVICE_DIR}"
install -m 0644 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${service_tmp}" "${SERVICE_PATH}"

run_as_target_user env "XDG_RUNTIME_DIR=/run/user/${TARGET_UID}" systemctl --user daemon-reload

if [[ "${SKIP_UDEV}" == "1" ]]; then
    cat <<EOF
[INFO] Installed user service only.
[INFO] To finish USB-plug auto start later, run without --skip-udev:

  sudo PHONE_LOCATION_ADB_USER=${TARGET_USER} PHONE_LOCATION_ANDROID_VENDOR_ID=${ANDROID_VENDOR_ID} ${SCRIPT_PATH}
EOF
else
    as_root install -m 0644 "${udev_tmp}" "${UDEV_RULE_PATH}"
    as_root udevadm control --reload-rules
    as_root udevadm trigger --subsystem-match=usb --action=add
fi

if [[ "${SKIP_UDEV}" == "1" ]]; then
    echo "[INFO] User service is ready; udev auto-start is still pending."
else
    echo "[INFO] Installed phone ADB auto reverse."
fi

cat <<EOF
[INFO] Reconnect the Android phone, then check:

  systemctl --user status phone-location-adb-reverse.service
  journalctl --user -u phone-location-adb-reverse.service -n 50

[INFO] On the phone, open:

  http://localhost:${PHONE_LOCATION_BRIDGE_PORT}/
EOF
