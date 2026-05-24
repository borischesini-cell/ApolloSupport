from database import SessionLocal
import models
db = SessionLocal()
logs = db.query(models.RemoteLog).order_by(models.RemoteLog.id.desc()).limit(100).all()
for l in reversed(logs):
    print(f"[{l.timestamp}] {l.source} (Dev {l.device_id}): {l.message}")
db.close()
