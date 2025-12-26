# Anding CCTV Relay - Windows 설치 스크립트
# PowerShell 관리자 권한으로 실행 필요
# 실행: powershell -ExecutionPolicy Bypass -File install.ps1

param(
    [switch]$SkipDocker,
    [switch]$SkipTailscale,
    [switch]$SkipGit
)

$ErrorActionPreference = "Stop"

# 색상 함수
function Write-Info { param($msg) Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err { param($msg) Write-Host "[ERROR] $msg" -ForegroundColor Red; exit 1 }
function Write-Step { param($step, $total, $msg) Write-Host "`n[$step/$total] $msg" -ForegroundColor Cyan }

# 관리자 권한 체크
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Err "관리자 권한으로 실행하세요. PowerShell을 '관리자 권한으로 실행'해주세요."
}

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Anding CCTV Relay - Windows 설치" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$TOTAL_STEPS = 7
$PROJECT_DIR = "$env:USERPROFILE\anding-cctv-relay"

# ============================================
Write-Step 1 $TOTAL_STEPS "winget 확인"
# ============================================
try {
    $wingetVersion = winget --version
    Write-Info "winget 버전: $wingetVersion"
} catch {
    Write-Err "winget이 설치되어 있지 않습니다. Windows 10 1809 이상 또는 Windows 11이 필요합니다."
}

# ============================================
Write-Step 2 $TOTAL_STEPS "Docker Desktop 설치"
# ============================================
if (-not $SkipDocker) {
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerPath) {
        Write-Info "Docker Desktop 이미 설치됨"
    } else {
        Write-Info "Docker Desktop 설치 중... (시간이 걸릴 수 있습니다)"
        winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
        Write-Warn "Docker Desktop 설치 완료. 설치 후 재부팅이 필요할 수 있습니다."
        Write-Warn "재부팅 후 Docker Desktop을 실행하고 이 스크립트를 다시 실행하세요."
    }
} else {
    Write-Info "Docker 설치 건너뜀 (-SkipDocker)"
}

# Docker 실행 확인
try {
    $dockerVersion = docker --version 2>$null
    Write-Info "Docker: $dockerVersion"
} catch {
    Write-Warn "Docker가 아직 실행 중이 아닙니다."
    Write-Warn "Docker Desktop을 실행하고 완전히 시작될 때까지 기다린 후 다시 실행하세요."
    Write-Host ""
    Write-Host "Docker Desktop 실행 방법:" -ForegroundColor Yellow
    Write-Host "1. 시작 메뉴에서 'Docker Desktop' 검색" -ForegroundColor White
    Write-Host "2. Docker Desktop 실행" -ForegroundColor White
    Write-Host "3. 트레이 아이콘이 'Docker Desktop is running'이 될 때까지 대기" -ForegroundColor White
    Write-Host "4. 이 스크립트 다시 실행" -ForegroundColor White
    exit 1
}

# ============================================
Write-Step 3 $TOTAL_STEPS "Git 설치"
# ============================================
if (-not $SkipGit) {
    try {
        $gitVersion = git --version 2>$null
        Write-Info "Git: $gitVersion"
    } catch {
        Write-Info "Git 설치 중..."
        winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
        # PATH 갱신
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Write-Info "Git 설치 완료"
    }
} else {
    Write-Info "Git 설치 건너뜀 (-SkipGit)"
}

# ============================================
Write-Step 4 $TOTAL_STEPS "Tailscale 설치"
# ============================================
if (-not $SkipTailscale) {
    $tailscalePath = "C:\Program Files\Tailscale\tailscale.exe"
    if (Test-Path $tailscalePath) {
        Write-Info "Tailscale 이미 설치됨"
    } else {
        Write-Info "Tailscale 설치 중..."
        winget install -e --id Tailscale.Tailscale --accept-source-agreements --accept-package-agreements
        Write-Info "Tailscale 설치 완료"
    }

    # Tailscale 로그인 안내
    try {
        $tsStatus = & "C:\Program Files\Tailscale\tailscale.exe" status 2>$null
        if ($tsStatus -match "Logged out" -or $tsStatus -match "NeedsLogin") {
            Write-Warn "Tailscale 로그인이 필요합니다."
            Write-Host "트레이의 Tailscale 아이콘을 클릭하여 로그인하세요." -ForegroundColor Yellow
        } else {
            Write-Info "Tailscale 로그인 완료"
        }
    } catch {
        Write-Warn "Tailscale 상태를 확인할 수 없습니다. 설치 후 로그인하세요."
    }
} else {
    Write-Info "Tailscale 설치 건너뜀 (-SkipTailscale)"
}

# ============================================
Write-Step 5 $TOTAL_STEPS "프로젝트 다운로드"
# ============================================
if (Test-Path $PROJECT_DIR) {
    Write-Info "기존 프로젝트 존재, 업데이트 중..."
    Set-Location $PROJECT_DIR
    git pull origin main --ff-only
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "git pull 실패. 로컬 변경사항이 있을 수 있습니다."
        Write-Warn "수동 확인 필요: cd $PROJECT_DIR; git status"
    }
} else {
    Write-Info "프로젝트 클론 중..."
    git clone https://github.com/muinlab/anding-cctv-relay.git $PROJECT_DIR
    Set-Location $PROJECT_DIR
}

