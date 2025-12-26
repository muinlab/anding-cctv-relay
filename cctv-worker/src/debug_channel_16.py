"""Debug Channel 16 detection for Seat 29."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher


def main():
    print("=" * 80)
    print("Debugging Channel 16 - Seat 29")
    print("=" * 80)

    # Channel 16 config
    channel_id = 16
    config_path = settings.ROI_CONFIG_DIR / f"channel_{channel_id:02d}.json"

    if not config_path.exists():
        print(f"❌ Config not found: {config_path}")
        return

    # Load config
    import json
    with open(config_path, 'r') as f:
        config = json.load(f)

    print(f"\nSeats configured: {len(config['seats'])}")
    for seat in config['seats']:
        print(f"  - Seat {seat['id']} ({seat['label']})")

    # RTSP URL
    username = settings.RTSP_USERNAME
    password = settings.RTSP_PASSWORD
    host = settings.RTSP_HOST
    port = settings.RTSP_PORT
    path = f"live_{channel_id:02d}"
    rtsp_url = f"rtsp://{username}:{password}@{host}:{port}/{path}"

    # Connect to RTSP
    print(f"\nConnecting to {rtsp_url}...")
    client = RTSPClient(rtsp_url)

    if not client.connect(timeout=10):
        print("❌ Failed to connect to RTSP")
        return

    print("✅ Connected to RTSP")

    # Capture frame
    print("\nCapturing frame...")
    frame = client.capture_frame()

    if frame is None:
        print("❌ Failed to capture frame")
        client.disconnect()
        return

    print(f"✅ Frame captured: {frame.shape[1]}x{frame.shape[0]}")

    # Load YOLO detector
    print("\nLoading YOLO model...")
    detector = PersonDetector(
        model_path=settings.YOLO_MODEL,
        confidence=settings.CONFIDENCE_THRESHOLD
    )
    print("✅ YOLO model loaded")

    # Detect persons
    print("\nDetecting persons...")
    detections = detector.detect_persons(frame)
    print(f"Found {len(detections)} person(s)")

    if detections:
        for i, (x1, y1, x2, y2, conf) in enumerate(detections, 1):
            bottom_center_x = (x1 + x2) / 2
            bottom_center_y = y2
            print(f"\n  Person {i}:")
            print(f"    BBox: ({x1:.0f}, {y1:.0f}) -> ({x2:.0f}, {y2:.0f})")
            print(f"    Bottom center: ({bottom_center_x:.1f}, {bottom_center_y:.1f})")
            print(f"    Confidence: {conf:.2%}")

    # Load ROI matcher
    matcher = ROIMatcher(config_path)

    # Check each seat's polygon
    print("\n" + "=" * 80)
    print("Seat 29 Polygon Coordinates:")
    print("=" * 80)
    for seat in config['seats']:
        if seat['id'] == '29':
            print(f"\nSeat 29 polygon points: {len(seat['roi'])} points")
            for i, point in enumerate(seat['roi'], 1):
                print(f"  Point {i}: ({point[0]}, {point[1]})")

            # Calculate polygon bounds
            x_coords = [p[0] for p in seat['roi']]
            y_coords = [p[1] for p in seat['roi']]
            print(f"\nPolygon bounds:")
            print(f"  X: {min(x_coords)} to {max(x_coords)}")
            print(f"  Y: {min(y_coords)} to {max(y_coords)}")

    # Check occupancy
    print("\n" + "=" * 80)
    print("Occupancy Check:")
    print("=" * 80)
    occupancy = matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)

    for seat_id, info in occupancy.items():
        status_emoji = "🔴" if info['status'] == 'occupied' else "🟢"
        print(f"{status_emoji} Seat {seat_id} ({info['label']}): {info['status'].upper()} (match: {info['max_iou']:.2f})")

    # Check if any person's bottom center is in Seat 29 polygon
    print("\n" + "=" * 80)
    print("Manual Check - Is person's foot in Seat 29 polygon?")
    print("=" * 80)

    if detections:
        for seat in config['seats']:
            if seat['id'] == '29':
                polygon = seat['roi']
                for i, (x1, y1, x2, y2, conf) in enumerate(detections, 1):
                    bottom_center = ((x1 + x2) / 2, y2)
                    is_inside = matcher.point_in_polygon(bottom_center, polygon)
                    print(f"\nPerson {i} bottom center {bottom_center}:")
                    print(f"  Inside Seat 29 polygon: {'YES ✅' if is_inside else 'NO ❌'}")

    # Save visualization
    print("\n" + "=" * 80)
    print("Saving visualization...")
    annotated = detector.annotate_image(frame, detections)
    annotated = matcher.visualize_rois(annotated, occupancy)

    # Draw person bottom center points
    for x1, y1, x2, y2, conf in detections:
        bottom_center = (int((x1 + x2) / 2), int(y2))
        cv2.circle(annotated, bottom_center, 10, (255, 0, 255), -1)  # Magenta dot

    output_path = settings.SNAPSHOT_DIR / "channel_16_debug.jpg"
    cv2.imwrite(str(output_path), annotated)
    print(f"✅ Saved to: {output_path}")

    client.disconnect()

    print("\n" + "=" * 80)
    print("Debug completed!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
