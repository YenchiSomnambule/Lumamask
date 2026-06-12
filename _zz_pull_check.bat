@echo off
cd /d "C:\Users\louisb\Documents\GitHub\Lumamask"
echo ===== git pull origin main =====
git pull origin main
echo.
echo ===== installed package check =====
python -c "import presidio_analyzer, spacy, anthropic; print('presidio/spacy/anthropic OK')"
echo.
echo ===== DONE =====
pause
