"""Mide el costo por etapa del pipeline de captura del agente, sin importar centinela.py.

Extrae por AST las funciones de captura reales del fuente (incluso las anidadas dentro
de capture_screenshot_thread_func) y las ejecuta aisladas, para saber cual es el techo
de FPS de esta PC y donde se va el tiempo por frame.

Uso:  python scripts/bench_capture.py [--iters 20] [--width 1366] [--dump]
"""
import argparse
import ast
import builtins
import ctypes
import io
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "agent" / "centinela.py"
DUMP = ROOT / "agent" / "dist" / "bench_frames"

TOP_LEVEL = {
    "_capture_gdi",
    "_capture_visible_windows_composite",
    "_capture_dxgi",
    "_is_rdp_session",
}
NESTED = {
    "_capture_printwindow_fallback",
    "_is_black_frame",
}


class _Permissive(dict):
    """Namespace que respeta builtins y devuelve MagicMock solo para globales reales."""

    def __missing__(self, key):
        if hasattr(builtins, key):
            return getattr(builtins, key)
        m = MagicMock(name=key)
        self[key] = m
        return m


def _func_source(lines, node):
    start = node.lineno - 1
    end = getattr(node, "end_lineno", start + 1)
    return "".join(lines[start:end])


def load_funcs():
    raw = SRC.read_bytes().decode("utf-8", "replace")
    lines = raw.splitlines(keepends=True)
    tree = ast.parse(raw)

    chunks = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in TOP_LEVEL:
            chunks.append(_func_source(lines, node))
            found.add(node.name)
        # funciones anidadas dentro de capture_screenshot_thread_func
        if isinstance(node, ast.FunctionDef) and node.name == "capture_screenshot_thread_func":
            for sub in ast.walk(node):
                if isinstance(sub, ast.FunctionDef) and sub.name in NESTED:
                    chunks.append(_func_source(lines, sub))
                    found.add(sub.name)

    missing = (TOP_LEVEL | NESTED) - found
    if missing:
        print("[!] No se encontraron en el fuente: %s" % ", ".join(sorted(missing)))

    ns = _Permissive()
    ns["ctypes"] = ctypes
    ns["sys"] = sys
    ns["logger"] = MagicMock()
    ns["ACTIVE_MONITOR"] = 1
    ns["HQ_MODE_ACTIVE"] = False
    # nombre unico para que el traceback muestre el chunk correcto
    exec(compile("\n\n".join(chunks), "<bench_chunks>", "exec"), ns)
    return ns


def is_black(img):
    if img is None:
        return True
    try:
        w, h = img.size
        cx, cy = w // 2, h // 2
        px = [img.getpixel((cx + dx * 20, cy + dy * 20))
              for dx in range(-2, 3) for dy in range(-2, 3)
              if 0 < cx + dx * 20 < w and 0 < cy + dy * 20 < h]
        if not px:
            return True
        return (sum(sum(p[:3]) for p in px) / (len(px) * 3)) < 5
    except Exception:
        return True


MIN_SIDE = 64


def real_size(img):
    """(w, h) reales o None si el objeto no es una imagen inspeccionable."""
    try:
        w, h = img.size
        return int(w), int(h)
    except Exception:
        return None


def bench(fn, iters):
    times, last, err = [], None, None
    for _ in range(iters):
        t0 = time.perf_counter()
        try:
            last = fn()
        except Exception as e:
            err, last = "%s: %s" % (type(e).__name__, e), None
        times.append((time.perf_counter() - t0) * 1000.0)
    return last, err, sum(times) / len(times), min(times), max(times)


