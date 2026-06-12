@echo off
echo =============================================
echo  Lumamask EXE Builder
echo =============================================
echo.

cd /d "%~dp0"

echo [1/3] Installing build dependencies...
pip install "pyinstaller>=6.0" pywebview platformdirs jaraco.text more-itertools --quiet
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

echo [2/3] Validating spaCy model...
python -m spacy validate
if errorlevel 1 (
    echo ERROR: spaCy model validation failed. Run: python -m spacy download en_core_web_md
    pause
    exit /b 1
)

echo [3/3] Building Lumamask.exe (this takes 3-5 minutes)...
python -m PyInstaller lumamask.spec --clean --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo =============================================
echo  Build complete!
echo  Output: dist\Lumamask.exe
echo  Size will be ~300-500 MB
echo =============================================
echo.
pause
