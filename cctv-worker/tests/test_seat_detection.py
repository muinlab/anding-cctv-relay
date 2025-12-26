"""End-to-end test: RTSP → YOLO → ROI matching → Seat status."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher


def test_seat_detection():
    """Test complete seat detection pipeline."""

    print("=" * 60)
    print("End-to-End Seat Detection Test")
    print("=" * 60)

    # 1. Load ROI configuration
    print("\n📍 Loading ROI configuration...")
    roi_config_path = settings.ROI_CONFIG_DIR / "example_config.json"

    if not roi_config_path.exists():
        print(f"⚠️  ROI config not found: {roi_config_path}")
        print("   Using example configuration from spec")
        # Create example config
        matcher = ROIMatcher()
        matcher.camera_id = "branch01_cam1"
        matcher.resolution = [1920, 1080]
        matcher.add_seat("9", [120, 380, 220, 480], "9번 좌석")
        matcher.add_seat("10", [240, 380, 340, 480], "10번 좌석")
        matcher.add_seat("11", [360, 380, 460, 480], "11번 좌석")
        matcher.add_seat("14", [280, 180, 380, 280], "14번 좌석")
        matcher.save_config(roi_config_path)
    else:
        matcher = ROIMatcher(roi_config_path)

    print(f"✅ Loaded {len(matcher.seats)} seat ROIs")

    # 2. Initialize YOLO detector
    print("\n🤖 Loading YOLO model...")
    try:
        detector = PersonDetector(
            model_path=settings.YOLO_MODEL,
            confidence=settings.CONFIDENCE_THRESHOLD
        )
        print("✅ YOLO model loaded")
    except Exception as e:
        print(f"❌ Failed to load YOLO: {e}")
        return False

    # 3. Connect to RTSP
    print("\n📡 Connecting to RTSP stream...")
    rtsp_url = settings.get_rtsp_url()
    client = RTSPClient(rtsp_url)

    if not client.connect(timeout=15):
        print("❌ Failed to connect to RTSP")
        return False

    print("✅ Connected to RTSP")

    # 4. Capture frame
    print("\n📸 Capturing frame...")
    frame = client.capture_frame()

    if frame is None:
        print("❌ Failed to capture frame")
        client.disconnect()
        return False

    print(f"✅ Frame captured: {frame.shape[1]}x{frame.shape[0]}")

    # 5. Detect persons
    print("\n🔍 Detecting persons...")
    detections = detector.detect_persons(frame)
    print(f"✅ Found {len(detections)} person(s)")

    # 6. Check seat occupancy
    print("\n💺 Checking seat occupancy...")
    occupancy = matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)

    print("\n📊 Seat Status:")
    print("-" * 60)
    occupied_count = 0
    for seat_id, info in occupancy.items():
        status = info['status']
        label = info['label']
        max_iou = info['max_iou']

        status_emoji = "🔴" if status == "occupied" else "🟢"
        print(f"{status_emoji} {label}: {status.upper()} (IoU: {max_iou:.2f})")

        if status == "occupied":
            occupied_count += 1

    print("-" * 60)
    print(f"Total: {occupied_count}/{len(occupancy)} seats occupied")

    # 7. Save visualization
    print("\n💾 Saving visualization...")

    # Draw person detections
    annotated = detector.annotate_image(frame, detections)

    # Draw ROIs with occupancy
    annotated = matcher.visualize_rois(annotated, occupancy)

    output_path = settings.SNAPSHOT_DIR / "seat_detection_result.jpg"
    cv2.imwrite(str(output_path), annotated)
    print(f"✅ Saved to: {output_path}")

    # Cleanup
    client.disconnect()

    print("\n" + "=" * 60)
    print("✅ Test completed successfully!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    try:
        success = test_seat_detection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
