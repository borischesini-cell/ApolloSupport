import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models

db = SessionLocal()
try:
    # Eliminar ID 746 de centinela_devices
    device_to_delete = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 746).first()
    if device_to_delete:
        print(f"Eliminando dispositivo duplicado colgado:")
        print(f"  ID: {device_to_delete.id} | Name: {device_to_delete.device_name} | PIN: {device_to_delete.remote_password}")
        
        # Eliminar cualquier registro relacionado si es necesario o directo
        db.delete(device_to_delete)
        db.commit()
        print("[OK] Dispositivo duplicado eliminado exitosamente.")
    else:
        print("[INFO] El dispositivo ID 746 no fue encontrado o ya fue eliminado.")
except Exception as e:
    print("Error:", e)
finally:
    db.close()
