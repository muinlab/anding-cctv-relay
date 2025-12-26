# Windows WSL2 설치 가이드

Windows PC에서 WSL2(Windows Subsystem for Linux)를 사용하여 CCTV Relay 서버를 구축하는 가이드입니다.

> **왜 WSL2인가?**
> - Docker Desktop 없이 Docker Engine 직접 실행 → 리소스 효율적
> - Linux 네이티브 환경 → 안정적인 24시간 운영
> - systemd 지원 → 자동 시작 설정 가능

---

## 목차

1. [사전 요구사항](#1-사전-요구사항)
2. [WSL2 설치](#2-wsl2-설치)
3. [Ubuntu 초기 설정](#3-ubuntu-초기-설정)
4. [Docker Engine 설치](#4-docker-engine-설치)
5. [프로젝트 설치](#5-프로젝트-설치)
6. [Tailscale 설정](#6-tailscale-설정)
7. [자동 시작 설정](#7-자동-시작-설정)
8. [디버그 스트림 사용](#8-디버그-스트림-사용)
9. [문제 해결](#9-문제-해결)

---

## 1. 사전 요구사항

### 하드웨어
- **CPU**: Intel i3 이상 또는 AMD Ryzen 3 이상
- **RAM**: 최소 8GB (16GB 권장)
- **저장소**: 50GB 이상 여유 공간
- **네트워크**: 유선 LAN 연결 권장

### 소프트웨어
- **Windows 10** 버전 2004 이상 (빌드 19041 이상)
- **Windows 11** 모든 버전

### 확인 방법
PowerShell에서 실행:
```powershell
winver
```

---

## 2. WSL2 설치

### 2.1 WSL 활성화

PowerShell을 **관리자 권한**으로 실행하고:

```powershell
# WSL 및 가상 머신 기능 활성화
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
```

**재부팅** 후 계속 진행합니다.

### 2.2 WSL2를 기본으로 설정

```powershell
wsl --set-default-version 2
```

### 2.3 Ubuntu 설치

```powershell
# Ubuntu 22.04 설치
wsl --install -d Ubuntu-22.04
```

설치 완료 후 **사용자 이름**과 **비밀번호**를 설정합니다.

### 2.4 설치 확인

```powershell
wsl -l -v
```

출력 예시:
```
  NAME            STATE           VERSION
* Ubuntu-22.04    Running         2
```

---

## 3. Ubuntu 초기 설정

WSL Ubuntu 터미널을 열고 (Windows Terminal 또는 `wsl` 명령):

### 3.1 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.2 필수 패키지 설치

```bash
sudo apt install -y \
    curl \
    wget \
    git \
    openssh-server \
    ca-certificates \
    gnupg \
    lsb-release
```

### 3.3 systemd 활성화

WSL2에서 systemd를 사용하려면 설정이 필요합니다:

```bash
sudo nano /etc/wsl.conf
```

다음 내용 추가:
```ini
[boot]
systemd=true

[network]
generateResolvConf=true
```

저장 후 WSL 재시작:
```powershell
# PowerShell에서
wsl --shutdown
wsl
```

systemd 확인:
```bash
systemctl --version
```

---

## 4. Docker Engine 설치

> **주의**: Docker Desktop이 아닌 Docker Engine을 직접 설치합니다.

### 4.1 Docker 저장소 추가

```bash
# Docker GPG 키 추가
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# 저장소 추가
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
```

### 4.2 Docker 설치

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

### 4.3 사용자를 docker 그룹에 추가

```bash
sudo usermod -aG docker $USER
```

**로그아웃 후 다시 로그인** (또는 `newgrp docker`)

### 4.4 Docker 서비스 시작

```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### 4.5 설치 확인

```bash
docker --version
docker compose version
docker run hello-world
```

---

## 5. 프로젝트 설치

### 5.1 프로젝트 클론

```bash
cd ~
git clone https://github.com/muinlab/anding-cctv-relay.git
cd anding-cctv-relay
```

### 5.2 환경 변수 설정

```bash
cp .env.example .env
nano .env
```

필수 설정:
```env
# 지점 ID
STORE_ID=your_store_id

# NVR 접속 정보
RTSP_HOST=192.168.0.100
RTSP_PORT=554
RTSP_USERNAME=admin
RTSP_PASSWORD=your_password

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# 디버그 스트림 (선택)
DEBUG_STREAM_ENABLED=true
```

### 5.3 디렉토리 생성

```bash
mkdir -p data/snapshots logs/worker
```

### 5.4 서비스 시작

```bash
# 빌드 및 시작
docker compose up -d --build

# 로그 확인
docker compose logs -f
```

### 5.5 동작 확인

```bash
# 컨테이너 상태
docker compose ps

# go2rtc 웹 UI (브라우저에서)
# http://localhost:1984

# 디버그 스트림 (DEBUG_STREAM_ENABLED=true인 경우)
# http://localhost:8001/debug/
```

---

## 6. Tailscale 설정

외부에서 접속하려면 Tailscale Funnel을 사용합니다.

### 6.1 Tailscale 설치

```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### 6.2 Tailscale 로그인

```bash
sudo tailscale up
```

표시된 URL로 이동하여 로그인합니다.

### 6.3 Funnel 활성화

```bash
# Funnel로 go2rtc 포트 노출
sudo tailscale funnel 1984
```

생성된 URL (예: `https://your-machine.tail12345.ts.net`)로 외부에서 접속할 수 있습니다.

### 6.4 Funnel 자동 시작

```bash
# systemd 서비스 생성
sudo nano /etc/systemd/system/tailscale-funnel.service
```

내용:
```ini
[Unit]
Description=Tailscale Funnel for go2rtc
After=network.target tailscaled.service

[Service]
Type=simple
ExecStart=/usr/bin/tailscale funnel 1984
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

활성화:
```bash
sudo systemctl daemon-reload
sudo systemctl enable tailscale-funnel
sudo systemctl start tailscale-funnel
```

---

## 7. 자동 시작 설정

### 7.1 Docker Compose 서비스 생성

```bash
sudo nano /etc/systemd/system/anding-cctv.service
```

내용:
```ini
[Unit]
Description=Anding CCTV Relay
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/$USER/anding-cctv-relay
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

> `$USER`를 실제 사용자명으로 변경하세요.

### 7.2 서비스 활성화

```bash
sudo systemctl daemon-reload
sudo systemctl enable anding-cctv.service
```

### 7.3 Windows 시작 시 WSL 자동 실행

Windows 작업 스케줄러에서:

1. **작업 스케줄러** 열기
2. **작업 만들기** 클릭
3. 설정:
   - 이름: `Start WSL`
   - 트리거: 로그온 시
   - 동작: 프로그램 시작
     - 프로그램: `wsl`
     - 인수: `-d Ubuntu-22.04 -- sudo systemctl start anding-cctv`

또는 PowerShell 스크립트:
```powershell
# startup.ps1
wsl -d Ubuntu-22.04 -- sudo systemctl start anding-cctv
wsl -d Ubuntu-22.04 -- sudo systemctl start tailscale-funnel
```

---

## 8. 디버그 스트림 사용

### 8.1 활성화

`.env` 파일에서:
```env
DEBUG_STREAM_ENABLED=true
DEBUG_STREAM_PORT=8001
```

서비스 재시작:
```bash
docker compose up -d --build
```

### 8.2 접속

Windows 브라우저에서:
- **디버그 UI**: http://localhost:8001/debug/
- **채널별 스트림**: http://localhost:8001/debug/stream/1
- **스냅샷**: http://localhost:8001/debug/snapshot/1

### 8.3 기능

- 실시간 MJPEG 스트림
- YOLO 바운딩 박스 오버레이
- ROI 폴리곤 시각화
- 감지 상태 표시

---

## 9. 문제 해결

### WSL이 시작되지 않음

```powershell
# WSL 업데이트
wsl --update

# WSL 재설치
wsl --unregister Ubuntu-22.04
wsl --install -d Ubuntu-22.04
```

### Docker가 시작되지 않음

```bash
# Docker 상태 확인
sudo systemctl status docker

# 수동 시작
sudo systemctl start docker

# 로그 확인
sudo journalctl -u docker
```

### 포트 접근 불가

WSL2는 Windows와 네트워크를 공유합니다. `localhost`로 접근 가능합니다.

방화벽 확인:
```powershell
# PowerShell (관리자)
netsh advfirewall firewall add rule name="WSL" dir=in action=allow protocol=TCP localport=1984,8001
```

### 메모리 부족

WSL2 메모리 제한 설정:

```powershell
# %UserProfile%\.wslconfig 파일 생성
notepad $env:USERPROFILE\.wslconfig
```

내용:
```ini
[wsl2]
memory=4GB
processors=2
```

WSL 재시작:
```powershell
wsl --shutdown
```

### RTSP 연결 실패

1. NVR과 같은 네트워크인지 확인
2. NVR IP 주소 확인
3. RTSP 포트(554) 방화벽 확인
4. 인증 정보 확인

테스트:
```bash
# ffmpeg으로 RTSP 테스트
docker run --rm jrottenberg/ffmpeg:4.4-alpine \
    -i "rtsp://admin:password@192.168.0.100:554/live_01" \
    -frames:v 1 -f image2 /dev/null
```

---

## 다음 단계

- [go2rtc 설정 가이드](03-go2rtc.md)
- [운영 및 모니터링](07-operations.md)
- [문제 해결 가이드](08-troubleshooting.md)
