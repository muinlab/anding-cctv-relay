# admin-web 연동

## 개요

admin-web에서 CCTV 스트리밍을 보기 위한 프론트엔드 연동 가이드

## 현재 구조

```
apps/admin-web/src/components/cctv/
├── cctv-grid.tsx       # 그리드 레이아웃
├── cctv-viewer.tsx     # 뷰어 컴포넌트 (현재 mock)
└── index.ts
```

## 환경변수 추가

```bash
# apps/admin-web/.env.local
NEXT_PUBLIC_CCTV_ENABLED=true
```

## DB 스키마 변경

stores 테이블에 CCTV URL 필드 추가:

```sql
-- Supabase Migration
ALTER TABLE stores ADD COLUMN cctv_base_url TEXT;

-- 지점별 URL 설정
UPDATE stores
SET cctv_base_url = 'https://cctv-oryudong.anding.kr'
WHERE store_id = 'oryudong';
```

## 스트리밍 방식 선택

### 옵션 1: WebRTC (권장)

- 지연: <1초 (실시간)
- 호환성: 대부분 브라우저 지원
- 장점: 낮은 지연, 양방향 통신 가능

```typescript
// WebRTC 플레이어
function WebRTCPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const pc = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    })

    pc.ontrack = (e) => {
      video.srcObject = e.streams[0]
    }

    async function connect() {
      pc.addTransceiver('video', { direction: 'recvonly' })
      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      const res = await fetch(src, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: offer.sdp
      })

      const answer = await res.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answer })
    }

    connect()
    return () => pc.close()
  }, [src])

  return <video ref={videoRef} autoPlay muted playsInline />
}
```

### 옵션 2: HLS (폴백)

- 지연: 3-5초
- 호환성: 최고 (모든 브라우저, 모바일)
- 용도: WebRTC 실패 시 폴백

```typescript
// HLS.js 사용
import Hls from 'hls.js'

function HlsPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        liveSyncDuration: 1,
        liveMaxLatencyDuration: 3
      })
      hls.loadSource(src)
      hls.attachMedia(video)
      return () => hls.destroy()
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 네이티브 HLS
      video.src = src
    }
  }, [src])

  return <video ref={videoRef} autoPlay muted playsInline />
}
```

### 옵션 3: MJPEG (최종 폴백)

- 지연: 1-2초
- 호환성: 좋음
- 단점: 대역폭 높음

```typescript
function MjpegPlayer({ src }: { src: string }) {
  return <img src={src} alt="CCTV Stream" />
}
```

## 통합 플레이어 컴포넌트

WebRTC → HLS → MJPEG 순서로 자동 폴백하는 통합 플레이어:

```typescript
// apps/admin-web/src/components/cctv/stream-player.tsx
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import Hls from 'hls.js'

interface StreamPlayerProps {
  cctvBaseUrl: string
  channelId: number
  className?: string
}

type StreamType = 'webrtc' | 'hls' | 'mjpeg'

export function StreamPlayer({
  cctvBaseUrl,
  channelId,
  className
}: StreamPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const pcRef = useRef<RTCPeerConnection | null>(null)
  const [streamType, setStreamType] = useState<StreamType>('webrtc')
  const [error, setError] = useState<string | null>(null)

  const streamUrls = {
    webrtc: `${cctvBaseUrl}/api/webrtc?src=ch${channelId}`,
    hls: `${cctvBaseUrl}/api/stream.m3u8?src=ch${channelId}`,
    mjpeg: `${cctvBaseUrl}/api/stream.mjpeg?src=ch${channelId}`
  }

  // WebRTC 연결
  const connectWebRTC = useCallback(async (video: HTMLVideoElement) => {
    const pc = new RTCPeerConnection({
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' },
        { urls: 'stun:stun1.l.google.com:19302' }
      ]
    })
    pcRef.current = pc

    pc.ontrack = (e) => {
      video.srcObject = e.streams[0]
    }

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'failed') {
        setError('WebRTC 연결 실패, HLS로 전환')
        setStreamType('hls')
      }
    }

    try {
      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      const res = await fetch(streamUrls.webrtc, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: offer.sdp
      })

      if (!res.ok) throw new Error('WebRTC negotiation failed')

      const answer = await res.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answer })
    } catch (err) {
      console.error('WebRTC error:', err)
      setError('WebRTC 연결 실패, HLS로 전환')
      setStreamType('hls')
    }
  }, [streamUrls.webrtc])

  // HLS 연결
  const connectHLS = useCallback((video: HTMLVideoElement) => {
    if (Hls.isSupported()) {
      const hls = new Hls({
        lowLatencyMode: true,
        liveSyncDuration: 1,
        liveMaxLatencyDuration: 3,
        maxBufferLength: 3
      })
      hls.loadSource(streamUrls.hls)
      hls.attachMedia(video)
      hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          setError('HLS 연결 실패, MJPEG로 전환')
          setStreamType('mjpeg')
        }
      })
      return () => hls.destroy()
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = streamUrls.hls
    }
  }, [streamUrls.hls])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    // 이전 연결 정리
    if (pcRef.current) {
      pcRef.current.close()
      pcRef.current = null
    }

    if (streamType === 'webrtc') {
      connectWebRTC(video)
      return () => {
        if (pcRef.current) {
          pcRef.current.close()
          pcRef.current = null
        }
      }
    }

    if (streamType === 'hls') {
      return connectHLS(video)
    }
  }, [streamType, connectWebRTC, connectHLS])

  if (streamType === 'mjpeg') {
    return (
      <div className={className}>
        <img
          src={streamUrls.mjpeg}
          alt={`Channel ${channelId}`}
          className="h-full w-full object-cover"
        />
        {error && (
          <div className="absolute bottom-2 left-2 bg-yellow-500 px-2 py-1 text-xs rounded">
            {error}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className={className}>
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        className="h-full w-full object-cover"
      />
      {error && (
        <div className="absolute bottom-2 left-2 bg-yellow-500 px-2 py-1 text-xs rounded">
          {error}
        </div>
      )}
      <div className="absolute top-2 right-2 bg-black/50 px-2 py-1 text-xs text-white rounded">
        {streamType.toUpperCase()}
      </div>
    </div>
  )
}
```

## CctvViewer 수정

```typescript
// apps/admin-web/src/components/cctv/cctv-viewer.tsx

import { StreamPlayer } from './stream-player'
import { useStore } from '@/hooks/use-stores'

export function CctvViewer({ storeId, channelId, ...props }) {
  const { data: store } = useStore(storeId)

  // CCTV URL이 설정되어 있으면 실제 스트리밍
  if (store?.cctvBaseUrl) {
    return (
      <StreamPlayer
        cctvBaseUrl={store.cctvBaseUrl}
        channelId={channelId}
        {...props}
      />
    )
  }

  // 없으면 기존 mock 표시
  return <MockViewer channelId={channelId} {...props} />
}
```

## 패키지 설치

```bash
cd apps/admin-web
pnpm add hls.js
pnpm add -D @types/hls.js
```

## 테스트

1. 미니PC에서 go2rtc 실행 확인
2. admin-web 개발 서버 실행
3. CCTV 페이지 접속
4. 스트림 확인

```bash
# 개발 서버
pnpm dev

# 브라우저
http://localhost:3000/dashboard/cctv
```

## 모바일 앱 (admin-mobile)

React Native에서도 동일하게 HLS 사용:

```typescript
import Video from 'react-native-video'

<Video
  source={{ uri: `${cctvBaseUrl}/api/stream.m3u8?src=ch${channelId}` }}
  style={styles.video}
/>
```
