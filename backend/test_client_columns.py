import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models

db = SessionLocal()
try:
    # Obtener el primer cliente y mostrar todos sus atributos/columnas
    client = db.query(models.Client).first()
    if client:
        print("Atributos del modelo Client:")
        for attr, value in client.__dict__.items():
            if not attr.startswith('_'):
                print(f"  - {attr}: {value}")
    else:
        print("No hay clientes en la base de datos.")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
