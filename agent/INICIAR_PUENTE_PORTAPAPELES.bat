@echo off
cd /d "%~dp0"
REM Arranca el puente de portapapeles sin ventana.
where pythonw >nul 2>&1
if %ERRORLEVEL%==0 (
  start "" pythonw "%~dp0clipboard_bridge.py"
) else (
  powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -FilePath python -ArgumentList '%~dp0clipboard_bridge.py' -WorkingDirectory '%~dp0' -WindowStyle Hidden"
)
exit /b 0
