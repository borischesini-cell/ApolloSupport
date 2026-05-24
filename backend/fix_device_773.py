from database import SessionLocal
import models

def fix():
    db = SessionLocal()
    try:
        # 1. Buscar el nuevo dispositivo que está conectado
        new_dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 773).first()
        if not new_dev:
            print("ERROR: No se encontró el dispositivo nuevo 773")
            return
        
        print(f"Encontrado dispositivo nuevo: {new_dev.device_name} (ID: {new_dev.id})")
        
        # 2. Asignar al cliente 279 (BENETTI HUGO DANIEL) y ponerle el PIN correcto de la pantalla
        new_dev.client_id = 279
        new_dev.remote_password = "5241"
        print("Asignado cliente 279 y clave 5241")
        
        # 3. Quitarle el cliente al dispositivo viejo duplicado (765) para archivarlo sin violar claves foráneas
        old_dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 765).first()
        if old_dev:
            print(f"Archivando duplicado viejo: {old_dev.device_name} (ID: {old_dev.id})")
            old_dev.client_id = None
            old_dev.device_name = "SERVIDOR-GESCOM-VIEJO"
        
        db.commit()
        print("¡Base de datos actualizada con éxito!")
    except Exception as e:
        print("Error:", e)
        db.rollback()
    finally:
        db.close()

if __name__ == '__main__':
    fix()
