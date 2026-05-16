import os
import uuid
from database import SessionLocal
import models

def main():
    print("Iniciando la generación masiva de licencias (300 PCs, sin vencimiento)...")
    db = SessionLocal()
    try:
        # 1. Obtener todos los clientes activos
        clients = db.query(models.Client).filter(models.Client.activo == True).all()
        print(f"Encontrados {len(clients)} clientes activos en la base de datos.")
        
        licenses_created = 0
        licenses_updated = 0
        
        for client in clients:
            # 2. Revisar si el cliente ya tiene una licencia activa
            lic = db.query(models.License).filter(models.License.client_id == client.id).first()
            if lic:
                # Actualizar los límites de la licencia existente
                lic.max_devices = 300
                lic.expiry_date = None
                lic.is_active = True
                licenses_updated += 1
            else:
                # Crear una nueva llave de licencia única y limpia
                new_key = f"APOLLO-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}"
                new_lic = models.License(
                    license_key=new_key,
                    client_id=client.id,
                    max_devices=300,
                    expiry_date=None,
                    is_active=True
                )
                db.add(new_lic)
                licenses_created += 1
                
        db.commit()
        print("¡Proceso completado exitosamente!")
        print(f"- Licencias nuevas creadas: {licenses_created}")
        print(f"- Licencias existentes actualizadas: {licenses_updated}")
        print(f"- Total de clientes con licencia activa: {licenses_created + licenses_updated}")
        
    except Exception as e:
        db.rollback()
        print(f"Error durante el proceso de licenciamiento masivo: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
