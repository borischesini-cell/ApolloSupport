from database import SessionLocal
import models
db = SessionLocal()
try:
    logs = db.query(models.RemoteLog).order_by(models.RemoteLog.timestamp.desc()).all()
    print(f"Total logs in database: {len(logs)}")
    for l in reversed(logs):
        device_name = "Unknown"
        if l.device_id:
            dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == l.device_id).first()
            if dev:
                device_name = dev.device_name
        print(f"[{l.timestamp}] {l.source} ({device_name} / ID {l.device_id}) [{l.level}]: {l.message}")
finally:
    db.close()
