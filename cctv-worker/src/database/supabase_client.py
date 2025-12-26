"""Supabase client wrapper for CCTV seat detection system."""
import os
from typing import Optional, Dict, List, Any
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


class SupabaseClient:
    """Supabase client wrapper with convenience methods."""

    def __init__(self):
        """Initialize Supabase client."""
        url = os.getenv("SUPABASE_URL")
        # Try service key first, fall back to anon key
        key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")

        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_KEY) must be set in .env"
            )

        self.client: Client = create_client(url, key)

    # ============================================================================
    # Store Operations
    # ============================================================================

    def get_store(self, store_id: str) -> Optional[Dict[str, Any]]:
        """Get store information."""
        response = self.client.table('stores').select('*').eq('store_id', store_id).execute()
        return response.data[0] if response.data else None

    def list_stores(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """List all stores."""
        query = self.client.table('stores').select('*')
        if active_only:
            query = query.eq('is_active', True)
        response = query.execute()
        return response.data

    def create_store(self, store_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new store."""
        response = self.client.table('stores').insert(store_data).execute()
        if not response.data:
            raise ValueError(f"Failed to create store: {store_data.get('store_id')}")
        return response.data[0]

    # ============================================================================
    # Seat Operations
    # ============================================================================

    def get_seats(self, store_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all seats for a store."""
        query = self.client.table('seats').select('*').eq('store_id', store_id)
        if active_only:
            query = query.eq('is_active', True)
        response = query.execute()
        return response.data

    def get_seat(self, store_id: str, seat_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific seat."""
        response = (
            self.client.table('seats')
            .select('*')
            .eq('store_id', store_id)
            .eq('seat_id', seat_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def create_seat(self, seat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new seat."""
        response = self.client.table('seats').insert(seat_data).execute()
        if not response.data:
            raise ValueError(f"Failed to create seat: {seat_data.get('seat_id')}")
        return response.data[0]

    def update_seat_roi(
        self,
        store_id: str,
        seat_id: str,
        channel_id: int,
        roi_polygon: List[List[int]]
    ) -> Dict[str, Any]:
        """Update seat ROI mapping."""
        response = (
            self.client.table('seats')
            .update({
                'channel_id': channel_id,
                'roi_polygon': roi_polygon
            })
            .eq('store_id', store_id)
            .eq('seat_id', seat_id)
            .execute()
        )
        if not response.data:
            raise ValueError(f"Failed to update ROI for seat: {store_id}/{seat_id}")
        return response.data[0]

    # ============================================================================
    # Seat Status Operations
    # ============================================================================

    def get_seat_status(self, store_id: str, seat_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a seat."""
        response = (
            self.client.table('seat_status')
            .select('*')
            .eq('store_id', store_id)
            .eq('seat_id', seat_id)
            .execute()
        )
        return response.data[0] if response.data else None

    def get_all_seat_statuses(self, store_id: str) -> List[Dict[str, Any]]:
        """Get status of all seats in a store."""
        response = (
            self.client.table('seat_status')
            .select('*')
            .eq('store_id', store_id)
            .execute()
        )
        return response.data

    def update_seat_status(
        self,
        store_id: str,
        seat_id: str,
        status_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update seat status."""
        response = (
            self.client.table('seat_status')
            .upsert({
                'store_id': store_id,
                'seat_id': seat_id,
                **status_data
            })
            .execute()
        )
        if not response.data:
            raise ValueError(f"Failed to update status for seat: {store_id}/{seat_id}")
        return response.data[0]

    def get_vacant_seats(
        self,
        store_id: str,
        min_duration_seconds: int = 0
    ) -> List[Dict[str, Any]]:
        """Get vacant seats with optional minimum vacant duration."""
        query = (
            self.client.table('seat_status')
            .select('*')
            .eq('store_id', store_id)
            .eq('status', 'empty')
        )
        if min_duration_seconds > 0:
            query = query.gte('vacant_duration_seconds', min_duration_seconds)
        response = query.execute()
        return response.data

    def get_abandoned_seats(self, store_id: str) -> List[Dict[str, Any]]:
        """Get seats with abandoned items."""
        response = (
            self.client.table('seat_status')
            .select('*')
            .eq('store_id', store_id)
            .eq('status', 'abandoned')
            .execute()
        )
        return response.data

    # ============================================================================
    # Detection Event Operations
    # ============================================================================

    def log_detection_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Log a detection event."""
        response = self.client.table('detection_events').insert(event_data).execute()
        if not response.data:
            raise ValueError("Failed to log detection event")
        return response.data[0]

    def get_recent_events(
        self,
        store_id: str,
        limit: int = 100,
        event_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get recent detection events."""
        query = (
            self.client.table('detection_events')
            .select('*')
            .eq('store_id', store_id)
        )
        if event_type:
            query = query.eq('event_type', event_type)
        response = query.order('created_at', desc=True).limit(limit).execute()
        return response.data

    def get_seat_events(
        self,
        store_id: str,
        seat_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get events for a specific seat."""
        response = (
            self.client.table('detection_events')
            .select('*')
            .eq('store_id', store_id)
            .eq('seat_id', seat_id)
            .order('created_at', desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    # ============================================================================
    # Occupancy Statistics
    # ============================================================================

    def get_occupancy_stats(
        self,
        store_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get occupancy statistics."""
        query = (
            self.client.table('occupancy_stats')
            .select('*')
            .eq('store_id', store_id)
        )
        if start_time:
            query = query.gte('hour_slot', start_time.isoformat())
        if end_time:
            query = query.lte('hour_slot', end_time.isoformat())
        response = query.order('hour_slot', desc=True).execute()
        return response.data

    def upsert_hourly_stat(self, stat_data: Dict[str, Any]) -> Dict[str, Any]:
        """Upsert hourly occupancy statistic."""
        response = self.client.table('occupancy_stats').upsert(stat_data).execute()
        if not response.data:
            raise ValueError("Failed to upsert hourly stat")
        return response.data[0]

    # ============================================================================
    # Real-time Subscriptions
    # ============================================================================

    def subscribe_seat_status(self, store_id: str, callback):
        """Subscribe to seat status changes for a store.

        Args:
            store_id: Store ID to monitor
            callback: Function to call on updates, signature: callback(payload)
        """
        def filter_callback(payload):
            if payload['new'].get('store_id') == store_id:
                callback(payload)

        self.client.table('seat_status').on('UPDATE', filter_callback).subscribe()

    def subscribe_detection_events(self, store_id: str, callback):
        """Subscribe to detection events for a store.

        Args:
            store_id: Store ID to monitor
            callback: Function to call on new events, signature: callback(payload)
        """
        def filter_callback(payload):
            if payload['new'].get('store_id') == store_id:
                callback(payload)

        self.client.table('detection_events').on('INSERT', filter_callback).subscribe()

    # ============================================================================
    # System Logs
    # ============================================================================

    def log_system_event(
        self,
        store_id: Optional[str],
        log_level: str,
        component: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log system event."""
        self.client.table('system_logs').insert({
            'store_id': store_id,
            'log_level': log_level,
            'component': component,
            'message': message,
            'metadata': metadata
        }).execute()

    # ============================================================================
    # Views (Read-only)
    # ============================================================================

    def get_realtime_status_view(self, store_id: str) -> List[Dict[str, Any]]:
        """Get real-time status view."""
        response = (
            self.client.table('v_realtime_seat_status')
            .select('*')
            .eq('store_id', store_id)
            .execute()
        )
        return response.data

    def get_occupancy_summary_view(self, store_id: str) -> Dict[str, Any]:
        """Get occupancy summary view."""
        response = (
            self.client.table('v_store_occupancy_summary')
            .select('*')
            .eq('store_id', store_id)
            .execute()
        )
        return response.data[0] if response.data else None


# Singleton instance
_supabase_client: Optional[SupabaseClient] = None


def get_supabase_client() -> SupabaseClient:
    """Get or create Supabase client singleton."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client


# Example usage
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    # Test connection
    client = get_supabase_client()

    # List stores
    stores = client.list_stores()
    print(f"Found {len(stores)} stores:")
    for store in stores:
        print(f"  - {store['store_id']}: {store['store_name']}")

    # Get seats for first store
    if stores:
        store_id = stores[0]['store_id']
        seats = client.get_seats(store_id)
        print(f"\nFound {len(seats)} seats in {store_id}")

        # Get seat status
        statuses = client.get_all_seat_statuses(store_id)
        print(f"Found {len(statuses)} seat statuses")

        # Get occupancy summary
        summary = client.get_occupancy_summary_view(store_id)
        if summary:
            print(f"\nOccupancy: {summary['occupied_count']}/{summary['total_seats']}")
