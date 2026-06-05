<#
.SYNOPSIS
  ติดตั้ง Auto Bot แบบครบจบในคำสั่งเดียว (Windows / PowerShell)

.DESCRIPTION
  - สร้าง virtual environment (.venv) เพื่อเลี่ยงปัญหาสิทธิ์การเขียนลง system Python
  - ติดตั้ง dependencies จาก requirements.txt
  - ติดตั้ง Chromium ของ Playwright
  - ตรวจ/ติดตั้ง Tesseract-OCR (ผ่าน winget) แล้วตั้ง env var TESSERACT_CMD ให้อัตโนมัติ
  - คัดลอก config ตัวอย่างถ้ายังไม่มี

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#>
[CmdletBinding()]
param(
    [switch]$SkipBrowser,   # ข้ามการดาวน์โหลด Chromium (~140MB) ถ้าไม่ใช้งานเว็บ
    [switch]$SkipTesseract  # ข้ามการติดตั้ง Tesseract ถ้าไม่ใช้ฟีเจอร์ OCR
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "==> Auto Bot setup (root: $root)" -ForegroundColor Cyan

# --- 1. ตรวจ Python ---
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { throw "ไม่พบ Python ใน PATH — ติดตั้ง Python 3.12+ จาก https://www.python.org/ ก่อน" }
$ver = (& python -c "import sys;print('%d.%d'%sys.version_info[:2])")
Write-Host "    Python $ver" -ForegroundColor DarkGray
if ([version]$ver -lt [version]'3.12') { throw "ต้องใช้ Python 3.12 ขึ้นไป (เจอ $ver)" }

# --- 2. สร้าง venv ---
if (-not (Test-Path "$root\.venv")) {
    Write-Host "==> สร้าง virtual environment (.venv)" -ForegroundColor Cyan
    & python -m venv .venv
} else {
    Write-Host "==> ใช้ .venv เดิมที่มีอยู่" -ForegroundColor Cyan
}
$venvPy = "$root\.venv\Scripts\python.exe"

# --- 3. ติดตั้ง dependencies ---
Write-Host "==> ติดตั้ง dependencies" -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt

# --- 4. Playwright Chromium ---
if (-not $SkipBrowser) {
    Write-Host "==> ติดตั้ง Chromium สำหรับ Playwright" -ForegroundColor Cyan
    & $venvPy -m playwright install chromium
} else {
    Write-Host "==> ข้าม Chromium (--SkipBrowser)" -ForegroundColor DarkGray
}

# --- 5. Tesseract-OCR ---
if (-not $SkipTesseract) {
    $tessCmd = Get-Command tesseract -ErrorAction SilentlyContinue
    $tessPaths = @(
        "$env:ProgramFiles\Tesseract-OCR\tesseract.exe",
        "${env:ProgramFiles(x86)}\Tesseract-OCR\tesseract.exe",
        "$env:LOCALAPPDATA\Programs\Tesseract-OCR\tesseract.exe"
    )
    $tessExe = if ($tessCmd) { $tessCmd.Source } else { $tessPaths | Where-Object { Test-Path $_ } | Select-Object -First 1 }

    if (-not $tessExe) {
        $winget = Get-Command winget -ErrorAction SilentlyContinue
        if ($winget) {
            Write-Host "==> ติดตั้ง Tesseract-OCR ผ่าน winget" -ForegroundColor Cyan
            winget install --id UB-Mannheim.TesseractOCR -e --accept-source-agreements --accept-package-agreements --silent
            $tessExe = $tessPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        } else {
            Write-Warning "ไม่พบ winget — ติดตั้ง Tesseract เองจาก https://github.com/UB-Mannheim/tesseract/wiki (ข้าม OCR ได้ด้วย --SkipTesseract)"
        }
    }

    if ($tessExe) {
        [Environment]::SetEnvironmentVariable('TESSERACT_CMD', $tessExe, 'User')
        $env:TESSERACT_CMD = $tessExe
        Write-Host "    Tesseract: $tessExe" -ForegroundColor DarkGray
        Write-Host "    ตั้ง env var TESSERACT_CMD แล้ว (มีผลกับ terminal ที่เปิดใหม่)" -ForegroundColor DarkGray
    }
} else {
    Write-Host "==> ข้าม Tesseract (--SkipTesseract)" -ForegroundColor DarkGray
}

# --- 6. config ตัวอย่าง ---
if ((Test-Path "$root\config\bot_config.example.yaml") -and -not (Test-Path "$root\config\bot_config.yaml")) {
    Copy-Item "$root\config\bot_config.example.yaml" "$root\config\bot_config.yaml"
    Write-Host "==> สร้าง config\bot_config.yaml จากไฟล์ตัวอย่าง" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "เสร็จแล้ว! เริ่มใช้งานด้วย:" -ForegroundColor Green
Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host "    python main.py" -ForegroundColor White
