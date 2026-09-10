@echo off
setlocal enabledelayedexpansion
title Apollo Centinela Builder (non-interactive)

set "AGENT_DIR=%~dp0"
set "OUTPUT_DIR=%AGENT_DIR%installer_output"
cd /d "%AGENT_DIR%"

if not exist "%AGENT_DIR%ffmpeg.exe" (
    echo [ERROR] Falta ffmpeg.exe
    exit /b 1
)

set "PYTHON_32=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38-32\python.exe"
set "PYTHON_64=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38\python.exe"

echo Python x86: %PYTHON_32%
echo Python x64: %PYTHON_64%

echo [1/4] DEPENDENCIAS
"%PYTHON_32%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss
if %ERRORLEVEL% NEQ 0 exit /b 1
"%PYTHON_64%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss
if %ERRORLEVEL% NEQ 0 exit /b 1

if not exist dist mkdir dist

echo [2/4] BUILD x86
"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 exit /b 1
if not exist "dist\ApolloCentinela.exe" exit /b 1
move /Y "dist\ApolloCentinela.exe" "dist\ApolloCentinela_x86.exe" >nul

"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x86.spec
if %ERRORLEVEL% NEQ 0 exit /b 1
if not exist "dist\ApolloCentinelaService_x86.exe" exit /b 1
echo [OK] x86

echo [3/4] BUILD x64
"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 exit /b 1
if not exist "dist\ApolloCentinela.exe" exit /b 1
move /Y "dist\ApolloCentinela.exe" "dist\ApolloCentinela_x64.exe" >nul

"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x64.spec
if %ERRORLEVEL% NEQ 0 exit /b 1
if not exist "dist\ApolloCentinelaService_x64.exe" exit /b 1
echo [OK] x64

echo [4/4] INSTALADORES
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"
set "INNO=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%INNO%" set "INNO=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%INNO%" (
    echo [ERROR] Inno Setup no encontrado
    exit /b 1
)

"%INNO%" "%AGENT_DIR%installer\ApolloSetup.iss"
if %ERRORLEVEL% NEQ 0 exit /b 1
"%INNO%" "%AGENT_DIR%installer\ApolloSetup_x64.iss"
if %ERRORLEVEL% NEQ 0 exit /b 1
"%INNO%" "%AGENT_DIR%installer\ApolloSetup_x86.iss"
if %ERRORLEVEL% NEQ 0 exit /b 1

echo.
echo COMPLETADO
dir /b "%OUTPUT_DIR%\*.exe"
exit /b 0
