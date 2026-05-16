"""
Diagnóstico rápido: muestra qué devices tienen el mismo device_name
y qué device_id está usando el centinela actualmente.
Correr en el servidor: python check_device_748.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal
import models

db = SessionLocal()

print("=" * 60)
print("Buscando devices con nombre DESKTOP-J2PF6B3")
print("=" * 60)

devices = db.query(models.CentinelaDevice).filter(
    models.CentinelaDevice.device_name.ilike("%DESKTOP-J2PF6B3%")
).order_by(models.CentinelaDevice.id).all()

for d in devices:
    print(f"  ID={d.id} | client_id={d.client_id} | name={d.device_name} | online={d.is_online} | last_seen={d.last_seen}")

print()
print("=" * 60)
print("Todos los devices online ahora:")
print("=" * 60)
online = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.is_online == True).order_by(models.CentinelaDevice.id).all()
for d in online:
    print(f"  ID={d.id} | client_id={d.client_id} | name={d.device_name}")

db.close()
