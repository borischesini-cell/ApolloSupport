import requests
import json

# Clientes y cclifac
client_code = "0000197"  # GRUPO LEON SA

# 1. Serializador Xailer
def serialize_xailer_json(args: dict) -> str:
    json_string = "{\n"
    for key, value in args.items():
        json_string += f'"{key}": '
        if isinstance(value, str):
            if value.startswith("[") or value.startswith("{"):
                json_string += value
            elif value.startswith("#"):
                json_string += value[1:]
            else:
                json_string += f'"{value}"'
        else:
            json_string += json.dumps(value)
        json_string += ",\n"
    pos = json_string.rfind(",")
    if pos != -1:
        json_string = json_string[:pos] + json_string[pos+1:]
    json_string += "}\n"
    return json_string

# Parámetros de prueba: Saldo
args_saldo = {
    "action": "browse",
    "folder": "ventas",
    "table": "clientes",
    "orden": "Nil",
    "filter": f'CCod=="{client_code}"',
    "fields": '["CSaldo"]',
    "user": "--"
}

# Parámetros de prueba: Extracto
args_extracto = {
    "action": "function",
    "name": "extractoCliente",
    "codigo": client_code,
    "desde": "2025-12-12T00:00:00.000Z",
    "hasta": "2026-05-11T00:00:00.000Z",
    "fields": '["Fecha", "Documento", "Importe", "Saldo", "CodFac"]',
    "user": "--"
}

hosts = [
    "http://192.168.11.223",
    "http://localhost",
    "https://portal.ultimate.net.ar"
]

for host in hosts:
    print(f"\n======================================")
    print(f"Probando HOST: {host}")
    print(f"======================================")
    
    url = f"{host}/IA/xailer.php"
    headers = {
        "Authorization": "Bearer tu_token_secreto_aqui",
        "Content-Type": "application/json; charset=utf-8"
    }
    
    # Probar Saldo
    try:
        payload = serialize_xailer_json(args_saldo)
        res = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=5.0)
        print(f"  Peticion Saldo -> HTTP Status: {res.status_code}")
        if res.status_code == 200:
            lines = [json.loads(l.strip()) for l in res.text.split("\n") if l.strip()]
            print(f"  Respuesta Saldo: {lines}")
        else:
            print(f"  Respuesta Saldo (Error/HTML): {res.text[:100]}...")
    except Exception as e:
        print(f"  Peticion Saldo falló: {e}")
        
    # Probar Extracto
    try:
        payload = serialize_xailer_json(args_extracto)
        res = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=5.0)
        print(f"  Peticion Extracto -> HTTP Status: {res.status_code}")
        if res.status_code == 200:
            lines = [json.loads(l.strip()) for l in res.text.split("\n") if l.strip()]
            print(f"  Respuesta Extracto: {len(lines)} registros devueltos.")
            if lines:
                print(f"    Primeros 2 registros: {lines[:2]}")
        else:
            print(f"  Respuesta Extracto (Error/HTML): {res.text[:100]}...")
    except Exception as e:
        print(f"  Peticion Extracto falló: {e}")
