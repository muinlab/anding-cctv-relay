# Anding CCTV Relay Server

스터디카페 CCTV 실시간 스트리밍을 위한 미니PC 중계 서버 구축 가이드

## 왜 필요한가?

- Vercel(서버리스)에서는 RTSP 스트리밍 불가능
- 지점 내 미니PC가 RTSP → WebRTC/HLS 변환 후 웹으로 중계
- Cloudflare Tunnel로 포트포워딩 없이 외부 접근

## 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     스터디카페 지점                          │
│                                                             │
│  ┌───────┐  RTSP   ┌─────────────────────────────────────┐  │
│  │  NVR  │ ──────▶ │           미니PC                    │  │
│  │(CCTV) │         │                                     │  │
│  └───────┘         │  ┌──────────┐    ┌──────────────┐   │  │
│                    │  │  go2rtc  │    │ cctv-worker  │   │  │
│                    │  │ 스트리밍  │────│ YOLO 감지     │   │  │
│                    │  └────┬─────┘    └──────┬───────┘   │  │
│                    │       │                  │           │  │
│                    └───────┼──────────────────┼───────────┘  │
│                            │                  │              │
└────────────────────────────┼──────────────────┼──────────────┘
                             │                  │
          Cloudflare Tunnel  │                  │ Supabase
                             ▼                  ▼
                    ┌──────────────┐    ┌──────────────┐
                    │  admin-web   │    │   Realtime   │
                    │  (Vercel)    │    │   DB 업데이트 │
                    └──────────────┘    └──────────────┘
```

## 빠른 시작

```bash
# 1. 레포 클론
git clone https://github.com/muinlab/anding-cctv-relay.git
cd anding-cctv-relay

# 2. 환경변수 설정
cp .env.example .env
nano .env

# 3. 실행
docker compose up -d
```

## 문서

- [하드웨어 요구사항](docs/01-hardware.md)
- [Ubuntu 초기 설정](docs/02-ubuntu-setup.md)
- [go2rtc 설정](docs/03-go2rtc.md)
- [Cloudflare Tunnel 설정](docs/04-cloudflare-tunnel.md)
- [cctv-worker 연동](docs/05-cctv-worker.md)
- [admin-web 연동](docs/06-admin-web.md)
- [운영 및 모니터링](docs/07-operations.md)
- [문제 해결](docs/08-troubleshooting.md)

## 디렉토리 구조

```
anding-cctv-relay/
├── docker-compose.yaml     # 메인 컴포즈 파일
├── .env.example            # 환경변수 템플릿
├── go2rtc/
│   └── go2rtc.yaml         # 스트리밍 서버 설정
├── scripts/
│   ├── install.sh          # 초기 설치 스크립트
│   ├── health-check.sh     # 상태 체크
│   └── backup.sh           # 백업
├── systemd/
│   └── anding-cctv.service # systemd 서비스 파일
└── docs/                   # 상세 문서
```

## 지점별 배포

| 지점 | 도메인 | 상태 |
|-----|--------|------|
| 오류동역 | `cctv-oryudong.anding.kr` | 예정 |
| 강남구청역 | `cctv-gangnam.anding.kr` | 예정 |

## 라이선스

Private - Muinlab
