#!/bin/bash
# 로그 및 임시 파일 정리 스크립트
# Cron: 0 3 * * * /home/anding/anding-cctv-relay/scripts/cleanup-logs.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "[$(date)] 로그 정리 시작"

# 1. 7일 이상 된 로그 파일 삭제
find "$PROJECT_DIR/logs" -type f -mtime +7 -delete
echo "  - 오래된 로그 파일 삭제 완료"

# 2. 3일 이상 된 스냅샷 삭제
find "$PROJECT_DIR/data/snapshots" -type f -mtime +3 -delete
echo "  - 오래된 스냅샷 삭제 완료"

# 3. Docker 정리
docker system prune -f > /dev/null 2>&1
echo "  - Docker 정리 완료"

# 4. 시스템 저널 정리
sudo journalctl --vacuum-time=7d > /dev/null 2>&1
echo "  - 시스템 저널 정리 완료"

# 5. 현재 디스크 사용량 출력
echo ""
echo "디스크 사용량:"
df -h / | tail -1

echo ""
echo "[$(date)] 로그 정리 완료"
