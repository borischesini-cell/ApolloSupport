@echo off
setlocal enabledelayedexpansion
title Apollo Centinela Builder (x86 and x64)

:: ============================================================
:: Apollo Centinela - Build dual + instaladores Inno Setup
:: ffmpeg.exe NO se embebe; el instalador lo copia a {app} (essentials, no full)
:: El instalador unificado es solo x64. x86: ApolloSetup_x86.iss
:: ============================================================

set "AGENT_DIR=%~dp0"
set "OUTPUT_DIR=%AGENT_DIR%installer_output"
cd /d "%AGENT_DIR%"

if not exist "%AGENT_DIR%ffmpeg.exe" (
    echo [ERROR] Falta ffmpeg.exe en %AGENT_DIR%
    echo         Descargalo o copialo antes de generar instaladores.
    pause
    exit /b 1
)

:: --- Detectar Python 32/64 ---
set "PYTHON_32="
set "PYTHON_64="
if exist "%AGENT_DIR%python38-32\python.exe" set "PYTHON_32=%AGENT_DIR%python38-32\python.exe"
if exist "%AGENT_DIR%python32-x86\python.exe" if not defined PYTHON_32 set "PYTHON_32=%AGENT_DIR%python32-x86\python.exe"
if exist "C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38-32\python.exe" if not defined PYTHON_32 set "PYTHON_32=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38-32\python.exe"
if exist "C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38\python.exe" if not defined PYTHON_64 set "PYTHON_64=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38\python.exe"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
    if not defined PYTHON_64 for /f "delims=" %%P in ('py -3.8-64 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_64=%%P"
    if not defined PYTHON_32 for /f "delims=" %%P in ('py -3.8-32 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON_32=%%P"
)
if not defined PYTHON_64 set "PYTHON_64=%PYTHON_32%"
if not defined PYTHON_32 set "PYTHON_32=%PYTHON_64%"

if not exist "%PYTHON_32%" (
    echo [ERROR] No se encontro Python 32-bit. Ajusta PYTHON_32 en este .bat
    pause
    exit /b 1
)
if not exist "%PYTHON_64%" (
    echo [ERROR] No se encontro Python 64-bit. Ajusta PYTHON_64 en este .bat
    pause
    exit /b 1
)

echo Python x86: %PYTHON_32%
echo Python x64: %PYTHON_64%
echo Carpeta:    %AGENT_DIR%
echo.

echo ============================================================
echo [1/4] DEPENDENCIAS (pip)
echo ============================================================
"%PYTHON_32%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss
if %ERRORLEVEL% NEQ 0 goto :pip_fail
"%PYTHON_64%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss
if %ERRORLEVEL% NEQ 0 goto :pip_fail
echo WebRTC (solo x64, aiortc 1.9 para Python 3.8)...
"%PYTHON_64%" -m pip install -q -r "%AGENT_DIR%requirements-webrtc.txt"
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] aiortc no se instalo. El companion x64 compilara sin Canal rapido.
)

echo.
echo ============================================================
echo [2/4] BUILD x86
echo ============================================================
if not exist dist mkdir dist
echo Companion x86...
"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 goto :build_fail
if not exist "dist\ApolloCentinela.exe" goto :missing_exe
move /Y "dist\ApolloCentinela.exe" "dist\ApolloCentinela_x86.exe" >nul

echo Servicio x86...
"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x86.spec
if %ERRORLEVEL% NEQ 0 goto :build_fail
if not exist "dist\ApolloCentinelaService_x86.exe" goto :missing_exe
echo [OK] x86

echo.
echo ============================================================
echo [3/4] BUILD x64
echo ============================================================
echo Companion x64...
"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 goto :build_fail
if not exist "dist\ApolloCentinela.exe" goto :missing_exe
move /Y "dist\ApolloCentinela.exe" "dist\ApolloCentinela_x64.exe" >nul

echo Servicio x64...
"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x64.spec
if %ERRORLEVEL% NEQ 0 goto :build_fail
if not exist "dist\ApolloCentinelaService_x64.exe" goto :missing_exe
echo [OK] x64

echo.
echo ============================================================
echo [4/4] INSTALADORES INNO SETUP
echo ============================================================
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

set "INNO="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "INNO=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not defined INNO if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "INNO=C:\Program Files\Inno Setup 6\ISCC.exe"
if not defined INNO if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "INNO=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not defined INNO (
    echo [ERROR] Inno Setup 6 no encontrado. Instalalo desde https://jrsoftware.org/isinfo.php
    pause
    exit /b 1
)

echo Inno: %INNO%
echo.

call :run_inno "installer\ApolloSetup.iss"
if %ERRORLEVEL% NEQ 0 goto :inno_fail
call :run_inno "installer\ApolloSetup_x64.iss"
if %ERRORLEVEL% NEQ 0 goto :inno_fail
call :run_inno "installer\ApolloSetup_x86.iss"
if %ERRORLEVEL% NEQ 0 goto :inno_fail

echo.
echo ============================================================
echo  COMPLETADO
echo  Instaladores en: %OUTPUT_DIR%
echo ============================================================
dir /b "%OUTPUT_DIR%\*.exe" 2>nul
pause
exit /b 0

:run_inno
echo Compilando %~1 ...
"%INNO%" "%AGENT_DIR%%~1"
exit /b %ERRORLEVEL%

:pip_fail
echo [ERROR] pip install fallo
pause
exit /b 1

:build_fail
echo [ERROR] PyInstaller fallo. Revisa build\*\warn-*.txt
pause
exit /b 1

:missing_exe
echo [ERROR] No se genero el .exe esperado en dist\
pause
exit /b 1

:inno_fail
echo [ERROR] ISCC fallo. Verifica que existan los 4 exe en dist\
dir dist\*.exe
pause
exit /b 1
