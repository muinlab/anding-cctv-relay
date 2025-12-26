#!/bin/bash
# Anding CCTV Relay 초기 설치 스크립트
# 미니PC Ubuntu에서 실행
set -e

echo "========================================="
echo "  Anding CCTV Relay 설치 스크립트"
echo "========================================="
echo ""

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
step() { echo -e "\n${BLUE}[$1/$TOTAL_STEPS]${NC} $2"; }

TOTAL_STEPS=9

# 루트 체크
if [ "$EUID" -eq 0 ]; then
  error "root로 실행하지 마세요. 일반 사용자로 실행하세요."
fi

# 현재 사용자
CURRENT_USER=$(whoami)
info "현재 사용자: $CURRENT_USER"

# ============================================
step 1 "시스템 패키지 업데이트"
# ============================================
sudo apt update && sudo apt upgrade -y

# ============================================
step 2 "필수 패키지 설치 (Docker, Git, SSH)"
# ============================================
sudo apt install -y \
  docker.io \
  docker-compose-plugin \
  git \
  openssh-server \
  htop \
  vim \
  curl \
  wget \
  net-tools \
  jq

# SSH 서비스 활성화
sudo systemctl enable ssh
sudo systemctl start ssh

# Docker 서비스 확인
if ! sudo systemctl is-active --quiet docker; then
  sudo systemctl start docker
fi
info "Docker 서비스 실행 중"

# ============================================
step 3 "Docker 권한 설정"
# ============================================
sudo usermod -aG docker $CURRENT_USER
warn "Docker 그룹이 추가되었습니다. 스크립트 완료 후 'newgrp docker' 또는 재로그인 필요합니다."

# ============================================
step 4 "Tailscale 설치 (원격 접속용)"
# ============================================
if ! command -v tailscale &> /dev/null; then
  info "Tailscale 설치 중..."
  # 보안: 스크립트를 먼저 다운로드 후 실행
  TAILSCALE_INSTALLER=$(mktemp)
  if curl -fsSL https://tailscale.com/install.sh -o "$TAILSCALE_INSTALLER"; then
    sh "$TAILSCALE_INSTALLER"
    rm -f "$TAILSCALE_INSTALLER"
    info "Tailscale 설치 완료"
  else
    rm -f "$TAILSCALE_INSTALLER"
    warn "Tailscale 설치 실패. 나중에 수동 설치 필요."
  fi
else
  info "Tailscale 이미 설치됨"
fi

# ============================================
step 5 "프로젝트 디렉토리 설정"
# ============================================
PROJECT_DIR="$HOME/anding-cctv-relay"

if [ -d "$PROJECT_DIR" ]; then
  info "기존 프로젝트 디렉토리 존재, git pull 실행"
  cd "$PROJECT_DIR" || error "디렉토리 이동 실패"

  # main 브랜치 확인
  git checkout main 2>/dev/null || true

  # pull 시도
  if ! git pull origin main --ff-only; then
    warn "git pull 실패. 로컬 변경사항이 있을 수 있습니다."
    warn "수동 확인 필요: cd $PROJECT_DIR && git status"
    error "git pull 실패로 설치 중단"
  fi
else
  info "프로젝트 클론 중..."
  if ! git clone https://github.com/muinlab/anding-cctv-relay.git "$PROJECT_DIR"; then
    error "git clone 실패. 네트워크 연결을 확인하세요."
  fi
  cd "$PROJECT_DIR" || error "디렉토리 이동 실패"
fi

# 데이터 디렉토리 생성
mkdir -p "$PROJECT_DIR/data/snapshots" "$PROJECT_DIR/logs/worker"

# ============================================
step 6 "환경변수 파일 설정"
# ============================================
if [ ! -f "$PROJECT_DIR/.env" ]; then
  if [ ! -f "$PROJECT_DIR/.env.example" ]; then
    error ".env.example 파일을 찾을 수 없습니다. 저장소가 손상되었을 수 있습니다."
  fi
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  chmod 600 "$PROJECT_DIR/.env"  # 보안: 소유자만 읽기/쓰기 가능
  warn ".env 파일이 생성되었습니다. (권한: 600)"
  warn "나중에 편집 필요: nano $PROJECT_DIR/.env"
else
  info ".env 파일 이미 존재"
  chmod 600 "$PROJECT_DIR/.env"  # 권한 재확인
fi

# ============================================
step 7 "systemd 서비스 설치"
# ============================================
SYSTEMD_TARGET="/etc/systemd/system/anding-cctv.service"
FUNNEL_SYSTEMD_TARGET="/etc/systemd/system/tailscale-funnel.service"

# anding-cctv 서비스 생성 (변수 직접 대입)
sudo tee "$SYSTEMD_TARGET" > /dev/null <<EOF
[Unit]
Description=Anding CCTV Streaming Service
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR

# 시작 전 이미지 업데이트 (조용히)
ExecStartPre=/usr/bin/docker compose pull --quiet

# 자동 업데이트(watchtower) 포함해서 시작
ExecStart=/usr/bin/docker compose --profile auto-update up -d

# Graceful shutdown: 컨테이너 안전하게 종료
ExecStop=/usr/bin/docker compose --profile auto-update down --timeout 30

