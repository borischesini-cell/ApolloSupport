# -*- coding: utf-8 -*-
"""Prueba local offline PWA en localhost:8087"""
import re
import sys
import urllib.request

BASE = "http://localhost:8087"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=5) as r:
        return r.read().decode("utf-8", "replace"), r.status


def main():
    try:
        ping, st = get("/api/ping")
        print(f"GET /api/ping -> {st}: {ping[:120]}")
    except Exception as e:
        print(f"FAIL /api/ping: {e}")
        return 1

    sw, st = get("/sw.js")
    m = re.search(r"CACHE_NAME = '([^']+)'", sw)
    print(f"GET /sw.js -> {st}, len={len(sw)}, CACHE_NAME={m.group(1) if m else '?'}")
    print(f"  isBadNavResponse: {'yes' if 'isBadNavResponse' in sw else 'NO'}")
    print(f"  pwa-boot BOOT_URL: {'yes' if 'pwa-boot.html' in sw else 'NO'}")

    html, st = get("/")
    for pat, label in [
        (r"PWA_BUILD='([^']+)'", "PWA_BUILD"),
        (r"SW_CACHE='([^']+)'", "SW_CACHE"),
        (r"ui-shell-offline", "shell indicator"),
        (r"forceShellSave", "forceShellSave"),
    ]:
        if pat.startswith("ui") or pat.startswith("force"):
            print(f"  {label}: {'yes' if re.search(pat, html) else 'NO'}")
        else:
            m2 = re.search(pat, html)
            print(f"  {label}: {m2.group(1) if m2 else '?'}")

    boot, st = get("/pwa-boot.html")
    print(f"GET /pwa-boot.html -> {st}, shellFromCache: {'yes' if 'shellFromCache' in boot else 'NO'}")

    manifest, st = get("/manifest.json")
    print(f"GET /manifest.json -> {st}: {manifest[:100]}")

    # Coherencia SW vs app
    sw_cache = re.search(r"CACHE_NAME = '([^']+)'", sw)
    app_cache = re.search(r"SW_CACHE='([^']+)'", html)
    if sw_cache and app_cache and sw_cache.group(1) == app_cache.group(1):
        print("OK: SW y app usan el mismo cache")
    else:
        print(f"ERROR: cache mismatch SW={sw_cache.group(1) if sw_cache else '?'} app={app_cache.group(1) if app_cache else '?'}")
        return 2

    if sw_cache.group(1) != "gespresale-cache-v25":
        print(f"WARN: esperaba gespresale-cache-v25, hay {sw_cache.group(1)} (recompilar exe?)")
        return 3

    print("OK: servidor local sirve build offline v25")
    return 0


if __name__ == "__main__":
    sys.exit(main())
