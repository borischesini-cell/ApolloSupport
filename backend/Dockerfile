FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema (psycopg3 necesita libpq)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python (sin los paquetes de Windows que no aplican en Linux)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    fastapi==0.110.0 \
    uvicorn==0.27.1 \
    SQLAlchemy==2.0.48 \
    psycopg[binary]==3.3.3 \
    python-dotenv==1.0.1 \
    "python-jose[cryptography]==3.5.0" \
    passlib==1.7.4 \
    bcrypt==4.0.1 \
    psutil==7.2.2 \
    websockets==16.0 \
    email-validator==2.3.0 \
    python-multipart==0.0.22 \
    httpx==0.28.1 \
    Pillow==12.1.1 \
    requests==2.33.1 \
    dbfread==2.0.7 \
    PyMySQL==1.1.3 \
    cryptography==46.0.6 \
    anyio==4.13.0 \
    pydantic==2.12.5 \
    tzdata==2025.3

# Copiar código fuente (excluye venv, __pycache__, etc. via .dockerignore)
COPY . .

# Crear directorio de logs y uploads con permisos correctos
RUN mkdir -p /app/logs /app/uploads /app/temp_files

# Puerto que expone uvicorn
EXPOSE 8001

# Healthcheck: verifica que el backend responde
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/api/health')" || exit 1

# Iniciar con uvicorn en modo producción
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1", "--log-level", "warning"]
