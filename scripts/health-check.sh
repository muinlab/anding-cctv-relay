#!/bin/bash
# Anding CCTV 헬스 체크 스크립트
# Cron: */5 * * * * /home/anding/anding-cctv-relay/scripts/health-check.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_FILE="$PROJECT_DIR/logs/health.log"

# Discord/Slack 웹훅 (선택)
WEBHOOK_URL="${DISCORD_WEBHOOK_URL:-}"

# 함수 정의
log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

notify() {
  if [ -n "$WEBHOOK_URL" ]; then
    curl -s -H "Content-Type: application/json" \
      -d "{\"content\": \"🚨 CCTV Alert: $1\"}" \
      "$WEBHOOK_URL" > /dev/null
  fi
}

restart_service() {
  local service=$1
  log "Restarting $service..."
  cd "$PROJECT_DIR" && docker compose restart "$service"
}

# 1. go2rtc 상태 체크
if ! curl -sf http://localhost:1984/api > /dev/null 2>&1; then
  log "ERROR: go2rtc is not responding"
  notify "go2rtc 서비스 다운! 재시작 시도 중..."
  restart_service go2rtc
  sleep 10

  if ! curl -sf http://localhost:1984/api > /dev/null 2>&1; then
    log "ERROR: go2rtc restart failed"
    notify "go2rtc 재시작 실패! 수동 확인 필요"
  else
    log "INFO: go2rtc restarted successfully"
    notify "go2rtc 재시작 성공"
  fi
else
  log "OK: go2rtc is healthy"
fi

# 2. cctv-worker 상태 체크
if ! docker ps --format '{{.Names}}' | grep -q "cctv-worker"; then
  log "ERROR: cctv-worker is not running"
  notify "cctv-worker 서비스 다운!"
  restart_service cctv-worker
else
  # 최근 로그에서 에러 확인
  ERRORS=$(docker logs --since 5m cctv-worker 2>&1 | grep -c "ERROR" || true)
  if [ "$ERRORS" -gt 10 ]; then
    log "WARN: cctv-worker has $ERRORS errors in last 5 minutes"
    notify "cctv-worker 에러 다수 발생 ($ERRORS건)"
  else
    log "OK: cctv-worker is running (errors: $ERRORS)"
  fi
fi

# 3. cloudflared 상태 체크
if ! docker ps --format '{{.Names}}' | grep -q "cloudflared"; then
  log "ERROR: cloudflared is not running"
  notify "cloudflared 터널 다운!"
  restart_service cloudflared
else
  log "OK: cloudflared is running"
fi

# 4. 디스크 공간 체크
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
  log "WARN: Disk usage is at ${DISK_USAGE}%"
  notify "디스크 사용량 ${DISK_USAGE}%! 정리 필요"

  # 자동 정리 (90% 이상일 때)
  docker system prune -f > /dev/null 2>&1
  find "$PROJECT_DIR/logs" -type f -mtime +7 -delete
  find "$PROJECT_DIR/data/snapshots" -type f -mtime +3 -delete
else
  log "OK: Disk usage is at ${DISK_USAGE}%"
fi

# 5. 메모리 체크
MEM_USAGE=$(free | awk '/Mem:/ {printf "%.0f", $3/$2 * 100}')
if [ "$MEM_USAGE" -gt 90 ]; then
  log "WARN: Memory usage is at ${MEM_USAGE}%"
  notify "메모리 사용량 ${MEM_USAGE}%!"
else
  log "OK: Memory usage is at ${MEM_USAGE}%"
fi

log "Health check completed"
