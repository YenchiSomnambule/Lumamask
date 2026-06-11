@echo off
echo Installing Lumamask dependencies...
echo.

pip install presidio-analyzer presidio-anonymizer anthropic
echo.
echo Downloading spaCy model...
python -m spacy download en_core_web_md
echo.
echo Done! You can now run Lumamask.
pause
