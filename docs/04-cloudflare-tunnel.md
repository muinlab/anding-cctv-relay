# Cloudflare Tunnel 설정

## 왜 Cloudflare Tunnel?

- **포트포워딩 불필요**: 공유기 설정 변경 없음
- **고정 IP 불필요**: DDNS도 필요 없음
- **자동 HTTPS**: SSL 인증서 자동 관리
- **무료**: 기본 사용량 무료

## 사전 준비

1. Cloudflare 계정
2. 도메인 (Cloudflare DNS 연결됨)
   - 예: `anding.kr`

## 1. Cloudflare Zero Trust 설정

### 대시보드 접속

https://one.dash.cloudflare.com/

### 터널 생성

1. **Networks** > **Tunnels**
2. **Create a tunnel** 클릭
3. 터널 이름: `anding-oryudong-cctv`
4. **Cloudflared** 선택
5. **Docker** 탭 선택
6. 토큰 복사

```bash
# 토큰 형식
eyJhIjoiYWJjZGVmMTIzNDU2Nzg5MCIsInQiOiJ4eHh4LXh4eHgteHh4eC14eHh4IiwicyI6Inh4eHgiXQ==
```

## 2. 환경변수 설정

```bash
# .env 파일
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiYWJj...
```

## 3. Public Hostname 설정

Cloudflare 대시보드에서:

### go2rtc API

| 설정 | 값 |
|-----|-----|
| Subdomain | `cctv-oryudong` |
| Domain | `anding.kr` |
| Type | HTTP |
| URL | `localhost:1984` |

결과: `https://cctv-oryudong.anding.kr`

### 경로별 설정 (선택)

| Path | Service |
|------|---------|
| `/api/*` | `http://localhost:1984` |
| `/stream/*` | `http://localhost:1984` |

## 4. 접근 정책 설정 (선택)

### Application 생성

1. **Access** > **Applications** > **Add an application**
2. **Self-hosted** 선택
3. 설정:
   - Name: `CCTV Oryudong`
   - Domain: `cctv-oryudong.anding.kr`

### Policy 설정

```
Name: Anding Staff
Action: Allow
Include:
  - Emails ending in: @anding.kr
  - Emails: admin@example.com
```

## 5. Docker 실행

```bash
docker compose up -d cloudflared
```

### 로그 확인

```bash
docker logs -f cloudflared
```

성공 시:

```
INF Connection established connIndex=0 ...
INF Connection established connIndex=1 ...
```

## 6. 연결 테스트

### 외부에서 접속

```bash
# API 테스트
curl https://cctv-oryudong.anding.kr/api/streams

# 스트림 테스트 (브라우저)
https://cctv-oryudong.anding.kr/api/stream.mjpeg?src=ch1
```

## WebRTC 한계

Cloudflare Tunnel은 **TCP만 지원**하므로 순수 WebRTC(UDP)는 작동 안 함.

### 해결책 1: HLS 사용 (권장)

```
https://cctv-oryudong.anding.kr/api/stream.m3u8?src=ch1
```

- 지연: 3-5초
- 호환성: 모든 브라우저

### 해결책 2: WebRTC over TCP

go2rtc는 WebRTC TCP 폴백 지원:

```yaml
webrtc:
  listen: ":8555/tcp"  # TCP 명시
```

- 지연: ~1초
- 일부 NAT에서 작동 안 할 수 있음

### 해결책 3: TURN 서버 추가

외부 TURN 서버로 UDP 릴레이:

```yaml
webrtc:
  ice_servers:
    - urls: [turn:a.turn.metered.ca:443?transport=tcp]
      username: ${TURN_USERNAME}
      credential: ${TURN_CREDENTIAL}
```

**TURN 서버 추천**:
- [Metered TURN](https://www.metered.ca/turn-server) - 월 $5~
- [Twilio TURN](https://www.twilio.com/stun-turn) - 사용량 기반

## 다중 지점 설정

### 지점별 터널

| 지점 | 터널 이름 | 도메인 |
|-----|----------|--------|
| 오류동역 | `anding-oryudong-cctv` | `cctv-oryudong.anding.kr` |
| 강남구청역 | `anding-gangnam-cctv` | `cctv-gangnam.anding.kr` |

### 또는 경로 기반

단일 터널에서:

| Path | 서비스 |
|------|--------|
| `/oryudong/*` | 오류동역 미니PC |
| `/gangnam/*` | 강남구청역 미니PC |

## 문제 해결

### 터널 연결 안됨

```bash
# 로그 확인
docker logs cloudflared

# 토큰 확인
echo $CLOUDFLARE_TUNNEL_TOKEN | base64 -d | jq
```

### 502 Bad Gateway

go2rtc가 실행 중인지 확인:

```bash
curl http://localhost:1984/api
```

### 속도 느림

- HLS 세그먼트 크기 조정
- 서브스트림(저해상도) 사용
