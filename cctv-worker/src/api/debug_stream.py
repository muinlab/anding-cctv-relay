"""FastAPI endpoints for debug MJPEG streaming with YOLO overlay.

This module provides real-time MJPEG streaming with YOLO detection
bounding boxes overlaid on the video feed for debugging purposes.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from typing import Generator, Optional
import threading
import logging
import numpy as np
import cv2
import time
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher


# Logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/debug", tags=["Debug Stream"])

# Constants
STREAM_JPEG_QUALITY = 80
SNAPSHOT_JPEG_QUALITY = 90

# Global detector instance with thread-safe initialization
_detector: Optional[PersonDetector] = None
_detector_lock = threading.Lock()


def get_detector() -> PersonDetector:
    """Get or create YOLO detector instance (thread-safe)."""
    global _detector
    if _detector is None:
        with _detector_lock:
            # Double-checked locking
            if _detector is None:
                logger.info("Initializing YOLO detector...")
                _detector = PersonDetector(
                    model_path=settings.YOLO_MODEL,
                    confidence=settings.CONFIDENCE_THRESHOLD
                )
                logger.info("YOLO detector initialized")
    return _detector


def get_roi_matcher(channel_id: int) -> Optional[ROIMatcher]:
    """Get ROI matcher for channel if config exists."""
    config_path = settings.ROI_CONFIG_DIR / f"channel_{channel_id:02d}.json"
    if config_path.exists():
        return ROIMatcher(config_path)
    return None


def generate_mjpeg_stream(channel_id: int, fps: int = 5) -> Generator[bytes, None, None]:
    """Generate MJPEG stream with YOLO detection overlay.

    Args:
        channel_id: RTSP channel number (1-16)
        fps: Target frames per second (lower = less CPU)

    Yields:
        MJPEG frame bytes
    """
    # Build RTSP URL using settings method (secure)
    rtsp_url = settings.get_rtsp_url(
        host=settings.RTSP_HOST,
        port=settings.RTSP_PORT,
        channel_id=channel_id
    )

    client = RTSPClient(rtsp_url)
    detector = get_detector()
    roi_matcher = get_roi_matcher(channel_id)

    frame_interval = 1.0 / fps
    error_count = 0
    max_errors = 10

    logger.info(f"Starting MJPEG stream for channel {channel_id} at {fps} FPS")

    try:
        if not client.connect(timeout=10):
            logger.error(f"Failed to connect to channel {channel_id}")
            error_frame = create_error_frame(f"Failed to connect to channel {channel_id}")
            _, buffer = cv2.imencode('.jpg', error_frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            return

        while True:
            start_time = time.time()

            try:
                # Capture frame
                frame = client.capture_frame()
                if frame is None:
                    error_count += 1
                    if error_count >= max_errors:
                        logger.error(f"Max errors reached on channel {channel_id}, stopping stream")
                        break

                    # Try to reconnect
                    client.disconnect()
                    if not client.connect(timeout=10):
                        error_frame = create_error_frame("Connection lost, reconnecting...")
                        _, buffer = cv2.imencode('.jpg', error_frame)
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
                        time.sleep(1)
                        continue
                    # Reset error count on successful reconnection
                    error_count = 0
                    logger.info(f"Reconnected to channel {channel_id}")
                    continue

                # Reset error count on successful frame
                error_count = 0

                # Detect persons
                detections = detector.detect_persons(frame)

                # Annotate frame with bounding boxes
                annotated = detector.annotate_image(frame, detections)

                # Add ROI overlay if config exists
                if roi_matcher:
                    occupancy = roi_matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)
                    annotated = roi_matcher.visualize_rois(annotated, occupancy)

                    # Draw person bottom center points
                    for x1, y1, x2, y2, conf in detections:
                        bottom_center = (int((x1 + x2) / 2), int(y2))
                        cv2.circle(annotated, bottom_center, 8, (255, 0, 255), -1)

                # Add debug info overlay
                annotated = add_debug_overlay(annotated, channel_id, len(detections), fps)

                # Encode to JPEG
                _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, STREAM_JPEG_QUALITY])

                # Yield MJPEG frame
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            except cv2.error as e:
                logger.error(f"OpenCV error on channel {channel_id}: {e}")
                error_count += 1
                if error_count >= max_errors:
                    break
                continue

            # Control frame rate
            elapsed = time.time() - start_time
            if elapsed < frame_interval:
                time.sleep(frame_interval - elapsed)

    except GeneratorExit:
        logger.info(f"Stream closed for channel {channel_id}")
    except Exception as e:
        logger.error(f"Unexpected error on channel {channel_id}: {e}", exc_info=True)
        # Yield error frame before exiting
        try:
            error_frame = create_error_frame(f"Error: {str(e)[:30]}")
            _, buffer = cv2.imencode('.jpg', error_frame)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        except Exception as encode_error:
            logger.error(f"Failed to create error frame for channel {channel_id}: {encode_error}")
    finally:
        client.disconnect()
        logger.info(f"Disconnected from channel {channel_id}")


def create_error_frame(message: str, width: int = 640, height: int = 480) -> np.ndarray:
    """Create an error message frame."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (40, 40, 40)  # Dark gray background

    # Add error message
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.8
    thickness = 2
    color = (0, 0, 255)  # Red

    text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
    text_x = (width - text_size[0]) // 2
    text_y = (height + text_size[1]) // 2

    cv2.putText(frame, message, (text_x, text_y), font, font_scale, color, thickness)

    return frame


