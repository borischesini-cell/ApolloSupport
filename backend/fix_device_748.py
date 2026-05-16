"""
Ver qué es el device 748 y hacer el cleanup.
Correr: python fix_device_748.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal
import models

db = SessionLocal()

print("=== Device 748 ===")
d748 = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 748).first()
if d748:
    print(f"  ID={d748.id} | client_id={d748.client_id} | name={d748.device_name} | online={d748.is_online} | last_seen={d748.last_seen}")
else:
    print("  Device 748 NO existe en la DB")

print()
print("=== Device 749 ===")
d749 = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 749).first()
if d749:
    print(f"  ID={d749.id} | client_id={d749.client_id} | name={d749.device_name} | online={d749.is_online} | last_seen={d749.last_seen}")

print()
print("=== Devices recientes (ID >= 745) ===")
recent = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id >= 745).order_by(models.CentinelaDevice.id).all()
for d in recent:
    print(f"  ID={d.id} | client_id={d.client_id} | name={d.device_name} | online={d.is_online}")

db.close()
