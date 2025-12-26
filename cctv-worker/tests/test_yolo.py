"""Test YOLO person detection on RTSP stream."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector


def test_yolo_detection():
    """Test YOLO person detection on RTSP stream."""

    print("=" * 60)
    print("YOLO Person Detection Test")
    print("=" * 60)

    # Initialize detector
    print("\n🤖 Initializing YOLO model...")
    try:
        detector = PersonDetector(
            model_path=settings.YOLO_MODEL,
            confidence=settings.CONFIDENCE_THRESHOLD
        )

        model_info = detector.get_model_info()
        print(f"✅ Model loaded: {model_info['model_path']}")
        print(f"   - Confidence threshold: {model_info['confidence']}")
        print(f"   - Device: {model_info['device']}")

    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        print("\n💡 Tip: Model will be downloaded automatically on first run")
        return False

    # Connect to RTSP
    rtsp_url = settings.get_rtsp_url()
    print(f"\n📡 Connecting to RTSP: {rtsp_url.replace(settings.RTSP_PASSWORD, '***')}")

    client = RTSPClient(rtsp_url)
    if not client.connect(timeout=15):
        print("❌ Failed to connect to RTSP stream")
        return False

    print("✅ Connected to RTSP stream")

    # Capture and detect
    print("\n📸 Capturing frame and detecting persons...")
    frame = client.capture_frame()

    if frame is None:
        print("❌ Failed to capture frame")
        client.disconnect()
        return False

    print(f"✅ Frame captured: {frame.shape[1]}x{frame.shape[0]}")

    # Run detection
    print("\n🔍 Running person detection...")
    detections = detector.detect_persons(frame)

    print(f"\n📊 Detection Results:")
    print(f"   - Persons detected: {len(detections)}")

    if detections:
        print("\n👥 Detected persons:")
        for i, (x1, y1, x2, y2, conf) in enumerate(detections, 1):
            print(f"   {i}. Position: ({x1}, {y1}) → ({x2}, {y2})")
            print(f"      Confidence: {conf:.2%}")

        # Save annotated image
        annotated = detector.annotate_image(frame, detections)
        output_path = settings.SNAPSHOT_DIR / "test_detection.jpg"
        cv2.imwrite(str(output_path), annotated)
        print(f"\n💾 Annotated image saved to:\n   {output_path}")

    else:
        print("\n⚠️  No persons detected in the frame")
        # Save original frame anyway
        output_path = settings.SNAPSHOT_DIR / "test_no_detection.jpg"
        cv2.imwrite(str(output_path), frame)
        print(f"\n💾 Original frame saved to:\n   {output_path}")

    # Cleanup
    client.disconnect()
    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_yolo_detection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
