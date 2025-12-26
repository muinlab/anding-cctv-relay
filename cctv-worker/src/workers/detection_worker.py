"""Real-time detection worker for multi-store CCTV seat monitoring."""
import os
import sys
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from multiprocessing import Process, Queue, Event
from collections import defaultdict
from dateutil import parser as date_parser

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.utils import RTSPClient, StructuredLogger, PerformanceMonitor, create_detection_logger
from src.core import PersonDetector, ROIMatcher
from src.database.supabase_client import get_supabase_client
from dotenv import load_dotenv

load_dotenv()


class ChannelWorker:
    """Worker for monitoring a single RTSP channel."""

    def __init__(
        self,
        store_id: str,
        channel_id: int,
        rtsp_url: str,
        stop_event: Event,
        snapshot_interval: int = 3
    ):
        """Initialize channel worker.

        Args:
            store_id: Store identifier
            channel_id: Channel number (1-16)
            rtsp_url: RTSP stream URL
            stop_event: Multiprocessing event for graceful shutdown
            snapshot_interval: Seconds between snapshots
        """
        self.store_id = store_id
        self.channel_id = channel_id
        self.rtsp_url = rtsp_url
        self.stop_event = stop_event
        self.snapshot_interval = snapshot_interval

        # Initialize clients (will be created in worker process)
        self.rtsp_client = None
        self.detector = None
        self.roi_matcher = None
        self.db = None
        self.logger = None
        self.perf_monitor = None
        self.detection_logger = None  # For comprehensive frame logging

        # State tracking
        self.previous_occupancy = {}
        self.abandoned_timers = defaultdict(float)  # seat_id -> elapsed time with object only

    def initialize(self):
        """Initialize resources (must be called in worker process)."""
        # Initialize logger first
        self.logger = StructuredLogger(
            component=f"channel_{self.channel_id}_worker",
            store_id=self.store_id
        )
        self.logger.info("Initializing worker", channel=self.channel_id)

        # Initialize performance monitor
        self.perf_monitor = PerformanceMonitor(self.logger, report_interval=60)

        # RTSP client
        self.rtsp_client = RTSPClient(self.rtsp_url)

        # YOLO detector
        self.detector = PersonDetector(
            model_path=settings.YOLO_MODEL,
            confidence=settings.CONFIDENCE_THRESHOLD
        )

        # Database client
        self.db = get_supabase_client()

        # Detection logger for comprehensive frame logging
        self.detection_logger = create_detection_logger(
            store_id=self.store_id,
            channel_id=self.channel_id,
            db_client=self.db,
            enable_frame_logging=True  # Log every frame for analysis
        )

        # Load ROI configuration from database
        seats = self.db.get_seats(self.store_id, active_only=True)
        channel_seats = [s for s in seats if s.get('channel_id') == self.channel_id]

        if not channel_seats:
            self.logger.warning(
                "No seats configured for channel",
                channel=self.channel_id,
                total_seats=len(seats)
            )
            return False

        # Build ROI config for matcher
        roi_config = {
            "camera_id": f"{self.store_id}_channel_{self.channel_id}",
            "resolution": [1920, 1080],
            "seats": [
                {
                    "id": s['seat_id'],
                    "roi": s['roi_polygon'],
                    "label": s.get('seat_label', s['seat_id']),
                    "type": "polygon"
                }
                for s in channel_seats
                if s.get('roi_polygon') and len(s['roi_polygon']) > 0
            ]
        }

        if not roi_config['seats']:
            self.logger.warning(
                "No ROI polygons configured",
                channel=self.channel_id
            )
            return False

        self.roi_matcher = ROIMatcher(roi_config)

        # Initialize previous state
        for seat in roi_config['seats']:
            seat_id = seat['id']
            status = self.db.get_seat_status(self.store_id, seat_id)
            if status:
                self.previous_occupancy[seat_id] = status.get('status', 'empty')
            else:
                self.previous_occupancy[seat_id] = 'empty'

        self.logger.info(
            "Worker initialized successfully",
            channel=self.channel_id,
            seats_count=len(roi_config['seats']),
            seat_ids=[s['id'] for s in roi_config['seats']]
        )
        return True

    def connect_rtsp(self) -> bool:
        """Connect to RTSP stream."""
        self.logger.info("Connecting to RTSP stream", channel=self.channel_id)
        if self.rtsp_client.connect(timeout=15):
            self.logger.info("RTSP connected successfully", channel=self.channel_id)
            return True
        else:
            self.logger.error("RTSP connection failed", channel=self.channel_id)
            return False

    def process_frame(self, frame):
        """Process a single frame and update seat statuses."""
        import time
        start_time = time.time()

        # Detect persons
        detections = self.detector.detect_persons(frame)

        # Match with ROIs
        occupancy = self.roi_matcher.check_occupancy(
            detections,
            iou_threshold=settings.IOU_THRESHOLD
        )

        # Record performance
        detection_time_ms = int((time.time() - start_time) * 1000)
        self.perf_monitor.record_frame(detection_time_ms)

        # Process each seat
        current_time = datetime.now()

        for seat_id, info in occupancy.items():
            current_status = info['status']  # 'occupied' or 'empty'
            person_detected = current_status == 'occupied'
            belongings_detected = False  # TODO: Implement belongings detection
            confidence = info['max_iou'] if person_detected else 0.0

            # Build person bboxes list
            person_bboxes = []
            person_count = 0
            if person_detected and info.get('matched_detection'):
                det = info['matched_detection']
                person_bboxes = [[int(det[0]), int(det[1]), int(det[2]), int(det[3])]]
                person_count = 1

            # Log every frame detection for comprehensive analysis
            if self.detection_logger:
                self.detection_logger.log_frame_detection(
                    seat_id=seat_id,
                    person_detected=person_detected,
                    person_count=person_count,
                    person_confidence=confidence if person_detected else None,
                    person_bboxes=person_bboxes if person_bboxes else None,
                    belongings_detected=belongings_detected,
                    processing_time_ms=detection_time_ms
                )

            # Get previous status
            prev_status = self.previous_occupancy.get(seat_id, 'empty')

            # Determine new status (considering abandoned items)
            new_status = current_status

            # Abandoned item detection logic
            if not person_detected and belongings_detected:
                # Object without person - increment timer
                self.abandoned_timers[seat_id] += self.snapshot_interval
                if self.abandoned_timers[seat_id] >= 600:  # 10 minutes
                    new_status = 'abandoned'
            else:
                # Reset timer
                self.abandoned_timers[seat_id] = 0

            # Calculate vacant duration
            vacant_duration = 0
            last_person_seen = None
            last_empty_time = None

            if new_status == 'empty':
                # Get previous status from DB to calculate duration
                db_status = self.db.get_seat_status(self.store_id, seat_id)
                if db_status:
                    last_empty_time_raw = db_status.get('last_empty_time')
                    if last_empty_time_raw:
                        # Parse datetime string from Supabase
                        if isinstance(last_empty_time_raw, str):
                            last_empty_time = date_parser.parse(last_empty_time_raw)
                        else:
                            last_empty_time = last_empty_time_raw
                        vacant_duration = int((current_time - last_empty_time).total_seconds())
                    else:
                        last_empty_time = current_time
                else:
                    last_empty_time = current_time
            elif new_status == 'occupied':
                last_person_seen = current_time

            # Update database
            status_update = {
                'status': new_status,
                'person_detected': person_detected,
                'object_detected': belongings_detected,
                'detection_confidence': confidence,
                'last_person_seen': last_person_seen,
                'last_empty_time': last_empty_time,
                'vacant_duration_seconds': vacant_duration
            }

            try:
                self.db.update_seat_status(self.store_id, seat_id, status_update)
            except Exception as e:
                self.logger.warning(
                    "Failed to update seat status",
                    channel=self.channel_id,
                    seat_id=seat_id,
                    error=str(e)
                )
                self.perf_monitor.record_warning()

            # Log status change event (immediate, not batched)
            if new_status != prev_status:
                event_type_map = {
                    ('empty', 'occupied'): 'person_enter',
                    ('occupied', 'empty'): 'person_leave',
                    ('empty', 'abandoned'): 'abandoned_detected',
                    ('occupied', 'abandoned'): 'abandoned_detected',
                    ('abandoned', 'occupied'): 'person_enter',
                    ('abandoned', 'empty'): 'item_removed'
                }

                event_type = event_type_map.get((prev_status, new_status), 'status_change')

                # Use DetectionLogger for status changes
                if self.detection_logger:
                    self.detection_logger.log_status_change(
                        seat_id=seat_id,
                        event_type=event_type,
                        previous_status=prev_status,
                        new_status=new_status,
                        person_detected=person_detected,
                        person_confidence=confidence if person_detected else None,
                        person_bboxes=person_bboxes if person_bboxes else None,
                        belongings_detected=belongings_detected,
                        metadata={
                            'detections_count': len(detections),
                            'iou': info['max_iou']
                        }
                    )

                self.logger.info(
                    "Status changed",
                    channel=self.channel_id,
                    seat_id=seat_id,
                    previous_status=prev_status,
                    new_status=new_status,
                    event_type=event_type,
                    confidence=round(confidence, 3)
                )

            # Update previous state
            self.previous_occupancy[seat_id] = new_status

    def run(self):
        """Main worker loop."""
        try:
            # Initialize in worker process
            if not self.initialize():
                if self.logger:
                    self.logger.error("Initialization failed", channel=self.channel_id)
                return

            # Connect to RTSP
            if not self.connect_rtsp():
                self.logger.error("RTSP connection failed", channel=self.channel_id)
                return

            self.logger.info("Starting monitoring loop", channel=self.channel_id)

            # Main loop
            frame_count = 0
            error_count = 0
            max_errors = 10

            while not self.stop_event.is_set():
                try:
                    # Capture frame
                    frame = self.rtsp_client.capture_frame()

                    if frame is None:
                        error_count += 1
                        self.logger.warning(
                            "Failed to capture frame",
                            channel=self.channel_id,
                            error_count=error_count,
                            max_errors=max_errors
                        )
                        self.perf_monitor.record_error()

                        if error_count >= max_errors:
                            self.logger.error(
                                "Too many errors, attempting reconnection",
                                channel=self.channel_id
                            )
                            self.rtsp_client.disconnect()
                            time.sleep(5)
                            if not self.connect_rtsp():
                                self.logger.critical(
                                    "Reconnection failed, exiting worker",
                                    channel=self.channel_id
                                )
                                break
                            error_count = 0

                        time.sleep(1)
                        continue

                    # Reset error count on successful frame
                    error_count = 0
                    frame_count += 1

                    # Process frame
                    self.process_frame(frame)

                    # Log progress
                    if frame_count % 20 == 0:
                        occupied = sum(1 for s in self.previous_occupancy.values() if s == 'occupied')
                        total = len(self.previous_occupancy)
                        self.logger.debug(
                            "Processing progress",
                            channel=self.channel_id,
                            frame_count=frame_count,
                            occupied=occupied,
                            total_seats=total,
                            occupancy_rate=round(occupied / total, 2) if total > 0 else 0
                        )

                    # Wait for next snapshot
                    time.sleep(self.snapshot_interval)

                except KeyboardInterrupt:
                    self.logger.info("Received keyboard interrupt", channel=self.channel_id)
                    break
                except Exception as e:
                    error_count += 1
                    self.logger.error(
                        "Unexpected error in processing loop",
                        channel=self.channel_id,
                        error=str(e),
                        error_count=error_count
                    )
                    self.perf_monitor.record_error()
                    if error_count >= max_errors:
                        self.logger.critical(
                            "Max errors reached, exiting",
                            channel=self.channel_id
                        )
                        break
                    time.sleep(2)

        finally:
            # Cleanup
            if self.logger:
                self.logger.info("Shutting down worker", channel=self.channel_id)

                # Final performance report
                if self.perf_monitor:
                    self.perf_monitor.report()

            # Flush pending detection logs
            if self.detection_logger:
                # Get stats before closing to ensure data integrity
                stats = self.detection_logger.get_stats()
                self.detection_logger.close()
                if self.logger:
                    self.logger.info(
                        "Detection logger stats",
                        total_logged=stats['total_logged'],
                        batch_inserts=stats['batch_inserts'],
                        errors=stats['errors']
                    )

            if self.rtsp_client:
                self.rtsp_client.disconnect()

            # Log final statistics
            if self.db and self.perf_monitor:
                try:
                    stats = self.perf_monitor.get_stats()
                    self.db.log_system_event(
                        store_id=self.store_id,
                        log_level='INFO',
                        component=f'channel_{self.channel_id}_worker',
                        message='Worker stopped',
                        metadata={
                            'frame_count': frame_count,
                            'uptime_hours': round(stats['uptime_seconds'] / 3600, 2),
                            'avg_fps': round(stats['fps'], 2),
                            'error_count': stats['error_count']
                        }
                    )
                except Exception as e:
                    if self.logger:
                        self.logger.error("Failed to log final statistics", error=str(e))


