"""FastAPI endpoints for multi-store seat status and detection."""
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.supabase_client import get_supabase_client, SupabaseClient
from src.utils.gosca_client import GoScaClient
from src.config import settings


app = FastAPI(
    title="CCTV Seat Detection API",
    description="Multi-store seat detection and occupancy management",
    version="2.0.0"
)

# CORS middleware for web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

class StoreInfo(BaseModel):
    store_id: str
    store_name: str
    gosca_store_id: str
    total_channels: int
    is_active: bool
    rtsp_host: Optional[str] = None


class SeatInfo(BaseModel):
    store_id: str
    seat_id: str
    grid_row: Optional[int] = None
    grid_col: Optional[int] = None
    channel_id: Optional[int] = None
    has_roi: bool
    seat_type: str
    seat_label: Optional[str] = None
    is_active: bool


class SeatStatusInfo(BaseModel):
    store_id: str
    seat_id: str
    status: str  # 'empty', 'occupied', 'abandoned'
    person_detected: bool
    object_detected: bool
    detection_confidence: Optional[float] = None
    last_person_seen: Optional[datetime] = None
    last_empty_time: Optional[datetime] = None
    vacant_duration_seconds: int
    updated_at: datetime


class OccupancySummary(BaseModel):
    store_id: str
    store_name: str
    total_seats: int
    occupied_count: int
    empty_count: int
    abandoned_count: int
    occupancy_rate: float
    updated_at: datetime


class DetectionEventCreate(BaseModel):
    store_id: str
    seat_id: str
    channel_id: int
    event_type: str  # 'person_enter', 'person_leave', 'abandoned_detected'
    previous_status: Optional[str] = None
    new_status: str
    person_detected: bool
    object_detected: bool
    confidence: float
    bbox_x1: Optional[int] = None
    bbox_y1: Optional[int] = None
    bbox_x2: Optional[int] = None
    bbox_y2: Optional[int] = None
    snapshot_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SeatStatusUpdate(BaseModel):
    status: str
    person_detected: bool
    object_detected: bool
    detection_confidence: Optional[float] = None
    last_person_seen: Optional[datetime] = None
    last_empty_time: Optional[datetime] = None
    vacant_duration_seconds: int = 0


# ============================================================================
# Store Endpoints
# ============================================================================

