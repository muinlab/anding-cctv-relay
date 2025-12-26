"""Configuration settings for the CCTV seat detection system."""
import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Settings:
    """Application settings."""

    # Project paths
    BASE_DIR = Path(__file__).parent.parent.parent
    DATA_DIR = BASE_DIR / "data"
    ROI_CONFIG_DIR = DATA_DIR / "roi_configs"
    SNAPSHOT_DIR = DATA_DIR / "snapshots"
    LOG_DIR = BASE_DIR / "logs"

    # Current store (from STORE_ID env variable)
    STORE_ID = os.getenv("STORE_ID", "oryudong")

    # RTSP credentials (공통 - 보안상 env에서만 관리)
    # 각 지점 NVR 비밀번호가 다르면 DB에 저장하거나 별도 비밀 관리 필요
    RTSP_HOST = os.getenv("RTSP_HOST", "")
    RTSP_PORT = int(os.getenv("RTSP_PORT", "554"))
    RTSP_USERNAME = os.getenv("RTSP_USERNAME", "admin")
    RTSP_PASSWORD = os.getenv("RTSP_PASSWORD", "")

    # Model settings
    YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))
    IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.3"))

    # Processing settings
    SNAPSHOT_INTERVAL = int(os.getenv("SNAPSHOT_INTERVAL", "3"))
    MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))

    # API settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))

    # GoSca 좌석 관리 시스템 설정
    GOSCA_BASE_URL = os.getenv("GOSCA_BASE_URL", "https://gosca.co.kr")
    GOSCA_STORE_ID = os.getenv("GOSCA_STORE_ID", "Anding-Oryudongyeok-sca")

    # Debug settings
    DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    DRY_RUN = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes")

    def get_rtsp_url(self, host: str, port: int, channel_id: int) -> str:
        """Generate RTSP URL for a channel.

        Args:
            host: RTSP server host
            port: RTSP server port
            channel_id: Channel number (1-16)

        Returns:
            Complete RTSP URL
        """
        path = f"live_{channel_id:02d}"
        return f"rtsp://{self.RTSP_USERNAME}:{self.RTSP_PASSWORD}@{host}:{port}/{path}"

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.ROI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
