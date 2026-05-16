# Apollo Support

Sistema de soporte remoto y monitoreo centinela.

## Estructura del Proyecto

- **/backend**: API construida con FastAPI (Python).
- **/frontend**: Dashboard web construido con React + Vite.
- **/agent**: Agente de monitoreo y soporte remoto (Centinela) para Windows.
- **/mobile**: Aplicación móvil para técnicos.

## Requisitos para el Desarrollador

### Backend
1. Crear un entorno virtual: `python -m venv venv`
2. Instalar dependencias: `pip install -r requirements.txt`
3. Configurar el archivo `.env` basado en `.env.example`.
4. Ejecutar con: `uvicorn main:app --reload`

### Frontend
1. Instalar dependencias: `npm install`
2. Ejecutar en desarrollo: `npm run dev`
3. Construir para producción: `npm run build`

### Agente (Centinela)
- Requiere Python 3.11 para compilación con PyInstaller.
- Ver `agent/README.md` para más detalles.

## Despliegue
Ver el archivo `DEPLOY_GUIDE.txt` en la raíz para instrucciones detalladas de despliegue en Windows Server con Apache.
