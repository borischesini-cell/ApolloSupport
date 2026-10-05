"""
Agente Centinela simulado — prueba local end-to-end del pipeline de video.

Se conecta al WS del backend como el agente real (device_name=TEST_PIPELINE_LOCAL),
manda telemetria, responde get_sessions y transmite frames WebP animados:
  - full:  b'\\x01' + webp(1280x720)
  - delta: b'\\x02' + u32be(len(json)) + json + webp(crop)

Pensado para ver el viewer remoto del Portal en modo debug:
  backend local en 8001  +  Portal dev en localhost (VITE_BACKEND_MODE=local)

Modos:
  --capture synth   imagen animada sintetica (default)
  --capture screen  captura REAL de esta pantalla, replicando el companion:
                    cascada RDP-safe (composite PrintWindow -> mss -> ImageGrab
                    -> GDI -> BitBlt) -> resize 1366px -> WEBP 82/58 method=0
                    -> frames completos + capture_warning/capture_ok si hay negro

Uso:
  python scripts/fake_agent_live.py [--url http://127.0.0.1:8001] [--fps 8]
                                    [--no-deltas] [--full-every 1.5]
  python scripts/fake_agent_live.py --capture screen
"""
import argparse
import asyncio
import ctypes
import json
import math
import os
import struct
import sys
import time
from io import BytesIO

from PIL import Image, ImageDraw
import websockets

DEVICE_NAME = "TEST_PIPELINE_LOCAL"
W, H = 1280, 720

SESSION_LIST = [
    {"id": 1, "name": "Console", "username": "TESTPC\\boris", "state": "Active", "current": True},
]


def render(t: float):
    """Fondo con grilla + circulo en movimiento. Devuelve (imagen PIL, bbox circulo)."""
    img = Image.new("RGB", (W, H), (16, 22, 34))
    d = ImageDraw.Draw(img)
    for x in range(0, W, 80):
        d.line([(x, 0), (x, H)], fill=(26, 34, 48))
    for y in range(0, H, 80):
        d.line([(0, y), (W, y)], fill=(26, 34, 48))
    cx = W / 2 + math.cos(t * 2.2) * (W * 0.32)
    cy = H / 2 + math.sin(t * 2.9) * (H * 0.30)
    r = 55
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(235, 90, 60))
    d.rectangle([10, 10, 660, 108], fill=(8, 12, 20))
    d.text((22, 22), "AGENTE SIMULADO - ApolloSupport", fill=(150, 230, 170))
    d.text((22, 46), f"t={t:6.2f}s   {time.strftime('%H:%M:%S')}", fill=(160, 180, 200))
    d.text((22, 70), "fake agent -> backend local -> Portal dev", fill=(120, 140, 170))
    return img, (cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4)


def to_webp(img: Image.Image, quality: int = 75) -> bytes:
    buf = BytesIO()
    img.save(buf, "WEBP", quality=quality)
    return buf.getvalue()


def clamp_box(box):
    x0, y0, x1, y1 = [int(v) for v in box]
    x0 = max(0, x0); y0 = max(0, y0)
    x1 = min(W, max(x0 + 2, x1)); y1 = min(H, max(y0 + 2, y1))
    return x0, y0, x1, y1


def union_box(a, b):
    if a is None:
        return b
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


async def reader(ws, force_full: asyncio.Event, stop: asyncio.Event):
    """Escucha mensajes del backend (refresh_frame, get_sessions, ping...)."""
    try:
        async for raw in ws:
            if isinstance(raw, (bytes, bytearray)):
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            t = data.get("type")
            if t == "get_sessions":
                await ws.send(json.dumps({
                    "type": "session_list",
                    "sessions": SESSION_LIST,
                    "current_session": 1,
                }))
                print("[fake] get_sessions -> session_list enviado")
            elif t == "refresh_frame":
                force_full.set()
                print("[fake] refresh_frame -> proximo frame completo")
            elif t == "ping":
                await ws.send(json.dumps({"type": "pong"}))
            else:
                print(f"[fake] msg del backend: {t or raw[:120]}")
    except websockets.ConnectionClosed:
        pass
    finally:
        stop.set()


async def telemetry_loop(ws, stop: asyncio.Event):
    while not stop.is_set():
        try:
            await ws.send(json.dumps({
                "type": "telemetry",
                "data": {
                    "status": "online",
                    "cpu": 7.5,
                    "ram": 42.0,
                    "os": "Windows 10 (simulado)",
                    "hostname": DEVICE_NAME,
                    "service_mode": False,
                    "centinela_version": "SIM",
                },
            }))
        except Exception:
            return
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass


