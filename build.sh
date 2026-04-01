#!/bin/bash
set -eE

pause_on_error() {
    local status=$?
    if [[ ${status} -ne 0 ]]; then
        echo
        echo "[ERROR] build.sh failed with exit code ${status}."
        if [[ -t 0 && -t 1 && "${AMARANTHUS_NO_ERROR_PAUSE:-0}" != "1" ]]; then
            read -r -p "Press Enter to close..." _
        fi
    fi
}

trap pause_on_error EXIT

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Memory-safe defaults for large colcon workspaces.
# These can be overridden from the environment when you want a faster build.
export AMARANTHUS_COLCON_PARALLEL_WORKERS="${AMARANTHUS_COLCON_PARALLEL_WORKERS:-1}"
export AMARANTHUS_BUILD_JOBS="${AMARANTHUS_BUILD_JOBS:-}"
export AMARANTHUS_BUILD_LOAD_LIMIT="${AMARANTHUS_BUILD_LOAD_LIMIT:-}"

bash "${SCRIPT_DIR}/src/drivers/livox_ros_driver2/build.sh" humble
