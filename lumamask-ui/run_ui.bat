@echo off
cd /d "%~dp0"
echo Checking dependencies...
pip install flask --quiet
echo Starting Lumamask UI...
python app.py
pause
