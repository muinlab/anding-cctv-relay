"""FastAPI endpoints for ROI configuration management."""
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from pathlib import Path
import json
import sys
import os
import cv2
import io

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher
from src.api.debug_stream import router as debug_router


app = FastAPI(title="CCTV ROI Configuration API")

# Include debug stream router if enabled
if os.getenv("DEBUG_STREAM_ENABLED", "false").lower() == "true":
    app.include_router(debug_router)

# Mount static files for frontend
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Pydantic models
class Point(BaseModel):
    x: int
    y: int


class Seat(BaseModel):
    id: str
    roi: List[List[int]]
    type: str = "polygon"
    label: str


class ROIConfig(BaseModel):
    camera_id: str
    resolution: List[int]
    seats: List[Seat]


class ChannelInfo(BaseModel):
    channel_id: int
    rtsp_path: str
    config_exists: bool


# Helper functions
def get_rtsp_url_for_channel(channel_id: int) -> str:
    """Get RTSP URL for specific channel (1-16)."""
    username = settings.RTSP_USERNAME
    password = settings.RTSP_PASSWORD
    host = settings.RTSP_HOST
    port = settings.RTSP_PORT
    path = f"live_{channel_id:02d}"  # Format as 01, 02, 03, etc.

    return f"rtsp://{username}:{password}@{host}:{port}/{path}"


def get_config_path_for_channel(channel_id: int) -> Path:
    """Get ROI config file path for specific channel."""
    return settings.ROI_CONFIG_DIR / f"channel_{channel_id:02d}.json"


# API Endpoints
@app.get("/")
async def root():
    """Serve the main web UI."""
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return FileResponse(html_path)
    return {"message": "ROI Configuration API", "docs": "/docs"}


@app.get("/api/channels", response_model=List[ChannelInfo])
async def list_channels():
    """List active RTSP channels with their config status."""
    channels = []
    active_channels = settings.ACTIVE_CHANNELS

    for i in active_channels:
        config_path = get_config_path_for_channel(i)
        channels.append(ChannelInfo(
            channel_id=i,
            rtsp_path=f"live_{i:02d}",  # Format as 01, 02, 03, etc.
            config_exists=config_path.exists()
        ))
    return channels


@app.get("/api/channels/{channel_id}/snapshot")
async def get_channel_snapshot(channel_id: int, width: int = 1920, height: int = 1080):
    """Capture a snapshot from the specified channel.

    Args:
        channel_id: Channel number (1-16)
        width: Desired image width for response
        height: Desired image height for response
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    rtsp_url = get_rtsp_url_for_channel(channel_id)
    client = RTSPClient(rtsp_url)

    try:
        if not client.connect(timeout=10):
            raise HTTPException(status_code=503, detail=f"Failed to connect to channel {channel_id}")

        frame = client.capture_frame()

        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        # Resize if needed
        if frame.shape[1] != width or frame.shape[0] != height:
            frame = cv2.resize(frame, (width, height))

        # Convert to JPEG
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

        if not success:
            raise HTTPException(status_code=500, detail="Failed to encode image")

        return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/jpeg")

    finally:
        client.disconnect()


@app.get("/api/channels/{channel_id}/config", response_model=ROIConfig)
async def get_channel_config(channel_id: int):
    """Get ROI configuration for the specified channel.

    Args:
        channel_id: Channel number (1-16)
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    config_path = get_config_path_for_channel(channel_id)

    if not config_path.exists():
        # Return empty config
        return ROIConfig(
            camera_id=f"branch01_cam{channel_id}",
            resolution=[1920, 1080],
            seats=[]
        )

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return ROIConfig(**config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load config: {str(e)}")


@app.post("/api/channels/{channel_id}/config")
async def save_channel_config(channel_id: int, config: ROIConfig):
    """Save ROI configuration for the specified channel.

    Args:
        channel_id: Channel number (1-16)
        config: ROI configuration to save
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    config_path = get_config_path_for_channel(channel_id)

    try:
        # Ensure directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Save config
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config.model_dump(), f, ensure_ascii=False, indent=2)

        return {"message": f"Config saved for channel {channel_id}", "path": str(config_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save config: {str(e)}")


@app.post("/api/channels/{channel_id}/auto-detect")
async def auto_detect_seats(channel_id: int, min_area: int = 10000, max_area: int = 150000):
    """Auto-detect seat regions from camera image.

    Args:
        channel_id: Channel number (1-16)
        min_area: Minimum contour area
        max_area: Maximum contour area
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    rtsp_url = get_rtsp_url_for_channel(channel_id)
    client = RTSPClient(rtsp_url)

    try:
        if not client.connect(timeout=10):
            raise HTTPException(status_code=503, detail=f"Failed to connect to channel {channel_id}")

        frame = client.capture_frame()

        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        # Auto-detect seats
        import numpy as np

        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)

        # Morphological operations
        kernel = np.ones((5, 5), np.uint8)
        closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find contours
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter and convert to polygons
        polygons = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if min_area <= area <= max_area:
                # Approximate contour
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)

                # Convert to list
                polygon = [[int(point[0][0]), int(point[0][1])] for point in approx]

                if len(polygon) >= 4:
                    polygons.append({
                        "roi": polygon,
                        "area": float(area)
                    })

        return {
            "detected": len(polygons),
            "polygons": polygons
        }

    finally:
        client.disconnect()


