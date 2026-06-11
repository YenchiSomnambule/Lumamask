@echo off
echo =============================================
echo  Lumamask Demo
echo =============================================
echo.
set /p APIKEY="Paste your Anthropic API key here: "
set ANTHROPIC_API_KEY=%APIKEY%
echo.
echo Running on invoice_sample.txt...
echo.
cd /d "%~dp0"
python -m lumamask.cli --input samples/invoice_sample.txt --instruction "Summarise this invoice in two sentences."
echo.
pause
