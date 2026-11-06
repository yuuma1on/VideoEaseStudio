@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade pyinstaller
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name VideoEaseStudio videoease.py
if errorlevel 1 goto fail
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name VideoEaseUpdater apply_update.py
if errorlevel 1 goto fail
copy /Y update_config.json dist\update_config.json >nul
echo Build complete. Run dist\VideoEaseStudio.exe
pause
exit /b 0
:fail
echo Build failed
pause
exit /b 1
