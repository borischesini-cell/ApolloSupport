from backend.database import SessionLocal
from backend import models

db = SessionLocal()
devices = db.query(models.Device).all()
for d in devices:
    print(f"ID: {d.id}, Name: {d.device_name}, Client ID: {d.client_id}")
