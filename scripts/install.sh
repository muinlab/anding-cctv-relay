#!/bin/bash
# Anding CCTV Relay 초기 설치 스크립트
set -e

echo "=== Anding CCTV Relay 설치 ==="

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 함수 정의
info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 루트 체크
if [ "$EUID" -eq 0 ]; then
  error "root로 실행하지 마세요. 일반 사용자로 실행하세요."
fi

# 1. 시스템 업데이트
info "시스템 패키지 업데이트 중..."
sudo apt update && sudo apt upgrade -y

# 2. 필수 패키지 설치
info "필수 패키지 설치 중..."
sudo apt install -y \
  docker.io \
  docker-compose-plugin \
  git \
  htop \
  vim \
  curl \
  wget \
  net-tools \
  jq

# 3. Docker 권한 설정
info "Docker 권한 설정 중..."
sudo usermod -aG docker $USER

# 4. 디렉토리 생성
info "디렉토리 생성 중..."
mkdir -p ~/anding-cctv-relay/{data/snapshots,logs/worker}

# 5. 환경변수 파일 확인
if [ ! -f ~/anding-cctv-relay/.env ]; then
  if [ -f ~/anding-cctv-relay/.env.example ]; then
    cp ~/anding-cctv-relay/.env.example ~/anding-cctv-relay/.env
    warn ".env 파일이 생성되었습니다. 편집해주세요:"
    warn "  nano ~/anding-cctv-relay/.env"
  else
    error ".env.example 파일을 찾을 수 없습니다."
  fi
fi

# 6. systemd 서비스 설치
info "systemd 서비스 설치 중..."
if [ -f ~/anding-cctv-relay/systemd/anding-cctv.service ]; then
  sudo cp ~/anding-cctv-relay/systemd/anding-cctv.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable anding-cctv
  info "systemd 서비스가 설치되었습니다."
fi

# 7. 방화벽 설정
info "방화벽 설정 중..."
sudo ufw --force enable
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from 192.168.0.0/24 to any port 22
sudo ufw allow from 192.168.0.0/24 to any port 1984

# 8. 타임존 설정
info "타임존 설정 중..."
sudo timedatectl set-timezone Asia/Seoul

# 9. 완료 메시지
echo ""
echo "==================================="
echo -e "${GREEN}설치 완료!${NC}"
echo "==================================="
echo ""
echo "다음 단계:"
echo "1. .env 파일 편집:"
echo "   nano ~/anding-cctv-relay/.env"
echo ""
echo "2. Docker 그룹 적용 (재로그인 또는):"
echo "   newgrp docker"
echo ""
echo "3. 서비스 시작:"
echo "   cd ~/anding-cctv-relay && docker compose up -d"
echo ""
echo "4. 상태 확인:"
echo "   docker compose ps"
echo ""
