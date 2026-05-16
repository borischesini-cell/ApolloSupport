"""
-------------------------------------------------------------------------
Módulo de Conexión a la Base de Datos (PostgreSQL)
Proyecto: ApolloSupport
Descripción: Maneja la configuración y el pooling de conexiones a la BdD.
-------------------------------------------------------------------------
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Cargamos las credenciales desde el archivo .env para no tenerlas en el código fuente (Práctica de Seguridad)
load_dotenv()

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "apollosupport_db")

# Creamos la cadena de conexión (Connection String) compatible con el driver más moderno (psycopg3)
SQLALCHEMY_DATABASE_URL = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    # Creamos el "Motor" (Engine) de la base de datos con un pool grande
    # para soportar múltiples WebSockets (agentes) conectados simultáneamente.
    engine = create_engine(SQLALCHEMY_DATABASE_URL, pool_size=100, max_overflow=200)
    
    # SessionLocal es la fábrica que genera sesiones temporales de trabajo
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Base es la clase madre que todas nuestras Tablas (Modelos) heredarán
    Base = declarative_base()
except Exception as e:
    print(f"Error al configurar el motor de Base de Datos: {str(e)}")


def get_db():
    """
    Función generadora para las rutas de la API (Dependency Injection).
    Crea una conexión cada vez que se hace un requerimiento web, 
    y se asegura de cerrarla al finalizar, evitando agotar las conexiones del servidor.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