class MultiChannelWorker:
    """Manager for multiple channel workers."""

    def __init__(self, store_id: str, channel_ids: List[int]):
        """Initialize multi-channel worker.

        Args:
            store_id: Store identifier
            channel_ids: List of channel IDs to monitor
        """
        self.store_id = store_id
        self.channel_ids = channel_ids
        self.processes: List[Process] = []
        self.stop_event = Event()

        # Initialize logger for orchestrator
        self.logger = StructuredLogger(
            component="multi_channel_orchestrator",
            store_id=store_id
        )

        # Load store config
        db = get_supabase_client()
        self.store = db.get_store(store_id)
        if not self.store:
            raise ValueError(f"Store {store_id} not found")

    def get_rtsp_url(self, channel_id: int) -> str:
        """Generate RTSP URL for channel using settings method."""
        host = self.store.get('rtsp_host') or settings.RTSP_HOST
        port = self.store.get('rtsp_port') or settings.RTSP_PORT
        return settings.get_rtsp_url(host=host, port=port, channel_id=channel_id)

    def start(self):
        """Start all channel workers."""
        print(f"\n{'='*60}")
        print(f"Starting Multi-Channel Detection Worker")
        print(f"Store: {self.store['store_name']} ({self.store_id})")
        print(f"Channels: {self.channel_ids}")
        print(f"{'='*60}\n")

        self.logger.info(
            "Starting multi-channel worker",
            store_id=self.store_id,
            store_name=self.store['store_name'],
            channel_ids=self.channel_ids,
            channel_count=len(self.channel_ids)
        )

        for channel_id in self.channel_ids:
            rtsp_url = self.get_rtsp_url(channel_id)

            worker = ChannelWorker(
                store_id=self.store_id,
                channel_id=channel_id,
                rtsp_url=rtsp_url,
                stop_event=self.stop_event,
                snapshot_interval=settings.SNAPSHOT_INTERVAL
            )

            process = Process(target=worker.run, name=f"Channel-{channel_id}")
            process.start()
            self.processes.append(process)

            print(f"✅ Started worker for channel {channel_id} (PID: {process.pid})")
            self.logger.info(
                "Started channel worker",
                channel_id=channel_id,
                process_pid=process.pid,
                process_name=process.name
            )
            time.sleep(1)  # Stagger starts

        print(f"\n🚀 All {len(self.processes)} workers started!\n")
        self.logger.info(
            "All workers started successfully",
            worker_count=len(self.processes)
        )

    def stop(self):
        """Stop all workers."""
        print("\n🛑 Stopping all workers...")
        self.logger.info("Stopping all workers", worker_count=len(self.processes))
        self.stop_event.set()

        for process in self.processes:
            process.join(timeout=10)
            if process.is_alive():
                print(f"⚠️  Force terminating {process.name}")
                self.logger.warning(
                    "Force terminating worker",
                    process_name=process.name,
                    process_pid=process.pid
                )
                process.terminate()
                process.join(timeout=5)

        print("✅ All workers stopped\n")
        self.logger.info("All workers stopped successfully")

    def wait(self):
        """Wait for all workers to complete."""
        try:
            for process in self.processes:
                process.join()
        except KeyboardInterrupt:
            print("\n⚠️  Received interrupt signal")
            self.stop()


