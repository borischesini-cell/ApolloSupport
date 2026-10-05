"""Mide el stream H.264 (HQ) real que recibe un viewer del portal.

Replica lo que hace el frontend con el modo HQ activado: abre los DOS WS:
  - /api/ws/viewer/{id}       std (technician_joined + refresh_frame cada 20s
                              para que el agente no caiga por viewer idle)
  - /api/ws/viewer/{id}/hq    push fMP4 crudo que el backend forwarda

Cuenta bytes, fragmentos fMP4 (box 'moof') y la hora de llegada de cada uno
para estimar los FPS de pared del pipeline remoto (GDI feed + x264 en la PC
del agente). El agente corta un fragmento por keyframe (-g 12), asi que:

    FPS pared ~ 12 * moofs / segundos

Tambien cuenta los frames WebP que llegan por el WS std (el numero que
mostraria el indicador del portal).

El JWT se pasa por variable de entorno y nunca se imprime.

Uso:
  python scripts/measure_hq_stream.py --device 828 --seconds 90
"""
import argparse
import asyncio
import json
import os
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_selftest as fs  # noqa: E402


def _u32(buf, off):
    return struct.unpack_from(">I", buf, off)[0]


def _u64(buf, off):
    return struct.unpack_from(">Q", buf, off)[0]


def find_box(buf, fourcc, start=0):
    i = buf.find(fourcc, start)
    while i >= 0:
        if i >= 4 and _u32(buf, i - 4) >= 8:
            yield i
        i = buf.find(fourcc, i + 1)


def parse_mp4_stats(buf, chunk_meta):
    """Devuelve (timescale, lista de moof: {wall, offset, tfdt})."""
    timescale = None
    for i in find_box(buf, b"mvhd"):
        ver = buf[i + 4]
        off = i + 16 if ver == 0 else i + 24
        if off + 4 <= len(buf):
            timescale = _u32(buf, off)
            break
    moofs = []
    for i in find_box(buf, b"moof"):
        wall = None
        for el, ln, cum in chunk_meta:
            if cum <= i - 4:
                wall = el
        tfdt = None
        box_end = min(i - 4 + _u32(buf, i - 4), len(buf))
        j = buf.find(b"tfdt", i, box_end)
        if j >= 0 and j + 20 <= len(buf):
            ver = buf[j + 4]
            if ver == 1 and j + 20 <= len(buf):
                tfdt = _u64(buf, j + 8)
            elif ver == 0 and j + 16 <= len(buf):
                tfdt = _u32(buf, j + 8)
        moofs.append({"wall": wall, "tfdt": tfdt})
    return timescale, moofs


