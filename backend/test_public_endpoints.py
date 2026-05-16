import requests
import json

# Clientes y cclifac
client_code = "0000197"  # GRUPO LEON SA

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

args_saldo = {
    "action": "browse",
    "folder": "ventas",
    "table": "clientes",
    "orden": "Nil",
    "filter": f'CCod=="{client_code}"',
    "fields": '["CSaldo"]',
    "user": "--"
}

public_hosts = [
    "http://190.16.4.146",
    "https://connect.ultimate.com.ar",
    "http://connect.ultimate.com.ar",
    "https://portal.ultimate.net.ar",
    "http://portal.ultimate.net.ar"
]

for host in public_hosts:
    print(f"\n======================================")
    print(f"Probando HOST: {host}")
    print(f"======================================")
    url = f"{host}/IA/xailer.php"
    headers = {
        "Authorization": "Bearer tu_token_secreto_aqui",
        "Content-Type": "application/json; charset=utf-8"
    }
    try:
        payload = serialize_xailer_json(args_saldo)
        res = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=5.0)
        print(f"  HTTP Status: {res.status_code}")
        if res.status_code == 200:
            print(f"  Respuesta: {res.text.strip()[:150]}")
        else:
            print(f"  Respuesta (Error): {res.text.strip()[:100]}...")
    except Exception as e:
        print(f"  Falló con error: {e}")
