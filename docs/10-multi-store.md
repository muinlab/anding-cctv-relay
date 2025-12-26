# 다중 지점 관리

여러 지점에 anding-cctv-relay를 배포하고 관리하는 가이드입니다.

## 아키텍처

```
지점 A (오류동)     지점 B (강남)      지점 C (...)
    │                   │                  │
    ▼                   ▼                  ▼
 미니PC A            미니PC B           미니PC C
    │                   │                  │
    ▼                   ▼                  ▼
Funnel URL A        Funnel URL B       Funnel URL C
    │                   │                  │
    └───────────────────┴──────────────────┘
                        │
                        ▼
                   Supabase
                  (stores 테이블)
                        │
                        ▼
                   admin-web
                (지점 선택 드롭다운)
```

## 지점별 설정

각 지점마다 고유한 설정이 필요합니다:

| 항목 | 지점 A | 지점 B |
|------|--------|--------|
| STORE_ID | oryudong | gangnam |
| RTSP_HOST | 192.168.1.100 | 192.168.1.100 |
| Funnel URL | cctv-oryudong.xxx.ts.net | cctv-gangnam.xxx.ts.net |

## 지점 추가 절차

### 1. 미니PC 설치

1. 미니PC 하드웨어 준비 (Intel N100+ 권장)
2. OS 설치 (Windows 11 / Ubuntu 22.04+)
3. 네트워크 연결 및 NVR 접근 확인

### 2. anding-cctv-relay 배포

```bash
# 자동 설치
curl -fsSL https://raw.githubusercontent.com/muinlab/anding-cctv-relay/main/scripts/install.sh | bash

# 환경변수 설정
nano ~/anding-cctv-relay/.env
```

### 3. 환경변수 설정

```bash
# 필수: 해당 지점의 store_id
STORE_ID=gangnam

# 필수: 해당 지점 NVR 정보
RTSP_HOST=192.168.1.100
RTSP_PORT=554
RTSP_USERNAME=admin
RTSP_PASSWORD=xxx

# Supabase (공통)
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
```

### 4. Tailscale 설정

```bash
# Tailscale 로그인
tailscale up

# 기기 이름 변경 (관리 편의)
# Tailscale Admin Console에서 "minipc-gangnam" 등으로 변경

# Funnel 활성화
tailscale funnel 1984
```

### 5. Supabase 설정

admin-web 지점 관리에서:
1. 해당 지점 선택
2. CCTV 설정 탭
3. "중계 서버 URL"에 Funnel URL 입력
4. 저장

또는 SQL:
```sql
UPDATE stores
SET cctv_base_url = 'https://minipc-gangnam.xxx.ts.net'
WHERE store_id = 'gangnam';
```

### 6. 연동 확인

1. admin-web 로그인
2. 해당 지점 선택
3. CCTV 페이지에서 스트리밍 확인
4. 좌석 현황에서 감지 상태 확인

## 지점 목록 관리

### 현황 표

| 지점 | store_id | cctv_base_url | 상태 |
|------|----------|---------------|------|
| 오류동 | oryudong | https://minipc-oryudong.xxx.ts.net | 운영 중 |
| 강남 | gangnam | https://minipc-gangnam.xxx.ts.net | 설치 예정 |
| ... | ... | ... | ... |

### Tailscale 기기 목록

```bash
# 모든 기기 확인
tailscale status

# 또는 Tailscale Admin Console
https://login.tailscale.com/admin/machines
```

## 중앙 모니터링

### 헬스체크 스크립트

각 지점 상태를 한 번에 확인하는 스크립트:

```bash
#!/bin/bash
# scripts/check-all-stores.sh

STORES=(
  "oryudong|https://minipc-oryudong.xxx.ts.net"
  "gangnam|https://minipc-gangnam.xxx.ts.net"
)

for store in "${STORES[@]}"; do
  IFS='|' read -r name url <<< "$store"

  if curl -sf "$url/api" > /dev/null 2>&1; then
    echo "✅ $name: OK"
  else
    echo "❌ $name: DOWN"
  fi
done
```

### Discord 알림

```bash
# 특정 지점 다운 시 알림
if ! curl -sf "$url/api" > /dev/null 2>&1; then
  curl -H "Content-Type: application/json" \
    -d "{\"content\": \"🚨 $name 지점 CCTV 연결 끊김!\"}" \
    $DISCORD_WEBHOOK
fi
```

## 원격 관리

### SSH 접근

```bash
# Tailscale을 통한 SSH
ssh anding@minipc-oryudong.xxx.ts.net
ssh anding@minipc-gangnam.xxx.ts.net
```

### 일괄 업데이트

```bash
#!/bin/bash
# scripts/update-all.sh

HOSTS=(
  "minipc-oryudong.xxx.ts.net"
  "minipc-gangnam.xxx.ts.net"
)

for host in "${HOSTS[@]}"; do
  echo "Updating $host..."
  ssh anding@$host "cd ~/anding-cctv-relay && git pull && docker compose up -d --build"
done
```

## 트러블슈팅

### 특정 지점만 연결 안 됨

1. Tailscale 상태 확인: `tailscale status`
2. Docker 컨테이너 확인: `docker compose ps`
3. NVR 연결 확인: RTSP URL 테스트

### 모든 지점 연결 안 됨

1. Supabase 상태 확인
2. admin-web 서버 상태 확인
3. 네트워크 전반 이슈 확인

### 지점 추가 후 인식 안 됨

1. `stores.cctv_base_url` 설정 확인
2. `stores.is_active` = true 확인
3. admin-web 캐시 새로고침

## 확장 고려사항

### 10개 이상 지점

- Tailscale ACL로 접근 제어
- 모니터링 대시보드 (Grafana 등) 고려
- 중앙 로그 수집 (Loki 등) 고려

### 지점당 미니PC 여러 대

- 채널 분산: PC1은 ch1-8, PC2는 ch9-16
- 각 PC마다 다른 Funnel URL
- `stores` 테이블에 여러 URL 지원 필요 (추후 구현)
