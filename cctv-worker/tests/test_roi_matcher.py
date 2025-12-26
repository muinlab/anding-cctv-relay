"""Tests for ROI matcher module."""
import pytest
from src.core.roi_matcher import ROIMatcher


class TestROIMatcher:
    """Test cases for ROIMatcher class."""

    def test_init_with_dict(self, sample_roi_config):
        """Test initialization with dictionary config."""
        matcher = ROIMatcher(sample_roi_config)

        assert matcher.camera_id == "test_camera"
        assert matcher.resolution == [1920, 1080]
        assert len(matcher.seats) == 2

    def test_init_empty(self):
        """Test initialization without config."""
        matcher = ROIMatcher()

        assert matcher.seats == []
        assert matcher.camera_id is None

    def test_calculate_iou_full_overlap(self):
        """Test IoU calculation with identical boxes."""
        box = (100, 100, 200, 200)
        iou = ROIMatcher.calculate_iou(box, box)

        assert iou == 1.0

    def test_calculate_iou_no_overlap(self):
        """Test IoU calculation with non-overlapping boxes."""
        box1 = (0, 0, 100, 100)
        box2 = (200, 200, 300, 300)
        iou = ROIMatcher.calculate_iou(box1, box2)

        assert iou == 0.0

    def test_calculate_iou_partial_overlap(self):
        """Test IoU calculation with partial overlap."""
        box1 = (0, 0, 100, 100)
        box2 = (50, 50, 150, 150)
        iou = ROIMatcher.calculate_iou(box1, box2)

        # Expected: intersection = 50*50 = 2500
        # union = 10000 + 10000 - 2500 = 17500
        # IoU = 2500/17500 ≈ 0.143
        assert 0.14 < iou < 0.15

    def test_point_in_polygon_inside(self):
        """Test point inside polygon."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        point = (50, 50)

        assert ROIMatcher.point_in_polygon(point, polygon) is True

    def test_point_in_polygon_outside(self):
        """Test point outside polygon."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        point = (150, 150)

        assert ROIMatcher.point_in_polygon(point, polygon) is False

    def test_point_in_polygon_on_edge(self):
        """Test point on polygon edge."""
        polygon = [[0, 0], [100, 0], [100, 100], [0, 100]]
        point = (0, 50)

        # Edge cases can be tricky, just ensure no crash
        result = ROIMatcher.point_in_polygon(point, polygon)
        assert isinstance(result, bool)

    def test_check_occupancy_empty(self, sample_roi_config):
        """Test occupancy check with no detections."""
        matcher = ROIMatcher(sample_roi_config)
        results = matcher.check_occupancy([])

        assert len(results) == 2
        assert results["A-01"]["status"] == "empty"
        assert results["A-02"]["status"] == "empty"

    def test_check_occupancy_with_detection(self, sample_roi_config, sample_detections):
        """Test occupancy check with person in seat A-01."""
        matcher = ROIMatcher(sample_roi_config)
        results = matcher.check_occupancy(sample_detections)

        # Person (120, 80, 180, 200) has bottom center at (150, 200)
        # This should be inside A-01's polygon [[100,100], [200,100], [200,200], [100,200]]
        assert results["A-01"]["status"] == "occupied"
        assert results["A-02"]["status"] == "empty"

    def test_add_seat(self):
        """Test adding a new seat."""
        matcher = ROIMatcher()
        matcher.add_seat("B-01", [0, 0, 100, 100], "B-01 좌석")

        assert len(matcher.seats) == 1
        assert matcher.seats[0]["id"] == "B-01"
        assert matcher.seats[0]["label"] == "B-01 좌석"

    def test_remove_seat(self):
        """Test removing a seat."""
        matcher = ROIMatcher()
        matcher.add_seat("B-01", [0, 0, 100, 100])
        matcher.add_seat("B-02", [100, 0, 200, 100])

        result = matcher.remove_seat("B-01")

        assert result is True
        assert len(matcher.seats) == 1
        assert matcher.seats[0]["id"] == "B-02"

    def test_remove_seat_not_found(self):
        """Test removing non-existent seat."""
        matcher = ROIMatcher()

        result = matcher.remove_seat("NOT_EXIST")

        assert result is False


class TestROIMatcherEdgeCases:
    """Edge case tests for ROIMatcher."""

    def test_empty_polygon(self):
        """Test with empty polygon list."""
        config = {
            "camera_id": "test",
            "resolution": [1920, 1080],
            "seats": []
        }
        matcher = ROIMatcher(config)
        results = matcher.check_occupancy([(0, 0, 100, 100, 0.9)])

        assert len(results) == 0

    def test_multiple_persons_same_seat(self):
        """Test multiple persons detected, one in seat."""
        config = {
            "camera_id": "test",
            "resolution": [1920, 1080],
            "seats": [{
                "id": "A-01",
                "roi": [[100, 100], [200, 100], [200, 200], [100, 200]],
                "label": "A-01",
                "type": "polygon"
            }]
        }
        matcher = ROIMatcher(config)

        # Multiple detections
        detections = [
            (120, 80, 180, 200, 0.95),  # In seat
            (500, 300, 600, 500, 0.87),  # Outside
            (800, 100, 900, 300, 0.75),  # Outside
        ]
        results = matcher.check_occupancy(detections)

        assert results["A-01"]["status"] == "occupied"

    def test_rectangle_roi(self):
        """Test rectangle-based ROI matching."""
        config = {
            "camera_id": "test",
            "resolution": [1920, 1080],
            "seats": [{
                "id": "A-01",
                "roi": [100, 100, 200, 200],  # Rectangle format
                "label": "A-01",
                "type": "rectangle"
            }]
        }
        matcher = ROIMatcher(config)

        # Detection overlapping with seat
        detections = [(120, 120, 180, 180, 0.9)]
        results = matcher.check_occupancy(detections, iou_threshold=0.3)

        assert results["A-01"]["status"] == "occupied"
