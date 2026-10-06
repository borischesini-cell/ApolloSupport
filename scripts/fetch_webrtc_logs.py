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
        if any(k in msg for k in KEYWORDS):
            hits += 1
            ts = entry.get("timestamp", "?")
            print(f"{ts} | {msg[:500]}")
    print(f"\n# {hits} coincidencias")
    return 0


if __name__ == "__main__":
    sys.exit(main())
