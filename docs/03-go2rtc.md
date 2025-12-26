# go2rtc 설정

## go2rtc란?

경량 스트리밍 서버로 RTSP를 WebRTC/HLS/MJPEG로 변환하는 오픈소스 미디어 서버

- **GitHub**: https://github.com/AlexxIT/go2rtc
- **언어**: Go (단일 바이너리, 경량)
- **라이선스**: MIT

### 주요 특징

| 특징 | 설명 |
|------|------|
| **저지연** | WebRTC로 1초 미만 지연 |
| **패스스루** | 트랜스코딩 없이 원본 전달 (CPU 절약) |
| **다중 프로토콜** | RTSP, WebRTC, HLS, MJPEG, MSE 지원 |
| **NAT 통과** | STUN/TURN 지원으로 외부 접속 가능 |
| **WebUI** | 내장 관리 인터페이스 |

### 지원 프로토콜

```
입력 (Sources)          출력 (Consumers)
─────────────────────   ─────────────────────
RTSP                    WebRTC (권장, <1초)
RTMP                    HLS (폴백, 3-5초)
HTTP-FLV                MJPEG (최종 폴백)
FFmpeg                  MSE
HomeKit                 RTSP
Exec                    MP4/JPEG
```

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
  listen: ":8555"           # TCP + UDP 모두 지원
  ice_servers:
    - urls: [stun:stun.l.google.com:19302]
    - urls: [stun:stun1.l.google.com:19302]

hls:
  # HLS 자동 활성화 (설정 옵션 제한적)

streams:
  ch1:
    - "rtsp://user:pass@192.168.0.100:554/live_01"
```

## WebRTC 상세 설정

WebRTC는 **권장 스트리밍 방식**으로, 1초 미만의 지연을 제공합니다.

### 기본 설정

```yaml
webrtc:
  listen: ":8555"  # TCP + UDP 모두 사용 (권장)
  # listen: ":8555/tcp"  # TCP만 사용
  # listen: ""           # 랜덤 UDP만 사용
```

### ICE 서버 설정

```yaml
webrtc:
  ice_servers:
    # STUN 서버 (NAT 타입 확인용)
    - urls: [stun:stun.l.google.com:19302]
    - urls: [stun:stun1.l.google.com:19302]

    # TURN 서버 (NAT 통과 필요시)
    - urls: [turn:turn.example.com:443?transport=tcp]
      username: ${TURN_USERNAME}
      credential: ${TURN_CREDENTIAL}
```

### 필터 옵션

```yaml
webrtc:
  filters:
    networks: [udp4, tcp4]     # IPv4만 사용
    # networks: [udp4, udp6, tcp4, tcp6]  # 전체

    candidates: []              # 특정 IP만 허용 (빈 배열 = 자동)
    loopback: false             # localhost 허용 여부
    interfaces: []              # 특정 네트워크 인터페이스만
    ips: []                     # 특정 IP만
    udp_ports: [50000, 50100]   # UDP 포트 범위
```

### NAT 환경별 설정

| 환경 | 설정 |
|------|------|
| **로컬 네트워크** | STUN만으로 충분 |
| **NAT 뒤 (대칭 NAT)** | TURN 서버 필요 |
| **Cloudflare Tunnel** | WebRTC 불가, HLS 사용 |

## HLS 상세 설정

HLS는 WebRTC 실패 시 **폴백 옵션**으로 사용됩니다.

### 제한사항

go2rtc의 HLS는 설정 옵션이 제한적입니다:

| 항목 | 값 | 설명 |
|------|-----|------|
| **세션 타임아웃** | 5초 | 고정값, 변경 불가 |
| **세그먼트 길이** | 자동 | go2rtc 내부 결정 |
| **플레이리스트 크기** | 자동 | go2rtc 내부 결정 |

### 지연 최소화 (프론트엔드)

HLS 지연은 **클라이언트(HLS.js) 설정**으로 최적화합니다:

```typescript
import Hls from 'hls.js'

const hls = new Hls({
  lowLatencyMode: true,        // 저지연 모드
  liveSyncDuration: 1,         // 라이브 동기화 버퍼 (초)
  liveMaxLatencyDuration: 3,   // 최대 허용 지연 (초)
  maxBufferLength: 3,          // 최대 버퍼 길이 (초)
})
```

### HLS vs WebRTC 비교

| 항목 | WebRTC | HLS |
|------|--------|-----|
| **지연** | <1초 | 3-5초 |
| **호환성** | 대부분 브라우저 | 모든 브라우저/모바일 |
| **NAT 통과** | STUN/TURN 필요 | HTTP로 문제없음 |
| **Cloudflare** | UDP 차단됨 | 정상 작동 |
| **CPU 사용** | 낮음 | 낮음 |

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
