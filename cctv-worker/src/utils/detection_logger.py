"""Detection event logger for comprehensive frame-by-frame logging.

This module provides a dedicated logger for detection events that:
1. Logs every frame detection (not just status changes)
2. Supports the extended detection_events schema
3. Batches inserts for better performance
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from collections import deque
import asyncio
import threading


class DetectionLogger:
    """Logger for detection events with batch support.

    Logs detection results to the detection_events table with support for:
    - Frame-by-frame logging (event_type='detection_frame')
    - Status change events (existing event types)
    - Batch inserts for performance
    - Extended schema (person_count, belongings, bboxes, etc.)
    """

    def __init__(
        self,
        store_id: str,
        channel_id: int,
        db_client,
        batch_size: int = 10,
        flush_interval: float = 5.0,
        enable_frame_logging: bool = True
    ):
        """Initialize detection logger.

        Args:
            store_id: Store identifier
            channel_id: CCTV channel number
            db_client: Supabase client instance
            batch_size: Number of events to batch before insert
            flush_interval: Max seconds between flushes
            enable_frame_logging: Whether to log every frame
        """
        self.store_id = store_id
        self.channel_id = channel_id
        self.db = db_client
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enable_frame_logging = enable_frame_logging

        # Batch queue
        self._batch: List[Dict[str, Any]] = []
        self._last_flush = datetime.now()
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            'total_logged': 0,
            'batch_inserts': 0,
            'errors': 0
        }

    def log_frame_detection(
        self,
        seat_id: str,
        person_detected: bool,
        person_count: int = 0,
        person_confidence: Optional[float] = None,
        person_bboxes: Optional[List[List[int]]] = None,
        belongings_detected: bool = False,
        belongings_confidence: Optional[float] = None,
        belongings_bboxes: Optional[List[List[int]]] = None,
        model_version: str = 'yolov8n',
        processing_time_ms: Optional[int] = None
    ):
        """Log a single frame detection result.

        This logs every detection frame, not just status changes.
        Use for comprehensive analysis and debugging.

        Args:
            seat_id: Seat identifier
            person_detected: Whether a person was detected
            person_count: Number of persons detected
            person_confidence: Detection confidence (0.0-1.0)
            person_bboxes: List of bounding boxes [[x1,y1,x2,y2], ...]
            belongings_detected: Whether belongings were detected
            belongings_confidence: Belongings detection confidence
            belongings_bboxes: Belongings bounding boxes
            model_version: YOLO model version used
            processing_time_ms: Frame processing time in milliseconds
        """
        if not self.enable_frame_logging:
            return

        event = self._build_event(
            seat_id=seat_id,
            event_type='detection_frame',
            person_detected=person_detected,
            person_count=person_count,
            person_confidence=person_confidence,
            person_bboxes=person_bboxes,
            belongings_detected=belongings_detected,
            belongings_confidence=belongings_confidence,
            belongings_bboxes=belongings_bboxes,
            model_version=model_version,
            processing_time_ms=processing_time_ms
        )

        self._add_to_batch(event)

    def log_status_change(
        self,
        seat_id: str,
        event_type: str,
        previous_status: str,
        new_status: str,
        person_detected: bool,
        person_confidence: Optional[float] = None,
        person_bboxes: Optional[List[List[int]]] = None,
        belongings_detected: bool = False,
        belongings_confidence: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log a status change event.

        This logs when seat status changes (person_enter, person_leave, etc.)
        Always logged immediately, not batched.

        Args:
            seat_id: Seat identifier
            event_type: Event type (person_enter, person_leave, abandoned_detected, etc.)
            previous_status: Previous seat status
            new_status: New seat status
            person_detected: Whether a person is currently detected
            person_confidence: Detection confidence
            person_bboxes: Person bounding boxes
            belongings_detected: Whether belongings detected
            belongings_confidence: Belongings confidence
            metadata: Additional metadata
        """
        event = self._build_event(
            seat_id=seat_id,
            event_type=event_type,
            previous_status=previous_status,
            new_status=new_status,
            person_detected=person_detected,
            person_confidence=person_confidence,
            person_bboxes=person_bboxes,
            belongings_detected=belongings_detected,
            belongings_confidence=belongings_confidence,
            metadata=metadata
        )

        # Status changes are logged immediately
        self._insert_single(event)

    def _build_event(
        self,
        seat_id: str,
        event_type: str,
        person_detected: bool = False,
        person_count: int = 0,
        person_confidence: Optional[float] = None,
        person_bboxes: Optional[List[List[int]]] = None,
        belongings_detected: bool = False,
        belongings_confidence: Optional[float] = None,
        belongings_bboxes: Optional[List[List[int]]] = None,
        previous_status: Optional[str] = None,
        new_status: Optional[str] = None,
        model_version: str = 'yolov8n',
        processing_time_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build event data dictionary."""
        event = {
            'store_id': self.store_id,
            'seat_id': seat_id,
            'channel_id': self.channel_id,
            'event_type': event_type,
            'person_detected': person_detected,
            'person_count': person_count,
            'belongings_detected': belongings_detected,
            'model_version': model_version,
        }

        # Optional fields
        if person_confidence is not None:
            event['confidence'] = person_confidence

        if person_bboxes:
            event['person_bboxes'] = person_bboxes
            # Also set legacy bbox fields from first detection
            if len(person_bboxes) > 0:
                bbox = person_bboxes[0]
                event['bbox_x1'] = int(bbox[0])
                event['bbox_y1'] = int(bbox[1])
                event['bbox_x2'] = int(bbox[2])
                event['bbox_y2'] = int(bbox[3])

        if belongings_confidence is not None:
            event['belongings_confidence'] = belongings_confidence

        if belongings_bboxes:
            event['belongings_bboxes'] = belongings_bboxes

        if previous_status:
            event['previous_status'] = previous_status

        if new_status:
            event['new_status'] = new_status

        if processing_time_ms is not None:
            event['processing_time_ms'] = processing_time_ms

        if metadata:
            event['metadata'] = metadata

        # Legacy compatibility
        event['object_detected'] = belongings_detected

        return event

    def _add_to_batch(self, event: Dict[str, Any]):
        """Add event to batch and flush if needed."""
        with self._lock:
            self._batch.append(event)

            # Check if we should flush
            should_flush = (
                len(self._batch) >= self.batch_size or
                (datetime.now() - self._last_flush).total_seconds() >= self.flush_interval
            )

            if should_flush:
                self._flush_batch()

    def _flush_batch(self):
        """Flush batch to database."""
        if not self._batch:
            return

        batch_to_insert = self._batch.copy()
        self._batch = []
        self._last_flush = datetime.now()

        try:
            # Batch insert
            self.db.client.table('detection_events').insert(batch_to_insert).execute()
            self.stats['total_logged'] += len(batch_to_insert)
            self.stats['batch_inserts'] += 1
        except Exception as e:
            self.stats['errors'] += 1
            # Log error but don't crash
            print(f"[DetectionLogger] Batch insert failed: {e}")

    def _insert_single(self, event: Dict[str, Any]):
        """Insert single event immediately."""
        try:
            self.db.log_detection_event(event)
            self.stats['total_logged'] += 1
        except Exception as e:
            self.stats['errors'] += 1
            print(f"[DetectionLogger] Single insert failed: {e}")

    def flush(self):
        """Force flush any pending events."""
        with self._lock:
            self._flush_batch()

    def get_stats(self) -> Dict[str, Any]:
        """Get logging statistics."""
        return {
            **self.stats,
            'pending_batch': len(self._batch)
        }

    def close(self):
        """Flush and close the logger."""
        self.flush()


# Factory function for easy creation
def create_detection_logger(
    store_id: str,
    channel_id: int,
    db_client,
    enable_frame_logging: bool = True
) -> DetectionLogger:
    """Create a DetectionLogger instance.

    Args:
        store_id: Store identifier
        channel_id: CCTV channel number
        db_client: Supabase client instance
        enable_frame_logging: Whether to log every frame (default: True)

    Returns:
        Configured DetectionLogger instance
    """
    return DetectionLogger(
        store_id=store_id,
        channel_id=channel_id,
        db_client=db_client,
        batch_size=10,
        flush_interval=5.0,
        enable_frame_logging=enable_frame_logging
    )
