import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models

db = SessionLocal()
try:
    users = db.query(models.User).all()
    print("Usuarios en PostgreSQL (apollosupport_db.users):")
    for u in users:
        print("\nUsuario:")
        for attr, value in u.__dict__.items():
            if not attr.startswith('_'):
                print(f"  - {attr}: {value}")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
