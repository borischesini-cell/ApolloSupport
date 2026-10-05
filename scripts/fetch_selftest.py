#!/usr/bin/env python3
"""
Lector del [SELFTEST] que cada agente Centinela reporta via remote_logs.

Uso:
  python scripts/fetch_selftest.py                 # un disparo, veredicto por device
  python scripts/fetch_selftest.py --watch         # refresca cada 60s
  python scripts/fetch_selftest.py --device 875923 --limit 20

Credenciales (en este orden):
  1. variables de entorno APOLLO_USER / APOLLO_PASS
  2. archivo %USERPROFILE%\\.apollo_selftest.json  {"user": "...", "pass": "..."}
Base URL: variable APOLLO_BASE_URL (default https://support.ultimate.net.ar)

OJO: el login es el mismo de la web; si se usa una cuenta humana, pisa
is_online/current_task del dashboard mientras corre el script.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

GMT3 = timezone(timedelta(hours=-3))
SELFTEST_PREFIX = "[SELFTEST] "
STATS_SEPARATOR = " | [BACKEND STATS]"


def load_credentials() -> tuple[str, str]:
    user = os.environ.get("APOLLO_USER", "").strip()
    pwd = os.environ.get("APOLLO_PASS", "").strip()
    if user and pwd:
        return user, pwd
    cfg = Path.home() / ".apollo_selftest.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            user = str(data.get("user", "")).strip()
            pwd = str(data.get("pass", "")).strip()
            if user and pwd:
                return user, pwd
        except Exception as e:
            sys.exit(f"No se pudo leer {cfg}: {e}")
    sys.exit(
        "Faltan credenciales.\n"
        f"  Crear {cfg} con {{\"user\": \"email\", \"pass\": \"clave\"}}\n"
        "  o definir APOLLO_USER / APOLLO_PASS."
    )


def http_request(url: str, *, method: str = "GET", data: dict | None = None,
                 token: str | None = None) -> tuple[int, bytes]:
    body = None
    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    }
    if data is not None:
        body = urllib.parse.urlencode(data).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        sys.exit(f"No se pudo conectar a {url}: {e}")


def login(base: str, user: str, pwd: str) -> str:
    status, raw = http_request(
        f"{base}/api/token", method="POST",
        data={"username": user, "password": pwd},
    )
    if status != 200:
        sys.exit(f"Login fallo (HTTP {status}): {raw[:300].decode('utf-8', 'replace')}")
    token = json.loads(raw.decode("utf-8")).get("access_token", "")
    if not token:
        sys.exit("Login no devolvio access_token.")
    return token


def fetch_logs(base: str, token: str, limit: int, device_id: int | None) -> list[dict]:
    q = {"limit": str(limit)}
    if device_id is not None:
        q["device_id"] = str(device_id)
    url = f"{base}/api/centinelas/logs?{urllib.parse.urlencode(q)}"
    status, raw = http_request(url, token=token)
    if status != 200:
        sys.exit(f"GET logs fallo (HTTP {status}): {raw[:300].decode('utf-8', 'replace')}")
    return json.loads(raw.decode("utf-8"))


def parse_selftest(message: str) -> dict | None:
    if not message.startswith(SELFTEST_PREFIX):
        return None
    payload = message[len(SELFTEST_PREFIX):].split(STATS_SEPARATOR)[0].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"_raw": payload[:120]}


def collect(logs: list[dict]) -> list[dict]:
    # El endpoint viene ordenado id DESC (mas nuevo primero):
    # el primer [SELFTEST] que aparece por device es su reporte mas reciente.
    seen: set[int] = set()
    out = []
    for log in logs:
        dev_id = log.get("device_id")
        if dev_id in seen:
            continue
        st = parse_selftest(log.get("message") or "")
        if st is None:
            continue
        seen.add(dev_id)
        out.append({"device_id": dev_id, "device_name": log.get("device_name"),
                    "timestamp": log.get("timestamp"), "st": st})
    return out


def verdict(st: dict, age_min: float, silence_min: float) -> tuple[str, str, str]:
    if age_min > silence_min:
        return ("SILENCIO", "NO ANDA", f"hace {age_min:.0f} min sin reportar (umbral {silence_min:.0f}m)")
    status = st.get("status", "?")
    detail_bits = [
        f"v={st.get('v', '?')}",
        f"frames={st.get('frames', '?')}",
        f"metodo={st.get('method') or '-'}",
    ]
    if st.get("rdp"):
        detail_bits.append("RDP")
    if st.get("hq"):
        detail_bits.append("HQ")
    if st.get("cap_err"):
        detail_bits.append(f"cap_err={st['cap_err']}")
    if st.get("err"):
        detail_bits.append(f"err={st['err']}")
    detail = " ".join(detail_bits)
    if status == "OK":
        return ("OK", "ANDA", detail)
    if status == "IDLE":
        return ("IDLE", "ANDA", detail + " (sin viewer, captura pausada)")
    if status == "NO_FRAMES":
        return ("NO_FRAMES", "NO ANDA", detail + " -> viewer pidiendo, nunca capturo")
    if status == "STALE":
        return ("STALE", "NO ANDA", detail + f" -> frames congelados hace {st.get('frame_age_ms', '?')}ms")
    if status == "BLACK_SCREEN":
        return ("BLACK_SCREEN", "NO ANDA", detail + f" -> negro (streak={st.get('black_streak')})")
    return (status, "?", detail)


def render(rows: list[dict], silence_min: float) -> str:
    now = datetime.now(GMT3)
    lines = [f"== Selftest Centinela - {now:%Y-%m-%d %H:%M:%S} GMT-3 ==", ""]
    if not rows:
        lines.append("Sin reportes [SELFTEST] en el rango pedido.")
        return "\n".join(lines)
    header = f"{'DEVICE':<34} {'ULTIMO REPORTE':<17} {'STATUS':<13} {'VEREDICTO':<9} DETALLE"
    lines.append(header)
    lines.append("-" * len(header) + "-" * 40)
    for row in rows:
        ts = row.get("timestamp")
        try:
            reported = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            if reported.tzinfo is None:
                reported = reported.replace(tzinfo=timezone.utc)
            age_min = (datetime.now(timezone.utc) - reported).total_seconds() / 60.0
            reported_str = reported.astimezone(GMT3).strftime("%m-%d %H:%M:%S")
        except ValueError:
            age_min = 0.0
            reported_str = str(ts)[:16]
        status, v, detail = verdict(row["st"], age_min, silence_min)
        name = f"{row['device_name'] or '?'} ({row['device_id']})"[:33]
        lines.append(f"{name:<34} {reported_str:<17} {status:<13} {v:<9} {detail}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Veredicto de selftest por dispositivo Centinela.")
    ap.add_argument("--device", help="device_id (numero) o parte del nombre")
    ap.add_argument("--limit", type=int, default=500, help="logs a pedir al server (default 500)")
    ap.add_argument("--watch", action="store_true", help="refresca cada 60s")
    ap.add_argument("--silence", type=float, default=3.0, help="minutos sin reportar = SILENCIO (default 3)")
    args = ap.parse_args()

    base = os.environ.get("APOLLO_BASE_URL", "https://support.ultimate.net.ar").rstrip("/")
    user, pwd = load_credentials()
    device_id = int(args.device) if (args.device or "").isdigit() else None

    while True:
        token = login(base, user, pwd)
        logs = fetch_logs(base, token, args.limit, device_id)
        rows = collect(logs)
        if args.device and not device_id:
            needle = args.device.lower()
            rows = [r for r in rows if needle in (r.get("device_name") or "").lower()]
        if sys.platform == "win32":
            os.system("cls")
        print(render(rows, args.silence))
        if not args.watch:
            return 0
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