async def run(base: str, fps: float, use_deltas: bool, full_every: float):
    ws_url = base.replace("http", "ws") + f"/api/ws/centinela/0?device_name={DEVICE_NAME}&session_id=1"
    print(f"[fake] conectando a {ws_url}")
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        device_id = welcome.get("device_id")
        print(f"[fake] welcome: {welcome.get('type')} device_id={device_id}")

        stop = asyncio.Event()
        force_full = asyncio.Event()
        rtask = asyncio.create_task(reader(ws, force_full, stop))
        ttask = asyncio.create_task(telemetry_loop(ws, stop))

        interval = 1.0 / max(1.0, fps)
        t0 = time.time()
        last_full = -999.0
        prev_box = None
        sent = 0
        bytes_sent = 0
        stat_at = time.time()

        try:
            while not stop.is_set():
                t = time.time() - t0
                img, box = render(t)
                want_full = (
                    not use_deltas
                    or (t - last_full) >= full_every
                    or force_full.is_set()
                    or prev_box is None
                )
                if want_full:
                    payload = b"\x01" + to_webp(img)
                    last_full = t
                    force_full.clear()
                else:
                    ubox = union_box(prev_box, box)
                    x0, y0, x1, y1 = clamp_box(ubox)
                    crop = img.crop((x0, y0, x1, y1))
                    delta = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "fw": W, "fh": H}
                    dj = json.dumps(delta).encode()
                    payload = b"\x02" + struct.pack(">I", len(dj)) + dj + to_webp(crop, quality=80)
                prev_box = box

                await ws.send(payload)
                sent += 1
                bytes_sent += len(payload)

                now = time.time()
                if now - stat_at >= 5.0:
                    print(f"[fake] frames={sent} ({sent / (now - t0):.1f}/s) bytes={bytes_sent / 1024:.0f}KB ultimo={'full' if want_full else 'delta'}")
                    stat_at = now

                await asyncio.sleep(interval)
        finally:
            stop.set()
            for task in (rtask, ttask):
                task.cancel()
            print(f"[fake] fin: {sent} frames, {bytes_sent / 1024:.0f}KB enviados")


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AGENT_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "agent")


def _load_dxgi():
    """Carga dxgi_capture.py del agente real (mismo capturador que el companion)."""
    if AGENT_DIR not in sys.path:
        sys.path.insert(0, AGENT_DIR)
    try:
        import dxgi_capture
        return dxgi_capture
    except Exception as exc:
        print(f"[fake] dxgi_capture no disponible ({exc}); uso cascada RDP-safe")
        return None


def is_black_frame(img: Image.Image) -> bool:
    """Misma heuristica que centinela.py:_is_black_frame."""
    w, h = img.size
    cx, cy = w // 2, h // 2
    pixels = [img.getpixel((cx + dx * 20, cy + dy * 20))
              for dx in range(-2, 3) for dy in range(-2, 3)
              if 0 < cx + dx * 20 < w and 0 < cy + dy * 20 < h]
    avg = sum(sum(p[:3]) for p in pixels) / (len(pixels) * 3) if pixels else 0
    return avg < 5


def _is_rdp_session():
    """True en sesion RDP: DXGI captura la GPU fisica (consola), no este escritorio."""
    try:
        return bool(ctypes.windll.user32.GetSystemMetrics(0x1000))  # SM_REMOTESESSION
    except Exception:
        return False


