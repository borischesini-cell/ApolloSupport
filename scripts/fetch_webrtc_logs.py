#!/usr/bin/env python3
"""Busca lineas [WEBRTC] (y de captura/selftest) en los remote_logs del device."""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DEVICE_ID = int(os.environ.get("APOLLO_DEVICE", "819"))
LIMIT = int(os.environ.get("APOLLO_LIMIT", "400"))
BASE = os.environ.get("APOLLO_BASE_URL", "https://support.ultimate.net.ar").rstrip("/")
KEYWORDS = ("[WEBRTC]", "WEBRTC", "canal", "Canal", "relay_candidate", "signaling")
# APOLLO_ALL=1 imprime todas las lineas sin filtrar (para ver version/selftest/etc).
SHOW_ALL = os.environ.get("APOLLO_ALL", "") == "1"
# APOLLO_FORCE_UPDATE=1 dispara POST /api/centinela/{device_id}/force_update en lugar de leer logs.
FORCE_UPDATE = os.environ.get("APOLLO_FORCE_UPDATE", "") == "1"
# APOLLO_ACTIVOS=1 lista /api/centinelas/activos (versiones de los agentes conectados).
ACTIVOS = os.environ.get("APOLLO_ACTIVOS", "") == "1"
# APOLLO_UPDATE_CHECK=1 muestra lo que el endpoint publico update_check le ofrece a los agentes.
UPDATE_CHECK = os.environ.get("APOLLO_UPDATE_CHECK", "") == "1"


def creds() -> tuple[str, str]:
    u = os.environ.get("APOLLO_USER", "").strip()
    p = os.environ.get("APOLLO_PASS", "").strip()
    if u and p:
        return u, p
    cfg = Path.home() / ".apollo_selftest.json"
    d = json.loads(cfg.read_text(encoding="utf-8"))
    return str(d["user"]), str(d["pass"])


def req(url: str, *, method: str = "GET", data: dict | None = None, token: str | None = None):
    body = None
    h = {"Accept": "application/json", "User-Agent": "apollo-webrtc-diag/1.0"}
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        h["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def main() -> int:
    u, p = creds()
    st, raw = req(f"{BASE}/api/token", method="POST",
                  data={"username": u, "password": p})
    if st != 200:
        print(f"login HTTP {st}", file=sys.stderr)
        return 1
    token = json.loads(raw.decode())["access_token"]

    if FORCE_UPDATE:
        st, raw = req(f"{BASE}/api/centinela/{DEVICE_ID}/force_update", method="POST", token=token)
        print(f"force_update HTTP {st}: {raw.decode()[:300]}")
        return 0 if st == 200 else 1

    if UPDATE_CHECK:
        st, raw = req(f"{BASE}/api/centinela/update_check")
        if st != 200:
            print(f"update_check HTTP {st}", file=sys.stderr)
            return 1
        data = json.loads(raw.decode())
        print(f"[UPDATE_CHECK] version={data.get('version')} published={data.get('published')} url={data.get('url')}")
        for key, val in (data.get("downloads") or {}).items():
            print(f"  {key}: {val.get('filename')} | {val.get('size_mb')} MB | {val.get('url')}")
        return 0

    if ACTIVOS:
        st, raw = req(f"{BASE}/api/centinelas/activos", token=token)
        if st != 200:
            print(f"activos HTTP {st}", file=sys.stderr)
            return 1
        data = json.loads(raw.decode())
        if isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, list):
                    for dev in val:
                        if isinstance(dev, dict):
                            print(f"id={dev.get('id')} | {dev.get('device_name')} | v={dev.get('client_version') or dev.get('version')} | online={dev.get('is_online')}")
                else:
                    print(f"{key}: {val}")
        else:
            for dev in data:
                print(json.dumps(dev, ensure_ascii=False)[:300])
        return 0

    q = urllib.parse.urlencode({"limit": str(LIMIT), "device_id": str(DEVICE_ID)})
    st, raw = req(f"{BASE}/api/centinelas/logs?{q}", token=token)
    if st != 200:
        print(f"logs HTTP {st}", file=sys.stderr)
        return 1
    logs = json.loads(raw.decode())
    print(f"# {len(logs)} lineas (limit={LIMIT}) device={DEVICE_ID}\n")
    hits = 0
    for entry in logs:
        msg = entry.get("message") or ""
        if not SHOW_ALL and not any(k in msg for k in KEYWORDS):
            continue
        hits += 1
        ts = entry.get("timestamp", "?")
        print(f"{ts} | {msg[:500]}")
    print(f"\n# {hits} coincidencias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
