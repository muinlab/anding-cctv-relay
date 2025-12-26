"""Test multiple RTSP stream paths to find the best quality."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient


def test_stream_path(base_url: str, path: str, channel: str = "12"):
    """Test a specific RTSP stream path.

    Args:
        base_url: Base RTSP URL without path
        path: Stream path to test
        channel: Channel number

    Returns:
        Tuple of (success, resolution, file_size)
    """
    # Build full path
    full_path = f"{path}_{channel}" if path else channel

    # Build full URL
    rtsp_url = f"{base_url}/{full_path}"

    print(f"\n{'='*60}")
    print(f"Testing: {full_path}")
    print(f"{'='*60}")

    client = RTSPClient(rtsp_url)

    # Try to connect
    print("⏳ Connecting...")
    if not client.connect(timeout=10):
        print("❌ Connection failed")
        return False, None, None

    print("✅ Connected!")

    # Get stream info
    info = client.get_stream_info()
    if info:
        resolution = f"{info['width']}x{info['height']}"
        print(f"📊 Resolution: {resolution}")
        print(f"   FPS: {info['fps']}")
    else:
        resolution = "unknown"

    # Capture frame
    print("📸 Capturing frame...")
    frame = client.capture_frame()

    if frame is None:
        print("❌ Failed to capture frame")
        client.disconnect()
        return False, resolution, None

    # Save snapshot
    output_path = settings.SNAPSHOT_DIR / f"test_{full_path.replace('/', '_')}.jpg"
    if client.save_snapshot(output_path, quality=95):
        file_size = output_path.stat().st_size / 1024  # KB
        print(f"💾 Saved to: {output_path.name}")
        print(f"   File size: {file_size:.1f} KB")
        print(f"   Frame shape: {frame.shape}")

        # Calculate average brightness (rough quality indicator)
        brightness = frame.mean()
        print(f"   Avg brightness: {brightness:.1f}")

        client.disconnect()
        return True, resolution, file_size
    else:
        print("❌ Failed to save snapshot")
        client.disconnect()
        return False, resolution, None


def main():
    """Test multiple RTSP paths to find best quality."""

    print("=" * 60)
    print("RTSP Stream Quality Test")
    print("=" * 60)

    # Base URL without path
    base_url = f"rtsp://{settings.RTSP_USERNAME}:{settings.RTSP_PASSWORD}@{settings.RTSP_HOST}:{settings.RTSP_PORT}"

    # Common RTSP path patterns for DVRs
    # DVR마다 다르므로 여러 패턴 시도
    test_paths = [
        "live",           # live_12
        "stream1",        # stream1_12 (보통 고화질)
        "stream2",        # stream2_12 (보통 저화질)
        "main",           # main_12 (고화질)
        "sub",            # sub_12 (저화질)
        "ch",             # ch12
        "channel",        # channel12
        "h264",           # h264_12
        "",               # 12 (path 없이 채널만)
    ]

    channel = "12"  # 채널 번호
    results = []

    print(f"\n📡 Testing channel {channel} with different stream paths...")
    print(f"   Base URL: {base_url.replace(settings.RTSP_PASSWORD, '***')}")

    for path in test_paths:
        success, resolution, file_size = test_stream_path(base_url, path, channel)

        if success:
            results.append({
                'path': f"{path}_{channel}" if path else channel,
                'resolution': resolution,
                'file_size': file_size
            })

    # Summary
    print("\n" + "=" * 60)
    print("📊 Summary of Successful Connections")
    print("=" * 60)

    if not results:
        print("❌ No successful connections found")
        print("\n💡 Troubleshooting tips:")
        print("   1. Check if channel 12 exists on your DVR")
        print("   2. Try different channel numbers (1, 2, 3, etc.)")
        print("   3. Check DVR manual for correct RTSP path format")
        print("   4. Verify network connectivity to DVR")
        return False

    print(f"\n✅ Found {len(results)} working stream(s):\n")

    # Sort by file size (larger = better quality usually)
    results.sort(key=lambda x: x['file_size'] or 0, reverse=True)

    for i, result in enumerate(results, 1):
        marker = "⭐" if i == 1 else "  "
        print(f"{marker} {i}. {result['path']}")
        print(f"      Resolution: {result['resolution']}")
        print(f"      File size: {result['file_size']:.1f} KB")

    # Recommend best option
    best = results[0]
    print(f"\n🎯 Recommended path: {best['path']}")
    print(f"\n💡 Update your .env file:")
    print(f"   RTSP_PATH={best['path']}")

    return True


if __name__ == "__main__":
    try:
        success = main()
        print("\n" + "=" * 60)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
