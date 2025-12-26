"""Pytest configuration and fixtures."""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


@pytest.fixture
def sample_roi_config():
    """Sample ROI configuration for testing."""
    return {
        "camera_id": "test_camera",
        "resolution": [1920, 1080],
        "seats": [
            {
                "id": "A-01",
                "roi": [[100, 100], [200, 100], [200, 200], [100, 200]],
                "label": "A-01",
                "type": "polygon"
            },
            {
                "id": "A-02",
                "roi": [[300, 100], [400, 100], [400, 200], [300, 200]],
                "label": "A-02",
                "type": "polygon"
            }
        ]
    }


@pytest.fixture
def sample_detections():
    """Sample person detections for testing."""
    return [
        (120, 80, 180, 200, 0.95),  # Person in seat A-01
        (500, 300, 600, 500, 0.87),  # Person outside seats
    ]