def parse_store_id_from_gosca(gosca_id: str) -> str:
    """Parse store ID from GOSCA_STORE_ID environment variable.

    Args:
        gosca_id: GoSca store ID like 'Anding-Oryudongyeok-sca' or 'oryudong'

    Returns:
        Store ID like 'oryudong'
    """
    if not gosca_id:
        return 'oryudong'

    parts = gosca_id.split('-')
    if len(parts) > 1:
        # Format: 'Anding-Oryudongyeok-sca' -> 'oryudongyeok'
        return parts[1].lower()
    else:
        # Already a simple ID like 'oryudong'
        return gosca_id.lower()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Real-time CCTV seat detection worker")
    parser.add_argument(
        '--store',
        type=str,
        default=os.getenv('STORE_ID', 'oryudong'),
        help='Store ID (e.g., oryudong, gangnam)'
    )
    parser.add_argument(
        '--channels',
        type=str,
        default=None,
        help='Comma-separated channel IDs (e.g., 1,2,3). Default: from database'
    )

    args = parser.parse_args()

    # Get store config from database
    db = get_supabase_client()
    store = db.get_store(args.store)

    if not store:
        print(f"❌ Store '{args.store}' not found in database")
        print("\nAvailable stores:")
        for s in db.list_stores():
            print(f"  - {s['store_id']}: {s['store_name']}")
        sys.exit(1)

    # Parse channels: CLI > DB > default
    if args.channels:
        # CLI에서 명시적으로 지정
        channel_ids = [int(c.strip()) for c in args.channels.split(',')]
    elif store.get('active_channels'):
        # DB에서 가져오기
        channel_ids = store['active_channels']
    else:
        # 기본값: 1부터 total_channels까지
        total = store.get('total_channels', 4)
        channel_ids = list(range(1, total + 1))

    print(f"\n📍 Store: {store['store_name']} ({args.store})")
    print(f"📺 RTSP: {store.get('rtsp_host')}:{store.get('rtsp_port')}")
    print(f"📡 Channels: {channel_ids}\n")

    # Create and start worker
    worker = MultiChannelWorker(args.store, channel_ids)

    # Handle signals
    def signal_handler(sig, frame):
        print("\n⚠️  Received shutdown signal")
        worker.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start
    worker.start()

    # Wait
    worker.wait()


if __name__ == "__main__":
    main()
