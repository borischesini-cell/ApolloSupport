@echo off
setlocal enabledelayedexpansion
set AGENT_DIR=%~dp0
set BACKEND_VENV=%AGENT_DIR%..\backend\venv\Scripts
set PYINSTALLER=%BACKEND_VENV%\pyinstaller.exe
set ISS_SCRIPT=%AGENT_DIR%installer\ApolloSetup.iss
set OUTPUT_DIR=%AGENT_DIR%installer_output

echo [1/3] Compilando Apollo Centinela...
"%PYINSTALLER%" --clean --noconfirm "%AGENT_DIR%..\ApolloCentinela_x64.spec"
"%PYINSTALLER%" --clean --noconfirm "%AGENT_DIR%ApolloCentinelaService.spec"

copy /Y "%AGENT_DIR%dist\ApolloCentinela_x64.exe"       "%AGENT_DIR%dist\ApolloCentinela.exe"
copy /Y "%AGENT_DIR%dist\ApolloCentinelaService_x64.exe"    "%AGENT_DIR%dist\ApolloCentinelaService.exe"
copy /Y "%AGENT_DIR%ffmpeg.exe"                             "%AGENT_DIR%dist\ffmpeg.exe"
copy /Y "%AGENT_DIR%..\dist\ApolloCentinelaService_x86.exe" "%AGENT_DIR%dist\ApolloCentinelaService_x86.exe"
copy /Y "%AGENT_DIR%..\dist\ApolloCentinela_x86.exe"        "%AGENT_DIR%dist\ApolloCentinela_x86.exe"

echo [2/3] Generando instalador...
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="ISCC.exe"

%INNO% "%ISS_SCRIPT%"

echo [3/3] Finalizado.
dir "%OUTPUT_DIR%"
pause



