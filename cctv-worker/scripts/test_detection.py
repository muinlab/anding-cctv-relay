#!/usr/bin/env python3
"""Test YOLO detection on a single RTSP channel."""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_single_channel(channel: int = 12):
    """Test detection on a single channel.

    Args:
        channel: Channel number (1-16)
    """
    from dotenv import load_dotenv

    load_dotenv()

    # Get RTSP settings
    host = os.getenv("RTSP_HOST", "218.50.241.157")
    port = int(os.getenv("RTSP_PORT", "8554"))
    username = os.getenv("RTSP_USERNAME", "admin")
    password = os.getenv("RTSP_PASSWORD", "")

    rtsp_url = f"rtsp://{username}:{password}@{host}:{port}/live_{channel:02d}"

    print(f"Testing channel {channel}")
    print(f"RTSP URL: rtsp://{username}:****@{host}:{port}/live_{channel:02d}")
    print("-" * 50)

    # Import modules
    from utils.rtsp_client import RTSPClient
    from core.detector import PersonDetector
    from core.roi_matcher import ROIMatcher

    # Load ROI config
    roi_config_path = Path(__file__).parent.parent / f"data/roi_configs/channel_{channel}.json"
    if not roi_config_path.exists():
        print(f"ROI config not found: {roi_config_path}")
        print("Available configs:")
        for f in (Path(__file__).parent.parent / "data/roi_configs").glob("*.json"):
            print(f"  - {f.name}")
        return

    # Initialize components
    print("Loading YOLO model...")
    detector = PersonDetector(
        model_path=os.getenv("YOLO_MODEL", "yolo11n.pt"),
        confidence=float(os.getenv("CONFIDENCE_THRESHOLD", "0.3"))
    )

    print("Loading ROI config...")
    roi_matcher = ROIMatcher(roi_config_path)
    print(f"  Seats: {len(roi_matcher.seats)}")

    print("Connecting to RTSP...")
    rtsp_client = RTSPClient(rtsp_url)
    if not rtsp_client.connect():
        print("Failed to connect to RTSP stream")
        return

    print("Capturing frame...")
    frame = rtsp_client.capture_frame()
    if frame is None:
        print("Failed to capture frame")
        return

    print(f"Frame shape: {frame.shape}")

    print("Detecting persons...")
    detections = detector.detect_persons(frame)
    print(f"  Found {len(detections)} person(s)")

    for i, det in enumerate(detections):
        x1, y1, x2, y2, conf = det
        print(f"    [{i+1}] ({x1}, {y1}) - ({x2}, {y2}) conf={conf:.2f}")

    print("Checking seat occupancy...")
    iou_threshold = float(os.getenv("IOU_THRESHOLD", "0.3"))
    occupancy = roi_matcher.check_occupancy(detections, iou_threshold)

    for seat_id, status in occupancy.items():
        emoji = "🔴" if status["status"] == "occupied" else "🟢"
        print(f"  {emoji} Seat {seat_id}: {status['status']} (IoU: {status['max_iou']:.2f})")

    # Save annotated image
    output_dir = Path(__file__).parent.parent / "data/snapshots"
    output_dir.mkdir(parents=True, exist_ok=True)

    annotated = detector.annotate_image(frame, detections)
    annotated = roi_matcher.visualize_rois(annotated, occupancy)

    import cv2
    output_path = output_dir / f"test_channel_{channel}.jpg"
    cv2.imwrite(str(output_path), annotated)
    print(f"\nSaved annotated image: {output_path}")

    rtsp_client.disconnect()
    print("\nDone!")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test YOLO detection on RTSP channel")
    parser.add_argument(
        "--channel", "-c",
        type=int,
        default=12,
        help="Channel number (default: 12)"
    )
    args = parser.parse_args()

    test_single_channel(args.channel)


if __name__ == "__main__":
    main()