@app.delete("/api/channels/{channel_id}/config")
async def delete_channel_config(channel_id: int):
    """Delete ROI configuration for the specified channel.

    Args:
        channel_id: Channel number (1-16)
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    config_path = get_config_path_for_channel(channel_id)

    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"No config found for channel {channel_id}")

    try:
        config_path.unlink()
        return {"message": f"Config deleted for channel {channel_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete config: {str(e)}")


@app.get("/api/channels/{channel_id}/detect")
async def detect_persons_on_channel(channel_id: int):
    """Run person detection on the specified channel with current ROI config.

    Args:
        channel_id: Channel number (1-16)
    """
    if not 1 <= channel_id <= 16:
        raise HTTPException(status_code=400, detail="Channel ID must be between 1 and 16")

    config_path = get_config_path_for_channel(channel_id)

    if not config_path.exists():
        raise HTTPException(status_code=404, detail=f"No config found for channel {channel_id}")

    rtsp_url = get_rtsp_url_for_channel(channel_id)
    client = RTSPClient(rtsp_url)

    try:
        # Connect to RTSP
        if not client.connect(timeout=10):
            raise HTTPException(status_code=503, detail=f"Failed to connect to channel {channel_id}")

        # Capture frame
        frame = client.capture_frame()
        if frame is None:
            raise HTTPException(status_code=500, detail="Failed to capture frame")

        # Load YOLO detector
        detector = PersonDetector(
            model_path=settings.YOLO_MODEL,
            confidence=settings.CONFIDENCE_THRESHOLD
        )

        # Detect persons
        detections = detector.detect_persons(frame)
        print(f"\n[DEBUG] Detected {len(detections)} person(s) on channel {channel_id}:")
        for i, (x1, y1, x2, y2, conf) in enumerate(detections, 1):
            bottom_center = ((x1 + x2) / 2, y2)
            print(f"  Person {i}: bbox=({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f}), bottom_center={bottom_center}, conf={conf:.2%}")

        # Load ROI matcher
        matcher = ROIMatcher(config_path)

        # Check occupancy
        occupancy = matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)

        print(f"\n[DEBUG] Occupancy results:")
        for seat_id, info in occupancy.items():
            print(f"  Seat {seat_id} ({info['label']}): {info['status']} (match: {info['max_iou']:.2f})")

        # Annotate image
        annotated = detector.annotate_image(frame, detections)
        annotated = matcher.visualize_rois(annotated, occupancy)

        # Draw person bottom center points
        for x1, y1, x2, y2, conf in detections:
            bottom_center = (int((x1 + x2) / 2), int(y2))
            cv2.circle(annotated, bottom_center, 10, (255, 0, 255), -1)

        # Convert to JPEG
        success, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        if not success:
            raise HTTPException(status_code=500, detail="Failed to encode image")

        # Return both image and occupancy data
        # For now, just return the image
        return StreamingResponse(io.BytesIO(buffer.tobytes()), media_type="image/jpeg")

    finally:
        client.disconnect()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
