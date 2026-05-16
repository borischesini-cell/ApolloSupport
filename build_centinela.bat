@echo off
:: ============================================================
:: Apollo Centinela - Script de Build Dual (32 y 64 bits)
:: Ejecutar desde la raiz del proyecto ApolloSupport
:: ============================================================

echo.
echo ============================================================
echo  Apollo Centinela - Build x64 (64 bits)
echo ============================================================
pyinstaller --clean --noconfirm ApolloCentinela_x64.spec
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Fallo el build x64.
    pause
    exit /b 1
)
echo [OK] Build x64 completado: dist\ApolloCentinela_x64.exe

echo.
echo ============================================================
echo  Copiando scripts de instalacion al directorio dist\
echo ============================================================
copy /Y agent\instalar_servicio.bat dist\instalar_servicio.bat
copy /Y agent\desinstalar_servicio.bat dist\desinstalar_servicio.bat
echo [OK] Scripts copiados.

echo.
echo ============================================================
echo  NOTA IMPORTANTE - Build x86 (32 bits)
echo ============================================================
echo  Para compilar la version de 32 bits necesitas:
echo  1. Instalar Python 32-bit (ej. C:\Python311_32\python.exe)
echo  2. Instalar dependencias en ese Python:
echo     C:\Python311_32\python.exe -m pip install pyinstaller websockets pyautogui psutil pillow pystray requests mss
echo  3. Ejecutar:
echo     C:\Python311_32\Scripts\pyinstaller.exe --clean --noconfirm ApolloCentinela_x86.spec
echo  4. El resultado estara en dist\ApolloCentinela_x86.exe
echo.
echo  El EXE x86 corre en AMBAS versiones de Windows (32 y 64 bits).
echo  El EXE x64 solo corre en Windows de 64 bits.
echo.
echo  RECOMENDACION: Distribuir el x86 a clientes desconocidos.
echo ============================================================
echo.
pause
