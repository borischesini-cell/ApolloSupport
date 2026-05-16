from database import SessionLocal
from models import User
import auth

def seed_users():
    db = SessionLocal()
    
    admin_existe = db.query(User).filter(User.email == "admin@masteris.com").first()
    if not admin_existe:
        admin = User(
            nombre="Juan Administrador",
            email="admin@masteris.com",
            hashed_password=auth.get_password_hash("admin123"),
            rol="admin",
            activo=True
        )
        db.add(admin)
        print("Usuario admin@masteris.com creado (pass: admin123)")
        
    dev_existe = db.query(User).filter(User.email == "dev@masteris.com").first()
    if not dev_existe:
        dev = User(
            nombre="María Programadora",
            email="dev@masteris.com",
            hashed_password=auth.get_password_hash("dev123"),
            rol="desarrollo",
            activo=True
        )
        db.add(dev)
        print("Usuario dev@masteris.com creado (pass: dev123)")
    
    try:
        db.commit()
    except Exception as e:
        print("Error al guardar:", e)
        db.rollback()
    finally:
        db.close()
    
    print("Semillas de usuarios VIP inyectadas.")

if __name__ == "__main__":
    seed_users()
