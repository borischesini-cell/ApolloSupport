import asyncio
import websockets
import json
import random

# URL del Servidor (Ajustar según entorno)
SERVER_URL = "wss://support.ultimate.net.ar/api/ws/centinela/"
NUM_AGENTS = 50

async def simulate_agent(agent_id):
    """ Simula un agente Centinela enviando telemetría periódica. """
    device_name = f"Simulado-PC-{agent_id}"
    print(f"[*] Agente {agent_id} iniciando...")
    
    # Simular diferentes intervalos para evitar picos exactos
    await asyncio.sleep(random.uniform(0, 5))
    
    try:
        async with websockets.connect(f"{SERVER_URL}{agent_id}?name={device_name}") as ws:
            print(f"[+] {device_name} conectado al sistema.")
            while True:
                # Simular telemetría fluctuante
                cpu = random.randint(5, 45)
                ram = random.randint(30, 70)
                
                payload = {
                    "type": "telemetry",
                    "data": {
                        "cpu": cpu,
                        "ram": ram,
                        "disk": 25,
                        "status": "online",
                        "device_name": device_name
                    }
                }
                
                await ws.send(json.dumps(payload))
                
                # Esperar entre 8 y 15 segundos antes de la siguiente actualización
                await asyncio.sleep(random.uniform(8, 15))
                
    except Exception as e:
        print(f"[-] {device_name} desconectado: {e}")

async def run_test():
    print(f"=== INICIANDO PRUEBA DE CARGA: {NUM_AGENTS} AGENTES ===")
    agents = [simulate_agent(i) for i in range(5000, 5000 + NUM_AGENTS)]
    await asyncio.gather(*agents)

if __name__ == "__main__":
    try:
        asyncio.run(run_test())
    except KeyboardInterrupt:
        print("\n[!] Prueba de carga finalizada por el usuario.")
