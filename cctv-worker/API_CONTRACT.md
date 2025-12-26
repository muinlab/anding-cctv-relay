# cctv-worker 인터페이스 계약

이 문서는 cctv-worker와 외부 시스템 간의 인터페이스 계약을 정의합니다.

---

## 목차

1. [Supabase 테이블 스키마](#1-supabase-테이블-스키마)
2. [상태값 및 이벤트 타입](#2-상태값-및-이벤트-타입)
3. [환경변수](#3-환경변수)
4. [API 엔드포인트](#4-api-엔드포인트)
5. [데이터 흐름](#5-데이터-흐름)

---

## 1. Supabase 테이블 스키마

### 1.1 stores (지점 정보)

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `store_id` | `text` (PK) | 지점 고유 ID | `oryudong` |
| `store_name` | `text` | 지점 이름 | `앤딩 오류동역점` |
| `rtsp_host` | `text` | NVR IP 주소 | `192.168.0.100` |
| `rtsp_port` | `integer` | RTSP 포트 | `8554` |
| `active_channels` | `integer[]` | 활성 채널 목록 | `{1,2,3,4}` |
| `total_channels` | `integer` | 총 채널 수 | `16` |
| `is_active` | `boolean` | 활성화 여부 | `true` |
| `created_at` | `timestamptz` | 생성 시간 | |
| `updated_at` | `timestamptz` | 수정 시간 | |

### 1.2 seats (좌석 마스터)

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `id` | `uuid` (PK) | 좌석 UUID | |
| `store_id` | `text` (FK) | 지점 ID | `oryudong` |
| `seat_id` | `text` | 좌석 번호 | `A-01` |
| `channel_id` | `integer` | 카메라 채널 | `1` |
| `roi_polygon` | `jsonb` | ROI 폴리곤 좌표 | `[[100,100],[200,100],...]` |
| `seat_type` | `text` | 좌석 유형 | `fixed`, `hourly` |
| `label` | `text` | 표시 라벨 | `A열 1번` |
| `is_active` | `boolean` | 활성화 여부 | `true` |
| `created_at` | `timestamptz` | 생성 시간 | |

### 1.3 seat_status (좌석 실시간 상태)

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `id` | `uuid` (PK) | 상태 UUID | |
| `seat_id` | `uuid` (FK) | 좌석 UUID | |
| `store_id` | `text` | 지점 ID | `oryudong` |
| `status` | `text` | 현재 상태 | `empty`, `occupied`, `abandoned` |
| `person_detected` | `boolean` | 사람 감지 여부 | `true` |
| `detection_confidence` | `float` | 감지 신뢰도 | `0.85` |
| `last_person_seen` | `timestamptz` | 마지막 사람 감지 시간 | |
| `vacant_duration_seconds` | `integer` | 비어있는 시간(초) | `300` |
| `updated_at` | `timestamptz` | 상태 업데이트 시간 | |

### 1.4 detection_events (감지 이벤트 로그)

| 컬럼 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `id` | `uuid` (PK) | 이벤트 UUID | |
| `store_id` | `text` | 지점 ID | `oryudong` |
| `seat_id` | `text` | 좌석 번호 | `A-01` |
| `channel_id` | `integer` | 카메라 채널 | `1` |
| `event_type` | `text` | 이벤트 유형 | `person_enter` |
| `person_detected` | `boolean` | 사람 감지 여부 | `true` |
| `person_count` | `integer` | 감지된 사람 수 | `1` |
| `person_bboxes` | `jsonb` | 바운딩 박스 좌표 | `[[100,100,200,300]]` |
| `person_confidence` | `float` | 감지 신뢰도 | `0.92` |
| `processing_time_ms` | `integer` | 처리 시간(ms) | `45` |
| `created_at` | `timestamptz` | 이벤트 발생 시간 | |

---

## 2. 상태값 및 이벤트 타입

### 2.1 SeatStatus (좌석 상태)

| 값 | 설명 | 조건 |
|----|------|------|
| `empty` | 비어있음 | 사람 미감지 |
| `occupied` | 사용 중 | 사람 감지됨 |
| `abandoned` | 물건만 있음 | 10분 이상 사람 없이 물건 감지 |

### 2.2 EventType (이벤트 유형)

| 값 | 설명 | 상태 변화 |
|----|------|----------|
| `person_enter` | 사람 입장 | empty/abandoned → occupied |
| `person_leave` | 사람 퇴장 | occupied → empty |
| `abandoned_detected` | 물건 방치 감지 | empty/occupied → abandoned |
| `item_removed` | 물건 제거 | abandoned → empty |
| `status_change` | 기타 상태 변화 | - |

### 2.3 상태 전이 다이어그램

```
                    person_enter
         ┌─────────────────────────────┐
         │                             │
         ▼                             │
      ┌──────┐    person_leave    ┌────┴─────┐
      │ EMPTY│◄───────────────────│ OCCUPIED │
      └──┬───┘                    └────┬─────┘
         │                             │
         │  abandoned_detected         │ abandoned_detected
         │  (10min timeout)            │ (10min timeout)
         ▼                             ▼
      ┌──────────┐                     │
      │ ABANDONED│◄────────────────────┘
      └──┬───────┘
         │
         │ item_removed / person_enter
         │
         └─────────────► EMPTY / OCCUPIED
```

---

## 3. 환경변수

### 3.1 필수 환경변수

| 변수명 | 설명 | 예시 |
|--------|------|------|
| `SUPABASE_URL` | Supabase 프로젝트 URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Service Role 키 | `eyJ...` |
| `STORE_ID` | 현재 지점 ID | `oryudong` |
| `RTSP_USERNAME` | NVR 사용자명 | `admin` |
| `RTSP_PASSWORD` | NVR 비밀번호 | |

### 3.2 선택 환경변수

| 변수명 | 기본값 | 설명 |
|--------|--------|------|
| `RTSP_HOST` | `localhost` | RTSP 서버 호스트 |
| `RTSP_PORT` | `8554` | RTSP 서버 포트 |
| `YOLO_MODEL` | `yolov8n.pt` | YOLO 모델 파일 |
| `CONFIDENCE_THRESHOLD` | `0.3` | 감지 신뢰도 임계값 |
| `IOU_THRESHOLD` | `0.3` | IoU 임계값 |
| `SNAPSHOT_INTERVAL` | `3` | 프레임 캡처 간격(초) |
| `MAX_WORKERS` | `4` | 최대 워커 수 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |
| `DEBUG_STREAM_ENABLED` | `false` | 디버그 스트림 활성화 |
| `DEBUG_STREAM_PORT` | `8001` | 디버그 스트림 포트 |

---

## 4. API 엔드포인트

### 4.1 ROI 설정 API (포트 8001)

#### 채널 목록 조회
```http
GET /api/channels
```

응답:
```json
[
  {
    "channel_id": 1,
    "rtsp_path": "live_01",
    "config_exists": true
  }
]
```

#### 채널 스냅샷
```http
GET /api/channels/{channel_id}/snapshot
```

응답: `image/jpeg`

#### ROI 설정 조회
```http
GET /api/channels/{channel_id}/config
```

응답:
```json
{
  "camera_id": "branch01_cam1",
  "resolution": [1920, 1080],
  "seats": [
    {
      "id": "A-01",
      "roi": [[100,100], [200,100], [200,200], [100,200]],
      "type": "polygon",
      "label": "A열 1번"
    }
  ]
}
```

#### ROI 설정 저장
```http
POST /api/channels/{channel_id}/config
Content-Type: application/json

{
  "camera_id": "branch01_cam1",
  "resolution": [1920, 1080],
  "seats": [...]
}
```

### 4.2 디버그 스트림 API (DEBUG_STREAM_ENABLED=true)

#### 디버그 UI
```http
GET /debug/
```

응답: HTML 페이지

#### MJPEG 스트림
```http
GET /debug/stream/{channel_id}?fps=5
```

응답: `multipart/x-mixed-replace; boundary=frame`

#### 단일 스냅샷 (바운딩 박스 포함)
```http
GET /debug/snapshot/{channel_id}
```

응답: `image/jpeg`

#### 상태 조회
```http
GET /debug/status
```

응답:
```json
{
  "enabled": true,
  "store_id": "oryudong",
  "active_channels": [1, 2, 3, 4],
  "yolo_model": "yolov8n.pt",
  "confidence_threshold": 0.3,
  "iou_threshold": 0.3
}
```

---

## 5. 데이터 흐름

### 5.1 감지 → DB 업데이트 흐름

```
1. RTSP 프레임 캡처
   │
2. YOLO 사람 감지
   │  └─ 반환: [(x1,y1,x2,y2,confidence), ...]
   │
3. ROI 매칭
   │  └─ 폴리곤 내 사람 발(bottom center) 위치 확인
   │
4. 상태 결정
   │  ├─ 이전 상태와 비교
   │  └─ 이벤트 타입 결정
   │
5. Supabase 업데이트
   │  ├─ seat_status 테이블 UPDATE
   │  └─ detection_events 테이블 INSERT
   │
6. 반복 (3초 간격)
```

### 5.2 외부 시스템 연동

```
┌─────────────────────────────────────────────────────────────┐
│                      Supabase                                │
│  ┌─────────────┐  ┌─────────────┐  ┌───────────────────┐   │
│  │   stores    │  │seat_status  │  │ detection_events  │   │
│  └─────────────┘  └──────┬──────┘  └───────────────────┘   │
│                          │                                   │
│                    Realtime                                  │
│                          │                                   │
└──────────────────────────┼───────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │ admin-web  │  │admin-mobile│  │  GoSca     │
    │ (Next.js)  │  │ (React)    │  │ (연동 예정)│
    └────────────┘  └────────────┘  └────────────┘
```

---

## 버전 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|----------|
| 1.0 | 2024-12 | 최초 작성 |
