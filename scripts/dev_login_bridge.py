"""
Puente de login para el Portal dev (prueba local end-to-end).

Lee las credenciales de ~/.apollo_selftest.json en runtime, hace el login real
contra POST {backend}/api/token y sirve {"token", "user"} por HTTP en
127.0.0.1:8765 para que el browser en modo dev las inyecte en localStorage
sin que las credenciales pasen por terminal, logs ni chat.

Uso: python scripts/dev_login_bridge.py [--backend http://127.0.0.1:8001] [--port 8765]
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

CRED_PATH = os.path.join(os.path.expanduser("~"), ".apollo_selftest.json")


def do_login(backend: str):
    with open(CRED_PATH, "r", encoding="utf-8") as fh:
        creds = json.load(fh)
    body = urllib.parse.urlencode({
        "username": creds["user"],
        "password": creds["pass"],
    }).encode()
    req = urllib.request.Request(
        f"{backend}/api/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (ApolloDevBridge)",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


class Handler(BaseHTTPRequestHandler):
    session = {}

    def do_GET(self):
        if self.path.split("?")[0] != "/session":
            self.send_response(404)
            self.end_headers()
            return
        payload = json.dumps({
            "token": self.session.get("access_token"),
            "user": self.session.get("usuario"),
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description="Puente de login para Portal dev")
    ap.add_argument("--backend", default="http://127.0.0.1:8001")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    data = do_login(args.backend)
    Handler.session = data
    print(f"[bridge] login OK contra {args.backend} (usuario {data.get('usuario', {}).get('email', '?')})")
    print(f"[bridge] sesion servida en http://127.0.0.1:{args.port}/session")
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
