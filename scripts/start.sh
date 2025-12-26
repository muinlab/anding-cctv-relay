#!/bin/bash
# CCTV Relay 서버 시작 스크립트
#
# 1. Supabase에서 설정 가져와서 go2rtc.yaml 생성
# 2. Docker Compose 실행
#
# 사용법:
#   ./scripts/start.sh [서비스명...]
#
# 예시:
#   ./scripts/start.sh              # 모든 서비스 시작
#   ./scripts/start.sh go2rtc       # go2rtc만 시작
#   ./scripts/start.sh --build      # 빌드 후 시작

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "=========================================="
echo "  Anding CCTV Relay Server"
echo "=========================================="
echo ""

# 1. go2rtc.yaml 동적 생성
echo "[1/2] Generating go2rtc config from Supabase..."
if ! "$SCRIPT_DIR/generate-go2rtc-config.sh"; then
    echo "Warning: Failed to generate config, using existing go2rtc.yaml"
fi
echo ""

# 2. Docker Compose 실행
echo "[2/2] Starting Docker containers..."
docker compose up -d "$@"
echo ""

# 상태 출력
echo "=========================================="
echo "  Services Status"
echo "=========================================="
docker compose ps
echo ""

# 접속 정보 출력
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null || echo "localhost")
echo "=========================================="
echo "  Access URLs"
echo "=========================================="
echo "  go2rtc WebUI: http://${TAILSCALE_IP}:1984/"
echo "  Debug Stream: http://${TAILSCALE_IP}:8001/debug/"
echo "=========================================="
