#!/bin/bash
# Anding CCTV 설정 백업 스크립트

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="$PROJECT_DIR/backups"
DATE=$(date +%Y-%m-%d)
BACKUP_FILE="$BACKUP_DIR/backup-$DATE.tar.gz"

# 백업 디렉토리 생성
mkdir -p "$BACKUP_DIR"

echo "=== Anding CCTV 백업 시작 ==="

# 백업할 파일들
cd "$PROJECT_DIR"
tar -czf "$BACKUP_FILE" \
  --exclude='data/snapshots/*' \
  --exclude='logs/*' \
  --exclude='backups/*' \
  --exclude='.git' \
  .

echo "백업 완료: $BACKUP_FILE"
ls -lh "$BACKUP_FILE"

# 7일 이상 된 백업 삭제
find "$BACKUP_DIR" -name "backup-*.tar.gz" -mtime +7 -delete
echo "오래된 백업 정리 완료"

# 백업 목록
echo ""
echo "현재 백업 목록:"
ls -lh "$BACKUP_DIR"
