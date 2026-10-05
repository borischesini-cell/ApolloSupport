# -*- coding: utf-8 -*-
"""Banco de pruebas local del pipeline WS: agente Centinela -> backend -> viewer.

Levanta dos clientes WebSocket (agente simulado + viewer tecnico) contra un
backend en --url (default 127.0.0.1:8017) y verifica el relay byte a byte.
Puede apuntarse a produccion (https://support.ultimate.net.ar) usando las
credenciales de ~/.apollo_selftest.json (mismo patron que fetch_selftest.py).

Nota: crea/reutiliza un device *pendiente* llamado TEST_PIPELINE_LOCAL en la DB
del backend apuntado. En produccion, borrarlo luego desde el portal.

Requisitos: correr con el python del venv del backend (websockets + jose).
Uso:  venv/Scripts/python.exe ../scripts/test_pipeline_local.py [--url URL]
"""
import argparse
import asyncio
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    from websockets.asyncio.client import connect as ws_connect
except ImportError:
    from websockets import connect as ws_connect

DEV_SECRET = "apollo_super_secreto_para_master_is_2026_x"
DEVICE_NAME = "TEST_PIPELINE_LOCAL"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f"  ({detail})" if detail else ""))
    return ok


def http_get(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout)


def wait_http(base, timeout_s=25.0):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        for path in ("/docs", "/openapi.json", "/"):
            try:
                http_get(base + path).close()
                return True
            except urllib.error.HTTPError:
                return True
            except Exception:
                continue
        time.sleep(0.5)
    return False


def load_credentials():
    user = os.environ.get("APOLLO_USER")
    pwd = os.environ.get("APOLLO_PASS")
    if user and pwd:
        return user, pwd
    cfg_path = os.path.join(os.path.expanduser("~"), ".apollo_selftest.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
        return cfg.get("user"), cfg.get("pass")
    return None, None


def login_token(base, user, pwd):
    data = urllib.parse.urlencode({"username": user, "password": pwd}).encode()
    req = urllib.request.Request(
        base + "/api/token",
        data=data,
        headers={"User-Agent": UA, "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())["access_token"]


def dev_token(email):
    from jose import jwt

    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode({"sub": email, "exp": exp}, DEV_SECRET, algorithm="HS256")


def make_viewer_token(base):
    """Login real si hay credenciales; fallback al secret de desarrollo SOLO en localhost."""
    user, pwd = load_credentials()
    if user and pwd:
        try:
            token = login_token(base, user, pwd)
            print(f"  token: login real con {user}")
            return token
        except Exception as e:
            print(f"  login fallo ({type(e).__name__}: {str(e)[:120]})")
    if "127.0.0.1" in base or "localhost" in base:
        print("  token: fallback dev (backend local usa APOLLO_SECRET_KEY default)")
        return dev_token("pipeline-test@local")
    print("FALLO: sin credenciales validas para un backend remoto (~/.apollo_selftest.json)")
    return None


async def recv_until(ws, predicate, timeout=10.0):
    """Lee mensajes (ignorando pings) hasta que predicate(kind, payload) sea True.
    kind: 'json' | 'bytes'. Devuelve (kind, payload) o None si expira el timeout."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            return None
        try:
            msg = await asyncio.wait_for(ws.recv(), timeout=remaining)
        except Exception:
            return None
        if isinstance(msg, bytes):
            if predicate("bytes", msg):
                return ("bytes", msg)
            continue
        text = msg if isinstance(msg, str) else msg.decode("utf-8", "replace")
        stripped = text.strip()
        if stripped in ("ping", "pong"):
            continue
        try:
            data = json.loads(stripped)
        except Exception:
            continue
        if isinstance(data, dict) and data.get("type") in ("ping", "pong"):
            continue
        if predicate("json", data):
            return ("json", data)


async def run(base, token):
    http = base.replace("https://", "wss://").replace("http://", "ws://")

    agent_url = f"{http}/api/ws/centinela/0?device_name={DEVICE_NAME}&session_id=1"
    async with ws_connect(agent_url, max_size=None, open_timeout=15) as agent:
        got = await recv_until(
            agent, lambda k, p: k == "json" and p.get("type") == "welcome", timeout=20
        )
        if not check("Agente conecta al WS centinela y recibe welcome", got is not None):
            return 1
        device_id = got[1].get("device_id")
        print(f"  device de prueba: id={device_id} name={DEVICE_NAME}")
        check("welcome trae device_id", bool(device_id))

        viewer_url = f"{http}/api/ws/viewer/{device_id}?token={token}"
        async with ws_connect(viewer_url, max_size=None, open_timeout=15) as viewer:
            got = await recv_until(
                agent,
                lambda k, p: k == "json" and p.get("type") == "technician_joined",
                timeout=10,
            )
            check("Agente recibe technician_joined al abrir viewer", got is not None)

            got = await recv_until(
                agent,
                lambda k, p: k == "json"
                and p.get("type") == "active_technicians"
                and p.get("technicians"),
                timeout=10,
            )
            check("Agente recibe active_technicians con el tecnico", got is not None)

            payload1 = b"RIFF" + os.urandom(32000) + b"WEBP"
            packet1 = b"\x01" + payload1
            await agent.send(packet1)
            got = await recv_until(viewer, lambda k, p: k == "bytes", timeout=10)
            ok = got is not None and got[1] == packet1
            check(
                "Viewer recibe frame completo (0x01) byte-identico",
                ok,
                f"{len(packet1)} bytes",
            )

            delta = {"x": 10, "y": 20, "w": 100, "h": 50, "fw": 1920, "fh": 1080}
            djson = json.dumps(delta).encode("utf-8")
            payload2 = os.urandom(8192)
            packet2 = b"\x02" + struct.pack(">I", len(djson)) + djson + payload2
            await agent.send(packet2)
            got = await recv_until(viewer, lambda k, p: k == "bytes", timeout=10)
            ok = got is not None and got[1] == packet2
            check(
                "Viewer recibe dirty-rect (0x02 + delta JSON) byte-identico",
                ok,
                f"{len(packet2)} bytes",
            )

            await viewer.send(json.dumps({"type": "refresh_frame"}))
            got = await recv_until(
                agent,
                lambda k, p: k == "json" and p.get("type") == "refresh_frame",
                timeout=10,
            )
            check("Comando viewer->agente (refresh_frame) reenviado", got is not None)

            await viewer.close()
        got = await recv_until(
            agent,
            lambda k, p: k == "json"
            and p.get("type") == "active_technicians"
            and p.get("technicians") == [],
            timeout=15,
        )
        check("Al cerrar viewer, agente recibe active_technicians=[]", got is not None)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Banco de pruebas del pipeline WS.")
    ap.add_argument("--url", default=os.environ.get("APOLLO_LOCAL_URL", "http://127.0.0.1:8017"))
    args = ap.parse_args()
    base = args.url.rstrip("/")

    print(f"== Pipeline WS: agente -> backend -> viewer ({base}) ==")
    if not wait_http(base):
        print(f"FALLO: el backend no responde en {base}. Levantalo primero.")
        return 2

    token = make_viewer_token(base)
    if not token:
        return 2

    rc = asyncio.run(run(base, token))

    failed = [n for n, ok in RESULTS if not ok]
    total = len(RESULTS)
    if failed:
        print(f"\nRESULTADO: {total - len(failed)}/{total} PASS — FALLARON: {'; '.join(failed)}")
        return 1
    print(f"\nRESULTADO: {total}/{total} PASS — relay agente->backend->viewer OK end-to-end")
    return rc


if __name__ == "__main__":
    sys.exit(main())
