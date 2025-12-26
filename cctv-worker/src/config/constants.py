"""Constants for CCTV Worker."""
from enum import Enum
from typing import Final


# ==============================================================================
# YOLO Detection
# ==============================================================================
PERSON_CLASS_ID: Final[int] = 0  # COCO dataset person class


# ==============================================================================
# Seat Status
# ==============================================================================
class SeatStatus(str, Enum):
    """Seat occupancy status."""
    EMPTY = "empty"
    OCCUPIED = "occupied"
    ABANDONED = "abandoned"


# ==============================================================================
# Detection Events
# ==============================================================================
class EventType(str, Enum):
    """Detection event types."""
    PERSON_ENTER = "person_enter"
    PERSON_LEAVE = "person_leave"
    ABANDONED_DETECTED = "abandoned_detected"
    ITEM_REMOVED = "item_removed"
    STATUS_CHANGE = "status_change"


# Event type mapping: (prev_status, new_status) -> event_type
EVENT_TYPE_MAP: Final[dict] = {
    (SeatStatus.EMPTY, SeatStatus.OCCUPIED): EventType.PERSON_ENTER,
    (SeatStatus.OCCUPIED, SeatStatus.EMPTY): EventType.PERSON_LEAVE,
    (SeatStatus.EMPTY, SeatStatus.ABANDONED): EventType.ABANDONED_DETECTED,
    (SeatStatus.OCCUPIED, SeatStatus.ABANDONED): EventType.ABANDONED_DETECTED,
    (SeatStatus.ABANDONED, SeatStatus.OCCUPIED): EventType.PERSON_ENTER,
    (SeatStatus.ABANDONED, SeatStatus.EMPTY): EventType.ITEM_REMOVED,
}


# ==============================================================================
# Thresholds and Timeouts
# ==============================================================================
# Abandoned item detection: time threshold in seconds
ABANDONED_THRESHOLD_SECONDS: Final[int] = 600  # 10 minutes

# RTSP connection
RTSP_DEFAULT_TIMEOUT: Final[int] = 10  # seconds
RTSP_RECONNECT_DELAY: Final[int] = 5  # seconds
RTSP_MAX_ERRORS: Final[int] = 10

# Detection worker
DEFAULT_SNAPSHOT_INTERVAL: Final[int] = 3  # seconds
LOG_PROGRESS_INTERVAL: Final[int] = 20  # frames


# ==============================================================================
# ROI Types
# ==============================================================================
class ROIType(str, Enum):
    """ROI shape types."""
    RECTANGLE = "rectangle"
    POLYGON = "polygon"


# ==============================================================================
# Log Levels
# ==============================================================================
class LogLevel(str, Enum):
    """System log levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
