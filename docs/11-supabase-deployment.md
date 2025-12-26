# Supabase 기반 신규 지점 배포 가이드

이 문서는 새로운 스터디카페 지점에 CCTV 릴레이 서버를 설치하고 Supabase를 통해 자동 배포하는 방법을 설명합니다.

## 전체 흐름

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. Supabase    │     │  2. 지점 PC     │     │  3. GitHub      │
│  stores 설정    │────▶│  러너 설치      │────▶│  Actions 배포   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
         │                      │                       │
         ▼                      ▼                       ▼
   RTSP/채널 정보        self-hosted runner      자동 배포 트리거
   cctv_base_url         Tailscale Funnel        go2rtc 설정 생성
```

## 1단계: Supabase stores 테이블 설정

### stores 테이블 스키마

```sql
CREATE TABLE stores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id TEXT UNIQUE NOT NULL,          -- 지점 식별자 (예: oryudong)
  store_name TEXT NOT NULL,               -- 지점명 (예: 앤딩스터디카페 오류동역점)

  -- NVR 연결 정보
  rtsp_host TEXT NOT NULL,                -- NVR IP 주소 (예: 218.50.241.157)
  rtsp_port INTEGER DEFAULT 8554,         -- RTSP 포트
  rtsp_username TEXT DEFAULT 'admin',     -- NVR 사용자명
  rtsp_password TEXT,                     -- NVR 비밀번호

  -- 채널 설정
  active_channels INTEGER[] NOT NULL,     -- 활성 채널 배열 (예: [1,2,3,4])

  -- 외부 접속 URL (Tailscale Funnel)
  cctv_base_url TEXT,                     -- 예: https://desktop-v4qfv1i.tail48e9b8.ts.net

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 새 지점 추가 예시

```sql
INSERT INTO stores (
  store_id,
  store_name,
  rtsp_host,
  rtsp_port,
  rtsp_username,
  rtsp_password,
  active_channels,
  cctv_base_url
) VALUES (
  'gangnam',
  '앤딩스터디카페 강남구청역점',
  '192.168.1.100',
  8554,
  'admin',
  'your-nvr-password',
  ARRAY[1, 2, 3, 4, 5, 6, 7, 8],
  NULL  -- Tailscale Funnel 설정 후 업데이트
);
```

## 2단계: 지점 PC 설정

### 2.1 필수 소프트웨어 설치

```bash
# Ubuntu/WSL2 기준
sudo apt update
sudo apt install -y docker.io docker-compose-v2 curl jq git

# user를 docker 그룹에 추가 (sudo 없이 docker 사용)
sudo usermod -aG docker $USER
newgrp docker
```

### 2.2 Tailscale 설치 및 Funnel 활성화

```bash
# Tailscale 설치
curl -fsSL https://tailscale.com/install.sh | sh

# Tailscale 로그인
sudo tailscale up

# Funnel 활성화 (go2rtc 포트)
sudo tailscale funnel 1984

# Funnel URL 확인
tailscale funnel status
# 출력 예: https://your-machine-name.tail12345.ts.net
```

> **중요**: Funnel 활성화 시 tailnet 설정에서 Funnel이 허용되어 있어야 합니다.
> https://login.tailscale.com/admin/acls 에서 확인

### 2.3 Supabase에 cctv_base_url 업데이트

Tailscale Funnel URL을 확인한 후 Supabase stores 테이블 업데이트:

```sql
UPDATE stores
SET cctv_base_url = 'https://your-machine-name.tail12345.ts.net'
WHERE store_id = 'gangnam';
```

## 3단계: GitHub Actions Self-Hosted Runner 설치

### 3.1 Runner 다운로드 및 설정

```bash
# Runner 디렉토리 생성
mkdir ~/actions-runner && cd ~/actions-runner

# Runner 다운로드 (최신 버전은 GitHub에서 확인)
curl -o actions-runner-linux-x64-2.321.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.321.0/actions-runner-linux-x64-2.321.0.tar.gz

# 압축 해제
tar xzf ./actions-runner-linux-x64-2.321.0.tar.gz

# 의존성 설치
sudo ./bin/installdependencies.sh
```

### 3.2 Runner 등록

GitHub 레포지토리 → Settings → Actions → Runners → New self-hosted runner에서 토큰 확인 후:

```bash
./config.sh --url https://github.com/muinlab/anding-cctv-relay \
  --token YOUR_RUNNER_TOKEN \
  --name "지점명-runner" \
  --labels "self-hosted,Linux,X64,지점store_id,cctv-relay" \
  --work "_work"
```