def _capture_visible_windows_composite():
    """Compone ventanas visibles con PrintWindow(PW_RENDERFULLCONTENT).
    Puerto de centinela.py: en RDP/Server, BitBlt/mss del desktop suelen devolver
    negro aunque el escritorio se vea bien; PrintWindow por HWND si funciona."""
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long),
            ]

        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        user32.IsIconic.argtypes = [ctypes.c_void_p]
        user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(RECT)]
        user32.PrintWindow.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        user32.PrintWindow.restype = ctypes.c_int
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.GetDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
        gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.SelectObject.restype = ctypes.c_void_p
        gdi32.BitBlt.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32,
        ]
        gdi32.BitBlt.restype = ctypes.c_int
        gdi32.PatBlt.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint32,
        ]
        gdi32.CreateSolidBrush.argtypes = [ctypes.c_uint32]
        gdi32.CreateSolidBrush.restype = ctypes.c_void_p
        gdi32.GetDIBits.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint,
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint,
        ]
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

        sw = user32.GetSystemMetrics(0)
        sh = user32.GetSystemMetrics(1)
        if sw <= 0 or sh <= 0:
            return None

        # EnumWindows: frente→atrás; reverse = fondo→frente para pintar
        hwnds_ordered = []

        def _enum(hwnd, _lp):
            try:
                hwnd_p = ctypes.c_void_p(hwnd)
                if not user32.IsWindowVisible(hwnd_p) or user32.IsIconic(hwnd_p):
                    return True
                rc = RECT()
                if not user32.GetWindowRect(hwnd_p, ctypes.byref(rc)):
                    return True
                ww = int(rc.right - rc.left)
                hh = int(rc.bottom - rc.top)
                if ww < 8 or hh < 8:
                    return True
                if rc.right <= 0 or rc.bottom <= 0 or rc.left >= sw or rc.top >= sh:
                    return True
                hwnds_ordered.append((int(hwnd) if not isinstance(hwnd, int) else hwnd, rc))
            except Exception:
                pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(WNDENUMPROC(_enum), 0)
        hwnds_ordered.reverse()
        if len(hwnds_ordered) > 25:
            hwnds_ordered = hwnds_ordered[-25:]

        hdc_screen = user32.GetDC(None)
        if not hdc_screen:
            return None
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, sw, sh)
        if not hdc_mem or not hbmp:
            if hbmp:
                gdi32.DeleteObject(hbmp)
            if hdc_mem:
                gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(None, hdc_screen)
            return None
        gdi32.SelectObject(hdc_mem, hbmp)
        brush = gdi32.CreateSolidBrush(0)
        old_br = gdi32.SelectObject(hdc_mem, brush)
        gdi32.PatBlt(hdc_mem, 0, 0, sw, sh, 0x000F0001)  # PATCOPY
        gdi32.SelectObject(hdc_mem, old_br)
        gdi32.DeleteObject(brush)

        PW_RENDERFULLCONTENT = 0x00000002
        painted = 0
        for hwnd_i, rc in hwnds_ordered:
            try:
                ww = int(rc.right - rc.left)
                hh = int(rc.bottom - rc.top)
                hdc_win = gdi32.CreateCompatibleDC(hdc_screen)
                hbmp_win = gdi32.CreateCompatibleBitmap(hdc_screen, ww, hh)
                if not hdc_win or not hbmp_win:
                    if hbmp_win:
                        gdi32.DeleteObject(hbmp_win)
                    if hdc_win:
                        gdi32.DeleteDC(hdc_win)
                    continue
                gdi32.SelectObject(hdc_win, hbmp_win)
                ok = user32.PrintWindow(ctypes.c_void_p(hwnd_i), hdc_win, PW_RENDERFULLCONTENT)
                if not ok:
                    ok = user32.PrintWindow(ctypes.c_void_p(hwnd_i), hdc_win, 0)
                if ok:
                    gdi32.BitBlt(
                        hdc_mem, int(rc.left), int(rc.top), ww, hh,
                        hdc_win, 0, 0, 0x00CC0020,
                    )
                    painted += 1
                gdi32.DeleteObject(hbmp_win)
                gdi32.DeleteDC(hdc_win)
            except Exception:
                pass

        class _BIH(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPPM", ctypes.c_int32),
                ("biYPPM", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]
        bmi = _BIH(
            biSize=ctypes.sizeof(_BIH), biWidth=sw, biHeight=-sh,
            biPlanes=1, biBitCount=32, biCompression=0,
        )
        buf = (ctypes.c_byte * (sw * sh * 4))()
        gdi32.GetDIBits(hdc_mem, hbmp, 0, sh, buf, ctypes.byref(bmi), 0)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)

        if painted <= 0:
            return None
        img = Image.frombuffer("RGBX", (sw, sh), bytes(buf), "raw", "BGRX", 0, 1)
        return img.convert("RGB")
    except Exception:
        return None


