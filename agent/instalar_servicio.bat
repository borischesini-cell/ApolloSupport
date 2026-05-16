@echo off
:: ============================================================
:: Apollo Centinela - Instalador de Servicio de Windows
:: Ejecutar como Administrador
:: ============================================================

set SERVICE_NAME=ApolloCentinela
set SERVICE_DISPLAY=Apollo Centinela Agent
set EXE_PATH=%~dp0ApolloCentinela.exe

echo ============================================================
echo  Apollo Centinela - Instalacion de Servicio Windows
echo ============================================================
echo.

:: Verificar que el EXE existe
if not exist "%EXE_PATH%" (
    echo [ERROR] No se encontro ApolloCentinela.exe en esta carpeta.
    echo         Asegurese de ejecutar este script desde la misma carpeta que el EXE.
    pause
    exit /b 1
)

echo [1/5] Deteniendo servicio anterior si existe...
sc.exe stop %SERVICE_NAME% >nul 2>&1
timeout /t 2 /nobreak >nul

echo [2/5] Eliminando registro anterior si existe...
sc.exe delete %SERVICE_NAME% >nul 2>&1
timeout /t 2 /nobreak >nul

echo [3/5] Creando servicio de Windows (inicio automatico con SYSTEM)...
sc.exe create %SERVICE_NAME% binPath= "\"%EXE_PATH%\"" start= auto obj= LocalSystem DisplayName= "%SERVICE_DISPLAY%"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] No se pudo crear el servicio. Asegurese de ejecutar como Administrador.
    pause
    exit /b 1
)

echo [4/5] Configurando politica de recuperacion automatica...
sc.exe failure %SERVICE_NAME% reset= 3600 actions= restart/30000/restart/60000/restart/120000

echo [5/5] Iniciando el servicio...
sc.exe start %SERVICE_NAME%
if %ERRORLEVEL% NEQ 0 (
    echo [AVISO] El servicio fue instalado pero no pudo iniciarse en este momento.
    echo         Se iniciara automaticamente en el proximo reinicio de Windows.
) else (
    echo.
    echo [OK] Servicio instalado e iniciado correctamente.
)

echo.
echo ============================================================
echo  Estado actual del servicio:
echo ============================================================
sc.exe query %SERVICE_NAME%

echo.
echo El servicio "%SERVICE_DISPLAY%" ahora se iniciara automaticamente
echo con Windows, incluso tras reinicios o cierres de sesion.
echo.
pause
