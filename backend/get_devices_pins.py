import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models

db = SessionLocal()
try:
    devices = db.query(models.CentinelaDevice).all()
    print("Dispositivos y sus contraseñas en PostgreSQL:")
    for d in devices:
        print(f"  ID: {d.id} | Name: {d.device_name} | Client ID: {d.client_id} | PIN en DB: {repr(d.remote_password)} | Online: {d.is_online}")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
