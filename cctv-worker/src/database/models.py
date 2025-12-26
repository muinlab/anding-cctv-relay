"""SQLAlchemy ORM models for CCTV seat detection system."""
from sqlalchemy import Column, String, Integer, Float, Boolean, TIMESTAMP, Text, ForeignKey, JSON, UniqueConstraint, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class Store(Base):
    """지점 정보."""
    __tablename__ = "stores"

    store_id = Column(String(50), primary_key=True)
    gosca_store_id = Column(String(100), nullable=False)
    store_name = Column(String(100), nullable=False)
    rtsp_host = Column(String(100))
    rtsp_port = Column(Integer, default=8554)
    total_channels = Column(Integer, default=16)
    is_active = Column(Boolean, default=True)
    extra_data = Column("metadata", JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    seats = relationship("Seat", back_populates="store", cascade="all, delete-orphan")
    seat_statuses = relationship("SeatStatus", back_populates="store", cascade="all, delete-orphan")
    detection_events = relationship("DetectionEvent", back_populates="store", cascade="all, delete-orphan")
    occupancy_stats = relationship("OccupancyStat", back_populates="store", cascade="all, delete-orphan")
    system_logs = relationship("SystemLog", back_populates="store", cascade="all, delete-orphan")


class Seat(Base):
    """좌석 마스터 테이블 (GoSca + CCTV ROI 매핑)."""
    __tablename__ = "seats"
    __table_args__ = (
        UniqueConstraint('store_id', 'seat_id', name='uq_store_seat'),
        Index('idx_seats_store', 'store_id'),
        Index('idx_seats_channel', 'store_id', 'channel_id'),
        Index('idx_seats_active', 'store_id', 'is_active'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False)
    seat_id = Column(String(20), nullable=False)
    chairtbl_id = Column(String(50))

    # 좌석 위치
    grid_row = Column(Integer)
    grid_col = Column(Integer)

    # CCTV 매핑
    channel_id = Column(Integer)
    roi_polygon = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...]

    # 좌석 속성
    seat_type = Column(String(20), default='daily')  # 'fixed', 'daily', 'charging'
    seat_label = Column(String(100))

    # 상태
    is_active = Column(Boolean, default=True)

    # 메타데이터
    walls = Column(JSON)
    extra_data = Column("metadata", JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    store = relationship("Store", back_populates="seats")
    status = relationship("SeatStatus", back_populates="seat", uselist=False, cascade="all, delete-orphan")


class SeatStatus(Base):
    """좌석 실시간 상태."""
    __tablename__ = "seat_status"
    __table_args__ = (
        Index('idx_status_store', 'store_id'),
        Index('idx_status_status', 'store_id', 'status'),
        Index('idx_status_vacant', 'store_id', 'vacant_duration_seconds'),
    )

    store_id = Column(String(50), ForeignKey('stores.store_id', ondelete='CASCADE'), primary_key=True)
    seat_id = Column(String(20), primary_key=True)

    # 현재 상태
    status = Column(String(20), nullable=False, default='empty')  # 'empty', 'occupied', 'abandoned'

    # 감지 정보
    person_detected = Column(Boolean, default=False)
    object_detected = Column(Boolean, default=False)
    detection_confidence = Column(Float)

    # 시간 추적
    last_person_seen = Column(TIMESTAMP)
    last_empty_time = Column(TIMESTAMP)
    vacant_duration_seconds = Column(Integer, default=0)

    # GoSca 데이터
    gosca_occupied = Column(Boolean)
    gosca_user_name = Column(String(100))
    gosca_synced_at = Column(TIMESTAMP)

    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    store = relationship("Store", back_populates="seat_statuses")
    seat = relationship("Seat", back_populates="status", foreign_keys=[store_id, seat_id])


class DetectionEvent(Base):
    """감지 이벤트 로그."""
    __tablename__ = "detection_events"
    __table_args__ = (
        Index('idx_events_store_time', 'store_id', 'created_at'),
        Index('idx_events_seat', 'store_id', 'seat_id', 'created_at'),
        Index('idx_events_type', 'store_id', 'event_type', 'created_at'),
        Index('idx_events_channel', 'store_id', 'channel_id', 'created_at'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False)
    seat_id = Column(String(20), nullable=False)
    channel_id = Column(Integer)

    # 이벤트 타입
    event_type = Column(String(30), nullable=False)  # 'person_enter', 'person_leave', 'abandoned_detected'

    # 상태 변화
    previous_status = Column(String(20))
    new_status = Column(String(20))

    # 감지 정보
    person_detected = Column(Boolean)
    object_detected = Column(Boolean)
    confidence = Column(Float)

    # 바운딩 박스
    bbox_x1 = Column(Integer)
    bbox_y1 = Column(Integer)
    bbox_x2 = Column(Integer)
    bbox_y2 = Column(Integer)

    # 스냅샷
    snapshot_path = Column(String(255))

    # 메타데이터
    extra_data = Column("metadata", JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    store = relationship("Store", back_populates="detection_events")


class OccupancyStat(Base):
    """점유율 통계 (시간대별 집계)."""
    __tablename__ = "occupancy_stats"
    __table_args__ = (
        UniqueConstraint('store_id', 'seat_id', 'hour_slot', name='uq_store_seat_hour'),
        Index('idx_stats_store_hour', 'store_id', 'hour_slot'),
        Index('idx_stats_seat', 'store_id', 'seat_id', 'hour_slot'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), ForeignKey('stores.store_id', ondelete='CASCADE'), nullable=False)
    seat_id = Column(String(20))  # NULL이면 전체 지점 통계

    # 시간 슬롯
    hour_slot = Column(TIMESTAMP, nullable=False)

    # 집계 데이터 (분 단위)
    occupied_minutes = Column(Integer, default=0)
    vacant_minutes = Column(Integer, default=0)
    abandoned_minutes = Column(Integer, default=0)

    # 출입 통계
    total_entries = Column(Integer, default=0)
    total_exits = Column(Integer, default=0)

    # 체류 시간
    avg_stay_minutes = Column(Integer)
    max_stay_minutes = Column(Integer)

    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    store = relationship("Store", back_populates="occupancy_stats")


class SystemLog(Base):
    """시스템 로그."""
    __tablename__ = "system_logs"
    __table_args__ = (
        Index('idx_logs_store_time', 'store_id', 'created_at'),
        Index('idx_logs_level', 'log_level', 'created_at'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    store_id = Column(String(50), ForeignKey('stores.store_id', ondelete='CASCADE'))
    log_level = Column(String(20), nullable=False)  # 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    component = Column(String(50))  # 'worker', 'api', 'detector'
    message = Column(Text, nullable=False)
    extra_data = Column("metadata", JSON)
    created_at = Column(TIMESTAMP, server_default=func.now())

    # Relationships
    store = relationship("Store", back_populates="system_logs")