async def run(url: str, device: int, seconds: int):
    token = os.environ["APOLLO_TOKEN"]
    std_url = f"{url}/api/ws/viewer/{device}?token={token}"
    hq_url = f"{url}/api/ws/viewer/{device}/hq?token={token}"

    stop = asyncio.Event()
    webp = {"frames": 0, "full": 0, "delta": 0, "bytes": 0}

    async def std_keepalive(std_ws):
        try:
            while not stop.is_set():
                await std_ws.send(json.dumps({"type": "refresh_frame"}))
                await asyncio.sleep(20.0)
        except Exception:
            pass

    async def std_drain(std_ws):
        try:
            while not stop.is_set():
                msg = await asyncio.wait_for(std_ws.recv(), timeout=5.0)
                if isinstance(msg, (bytes, bytearray)):
                    webp["frames"] += 1
                    webp["bytes"] += len(msg)
                    if msg[0] == 1:
                        webp["full"] += 1
                    elif msg[0] == 2:
                        webp["delta"] += 1
        except Exception:
            pass
        finally:
            stop.set()

    print(f"[HQ-PROBE] conectando std  {url}/api/ws/viewer/{device}?token=***")
    async with websockets.connect(std_url, ping_interval=20, ping_timeout=60) as std:
        await std.send(json.dumps({"type": "refresh_frame"}))
        print(f"[HQ-PROBE] conectando /hq {url}/api/ws/viewer/{device}/hq?token=***")
        async with websockets.connect(hq_url, ping_interval=20, ping_timeout=60) as hq:
            tasks = [
                asyncio.create_task(std_keepalive(std)),
                asyncio.create_task(std_drain(std)),
            ]
            t0 = time.time()
            buf = bytearray()
            chunk_meta = []  # (elapsed, len, cum_offset)
            total = 0
            last_report = t0
            try:
                while time.time() - t0 < seconds:
                    try:
                        msg = await asyncio.wait_for(hq.recv(), timeout=10.0)
                    except asyncio.TimeoutError:
                        print("[HQ-PROBE] 10s sin datos H.264")
                        continue
                    except websockets.ConnectionClosed as e:
                        print(f"[HQ-PROBE] /hq cerrado por el server: {e}")
                        break
                    if isinstance(msg, (bytes, bytearray)):
                        el = time.time() - t0
                        chunk_meta.append((el, len(msg), total))
                        total += len(msg)
                        buf.extend(msg)
                    now = time.time()
                    if now - last_report >= 15.0:
                        n_moof = sum(1 for _ in find_box(buf, b"moof"))
                        el = now - t0
                        print(f"[HQ-PROBE] t={el:5.1f}s bytes={total} "
                              f"({total * 8 / 1000 / el:5.0f} kbps) moof={n_moof} "
                              f"est={12 * n_moof / el:4.1f} FPS pared")
                        last_report = now
            finally:
                stop.set()
                for t in tasks:
                    t.cancel()

    el = time.time() - t0
    timescale, moofs = parse_mp4_stats(bytes(buf), chunk_meta)
    print(f"\n[HQ-PROBE] FIN {el:.1f}s | bytes={total} | "
          f"{total * 8 / 1000 / max(el, 0.1):.0f} kbps | timescale={timescale} | "
          f"moofs={len(moofs)}")
    print(f"[HQ-PROBE] WebP por std: {webp['frames']} frames "
          f"(full={webp['full']} delta={webp['delta']}) "
          f"{webp['bytes'] / 1024 / max(el, 0.1):.0f} KiB/s "
          f"-> indicador portal ~ {round(webp['frames'] / max(el, 0.1))} FPS")

    if len(moofs) >= 2:
        print("\n[FRAGMENTOS] wall_delta_s | frames_nom | est_fps")
        fps_vals = []
        for k in range(len(moofs) - 1):
            a, b = moofs[k], moofs[k + 1]
            if a["wall"] is None or b["wall"] is None:
                continue
            dwall = b["wall"] - a["wall"]
            frames = None
            if a["tfdt"] is not None and b["tfdt"] is not None and timescale:
                frames = (b["tfdt"] - a["tfdt"]) / (timescale / 24.0)
            est = (frames if frames else 12) / dwall if dwall > 0 else 0
            fps_vals.append(est)
            print(f"  frag #{k + 1}: {dwall:6.2f}s | "
                  f"{('%6.1f' % frames) if frames else '   n/a'} | {est:5.2f}")
        if fps_vals:
            avg = sum(fps_vals) / len(fps_vals)
            print(f"\n[RESULTADO] H.264 real ~ {avg:.1f} FPS pared "
                  f"(min {min(fps_vals):.2f} / max {max(fps_vals):.2f})")
    elif len(moofs) == 1:
        print("[RESULTADO] un solo fragmento en la ventana; no alcanza para estimar FPS")
    else:
        print("[RESULTADO] sin fragmentos: el agente no estaba streameando H.264")


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
    logs = fs.fetch_logs(base, token, args.limit, args.device)
    samples = []
    for log in logs:
        st = fs.parse_selftest(log.get("message") or "")
        if st:
            samples.append((str(log.get("timestamp"))[:19], st))
    samples.reverse()
    if samples:
        ts, st = samples[-1]
        print(f"[ANTES] {ts} status={st.get('status')} frames={st.get('frames')} "
              f"viewer={st.get('viewer')} hq={st.get('hq')} frame_ms={st.get('frame_ms')}")

    os.environ["APOLLO_TOKEN"] = token
    print(f"[HQ-PROBE] arranca {datetime.now(timezone.utc):%H:%M:%S} UTC por {args.seconds}s")
    asyncio.run(run(ws_base, args.device, args.seconds))

    token = fs.login(base, user, pwd)
    logs = fs.fetch_logs(base, token, args.limit, args.device)
    for log in logs[:6]:
        st = fs.parse_selftest(log.get("message") or "")
        if st:
            print(f"[SELFTEST] {str(log.get('timestamp'))[:19]} frames={st.get('frames')} "
                  f"status={st.get('status')} viewer={st.get('viewer')} hq={st.get('hq')} "
                  f"frame_ms={st.get('frame_ms')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
