# 학습 자료: 스트리밍 & 네트워크 기술

이 프로젝트에서 사용하는 핵심 기술들의 학습 자료 모음

## 목차

1. [RTSP (Real Time Streaming Protocol)](#1-rtsp)
2. [WebRTC (Web Real-Time Communication)](#2-webrtc)
3. [HLS (HTTP Live Streaming)](#3-hls)
4. [NAT & STUN/TURN](#4-nat--stunturn)
5. [코덱 (H.264/H.265)](#5-코덱)
6. [go2rtc 내부 동작](#6-go2rtc-내부-동작)

---

## 1. RTSP

### 개념

**RTSP (Real Time Streaming Protocol)** - 실시간 미디어 스트리밍 제어 프로토콜

```
┌─────────┐    RTSP (554)    ┌─────────┐
│  NVR/   │ ◄──────────────► │ Client  │
│ Camera  │    RTP (UDP)     │         │
└─────────┘ ────────────────► └─────────┘
             미디어 데이터
```

### 핵심 포인트

- **제어 프로토콜**: 재생, 일시정지, 탐색 등 제어 (HTTP와 유사한 텍스트 기반)
- **RTP로 미디어 전송**: 실제 영상/오디오는 RTP(Real-time Transport Protocol)로 전송
- **기본 포트**: 554 (TCP)
- **URL 형식**: `rtsp://user:pass@ip:port/path`

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| RTSP 위키백과 | https://ko.wikipedia.org/wiki/RTSP | 입문 |
| RFC 2326 (RTSP 스펙) | https://datatracker.ietf.org/doc/html/rfc2326 | 고급 |
| RTSP vs HTTP 비교 | https://www.wowza.com/blog/rtsp-the-real-time-streaming-protocol-explained | 중급 |
| ffmpeg RTSP 가이드 | https://trac.ffmpeg.org/wiki/StreamingGuide | 중급 |

### 실습

```bash
# RTSP 스트림 테스트
ffprobe "rtsp://user:pass@192.168.0.100:554/live_01"

# RTSP → 파일 저장
ffmpeg -i "rtsp://..." -c copy output.mp4

# RTSP 스트림 재생
ffplay "rtsp://..."
```

---

## 2. WebRTC

### 개념

**WebRTC (Web Real-Time Communication)** - 브라우저 간 P2P 실시간 통신

```
┌──────────┐                      ┌──────────┐
│ Browser  │ ◄──── P2P 연결 ────► │ go2rtc   │
│ (Client) │      (UDP 선호)      │ (Server) │
└──────────┘                      └──────────┘
      │                                 │
      └──────── STUN/TURN 서버 ────────┘
              (NAT 통과 지원)
```

### 핵심 포인트

- **P2P 통신**: 서버 거치지 않고 직접 연결 (가능한 경우)
- **초저지연**: 1초 미만 지연
- **ICE (Interactive Connectivity Establishment)**: 최적 경로 탐색
- **SDP (Session Description Protocol)**: 미디어 협상

### 연결 과정 (Signaling)

```
1. Client: Offer SDP 생성 (내 미디어 정보)
2. Client → Server: Offer 전송
3. Server: Answer SDP 생성 (수락/협상)
4. Server → Client: Answer 전송
5. ICE Candidate 교환 (네트워크 경로)
6. P2P 연결 수립
```

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| WebRTC 공식 사이트 | https://webrtc.org/ | 입문 |
| MDN WebRTC API | https://developer.mozilla.org/ko/docs/Web/API/WebRTC_API | 중급 |
| WebRTC for the Curious (무료 책) | https://webrtcforthecurious.com/ | 중급 |
| High Performance Browser Networking - WebRTC | https://hpbn.co/webrtc/ | 고급 |
| WebRTC Samples | https://webrtc.github.io/samples/ | 실습 |

### 핵심 코드 이해

```typescript
// 1. PeerConnection 생성
const pc = new RTCPeerConnection({
  iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
})

// 2. 미디어 트랙 수신 이벤트
pc.ontrack = (event) => {
  video.srcObject = event.streams[0]
}

// 3. Offer 생성 및 전송
const offer = await pc.createOffer()
await pc.setLocalDescription(offer)

// 4. Answer 수신 및 설정
const answer = await fetch('/api/webrtc', {
  method: 'POST',
  body: offer.sdp
}).then(r => r.text())

await pc.setRemoteDescription({ type: 'answer', sdp: answer })
```

---

## 3. HLS

### 개념

**HLS (HTTP Live Streaming)** - Apple이 개발한 HTTP 기반 스트리밍

```
┌──────────┐    ┌─────────────────┐    ┌──────────┐
│  Source  │ ─► │ HLS Segmenter   │ ─► │  Client  │
│ (RTSP)   │    │ (go2rtc/ffmpeg) │    │ (HLS.js) │
└──────────┘    └─────────────────┘    └──────────┘
                       │
                       ▼
              ┌─────────────────┐
              │ playlist.m3u8   │ ← 세그먼트 목록
              │ segment1.ts    │ ← 2초 영상 청크
              │ segment2.ts    │
              │ segment3.ts    │
              └─────────────────┘
```

### 핵심 포인트

- **HTTP 기반**: 일반 웹 서버로 제공 가능, 방화벽 통과 용이
- **세그먼트 방식**: 영상을 작은 조각(2-10초)으로 분할
- **적응형 비트레이트**: 네트워크 상태에 따라 품질 자동 조절
- **지연**: 세그먼트 크기 × 3 이상 (일반적으로 6-30초)

### m3u8 플레이리스트 구조

```m3u8
#EXTM3U
#EXT-X-VERSION:3
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:100
#EXTINF:2.000,
segment100.ts
#EXTINF:2.000,
segment101.ts
#EXTINF:2.000,
segment102.ts
```

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| Apple HLS 공식 문서 | https://developer.apple.com/streaming/ | 중급 |
| HLS.js 문서 | https://github.com/video-dev/hls.js | 중급 |
| RFC 8216 (HLS 스펙) | https://datatracker.ietf.org/doc/html/rfc8216 | 고급 |
| HLS vs DASH 비교 | https://www.wowza.com/blog/hls-vs-dash | 입문 |
| Low-Latency HLS | https://developer.apple.com/documentation/http-live-streaming/enabling-low-latency-http-live-streaming-ll-hls | 고급 |

### HLS.js 최적화 옵션

```typescript
const hls = new Hls({
  // 저지연 설정
  lowLatencyMode: true,

  // 버퍼 설정
  liveSyncDuration: 1,         // 라이브 싱크 위치 (초)
  liveMaxLatencyDuration: 3,   // 최대 허용 지연 (초)
  maxBufferLength: 3,          // 최대 버퍼 길이 (초)

  // 성능 설정
  enableWorker: true,          // Web Worker 사용
  maxMaxBufferLength: 10,      // 탐색 시 최대 버퍼
})
```

---

## 4. NAT & STUN/TURN

### NAT 개념

**NAT (Network Address Translation)** - 사설 IP ↔ 공인 IP 변환

```
┌─────────────────────────────────────────────┐
│                인터넷                        │
│            (공인 IP 영역)                    │
└─────────────────────────────────────────────┘
                     │
              ┌──────┴──────┐
              │   Router    │ ← NAT 수행
              │ (공인 IP)   │
              └──────┬──────┘
                     │
┌─────────────────────────────────────────────┐
│              사설 네트워크                   │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │ PC      │  │ Phone   │  │ Camera  │     │
│  │192.168. │  │192.168. │  │192.168. │     │
│  │  0.10   │  │  0.11   │  │  0.100  │     │
│  └─────────┘  └─────────┘  └─────────┘     │
└─────────────────────────────────────────────┘
```

### NAT 유형

| 유형 | 특징 | WebRTC 연결 |
|------|------|-------------|
| **Full Cone** | 가장 개방적 | STUN만으로 가능 |
| **Restricted Cone** | IP 제한 | STUN 가능 |
| **Port Restricted** | IP+포트 제한 | STUN 가능 |
| **Symmetric** | 가장 엄격 | TURN 필요 |

### STUN vs TURN

```
STUN (Session Traversal Utilities for NAT)
─────────────────────────────────────────
- 내 공인 IP/포트 확인용
- 무료 (Google STUN 등)
- P2P 연결 시도

TURN (Traversal Using Relays around NAT)
─────────────────────────────────────────
- 릴레이 서버 (중계)
- 유료 (대역폭 비용)
- STUN 실패 시 폴백
```

```
┌────────┐         ┌────────┐         ┌────────┐
│ Client │ ──────► │  STUN  │ ◄────── │ Server │
│        │         │ Server │         │        │
└────────┘         └────────┘         └────────┘
    │                                      │
    └─────────── P2P 직접 연결 ───────────┘


    STUN 실패 시:

┌────────┐         ┌────────┐         ┌────────┐
│ Client │ ──────► │  TURN  │ ◄────── │ Server │
│        │         │ Server │         │        │
└────────┘         └────────┘         └────────┘
                   (모든 트래픽
                    릴레이)
```

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| NAT 위키백과 | https://ko.wikipedia.org/wiki/NAT | 입문 |
| WebRTC NAT Traversal | https://webrtcforthecurious.com/docs/03-connecting/ | 중급 |
| STUN/TURN 설명 | https://www.html5rocks.com/ko/tutorials/webrtc/infrastructure/ | 중급 |
| ICE 프로토콜 | https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API/Protocols | 중급 |
| coturn (오픈소스 TURN) | https://github.com/coturn/coturn | 실습 |

---

## 5. 코덱

### 비디오 코덱 비교

| 코덱 | 압축률 | CPU 사용 | 호환성 | 라이선스 |
|------|--------|----------|--------|----------|
| **H.264 (AVC)** | 보통 | 낮음 | 최고 | 특허료 |
| **H.265 (HEVC)** | 높음 (50%↑) | 높음 | 중간 | 특허료 |
| **VP9** | 높음 | 높음 | Chrome | 무료 |
| **AV1** | 최고 | 매우 높음 | 제한적 | 무료 |

### CCTV에서 주로 사용

```
H.264 High Profile
├── 해상도: 1080p, 4K
├── 프레임레이트: 15-30fps
├── 비트레이트: 2-8 Mbps
└── 키프레임 간격: 1-2초 (GOP)
```

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| H.264 위키백과 | https://ko.wikipedia.org/wiki/H.264/MPEG-4_AVC | 입문 |
| 비디오 코덱 비교 | https://www.wowza.com/blog/video-codecs-encoding | 중급 |
| FFmpeg 코덱 가이드 | https://trac.ffmpeg.org/wiki/Encode/H.264 | 중급 |

---

## 6. go2rtc 내부 동작

### 아키텍처

```
┌─────────────────────────────────────────────────────┐
│                      go2rtc                          │
│                                                      │
│  ┌──────────┐    ┌──────────────┐    ┌──────────┐  │
│  │  Sources │ ─► │   Streams    │ ─► │Consumers │  │
│  │          │    │   (버퍼)     │    │          │  │
│  │ - RTSP   │    │              │    │ - WebRTC │  │
│  │ - RTMP   │    │  패스스루    │    │ - HLS    │  │
│  │ - FFmpeg │    │  or 변환     │    │ - MJPEG  │  │
│  └──────────┘    └──────────────┘    └──────────┘  │
│                                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │                  API Server                  │   │
│  │              (HTTP :1984)                    │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### 데이터 흐름

```
1. RTSP 소스 연결
   NVR ──RTP──► go2rtc (RTSP Client)

2. 패스스루 (트랜스코딩 없음)
   H.264/AAC 원본 그대로 전달

3. 출력 변환
   - WebRTC: RTP 패킷으로 변환
   - HLS: fMP4/TS 세그먼트 생성
   - MJPEG: 프레임 추출 후 JPEG 인코딩
```

### 소스 코드 분석

| 경로 | 설명 |
|------|------|
| `internal/rtsp/` | RTSP 클라이언트/서버 |
| `internal/webrtc/` | WebRTC 시그널링 |
| `internal/hls/` | HLS 세그먼터 |
| `internal/streams/` | 스트림 관리 |
| `internal/api/` | REST API |

### 학습 자료

| 자료 | 링크 | 난이도 |
|------|------|--------|
| go2rtc GitHub | https://github.com/AlexxIT/go2rtc | 소스 |
| go2rtc Wiki | https://github.com/AlexxIT/go2rtc/wiki | 중급 |
| go2rtc 소스 분석 | 직접 코드 읽기 추천 | 고급 |

---

## 추천 학습 순서

### 1단계: 기초 (1-2주)
1. RTSP 개념 이해
2. ffmpeg/ffplay로 스트림 테스트
3. HLS 구조 이해

### 2단계: 중급 (2-3주)
1. WebRTC 개념 및 시그널링
2. NAT/STUN/TURN 이해
3. HLS.js로 플레이어 구현

### 3단계: 심화 (3-4주)
1. go2rtc 소스 코드 분석
2. WebRTC ICE 연결 디버깅
3. 코덱 및 트랜스코딩 이해

---

## 실습 환경

### 필수 도구

```bash
# FFmpeg (스트림 테스트)
brew install ffmpeg  # macOS
apt install ffmpeg   # Ubuntu

# Wireshark (네트워크 분석)
brew install wireshark

# webrtc-internals (Chrome)
chrome://webrtc-internals
```

### 유용한 테스트 사이트

| 사이트 | 용도 |
|--------|------|
| https://webrtc.github.io/samples/ | WebRTC 샘플 |
| https://test.webrtc.org/ | WebRTC 연결 테스트 |
| https://icetest.info/ | ICE 서버 테스트 |
| https://hls-js.netlify.app/demo/ | HLS.js 데모 |

---

## 참고 서적

| 책 | 설명 |
|----|------|
| **High Performance Browser Networking** | 웹 네트워킹 전반 (무료 온라인) |
| **WebRTC for the Curious** | WebRTC 심층 이해 (무료 온라인) |
| **Video Encoding by the Numbers** | 비디오 코덱 기초 |
