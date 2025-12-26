"""ROI (Region of Interest) matching for seat occupancy detection."""
import json
import logging
import numpy as np
from typing import List, Tuple, Dict, Union, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ROIMatcher:
    """Match person detections with seat ROIs."""

    def __init__(self, roi_config: Union[Path, Dict, None] = None):
        """Initialize ROI matcher.

        Args:
            roi_config: Path to ROI configuration JSON file or dict config
        """
        self.roi_config_path = None
        self.seats = []
        self.camera_id = None
        self.resolution = None

        if roi_config is not None:
            if isinstance(roi_config, dict):
                self.load_from_dict(roi_config)
            elif isinstance(roi_config, (Path, str)):
                roi_config = Path(roi_config)
                self.roi_config_path = roi_config
                if roi_config.exists():
                    self.load_config(roi_config)

    def load_from_dict(self, config: Dict):
        """Load ROI configuration from dictionary.

        Args:
            config: Dict with camera_id, resolution, and seats
        """
        self.camera_id = config.get('camera_id')
        self.resolution = config.get('resolution')
        self.seats = config.get('seats', [])

        logger.info("Loaded ROI config: %d seats", len(self.seats))

    def load_config(self, config_path: Path):
        """Load ROI configuration from JSON.

        Args:
            config_path: Path to ROI config file

        Expected JSON format:
        {
            "camera_id": "branch01_cam1",
            "resolution": [1920, 1080],
            "seats": [
                {"id": "9", "roi": [120, 380, 220, 480], "label": "9번 좌석"},
                ...
            ]
        }
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            self.load_from_dict(config)

        except Exception as e:
            logger.error("Failed to load ROI config: %s", e)
            raise

    def save_config(self, config_path: Path):
        """Save current ROI configuration to JSON.

        Args:
            config_path: Path to save config file
        """
        config = {
            'camera_id': self.camera_id,
            'resolution': self.resolution,
            'seats': self.seats
        }

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            logger.info("Saved ROI config to: %s", config_path)

        except Exception as e:
            logger.error("Failed to save ROI config: %s", e)
            raise

    @staticmethod
    def calculate_iou(box1: Tuple[int, int, int, int],
                     box2: Tuple[int, int, int, int]) -> float:
        """Calculate Intersection over Union (IoU) between two boxes.

        Args:
            box1: (x1, y1, x2, y2)
            box2: (x1, y1, x2, y2)

        Returns:
            IoU value (0-1)
        """
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2

        # Calculate intersection
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)

        if x2_i < x1_i or y2_i < y1_i:
            return 0.0

        intersection = (x2_i - x1_i) * (y2_i - y1_i)

        # Calculate union
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        union = area1 + area2 - intersection

        if union == 0:
            return 0.0

        return intersection / union

    @staticmethod
    def point_in_polygon(point: Tuple[float, float], polygon: List[List[int]]) -> bool:
        """Check if a point is inside a polygon using ray casting algorithm.

        Args:
            point: (x, y) coordinates
            polygon: List of [x, y] coordinates forming the polygon

        Returns:
            True if point is inside polygon, False otherwise
        """
        x, y = point
        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def check_occupancy(
        self,
        person_detections: List[Tuple[int, int, int, int, float]],
        iou_threshold: float = 0.3
    ) -> Dict[str, str]:
        """Check seat occupancy based on person detections.

        Args:
            person_detections: List of (x1, y1, x2, y2, confidence) from YOLO
            iou_threshold: Minimum IoU to consider seat occupied

        Returns:
            Dictionary mapping seat_id to status ("occupied" or "empty")
        """
        results = {}

        for seat in self.seats:
            seat_id = seat['id']
            seat_type = seat.get('type', 'rectangle')

            occupied = False
            max_iou = 0.0

            if seat_type == 'polygon':
                # Polygon-based detection: check if person's bottom center is in polygon
                polygon = seat['roi']

                for person_box in person_detections:
                    x1, y1, x2, y2 = person_box[:4]
                    # Person's bottom center point (where their feet are)
                    person_bottom_center = ((x1 + x2) / 2, y2)

                    if self.point_in_polygon(person_bottom_center, polygon):
                        occupied = True
                        max_iou = 1.0  # Full match
                        break
            else:
                # Rectangle-based detection: use IoU
                seat_box = tuple(seat['roi'])  # (x1, y1, x2, y2)

                for person_box in person_detections:
                    person_bbox = person_box[:4]
                    iou = self.calculate_iou(person_bbox, seat_box)

                    if iou > max_iou:
                        max_iou = iou

                    if iou > iou_threshold:
                        occupied = True
                        break

            # Store matched detection for event logging
            matched_detection = None
            if occupied and person_detections:
                # Find the detection that matched this seat
                for person_box in person_detections:
                    if seat_type == 'polygon':
                        x1, y1, x2, y2 = person_box[:4]
                        person_bottom_center = ((x1 + x2) / 2, y2)
                        if self.point_in_polygon(person_bottom_center, seat['roi']):
                            matched_detection = person_box
                            break
                    else:
                        person_bbox = person_box[:4]
                        iou = self.calculate_iou(person_bbox, tuple(seat['roi']))
                        if iou > iou_threshold:
                            matched_detection = person_box
                            break

            results[seat_id] = {
                'status': 'occupied' if occupied else 'empty',
                'max_iou': max_iou,
                'label': seat.get('label', f'Seat {seat_id}'),
                'matched_detection': matched_detection
            }

        return results

    def visualize_rois(self, image: np.ndarray,
                       occupancy_status: Dict[str, Dict] = None) -> np.ndarray:
        """Draw ROI boxes/polygons on image.

        Args:
            image: Input image
            occupancy_status: Optional occupancy status from check_occupancy()

        Returns:
            Image with ROIs drawn
        """
        import cv2

        annotated = image.copy()

        for seat in self.seats:
            seat_id = seat['id']
            seat_type = seat.get('type', 'rectangle')
            label = seat.get('label', f'Seat {seat_id}')

            # Determine color based on occupancy
            if occupancy_status and seat_id in occupancy_status:
                status = occupancy_status[seat_id]['status']
                color = (0, 0, 255) if status == 'occupied' else (0, 255, 0)
                label = f"{label}: {status}"
            else:
                color = (255, 255, 0)  # Yellow for unknown

            if seat_type == 'polygon':
                # Draw polygon
                points = np.array(seat['roi'], dtype=np.int32)
                cv2.polylines(annotated, [points], isClosed=True, color=color, thickness=2)

                # Label at first point
                x, y = points[0]
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x, y - h - 10), (x + w, y), color, -1)
                cv2.putText(annotated, label, (x, y - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            else:
                # Draw rectangle
                x1, y1, x2, y2 = seat['roi']
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)

                # Draw label background
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(annotated, (x1, y1 - h - 10), (x1 + w, y1), color, -1)

                # Draw label text
                cv2.putText(annotated, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

        return annotated

    def add_seat(self, seat_id: str, roi: List[int], label: str = None):
        """Add a new seat ROI.

        Args:
            seat_id: Unique seat identifier
            roi: [x1, y1, x2, y2]
            label: Optional human-readable label
        """
        seat = {
            'id': seat_id,
            'roi': roi,
            'label': label or f'{seat_id}번 좌석'
        }
        self.seats.append(seat)

    def remove_seat(self, seat_id: str) -> bool:
        """Remove a seat by ID.

        Args:
            seat_id: Seat identifier to remove

        Returns:
            True if removed, False if not found
        """
        for i, seat in enumerate(self.seats):
            if seat['id'] == seat_id:
                self.seats.pop(i)
                return True
        return False
