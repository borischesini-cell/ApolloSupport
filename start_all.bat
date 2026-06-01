@echo off
title ApolloSupport - Iniciar Todo

echo ===================================================
echo   APOLLO SUPPORT - INICIANDO SISTEMA
echo ===================================================
echo.

echo [*] Iniciando el Backend en una nueva ventana...
start "Apollo Backend" cmd /k "cd /d "%~dp0backend" && run_backend.bat"

echo [*] Iniciando el Frontend en una nueva ventana...
start "Apollo Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ===================================================
echo Todo listo. Se abrieron dos ventanas separadas
echo para el Backend y el Frontend.
echo ===================================================
pause
