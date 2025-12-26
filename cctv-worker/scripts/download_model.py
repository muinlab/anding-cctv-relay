#!/usr/bin/env python3
"""Download YOLO model for seat detection."""
import sys
from pathlib import Path

def download_model(model_name: str = "yolo11n.pt") -> Path:
    """Download YOLO model using ultralytics.

    Args:
        model_name: Model name (yolo11n.pt, yolov8n.pt, etc.)

    Returns:
        Path to downloaded model
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ultralytics not installed. Run: pip install ultralytics")
        sys.exit(1)

    print(f"Downloading {model_name}...")

    # YOLO automatically downloads model if not exists
    model = YOLO(model_name)

    # Get model path
    model_path = Path(model_name)
    if model_path.exists():
        print(f"Model downloaded: {model_path} ({model_path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        print(f"Model ready: {model_name}")

    return model_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Download YOLO model")
    parser.add_argument(
        "--model",
        default="yolo11n.pt",
        help="Model name (default: yolo11n.pt)"
    )
    args = parser.parse_args()

    download_model(args.model)

    print("\nAvailable models:")
    print("  - yolo11n.pt  (fastest, ~6MB)")
    print("  - yolo11s.pt  (small, ~20MB)")
    print("  - yolo11m.pt  (medium, ~40MB)")
    print("  - yolov8n.pt  (v8 nano)")
    print("  - yolov8s.pt  (v8 small)")


if __name__ == "__main__":
    main()
