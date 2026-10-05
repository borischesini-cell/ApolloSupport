"""Mide el stream de un device FORZANDO movimiento de mouse.

Inyecta mouse_move en un circulo chico (centro 0.5,0.5 radio 0.06) cada
~150 ms por el WS viewer (el mismo camino que usa el portal) mientras
cuenta los frames binarios recibidos. Con movimiento sostenido el
dirty-rect del agente dispara en cada iteracion del loop, asi que la
captura queda ejercitada al maximo y se expone el techo real:

  FPS recibidos ~ 7 con kbps altos      -> techo CPU del 828 (frame_ms 135)
  FPS recibidos bajos y kbps ~= ancho de subida -> cuello de uplink / congestion
  FPS recibidos ~= FPS capturados (SELFTEST) y ambos bajos -> loop de captura

El JWT se pasa por variable de entorno al WS y nunca se imprime.

Uso:
  python scripts/measure_motion_stream.py --device 828 --seconds 90
"""
import argparse
import asyncio
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_selftest as fs  # noqa: E402


def selftest_samples(logs, device_id):
    out = []
    for log in logs:
        if log.get("device_id") != device_id:
            continue
        st = fs.parse_selftest(log.get("message") or "")
        if not st:
            continue
        out.append({"ts": str(log.get("timestamp")), "st": st})
    out.reverse()
    return out


def frames_of(samples):
    return [int(s["st"].get("frames", 0)) for s in samples]


async def run(url: str, device: int, seconds: int):
    ws_url = f"{url}/api/ws/viewer/{device}?token={os.environ['APOLLO_TOKEN']}"
    print(f"[PROBE] conectando a {url}/api/ws/viewer/{device}?token=***")
    frames = 0
    full = 0
    delta = 0
    total_bytes = 0
    t0 = time.time()
    last_report = t0
    stop = asyncio.Event()

    async def mover():
        # circulo chico en el centro: movimiento constante, desplazamiento minimo
        step = 0
        while not stop.is_set():
            ang = (step % 20) / 20.0 * 2.0 * math.pi
            x = 0.5 + 0.06 * math.cos(ang)
            y = 0.5 + 0.06 * math.sin(ang)
            try:
                await ws.send(json.dumps({"type": "mouse_move", "x": round(x, 4), "y": round(y, 4)}))
            except Exception as e:
                print(f"[MOVER] error enviando: {e}")
                return
            step += 1
            await asyncio.sleep(0.15)

    async with websockets.connect(ws_url, ping_interval=20, ping_timeout=60) as ws:
        print("[PROBE] conectado OK; arranca movimiento forzado")
        mover_task = asyncio.create_task(mover())
        try:
            while time.time() - t0 < seconds:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                except asyncio.TimeoutError:
                    print("[PROBE] 10s sin mensajes")
                    continue
                except websockets.ConnectionClosed as e:
                    print(f"[PROBE] conexion cerrada: {e}")
                    break
                if isinstance(msg, (bytes, bytearray)):
                    tag = msg[0]
                    if tag == 1:
                        full += 1
                    elif tag == 2:
                        delta += 1
                    frames += 1
                    total_bytes += len(msg)
                now = time.time()
                if now - last_report >= 10.0:
                    el = now - t0
                    print(f"[PROBE] t={el:5.1f}s frames={frames} full={full} delta={delta} "
                          f"{frames / el:5.2f} FPS {total_bytes / 1024 / el:6.0f} KiB/s")
                    last_report = now
        finally:
            stop.set()
            mover_task.cancel()
            try:
                await ws.send(json.dumps({"type": "mouse_move", "x": 0.5, "y": 0.5}))
                await ws.send(json.dumps({"type": "release_input"}))
            except Exception:
                pass

    elapsed = time.time() - t0
    print(f"[PROBE] FIN: {frames} binarios (full={full} delta={delta}) en {elapsed:.1f}s "
          f"-> {frames / elapsed:.2f} FPS | {total_bytes / 1024:.0f} KiB | "
          f"{total_bytes * 8 / 1000 / elapsed:.0f} kbps")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", type=int, required=True)
    ap.add_argument("--seconds", type=int, default=90)
    ap.add_argument("--limit", type=int, default=400)
    args = ap.parse_args()

    base = os.environ.get("APOLLO_BASE_URL", "https://support.ultimate.net.ar").rstrip("/")
    ws_base = os.environ.get("APOLLO_WS_URL", base.replace("https://", "wss://").replace("http://", "ws://"))
    user, pwd = fs.load_credentials()

    token = fs.login(base, user, pwd)
    before = selftest_samples(fs.fetch_logs(base, token, args.limit, args.device), args.device)
    f_before = frames_of(before)[-1] if before else None
    print(f"[ANTES] frames={f_before} ultima muestra: ", end="")
    if before:
        st = before[-1]["st"]
        print(f"status={st.get('status')} age_ms={st.get('frame_age_ms')} viewer={st.get('viewer')} hq={st.get('hq')} frame_ms={st.get('frame_ms')}")
    else:
        print("(sin muestras)")

    os.environ["APOLLO_TOKEN"] = token
    t0 = datetime.now(timezone.utc)
    print(f"[PROBE] arranca {t0:%H:%M:%S} UTC por {args.seconds}s (se va a mover el mouse remoto)")
    asyncio.run(run(ws_base, args.device, args.seconds))

    token = fs.login(base, user, pwd)
    after = selftest_samples(fs.fetch_logs(base, token, args.limit, args.device), args.device)
    new = [r for r in after if r not in before]
    for row in new:
        st = row["st"]
        print(f"[SELFTEST] {row['ts'][:19]} frames={st.get('frames')} age_ms={st.get('frame_age_ms')} "
              f"status={st.get('status')} frame_ms={st.get('frame_ms')}")
    if len(new) >= 2:
        t_first = datetime.fromisoformat(new[0]["ts"].replace("Z", "+00:00"))
        t_last = datetime.fromisoformat(new[-1]["ts"].replace("Z", "+00:00"))
        secs = (t_last - t_first).total_seconds()
        d = int(new[-1]["st"].get("frames", 0)) - int(new[0]["st"].get("frames", 0))
        if secs > 0:
            print(f"[DELTA] {d} frames capturados en {secs:.0f}s -> {d / secs:.2f} FPS de captura")
    elif new:
        print("[DELTA] 1 sola muestra nueva; selftest emite cada 60s")
    else:
        print("[DELTA] sin muestras nuevas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
