"""
Viewer de prueba local — se conecta al WS viewer del backend como un tecnico.

Dispara technician_joined en el agente (HAS_ACTIVE_VIEWER=True) y cuenta los
paquetes binarios que el backend retransmite (mismo camino que el viewer real
del Portal: tag 0x01 = full, 0x02 = delta).

Uso:
  python scripts/viewer_probe_local.py --device 780 --token <JWT> [--seconds 45]
  set APOLLO_TOKEN=<JWT> && python scripts/viewer_probe_local.py --device 780
"""
import argparse
import asyncio
import json
import os
import time

import websockets


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8001")
    ap.add_argument("--device", type=int, required=True)
    ap.add_argument("--token", default=os.getenv("APOLLO_TOKEN"))
    ap.add_argument("--seconds", type=int, default=45)
    args = ap.parse_args()

    if not args.token:
        raise SystemExit("falta el JWT: --token o variable APOLLO_TOKEN")

    url = f"{args.url}/api/ws/viewer/{args.device}?token={args.token}"
    print(f"[PROBE] conectando a {args.url}/api/ws/viewer/{args.device}?token=***")
    frames = 0
    tags = {1: 0, 2: 0}
    other_tags = 0
    total_bytes = 0
    text_types = {}
    t0 = time.time()
    last_report = t0

    async with websockets.connect(url, ping_interval=20, ping_timeout=60) as ws:
        print("[PROBE] conectado OK (token validado)")
        while time.time() - t0 < args.seconds:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
            except asyncio.TimeoutError:
                print("[PROBE] 10s sin mensajes")
                continue
            except websockets.ConnectionClosed as e:
                print(f"[PROBE] conexion cerrada por el server: {e}")
                break
            if isinstance(msg, (bytes, bytearray)):
                tag = msg[0]
                if tag in tags:
                    tags[tag] += 1
                else:
                    other_tags += 1
                frames += 1
                total_bytes += len(msg)
            else:
                try:
                    j = json.loads(msg)
                    t = j.get("type", "?")
                    text_types[t] = text_types.get(t, 0) + 1
                except Exception:
                    text_types["parse_error"] = text_types.get("parse_error", 0) + 1

            now = time.time()
            if now - last_report >= 5.0:
                print(f"[PROBE] t={now - t0:5.1f}s binarios={frames} tags01={tags[1]} tags02={tags[2]} otros={other_tags} texto={text_types}")
                last_report = now

    elapsed = time.time() - t0
    fps = frames / elapsed if elapsed > 0 else 0.0
    kbps = (total_bytes * 8 / 1000.0) / elapsed if elapsed > 0 else 0.0
    print(f"[PROBE] FIN: {frames} binarios (full={tags[1]} delta={tags[2]} otros={other_tags}), texto={text_types}")
    print(f"[PROBE] {elapsed:.1f}s -> {fps:.2f} FPS | {total_bytes/1024:.0f} KiB | {kbps:.0f} kbps")


if __name__ == "__main__":
    asyncio.run(main())