**라벨 설명**:
- `self-hosted`: 기본 라벨
- `지점store_id`: 해당 지점만 타겟팅 (예: `oryudong`, `gangnam`)
- `cctv-relay`: 이 프로젝트 전용

### 3.3 서비스로 등록 (자동 시작)

```bash
# 서비스 설치
sudo ./svc.sh install

# 서비스 시작
sudo ./svc.sh start

# 상태 확인
sudo ./svc.sh status
```

## 4단계: GitHub Actions 워크플로우

### deploy.yml 구조

```yaml
name: Deploy to CCTV Relay Servers

on:
  push:
    branches:
      - deploy  # deploy 브랜치에 머지 시 자동 배포

jobs:
  deploy-gangnam:  # 각 지점별 job 추가
    name: Deploy to 강남구청역점
    runs-on: [self-hosted, gangnam]  # 지점 라벨로 타겟팅
    env:
      STORE_ID: gangnam
      SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
      SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}

    steps:
      - uses: actions/checkout@v4

      - name: Generate go2rtc config from Supabase
        run: ./scripts/generate-go2rtc-config.sh

      - name: Restart services
        run: |
          docker compose down
          docker compose up -d go2rtc

      - name: Health check
        run: |
          sleep 5
          curl -sf http://localhost:1984/api || exit 1
```

### 새 지점 추가 시 워크플로우 수정

`.github/workflows/deploy.yml`에 새 job 추가:

```yaml
  deploy-신규지점:
    name: Deploy to 신규지점명
    runs-on: [self-hosted, 신규store_id]
    env:
      STORE_ID: 신규store_id
      # ... 동일한 구조
```

## 5단계: 배포 실행

### 초기 배포

```bash
# 로컬에서
git checkout main
git pull origin main

# deploy 브랜치로 머지
git checkout deploy
git merge main
git push origin deploy
```

### 배포 확인

1. GitHub Actions 탭에서 워크플로우 실행 상태 확인
2. 지점 PC에서 상태 확인:
   ```bash
   docker compose ps
   curl http://localhost:1984/api/streams | jq 'keys'
   ```
3. 외부 접속 테스트:
   ```bash
   curl https://your-machine-name.tail12345.ts.net/api/streams
   ```

## 동적 설정 생성 원리

`scripts/generate-go2rtc-config.sh`는 다음을 수행합니다:

1. Supabase에서 `stores` 테이블 조회 (STORE_ID 기준)
2. RTSP 연결 정보 및 active_channels 파싱
3. go2rtc.yaml 동적 생성:

```yaml
streams:
  ch1:
    - "rtsp://admin:password@192.168.1.100:8554/live_01"
  ch2:
    - "rtsp://admin:password@192.168.1.100:8554/live_02"
  # ... active_channels의 각 채널
```

## 체크리스트

### 신규 지점 설정 체크리스트

- [ ] Supabase stores 테이블에 지점 정보 추가
- [ ] 지점 PC에 Docker, Tailscale 설치
- [ ] Tailscale Funnel 활성화 및 URL 확인
- [ ] Supabase에 cctv_base_url 업데이트
- [ ] GitHub Actions self-hosted runner 설치 및 등록
- [ ] `.github/workflows/deploy.yml`에 지점 job 추가
- [ ] deploy 브랜치에 머지하여 배포 테스트
- [ ] 외부 접속 테스트 (Tailscale Funnel URL)

## 문제 해결

### Runner가 offline으로 표시됨

```bash
# 서비스 상태 확인
sudo ./svc.sh status

# 서비스 재시작
sudo ./svc.sh stop
sudo ./svc.sh start
```

### Docker 권한 오류

```bash
# user가 docker 그룹에 있는지 확인
groups $USER

# 없다면 추가
sudo usermod -aG docker $USER
# 로그아웃 후 다시 로그인 필요
```

### Supabase 연결 실패

```bash
# 환경변수 확인
echo $SUPABASE_URL
echo $SUPABASE_SERVICE_ROLE_KEY

# 직접 테스트
curl "${SUPABASE_URL}/rest/v1/stores?store_id=eq.your_store_id" \
  -H "apikey: ${SUPABASE_SERVICE_ROLE_KEY}" \
  -H "Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}"
```

### Tailscale Funnel 접속 불가

```bash
# Funnel 상태 확인
tailscale funnel status

# Funnel이 비활성화되어 있다면
sudo tailscale funnel 1984
```
