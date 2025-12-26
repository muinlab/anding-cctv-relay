# Anding CCTV Relay Server

스터디카페 CCTV 실시간 스트리밍을 위한 미니PC 중계 서버 구축 가이드

## 왜 필요한가?

- Vercel(서버리스)에서는 RTSP 스트리밍 불가능
- 지점 내 미니PC가 RTSP → WebRTC/HLS 변환 후 웹으로 중계
- Tailscale Funnel 또는 Cloudflare Tunnel로 외부 접근

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
     Tailscale Funnel 또는   │                  │ Supabase
     Cloudflare Tunnel       ▼                  ▼
                    ┌──────────────┐    ┌──────────────┐
                    │  admin-web   │    │   Realtime   │
                    │  (Vercel)    │    │   DB 업데이트 │
                    └──────────────┘    └──────────────┘
```

## 빠른 시작

### Windows (권장)

```powershell
# PowerShell에서 한 줄로 설치 (관리자 권한 자동 요청)
irm https://anding.kr/cctv | iex
```

또는 수동으로 관리자 PowerShell에서:
```powershell
irm https://raw.githubusercontent.com/muinlab/anding-cctv-relay/main/scripts/install.ps1 | iex
```

수동 설치:
```powershell
# 1. Docker Desktop, Git, Tailscale 설치 (winget 사용)
winget install -e --id Docker.DockerDesktop
winget install -e --id Git.Git
winget install -e --id Tailscale.Tailscale

# 2. 레포 클론
git clone https://github.com/muinlab/anding-cctv-relay.git
cd anding-cctv-relay

# 3. 환경변수 설정
copy .env.example .env
notepad .env

# 4. 실행
docker compose --profile auto-update up -d

# 5. Tailscale Funnel 활성화 (외부 접속용)
& "C:\Program Files\Tailscale\tailscale.exe" funnel 1984
```

### Ubuntu/Linux

```bash
# 1. 자동 설치 스크립트 실행
curl -fsSL https://raw.githubusercontent.com/muinlab/anding-cctv-relay/main/scripts/install.sh | bash

# 2. 환경변수 설정
nano ~/anding-cctv-relay/.env

# 3. Tailscale 로그인 및 Funnel 활성화
sudo tailscale up
sudo tailscale funnel 1984

# 4. 서비스 시작
sudo systemctl start anding-cctv
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
│   ├── bootstrap.ps1       # Windows 부트스트랩 (관리자 자동 요청)
│   ├── install.ps1         # Windows 설치 스크립트 (PowerShell)
│   ├── install.sh          # Linux 설치 스크립트 (Bash)
│   ├── start.bat           # Windows 시작 스크립트 (자동 생성)
│   └── stop.bat            # Windows 종료 스크립트 (자동 생성)
├── systemd/
│   ├── anding-cctv.service         # Linux systemd 서비스
│   └── tailscale-funnel.service    # Tailscale Funnel 서비스
└── docs/                   # 상세 문서
```

## 지점별 배포

| 지점 | 접속 URL | 상태 |
|-----|---------|------|
| 오류동역 | Tailscale Funnel URL | 예정 |
| 강남구청역 | Tailscale Funnel URL | 예정 |

> Tailscale Funnel 활성화 후 `tailscale funnel status`로 URL 확인

## 라이선스

Private - Muinlab
