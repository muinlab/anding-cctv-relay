"""Auto-detect seats from camera image and generate polygons."""
import sys
from pathlib import Path
import cv2
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import RTSPClient


def auto_detect_seats(image, min_area=5000, max_area=200000):
    """Automatically detect seat regions from image.

    Args:
        image: Input image (BGR)
        min_area: Minimum contour area to consider as a seat
        max_area: Maximum contour area to consider as a seat

    Returns:
        List of polygons (each polygon is a list of [x,y] points)
    """
    print("\n" + "="*80)
    print("Auto-Detecting Seats")
    print("="*80)

    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Apply Gaussian blur to reduce noise
    print("\n1. Applying Gaussian blur...")
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)

    # Edge detection
    print("2. Detecting edges with Canny...")
    edges = cv2.Canny(blurred, 50, 150)

    # Morphological operations to close gaps
    print("3. Closing gaps with morphological operations...")
    kernel = np.ones((5, 5), np.uint8)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)

    # Find contours
    print("4. Finding contours...")
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"   Found {len(contours)} contours")

    # Filter contours by area
    print(f"5. Filtering contours (area between {min_area} and {max_area})...")
    valid_contours = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if min_area <= area <= max_area:
            valid_contours.append(contour)

    print(f"   {len(valid_contours)} contours passed area filter")

    # Approximate contours to polygons
    print("6. Approximating contours to polygons...")
    polygons = []
    for i, contour in enumerate(valid_contours):
        # Approximate contour to reduce number of points
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)

        # Convert to list of [x, y] points
        polygon = [[int(point[0][0]), int(point[0][1])] for point in approx]

        # Only keep polygons with 4+ points
        if len(polygon) >= 4:
            polygons.append(polygon)
            print(f"   Polygon {i+1}: {len(polygon)} points, area={cv2.contourArea(contour):.0f}")

    print(f"\n✅ Detected {len(polygons)} potential seat regions")
    return polygons


def visualize_detected_seats(image, polygons):
    """Draw detected polygons on image.

    Args:
        image: Input image
        polygons: List of polygons to draw

    Returns:
        Annotated image
    """
    annotated = image.copy()

    for i, polygon in enumerate(polygons):
        # Draw polygon
        points = np.array(polygon, dtype=np.int32)
        cv2.polylines(annotated, [points], isClosed=True, color=(0, 255, 0), thickness=2)

        # Draw label
        x, y = points[0]
        label = f"Seat {i+1}"
        cv2.putText(annotated, label, (x, y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        # Draw vertices
        for point in points:
            cv2.circle(annotated, tuple(point), 5, (255, 0, 0), -1)

    return annotated


def main():
    """Test auto-detection on a channel."""
    import argparse

    parser = argparse.ArgumentParser(description='Auto-detect seats from camera')
    parser.add_argument('channel', type=int, help='Channel number (1-16)')
    parser.add_argument('--min-area', type=int, default=5000, help='Minimum seat area')
    parser.add_argument('--max-area', type=int, default=200000, help='Maximum seat area')
    parser.add_argument('--save', action='store_true', help='Save detected polygons to config')

    args = parser.parse_args()

    print("="*80)
    print(f"Auto-Detecting Seats for Channel {args.channel}")
    print("="*80)

    # Connect to RTSP
    username = settings.RTSP_USERNAME
    password = settings.RTSP_PASSWORD
    host = settings.RTSP_HOST
    port = settings.RTSP_PORT
    path = f"live_{args.channel:02d}"
    rtsp_url = f"rtsp://{username}:{password}@{host}:{port}/{path}"

    print(f"\nConnecting to {rtsp_url}...")
    client = RTSPClient(rtsp_url)

    if not client.connect(timeout=10):
        print("❌ Failed to connect to RTSP")
        return

    print("✅ Connected to RTSP")

    # Capture frame
    print("\nCapturing frame...")
    frame = client.capture_frame()
    client.disconnect()

    if frame is None:
        print("❌ Failed to capture frame")
        return

    print(f"✅ Frame captured: {frame.shape[1]}x{frame.shape[0]}")

    # Auto-detect seats
    polygons = auto_detect_seats(frame, min_area=args.min_area, max_area=args.max_area)

    if not polygons:
        print("\n❌ No seats detected. Try adjusting --min-area and --max-area parameters.")
        return

    # Visualize
    print("\nVisualizing detected seats...")
    annotated = visualize_detected_seats(frame, polygons)

    # Save visualization
    output_path = settings.SNAPSHOT_DIR / f"channel_{args.channel:02d}_auto_detect.jpg"
    cv2.imwrite(str(output_path), annotated)
    print(f"✅ Saved visualization to: {output_path}")

    # Save config if requested
    if args.save:
        import json

        config_path = settings.ROI_CONFIG_DIR / f"channel_{args.channel:02d}.json"

        seats = []
        for i, polygon in enumerate(polygons, 1):
            seats.append({
                "id": str(i),
                "roi": polygon,
                "type": "polygon",
                "label": f"Seat {i}"
            })

        config = {
            "camera_id": f"branch01_cam{args.channel}",
            "resolution": [1920, 1080],
            "seats": seats
        }

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        print(f"✅ Saved config to: {config_path}")
        print(f"   {len(seats)} seats saved")
    else:
        print("\nℹ️  To save these polygons to config, run with --save flag")

    print("\n" + "="*80)
    print("Done!")
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
