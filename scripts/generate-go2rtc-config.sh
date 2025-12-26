#!/bin/bash
# Supabase stores 테이블에서 설정을 가져와 go2rtc.yaml 동적 생성
#
# 사용법:
#   ./scripts/generate-go2rtc-config.sh
#
# 필요 환경변수:
#   - STORE_ID
#   - SUPABASE_URL
#   - SUPABASE_SERVICE_ROLE_KEY

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# .env 파일 로드
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    source "$PROJECT_DIR/.env"
    set +a
fi

# 필수 환경변수 확인
if [ -z "$STORE_ID" ] || [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    echo "Error: Required environment variables not set"
    echo "  STORE_ID: ${STORE_ID:-<not set>}"
    echo "  SUPABASE_URL: ${SUPABASE_URL:-<not set>}"
    echo "  SUPABASE_SERVICE_ROLE_KEY: ${SUPABASE_SERVICE_ROLE_KEY:+<set>}${SUPABASE_SERVICE_ROLE_KEY:-<not set>}"
    exit 1
fi

echo "Fetching store config from Supabase..."
echo "  Store ID: $STORE_ID"

# Supabase에서 store 정보 가져오기
STORE_DATA=$(curl -s "${SUPABASE_URL}/rest/v1/stores?store_id=eq.${STORE_ID}&select=*" \
    -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
    -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}")

# 데이터 확인
if [ "$(echo "$STORE_DATA" | jq 'length')" -eq 0 ]; then
    echo "Error: Store '$STORE_ID' not found in Supabase"
    exit 1
fi

# 설정값 파싱
STORE_NAME=$(echo "$STORE_DATA" | jq -r '.[0].store_name')
RTSP_HOST=$(echo "$STORE_DATA" | jq -r '.[0].rtsp_host // empty')
RTSP_PORT=$(echo "$STORE_DATA" | jq -r '.[0].rtsp_port // 554')
RTSP_USERNAME=$(echo "$STORE_DATA" | jq -r '.[0].rtsp_username // "admin"')
RTSP_PASSWORD=$(echo "$STORE_DATA" | jq -r '.[0].rtsp_password // empty')
ACTIVE_CHANNELS=$(echo "$STORE_DATA" | jq -r '.[0].active_channels // []')
CHANNEL_COUNT=$(echo "$ACTIVE_CHANNELS" | jq 'length')

echo "  Store Name: $STORE_NAME"
echo "  RTSP Host: $RTSP_HOST"
echo "  RTSP Port: $RTSP_PORT"
echo "  Active Channels: $CHANNEL_COUNT"

# RTSP 호스트 확인
if [ -z "$RTSP_HOST" ] || [ "$RTSP_HOST" = "null" ]; then
    echo "Warning: RTSP host not configured in Supabase, using environment variable"
    RTSP_HOST="${RTSP_HOST:-localhost}"
fi

# go2rtc.yaml 생성
CONFIG_FILE="$PROJECT_DIR/go2rtc/go2rtc.yaml"
echo "Generating $CONFIG_FILE..."

cat > "$CONFIG_FILE" << EOF
# go2rtc 설정 파일 (자동 생성)
# Store: $STORE_NAME ($STORE_ID)
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Channels: $CHANNEL_COUNT

log:
  level: info

# API 서버 (WebUI + REST)
api:
  listen: ":1984"
  origin: "*"

# RTSP 출력 서버 (cctv-worker용)
rtsp:
  listen: ":8554"
  default_query: "video"

# WebRTC 설정
webrtc:
  listen: ":8555/tcp"
  candidates:
    - stun:stun.l.google.com:19302
    - stun:stun1.l.google.com:19302

# HLS 스트리밍 (WebRTC 실패시 폴백)
hls:

# FFmpeg 설정 (트랜스코딩 필요시)
ffmpeg:
  bin: ffmpeg

# 스트림 정의 (Supabase에서 동적 생성)
streams:
EOF

# 각 채널에 대해 스트림 추가
for ch in $(echo "$ACTIVE_CHANNELS" | jq -r '.[]'); do
    printf "  ch%d:\n" "$ch" >> "$CONFIG_FILE"
    printf "    - \"rtsp://%s:%s@%s:%s/live_%02d\"\n" \
        "$RTSP_USERNAME" "$RTSP_PASSWORD" "$RTSP_HOST" "$RTSP_PORT" "$ch" >> "$CONFIG_FILE"
    printf "\n" >> "$CONFIG_FILE"
done

echo ""
echo "Generated go2rtc.yaml with $CHANNEL_COUNT channels:"
echo "$ACTIVE_CHANNELS" | jq -r '.[] | "  - ch\(.)"'
echo ""
echo "Done! Restart go2rtc to apply changes:"
echo "  docker compose restart go2rtc"
