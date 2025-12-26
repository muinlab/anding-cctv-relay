#!/usr/bin/env python3
"""Sync ROI configurations from JSON files to Supabase database.

Usage:
    python -m src.scripts.sync_roi_to_db                    # Sync all channels
    python -m src.scripts.sync_roi_to_db --channel 12       # Sync specific channel
    python -m src.scripts.sync_roi_to_db --store oryudong   # Specific store
    python -m src.scripts.sync_roi_to_db --dry-run          # Preview only
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings
from src.database.supabase_client import get_supabase_client


def load_roi_configs(channel_id: int = None) -> dict:
    """Load ROI configurations from JSON files.

    Returns:
        Dict mapping channel_id to config
    """
    roi_dir = settings.ROI_CONFIG_DIR
    configs = {}

    if channel_id:
        # Load specific channel
        config_file = roi_dir / f"channel_{channel_id}.json"
        if config_file.exists():
            with open(config_file) as f:
                configs[channel_id] = json.load(f)
    else:
        # Load all channels
        for config_file in roi_dir.glob("channel_*.json"):
            try:
                ch_id = int(config_file.stem.split("_")[1])
                with open(config_file) as f:
                    configs[ch_id] = json.load(f)
            except (ValueError, IndexError):
                continue

    return configs


def sync_to_database(
    store_id: str,
    configs: dict,
    dry_run: bool = False,
    seat_id_mapping: dict = None
) -> dict:
    """Sync ROI configurations to database.

    Args:
        store_id: Store identifier
        configs: Dict of channel_id -> ROI config
        dry_run: If True, don't actually update DB
        seat_id_mapping: Optional mapping from ROI seat ID to DB seat ID
                        e.g., {"9": "1-0-8", "10": "1-0-9"}

    Returns:
        Summary of operations
    """
    db = get_supabase_client()

    # Get existing seats from DB
    db_seats = db.get_seats(store_id, active_only=False)
    db_seat_map = {s['seat_id']: s for s in db_seats}

    results = {
        'updated': [],
        'skipped': [],
        'not_found': [],
        'errors': []
    }

    for channel_id, config in configs.items():
        print(f"\n📺 Channel {channel_id}: {len(config.get('seats', []))} seats")

        for seat_config in config.get('seats', []):
            roi_seat_id = seat_config['id']
            roi_polygon = seat_config['roi']

            # Map ROI seat ID to DB seat ID if mapping provided
            if seat_id_mapping and roi_seat_id in seat_id_mapping:
                db_seat_id = seat_id_mapping[roi_seat_id]
            else:
                # Try to find matching seat in DB
                # Strategy 1: Direct match
                if roi_seat_id in db_seat_map:
                    db_seat_id = roi_seat_id
                else:
                    # Strategy 2: Match by label (e.g., "Seat 9" -> find seat with label containing "9")
                    db_seat_id = None
                    for sid, seat in db_seat_map.items():
                        if seat.get('seat_label') and roi_seat_id in seat['seat_label']:
                            db_seat_id = sid
                            break

            if not db_seat_id or db_seat_id not in db_seat_map:
                print(f"  ⚠️  Seat '{roi_seat_id}' not found in DB (label: {seat_config.get('label')})")
                results['not_found'].append({
                    'roi_id': roi_seat_id,
                    'channel': channel_id,
                    'label': seat_config.get('label')
                })
                continue

            # Update database
            if dry_run:
                print(f"  🔍 Would update: {db_seat_id} <- channel={channel_id}, roi={len(roi_polygon)} points")
                results['skipped'].append(db_seat_id)
            else:
                try:
                    db.update_seat_roi(
                        store_id=store_id,
                        seat_id=db_seat_id,
                        channel_id=channel_id,
                        roi_polygon=roi_polygon
                    )
                    print(f"  ✅ Updated: {db_seat_id} <- channel={channel_id}, roi={len(roi_polygon)} points")
                    results['updated'].append(db_seat_id)
                except Exception as e:
                    print(f"  ❌ Error updating {db_seat_id}: {e}")
                    results['errors'].append({'seat_id': db_seat_id, 'error': str(e)})

    return results


def show_current_status(store_id: str):
    """Show current ROI configuration status."""
    db = get_supabase_client()
    seats = db.get_seats(store_id, active_only=False)

    print(f"\n📊 Current DB Status for '{store_id}':")
    print(f"   Total seats: {len(seats)}")

    # Count by channel
    by_channel = {}
    unmapped = []
    for seat in seats:
        ch = seat.get('channel_id')
        if ch:
            by_channel[ch] = by_channel.get(ch, 0) + 1
        else:
            unmapped.append(seat['seat_id'])

    print(f"\n   Mapped by channel:")
    for ch in sorted(by_channel.keys()):
        print(f"     Channel {ch}: {by_channel[ch]} seats")

    print(f"\n   Unmapped seats: {len(unmapped)}")
    if unmapped and len(unmapped) <= 10:
        print(f"     {', '.join(unmapped)}")

    # Check ROI configs
    roi_dir = settings.ROI_CONFIG_DIR
    print(f"\n📁 ROI Config Files ({roi_dir}):")
    for config_file in sorted(roi_dir.glob("channel_*.json")):
        with open(config_file) as f:
            config = json.load(f)
        print(f"     {config_file.name}: {len(config.get('seats', []))} seats")


def create_seat_id_mapping(store_id: str) -> dict:
    """Create interactive mapping between ROI seat IDs and DB seat IDs.

    This is needed because GoSca seat IDs (e.g., "1-0-8") don't match
    the simple IDs used in ROI config (e.g., "9").
    """
    db = get_supabase_client()
    seats = db.get_seats(store_id, active_only=False)

    print("\n🔗 Seat ID Mapping Helper")
    print("   GoSca uses format like '1-0-8', ROI uses '9'")
    print("   You may need to create a mapping file.\n")

    # Show DB seats
    print("   DB Seats (first 20):")
    for seat in seats[:20]:
        label = seat.get('seat_label', 'no label')
        ch = seat.get('channel_id', 'unmapped')
        print(f"     {seat['seat_id']:10} | {label:20} | channel: {ch}")

    if len(seats) > 20:
        print(f"     ... and {len(seats) - 20} more")

    return {}


def main():
    parser = argparse.ArgumentParser(description="Sync ROI configs to database")
    parser.add_argument('--store', type=str, default='oryudong', help='Store ID')
    parser.add_argument('--channel', type=int, help='Specific channel to sync')
    parser.add_argument('--dry-run', action='store_true', help='Preview without updating')
    parser.add_argument('--status', action='store_true', help='Show current status only')
    parser.add_argument('--mapping', type=str, help='JSON file with seat ID mapping')

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"ROI Config Sync Tool")
    print(f"Store: {args.store}")
    print(f"{'='*60}")

    if args.status:
        show_current_status(args.store)
        return

    # Load ROI configs
    configs = load_roi_configs(args.channel)
    print(f"\n📂 Loaded {len(configs)} channel config(s)")

    if not configs:
        print("   No ROI configs found!")
        print(f"   Expected location: {settings.ROI_CONFIG_DIR}/channel_*.json")
        return

    # Load seat ID mapping if provided
    seat_mapping = None
    if args.mapping:
        with open(args.mapping) as f:
            seat_mapping = json.load(f)
        print(f"   Loaded {len(seat_mapping)} seat ID mappings")

    # Sync to database
    results = sync_to_database(
        store_id=args.store,
        configs=configs,
        dry_run=args.dry_run,
        seat_id_mapping=seat_mapping
    )

    # Summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"  ✅ Updated: {len(results['updated'])}")
    print(f"  🔍 Skipped (dry-run): {len(results['skipped'])}")
    print(f"  ⚠️  Not found: {len(results['not_found'])}")
    print(f"  ❌ Errors: {len(results['errors'])}")

    if results['not_found']:
        print("\n⚠️  Seats not found in DB - need ID mapping:")
        for item in results['not_found'][:10]:
            print(f"     ROI id='{item['roi_id']}' (label: {item['label']}) on channel {item['channel']}")

        print("\n   Create a mapping file (mapping.json):")
        print('   {')
        for item in results['not_found'][:5]:
            print(f'     "{item["roi_id"]}": "1-0-X",  // {item["label"]}')
        print('   }')
        print(f"\n   Then run: python -m src.scripts.sync_roi_to_db --mapping mapping.json")


if __name__ == "__main__":
    main()
