# go2rtc 설정

## go2rtc란?

경량 스트리밍 서버로 RTSP를 WebRTC/HLS/MJPEG로 변환

- GitHub: https://github.com/AlexxIT/go2rtc
- 저지연 WebRTC 지원
- 트랜스코딩 없이 패스스루 가능 (CPU 절약)

## 설정 파일 구조

```yaml
# go2rtc/go2rtc.yaml

log:
  level: info  # debug, info, warn, error

api:
  listen: ":1984"  # WebUI 포트
  origin: "*"      # CORS

rtsp:
  listen: ":8554"  # RTSP 출력 (cctv-worker용)

webrtc:
  listen: ":8555/tcp"
  candidates:
    - stun:stun.l.google.com:19302

streams:
  ch1:
    - "rtsp://user:pass@192.168.0.100:554/live_01"
```

## 스트림 소스 형식

### 일반 RTSP

```yaml
streams:
  camera1: rtsp://user:pass@192.168.0.100:554/stream1
```

### 다중 소스 (폴백)

```yaml
streams:
  camera1:
    - rtsp://user:pass@192.168.0.100:554/main    # 메인 스트림
    - rtsp://user:pass@192.168.0.100:554/sub     # 서브 스트림 (폴백)
```

### FFmpeg 트랜스코딩

```yaml
streams:
  camera1:
    - "ffmpeg:rtsp://user:pass@ip/stream#video=h264#audio=opus"
```

## NVR 브랜드별 RTSP URL

### 하이크비전 (Hikvision)

```
rtsp://user:pass@ip:554/Streaming/Channels/101  # 채널1 메인
rtsp://user:pass@ip:554/Streaming/Channels/102  # 채널1 서브
```

### 다후아 (Dahua)

```
rtsp://user:pass@ip:554/cam/realmonitor?channel=1&subtype=0  # 메인
rtsp://user:pass@ip:554/cam/realmonitor?channel=1&subtype=1  # 서브
```

### 한화테크윈

```
rtsp://user:pass@ip:554/profile1/media.smp  # 프로파일1
```

### 일반 NVR

```
rtsp://user:pass@ip:554/live_01  # 채널 1
rtsp://user:pass@ip:554/live_02  # 채널 2
```

## WebUI 접속

```
http://192.168.0.10:1984
```

### 기능

- 스트림 상태 확인
- 실시간 미리보기
- 로그 확인
- API 테스트

## API 엔드포인트

### 스트림 목록

```bash
curl http://localhost:1984/api/streams
```

### WebRTC SDP

```bash
curl -X POST http://localhost:1984/api/webrtc?src=ch1 \
  -H "Content-Type: application/sdp" \
  -d "$(cat offer.sdp)"
```

### HLS 스트림

```
http://localhost:1984/api/stream.m3u8?src=ch1
```

### MJPEG 스트림

```
http://localhost:1984/api/stream.mjpeg?src=ch1
```

### 스냅샷

```
http://localhost:1984/api/frame.jpeg?src=ch1
```

## 환경변수 사용

`go2rtc.yaml`에서 환경변수 참조:

```yaml
streams:
  ch1:
    - "rtsp://${RTSP_USERNAME}:${RTSP_PASSWORD}@${RTSP_HOST}:${RTSP_PORT}/live_01"
```

## 테스트

### 1. 컨테이너 실행

```bash
docker compose up go2rtc
```

### 2. WebUI 접속

```
http://192.168.0.10:1984
```

### 3. 스트림 확인

- streams 탭에서 ch1~ch4 확인
- 각 스트림 클릭하여 미리보기

### 4. RTSP 출력 테스트

```bash
ffplay rtsp://localhost:8554/ch1
```

## 문제 해결

### 스트림 연결 안됨

```bash
# NVR 직접 테스트
ffprobe "rtsp://user:pass@192.168.0.100:554/live_01"

# 로그 확인
docker logs go2rtc
```

### CPU 사용량 높음

트랜스코딩 비활성화 (패스스루):

```yaml
streams:
  ch1:
    - "rtsp://...#video=copy#audio=copy"
```

### WebRTC 연결 실패

TURN 서버 추가:

```yaml
webrtc:
  ice_servers:
    - urls: [stun:stun.l.google.com:19302]
    - urls: [turn:turn.example.com:443?transport=tcp]
      username: user
      credential: pass
```
