"""Tests for constants module."""
import pytest
from src.config.constants import (
    SeatStatus,
    EventType,
    ROIType,
    LogLevel,
    PERSON_CLASS_ID,
    EVENT_TYPE_MAP,
    ABANDONED_THRESHOLD_SECONDS,
)


class TestSeatStatus:
    """Test SeatStatus enum."""

    def test_values(self):
        """Test all status values exist."""
        assert SeatStatus.EMPTY == "empty"
        assert SeatStatus.OCCUPIED == "occupied"
        assert SeatStatus.ABANDONED == "abandoned"

    def test_is_string_enum(self):
        """Test that SeatStatus is a string enum."""
        assert isinstance(SeatStatus.EMPTY, str)
        assert SeatStatus.EMPTY == "empty"


class TestEventType:
    """Test EventType enum."""

    def test_values(self):
        """Test all event types exist."""
        assert EventType.PERSON_ENTER == "person_enter"
        assert EventType.PERSON_LEAVE == "person_leave"
        assert EventType.ABANDONED_DETECTED == "abandoned_detected"
        assert EventType.ITEM_REMOVED == "item_removed"
        assert EventType.STATUS_CHANGE == "status_change"


class TestEventTypeMap:
    """Test event type mapping."""

    def test_empty_to_occupied(self):
        """Test empty -> occupied transition."""
        key = (SeatStatus.EMPTY, SeatStatus.OCCUPIED)
        assert EVENT_TYPE_MAP[key] == EventType.PERSON_ENTER

    def test_occupied_to_empty(self):
        """Test occupied -> empty transition."""
        key = (SeatStatus.OCCUPIED, SeatStatus.EMPTY)
        assert EVENT_TYPE_MAP[key] == EventType.PERSON_LEAVE

    def test_abandoned_detection(self):
        """Test abandoned detection events."""
        key1 = (SeatStatus.EMPTY, SeatStatus.ABANDONED)
        key2 = (SeatStatus.OCCUPIED, SeatStatus.ABANDONED)

        assert EVENT_TYPE_MAP[key1] == EventType.ABANDONED_DETECTED
        assert EVENT_TYPE_MAP[key2] == EventType.ABANDONED_DETECTED


class TestROIType:
    """Test ROIType enum."""

    def test_values(self):
        """Test ROI types."""
        assert ROIType.RECTANGLE == "rectangle"
        assert ROIType.POLYGON == "polygon"


class TestLogLevel:
    """Test LogLevel enum."""

    def test_values(self):
        """Test log levels."""
        assert LogLevel.DEBUG == "DEBUG"
        assert LogLevel.INFO == "INFO"
        assert LogLevel.WARNING == "WARNING"
        assert LogLevel.ERROR == "ERROR"
        assert LogLevel.CRITICAL == "CRITICAL"


class TestConstants:
    """Test constant values."""

    def test_person_class_id(self):
        """Test YOLO person class ID."""
        assert PERSON_CLASS_ID == 0

    def test_abandoned_threshold(self):
        """Test abandoned threshold is 10 minutes."""
        assert ABANDONED_THRESHOLD_SECONDS == 600
