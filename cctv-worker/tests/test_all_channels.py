"""Test all 16 RTSP channels to see which ones are active."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient


def get_rtsp_url_for_channel(channel_id: int) -> str:
    """Get RTSP URL for specific channel (1-16)."""
    username = settings.RTSP_USERNAME
    password = settings.RTSP_PASSWORD
    host = settings.RTSP_HOST
    port = settings.RTSP_PORT
    path = f"live_{channel_id:02d}"

    return f"rtsp://{username}:{password}@{host}:{port}/{path}"


def test_all_channels():
    """Test connection to all 16 channels."""
    print("=" * 70)
    print("Testing All 16 RTSP Channels")
    print("=" * 70)

    active_channels = []
    inactive_channels = []

    for channel_id in range(1, 17):
        rtsp_url = get_rtsp_url_for_channel(channel_id)
        print(f"\nChannel {channel_id:02d}: ", end="", flush=True)

        client = RTSPClient(rtsp_url)

        try:
            if client.connect(timeout=5):
                frame = client.capture_frame()
                if frame is not None:
                    print(f"✅ ACTIVE ({frame.shape[1]}x{frame.shape[0]})")
                    active_channels.append(channel_id)
                else:
                    print("❌ Connected but no frame")
                    inactive_channels.append(channel_id)
            else:
                print("❌ INACTIVE (connection failed)")
                inactive_channels.append(channel_id)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            inactive_channels.append(channel_id)
        finally:
            client.disconnect()

    print("\n" + "=" * 70)
    print(f"Summary: {len(active_channels)} active, {len(inactive_channels)} inactive")
    print("=" * 70)

    if active_channels:
        print(f"\n✅ Active Channels: {', '.join(map(str, active_channels))}")

    if inactive_channels:
        print(f"\n❌ Inactive Channels: {', '.join(map(str, inactive_channels))}")

    return active_channels


if __name__ == "__main__":
    try:
        active = test_all_channels()
        print(f"\n\nRecommendation: Configure UI to only show channels: {active}")
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