def row(label, ok, avg, mn, mx, extra=""):
    print("%-36s %-6s %8.1f %8.1f %8.1f  %s"
          % (label, "OK" if ok else "FALLA", avg, mn, mx, extra))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iters", type=int, default=20)
    ap.add_argument("--width", type=int, default=1366)
    ap.add_argument("--dump", action="store_true", help="guarda un PNG por fuente")
    args = ap.parse_args()

    ns = load_funcs()
    from PIL import Image, ImageChops, ImageGrab
    try:
        import mss
    except ImportError:
        mss = None

    if args.dump:
        DUMP.mkdir(parents=True, exist_ok=True)

    print("=" * 92)
    print("BENCHMARK DE CAPTURA  —  iters=%d   rdp=%s" % (args.iters, bool(ns["_is_rdp_session"]())))
    print("=" * 92)

    sct = None
    if mss is not None:
        try:
            sct = mss.mss()
        except Exception as e:
            print("mss no inicializable: %s" % e)

    def _mss():
        if sct is None:
            raise RuntimeError("mss no disponible")
        g = sct.grab(sct.monitors[1])
        return Image.frombytes("RGB", g.size, g.bgra, "raw", "BGRX")

    cands = [
        ("composite", ns["_capture_visible_windows_composite"]),
        ("mss", _mss),
        ("imagegrab", ImageGrab.grab),
        ("gdi", ns["_capture_gdi"]),
        ("printwindow", ns.get("_capture_printwindow_fallback")),
        ("dxgi", ns["_capture_dxgi"]),
    ]

    print("\n--- 1. FUENTES DE CAPTURA (una por vez) ---")
    print("%-36s %-6s %8s %8s %8s" % ("fuente", "estado", "avg_ms", "min_ms", "max_ms"))
    working = {}
    for name, fn in cands:
        if fn is None:
            print("%-36s %s" % (name, "NO EXTRAIDA"))
            continue
        img, err, avg, mn, mx = bench(fn, args.iters)
        size = real_size(img)
        usable = err is None and size is not None and min(size) >= MIN_SIDE and not is_black(img)
        note = ""
        if err:
            note = "<- " + err[:60]
        elif img is None:
            note = "<- devolvio None"
        elif size is None:
            note = "<- size ilegible: %r" % (getattr(img, "size", None),)
        elif min(size) < MIN_SIDE:
            note = "<- %dx%d demasiado chica (fuente rota)" % size
        elif is_black(img):
            note = "<- imagen NEGRA"
        else:
            note = "%dx%d" % size
            working[name] = (avg, fn)
        row(name, usable, avg, mn, mx, note)
        if args.dump and usable:
            img.save(DUMP / ("%s.png" % name))

    if not working:
        print("\n[!] Ninguna fuente devolvio imagen usable. No se puede seguir.")
        return

    best_name = min(working, key=lambda k: working[k][0])
    best_avg, best_fn = working[best_name]
    print("\nMejor fuente usable: %s  (%.1f ms => %.1f FPS)"
          % (best_name, best_avg, 1000.0 / best_avg))

    print("\n--- 2. COSTO DE LA CASCADA QUE HACE EL AGENTE HOY ---")

    def cascade():
        out = None
        for _n, f in cands:
            if f is None:
                continue
            try:
                r = f()
            except Exception:
                r = None
            if out is None and r is not None:
                out = r
        return out

    img, err, avg, mn, mx = bench(cascade, max(5, args.iters // 2))
    row("cascada (todas las fuentes)", img is not None, avg, mn, mx,
        "=> techo %.1f FPS" % (1000.0 / avg if avg else 0))
    row("solo fuente ganadora", True, best_avg, 0, 0,
        "=> techo %.1f FPS" % (1000.0 / best_avg))

    img = best_fn()
    print("\nFrame de trabajo: %dx%d modo=%s (fuente=%s)" % (img.size[0], img.size[1], img.mode, best_name))

    print("\n--- 3. REDIMENSIONADO ---")
    if img.size[0] > args.width:
        th = max(1, int(round(img.size[1] * args.width / img.size[0])))
        target = (args.width, th)
    else:
        target = img.size
    small = img.resize(target, Image.BILINEAR)
    _, _, avg, mn, mx = bench(lambda: img.resize(target, Image.BILINEAR), args.iters)
    row("resize BILINEAR -> %dx%d" % target, True, avg, mn, mx)

    print("\n--- 4. DIRTY RECT ---")
    prev = small.copy()
    _, _, avg_d, mn, mx = bench(lambda: ImageChops.difference(small, prev).getbbox(), args.iters)
    row("difference+getbbox (quieto)", True, avg_d, mn, mx, "bbox=None => el agente NO publica")
    import random
    noisy = small.copy()
    for _ in range(200):
        noisy.putpixel((random.randrange(small.size[0]), random.randrange(small.size[1])),
                       (random.randrange(256),) * 3)
    _, _, avg_n, mn, mx = bench(lambda: ImageChops.difference(small, noisy).getbbox(), args.iters)
    row("difference+getbbox (con cambios)", True, avg_n, mn, mx)

    print("\n--- 5. ENCODE WEBP (%dx%d) ---" % small.size)
    for q in (58, 82):
        for method in (0, 4):
            def _enc(q=q, method=method):
                b = io.BytesIO()
                small.save(b, format="WEBP", quality=q, method=method)
                return b.getvalue()
            data, err, avg, mn, mx = bench(_enc, max(5, args.iters // 2))
            row("WEBP q=%d method=%d" % (q, method), err is None, avg, mn, mx,
                "%7.1f KB" % (len(data) / 1024.0 if data else 0))

    def _enc_b64():
        import base64
        b = io.BytesIO()
        small.save(b, format="WEBP", quality=82, method=0)
        return base64.b64encode(b.getvalue())

    _, _, avg, mn, mx = bench(_enc_b64, max(5, args.iters // 2))
    row("WEBP q=82 m=0 + base64", True, avg, mn, mx, "(la via binaria no necesita b64)")

    # Alternativas de encode: JPEG (el frontend hardcodea image/webp, asi que esto
    # solo sirve para saber cuanto hay sobre la mesa) y WEBP a menor ancho.
    for q in (70, 82):
        def _encj(q=q):
            b = io.BytesIO()
            small.save(b, format="JPEG", quality=q, optimize=False)
            return b.getvalue()
        data, err, avg, mn, mx = bench(_encj, max(5, args.iters // 2))
        row("JPEG q=%d" % q, err is None, avg, mn, mx,
            "%7.1f KB" % (len(data) / 1024.0 if data else 0))

    for w in (1280, 1152, 1024):
        if w >= small.size[0]:
            continue
        h = max(1, int(round(small.size[1] * w / small.size[0])))
        resized = small.resize((w, h), Image.BILINEAR)

        def _encw(resized=resized):
            b = io.BytesIO()
            resized.save(b, format="WEBP", quality=82, method=0)
            return b.getvalue()
        data, err, avg, mn, mx = bench(_encw, max(5, args.iters // 2))
        _, _, avg_r, _, _ = bench(lambda: img.resize((w, h), Image.BILINEAR), args.iters)
        row("WEBP q=82 m=0 @%dx%d" % (w, h), err is None, avg + avg_r, mn, mx,
            "%7.1f KB (resize %.1f + enc %.1f)" % (len(data) / 1024.0 if data else 0, avg_r, avg))

    print("\n--- 6. PRESUPUESTO POR FRAME ---")
    _, _, t_cap, _, _ = bench(best_fn, args.iters)
    _, _, t_res, _, _ = bench(lambda: img.resize(target, Image.BILINEAR), args.iters)
    _, _, t_dif, _, _ = bench(lambda: ImageChops.difference(small, prev).getbbox(), args.iters)

    def _e():
        b = io.BytesIO()
        small.save(b, format="JPEG", quality=55, subsampling=2)
        return b.getvalue()
    _, _, t_enc, _, _ = bench(_e, args.iters)

    print("  captura (%s) %8.1f ms" % (best_name, t_cap))
    print("  resize         %8.1f ms" % t_res)
    print("  dirty-rect     %8.1f ms" % t_dif)
    print("  jpeg q55 sub2  %8.1f ms" % t_enc)
    tot = t_cap + t_res + t_dif + t_enc
    print("  " + "-" * 30)
    print("  TOTAL          %8.1f ms  => techo %.1f FPS" % (tot, 1000.0 / tot if tot else 0))
    print("\n  _FRAME_BUDGET del agente = 45.0 ms (22 FPS)")
    print("  Objetivo de Boris        = 50.0 ms (20 FPS)")
    if tot <= 50.0:
        print("  => ALCANZABLE con esta fuente de captura.")
    else:
        print("  => NO alcanza: hay que bajar captura o encode.")

    print("\n--- 7. PIPELINE PARALELO (captura en un hilo, resize+diff+encode en el otro) ---")
    import threading

    def encode_jpeg(im, q=55):
        b = io.BytesIO()
        im.save(b, format="JPEG", quality=q, subsampling=2)
        return b.getvalue()

    def stage_post(im):
        """Lo que hace el agente despues de capturar: resize + dirty-rect + encode."""
        sm = im.resize(target, Image.BILINEAR) if im.size != target else im
        ImageChops.difference(sm, prev).getbbox()
        return encode_jpeg(sm)

    def serial():
        return stage_post(best_fn())

    def make_cap_for_thread():
        """mss no es thread-safe: cada hilo necesita su propia instancia."""
        if best_name == "mss" and mss is not None:
            s = mss.mss()

            def _cap():
                g = s.grab(s.monitors[1])
                return Image.frombytes("RGB", g.size, g.bgra, "raw", "BGRX")
            return _cap
        return best_fn

    _, err_s, avg_serial, _, _ = bench(serial, args.iters)
    row("serial (todo en el mismo hilo)", err_s is None, avg_serial, 0, 0,
        "=> %.1f FPS" % (1000.0 / avg_serial if avg_serial else 0))

    stop = threading.Event()
    slot = {}
    slot_lock = threading.Lock()
    caps = [0]

    def cap_worker():
        cap = make_cap_for_thread()
        while not stop.is_set():
            try:
                im = cap()
            except Exception:
                continue
            with slot_lock:
                slot["img"] = im
            caps[0] += 1

    thr = threading.Thread(target=cap_worker, daemon=True)
    thr.start()
    secs = 5.0
    t0 = time.perf_counter()
    published = 0
    while time.perf_counter() - t0 < secs:
        with slot_lock:
            im = slot.get("img")
        if im is None:
            time.sleep(0.001)
            continue
        try:
            stage_post(im)
            published += 1
        except Exception as e:
            print("  post-stage fallo: %s" % e)
            break
    elapsed = time.perf_counter() - t0
    stop.set()
    thr.join(timeout=3)
    fps_pub = published / elapsed if elapsed else 0
    fps_serial = 1000.0 / avg_serial if avg_serial else 0
    row("paralelo: post-stage (publica)", True, 1000.0 / fps_pub if fps_pub else 0, 0, 0,
        "=> %.1f FPS  (%d caps del hilo en %.1fs = %.1f FPS de captura)"
        % (fps_pub, caps[0], elapsed, caps[0] / elapsed if elapsed else 0))
    if fps_pub < fps_serial * 1.15:
        print("  => el solapamiento NO rinde (GIL): %.1f FPS contra %.1f FPS serial"
              % (fps_pub, fps_serial))
    else:
        print("  => el solapamiento rinde: %.1f FPS contra %.1f FPS serial"
              % (fps_pub, fps_serial))

    print("\n--- 8. FUGA DE RECURSOS GDI (hipotesis del 'BitBlt: recurso en uso') ---")
    import os
    k32 = ctypes.windll.kernel32
    u32 = ctypes.windll.user32
    hproc = k32.GetCurrentProcess()

    def res():
        return (u32.GetGuiResources(hproc, 0), u32.GetGuiResources(hproc, 1))

    print("  GDI objects / USER objects al iniciar la seccion: %d / %d" % res())
    for _ in range(60):
        cascade()
    print("  tras  60 cascadas: %d / %d" % res())
    for _ in range(60):
        cascade()
    print("  tras 120 cascadas: %d / %d" % res())
    for _ in range(120):
        cascade()
    print("  tras 240 cascadas: %d / %d" % res())

    for label, fn in (("mss", _mss), ("imagegrab", ImageGrab.grab)):
        im, er, av, mnm, mxm = bench(fn, 10)
        row("  %s tras 240 cascadas" % label,
            er is None and im is not None and not is_black(im), av, mnm, mxm,
            (er or "")[:70])
    print("  PID del benchmark: %d" % os.getpid())


if __name__ == "__main__":
    main()
