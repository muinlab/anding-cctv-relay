"""YOLO-based person detection."""
import logging
import numpy as np
from typing import List, Tuple, Optional
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logger = logging.getLogger(__name__)


class PersonDetector:
    """Person detector using YOLOv8."""

    def __init__(self, model_path: str = "yolov8n.pt", confidence: float = 0.5):
        """Initialize person detector.

        Args:
            model_path: Path to YOLO model file
            confidence: Confidence threshold for detection (0-1)
        """
        if YOLO is None:
            raise ImportError(
                "ultralytics not installed. Run: pip install ultralytics"
            )

        self.model_path = model_path
        self.confidence = confidence
        self.model: Optional[YOLO] = None
        self._load_model()

    def _load_model(self) -> None:
        """Load YOLO model."""
        try:
            logger.info("Loading YOLO model: %s", self.model_path)
            self.model = YOLO(self.model_path)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error("Failed to load model: %s", e)
            raise

    def detect_persons(
        self, image: np.ndarray, visualize: bool = False
    ) -> List[Tuple[int, int, int, int, float]]:
        """Detect persons in an image.

        Args:
            image: Input image (BGR format)
            visualize: If True, return annotated image

        Returns:
            List of detections as (x1, y1, x2, y2, confidence)
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Run inference
        results = self.model(image, conf=self.confidence, verbose=False)

        detections = []
        for result in results:
            boxes = result.boxes

            # Filter for person class (class_id = 0 in COCO dataset)
            for box in boxes:
                class_id = int(box.cls[0])
                if class_id == 0:  # Person class
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    conf = float(box.conf[0])
                    detections.append((int(x1), int(y1), int(x2), int(y2), conf))

        return detections

    def annotate_image(
        self, image: np.ndarray, detections: List[Tuple[int, int, int, int, float]]
    ) -> np.ndarray:
        """Draw bounding boxes on image.

        Args:
            image: Input image
            detections: List of detections from detect_persons()

        Returns:
            Annotated image
        """
        import cv2

        annotated = image.copy()

        for x1, y1, x2, y2, conf in detections:
            # Draw rectangle
            cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)

            # Draw label
            label = f"Person {conf:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(annotated, (x1, y1 - h - 10), (x1 + w, y1), (0, 255, 0), -1)
            cv2.putText(
                annotated,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 0, 0),
                1,
            )

        return annotated

    def get_model_info(self) -> dict:
        """Get model information.

        Returns:
            Dictionary with model details
        """
        if self.model is None:
            return {}

        return {
            "model_path": self.model_path,
            "confidence": self.confidence,
            "device": str(self.model.device),
        }
