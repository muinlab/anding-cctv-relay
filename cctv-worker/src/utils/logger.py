"""Structured logging utility for CCTV seat detection system.

This module provides structured logging that writes to both:
1. File logs (JSON format for debugging)
2. Database (system_logs table for LLM analysis)
"""
import logging
import json
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path


class StructuredLogger:
    """Structured logger with database integration."""

    def __init__(
        self,
        component: str,
        store_id: Optional[str] = None,
        enable_db: bool = True
    ):
        """Initialize structured logger.

        Args:
            component: Component name (e.g., 'channel_1_worker', 'api_server')
            store_id: Store ID for filtering (optional)
            enable_db: Whether to write logs to database
        """
        self.component = component
        self.store_id = store_id
        self.enable_db = enable_db
        self._db = None

        # Configure Python logging
        self.logger = logging.getLogger(component)
        self.logger.setLevel(logging.DEBUG)

        # File handler (JSON format)
        log_dir = Path(__file__).parent.parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # Separate file per component for easier debugging
        log_file = log_dir / f"{component}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)

        # JSON formatter
        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                    'level': record.levelname,
                    'component': component,
                    'message': record.getMessage(),
                }
                # Add extra fields from record
                if hasattr(record, 'metadata'):
                    log_data['metadata'] = record.metadata
                return json.dumps(log_data, ensure_ascii=False)

        file_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(file_handler)

        # Console handler (human-readable)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

    @property
    def db(self):
        """Lazy load database client."""
        if self._db is None and self.enable_db:
            try:
                from src.database.supabase_client import get_supabase_client
                self._db = get_supabase_client()
            except Exception as e:
                self.logger.error(f"Failed to initialize database client: {e}")
                self.enable_db = False
        return self._db

    def _log(
        self,
        level: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        store_to_db: bool = False
    ):
        """Internal logging method.

        Args:
            level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            message: Log message
            metadata: Additional structured data
            store_to_db: Force database storage even for INFO/DEBUG
        """
        # Add metadata to log record
        extra = {'metadata': metadata or {}}

        # Log to file and console
        log_method = getattr(self.logger, level.lower())
        log_method(message, extra=extra)

        # Log to database (only for WARNING+ or if forced)
        should_log_to_db = store_to_db or level in ['WARNING', 'ERROR', 'CRITICAL']

        if self.enable_db and should_log_to_db and self.db:
            try:
                self.db.log_system_event(
                    store_id=self.store_id,
                    log_level=level,
                    component=self.component,
                    message=message,
                    metadata=metadata
                )
            except Exception as e:
                # Don't fail on logging errors, but print to stderr
                print(f"Failed to log to database: {e}", file=sys.stderr)

    def debug(self, message: str, **metadata):
        """Log debug message."""
        self._log('DEBUG', message, metadata)

    def info(self, message: str, **metadata):
        """Log info message."""
        self._log('INFO', message, metadata)

    def warning(self, message: str, **metadata):
        """Log warning message (stored to database)."""
        self._log('WARNING', message, metadata)

    def error(self, message: str, **metadata):
        """Log error message (stored to database)."""
        self._log('ERROR', message, metadata)

    def critical(self, message: str, **metadata):
        """Log critical message (stored to database)."""
        self._log('CRITICAL', message, metadata)

    def metric(self, message: str, **metadata):
        """Log performance metric (stored to database for analysis)."""
        self._log('INFO', message, metadata, store_to_db=True)


class PerformanceMonitor:
    """Monitor and report performance metrics."""

    def __init__(self, logger: StructuredLogger, report_interval: int = 60):
        """Initialize performance monitor.

        Args:
            logger: Structured logger instance
            report_interval: Seconds between automatic reports
        """
        self.logger = logger
        self.report_interval = report_interval
        self.metrics = {
            'frame_count': 0,
            'detection_times_ms': [],
            'error_count': 0,
            'warning_count': 0,
            'start_time': datetime.now()
        }
        self.last_report = datetime.now()

    def record_frame(self, detection_time_ms: float):
        """Record successful frame processing."""
        self.metrics['frame_count'] += 1
        self.metrics['detection_times_ms'].append(detection_time_ms)

        # Auto-report if interval passed
        self._check_report()

    def record_error(self):
        """Record an error occurrence."""
        self.metrics['error_count'] += 1

    def record_warning(self):
        """Record a warning occurrence."""
        self.metrics['warning_count'] += 1

    def _check_report(self):
        """Check if it's time to report."""
        now = datetime.now()
        if (now - self.last_report).total_seconds() >= self.report_interval:
            self.report()
            self.last_report = now

    def report(self):
        """Generate and log performance report."""
        now = datetime.now()
        uptime_seconds = (now - self.metrics['start_time']).total_seconds()

        if uptime_seconds == 0:
            return

        fps = self.metrics['frame_count'] / uptime_seconds
        avg_latency = (
            sum(self.metrics['detection_times_ms']) / len(self.metrics['detection_times_ms'])
            if self.metrics['detection_times_ms'] else 0
        )

        error_rate = (
            self.metrics['error_count'] / self.metrics['frame_count']
            if self.metrics['frame_count'] > 0 else 0
        )

        self.logger.metric(
            "Performance report",
            uptime_hours=round(uptime_seconds / 3600, 2),
            total_frames=self.metrics['frame_count'],
            fps=round(fps, 2),
            avg_detection_ms=round(avg_latency, 2),
            error_count=self.metrics['error_count'],
            warning_count=self.metrics['warning_count'],
            error_rate=round(error_rate, 4)
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        uptime_seconds = (datetime.now() - self.metrics['start_time']).total_seconds()
        fps = self.metrics['frame_count'] / uptime_seconds if uptime_seconds > 0 else 0
        avg_latency = (
            sum(self.metrics['detection_times_ms']) / len(self.metrics['detection_times_ms'])
            if self.metrics['detection_times_ms'] else 0
        )

        return {
            'uptime_seconds': uptime_seconds,
            'frame_count': self.metrics['frame_count'],
            'fps': fps,
            'avg_detection_ms': avg_latency,
            'error_count': self.metrics['error_count'],
            'warning_count': self.metrics['warning_count']
        }


# Example usage
if __name__ == "__main__":
    # Create logger
    logger = StructuredLogger("test_component", store_id="oryudong")

    # Test different log levels
    logger.debug("This is a debug message", test_value=123)
    logger.info("System started", version="1.0.0")
    logger.warning("Low memory", available_mb=512, threshold_mb=1024)
    logger.error("Connection failed", error_code="ETIMEDOUT", retry_count=3)

    # Test performance monitor
    monitor = PerformanceMonitor(logger, report_interval=5)
    import time
    for i in range(10):
        monitor.record_frame(detection_time_ms=50 + i * 5)
        time.sleep(0.5)

    monitor.report()
    print("\nFinal stats:", monitor.get_stats())
