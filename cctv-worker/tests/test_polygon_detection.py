"""Test polygon-based seat detection."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher


def test_polygon_detection():
    """Test polygon-based seat detection."""

    print("=" * 60)
    print("Polygon-Based Seat Detection Test")
    print("=" * 60)

    # Load polygon ROI configuration
    print("\nLoading polygon ROI configuration...")
    roi_config_path = settings.ROI_CONFIG_DIR / "test_polygon.json"

    if not roi_config_path.exists():
        print(f"ERROR: Config not found: {roi_config_path}")
        return False

    matcher = ROIMatcher(roi_config_path)
    print(f"Loaded {len(matcher.seats)} seat(s)")

    # Load YOLO
    print("\nLoading YOLO model...")
    detector = PersonDetector(
        model_path=settings.YOLO_MODEL,
        confidence=settings.CONFIDENCE_THRESHOLD
    )
    print("YOLO model loaded")

    # Connect to RTSP
    print("\nConnecting to RTSP stream...")
    rtsp_url = settings.get_rtsp_url()
    client = RTSPClient(rtsp_url)

    if not client.connect(timeout=15):
        print("ERROR: Failed to connect to RTSP")
        return False

    print("Connected to RTSP")

    # Capture frame
    print("\nCapturing frame...")
    frame = client.capture_frame()

    if frame is None:
        print("ERROR: Failed to capture frame")
        client.disconnect()
        return False

    print(f"Frame captured: {frame.shape[1]}x{frame.shape[0]}")

    # Detect persons
    print("\nDetecting persons...")
    detections = detector.detect_persons(frame)
    print(f"Found {len(detections)} person(s)")

    if detections:
        for i, (x1, y1, x2, y2, conf) in enumerate(detections, 1):
            bottom_center_x = (x1 + x2) / 2
            bottom_center_y = y2
            print(f"  Person {i}:")
            print(f"    BBox: ({x1}, {y1}) -> ({x2}, {y2})")
            print(f"    Bottom center: ({bottom_center_x:.1f}, {bottom_center_y:.1f})")
            print(f"    Confidence: {conf:.2%}")

    # Check occupancy
    print("\nChecking seat occupancy...")
    occupancy = matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)

    print("\nSeat Status:")
    print("-" * 60)
    occupied_count = 0
    for seat_id, info in occupancy.items():
        status = info['status']
        label = info['label']
        max_iou = info['max_iou']

        status_emoji = "OCCUPIED" if status == 'occupied' else "EMPTY"
        print(f"  {label}: {status_emoji} (match: {max_iou:.2f})")

        if status == 'occupied':
            occupied_count += 1

    print("-" * 60)
    print(f"Total: {occupied_count}/{len(occupancy)} seats occupied")

    # Save visualization
    print("\nSaving visualization...")

    # Draw person detections
    annotated = detector.annotate_image(frame, detections)

    # Draw ROIs with occupancy
    annotated = matcher.visualize_rois(annotated, occupancy)

    # Draw person bottom center points for debugging
    for x1, y1, x2, y2, conf in detections:
        bottom_center = (int((x1 + x2) / 2), int(y2))
        cv2.circle(annotated, bottom_center, 10, (255, 0, 255), -1)  # Magenta dot

    output_path = settings.SNAPSHOT_DIR / "polygon_detection_result.jpg"
    cv2.imwrite(str(output_path), annotated)
    print(f"Saved to: {output_path}")

    # Cleanup
    client.disconnect()

    print("\n" + "=" * 60)
    print("Test completed successfully!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_polygon_detection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
