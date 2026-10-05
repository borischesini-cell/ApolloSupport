"""Fetch bitácora from production for a device."""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request

SECRET = os.environ.get("APOLLO_SECRET_KEY", "apollo_super_secreto_para_master_is_2026_x")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_token(sub: str) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({"sub": sub, "rol": "admin", "exp": int(time.time()) + 3600}).encode())
    sig_input = f"{header}.{payload}".encode()
    sig = _b64url(hmac.new(SECRET.encode(), sig_input, hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"

device_id = int(sys.argv[1]) if len(sys.argv) > 1 else 773
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 150

token = make_token("boris@ultimate.net.ar")
url = f"https://support.ultimate.net.ar/api/centinelas/logs?device_id={device_id}&limit={limit}"
req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

try:
    with urllib.request.urlopen(req, timeout=45) as r:
        logs = json.loads(r.read().decode())
except Exception as e:
    body = ""
    if hasattr(e, "read"):
        try:
            body = e.read().decode()[:400]
        except Exception:
            pass
    print(f"HTTP error: {e}\n{body}")
    sys.exit(1)

print(f"=== Bitácora device {device_id} | {len(logs)} entradas (más recientes primero en API) ===\n")
keywords = [
    "SESSION", "SWITCH", "login", "TIMEOUT", "AUTOPROMOTE",
    "desconect", "ERROR", "HQ", "WS-CONEX", "PROMOTION", "companion",
]
filtered = []
for l in logs:
    msg = l.get("message", "")
    lvl = l.get("level", "")
    if any(k.lower() in msg.lower() for k in keywords) or lvl in ("ERROR", "WARNING"):
        filtered.append(l)

print(f"--- Filtradas ({len(filtered)}) sesión/errores ---")
for l in reversed(filtered[-80:]):
    print(f"[{l.get('timestamp')}] {l.get('source')} [{l.get('level')}]")
    print(f"  {l.get('message')[:600]}\n")

if not filtered:
    print("(sin coincidencias filtradas — últimas 25 crudas)")
    for l in reversed(logs[:25]):
        print(f"[{l.get('timestamp')}] {l.get('source')} [{l.get('level')}]: {l.get('message')[:400]}")
