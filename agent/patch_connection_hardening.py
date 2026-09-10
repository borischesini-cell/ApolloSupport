"""
Patch centinela.py para endurecer la estabilidad y velocidad de reconexión WebSocket:
- Bajar ping_interval=15, ping_timeout=10
- Bajar reconnect_delay inicial a 2s y tope máximo de 60s a 5s
"""
import os

TARGET = r"p:\ApolloSupport\agent\centinela.py"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

# ─── 1. ping_interval / ping_timeout ──────────────────────────────────────────
ANCHOR_PING = """\
            async with websockets.connect(
                SERVER_WS_URL,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=10
            ) as websocket:"""

REPLACE_PING = """\
            async with websockets.connect(
                SERVER_WS_URL,
                ping_interval=15,
                ping_timeout=10,
                close_timeout=5
            ) as websocket:"""

if "ping_interval=20" in src:
    src = src.replace(ANCHOR_PING, REPLACE_PING, 1)
    print("[OK] Paso 1: ping_interval=15, ping_timeout=10 actualizado")
else:
    print("[--] Paso 1: ping_interval ya actualizado o diferente")

# ─── 2. reconnect_delay inicial y max 5s ──────────────────────────────────────
ANCHOR_RECONNECT_INIT = "reconnect_delay = 5  # Resetear backoff al conectar exitosamente"
REPLACE_RECONNECT_INIT = "reconnect_delay = 2  # Resetear backoff rapido al conectar exitosamente"

if ANCHOR_RECONNECT_INIT in src:
    src = src.replace(ANCHOR_RECONNECT_INIT, REPLACE_RECONNECT_INIT, 1)
    print("[OK] Paso 2: reconnect_delay inicial bajado a 2s")

ANCHOR_RECONNECT_MAX = "reconnect_delay = min(reconnect_delay * 2, 60)  # Backoff exponencial: max 60s"
REPLACE_RECONNECT_MAX = "reconnect_delay = min(int(reconnect_delay * 1.5), 5)  # Reconexion ultra rapida: max 5s"

if ANCHOR_RECONNECT_MAX in src:
    src = src.replace(ANCHOR_RECONNECT_MAX, REPLACE_RECONNECT_MAX, 1)
    print("[OK] Paso 3: reconnect_delay tope bajado a 5s max")
else:
    print("[--] Paso 3: reconnect_delay max ya actualizado")

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print("Patch connection_hardening finalizado OK.")
