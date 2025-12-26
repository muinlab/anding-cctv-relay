"""Run detection on all configured channels and show occupancy summary."""
import sys
from pathlib import Path
import json

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient
from src.core import PersonDetector, ROIMatcher


def get_rtsp_url_for_channel(channel_id: int) -> str:
    """Get RTSP URL for specific channel."""
    username = settings.RTSP_USERNAME
    password = settings.RTSP_PASSWORD
    host = settings.RTSP_HOST
    port = settings.RTSP_PORT
    path = f"live_{channel_id:02d}"
    return f"rtsp://{username}:{password}@{host}:{port}/{path}"


def get_config_path_for_channel(channel_id: int) -> Path:
    """Get ROI config file path for specific channel."""
    return settings.ROI_CONFIG_DIR / f"channel_{channel_id:02d}.json"


def run_detection_on_channel(channel_id: int, detector: PersonDetector):
    """Run detection on a single channel."""
    config_path = get_config_path_for_channel(channel_id)

    if not config_path.exists():
        return None

    # Load config to get seat count
    with open(config_path, 'r') as f:
        config = json.load(f)

    total_seats = len(config.get('seats', []))

    # Connect to RTSP
    rtsp_url = get_rtsp_url_for_channel(channel_id)
    client = RTSPClient(rtsp_url)

    try:
        if not client.connect(timeout=10):
            return {
                'channel': channel_id,
                'status': 'error',
                'error': 'Failed to connect to RTSP',
                'total_seats': total_seats,
                'occupied': 0
            }

        # Capture frame
        frame = client.capture_frame()
        if frame is None:
            return {
                'channel': channel_id,
                'status': 'error',
                'error': 'Failed to capture frame',
                'total_seats': total_seats,
                'occupied': 0
            }

        # Detect persons
        detections = detector.detect_persons(frame)

        # Load ROI matcher
        matcher = ROIMatcher(config_path)

        # Check occupancy
        occupancy = matcher.check_occupancy(detections, iou_threshold=settings.IOU_THRESHOLD)

        # Count occupied seats
        occupied_count = sum(1 for seat_info in occupancy.values() if seat_info['status'] == 'occupied')

        # Get seat details
        seat_details = []
        for seat_id, info in occupancy.items():
            seat_details.append({
                'id': seat_id,
                'label': info['label'],
                'status': info['status'],
                'match': info['max_iou']
            })

        return {
            'channel': channel_id,
            'status': 'success',
            'total_seats': total_seats,
            'occupied': occupied_count,
            'empty': total_seats - occupied_count,
            'persons_detected': len(detections),
            'seats': seat_details
        }

    except Exception as e:
        return {
            'channel': channel_id,
            'status': 'error',
            'error': str(e),
            'total_seats': total_seats,
            'occupied': 0
        }
    finally:
        client.disconnect()


def main():
    """Run detection on all configured channels."""
    print("=" * 80)
    print("Running Detection on All Configured Channels")
    print("=" * 80)

    # Find channels with config
    channels_with_config = []
    for i in range(1, 17):
        config_path = get_config_path_for_channel(i)
        if config_path.exists():
            channels_with_config.append(i)

    if not channels_with_config:
        print("\n❌ No channels have ROI configurations!")
        return

    print(f"\nFound {len(channels_with_config)} configured channel(s): {channels_with_config}")

    # Load YOLO detector once
    print("\nLoading YOLO model...")
    detector = PersonDetector(
        model_path=settings.YOLO_MODEL,
        confidence=settings.CONFIDENCE_THRESHOLD
    )
    print("✅ YOLO model loaded")

    # Run detection on each channel
    results = []
    total_seats_all = 0
    total_occupied_all = 0

    for channel_id in channels_with_config:
        print(f"\n{'='*80}")
        print(f"Channel {channel_id}")
        print(f"{'='*80}")

        result = run_detection_on_channel(channel_id, detector)
        results.append(result)

        if result['status'] == 'success':
            total_seats_all += result['total_seats']
            total_occupied_all += result['occupied']

            print(f"Status: ✅ Success")
            print(f"Persons detected: {result['persons_detected']}")
            print(f"Total seats: {result['total_seats']}")
            print(f"Occupied: {result['occupied']}")
            print(f"Empty: {result['empty']}")

            print(f"\nSeat Details:")
            print(f"{'-'*80}")
            for seat in result['seats']:
                status_emoji = "🔴" if seat['status'] == 'occupied' else "🟢"
                print(f"  {status_emoji} {seat['label']}: {seat['status'].upper()} (match: {seat['match']:.2f})")
        else:
            print(f"Status: ❌ Error - {result.get('error', 'Unknown error')}")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total channels configured: {len(channels_with_config)}")
    print(f"Total seats across all channels: {total_seats_all}")
    print(f"Total occupied seats: {total_occupied_all}")
    print(f"Total empty seats: {total_seats_all - total_occupied_all}")
    print(f"Occupancy rate: {(total_occupied_all / total_seats_all * 100):.1f}%" if total_seats_all > 0 else "N/A")

    print(f"\n{'='*80}")


if __name__ == "__main__":
    try:
        main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n❌ Detection interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
