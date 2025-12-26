#!/bin/bash
set -e

# PID tracking
API_PID=""
WORKER_PID=""

# Cleanup function for graceful shutdown
cleanup() {
    echo "Shutting down services..."

    # Stop API server if running
    if [ -n "$API_PID" ] && kill -0 "$API_PID" 2>/dev/null; then
        echo "Stopping API server (PID: $API_PID)..."
        kill -TERM "$API_PID" 2>/dev/null || true
        wait "$API_PID" 2>/dev/null || true
    fi

    # Stop worker if running
    if [ -n "$WORKER_PID" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        echo "Stopping detection worker (PID: $WORKER_PID)..."
        kill -TERM "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi

    echo "Shutdown complete"
    exit 0
}

# Register signal handlers
trap cleanup EXIT TERM INT QUIT

# Start API server in background if DEBUG_STREAM_ENABLED
if [ "${DEBUG_STREAM_ENABLED:-false}" = "true" ]; then
    echo "Starting API server with debug stream on port ${DEBUG_STREAM_PORT:-8001}..."
    python -m uvicorn src.api.roi_config_api:app \
        --host 0.0.0.0 \
        --port "${DEBUG_STREAM_PORT:-8001}" \
        --log-level info &
    API_PID=$!
    echo "API server started with PID: $API_PID"

    # Give API server time to start
    sleep 2

    # Check if API server is still running
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "ERROR: API server failed to start"
        exit 1
    fi
fi

# Start detection worker
echo "Starting detection worker..."
python -m src.workers.detection_worker "$@" &
WORKER_PID=$!
echo "Detection worker started with PID: $WORKER_PID"

# Wait for worker to finish (main process)
wait "$WORKER_PID"
WORKER_EXIT_CODE=$?

echo "Detection worker exited with code: $WORKER_EXIT_CODE"
exit $WORKER_EXIT_CODE
