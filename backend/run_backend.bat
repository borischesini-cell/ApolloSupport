@echo off
title ApolloSupport Backend Service
color 0b

echo ===================================================
echo   APOLLO SUPPORT - INICIANDO BACKEND
echo ===================================================
echo.

:: Asegurar que el script corra en su propio directorio
cd /d "%~dp0"

:: 1. Activar Entorno Virtual si existe
if not exist venv\Scripts\activate.bat goto no_venv
echo [*] Activando entorno virtual de Python (venv)...
call venv\Scripts\activate.bat
goto venv_done

:no_venv
echo [!] ADVERTENCIA: No se encontro la carpeta 'venv'. Se ejecutara usando el Python global.

:venv_done

echo.
:: 2. Instalar / Actualizar dependencias de requirements.txt
echo [*] Instalando y actualizando dependencias desde requirements.txt...
python -m pip install --upgrade pip
pip install -r requirements.txt

echo.
:: 3. Inicializacion automatica de tablas de la base de datos (seguro de ejecutar siempre)
if not exist create_db.py goto skip_db
echo [*] Verificando e inicializando tablas en la Base de Datos...
python create_db.py
:skip_db

echo.
:: 4. Iniciar Servidor FastAPI con Uvicorn expuesto para conexiones externas
echo ===================================================
echo   APOLLO BACKEND CORRIENDO EN EL PUERTO 8001
echo   - Host externo permitido: 0.0.0.0 (Vital para Centinela)
echo   - Presione CTRL+C para detener el servidor.
echo ===================================================
echo.

uvicorn main:app --host 0.0.0.0 --port 8001

pause
