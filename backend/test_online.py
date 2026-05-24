import sys
import os
sys.path.append(os.path.abspath('.'))

from main import SessionLocal
import models

db = SessionLocal()
try:
    dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 767).first()
    print("Before:", dev.is_online)
    dev.is_online = True
    db.commit()
    db.refresh(dev)
    print("After commit and refresh:", dev.is_online)
finally:
    db.close()