# 데이터 디렉토리 생성
New-Item -ItemType Directory -Force -Path "$PROJECT_DIR\data\snapshots" | Out-Null
New-Item -ItemType Directory -Force -Path "$PROJECT_DIR\logs\worker" | Out-Null
Write-Info "데이터 디렉토리 생성 완료"

# ============================================
Write-Step 6 $TOTAL_STEPS ".env 파일 설정"
# ============================================
$envFile = "$PROJECT_DIR\.env"
$envExample = "$PROJECT_DIR\.env.example"

if (-not (Test-Path $envFile)) {
    if (Test-Path $envExample) {
        Copy-Item $envExample $envFile
        Write-Warn ".env 파일이 생성되었습니다."
        Write-Warn "메모장으로 편집하세요: notepad $envFile"
    } else {
        Write-Err ".env.example 파일을 찾을 수 없습니다."
    }
} else {
    Write-Info ".env 파일 이미 존재"
}

# ============================================
Write-Step 7 $TOTAL_STEPS "시작 프로그램 등록 (자동 시작)"
# ============================================
$taskName = "AndingCCTV"
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Info "기존 예약 작업 업데이트 중..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

# Docker Compose 시작 스크립트 생성
$startScript = @"
@echo off
cd /d "$PROJECT_DIR"
docker compose --profile auto-update up -d
"@
$startScriptPath = "$PROJECT_DIR\scripts\start.bat"
$startScript | Out-File -FilePath $startScriptPath -Encoding ASCII

# 종료 스크립트 생성
$stopScript = @"
@echo off
cd /d "$PROJECT_DIR"
docker compose --profile auto-update down --timeout 30
"@
$stopScriptPath = "$PROJECT_DIR\scripts\stop.bat"
$stopScript | Out-File -FilePath $stopScriptPath -Encoding ASCII

# 예약 작업 생성 (로그온 시 실행)
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$startScriptPath`"" -WorkingDirectory $PROJECT_DIR
$trigger = New-ScheduledTaskTrigger -AtLogOn
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Anding CCTV Relay 자동 시작" | Out-Null
Write-Info "시작 프로그램 등록 완료 (로그온 시 자동 시작)"

# ============================================
# 완료 메시지
# ============================================
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  설치 완료!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계를 순서대로 진행하세요:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. .env 파일 편집:" -ForegroundColor White
Write-Host "   notepad $envFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "   필수 항목:" -ForegroundColor White
Write-Host "   - STORE_ID=지점ID" -ForegroundColor Gray
Write-Host "   - RTSP_HOST=NVR_IP주소" -ForegroundColor Gray
Write-Host "   - RTSP_PASSWORD=NVR비밀번호" -ForegroundColor Gray
Write-Host "   - SUPABASE_URL=https://xxx.supabase.co" -ForegroundColor Gray
Write-Host "   - SUPABASE_SERVICE_ROLE_KEY=서비스키" -ForegroundColor Gray
Write-Host ""
Write-Host "2. Tailscale 로그인 (트레이 아이콘 클릭)" -ForegroundColor White
Write-Host ""
Write-Host "3. 서비스 시작:" -ForegroundColor White
Write-Host "   cd $PROJECT_DIR" -ForegroundColor Cyan
Write-Host "   docker compose --profile auto-update up -d" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. Tailscale Funnel 활성화 (PowerShell 관리자):" -ForegroundColor White
Write-Host "   & 'C:\Program Files\Tailscale\tailscale.exe' funnel 1984" -ForegroundColor Cyan
Write-Host ""
Write-Host "5. 상태 확인:" -ForegroundColor White
Write-Host "   docker compose ps" -ForegroundColor Cyan
Write-Host "   docker compose logs -f" -ForegroundColor Cyan
Write-Host ""
Write-Host "=========================================" -ForegroundColor Green
Write-Host "  유용한 명령어" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
Write-Host "로그 보기:       docker compose logs -f" -ForegroundColor White
Write-Host "재시작:          docker compose restart" -ForegroundColor White
Write-Host "중지:            .\scripts\stop.bat" -ForegroundColor White
Write-Host "시작:            .\scripts\start.bat" -ForegroundColor White
Write-Host "Tailscale IP:    & 'C:\Program Files\Tailscale\tailscale.exe' ip -4" -ForegroundColor White
Write-Host "Funnel 상태:     & 'C:\Program Files\Tailscale\tailscale.exe' funnel status" -ForegroundColor White
Write-Host ""

# .env 편집 프롬프트
Write-Host "지금 .env 파일을 편집하시겠습니까? (Y/N): " -ForegroundColor Yellow -NoNewline
$response = Read-Host
if ($response -eq "Y" -or $response -eq "y") {
    notepad $envFile
}
