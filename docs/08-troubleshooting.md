# 문제 해결

## 연결 문제

### RTSP 연결 안됨

**증상**: go2rtc에서 스트림이 표시되지 않음

**확인 순서**:

```bash
# 1. NVR ping 테스트
ping 192.168.0.100

# 2. RTSP 포트 확인
nc -zv 192.168.0.100 554

# 3. RTSP URL 직접 테스트
docker run --rm linuxserver/ffmpeg \
  ffprobe "rtsp://admin:password@192.168.0.100:554/live_01"

# 4. go2rtc 로그 확인
docker logs go2rtc | grep -i error
```

**해결책**:
- NVR IP/포트 확인
- RTSP 경로 확인 (NVR 브랜드별로 다름)
- NVR에서 RTSP 활성화 확인
- 방화벽 확인

### Cloudflare Tunnel 연결 안됨

**증상**: 외부에서 접속 불가

```bash
# 1. cloudflared 상태 확인
docker logs cloudflared

# 2. 토큰 확인
echo $CLOUDFLARE_TUNNEL_TOKEN | base64 -d | jq .

# 3. go2rtc 로컬 접속 확인
curl http://localhost:1984/api
```

**해결책**:
- 토큰 재생성
- Cloudflare 대시보드에서 터널 상태 확인
- DNS 전파 대기 (최대 24시간)

### WebRTC 연결 실패

**증상**: HLS는 되는데 WebRTC가 안됨

```bash
# 브라우저 콘솔에서 ICE 연결 상태 확인
pc.iceConnectionState  // 'failed'면 문제
```

**해결책**:
- TURN 서버 추가 (NAT 통과용)
- HLS로 폴백 사용
- go2rtc의 WebRTC TCP 모드 확인

## 성능 문제

### CPU 사용량 100%

**원인**: YOLO 처리 과부하

```bash
# 프로세스 확인
docker stats

# cctv-worker CPU 확인
docker exec cctv-worker top -bn1 | head -20
```

**해결책**:

```bash
# 1. 감지 주기 늘리기
SNAPSHOT_INTERVAL=5  # 3초 → 5초

# 2. 채널 수 줄이기
ACTIVE_CHANNELS=1,2  # 4개 → 2개

# 3. 해상도 낮추기 (go2rtc에서 서브스트림 사용)
```

### 스트림 끊김

**증상**: 영상이 자주 끊김

**확인**:

```bash
# 네트워크 상태
iperf3 -c 192.168.0.100

# NVR 부하
# NVR WebUI에서 확인
```

**해결책**:
- 유선 연결 확인
- NVR 동시 접속 수 확인 (보통 4-8개 제한)
- 서브스트림 사용 (대역폭 절약)

### 메모리 부족

**증상**: 서비스가 자동 종료됨

```bash
# 메모리 확인
free -h

# OOM 킬러 로그
dmesg | grep -i oom
```

**해결책**:

```bash
# 1. 스왑 추가
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 2. 메모리 제한 설정
# docker-compose.yaml
deploy:
  resources:
    limits:
      memory: 1.5G
```

## 스트리밍 문제

### HLS 지연이 너무 큼 (>10초)

**해결책**:

```yaml
# go2rtc.yaml
hls:
  segment_duration: 1  # 기본 2초
  playlist_size: 3     # 기본 6
```

```typescript
// 프론트엔드 HLS.js 설정
new Hls({
  lowLatencyMode: true,
  liveSyncDuration: 1,
  liveMaxLatencyDuration: 3
})
```

### 영상 깨짐/아티팩트

**원인**: 코덱 호환성 또는 네트워크 문제

**해결책**:

```yaml
# go2rtc.yaml - 트랜스코딩 추가
streams:
  ch1:
    - "ffmpeg:rtsp://...#video=h264#hardware"
```

### 오디오가 안 나옴

**원인**: 오디오 스트림 없음 또는 코덱 미지원

```yaml
# go2rtc.yaml
streams:
  ch1:
    - "rtsp://...#video=copy#audio=opus"
```

## cctv-worker 문제

### YOLO 모델 로드 실패

```bash
# 모델 확인
docker exec cctv-worker ls -la /app/models/

# 모델 다운로드
docker exec cctv-worker python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"
```

### Supabase 연결 실패

```bash
# 환경변수 확인
docker exec cctv-worker printenv | grep SUPABASE

# 연결 테스트
docker exec cctv-worker python -c "
from supabase import create_client
import os
client = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_ROLE_KEY'))
print(client.table('stores').select('*').limit(1).execute())
"
```

### 좌석 상태가 업데이트 안됨

```bash
# 1. ROI 설정 확인
# Supabase에서 seat_roi_configs 테이블 확인

# 2. 감지 로그 확인
docker logs cctv-worker | grep -i "seat\|detect"

# 3. 스냅샷 확인
ls ~/anding-cctv-relay/data/snapshots/
```

## 시스템 문제

### 부팅 후 서비스 안 올라옴

```bash
# systemd 서비스 확인
sudo systemctl status anding-cctv

# 수동 시작
cd ~/anding-cctv-relay && docker compose up -d
```

### 디스크 가득 참

```bash
# 원인 파악
du -sh /*

# Docker 정리
docker system prune -a --volumes

# 로그 정리
sudo journalctl --vacuum-time=3d
rm -rf ~/anding-cctv-relay/logs/*
```

### SSH 접속 불가

```bash
# 물리적 접근 필요
# 모니터/키보드 연결 후:

# 네트워크 확인
ip a
ping 8.8.8.8

# SSH 서비스 확인
sudo systemctl status ssh
```

## 로그 분석

### 주요 로그 위치

| 서비스 | 로그 |
|--------|------|
| go2rtc | `docker logs go2rtc` |
| cctv-worker | `docker logs cctv-worker` |
| cloudflared | `docker logs cloudflared` |
| 시스템 | `journalctl -xe` |

### 에러 검색

```bash
# 모든 에러 찾기
docker compose logs 2>&1 | grep -i "error\|fail\|exception"

# 최근 1시간 로그
docker compose logs --since 1h
```

## 지원 요청 시 포함할 정보

```bash
# 시스템 정보 수집
echo "=== System ===" > debug.txt
uname -a >> debug.txt
free -h >> debug.txt
df -h >> debug.txt

echo "=== Docker ===" >> debug.txt
docker compose ps >> debug.txt
docker stats --no-stream >> debug.txt

echo "=== Logs ===" >> debug.txt
docker compose logs --tail 100 >> debug.txt 2>&1
```
