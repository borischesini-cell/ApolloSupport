import sys
import os
sys.path.append(os.path.abspath('.'))

from main import SessionLocal
import models

db = SessionLocal()
try:
    devices = db.query(models.CentinelaDevice).order_by(models.CentinelaDevice.id.desc()).all()
    for d in devices[:10]:
        print(f"ID: {d.id}, Name: {d.device_name}, Online: {d.is_online}, AltID: {d.alt_remote_id}, Pass: {d.remote_password}, Seen: {d.last_seen}")
finally:
    db.close()
