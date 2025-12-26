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

# ============================================
step 3 "Docker 권한 설정"
# ============================================
sudo usermod -aG docker $CURRENT_USER

# ============================================
step 4 "Tailscale 설치 (원격 접속용)"
# ============================================
if ! command -v tailscale &> /dev/null; then
  info "Tailscale 설치 중..."
  curl -fsSL https://tailscale.com/install.sh | sh
  info "Tailscale 설치 완료"
else
  info "Tailscale 이미 설치됨"
fi

# ============================================
step 5 "프로젝트 디렉토리 설정"
# ============================================
PROJECT_DIR="$HOME/anding-cctv-relay"

if [ -d "$PROJECT_DIR" ]; then
  info "기존 프로젝트 디렉토리 존재, git pull 실행"
  cd "$PROJECT_DIR"
  git pull origin main
else
  info "프로젝트 클론 중..."
  git clone https://github.com/muinlab/anding-cctv-relay.git "$PROJECT_DIR"
  cd "$PROJECT_DIR"
fi

# 데이터 디렉토리 생성
mkdir -p "$PROJECT_DIR/data/snapshots" "$PROJECT_DIR/logs/worker"

# ============================================
step 6 "환경변수 파일 설정"
# ============================================
if [ ! -f "$PROJECT_DIR/.env" ]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
  warn ".env 파일이 생성되었습니다."
  warn "나중에 편집 필요: nano $PROJECT_DIR/.env"
else
  info ".env 파일 이미 존재"
fi

# ============================================
step 7 "systemd 서비스 설치"
# ============================================
SERVICE_FILE="$PROJECT_DIR/systemd/anding-cctv.service"
SYSTEMD_TARGET="/etc/systemd/system/anding-cctv.service"

if [ -f "$SERVICE_FILE" ]; then
  # 사용자명 치환
  sudo sed "s/anding/$CURRENT_USER/g" "$SERVICE_FILE" | sudo tee "$SYSTEMD_TARGET" > /dev/null
  sudo sed -i "s|/home/anding|$HOME|g" "$SYSTEMD_TARGET"

  sudo systemctl daemon-reload
  sudo systemctl enable anding-cctv
  info "systemd 서비스 설치 완료 (부팅 시 자동 시작)"
else
  warn "systemd 서비스 파일을 찾을 수 없음"
fi

# ============================================
step 8 "방화벽 설정"
# ============================================
info "방화벽 설정 중..."
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH 허용 (로컬 네트워크 + Tailscale)
sudo ufw allow ssh
sudo ufw allow from 100.64.0.0/10 to any  # Tailscale IP 범위

# go2rtc WebUI (로컬 네트워크만)
sudo ufw allow from 192.168.0.0/16 to any port 1984

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
echo "   - RTSP_PASSWORD=NVR비밀번호"
echo "   - CLOUDFLARE_TUNNEL_TOKEN=터널토큰"
echo "   - SUPABASE_URL=https://xxx.supabase.co"
echo "   - SUPABASE_SERVICE_ROLE_KEY=서비스키"
echo ""
echo "4. 서비스 시작:"
echo "   ${BLUE}sudo systemctl start anding-cctv${NC}"
echo ""
echo "5. 상태 확인:"
echo "   ${BLUE}sudo systemctl status anding-cctv${NC}"
echo "   ${BLUE}docker compose ps${NC}"
echo ""
echo "========================================="
echo -e "${GREEN}유용한 명령어${NC}"
echo "========================================="
echo "로그 보기:     docker compose logs -f"
echo "재시작:        sudo systemctl restart anding-cctv"
echo "중지:          sudo systemctl stop anding-cctv"
echo "Tailscale IP:  tailscale ip -4"
echo "SSH 접속:      ssh $CURRENT_USER@<tailscale-ip>"
echo ""
