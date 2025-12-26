"""GoSca API client for fetching seat information."""
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
import json


@dataclass
class Seat:
    """Seat information from GoSca."""
    cell_id: str
    chairtbl_id: str
    row: int
    col: int
    seat_type: str  # 'fixed', 'daily', 'charging'
    is_occupied: bool
    user_name: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[int] = None
    walls: Dict[str, bool] = None  # top, bottom, left, right

    def __post_init__(self):
        if self.walls is None:
            self.walls = {}


class GoScaClient:
    """Client for fetching seat data from GoSca system.

    Supports multiple store locations via environment variables.
    """

    def __init__(self, store_id: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize GoSca client.

        Args:
            store_id: GoSca store ID (e.g., 'Anding-Oryudongyeok-sca')
                     If None, uses GOSCA_STORE_ID from settings
            base_url: GoSca API base URL
                     If None, uses GOSCA_BASE_URL from settings
        """
        from src.config import settings

        self.base_url = base_url or settings.GOSCA_BASE_URL
        self.store_id = store_id or settings.GOSCA_STORE_ID

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def fetch_seat_list(self) -> List[Seat]:
        """Fetch all seats from GoSca API.

        Returns:
            List of Seat objects
        """
        url = f"{self.base_url}/gosca/seatlist"
        params = {"pstore": self.store_id}

        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()

            # Parse response
            data = response.json()

            seats = []
            # API returns components array with seat data
            for component in data.get('components', []):
                # Only process chair type cells
                if component.get('celltype') == 'chair':
                    seat = self._parse_seat(component)
                    if seat:
                        seats.append(seat)

            return seats

        except requests.RequestException as e:
            print(f"Failed to fetch seat list: {e}")
            return []

    def _parse_seat(self, data: dict) -> Optional[Seat]:
        """Parse seat data from API response.

        Args:
            data: Raw seat data from API

        Returns:
            Seat object or None if parsing fails
        """
        try:
            # Determine seat type based on product name
            prdname = data.get('prdname', '')
            seat_type = 'daily'  # default

            if '고정석' in prdname or '주' in prdname:
                seat_type = 'fixed'
            elif '충전권' in prdname:
                seat_type = 'charging'

            # Parse wall positions
            walls = {
                'top': data.get('walltop') == 1,
                'bottom': data.get('wallbottom') == 1,
                'left': data.get('wallleft') == 1,
                'right': data.get('wallright') == 1,
            }

            # Create unique cell_id from section, row, col
            cell_id = f"{data.get('section', 0)}-{data.get('cell_row', 0)}-{data.get('cell_col', 0)}"

            # Get product price from first product if available
            products = data.get('product', [])
            price = products[0].get('pcost') if products else None

            return Seat(
                cell_id=cell_id,
                chairtbl_id=str(data.get('chairtbl_id', '')),
                row=int(data.get('cell_row', 0)),
                col=int(data.get('cell_col', 0)),
                seat_type=seat_type,
                is_occupied=data.get('cuseyn', 'N') == 'Y',
                user_name=data.get('uname'),
                duration=data.get('remaintimeval'),
                price=price,
                walls=walls
            )

        except Exception as e:
            print(f"Failed to parse seat data: {e}, data: {data}")
            return None

    def get_seat_grid(self) -> Dict[str, List[List[Optional[Seat]]]]:
        """Get seats organized in a grid layout.

        Returns:
            Dictionary with 'grid' (2D array) and 'seats' (flat list)
        """
        seats = self.fetch_seat_list()

        if not seats:
            return {'grid': [], 'seats': []}

        # Find grid dimensions
        max_row = max(seat.row for seat in seats) + 1
        max_col = max(seat.col for seat in seats) + 1

        # Initialize grid
        grid = [[None for _ in range(max_col)] for _ in range(max_row)]

        # Populate grid
        for seat in seats:
            grid[seat.row][seat.col] = seat

        return {
            'grid': grid,
            'seats': seats,
            'dimensions': {'rows': max_row, 'cols': max_col}
        }

    def get_available_seats(self) -> List[Seat]:
        """Get only available (unoccupied) seats.

        Returns:
            List of available Seat objects
        """
        seats = self.fetch_seat_list()
        return [seat for seat in seats if not seat.is_occupied]

    def get_occupied_seats(self) -> List[Seat]:
        """Get only occupied seats.

        Returns:
            List of occupied Seat objects
        """
        seats = self.fetch_seat_list()
        return [seat for seat in seats if seat.is_occupied]

    def get_seat_by_id(self, cell_id: str) -> Optional[Seat]:
        """Get specific seat by cell_id.

        Args:
            cell_id: Cell ID to search for

        Returns:
            Seat object or None if not found
        """
        seats = self.fetch_seat_list()
        for seat in seats:
            if seat.cell_id == cell_id:
                return seat
        return None


def export_seats_to_json(store_id: Optional[str] = None, output_path: Optional[str] = None):
    """Export seat data to JSON file for mapping to CCTV ROIs.

    Args:
        store_id: GoSca store ID (uses env default if None)
        output_path: Path to save JSON file (auto-generated if None)
    """
    from pathlib import Path

    client = GoScaClient(store_id=store_id)
    result = client.get_seat_grid()

    # Auto-generate output path based on store_id
    if output_path is None:
        store_name = client.store_id.replace('-', '_').lower()
        output_path = f"data/gosca_seats_{store_name}.json"

    # Convert Seat objects to dict for JSON serialization
    seats_data = []
    for seat in result['seats']:
        if seat:
            seats_data.append({
                'cell_id': seat.cell_id,
                'chairtbl_id': seat.chairtbl_id,
                'row': seat.row,
                'col': seat.col,
                'seat_type': seat.seat_type,
                'is_occupied': seat.is_occupied,
                'user_name': seat.user_name,
                'walls': seat.walls,
                # Add placeholder for CCTV mapping
                'cctv_mapping': {
                    'channel_id': None,
                    'roi_polygon': None,
                    'mapped': False
                }
            })

    output = {
        'store_id': client.store_id,
        'base_url': client.base_url,
        'dimensions': result['dimensions'],
        'total_seats': len(seats_data),
        'seats': seats_data
    }

    # Save to file
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ Exported {len(seats_data)} seats to {output_path}")


if __name__ == "__main__":
    # Add parent dir to path for imports
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    # Test the client
    client = GoScaClient()

    print("Fetching seat data from GoSca...")
    result = client.get_seat_grid()

    print(f"\n📊 Grid Dimensions: {result['dimensions']['rows']}x{result['dimensions']['cols']}")
    print(f"📍 Total Seats: {len(result['seats'])}")

    # Count by type
    seats = result['seats']
    fixed = sum(1 for s in seats if s and s.seat_type == 'fixed')
    daily = sum(1 for s in seats if s and s.seat_type == 'daily')
    charging = sum(1 for s in seats if s and s.seat_type == 'charging')

    print(f"\nSeat Types:")
    print(f"  - Fixed: {fixed}")
    print(f"  - Daily: {daily}")
    print(f"  - Charging: {charging}")

    # Occupancy
    occupied = len(client.get_occupied_seats())
    available = len(client.get_available_seats())
    occupancy_rate = (occupied / len(seats) * 100) if seats else 0

    print(f"\nOccupancy:")
    print(f"  - Occupied: {occupied}")
    print(f"  - Available: {available}")
    print(f"  - Rate: {occupancy_rate:.1f}%")

    # Export to JSON
    print("\nExporting to JSON...")
    export_seats_to_json()