@app.get("/api/stores", response_model=List[StoreInfo])
async def list_stores(
    active_only: bool = True,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """List all stores."""
    stores = db.list_stores(active_only=active_only)
    return [StoreInfo(**store) for store in stores]


@app.get("/api/stores/{store_id}", response_model=StoreInfo)
async def get_store(
    store_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get store information."""
    store = db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")
    return StoreInfo(**store)


@app.get("/api/stores/{store_id}/summary", response_model=OccupancySummary)
async def get_store_summary(
    store_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get occupancy summary for a store."""
    summary = db.get_occupancy_summary_view(store_id)
    if not summary:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    return OccupancySummary(**summary)


@app.post("/api/stores/{store_id}/sync-gosca")
async def sync_gosca_seats(
    store_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Sync seat data from GoSca for a store."""
    store = db.get_store(store_id)
    if not store:
        raise HTTPException(status_code=404, detail=f"Store {store_id} not found")

    try:
        gosca = GoScaClient(store_id=store['gosca_store_id'])
        gosca_seats = gosca.fetch_seat_list()

        created = 0
        updated = 0

        for seat in gosca_seats:
            existing = db.get_seat(store_id, seat['seat_id'])

            seat_data = {
                'store_id': store_id,
                'seat_id': seat['seat_id'],
                'chairtbl_id': seat['chairtbl_id'],
                'grid_row': seat['grid_row'],
                'grid_col': seat['grid_col'],
                'seat_type': seat.get('seat_type', 'daily'),
                'seat_label': seat.get('seat_label'),
                'is_active': True,
                'roi_polygon': existing['roi_polygon'] if existing else [],
                'channel_id': existing['channel_id'] if existing else None,
                'walls': seat.get('walls'),
                'metadata': {'gosca_data': seat}
            }

            if existing:
                # Update only GoSca-related fields
                # Keep ROI mapping intact
                updated += 1
            else:
                db.create_seat(seat_data)
                # Initialize status
                db.update_seat_status(store_id, seat['seat_id'], {
                    'status': 'empty',
                    'person_detected': False,
                    'object_detected': False,
                    'vacant_duration_seconds': 0
                })
                created += 1

        return {
            "message": f"GoSca sync completed for {store_id}",
            "total": len(gosca_seats),
            "created": created,
            "updated": updated
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"GoSca sync failed: {str(e)}")


# ============================================================================
# Seat Endpoints
# ============================================================================

@app.get("/api/stores/{store_id}/seats", response_model=List[SeatInfo])
async def list_seats(
    store_id: str,
    active_only: bool = True,
    channel_id: Optional[int] = None,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """List all seats for a store."""
    seats = db.get_seats(store_id, active_only=active_only)

    # Filter by channel if specified
    if channel_id is not None:
        seats = [s for s in seats if s.get('channel_id') == channel_id]

    return [
        SeatInfo(
            **s,
            has_roi=bool(s.get('roi_polygon') and len(s['roi_polygon']) > 0)
        )
        for s in seats
    ]


@app.get("/api/stores/{store_id}/seats/{seat_id}", response_model=SeatInfo)
async def get_seat(
    store_id: str,
    seat_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get seat information."""
    seat = db.get_seat(store_id, seat_id)
    if not seat:
        raise HTTPException(
            status_code=404,
            detail=f"Seat {seat_id} not found in store {store_id}"
        )

    return SeatInfo(
        **seat,
        has_roi=bool(seat.get('roi_polygon') and len(seat['roi_polygon']) > 0)
    )


@app.patch("/api/stores/{store_id}/seats/{seat_id}/roi")
async def update_seat_roi(
    store_id: str,
    seat_id: str,
    channel_id: int,
    roi_polygon: List[List[int]],
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Update seat ROI mapping."""
    seat = db.get_seat(store_id, seat_id)
    if not seat:
        raise HTTPException(
            status_code=404,
            detail=f"Seat {seat_id} not found in store {store_id}"
        )

    try:
        updated = db.update_seat_roi(store_id, seat_id, channel_id, roi_polygon)
        return {
            "message": f"ROI updated for seat {seat_id}",
            "seat": SeatInfo(**updated, has_roi=True)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update ROI: {str(e)}")


# ============================================================================
# Seat Status Endpoints
# ============================================================================

@app.get("/api/stores/{store_id}/status", response_model=List[SeatStatusInfo])
async def get_all_seat_statuses(
    store_id: str,
    status_filter: Optional[str] = Query(None, description="Filter by status: empty, occupied, abandoned"),
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get real-time status of all seats in a store."""
    statuses = db.get_all_seat_statuses(store_id)

    # Filter by status if specified
    if status_filter:
        statuses = [s for s in statuses if s.get('status') == status_filter]

    return [SeatStatusInfo(**s) for s in statuses]


@app.get("/api/stores/{store_id}/status/{seat_id}", response_model=SeatStatusInfo)
async def get_seat_status(
    store_id: str,
    seat_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get current status of a specific seat."""
    status = db.get_seat_status(store_id, seat_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=f"Seat status not found for {seat_id} in store {store_id}"
        )

    return SeatStatusInfo(**status)


@app.patch("/api/stores/{store_id}/status/{seat_id}")
async def update_seat_status(
    store_id: str,
    seat_id: str,
    status_update: SeatStatusUpdate,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Update seat status (typically called by detection worker)."""
    try:
        updated = db.update_seat_status(
            store_id,
            seat_id,
            status_update.model_dump()
        )
        return {
            "message": f"Status updated for seat {seat_id}",
            "status": SeatStatusInfo(**updated)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@app.get("/api/stores/{store_id}/vacant")
async def get_vacant_seats(
    store_id: str,
    min_duration: int = Query(0, description="Minimum vacant duration in seconds"),
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get vacant seats with optional minimum vacant duration."""
    seats = db.get_vacant_seats(store_id, min_duration_seconds=min_duration)
    return [SeatStatusInfo(**s) for s in seats]


@app.get("/api/stores/{store_id}/abandoned")
async def get_abandoned_seats(
    store_id: str,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get seats with abandoned items."""
    seats = db.get_abandoned_seats(store_id)
    return [SeatStatusInfo(**s) for s in seats]


# ============================================================================
# Detection Events
# ============================================================================

@app.post("/api/events")
async def log_detection_event(
    event: DetectionEventCreate,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Log a detection event (called by detection worker)."""
    try:
        logged = db.log_detection_event(event.model_dump())
        return {
            "message": "Event logged",
            "event_id": logged['id']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")


@app.get("/api/stores/{store_id}/events")
async def get_store_events(
    store_id: str,
    limit: int = Query(100, le=1000),
    event_type: Optional[str] = None,
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get recent detection events for a store."""
    events = db.get_recent_events(store_id, limit=limit, event_type=event_type)
    return events


@app.get("/api/stores/{store_id}/seats/{seat_id}/events")
async def get_seat_events(
    store_id: str,
    seat_id: str,
    limit: int = Query(50, le=500),
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get detection events for a specific seat."""
    events = db.get_seat_events(store_id, seat_id, limit=limit)
    return events


# ============================================================================
# Statistics
# ============================================================================

@app.get("/api/stores/{store_id}/stats")
async def get_occupancy_stats(
    store_id: str,
    hours: int = Query(24, description="Number of hours to retrieve"),
    db: SupabaseClient = Depends(get_supabase_client)
):
    """Get occupancy statistics for a store."""
    from datetime import timedelta
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)

    stats = db.get_occupancy_stats(store_id, start_time, end_time)
    return stats


# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "CCTV Seat Detection API",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/")
async def root():
    """API root."""
    return {
        "message": "CCTV Seat Detection API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
