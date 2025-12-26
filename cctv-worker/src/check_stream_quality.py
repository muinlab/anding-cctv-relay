"""Check current stream quality and settings."""
import sys
from pathlib import Path
import cv2

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient


def check_quality():
    """Check and diagnose stream quality issues."""

    print("=" * 60)
    print("RTSP Stream Quality Diagnosis")
    print("=" * 60)

    rtsp_url = settings.get_rtsp_url()
    print(f"\n📡 Stream: {rtsp_url.replace(settings.RTSP_PASSWORD, '***')}")

    # Connect
    print("\n⏳ Connecting...")
    client = RTSPClient(rtsp_url)

    if not client.connect(timeout=15):
        print("❌ Connection failed")
        return False

    print("✅ Connected!")

    # Get detailed stream info
    info = client.get_stream_info()

    print("\n📊 Stream Information:")
    print("-" * 60)
    if info:
        width = info['width']
        height = info['height']
        fps = info['fps']

        print(f"   Resolution: {width} x {height} pixels")
        print(f"   Total pixels: {width * height:,}")
        print(f"   FPS: {fps}")
        print(f"   Codec: {info['codec']}")

        # Analyze resolution
        print("\n🔍 Resolution Analysis:")
        if width * height >= 1920 * 1080:
            print("   ✅ Full HD (1080p) or higher - GOOD")
        elif width * height >= 1280 * 720:
            print("   ⚠️  HD (720p) - OK for detection")
        elif width * height >= 640 * 480:
            print("   ⚠️  SD (480p) - Low quality, may affect detection")
        else:
            print("   ❌ Very low resolution - NOT recommended")

    # Capture multiple frames to check consistency
    print("\n📸 Capturing test frames...")

    frames_data = []
    for i in range(3):
        frame = client.capture_frame()
        if frame is not None:
            # Analyze frame quality
            brightness = frame.mean()
            sharpness = cv2.Laplacian(frame, cv2.CV_64F).var()

            frames_data.append({
                'brightness': brightness,
                'sharpness': sharpness,
                'size': frame.nbytes / 1024  # KB
            })

            print(f"   Frame {i+1}: brightness={brightness:.1f}, sharpness={sharpness:.1f}")

    if frames_data:
        avg_brightness = sum(f['brightness'] for f in frames_data) / len(frames_data)
        avg_sharpness = sum(f['sharpness'] for f in frames_data) / len(frames_data)

        print(f"\n   Average brightness: {avg_brightness:.1f}")
        print(f"   Average sharpness: {avg_sharpness:.1f}")

        print("\n🔍 Quality Analysis:")
        if avg_sharpness < 100:
            print("   ❌ Very blurry - stream quality is poor")
        elif avg_sharpness < 500:
            print("   ⚠️  Somewhat blurry - consider higher quality stream")
        else:
            print("   ✅ Good sharpness")

    # Save high-quality snapshot
    print("\n💾 Saving high-quality snapshot...")
    snapshot_path = settings.SNAPSHOT_DIR / "quality_test_95.jpg"
    if client.save_snapshot(snapshot_path, quality=95):
        size = snapshot_path.stat().st_size / 1024
        print(f"   ✅ Saved: {snapshot_path.name} ({size:.1f} KB)")

        # Also save PNG for comparison (lossless)
        png_path = settings.SNAPSHOT_DIR / "quality_test.png"
        frame = client.capture_frame()
        if frame is not None:
            cv2.imwrite(str(png_path), frame, [cv2.IMWRITE_PNG_COMPRESSION, 1])
            png_size = png_path.stat().st_size / 1024
            print(f"   ✅ Saved PNG: {png_path.name} ({png_size:.1f} KB)")

    client.disconnect()

    # Recommendations
    print("\n" + "=" * 60)
    print("💡 Recommendations")
    print("=" * 60)

    print("\n1️⃣  DVR 설정 확인 필요:")
    print("   - DVR 웹 관리 페이지 접속")
    print("   - 카메라 설정 → 채널 12 → 인코딩 설정")
    print("   - Main Stream (메인 스트림) 확인:")
    print("     • 해상도: 1920x1080 (Full HD) 권장")
    print("     • 비트레이트: 2048 Kbps 이상 권장")
    print("     • 프레임: 15~25 fps")

    print("\n2️⃣  RTSP 경로 변경 시도:")
    print("   현재 경로: live_12")
    print("   시도해볼 경로들:")
    print("   - main_12 또는 stream1_12 (고화질 스트림)")
    print("   - h264_12 또는 h264/12")

    print("\n3️⃣  네트워크 확인:")
    print("   - DVR과 서버 간 네트워크 속도 확인")
    print("   - 대역폭 부족시 화질 자동 저하될 수 있음")

    print("\n4️⃣  카메라 자체 화질 확인:")
    print("   - DVR 웹페이지에서 라이브 영상 직접 확인")
    print("   - 카메라 렌즈 청소 필요 여부 확인")

    return True


if __name__ == "__main__":
    try:
        check_quality()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
