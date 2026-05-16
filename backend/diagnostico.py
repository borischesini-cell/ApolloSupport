import sys
import os

print("==============================================")
print("  APOLLO SUPPORT - DIAGNOSTICO DEL BACKEND")
print("==============================================")
print()

# 1. Verificar variables de entorno
print("[*] Leyendo archivo .env...")
if os.path.exists(".env"):
    print("    [OK] Archivo .env encontrado.")
    with open(".env", "r") as f:
        for line in f:
            if "=" in line and not line.strip().startswith("#"):
                parts = line.strip().split("=", 1)
                if len(parts) == 2:
                    k, v = parts
                    # Ocultar la contraseña para seguridad en pantalla
                    if "PASS" in k.upper():
                        print(f"         - {k}: ********")
                    else:
                        print(f"         - {k}: {v}")
else:
    print("    [!] ADVERTENCIA: No se encontro el archivo .env.")

# 2. Probar conexion a PostgreSQL
print("\n[*] Probando conexion a PostgreSQL...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    import psycopg
    
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "apollosupport_db")
    
    # Intentar conectar a la base de datos master 'postgres' primero
    print(f"    - Conectando a base master 'postgres' en {DB_HOST}:{DB_PORT}...")
    conn = psycopg.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname="postgres"
    )
    print("    [OK] Conexion a la base 'postgres' exitosa.")
    
    # Verificar si existe apollosupport_db
    print("    - Buscando la base de datos 'apollosupport_db'...")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
    exists = cursor.fetchone()
    if exists:
        print(f"    [OK] La base de datos '{DB_NAME}' existe.")
    else:
        print(f"    [!] ERROR: La base de datos '{DB_NAME}' NO existe.")
        print("        Por favor, corre el script create_db.py primero.")
    conn.close()
    
    # Intentar conectar directamente a apollosupport_db
    if exists:
        print(f"    - Conectando directamente a '{DB_NAME}'...")
        conn_app = psycopg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        print(f"    [OK] Conexion directa a '{DB_NAME}' exitosa.")
        conn_app.close()

except Exception as e:
    print("    [!] ERROR CRITICO al conectar a PostgreSQL:")
    print(f"        {str(e)}")
    print("\n    Sugerencias de resolucion:")
    print("    1. Asegurate de que el servicio de PostgreSQL este INICIADO en Windows (en Servicios de Windows).")
    print("    2. Revisa que el puerto 5432 este abierto.")
    print("    3. Verifica que el usuario 'postgres' y la contraseña en el archivo .env sean correctos.")

# 3. Probar imports del backend
print("\n[*] Probando importacion de modulos del backend...")
try:
    import models
    print("    [OK] Modulo models importado.")
    import schemas
    print("    [OK] Módulo schemas importado.")
    import auth
    print("    [OK] Modulo auth importado.")
    from database import engine
    print("    [OK] Modulo database y engine importados.")
except Exception as e:
    print("    [!] ERROR al importar modulos:")
    print(f"        {str(e)}")

# 4. Probar integracion ERP Harbour (Modo CONNECT)
print("\n[*] Probando integracion ERP (Modo CONNECT)...")
try:
    from core.erp_bridge import ERPBridge
    import requests
    remote_host = ERPBridge.REMOTE_HOST
    print(f"    - URL del ERP configurada: {remote_host}")
    print("    - Probando conexion con el proxy PHP remoto...")
    url = f"{remote_host.rstrip('/')}/IA/xailer.php"
    try:
        # Enviar una peticion de prueba estructurada vacía para que el motor Harbour no se bloquee esperando parámetros
        headers = {
            "Authorization": "Bearer tu_token_secreto_aqui",
            "Content-Type": "application/json; charset=utf-8"
        }
        test_args = {
            "action": "browse",
            "folder": "ventas",
            "table": "clientes",
            "orden": "Nil",
            "filter": 'CCod=="9999999"',
            "fields": '["CSaldo"]',
            "user": "--"
        }
        payload = ERPBridge.serialize_xailer_json(test_args)
        res = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=5.0)
        if res.status_code == 200:
            print(f"    [OK] Conexion con el proxy remoto exitosa (Status: 200).")
            print(f"         Respuesta remota: {res.text.strip()[:100]}...")
        else:
            print(f"    [!] ADVERTENCIA: El proxy remoto respondio con Status {res.status_code}.")
    except Exception as conn_err:
        print(f"    [!] ERROR: No se pudo conectar al proxy remoto '{url}'.")
        print(f"        Detalle: {conn_err}")

except Exception as erp_err:
    print(f"    [!] ERROR al cargar o inicializar ERPBridge: {erp_err}")

print("\n==============================================")
input("\nPresione ENTER para salir...")
