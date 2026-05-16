@echo off
echo ===================================================
echo COMPILADOR: Agente Centinela ApolloGesCom (Master IS)
echo ===================================================
echo.
echo Compilando script Python a Ejecutable Windows (.exe)
echo Este proceso empaquetara todo el entorno en un solo archivo portatil e invisible.
echo.

..\backend\venv\Scripts\pyinstaller.exe --noconfirm --onefile --windowed --name "ApolloCentinela" --icon "apollo_logo.ico" --add-data "apollo_logo.ico;." --add-data "apollo_logo.png;." centinela.py

echo.
echo ===================================================
echo COMPILACION FINALIZADA.
echo El nuevo instalador lo encuentra en la carpeta "dist/ApolloCentinela.exe"
echo ===================================================
pause
