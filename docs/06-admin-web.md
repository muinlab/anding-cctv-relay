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

### 옵션 1: HLS (권장)

- 지연: 3-5초
- 호환성: 최고 (모든 브라우저, 모바일)
- 구현: 간단

```typescript
// HLS.js 사용
import Hls from 'hls.js'

function HlsPlayer({ src }: { src: string }) {
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    if (Hls.isSupported()) {
      const hls = new Hls()
      hls.loadSource(src)
      hls.attachMedia(video)
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari 네이티브 HLS
      video.src = src
    }
  }, [src])

  return <video ref={videoRef} autoPlay muted playsInline />
}
```

### 옵션 2: WebRTC

- 지연: <1초
- 호환성: 제한적 (NAT 이슈)
- 구현: 복잡

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

### 옵션 3: MJPEG (폴백)

- 지연: 1-2초
- 호환성: 좋음
- 단점: 대역폭 높음

```typescript
function MjpegPlayer({ src }: { src: string }) {
  return <img src={src} alt="CCTV Stream" />
}
```

## 통합 플레이어 컴포넌트

```typescript
// apps/admin-web/src/components/cctv/stream-player.tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import Hls from 'hls.js'

interface StreamPlayerProps {
  cctvBaseUrl: string
  channelId: number
  className?: string
}

type StreamType = 'hls' | 'webrtc' | 'mjpeg'

export function StreamPlayer({
  cctvBaseUrl,
  channelId,
  className
}: StreamPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [streamType, setStreamType] = useState<StreamType>('hls')
  const [error, setError] = useState<string | null>(null)

  const streamUrls = {
    hls: `${cctvBaseUrl}/api/stream.m3u8?src=ch${channelId}`,
    webrtc: `${cctvBaseUrl}/api/webrtc?src=ch${channelId}`,
    mjpeg: `${cctvBaseUrl}/api/stream.mjpeg?src=ch${channelId}`
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video || streamType === 'mjpeg') return

    if (streamType === 'hls') {
      if (Hls.isSupported()) {
        const hls = new Hls({
          lowLatencyMode: true,
          liveSyncDuration: 1,
          liveMaxLatencyDuration: 5
        })
        hls.loadSource(streamUrls.hls)
        hls.attachMedia(video)
        hls.on(Hls.Events.ERROR, () => {
          setError('HLS 연결 실패')
          setStreamType('mjpeg')  // 폴백
        })
        return () => hls.destroy()
      } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
        video.src = streamUrls.hls
      }
    }

    // WebRTC 구현은 별도 함수로
  }, [streamType, cctvBaseUrl, channelId])

  if (streamType === 'mjpeg') {
    return (
      <img
        src={streamUrls.mjpeg}
        alt={`Channel ${channelId}`}
        className={className}
      />
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
        <div className="absolute bottom-2 left-2 bg-yellow-500 px-2 py-1 text-xs">
          {error}
        </div>
      )}
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
