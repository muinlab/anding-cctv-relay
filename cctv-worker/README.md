# CCTV Worker

YOLO 기반 CCTV 좌석 감지 워커. RTSP 스트림에서 사람을 감지하고 ROI 매칭을 통해 좌석 점유 상태를 실시간으로 Supabase에 업데이트합니다.

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        CCTV Worker                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  RTSPClient  │───▶│ PersonDetector│───▶│  ROIMatcher  │       │
│  │              │    │   (YOLO)     │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                                        │               │
│         │ 프레임 캡처 (3초)                      │ 좌석 상태      │
│         ▼                                        ▼               │
│  ┌──────────────┐                        ┌──────────────┐       │
│  │     NVR      │                        │   Supabase   │       │
│  │  (RTSP 소스)  │                        │  (Realtime)  │       │
│  └──────────────┘                        └──────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## 디렉토리 구조

```
cctv-worker/
├── src/
│   ├── api/               # FastAPI 엔드포인트
│   │   ├── roi_config_api.py
│   │   └── seats_api.py
│   ├── config/            # 설정
│   │   └── settings.py
│   ├── core/              # 핵심 로직
│   │   ├── detector.py    # YOLO PersonDetector
│   │   └── roi_matcher.py # ROI 폴리곤 매칭
│   ├── database/          # DB 연동
│   │   └── supabase_client.py
│   ├── utils/             # 유틸리티
│   │   ├── rtsp_client.py
│   │   ├── gosca_client.py
│   │   └── logger.py
│   └── workers/           # 워커 프로세스
│       └── detection_worker.py
├── data/
│   ├── roi_configs/       # ROI 설정 JSON (백업용)
│   └── snapshots/         # 캡처 이미지
├── logs/                  # 로그 파일
├── pyproject.toml
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

## 설치

### 요구사항

- Python 3.11+
- CUDA 지원 GPU (선택, CPU로도 동작)

### 로컬 설치

```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 또는 pyproject.toml 사용
pip install -e .
```

### Docker 설치

```bash
docker build -t cctv-worker .
```

## 환경 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 설정합니다:

```bash
cp .env.example .env
```

### 필수 환경변수

```env
# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGc...

# Store 식별자
STORE_ID=oryudong

# RTSP 인증 (NVR 접속)
RTSP_USERNAME=admin
RTSP_PASSWORD=your_password
```

### 선택 환경변수

```env
# YOLO 설정
YOLO_MODEL=yolov8n.pt
CONFIDENCE_THRESHOLD=0.5
IOU_THRESHOLD=0.3

# 처리 설정
SNAPSHOT_INTERVAL=3      # 프레임 캡처 간격 (초)
MAX_WORKERS=4            # 최대 채널 워커 수

# 디버그
DEBUG=false
LOG_LEVEL=INFO
```

## 실행

### 기본 실행

```bash
# 단일 지점 실행 (DB에서 설정 로드)
python -m src.workers.detection_worker --store oryudong

# 특정 채널만 실행
python -m src.workers.detection_worker --store oryudong --channels 1,2,3,4
```

### Docker 실행

```bash
# 단일 컨테이너
docker run -d \
  --name cctv-worker \
  --env-file .env \
  cctv-worker

# docker-compose
docker-compose up -d
```

### systemd 서비스 (배포용)

```ini
# /etc/systemd/system/cctv-worker.service
[Unit]
Description=CCTV Seat Detection Worker
After=network.target

[Service]
Type=simple
User=cctv
WorkingDirectory=/opt/cctv-worker
ExecStart=/opt/cctv-worker/venv/bin/python -m src.workers.detection_worker
Restart=always
RestartSec=10
Environment=STORE_ID=oryudong

[Install]
WantedBy=multi-user.target
```

## API 서버 (선택)

ROI 설정 및 좌석 관리 API 서버:

```bash
# API 서버 실행
uvicorn src.api.roi_config_api:app --host 0.0.0.0 --port 8000
```

### 주요 엔드포인트

- `GET /health` - 헬스체크
- `GET /snapshot/{channel_id}` - RTSP 스냅샷
- `POST /roi/{channel_id}` - ROI 설정 저장
- `GET /status` - 전체 좌석 상태

## 데이터 흐름

```
1. Worker 시작
   └─▶ DB에서 store 설정 로드 (RTSP 호스트, 채널 목록)
   └─▶ DB에서 seats 로드 (ROI 폴리곤)

2. 채널별 프로세스 생성
   └─▶ RTSP 연결
   └─▶ YOLO 모델 로드

3. 감지 루프 (3초 간격)
   └─▶ 프레임 캡처
   └─▶ YOLO 사람 감지
   └─▶ ROI 매칭 (IoU 계산)
   └─▶ 좌석 상태 업데이트 (Supabase)
   └─▶ 이벤트 로그 (상태 변경 시)
```

## 로그

구조화된 JSON 로그를 사용합니다:

```json
{
  "timestamp": "2024-12-11T09:30:00.123Z",
  "level": "INFO",
  "component": "channel_1_worker",
  "store_id": "oryudong",
  "message": "Status changed",
  "seat_id": "A-01",
  "previous_status": "empty",
  "new_status": "occupied"
}
```

## 트러블슈팅

### RTSP 연결 실패

```bash
# RTSP 연결 테스트
python -m src.test_rtsp --channel 1

# ffmpeg로 직접 테스트
ffmpeg -rtsp_transport tcp -i "rtsp://admin:pass@192.168.1.100:554/live_01" -frames:v 1 test.jpg
```

### YOLO 모델 로드 실패

```bash
# 모델 다운로드
python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Supabase 연결 실패

```bash
# 연결 테스트
python -m src.database.supabase_client
```

## 성능 튜닝

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `SNAPSHOT_INTERVAL` | 3 | 프레임 캡처 간격 (초). 낮추면 실시간성 향상, 부하 증가 |
| `CONFIDENCE_THRESHOLD` | 0.5 | YOLO 신뢰도 임계값. 낮추면 감지율 향상, 오탐 증가 |
| `IOU_THRESHOLD` | 0.3 | ROI 매칭 IoU 임계값. 낮추면 매칭 범위 확대 |

## 라이선스

MIT
