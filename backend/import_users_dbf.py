"""
-------------------------------------------------------------------------
Script de Importación de Usuarios desde USERG.dbf
Proyecto: ApolloSupport
Descripción: Lee los usuarios del personal de USERG.dbf y los da de alta
             en la base de datos PostgreSQL con clave por defecto 'user1234' (encriptada).
-------------------------------------------------------------------------
"""
import os
import sys
from dbfread import DBF
from database import SessionLocal
import models
import auth

def import_users():
    db = SessionLocal()
    dbf_path = r"p:\ApolloSupport\bases\USERG.dbf"
    
    if not os.path.exists(dbf_path):
        print(f"Error: No se encontró el archivo DBF en: {dbf_path}")
        return

    print(f"Leyendo usuarios desde: {dbf_path}...")
    table = DBF(dbf_path, encoding='latin1')
    
    generic_hashed_password = auth.get_password_hash("user1234")
    imported_count = 0
    updated_count = 0
    
    for record in table:
        username = record.get("UNOMUSER") or record.get("UDES")
        if not username:
            continue
            
        username_str = str(username).strip()
        if not username_str:
            continue
            
        email = record.get("UMAIL")
        if not email:
            email = f"{username_str.lower()}@apollogescom.com.ar"
        else:
            email = str(email).strip().lower()
            
        full_name = str(record.get("UDES") or username_str).strip().title()
        
        # Determinar rol y departamento por defecto para el personal clave
        rol = "soporte"
        departamento = "Atención al Cliente"
        
        email_clean = email.lower()
        if "boris" in email_clean or "sirobche" in email_clean:
            rol = "admin"
            departamento = "Desarrollo"
        elif "marianofilippi" in email_clean:
            rol = "admin"
            departamento = "Desarrollo"
        elif "joaquincasarotto" in email_clean:
            rol = "admin"
            departamento = "Atención al Cliente"
            
        # Buscar si ya existe por email
        user_exists = db.query(models.User).filter(models.User.email == email).first()
        if not user_exists:
            # Crear usuario nuevo
            new_user = models.User(
                nombre=username_str,
                email=email,
                hashed_password=generic_hashed_password,
                full_name=full_name,
                rol=rol,
                activo=True,
                celular="",
                departamento=departamento,
                is_online=False,
                current_task="",
                current_page=""
            )
            db.add(new_user)
            imported_count += 1
            print(f"[+] Importado: {full_name} ({email}) - Rol: {rol}")
        else:
            # Actualizar campos básicos si ya existe para no pisar contraseñas
            user_exists.nombre = username_str
            user_exists.full_name = full_name
            if not user_exists.departamento:
                user_exists.departamento = departamento
            updated_count += 1
            print(f"[*] Actualizado: {full_name} ({email})")
            
    try:
        db.commit()
        print(f"\n--- Importación Finalizada ---")
        print(f"Total creados: {imported_count}")
        print(f"Total actualizados: {updated_count}")
    except Exception as e:
        db.rollback()
        print(f"Error guardando usuarios en base de datos: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    import_users()
