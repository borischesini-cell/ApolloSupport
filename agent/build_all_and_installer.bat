@echo off
setlocal enabledelayedexpansion
title Apollo Centinela Builder (x86 and x64)

:: ============================================================
:: Apollo Centinela - Script de Build Dual Automatico
:: Soporte nativo para Windows 7 / Windows Server 2008 (Python 3.8)
:: ============================================================

set AGENT_DIR=%~dp0
set OUTPUT_DIR=%AGENT_DIR%installer_output

:: Rutas a las versiones de Python 3.8
set PYTHON_32=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38-32\python.exe
set PYTHON_64=C:\Users\Boris-2010\AppData\Local\Programs\Python\Python38\python.exe

echo.
echo ============================================================
echo [1/4] VERIFICANDO DEPENDENCIAS
echo ============================================================
echo [x86] Instalando dependencias en Python 32-bits...
"%PYTHON_32%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss

echo [x64] Instalando dependencias en Python 64-bits...
"%PYTHON_64%" -m pip install -q pyinstaller websockets pyautogui "psutil<6.0.0" pillow pystray requests mss

echo.
echo ============================================================
echo [2/4] COMPILANDO VERSION DE 32 BITS (x86)
echo ============================================================
cd "%AGENT_DIR%"

echo Compilando Companion x86...
"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo el build del Companion x86.
    pause
    exit /b 1
)
move /Y dist\ApolloCentinela.exe dist\ApolloCentinela_x86.exe > nul

echo Compilando Servicio x86...
"%PYTHON_32%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x86.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo el build del Servicio x86.
    pause
    exit /b 1
)

echo [OK] Build x86 completado.

echo.
echo ============================================================
echo [3/4] COMPILANDO VERSION DE 64 BITS (x64)
echo ============================================================
echo Compilando Companion x64...
"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinela.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo el build del Companion x64.
    pause
    exit /b 1
)
move /Y dist\ApolloCentinela.exe dist\ApolloCentinela_x64.exe > nul

echo Compilando Servicio x64...
"%PYTHON_64%" -m PyInstaller --clean --noconfirm ApolloCentinelaService_x64.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo el build del Servicio x64.
    pause
    exit /b 1
)

echo [OK] Build x64 completado.

echo.
echo ============================================================
echo [4/4] GENERANDO INSTALADOR INNO SETUP
echo ============================================================
if not exist "%OUTPUT_DIR%" mkdir "%OUTPUT_DIR%"

set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="C:\Program Files\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="%USERPROFILE%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if not exist %INNO% set INNO="ISCC.exe"

echo Generando Instalador Universal...
%INNO% "%AGENT_DIR%installer\ApolloSetup.iss"

echo Generando Instalador de 64 bits...
%INNO% "%AGENT_DIR%installer\ApolloSetup_x64.iss"

echo Generando Instalador de 32 bits...
%INNO% "%AGENT_DIR%installer\ApolloSetup_x86.iss"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo la generacion de instaladores.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  PROCESO COMPLETADO EXITOSAMENTE
echo  El nuevo instalador universal se encuentra en la carpeta:
echo  %OUTPUT_DIR%
echo ============================================================
pause
