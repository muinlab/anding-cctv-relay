# Ubuntu 초기 설정

## 1. Ubuntu 설치

### 부팅 USB 만들기

1. [Ubuntu 22.04 LTS Server](https://ubuntu.com/download/server) 다운로드
2. [Rufus](https://rufus.ie/) 또는 [balenaEtcher](https://etcher.io/)로 USB 굽기
3. 미니PC BIOS에서 USB 부팅

### 설치 옵션

- Language: English (서버 호환성)
- Keyboard: Korean
- Network: DHCP (나중에 고정 IP 설정)
- Storage: Use entire disk
- Username: `anding`
- Server name: `cctv-oryudong`

## 2. 초기 설정

### SSH 접속

```bash
ssh anding@192.168.0.10
```

### 시스템 업데이트

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  docker.io \
  docker-compose-plugin \
  git \
  htop \
  vim \
  curl \
  wget \
  net-tools
```

### Docker 권한

```bash
sudo usermod -aG docker $USER
newgrp docker

# 확인
docker ps
```

## 3. 고정 IP 설정

### Netplan 설정

```bash
sudo nano /etc/netplan/00-installer-config.yaml
```

```yaml
network:
  version: 2
  ethernets:
    enp1s0:  # 네트워크 인터페이스명 확인: ip a
      dhcp4: no
      addresses:
        - 192.168.0.10/24
      routes:
        - to: default
          via: 192.168.0.1
      nameservers:
        addresses:
          - 8.8.8.8
          - 1.1.1.1
```

```bash
sudo netplan apply
```

## 4. 방화벽 설정

```bash
sudo ufw enable
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH (로컬 네트워크만)
sudo ufw allow from 192.168.0.0/24 to any port 22

# go2rtc WebUI (로컬만)
sudo ufw allow from 192.168.0.0/24 to any port 1984

# 상태 확인
sudo ufw status
```

## 5. 타임존 설정

```bash
sudo timedatectl set-timezone Asia/Seoul
timedatectl
```

## 6. 스왑 설정 (RAM 4GB인 경우)

```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# 영구 적용
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 7. 자동 업데이트 비활성화 (안정성)

```bash
sudo systemctl disable unattended-upgrades
sudo systemctl stop unattended-upgrades
```

## 8. 프로젝트 설정

```bash
cd ~
git clone https://github.com/muinlab/anding-cctv-relay.git
cd anding-cctv-relay

# 환경변수 설정
cp .env.example .env
nano .env
```

## 9. NVR 연결 테스트

```bash
# ping 테스트
ping 192.168.0.100

# RTSP 테스트 (ffprobe)
docker run --rm -it linuxserver/ffmpeg \
  ffprobe -v quiet -print_format json -show_streams \
  "rtsp://admin:password@192.168.0.100:554/live_01"
```

## 체크리스트

- [ ] Ubuntu 설치 완료
- [ ] Docker 설치 및 권한 설정
- [ ] 고정 IP 설정
- [ ] 방화벽 설정
- [ ] NVR ping 성공
- [ ] RTSP 연결 테스트 성공