def _capture_gdi():
    """Captura via CreateDC('DISPLAY') — accede al framebuffer real del adaptador.
    Puerto directo de centinela.py (funciona en sesiones RDP/WDDM Server)."""
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int

        w = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
        h = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
        x = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
        y = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        if w <= 0 or h <= 0:
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            x = y = 0
        if w <= 0 or h <= 0:
            return None

        gdi32.CreateDCA.restype = ctypes.c_void_p
        gdi32.CreateDCA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
        user32.GetDesktopWindow.restype = ctypes.c_void_p
        user32.GetWindowDC.argtypes = [ctypes.c_void_p]
        user32.GetWindowDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
        gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.SelectObject.restype = ctypes.c_void_p
        gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
        gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

        hdc_s_raw = gdi32.CreateDCA(b"DISPLAY", None, None, None)
        use_release_dc = False
        hwnd = None
        if not hdc_s_raw:
            hwnd_raw = user32.GetDesktopWindow()
            hdc_s_raw = user32.GetWindowDC(hwnd_raw)
            if not hdc_s_raw:
                return None
            hwnd = ctypes.c_void_p(hwnd_raw)
            use_release_dc = True

        hdc_s = ctypes.c_void_p(hdc_s_raw)
        hdc_m_raw = gdi32.CreateCompatibleDC(hdc_s)
        if not hdc_m_raw:
            if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
            else: gdi32.DeleteDC(hdc_s)
            return None

        hdc_m = ctypes.c_void_p(hdc_m_raw)
        hbm_raw = gdi32.CreateCompatibleBitmap(hdc_s, w, h)
        if not hbm_raw:
            gdi32.DeleteDC(hdc_m)
            if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
            else: gdi32.DeleteDC(hdc_s)
            return None

        hbm = ctypes.c_void_p(hbm_raw)
        gdi32.SelectObject(hdc_m, hbm)
        gdi32.BitBlt(hdc_m, 0, 0, w, h, hdc_s, x, y, 0x00CC0020)

        class _BIH(ctypes.Structure):
            _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32),
                        ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16),
                        ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                        ("biSizeImage", ctypes.c_uint32), ("biXPPM", ctypes.c_int32),
                        ("biYPPM", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32),
                        ("biClrImportant", ctypes.c_uint32)]

        bmi = _BIH(biSize=ctypes.sizeof(_BIH), biWidth=w, biHeight=-h,
                   biPlanes=1, biBitCount=32, biCompression=0)
        buf = (ctypes.c_byte * (w * h * 4))()
        gdi32.GetDIBits(hdc_m, hbm, 0, h, buf, ctypes.byref(bmi), 0)

        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_m)
        if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
        else: gdi32.DeleteDC(hdc_s)

        img = Image.frombuffer("RGBX", (w, h), bytes(buf), "raw", "BGRX", 0, 1)
        return img.convert("RGB")
    except Exception:
        return None


def _capture_printwindow_fallback():
    """BitBlt del desktop via GetDC(GetDesktopWindow). Puerto de centinela.py."""
    try:
        gdi32 = ctypes.windll.gdi32
        user32 = ctypes.windll.user32

        user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        user32.GetSystemMetrics.restype = ctypes.c_int
        user32.GetDesktopWindow.argtypes = []
        user32.GetDesktopWindow.restype = ctypes.c_void_p
        user32.GetDC.argtypes = [ctypes.c_void_p]
        user32.GetDC.restype = ctypes.c_void_p
        user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        user32.ReleaseDC.restype = ctypes.c_int
        gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
        gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
        gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
        gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        gdi32.SelectObject.restype = ctypes.c_void_p
        gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
        gdi32.BitBlt.restype = ctypes.c_int
        gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        gdi32.GetDIBits.restype = ctypes.c_int
        gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
        gdi32.DeleteObject.restype = ctypes.c_int
        gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
        gdi32.DeleteDC.restype = ctypes.c_int

        hwnd = user32.GetDesktopWindow()
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        if w <= 0 or h <= 0:
            return None

        hdc_screen = user32.GetDC(hwnd)
        if not hdc_screen:
            return None

        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        if not hdc_mem:
            user32.ReleaseDC(hwnd, hdc_screen)
            return None

        hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
        if not hbmp:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(hwnd, hdc_screen)
            return None

        gdi32.SelectObject(hdc_mem, hbmp)
        SRCCOPY = 0xCC0020
        gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)

        bmi = (ctypes.c_uint32 * 40)()
        bmi[0] = 40
        bmi[1] = w; bmi[2] = -h
        bmi[3] = 1; bmi[4] = 32
        buf = (ctypes.c_char * (w * h * 4))()
        gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.cast(bmi, ctypes.POINTER(ctypes.c_uint32)), 0)
        img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA')

        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_screen)
        return img.convert('RGB')
    except Exception:
        return None


