import os
import sys

# Agregar la ruta actual al sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
import models
from core.erp_bridge import ERPBridge

db = SessionLocal()
try:
    # Buscar el cliente con código '0404' o razón social conteniendo 'LEON'
    clients = db.query(models.Client).filter(
        (models.Client.codigo == "0404") | 
        (models.Client.cclifac == "0404") | 
        (models.Client.razon_social.ilike("%LEON%"))
    ).all()
    
    print(f"Se encontraron {len(clients)} clientes matching:")
    for client in clients:
        print(f"\nCliente: {client.razon_social}")
        print(f"  ID: {client.id}")
        print(f"  Código: '{client.codigo}'")
        print(f"  CCLIFAC (cclifac): '{client.cclifac}'")
        print(f"  Saldo en DB local: {client.saldo}")
        
        # Consultar saldo real en ERP de manera remota
        print("[*] Consultando saldo real en ERP remoto...")
        saldo_erp = ERPBridge.get_client_balance(client.cclifac)
        print(f"    Saldo devuelto: ${saldo_erp}")
        
        # Consultar extracto real en ERP de manera remota
        print("[*] Consultando extracto en ERP remoto...")
        extracto = ERPBridge.get_client_extracto(client.cclifac)
        print(f"    Cantidad de comprobantes devueltos: {len(extracto)}")
        if len(extracto) > 0:
            print("    Primeros comprobantes:")
            for item in extracto[:3]:
                print("      ", item)
except Exception as e:
    print("Error:", e)
finally:
    db.close()
