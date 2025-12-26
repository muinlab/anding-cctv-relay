# cctv-worker 연동

## 개요

cctv-worker는 CCTV 영상에서 YOLO로 사람을 감지하고 좌석 상태를 Supabase에 업데이트합니다.

```
go2rtc (RTSP 출력) → cctv-worker (YOLO) → Supabase (좌석 상태)
           ↓
      :8554/ch1
```

## 아키텍처

```
┌──────────────────────────────────────────────────────────────┐
│                      cctv-worker                              │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐   프레임    ┌──────────────┐              │
│  │ RTSPClient   │ ─────────▶ │ PersonDetector│              │
│  │              │   (3초)    │   (YOLOv8n)   │              │
│  └──────────────┘            └───────┬───────┘              │
│         ▲                            │                       │
│         │                            │ 바운딩 박스            │
│   rtsp://localhost:8554/ch1          ▼                       │
│         │                    ┌──────────────┐               │
│         │                    │  ROIMatcher  │               │
│         │                    │ (좌석 매칭)   │               │
│         │                    └───────┬───────┘              │
│         │                            │                       │
│  ┌──────┴─────┐                      │ 점유 상태             │
│  │  go2rtc    │                      ▼                       │
│  └────────────┘              ┌──────────────┐               │
│                              │  Supabase    │               │
│                              │  (Realtime)  │               │
│                              └──────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## Docker 이미지

### 빌드 (개발용)

```bash
# anding-study-cafe 레포에서
cd apps/cctv-worker
docker build -t anding-cctv-worker:local .
```

### 레지스트리 (운영용)

```bash
# GitHub Container Registry
docker pull ghcr.io/muinlab/anding-cctv-worker:latest
```

## 환경변수

```bash
# RTSP 소스 (go2rtc의 RTSP 출력)
RTSP_HOST=localhost
RTSP_PORT=8554
RTSP_USERNAME=          # go2rtc는 인증 없음
RTSP_PASSWORD=

# 지점 ID
STORE_ID=oryudong

# 활성 채널
ACTIVE_CHANNELS=1,2,3,4

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# YOLO 설정
YOLO_MODEL=yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
IOU_THRESHOLD=0.3

# 처리 주기
SNAPSHOT_INTERVAL=3     # 초

# 로그
LOG_LEVEL=INFO
```

## RTSP URL 매핑

go2rtc가 RTSP 서버로도 동작하므로:

| NVR 원본 | go2rtc RTSP 출력 |
|---------|------------------|
| `rtsp://admin:pass@192.168.0.100:554/live_01` | `rtsp://localhost:8554/ch1` |
| `rtsp://admin:pass@192.168.0.100:554/live_02` | `rtsp://localhost:8554/ch2` |

cctv-worker는 `localhost:8554`로 연결하면 됨.

## docker-compose 설정

```yaml
cctv-worker:
  image: ghcr.io/muinlab/anding-cctv-worker:latest
  container_name: cctv-worker
  restart: unless-stopped
  depends_on:
    go2rtc:
      condition: service_healthy  # go2rtc가 준비될 때까지 대기
  environment:
    - STORE_ID=${STORE_ID}
    - RTSP_HOST=localhost
    - RTSP_PORT=8554
    - SUPABASE_URL=${SUPABASE_URL}
    - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
  volumes:
    - ./data/snapshots:/app/data/snapshots
    - ./logs/worker:/app/logs
```

## 로그 확인

```bash
# 실시간 로그
docker logs -f cctv-worker

# 최근 100줄
docker logs --tail 100 cctv-worker
```

### 정상 로그 예시

```
INFO - Starting worker for store: oryudong
INFO - Channels: [1, 2, 3, 4]
INFO - Channel 1: Connected to rtsp://localhost:8554/ch1
INFO - Channel 1: Frame captured, 2 persons detected
INFO - Channel 1: Seat A1 - occupied (confidence: 0.87)
INFO - Status updated: seat_id=xxx status=occupied
```

## ROI 설정

좌석별 ROI(관심 영역)는 Supabase `seat_roi_configs` 테이블에서 관리:

```sql
SELECT * FROM seat_roi_configs
WHERE store_id = 'oryudong';
```

### ROI 설정 방법

1. admin-web의 CCTV 설정 페이지 사용
2. 또는 직접 DB 업데이트

```sql
INSERT INTO seat_roi_configs (store_id, channel_id, seat_id, roi_polygon)
VALUES (
  'oryudong',
  1,
  'seat-a1-uuid',
  '[[100,100],[200,100],[200,200],[100,200]]'
);
```

## 문제 해결

### RTSP 연결 실패

```bash
# go2rtc RTSP 출력 테스트
docker exec -it cctv-worker \
  ffprobe rtsp://localhost:8554/ch1
```

### YOLO 모델 로드 실패

```bash
# 모델 파일 확인
docker exec -it cctv-worker ls -la /app/models/
```

### Supabase 연결 실패

```bash
# 환경변수 확인
docker exec -it cctv-worker printenv | grep SUPABASE
```

## 성능 최적화

### CPU 사용량 줄이기

```bash
# 감지 주기 늘리기
SNAPSHOT_INTERVAL=5  # 기본 3초 → 5초

# 저해상도 스트림 사용 (go2rtc에서 서브스트림 설정)
```

### 메모리 최적화

```yaml
# docker-compose.yaml
deploy:
  resources:
    limits:
      memory: 2G
```
