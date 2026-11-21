#!/bin/sh
# mock_qnx_service.sh - Safe dummy user-space background service for fault-isolation testing
# Demonstrates QNX microkernel resilience: killing this user-space daemon leaves procnto unaffected.

PID=$$
LOG_FILE="/tmp/mock_qnx_service.log"
RUN_FLAG="/tmp/mock_qnx_service.run"

echo "Starting mock_qnx_service (PID: ${PID}) at $(date)" > "${LOG_FILE}"
echo "${PID}" > "${RUN_FLAG}"

cleanup() {
    echo "mock_qnx_service caught termination signal, exiting cleanly." >> "${LOG_FILE}"
    rm -f "${RUN_FLAG}"
    exit 0
}

trap cleanup INT TERM HUP

COUNTER=0
while [ -f "${RUN_FLAG}" ]; do
    COUNTER=$((COUNTER + 1))
    echo "[$(date)] mock_qnx_service running heartbeat tick ${COUNTER}" >> "${LOG_FILE}"
    # Sleep 2 seconds
    sleep 2
done

cleanup
