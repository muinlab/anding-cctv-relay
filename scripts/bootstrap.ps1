# Anding CCTV Relay 부트스트랩
# 관리자 권한 자동 요청 후 설치 스크립트 실행
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "관리자 권한 요청 중..." -ForegroundColor Yellow
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"irm https://raw.githubusercontent.com/muinlab/anding-cctv-relay/main/scripts/install.ps1 | iex`""
    exit
}

# 이미 관리자면 바로 실행
irm https://raw.githubusercontent.com/muinlab/anding-cctv-relay/main/scripts/install.ps1 | iex
