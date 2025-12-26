# 운영 및 모니터링

## 서비스 관리

### 시작

```bash
cd ~/anding-cctv-relay
docker compose up -d
```

### 정지

```bash
docker compose down
```

### 재시작

```bash
docker compose restart
# 또는 특정 서비스만
docker compose restart go2rtc
```

### 상태 확인

```bash
docker compose ps
```

```
NAME          STATUS         PORTS
go2rtc        Up (healthy)   1984/tcp, 8554/tcp, 8555/tcp
cctv-worker   Up
cloudflared   Up
```

## 로그 확인

### 실시간 로그

```bash
# 전체
docker compose logs -f

# 특정 서비스
docker compose logs -f go2rtc
docker compose logs -f cctv-worker
```

### 로그 파일

```bash
# 호스트에 저장된 로그
ls -la ~/anding-cctv-relay/logs/
```

## systemd 서비스

### 서비스 파일 설치

```bash
sudo cp ~/anding-cctv-relay/systemd/anding-cctv.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable anding-cctv
```

### 서비스 관리

```bash
# 시작
sudo systemctl start anding-cctv

# 정지
sudo systemctl stop anding-cctv

# 상태
sudo systemctl status anding-cctv

# 로그
sudo journalctl -u anding-cctv -f
```

## 모니터링

### 리소스 사용량

```bash
# 실시간 모니터링
htop

# Docker 리소스
docker stats
```

### 기대 리소스 사용량

| 서비스 | CPU | RAM |
|--------|-----|-----|
| go2rtc | 5-15% | 100-200MB |
| cctv-worker | 20-40% | 500MB-1GB |
| cloudflared | 1-5% | 50-100MB |
| **합계** | **30-60%** | **~1.5GB** |

### 디스크 사용량

```bash
# 전체
df -h

# Docker
docker system df

# 로그 크기
du -sh ~/anding-cctv-relay/logs/
```

## 헬스 체크 스크립트

```bash
# scripts/health-check.sh 실행
~/anding-cctv-relay/scripts/health-check.sh
```

### Cron 설정

```bash
crontab -e
```

```
# 5분마다 헬스 체크
*/5 * * * * /home/anding/anding-cctv-relay/scripts/health-check.sh >> /home/anding/anding-cctv-relay/logs/health.log 2>&1

# 매일 로그 정리
0 3 * * * /home/anding/anding-cctv-relay/scripts/cleanup-logs.sh
```

## 알림 설정 (선택)

### Discord Webhook

```bash
# scripts/notify.sh
#!/bin/bash
WEBHOOK_URL="https://discord.com/api/webhooks/xxx"

notify() {
  curl -H "Content-Type: application/json" \
    -d "{\"content\": \"$1\"}" \
    $WEBHOOK_URL
}

notify "CCTV Alert: $1"
```

### 사용 예

```bash
# health-check.sh에서
if ! curl -sf http://localhost:1984/api > /dev/null; then
  ~/scripts/notify.sh "go2rtc 서비스 다운!"
fi
```

## 백업

### 설정 백업

```bash
# scripts/backup.sh 실행
~/anding-cctv-relay/scripts/backup.sh
```

### 복원

```bash
cd ~/anding-cctv-relay
tar -xzf backup-2024-01-15.tar.gz
docker compose up -d
```

## 업데이트

### 수동 업데이트

```bash
cd ~/anding-cctv-relay
git pull
docker compose pull
docker compose up -d
```

### 자동 업데이트 (Watchtower)

```bash
# auto-update 프로필 활성화
docker compose --profile auto-update up -d
```

## 장애 대응

### 서비스 다운 시

```bash
# 1. 상태 확인
docker compose ps

# 2. 로그 확인
docker compose logs --tail 50 [서비스명]

# 3. 재시작
docker compose restart [서비스명]

# 4. 전체 재시작
docker compose down && docker compose up -d
```

### 디스크 풀 시

```bash
# Docker 정리
docker system prune -a

# 로그 정리
rm -rf ~/anding-cctv-relay/logs/*

# 스냅샷 정리
rm -rf ~/anding-cctv-relay/data/snapshots/*
```

### 메모리 부족 시

```bash
# 스왑 추가
sudo fallocate -l 2G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
```

## 원격 접속

### SSH 터널

```bash
# 로컬에서 미니PC의 go2rtc WebUI 접속
ssh -L 1984:localhost:1984 anding@192.168.0.10

# 브라우저에서
http://localhost:1984
```

### Tailscale (추천)

```bash
# 미니PC에 Tailscale 설치
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# 어디서든 접속 가능
ssh anding@mini-pc.tail12345.ts.net
```
