@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python 3 was not found. Install Python 3.10 or newer, then try again.
  pause
  exit /b 1
)
python -c "import pypdf" >nul 2>nul
if errorlevel 1 (
  echo Installing Phillap's document reader dependency...
  python -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Could not install the document reader. Check your internet connection and try again.
    pause
    exit /b 1
  )
)
start "Phillap server" python app.py
powershell -NoProfile -ExecutionPolicy Bypass -Command "$end=(Get-Date).AddSeconds(30); do { try { $r=Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch { Start-Sleep -Milliseconds 500 } } while ((Get-Date) -lt $end); exit 1"
if errorlevel 1 (
  echo Phillap did not start. Check the server window for an error.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8765/
endlocal
