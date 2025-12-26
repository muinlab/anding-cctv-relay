"""Visualize polygon ROI on snapshot."""
import sys
from pathlib import Path
import cv2
import json
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings


def draw_polygon_on_image():
    """Draw polygon ROI on the latest snapshot."""

    # Load the latest snapshot
    snapshot_path = settings.SNAPSHOT_DIR / "seat_detection_result.jpg"

    if not snapshot_path.exists():
        print(f"❌ Snapshot not found: {snapshot_path}")
        return

    # Read image
    image = cv2.imread(str(snapshot_path))

    # Load polygon config
    config_path = settings.ROI_CONFIG_DIR / "test_polygon.json"
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Draw each seat polygon
    for seat in config['seats']:
        points = np.array(seat['roi'], dtype=np.int32)
        label = seat['label']

        # Draw polygon
        cv2.polylines(image, [points], isClosed=True, color=(0, 255, 255), thickness=3)

        # Fill polygon with transparency
        overlay = image.copy()
        cv2.fillPoly(overlay, [points], color=(0, 255, 255))
        cv2.addWeighted(overlay, 0.3, image, 0.7, 0, image)

        # Draw label
        x, y = points[0]
        cv2.putText(image, label, (x, y - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    # Save
    output_path = settings.SNAPSHOT_DIR / "polygon_test.jpg"
    cv2.imwrite(str(output_path), image)

    print(f"✅ Polygon visualization saved to: {output_path}")


if __name__ == "__main__":
    draw_polygon_on_image()
