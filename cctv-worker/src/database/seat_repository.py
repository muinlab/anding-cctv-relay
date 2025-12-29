"""Supabase seats 테이블에서 ROI 설정 조회 - 캐싱 및 에러 처리 포함.

이 모듈은 Supabase에서 좌석 ROI 정보를 조회하며,
3단계 fallback (캐시 → 만료캐시 → 로컬 JSON)을 통해 안정성을 보장합니다.
"""
import time
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from threading import Lock

from .supabase_client import get_supabase_client, SupabaseClient

logger = logging.getLogger(__name__)


class SeatRepository:
    """좌석 ROI 정보 조회 - 캐싱 및 Fallback 포함."""

    # 클래스 레벨 캐시 (모든 인스턴스 공유)
    _cache: Dict[str, Dict[str, Any]] = {}
    _cache_lock = Lock()
    _cache_ttl = 60  # 60초 캐시 (ROI는 자주 변경되지 않음)

    def __init__(self, fallback_dir: Optional[Path] = None):
        """Initialize repository.

        Args:
            fallback_dir: Fallback JSON 저장 디렉토리 (기본: data/roi_configs)
        """
        self._client: Optional[SupabaseClient] = None
        self.fallback_dir = fallback_dir or Path("data/roi_configs")

    @property
    def client(self) -> SupabaseClient:
        """Lazy initialization of Supabase client."""
        if self._client is None:
            try:
                self._client = get_supabase_client()
            except Exception as e:
                logger.error(f"Supabase 클라이언트 초기화 실패: {e}")
                raise
        return self._client

    def get_seats_by_channel(self, store_id: str, channel_id: int) -> List[Dict[str, Any]]:
        """특정 채널에 보이는 좌석들의 ROI 조회 (캐시 우선).

        Args:
            store_id: 지점 ID
            channel_id: CCTV 채널 번호

        Returns:
            좌석 정보 리스트 [{seat_id, roi_polygon, seat_label}, ...]
            Supabase 및 fallback 모두 실패 시 빈 리스트 반환
        """
        cache_key = f"{store_id}:{channel_id}"

        # 1. 캐시 확인
        with self._cache_lock:
            if cache_key in self._cache:
                entry = self._cache[cache_key]
                if time.time() - entry['timestamp'] < self._cache_ttl:
                    logger.debug(f"Cache hit: {cache_key}")
                    return entry['data']
                else:
                    logger.debug(f"Cache expired: {cache_key}")

        # 2. Supabase 조회 시도
        try:
            response = (
                self.client.client.table('seats')
                .select('seat_id, roi_polygon, seat_label, channel_id')
                .eq('store_id', store_id)
                .eq('channel_id', channel_id)
                .eq('is_active', True)
                .execute()
            )
            data = response.data or []

            # 캐시 업데이트
            with self._cache_lock:
                self._cache[cache_key] = {
                    'data': data,
                    'timestamp': time.time()
                }

            # Fallback JSON도 업데이트 (다음 에러 대비)
            if data:
                self._save_fallback(cache_key, data)

            logger.debug(f"Supabase 조회 성공: {cache_key}, {len(data)} seats")
            return data

        except Exception as e:
            logger.warning(f"Supabase 조회 실패: {e}, fallback 사용")

            # 3. 만료된 캐시라도 있으면 사용 (stale cache)
            with self._cache_lock:
                if cache_key in self._cache:
                    logger.info(f"Stale cache 사용: {cache_key}")
                    return self._cache[cache_key]['data']

            # 4. 로컬 JSON fallback
            return self._load_fallback(cache_key)

    def get_all_seats_for_store(self, store_id: str) -> List[Dict[str, Any]]:
        """지점의 모든 좌석 조회 (채널 무관).

        Args:
            store_id: 지점 ID

        Returns:
            모든 좌석 정보 리스트
        """
        try:
            response = (
                self.client.client.table('seats')
                .select('seat_id, roi_polygon, seat_label, channel_id')
                .eq('store_id', store_id)
                .eq('is_active', True)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"전체 좌석 조회 실패: {e}")
            return []

    def _save_fallback(self, cache_key: str, data: List[Dict[str, Any]]) -> None:
        """Fallback JSON 저장.

        Args:
            cache_key: 캐시 키 (store_id:channel_id)
            data: 저장할 좌석 데이터
        """
        try:
            self.fallback_dir.mkdir(parents=True, exist_ok=True)
            # ':' 를 '_'로 변환하여 파일명 생성
            safe_filename = cache_key.replace(':', '_')
            path = self.fallback_dir / f"{safe_filename}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Fallback 저장: {path}")
        except Exception as e:
            logger.debug(f"Fallback 저장 실패: {e}")

    def _load_fallback(self, cache_key: str) -> List[Dict[str, Any]]:
        """Fallback JSON 로드.

        Args:
            cache_key: 캐시 키 (store_id:channel_id)

        Returns:
            저장된 좌석 데이터 또는 빈 리스트
        """
        try:
            safe_filename = cache_key.replace(':', '_')
            path = self.fallback_dir / f"{safe_filename}.json"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Fallback 로드 성공: {path}")
                    return data
        except Exception as e:
            logger.debug(f"Fallback 로드 실패: {e}")
        return []

    def invalidate_cache(
        self,
        store_id: Optional[str] = None,
        channel_id: Optional[int] = None
    ) -> None:
        """캐시 무효화.

        Args:
            store_id: 특정 지점만 무효화 (None이면 전체)
            channel_id: 특정 채널만 무효화 (store_id 필요)
        """
        with self._cache_lock:
            if store_id and channel_id is not None:
                # 특정 채널만 무효화
                key = f"{store_id}:{channel_id}"
                if key in self._cache:
                    del self._cache[key]
                    logger.debug(f"Cache invalidated: {key}")
            elif store_id:
                # 특정 지점의 모든 채널 무효화
                keys_to_remove = [
                    k for k in self._cache
                    if k.startswith(f"{store_id}:")
                ]
                for k in keys_to_remove:
                    del self._cache[k]
                logger.debug(f"Cache invalidated for store: {store_id}")
            else:
                # 전체 캐시 클리어
                self._cache.clear()
                logger.debug("All cache cleared")

    @classmethod
    def get_cache_stats(cls) -> Dict[str, Any]:
        """캐시 통계 조회 (디버깅용).

        Returns:
            캐시 상태 정보
        """
        with cls._cache_lock:
            now = time.time()
            stats = {
                'total_entries': len(cls._cache),
                'ttl_seconds': cls._cache_ttl,
                'entries': {}
            }
            for key, entry in cls._cache.items():
                age = now - entry['timestamp']
                stats['entries'][key] = {
                    'seat_count': len(entry['data']),
                    'age_seconds': round(age, 1),
                    'expired': age >= cls._cache_ttl
                }
            return stats


