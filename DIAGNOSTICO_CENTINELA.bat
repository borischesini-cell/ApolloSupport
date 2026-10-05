@echo off
setlocal
title Diagnostico Apollo Centinela
echo ============================================
echo  Diagnostico Apollo Centinela
echo  %DATE% %TIME%
echo ============================================
echo.

echo ----- sc query ApolloCentinela -----
sc query ApolloCentinela
echo.

echo ----- Procesos ApolloCentinela -----
tasklist /FI "IMAGENAME eq ApolloCentinela.exe"
echo.
tasklist /FI "IMAGENAME eq ApolloCentinelaService.exe"
echo.

echo ----- Version instalada (registro) -----
reg query "HKLM\Software\MasterIS\ApolloSupport" 2>nul
echo.

echo ----- Archivos instalados -----
if exist "%ProgramFiles%\Apollo Centinela\ApolloCentinela.exe" (
  dir "%ProgramFiles%\Apollo Centinela\ApolloCentinela.exe" "%ProgramFiles%\Apollo Centinela\ApolloCentinelaService.exe"
) else if exist "%ProgramFiles(x86)%\Apollo Centinela\ApolloCentinela.exe" (
  dir "%ProgramFiles(x86)%\Apollo Centinela\ApolloCentinela.exe" "%ProgramFiles(x86)%\Apollo Centinela\ApolloCentinelaService.exe"
) else (
  echo No se encontro carpeta Apollo Centinela en Program Files
)
echo.

echo ----- SERVICE.LOG (ultimas 40) -----
if exist "%ProgramData%\ApolloSupport\service.log" (
  powershell -NoProfile -Command "Get-Content '%ProgramData%\ApolloSupport\service.log' -Tail 40"
) else (
  echo No existe service.log
)
echo.

echo ----- CENTINELA.LOG (ultimas 40) -----
if exist "%ProgramData%\ApolloSupport\centinela.log" (
  powershell -NoProfile -Command "Get-Content '%ProgramData%\ApolloSupport\centinela.log' -Tail 40"
) else (
  echo No existe centinela.log
)
echo.

echo ============================================
echo  Fin diagnostico
echo  Copia TODO este texto y envialo.
echo ============================================
echo.
pause
