"""Test RTSP connection and capture frames."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient


def test_rtsp_connection():
    """Test RTSP connection and capture a snapshot."""

    print("=" * 60)
    print("RTSP Connection Test")
    print("=" * 60)

    # Get RTSP URL
    rtsp_url = settings.get_rtsp_url()
    print(f"\n📡 RTSP URL: {rtsp_url.replace(settings.RTSP_PASSWORD, '***')}")

    # Create client
    client = RTSPClient(rtsp_url)

    # Try to connect
    print("\n⏳ Connecting to RTSP stream...")
    if client.connect(timeout=15):
        print("✅ Connected successfully!")

        # Get stream info
        info = client.get_stream_info()
        if info:
            print(f"\n📊 Stream Information:")
            print(f"   - Resolution: {info['width']}x{info['height']}")
            print(f"   - FPS: {info['fps']}")
            print(f"   - Codec: {info['codec']}")

        # Capture a snapshot
        snapshot_path = settings.SNAPSHOT_DIR / "test_snapshot.jpg"
        print(f"\n📸 Capturing snapshot to: {snapshot_path}")

        if client.save_snapshot(snapshot_path):
            print("✅ Snapshot saved successfully!")
            print(f"\n💡 You can view the snapshot at:\n   {snapshot_path}")
        else:
            print("❌ Failed to save snapshot")

        # Disconnect
        client.disconnect()
        print("\n🔌 Disconnected from stream")

    else:
        print("❌ Failed to connect to RTSP stream")
        print("\n🔍 Troubleshooting tips:")
        print("   1. Check if DVR is online and accessible")
        print("   2. Verify RTSP credentials in .env file")
        print("   3. Ensure port 8554 is not blocked by firewall")
        print("   4. Try different RTSP paths:")
        print("      - rtsp://....:8554/live")
        print("      - rtsp://....:8554/ch1")
        print("      - rtsp://....:8554/stream1")
        return False

    print("\n" + "=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_rtsp_connection()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
