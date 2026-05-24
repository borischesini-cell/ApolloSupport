import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from database import SessionLocal
import models

db = SessionLocal()

device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 767).first()
if device:
    print("=" * 60)
    print("CAMPOS EN CENTINELADEVICE:")
    print("=" * 60)
    for k, v in device.__dict__.items():
        if not k.startswith('_'):
            print(f"  {k}: {v}")
            
    # Mostrar todas las licencias del cliente 670
    print()
    print("=" * 60)
    print("LICENCIAS DEL CLIENTE 670:")
    print("=" * 60)
    lics = db.query(models.License).filter(models.License.client_id == device.client_id).all()
    for lic in lics:
        print(f"  License ID: {lic.id}")
        for l_k, l_v in lic.__dict__.items():
            if not l_k.startswith('_'):
                print(f"    {l_k}: {l_v}")
else:
    print("Dispositivo 767 no encontrado.")
db.close()
