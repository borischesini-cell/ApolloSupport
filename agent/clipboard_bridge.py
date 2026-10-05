"""Puente de portapapeles del técnico (como AnyDesk).

El portal corre en el navegador y no puede leer archivos copiados en el Explorador.
Este proceso, en la PC del técnico, lee CF_HDROP y se los entrega solo a Apollo.

Escucha en 127.0.0.1:47915
"""
import json
import os
import sys
import time
import ctypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = "127.0.0.1"
PORT = 47915
MAX_FILES = 8
MAX_BYTES = 25 * 1024 * 1024

ALLOWED_ORIGINS = {
    "https://support.ultimate.net.ar",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
}


def _origin_ok(origin: str) -> bool:
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    if origin.startswith("http://localhost:") or origin.startswith("http://127.0.0.1:"):
        return True
    return False


def _clipboard_files():
    u32 = ctypes.windll.user32
    CF_HDROP = 15
    files = []
    seq = int(u32.GetClipboardSequenceNumber())
    for _ in range(5):
        if u32.OpenClipboard(None):
            try:
                if u32.IsClipboardFormatAvailable(CF_HDROP):
                    h = u32.GetClipboardData(CF_HDROP)
                    if h:
                        s32 = ctypes.windll.shell32
                        count = s32.DragQueryFileW(h, 0xFFFFFFFF, None, 0)
                        buf = ctypes.create_unicode_buffer(1024)
                        for i in range(int(count)):
                            n = s32.DragQueryFileW(h, i, buf, 1024)
                            if n > 0:
                                files.append(buf.value)
            finally:
                u32.CloseClipboard()
            break
        time.sleep(0.03)
    return seq, files


class State:
    def __init__(self):
        self.seq = 0
        self.paths = []
        self.changed_at = 0.0
        self.ready = False
        self.lock = threading.Lock()

    def watch_once(self):
        seq, paths = _clipboard_files()
        files = []
        for p in paths:
            if not p or not os.path.isfile(p):
                continue
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            if size < 0 or size > MAX_BYTES:
                continue
            files.append(p)
            if len(files) >= MAX_FILES:
                break
        with self.lock:
            if not self.ready:
                self.seq = seq
                self.paths = files
                self.changed_at = 0.0
                self.ready = True
                return
            if seq != self.seq or files != self.paths:
                self.seq = seq
                self.paths = files
                self.changed_at = time.time()

    def read(self):
        with self.lock:
            return self.seq, list(self.paths), self.changed_at


STATE = State()


def _watch_loop():
    while True:
        try:
            STATE.watch_once()
        except Exception:
            pass
        time.sleep(0.4)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _origin(self) -> str:
        origin = self.headers.get("Origin", "")
        return origin if _origin_ok(origin) else ""

    def _write_cors(self, origin: str):
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _deny(self):
        body = b'{"error":"origin"}'
        self.send_response(403)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        origin = self._origin()
        if not origin:
            self._deny()
            return
        self.send_response(204)
        self._write_cors(origin)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        origin = self._origin()
        if not origin:
            self._deny()
            return
        path = self.path.split("?", 1)[0]
        if path == "/clipboard":
            seq, paths, changed = STATE.read()
            payload = {
                "seq": seq,
                "changed_at": changed,
                "files": [
                    {"index": i, "name": os.path.basename(p), "size": os.path.getsize(p)}
                    for i, p in enumerate(paths)
                ],
            }
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self._write_cors(origin)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/file":
            try:
                qs = self.path.split("?", 1)[1] if "?" in self.path else ""
                idx = int(dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("i", "-1"))
            except Exception:
                idx = -1
            _seq, paths, _changed = STATE.read()
            if idx < 0 or idx >= len(paths):
                self.send_response(404)
                self._write_cors(origin)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            fp = paths[idx]
            try:
                size = os.path.getsize(fp)
                self.send_response(200)
                self._write_cors(origin)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(size))
                self.end_headers()
                with open(fp, "rb") as fh:
                    while True:
                        chunk = fh.read(1024 * 256)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
            except Exception:
                self.send_response(500)
                self._write_cors(origin)
                self.send_header("Content-Length", "0")
                self.end_headers()
            return
        if path == "/health":
            body = b'{"ok":true}'
            self.send_response(200)
            self._write_cors(origin)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self._write_cors(origin)
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        print(f"No se pudo abrir {HOST}:{PORT}: {e}", file=sys.stderr)
        return 1
    print(f"Apollo clipboard bridge en http://{HOST}:{PORT}")
    threading.Thread(target=_watch_loop, daemon=True).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
