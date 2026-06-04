#!/usr/bin/env bash
set -euo pipefail

LIMIT="${BATTERY_CHARGE_LIMIT_PERCENT:-50}"
WAIT_SEC="${BATTERY_CHARGE_LIMIT_WAIT_SEC:-60}"
THRESHOLD_PATH="${BATTERY_CHARGE_THRESHOLD_PATH:-}"

if ! [[ "${LIMIT}" =~ ^[0-9]+$ ]] || (( LIMIT < 1 || LIMIT > 100 )); then
  echo "[ERROR] BATTERY_CHARGE_LIMIT_PERCENT must be an integer from 1 to 100: ${LIMIT}" >&2
  exit 2
fi

deadline=$((SECONDS + WAIT_SEC))
thresholds=()

find_thresholds() {
  thresholds=()
  if [[ -n "${THRESHOLD_PATH}" ]]; then
    if [[ -e "${THRESHOLD_PATH}" ]]; then
      thresholds+=("${THRESHOLD_PATH}")
    fi
    return
  fi

  local path
  for path in /sys/class/power_supply/BAT*/charge_control_end_threshold; do
    if [[ -e "${path}" ]]; then
      thresholds+=("${path}")
    fi
  done
}

while true; do
  find_thresholds
  if (( ${#thresholds[@]} > 0 )); then
    break
  fi
  if (( SECONDS >= deadline )); then
    echo "[WARN] No battery charge threshold file found. Nothing to apply." >&2
    exit 0
  fi
  sleep 1
done

for threshold in "${thresholds[@]}"; do
  echo "${LIMIT}" > "${threshold}"
  applied="$(cat "${threshold}" 2>/dev/null || true)"
  echo "[INFO] Set ${threshold} to ${applied:-${LIMIT}}"
done
