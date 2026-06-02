@echo off
echo Building AutoBot.exe...

REM ใช้ python -m เพื่อไม่ต้องพึ่ง PATH ของ pyinstaller
python -m pip install pyinstaller --quiet

REM ถอน backport 'typing' เก่าที่ชนกับ PyInstaller (ปล่อยผ่านถ้าไม่มี)
python -m pip uninstall typing -y >nul 2>&1

python -m PyInstaller auto_bot.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo BUILD FAILED — ดู error ด้านบน
    pause
    exit /b 1
)

echo.
echo Done! Output: dist\AutoBot.exe
pause
