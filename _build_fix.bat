@echo off
cd /d "C:\Users\louisb\Documents\GitHub\Lumamask\lumamask-ui"
echo ===== Building via python -m PyInstaller =====
python -m PyInstaller lumamask.spec --clean --noconfirm
echo.
echo ===== BUILD DONE (exit code %errorlevel%) =====
pause
