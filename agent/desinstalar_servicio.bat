@echo off
:: ============================================================
:: Apollo Centinela - Desinstalador de Servicio de Windows
:: Ejecutar como Administrador
:: ============================================================

set SERVICE_NAME=ApolloCentinela

echo Deteniendo y eliminando el servicio %SERVICE_NAME%...
sc.exe stop %SERVICE_NAME% >nul 2>&1
timeout /t 2 /nobreak >nul
sc.exe delete %SERVICE_NAME%

if %ERRORLEVEL% EQU 0 (
    echo [OK] Servicio desinstalado correctamente.
) else (
    echo [AVISO] El servicio no existia o ya habia sido eliminado.
)
pause
