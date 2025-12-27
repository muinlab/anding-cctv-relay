# 스트리밍 기술 가이드

CCTV 릴레이 시스템에서 사용하는 스트리밍 기술을 정리한 학습 문서입니다.

---

## 목차

1. [영상 스트리밍 (WebRTC/STUN/TURN)](#1-영상-스트리밍-webrtcstunturn)
2. [데이터 스트리밍 (Supabase Realtime)](#2-데이터-스트리밍-supabase-realtime)
3. [전체 아키텍처](#3-전체-아키텍처)

---

## 1. 영상 스트리밍 (WebRTC/STUN/TURN)

### 1.1 왜 WebRTC인가?

| 프로토콜 | 지연시간 | 브라우저 지원 | 용도 |
|----------|----------|---------------|------|
| RTSP | ~100ms | X (플러그인 필요) | NVR/카메라 간 통신 |
| HLS | 2-10초 | O | 대규모 방송 |
| **WebRTC** | **~200ms** | **O** | **실시간 양방향** |

CCTV 모니터링은 **저지연 + 브라우저 지원**이 필요해서 WebRTC 선택.

### 1.2 NAT 문제와 해결

```
┌─────────────────────────────────────────────────────────────────┐
│                        인터넷                                    │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
    ┌────┴────┐                          ┌────┴────┐
    │  NAT A  │                          │  NAT B  │
    │ (공유기) │                          │ (공유기) │
    └────┬────┘                          └────┬────┘
         │                                    │
    ┌────┴────┐                          ┌────┴────┐
    │ go2rtc  │  ←── 직접 연결 불가 ──→   │ 브라우저 │
    │(서버)   │                          │(클라이언트)│
    └─────────┘                          └─────────┘
```

**문제**: 둘 다 사설 IP라 서로 찾을 수 없음

### 1.3 STUN (Session Traversal Utilities for NAT)

**역할**: "내 공인 IP가 뭐지?" 알려주는 서버

```
┌─────────┐                    ┌─────────────┐
│ go2rtc  │ ──── 나 누구야? ──→│ STUN 서버   │
│         │ ←── 너 1.2.3.4야 ──│(Google 등)  │
└─────────┘                    └─────────────┘
```

**설정 예시**:
```yaml
webrtc:
  candidates:
    - stun:stun.l.google.com:19302    # 무료
    - stun:stun1.l.google.com:19302
```

**한계**: 대칭 NAT (Symmetric NAT)에서는 안 됨
- 기업 방화벽
- 일부 모바일 네트워크
- 호텔/카페 와이파이

### 1.4 TURN (Traversal Using Relays around NAT)

**역할**: 직접 연결 안 되면 중계해주는 서버

```
┌─────────┐                    ┌─────────────┐                    ┌─────────┐
│ go2rtc  │ ──── 영상 ────────→│ TURN 서버   │────── 영상 ──────→│ 브라우저 │
│         │ ←─── 명령 ─────────│  (릴레이)   │←───── 명령 ───────│         │
└─────────┘                    └─────────────┘                    └─────────┘
```

**설정 예시**:
```yaml
webrtc:
  ice_servers:
    - urls: [stun:stun.l.google.com:19302]
    - urls: [turn:turn.metered.ca:443?transport=tcp]
      username: your-username
      credential: your-password
```

### 1.5 ICE (Interactive Connectivity Establishment)

STUN과 TURN을 조합해서 **최적의 경로**를 찾는 프로토콜

```
연결 시도 순서:
1. 로컬 연결 (같은 네트워크) ─────→ 성공하면 사용
2. STUN으로 공인 IP 확인 ─────────→ P2P 연결 시도
3. TURN 릴레이 ───────────────────→ 최후의 수단
```

### 1.6 우리 시스템에서의 흐름

```
┌──────────┐     RTSP      ┌──────────┐    WebRTC     ┌──────────┐
│   NVR    │ ────────────→ │  go2rtc  │ ────────────→ │ 브라우저  │
│ (카메라)  │  192.168.x.x  │  (변환)   │   STUN/TURN  │ (admin)  │
└──────────┘               └──────────┘               └──────────┘
                                │
                                │ HLS (폴백)
                                ↓
                           WebRTC 실패 시
                           자동으로 HLS 전환
                           (지연 증가하지만 안정적)
```

### 1.7 TURN 서버 옵션 비교

| 서비스 | 무료 티어 | 가격 | 특징 |
|--------|-----------|------|------|
| [Metered.ca](https://www.metered.ca) | 500GB/월 | $0.40/GB 초과 | 설정 간단 |
| [Twilio](https://www.twilio.com/stun-turn) | 없음 | $0.40/GB | 안정적 |
| [Cloudflare Calls](https://developers.cloudflare.com/calls/) | 제한적 | 문의 | CF 통합 |
| [Coturn](https://github.com/coturn/coturn) (자체) | 무제한 | 서버 비용 | 관리 필요 |

### 1.8 디버깅 팁

```bash
# WebRTC 연결 상태 확인 (Chrome)
chrome://webrtc-internals/

# STUN 테스트
# https://webrtc.github.io/samples/src/content/peerconnection/trickle-ice/

# go2rtc 로그에서 ICE 후보 확인
docker logs go2rtc 2>&1 | grep -i ice
```

---

## 2. 데이터 스트리밍 (Supabase Realtime)

### 2.1 왜 Supabase Realtime인가?

| 방식 | 장점 | 단점 |
|------|------|------|
| Polling | 구현 간단 | 지연, 서버 부하 |
| WebSocket (직접) | 실시간 | 서버 구현 필요 |
| **Supabase Realtime** | **DB 변경 자동 감지** | **Supabase 종속** |

### 2.2 작동 원리

```
┌─────────────────────────────────────────────────────────────────┐
│                         Supabase                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │  PostgreSQL  │────→│   Realtime   │────→│  WebSocket   │    │
│  │   (테이블)    │     │   (감지)     │     │   (브로드캐스트)│    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│         ↑                                          │            │
│     INSERT/UPDATE                                  │            │
└─────────────────────────────────────────────────────┼────────────┘
          ↑                                          │
          │                                          ↓
    ┌─────┴─────┐                            ┌─────────────┐
    │cctv-worker│                            │  클라이언트   │
    │  (YOLO)   │                            │ (admin-web) │
    └───────────┘                            └─────────────┘
```

### 2.3 YOLO 디텍션 → DB 흐름

```python
# cctv-worker 내부 흐름

1. RTSP 프레임 캡처 (3초마다)
   │
   ↓
2. YOLO 추론
   persons = model.predict(frame)
   # 결과: [(x1, y1, x2, y2, confidence), ...]
   │
   ↓
3. ROI 매칭
   for person in persons:
       foot_point = (x1+x2)/2, y2  # 발 위치
       for seat in seats:
           if point_in_polygon(foot_point, seat.roi):
               seat.occupied = True
   │
   ↓
4. Supabase 업데이트
   # seat_status 테이블 UPDATE
   supabase.table('seat_status').upsert({
       'seat_id': seat.id,
       'status': 'occupied',
       'person_detected': True,
       'detection_confidence': 0.92
   })

   # detection_events 테이블 INSERT
   supabase.table('detection_events').insert({
       'event_type': 'person_enter',
       'seat_id': seat.id,
       ...
   })
```

### 2.4 클라이언트 구독 코드

```typescript
// Next.js / React에서 사용

import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// 좌석 상태 변경 구독
const channel = supabase
  .channel('seat-changes')
  .on(
    'postgres_changes',
    {
      event: 'UPDATE',           // INSERT, UPDATE, DELETE, *
      schema: 'public',
      table: 'seat_status',
      filter: `store_id=eq.${storeId}`
    },
    (payload) => {
      console.log('변경된 좌석:', payload.new)
      // payload.new = { seat_id, status, person_detected, ... }

      // UI 업데이트
      setSeatStatus(prev => ({
        ...prev,
        [payload.new.seat_id]: payload.new.status
      }))
    }
  )
  .subscribe()

// 컴포넌트 언마운트 시 정리
return () => {
  supabase.removeChannel(channel)
}
```

### 2.5 이벤트 타입 정리

| 이벤트 | 발생 조건 | payload.new |
|--------|-----------|-------------|
| `person_enter` | 빈 자리에 사람 감지 | `{ status: 'occupied' }` |
| `person_leave` | 사람이 자리 비움 | `{ status: 'empty' }` |
| `abandoned_detected` | 10분간 사람 없이 물건만 | `{ status: 'abandoned' }` |

### 2.6 상태 전이 다이어그램

```
                    person_enter
         ┌─────────────────────────────┐
         │                             │
         ▼                             │
      ┌──────┐    person_leave    ┌────┴─────┐
      │ EMPTY│◄───────────────────│ OCCUPIED │
      └──┬───┘                    └────┬─────┘
         │                             │
         │  10분 타임아웃               │ 10분 타임아웃
         │  (물건 감지)                 │ (물건 감지)
         ▼                             ▼
      ┌──────────────────────────────────┐
      │           ABANDONED              │
      └──────────────────────────────────┘
                    │
                    │ item_removed / person_enter
                    ↓
              EMPTY / OCCUPIED
```

### 2.7 디버깅 팁

```sql
-- 최근 이벤트 조회
SELECT * FROM detection_events
WHERE store_id = 'oryudong'
ORDER BY created_at DESC
LIMIT 20;

-- 현재 좌석 상태
SELECT seat_id, status, person_detected, updated_at
FROM seat_status
WHERE store_id = 'oryudong';
```

```bash
# cctv-worker 로그 확인
docker logs -f cctv-worker | grep -E "(detected|status|update)"
```

---

## 3. 전체 아키텍처

### 3.1 데이터 흐름 종합

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              현장 (오류동역점)                                │
│  ┌─────────┐     RTSP      ┌─────────┐     RTSP      ┌─────────────┐       │
│  │   NVR   │ ───────────→  │ go2rtc  │ ───────────→  │ cctv-worker │       │
│  │(16채널) │  192.168.0.x  │ (변환)   │  localhost    │   (YOLO)    │       │
│  └─────────┘               └────┬────┘               └──────┬──────┘       │
│                                 │                           │               │
│                                 │ WebRTC/HLS                │ DB 업데이트   │
│                                 │ (STUN/TURN)               │               │
└─────────────────────────────────┼───────────────────────────┼───────────────┘
                                  │                           │
                    ┌─────────────┼───────────────────────────┼─────────────┐
                    │             │         인터넷             │             │
                    │             ▼                           ▼             │
                    │      ┌─────────────┐             ┌───────────┐       │
                    │      │  Cloudflare │             │ Supabase  │       │
                    │      │   Tunnel    │             │ (Realtime)│       │
                    │      └──────┬──────┘             └─────┬─────┘       │
                    │             │                          │             │
                    └─────────────┼──────────────────────────┼─────────────┘
                                  │                          │
                    ┌─────────────┼──────────────────────────┼─────────────┐
                    │             ▼                          ▼             │
                    │      ┌───────────────────────────────────────┐       │
                    │      │              admin-web                │       │
                    │      │  ┌─────────────┐  ┌─────────────────┐ │       │
                    │      │  │ 영상 뷰어    │  │ 좌석 현황 대시보드 │ │       │
                    │      │  │ (WebRTC)    │  │ (Realtime)      │ │       │
                    │      │  └─────────────┘  └─────────────────┘ │       │
                    │      └───────────────────────────────────────┘       │
                    │                      클라이언트                        │
                    └──────────────────────────────────────────────────────┘
```

### 3.2 지연시간 비교

| 구간 | 기술 | 지연시간 |
|------|------|----------|
| NVR → go2rtc | RTSP | ~100ms |
| go2rtc → 브라우저 | WebRTC (STUN) | ~200ms |
| go2rtc → 브라우저 | WebRTC (TURN) | ~500ms |
| go2rtc → 브라우저 | HLS (폴백) | 2-5초 |
| cctv-worker → Supabase | HTTPS | ~100ms |
| Supabase → 브라우저 | WebSocket | ~50ms |

**총 영상 지연**: ~300ms (WebRTC) ~ 5초 (HLS)
**총 데이터 지연**: ~150ms

### 3.3 장애 대응

| 장애 상황 | 자동 대응 |
|-----------|-----------|
| WebRTC 연결 실패 | HLS로 폴백 |
| STUN 실패 | TURN으로 시도 |
| TURN 실패 | HLS로 폴백 |
| Supabase 연결 끊김 | 자동 재연결 |
| NVR 연결 끊김 | 재시도 + 알림 |

---

## 참고 자료

- [WebRTC 공식 문서](https://webrtc.org/)
- [STUN/TURN 이해하기](https://webrtc.github.io/samples/)
- [Supabase Realtime 문서](https://supabase.com/docs/guides/realtime)
- [go2rtc GitHub](https://github.com/AlexxIT/go2rtc)
