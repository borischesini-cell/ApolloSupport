import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal
import models

db = SessionLocal()

print("=" * 60)
print("Logs de telemetría para dispositivo 773:")
print("=" * 60)

from sqlalchemy import or_
logs = db.query(models.RemoteLog).filter(
    models.RemoteLog.device_id == 773,
    or_(
        models.RemoteLog.message.like("%Timeout%"),
        models.RemoteLog.message.like("%desconectado%")
    )
).order_by(models.RemoteLog.id.desc()).limit(150).all()

for l in reversed(logs):
    print(f"[{l.timestamp}] Source={l.source} | Level={l.level} | {l.message}")

db.close()
