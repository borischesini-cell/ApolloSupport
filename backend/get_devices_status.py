from database import SessionLocal
import models
from datetime import datetime
db = SessionLocal()
try:
    devices = db.query(models.CentinelaDevice).order_by(models.CentinelaDevice.id.desc()).all()
    print(f"Total devices in database: {len(devices)}")
    print("-" * 100)
    for d in devices:
        client_name = "Sin Cliente"
        if d.client_id:
            c = db.query(models.Client).filter(models.Client.id == d.client_id).first()
            if c:
                client_name = c.razon_social
        
        print(f"ID: {d.id} | Name: {d.device_name} | Client: {client_name} (ID {d.client_id}) | PIN: {d.remote_password} | Online: {d.is_online} | Last Seen: {d.last_seen}")
finally:
    db.close()
