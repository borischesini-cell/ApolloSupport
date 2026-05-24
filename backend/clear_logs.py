import sys
import os

# Asegurar que se pueda importar desde el backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models

def main():
    db = SessionLocal()
    try:
        deleted = db.query(models.RemoteLog).delete()
        db.commit()
        print(f"¡Tabla remote_logs limpiada con éxito! Se eliminaron {deleted} registros.")
    except Exception as e:
        db.rollback()
        print(f"Error limpiando la tabla: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
