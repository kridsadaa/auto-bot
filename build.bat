@echo off
setlocal
echo Building AutoBot.exe...

REM ใช้ python ของ .venv เสมอ — กัน lib แปลกปลอม (torch/scipy ฯลฯ) จาก global
REM site-packages หลุดเข้า exe ทำให้ไฟล์ใหญ่เกินจำเป็นและ build ช้า
set "VENV_PY=.venv\Scripts\python.exe"

REM สร้าง .venv + ติดตั้ง dependencies ถ้ายังไม่มี (ครั้งแรกเท่านั้น)
if not exist "%VENV_PY%" (
    echo No .venv found - creating a clean virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo สร้าง .venv ไม่ได้ - ตรวจว่าติดตั้ง Python 3.12+ และอยู่ใน PATH แล้ว
        pause
        exit /b 1
    )
    echo Installing project dependencies into .venv ^(ครั้งแรกอาจใช้เวลาสักครู่^)...
    "%VENV_PY%" -m pip install --upgrade pip --quiet
    "%VENV_PY%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ติดตั้ง dependencies ไม่สำเร็จ - ดู error ด้านบน
        pause
        exit /b 1
    )
)

REM ติดตั้ง PyInstaller ใน .venv (เร็วถ้ามีอยู่แล้ว)
"%VENV_PY%" -m pip install pyinstaller --quiet

REM ถอน backport 'typing' เก่าที่ชนกับ PyInstaller (ปล่อยผ่านถ้าไม่มี)
"%VENV_PY%" -m pip uninstall typing -y >nul 2>&1

"%VENV_PY%" -m PyInstaller auto_bot.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo BUILD FAILED — ดู error ด้านบน
    pause
    exit /b 1
)

echo.
echo Done! Output: dist\AutoBot.exe
echo.
echo หมายเหตุ: ถ้าเพิ่ม dependency ใหม่ใน requirements.txt ให้ลบโฟลเดอร์ .venv
echo แล้วรัน build.bat อีกครั้ง เพื่อให้ติดตั้ง dependency ใหม่ครบ
pause
