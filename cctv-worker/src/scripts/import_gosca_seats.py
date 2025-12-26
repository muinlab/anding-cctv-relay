"""Import GoSca seat data into Supabase."""
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.gosca_client import GoScaClient
from src.database.supabase_client import get_supabase_client
from dotenv import load_dotenv

load_dotenv()


def import_store_and_seats(store_id: str):
    """Import store and seat data from GoSca to Supabase."""

    # Initialize clients
    gosca = GoScaClient(store_id=store_id)
    supabase = get_supabase_client()

    print(f"\n🔄 Importing data for store: {store_id}")

    # 1. Create store if not exists
    print("\n1️⃣ Creating store...")
    store_data = {
        'store_id': store_id.split('-')[1].lower() if '-' in store_id else store_id,
        'gosca_store_id': store_id,
        'store_name': f"앤딩 {store_id.split('-')[1]}점" if '-' in store_id else store_id,
        'rtsp_host': os.getenv('RTSP_HOST'),
        'rtsp_port': int(os.getenv('RTSP_PORT', 8554)),
        'total_channels': 16,
        'is_active': True
    }

    try:
        existing_store = supabase.get_store(store_data['store_id'])
        if existing_store:
            print(f"   ✓ Store already exists: {store_data['store_id']}")
        else:
            supabase.create_store(store_data)
            print(f"   ✓ Store created: {store_data['store_id']}")
    except Exception as e:
        print(f"   ⚠️  Store creation error: {e}")

    # 2. Fetch seats from GoSca
    print("\n2️⃣ Fetching seats from GoSca...")
    gosca_seats = gosca.fetch_seat_list()
    print(f"   ✓ Fetched {len(gosca_seats)} seats")

    # 3. Import seats
    print("\n3️⃣ Importing seats to Supabase...")
    created_count = 0
    updated_count = 0

    for seat in gosca_seats:
        seat_data = {
            'store_id': store_data['store_id'],
            'seat_id': seat['seat_id'],
            'chairtbl_id': seat['chairtbl_id'],
            'grid_row': seat['grid_row'],
            'grid_col': seat['grid_col'],
            'seat_type': seat.get('seat_type', 'daily'),
            'seat_label': seat.get('seat_label'),
            'is_active': True,
            # Placeholder ROI (to be configured later)
            'roi_polygon': [],
            'channel_id': None,
            'walls': seat.get('walls'),
            'metadata': {
                'gosca_data': seat
            }
        }

        try:
            existing_seat = supabase.get_seat(
                store_data['store_id'],
                seat['seat_id']
            )

            if existing_seat:
                # Update if needed
                updated_count += 1
            else:
                supabase.create_seat(seat_data)
                created_count += 1

                # Initialize seat status
                supabase.update_seat_status(
                    store_data['store_id'],
                    seat['seat_id'],
                    {
                        'status': 'empty',
                        'person_detected': False,
                        'object_detected': False,
                        'vacant_duration_seconds': 0
                    }
                )
        except Exception as e:
            print(f"   ⚠️  Error importing seat {seat['seat_id']}: {e}")

    print(f"   ✓ Created: {created_count}, Updated: {updated_count}")

    # 4. Summary
    print("\n📊 Import Summary:")
    print(f"   Store: {store_data['store_name']}")
    print(f"   Total seats: {len(gosca_seats)}")
    print(f"   Created: {created_count}")
    print(f"   Updated: {updated_count}")

    # 5. Verify
    print("\n✅ Verifying import...")
    seats = supabase.get_seats(store_data['store_id'])
    statuses = supabase.get_all_seat_statuses(store_data['store_id'])
    print(f"   Seats in DB: {len(seats)}")
    print(f"   Seat statuses: {len(statuses)}")

    return store_data['store_id']


def main():
    """Main import function."""
    print("=" * 60)
    print("GoSca → Supabase Seat Import Tool")
    print("=" * 60)

    # Get store ID from env or command line
    store_id = os.getenv('GOSCA_STORE_ID', 'Anding-Oryudongyeok-sca')
    if len(sys.argv) > 1:
        store_id = sys.argv[1]

    try:
        imported_store_id = import_store_and_seats(store_id)
        print(f"\n✅ Import completed successfully!")
        print(f"\n🔗 Next steps:")
        print(f"   1. Configure CCTV ROI for each seat")
        print(f"   2. Start real-time detection worker")
        print(f"   3. Access web UI: http://localhost:8000")

    except Exception as e:
        print(f"\n❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
