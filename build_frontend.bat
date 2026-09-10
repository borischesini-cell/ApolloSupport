@echo off
echo ==========================================
echo    Compilando el Frontend de Apollo
echo ==========================================
cd /d "%~dp0frontend"
call npm run build
if errorlevel 1 (
  echo ERROR: build fallo
  pause
  exit /b 1
)
echo.
echo ==========================================
echo    Build OK — copiar TODO dist\ al servidor
echo ==========================================
echo.
echo Verificar en el servidor Apache (htdocs\apollosupport\):
echo   - version.txt          debe decir version=3.2.3
echo   - sw-v3.2.3.js         debe existir
echo   - assets\index-*.js    hash NUEVO (distinto al anterior)
echo.
echo En el navegador:
echo   https://support.ultimate.net.ar/version.txt
echo   https://support.ultimate.net.ar/sw-v3.2.3.js  (linea 1: Apollo Portal SW v3.2.3)
echo   Titulo pestana: v3.2.3 ^· SERVIDOR-GESCOM
echo   Boton stream: HD (no HQ) + badge v3.2.3 junto al ID
echo.
echo Si sigue viejo: esperar banner "Nueva version del portal" o Ctrl+Shift+R
echo   (el SW ya no cachea JS/CSS; actualiza solo cuando version.txt cambia)
echo.
pause