# 싱글톤 인스턴스
_seat_repository: Optional[SeatRepository] = None
_seat_repository_lock = Lock()


def get_seat_repository() -> SeatRepository:
    """Get or create SeatRepository singleton.

    Returns:
        SeatRepository 인스턴스
    """
    global _seat_repository
    if _seat_repository is None:
        with _seat_repository_lock:
            if _seat_repository is None:
                _seat_repository = SeatRepository()
    return _seat_repository


# CLI 테스트용
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    logging.basicConfig(level=logging.DEBUG)

    repo = get_seat_repository()
    store_id = "oryudong"
    channel_id = 1

    print(f"\n=== Testing SeatRepository ===")
    print(f"Store: {store_id}, Channel: {channel_id}")

    # 첫 번째 조회 (Supabase)
    print("\n1. First query (Supabase)...")
    seats = repo.get_seats_by_channel(store_id, channel_id)
    print(f"   Found {len(seats)} seats")

    # 두 번째 조회 (캐시)
    print("\n2. Second query (should be cached)...")
    seats = repo.get_seats_by_channel(store_id, channel_id)
    print(f"   Found {len(seats)} seats")

    # 캐시 통계
    print("\n3. Cache stats:")
    stats = SeatRepository.get_cache_stats()
    print(f"   {json.dumps(stats, indent=2)}")

    # 좌석 상세 정보
    if seats:
        print("\n4. Seat details:")
        for seat in seats[:3]:  # 최대 3개만 표시
            print(f"   - {seat['seat_id']}: {seat.get('seat_label', 'N/A')}")
            roi = seat.get('roi_polygon')
            if roi:
                print(f"     ROI points: {len(roi)}")
