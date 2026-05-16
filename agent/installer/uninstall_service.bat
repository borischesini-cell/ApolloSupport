@echo off
:: ============================================================
:: Apollo Centinela - Desinstalador de Servicio de Emergencia
:: Solo usar si el desinstalador normal no funciona
:: Ejecutar como Administrador
:: ============================================================
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Este script requiere privilegios de Administrador.
    echo         Click derecho → Ejecutar como Administrador
    pause
    exit /b 1
)

echo Deteniendo servicio Apollo Centinela...
sc.exe stop ApolloCentinela >nul 2>&1
timeout /t 3 /nobreak >nul

echo Eliminando registro del servicio...
sc.exe delete ApolloCentinela >nul 2>&1
timeout /t 2 /nobreak >nul

echo Verificando...
sc.exe query ApolloCentinela >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [OK] Servicio eliminado correctamente.
) else (
    echo [AVISO] El servicio puede requerir reinicio del sistema para eliminarse completamente.
)
pause