def add_debug_overlay(frame: np.ndarray, channel_id: int, person_count: int, fps: int) -> np.ndarray:
    """Add debug information overlay to frame."""
    # Add semi-transparent background for text
    overlay = frame.copy()
    cv2.rectangle(overlay, (10, 10), (350, 90), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)

    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    color = (0, 255, 0)  # Green

    # Channel info
    cv2.putText(frame, f"Channel: {channel_id}", (20, 35), font, font_scale, color, thickness)

    # Detection count
    cv2.putText(frame, f"Persons: {person_count}", (20, 60), font, font_scale, color, thickness)

    # Timestamp
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, timestamp, (20, 85), font, font_scale, (255, 255, 255), thickness)

    return frame


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/", response_class=HTMLResponse)
async def debug_index():
    """Debug stream index page with channel selection."""
    active_channels = getattr(settings, 'ACTIVE_CHANNELS', [1, 2, 3, 4])

    channel_links = "\n".join([
        f'<a href="/debug/stream/{ch}" target="_blank" class="channel-link">'
        f'Channel {ch}</a>'
        for ch in active_channels
    ])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>CCTV Debug Stream</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: #1a1a1a;
                color: #fff;
                margin: 0;
                padding: 20px;
            }}
            h1 {{
                color: #4CAF50;
                margin-bottom: 20px;
            }}
            .info {{
                background: #2d2d2d;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
            }}
            .channels {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 15px;
            }}
            .channel-link {{
                display: block;
                background: #4CAF50;
                color: white;
                padding: 20px;
                text-align: center;
                text-decoration: none;
                border-radius: 8px;
                font-size: 18px;
                transition: background 0.3s;
            }}
            .channel-link:hover {{
                background: #45a049;
            }}
            .grid-view {{
                margin-top: 30px;
            }}
            .grid-view h2 {{
                color: #888;
            }}
            .stream-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 10px;
            }}
            .stream-grid img {{
                width: 100%;
                border-radius: 4px;
            }}
        </style>
    </head>
    <body>
        <h1>CCTV Debug Stream</h1>
        <div class="info">
            <p><strong>Store:</strong> {settings.STORE_ID}</p>
            <p><strong>Active Channels:</strong> {', '.join(map(str, active_channels))}</p>
            <p><strong>Debug Mode:</strong> YOLO bounding boxes + ROI overlay</p>
        </div>

        <h2>Select Channel (opens in new tab)</h2>
        <div class="channels">
            {channel_links}
        </div>

        <div class="grid-view">
            <h2>All Channels Grid View</h2>
            <div class="stream-grid">
                {''.join([f'<img src="/debug/stream/{ch}" alt="Channel {ch}">' for ch in active_channels[:4]])}
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/stream/{channel_id}")
async def stream_channel(channel_id: int, fps: int = 5):
    """Stream MJPEG with YOLO detection overlay.

    Args:
        channel_id: Channel number (1-16)
        fps: Target frames per second (1-30, default: 5)
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    fps = max(1, min(30, fps))  # Clamp FPS between 1-30

    return StreamingResponse(
        generate_mjpeg_stream(channel_id, fps),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@router.get("/snapshot/{channel_id}")
async def snapshot_channel(channel_id: int):
    """Get single snapshot with YOLO detection overlay.

    Args:
        channel_id: Channel number (1-16)
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    # Build RTSP URL using settings method (secure)
    rtsp_url = settings.get_rtsp_url(
        host=settings.RTSP_HOST,
        port=settings.RTSP_PORT,
        channel_id=channel_id
    )

    client = RTSPClient(rtsp_url)
    detector = get_detector()
    roi_matcher = get_roi_matcher(channel_id)

    try:
        if not client.connect(timeout=10):
            raise HTTPException(status_code=503, detail=f"Failed to connect to channel {channel_id}")

        frame = client.capture_frame()
        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        # Detect and annotate
        detections = detector.detect_persons(frame)
        annotated = detector.annotate_image(frame, detections)

        if roi_matcher:
            occupancy = roi_matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)
            annotated = roi_matcher.visualize_rois(annotated, occupancy)

            for x1, y1, x2, y2, conf in detections:
                bottom_center = (int((x1 + x2) / 2), int(y2))
                cv2.circle(annotated, bottom_center, 8, (255, 0, 255), -1)

        annotated = add_debug_overlay(annotated, channel_id, len(detections), 0)

        _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, SNAPSHOT_JPEG_QUALITY])

        return StreamingResponse(
            iter([buffer.tobytes()]),
            media_type="image/jpeg"
        )

    finally:
        client.disconnect()


@router.get("/status")
async def stream_status():
    """Get debug stream status and settings."""
    return {
        "enabled": os.getenv("DEBUG_STREAM_ENABLED", "false").lower() == "true",
        "store_id": settings.STORE_ID,
        "active_channels": getattr(settings, 'ACTIVE_CHANNELS', [1, 2, 3, 4]),
        "yolo_model": settings.YOLO_MODEL,
        "confidence_threshold": settings.CONFIDENCE_THRESHOLD,
        "iou_threshold": settings.IOU_THRESHOLD
    }