class ScreenStreamer:
    """Camino de captura del companion real: DXGI/ImageGrab -> resize max_width
    -> diff (ImageChops) -> WEBP still/motion method=0 -> frame completo 0x01."""

    def __init__(self, max_width: int, w_still: int, w_motion: int):
        self.dxc = _load_dxgi()
        self.max_width = max_width
        self.w_still = w_still
        self.w_motion = w_motion
        self.rdp = _is_rdp_session()
        self.use_dxgi = not self.rdp
        self.use_gdi = not self.rdp
        self.dxgi_failures = 0
        self.sct = None
        self._mss_checked = False
        self.prev = None
        self.motion_frames = 0
        self.black_streak = 0
        self.last_black_warn_at = 0.0
        self.black_warn_active = False
        self.method = "?"
        print(f"[fake] captura real: rdp={self.rdp} dxgi={self.use_dxgi} gdi={self.use_gdi}")

    def _ensure_mss(self):
        if self._mss_checked:
            return self.sct
        self._mss_checked = True
        try:
            import mss as _mss
            self.sct = _mss.mss()
            print(f"[fake] mss OK ({len(self.sct.monitors) - 1} monitores)")
        except Exception as exc:
            self.sct = None
            print(f"[fake] mss no disponible ({exc})")
        return self.sct

    def _capture_dxgi(self):
        if self.dxc is None:
            return None
        try:
            return self.dxc.grab_rgb()
        except Exception:
            return None

    def _try_non_black_capture(self):
        """Cascada RDP-safe identica a centinela.py: composite PrintWindow (si RDP)
        -> mss -> ImageGrab -> GDI -> BitBlt -> composite (si no RDP)."""
        from PIL import ImageGrab
        candidates = []
        if self.rdp:
            comp = _capture_visible_windows_composite()
            if comp is not None:
                candidates.append(("composite", comp))
        sct = self._ensure_mss()
        if sct is not None:
            try:
                monitor = sct.monitors[1]
                sct_img = sct.grab(monitor)
                candidates.append(("mss", Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")))
            except Exception:
                pass
        try:
            candidates.append(("imagegrab", ImageGrab.grab()))
        except Exception:
            pass
        g = _capture_gdi()
        if g is not None:
            candidates.append(("gdi", g))
        pw = _capture_printwindow_fallback()
        if pw is not None:
            candidates.append(("printwindow", pw))
        if not self.rdp:
            comp = _capture_visible_windows_composite()
            if comp is not None:
                candidates.append(("composite", comp))

        for name, img in candidates:
            if img is not None and not is_black_frame(img):
                return name, img
        if candidates:
            return candidates[0][0] + "-black", candidates[0][1]
        return None, None

    def _capture_frame(self):
        """Flujo del loop real de centinela.py: DXGI -> cascada -> GDI -> mss/ImageGrab."""
        from PIL import ImageGrab
        screenshot = None
        if self.use_dxgi:
            screenshot = self._capture_dxgi()
            if screenshot is None:
                self.dxgi_failures += 1
                if self.dxgi_failures >= 3:
                    self.use_dxgi = False
            elif is_black_frame(screenshot):
                self.use_dxgi = False
                screenshot = None
                if self.dxc is not None:
                    try:
                        self.dxc.reset_capturer()
                    except Exception:
                        pass

        if screenshot is None or is_black_frame(screenshot) or self.rdp:
            src, img = self._try_non_black_capture()
            if img is not None:
                if screenshot is None or is_black_frame(screenshot) or (
                    src and not str(src).endswith("-black")
                ):
                    screenshot = img
                    self.method = src

        if screenshot is None and self.use_gdi:
            screenshot = _capture_gdi()
            if screenshot is not None:
                self.method = "gdi"
            else:
                self.use_gdi = False

        if screenshot is None and not self.use_gdi:
            sct = self._ensure_mss()
            try:
                if sct is not None:
                    sct_img = sct.grab(sct.monitors[1])
                    screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                    self.method = "mss"
                else:
                    screenshot = ImageGrab.grab()
                    self.method = "imagegrab"
            except Exception:
                screenshot = None
        return screenshot

    def next_packet(self, force: bool):
        """Devuelve (payload_bytes | None, event | None).
        event: dict capture_warning/capture_ok cuando cambia el estado de negro."""
        from PIL import ImageChops
        img = self._capture_frame()
        if img is None:
            return None, None
        if self.max_width and img.width > self.max_width:
            nh = max(1, int(round(img.height * self.max_width / img.width)))
            img = img.resize((self.max_width, nh), Image.Resampling.BILINEAR)

        # No publicar frame negro si habia uno bueno antes (igual que el agente real)
        fresh_black = is_black_frame(img)
        if fresh_black and self.prev is not None and not is_black_frame(self.prev):
            img = self.prev

        event = None
        if fresh_black:
            self.black_streak += 1
            if self.black_streak >= 25 and (time.time() - self.last_black_warn_at) > 20.0:
                self.last_black_warn_at = time.time()
                self.black_warn_active = True
                msg = (
                    "Pantalla en negro: si entrás por Escritorio remoto (RDP), "
                    "restaurá o maximizá esa ventana en tu PC (no la dejes minimizada). "
                    "Windows deja de dibujar el escritorio y Centinela captura negro."
                    if self.rdp
                    else
                    "Captura en negro. Probá el botón «Despertar pantalla» o revisá "
                    "si la sesión está bloqueada / pantalla apagada."
                )
                event = {
                    "type": "capture_warning",
                    "reason": "rdp_minimized_or_blank" if self.rdp else "blank_screen",
                    "rdp": self.rdp,
                    "message": msg,
                }
            return None, event
        self.black_streak = 0
        if self.black_warn_active:
            self.black_warn_active = False
            event = {"type": "capture_ok", "message": "Captura de pantalla recuperada."}

        if self.prev is not None and not force:
            if ImageChops.difference(img, self.prev).getbbox() is None:
                return None, event

        self.motion_frames = min(self.motion_frames + 1, 10)
        quality = self.w_motion if self.motion_frames > 4 else self.w_still
        buf = BytesIO()
        img.save(buf, "WEBP", quality=quality, method=0)
        self.prev = img
        return b"\x01" + buf.getvalue(), event


async def run_screen(base: str, fps: float, max_width: int, w_still: int, w_motion: int):
    ws_url = base.replace("http", "ws") + f"/api/ws/centinela/0?device_name={DEVICE_NAME}&session_id=1"
    print(f"[fake] conectando a {ws_url} (captura REAL de pantalla)")
    async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
        welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
        print(f"[fake] welcome: {welcome.get('type')} device_id={welcome.get('device_id')}")

        stop = asyncio.Event()
        force_full = asyncio.Event()
        rtask = asyncio.create_task(reader(ws, force_full, stop))
        ttask = asyncio.create_task(telemetry_loop(ws, stop))

        streamer = ScreenStreamer(max_width, w_still, w_motion)
        loop = asyncio.get_running_loop()
        interval = 1.0 / max(1.0, fps)
        t0 = time.time()
        sent = 0
        bytes_sent = 0
        stat_at = time.time()

        try:
            while not stop.is_set():
                packet, event = await loop.run_in_executor(
                    None, streamer.next_packet, force_full.is_set()
                )
                if event:
                    await ws.send(json.dumps(event))
                    print(f"[fake] {event['type']} enviado")
                if packet:
                    await ws.send(packet)
                    force_full.clear()
                    sent += 1
                    bytes_sent += len(packet)

                now = time.time()
                if now - stat_at >= 5.0:
                    print(f"[fake] frames={sent} ({sent / (now - t0):.1f}/s) "
                          f"bytes={bytes_sent / 1024:.0f}KB via={streamer.method} {max_width}px")
                    stat_at = now
                await asyncio.sleep(interval)
        finally:
            stop.set()
            for task in (rtask, ttask):
                task.cancel()
            print(f"[fake] fin: {sent} frames, {bytes_sent / 1024:.0f}KB enviados")


def main():
    ap = argparse.ArgumentParser(description="Agente Centinela simulado (prueba local)")
    ap.add_argument("--url", default="http://127.0.0.1:8001", help="base del backend local")
    ap.add_argument("--fps", type=float, default=8.0, help="frames por segundo")
    ap.add_argument("--no-deltas", action="store_true", help="mandar siempre frame completo (modo synth)")
    ap.add_argument("--full-every", type=float, default=1.5, help="cada cuantos segundos un full frame (modo synth)")
    ap.add_argument("--capture", choices=("synth", "screen"), default="synth",
                    help="synth: imagen animada | screen: captura real (como el companion)")
    ap.add_argument("--max-width", type=int, default=1366, help="ancho maximo de captura (default del agente real)")
    ap.add_argument("--quality-still", type=int, default=82, help="webp calidad pantalla quieta")
    ap.add_argument("--quality-motion", type=int, default=58, help="webp calidad pantalla en movimiento")
    args = ap.parse_args()
    try:
        if args.capture == "screen":
            asyncio.run(run_screen(args.url, args.fps, args.max_width,
                                   args.quality_still, args.quality_motion))
        else:
            asyncio.run(run(args.url, args.fps, not args.no_deltas, args.full_every))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
