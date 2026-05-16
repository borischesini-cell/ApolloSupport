"""
-------------------------------------------------------------------------
Motor de Autenticación (Tokens y Seguridad)
Proyecto: ApolloSupport
Descripción: Modulo independiente para no sobrecargar el main.py. Contiene
la lógica JWT y el encriptador irreversible (Bcrypt).
-------------------------------------------------------------------------
"""
import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext

# Llave maestra del servidor — leer de variable de entorno en producción.
# En desarrollo local usa el fallback. En producción SIEMPRE setear APOLLO_SECRET_KEY.
SECRET_KEY = os.environ.get("APOLLO_SECRET_KEY", "apollo_super_secreto_para_master_is_2026_x")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("APOLLO_ACCESS_TOKEN_MINUTES", str(60 * 24 * 365)))

# Inicializamos Bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """ Comprueba si la contraseña tipeada coincide con el Hash guardado """
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """ Encripta matemáticamente una contraseña (irreversible) """
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """ Fabrica la credencial (Ticket virtual) para el Agente """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt
