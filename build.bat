@echo off
echo Building AutoBot.exe...
pip install pyinstaller --quiet
pyinstaller auto_bot.spec --clean --noconfirm
echo.
echo Done! Output: dist\AutoBot.exe
pause