# 재시작 (설정 변경 후)
ExecReload=/usr/bin/docker compose --profile auto-update restart

User=$CURRENT_USER
Group=docker
TimeoutStartSec=600
TimeoutStopSec=60

# 환경변수 파일 로드
EnvironmentFile=-$PROJECT_DIR/.env

[Install]
WantedBy=multi-user.target
EOF
info "anding-cctv 서비스 설치 완료"

# Tailscale Funnel 서비스
FUNNEL_SERVICE_FILE="$PROJECT_DIR/systemd/tailscale-funnel.service"
if [ -f "$FUNNEL_SERVICE_FILE" ]; then
  sudo cp "$FUNNEL_SERVICE_FILE" "$FUNNEL_SYSTEMD_TARGET"
  info "tailscale-funnel 서비스 설치 완료"
else
  warn "tailscale-funnel 서비스 파일을 찾을 수 없음"
fi

sudo systemctl daemon-reload

# 서비스 파일 검증
if ! systemctl cat anding-cctv.service >/dev/null 2>&1; then
  error "서비스 파일 검증 실패"
fi

if sudo systemctl enable anding-cctv; then
  info "systemd 서비스 등록 완료 (부팅 시 자동 시작)"
else
  error "서비스 등록 실패"
fi

# ============================================
step 8 "방화벽 설정"
# ============================================
info "방화벽 설정 중..."

# SSH 먼저 허용 (락아웃 방지)
sudo ufw allow ssh

# Tailscale 허용
sudo ufw allow from 100.64.0.0/10 to any comment 'Tailscale'

# 로컬 네트워크 감지 및 go2rtc 포트 허용
LOCAL_IP=$(hostname -I | awk '{print $1}')
if [ -n "$LOCAL_IP" ]; then
  # IP에서 /24 서브넷 추출 (예: 192.168.0.x -> 192.168.0.0/24)
  LOCAL_SUBNET=$(echo "$LOCAL_IP" | sed 's/\.[0-9]*$/.0\/24/')
  sudo ufw allow from "$LOCAL_SUBNET" to any port 1984 comment 'go2rtc local network'
  info "로컬 네트워크: $LOCAL_SUBNET"
else
  # 폴백: 더 넓은 범위 허용
  sudo ufw allow from 192.168.0.0/24 to any port 1984 comment 'go2rtc local network'
  warn "로컬 IP 감지 실패. 192.168.0.0/24 허용"
fi

# 기본 정책 설정
sudo ufw default deny incoming
sudo ufw default allow outgoing

# UFW 활성화
if sudo ufw status | grep -q "Status: active"; then
  info "UFW 이미 활성화됨"
else
  warn "UFW 방화벽을 활성화합니다."
  sudo ufw --force enable
fi

info "방화벽 규칙 적용 완료"

# ============================================
step 9 "타임존 설정"
# ============================================
sudo timedatectl set-timezone Asia/Seoul
info "타임존: Asia/Seoul"

# ============================================
# 완료 메시지
# ============================================
echo ""
echo "========================================="
echo -e "${GREEN}설치 완료!${NC}"
echo "========================================="
echo ""
echo -e "${YELLOW}다음 단계를 순서대로 진행하세요:${NC}"
echo ""
echo "1. Docker 그룹 적용 (터미널 재시작 또는):"
echo "   ${BLUE}newgrp docker${NC}"
echo ""
echo "2. Tailscale 로그인 (원격 접속용):"
echo "   ${BLUE}sudo tailscale up${NC}"
echo ""
echo "3. .env 파일 편집:"
echo "   ${BLUE}nano $PROJECT_DIR/.env${NC}"
echo ""
echo "   필수 항목:"
echo "   - STORE_ID=지점ID"
echo "   - RTSP_HOST=NVR_IP주소"
echo "   - RTSP_PASSWORD=NVR비밀번호 (특수문자 있으면 URL 인코딩 필요)"
echo "   - SUPABASE_URL=https://xxx.supabase.co"
echo "   - SUPABASE_SERVICE_ROLE_KEY=서비스키"
echo ""
echo "4. Tailscale Funnel 활성화 (외부 접속용):"
echo "   ${BLUE}sudo tailscale funnel 1984${NC}"
echo "   → 자동 생성된 URL로 외부에서 접속 가능"
echo ""
echo "5. 서비스 시작:"
echo "   ${BLUE}sudo systemctl start anding-cctv${NC}"
echo ""
echo "6. 상태 확인:"
echo "   ${BLUE}sudo systemctl status anding-cctv${NC}"
echo "   ${BLUE}docker compose ps${NC}"
echo ""
echo "========================================="
echo -e "${GREEN}유용한 명령어${NC}"
echo "========================================="
echo "로그 보기:       docker compose logs -f"
echo "재시작:          sudo systemctl restart anding-cctv"
echo "중지:            sudo systemctl stop anding-cctv"
echo "Tailscale IP:    tailscale ip -4"
echo "Funnel 상태:     tailscale funnel status"
echo "Funnel URL 확인: tailscale funnel status | grep https"
echo "SSH 접속:        ssh $CURRENT_USER@<tailscale-ip>"
echo ""
