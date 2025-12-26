#!/bin/bash
set -e

# Start API server in background if DEBUG_STREAM_ENABLED
if [ "${DEBUG_STREAM_ENABLED:-false}" = "true" ]; then
    echo "Starting API server with debug stream on port ${DEBUG_STREAM_PORT:-8001}..."
    python -m uvicorn src.api.roi_config_api:app \
        --host 0.0.0.0 \
        --port "${DEBUG_STREAM_PORT:-8001}" \
        --log-level info &
    API_PID=$!
    echo "API server started with PID: $API_PID"
fi

# Start detection worker
echo "Starting detection worker..."
exec python -m src.workers.detection_worker "$@"
