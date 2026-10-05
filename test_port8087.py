# -*- coding: utf-8 -*-
"""Simula servidor caido y prueba si localhost responde."""
import socket
import sys
import urllib.error
import urllib.request

HOST, PORT = "127.0.0.1", 8087


def port_open():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1)
    try:
        s.connect((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def fetch(path):
    try:
        with urllib.request.urlopen(f"http://{HOST}:{PORT}{path}", timeout=3) as r:
            return r.status, r.read(200)
    except urllib.error.URLError as e:
        return None, str(e).encode()


def main():
    print("port open:", port_open())
    st, body = fetch("/")
    print("GET / before:", st, body[:80] if st else body.decode(errors="replace"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
