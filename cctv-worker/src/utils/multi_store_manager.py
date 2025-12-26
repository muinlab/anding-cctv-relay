"""Multi-store management for GoSca seat monitoring."""
from typing import List, Dict
from .gosca_client import GoScaClient, Seat


class MultiStoreManager:
    """Manage multiple store locations."""

    # 지점 목록 (확장 가능)
    STORES = {
        'oryudong': 'Anding-Oryudongyeok-sca',
        'gangnam': 'Anding-Gangnam-sca',  # 예시
        'hongdae': 'Anding-Hongdae-sca',  # 예시
    }

    def __init__(self):
        self.clients: Dict[str, GoScaClient] = {}

    def get_client(self, store_key: str) -> GoScaClient:
        """Get or create client for specific store.

        Args:
            store_key: Store key from STORES dict

        Returns:
            GoScaClient instance
        """
        if store_key not in self.clients:
            store_id = self.STORES.get(store_key)
            if not store_id:
                raise ValueError(f"Unknown store: {store_key}. Available: {list(self.STORES.keys())}")

            self.clients[store_key] = GoScaClient(store_id=store_id)

        return self.clients[store_key]

    def get_all_seats(self) -> Dict[str, List[Seat]]:
        """Fetch seats from all stores.

        Returns:
            Dictionary mapping store_key to list of seats
        """
        all_seats = {}

        for store_key in self.STORES.keys():
            try:
                client = self.get_client(store_key)
                seats = client.fetch_seat_list()
                all_seats[store_key] = seats
                print(f"✅ {store_key}: {len(seats)} seats")
            except Exception as e:
                print(f"❌ {store_key}: Failed - {e}")
                all_seats[store_key] = []

        return all_seats

    def get_total_occupancy(self) -> Dict[str, Dict]:
        """Get occupancy summary for all stores.

        Returns:
            Dictionary with occupancy stats per store
        """
        summary = {}

        for store_key, seats in self.get_all_seats().items():
            if not seats:
                continue

            occupied = sum(1 for s in seats if s.is_occupied)
            total = len(seats)
            rate = (occupied / total * 100) if total > 0 else 0

            summary[store_key] = {
                'total': total,
                'occupied': occupied,
                'available': total - occupied,
                'occupancy_rate': round(rate, 1)
            }

        return summary

    def export_all_stores(self):
        """Export seat data for all stores."""
        for store_key, store_id in self.STORES.items():
            try:
                from .gosca_client import export_seats_to_json
                export_seats_to_json(store_id=store_id)
                print(f"✅ Exported {store_key}")
            except Exception as e:
                print(f"❌ Failed to export {store_key}: {e}")


if __name__ == "__main__":
    # Test multi-store manager
    manager = MultiStoreManager()

    print("=" * 60)
    print("Multi-Store Occupancy Summary")
    print("=" * 60)

    summary = manager.get_total_occupancy()

    for store_key, stats in summary.items():
        print(f"\n📍 {store_key.upper()}")
        print(f"   Total: {stats['total']} seats")
        print(f"   Occupied: {stats['occupied']}")
        print(f"   Available: {stats['available']}")
        print(f"   Rate: {stats['occupancy_rate']}%")

    print("\n" + "=" * 60)
