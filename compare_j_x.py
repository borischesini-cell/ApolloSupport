# -*- coding: utf-8 -*-
import re
import base64
from pathlib import Path


def emb_cache(htmlapp):
    t = htmlapp.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"Function SwJsEmbedded\(\).*?Return hb_base64Decode", t, re.S)
    if not m:
        return "?"
    chunks = re.findall(r'cBase64 \+= "([^"]+)"', m.group(0))
    data = base64.b64decode("".join(chunks[:2])).decode("utf-8", "replace")
    cm = re.search(r"CACHE_NAME = '([^']+)'", data)
    return cm.group(1) if cm else "?"


def grep_val(text, pat):
    m = re.search(pat, text)
    return m.group(1) if m else "?"


for label, root in [("J (andaba)", Path("J:/WEB_PRESALE")), ("X (actual)", Path("X:/WEB_PRESALE"))]:
    ha = root / "Source/HtmlApp.prg"
    sw = root / "Source/sw_presale.js"
    dm = root / "Source/Daemon.prg"
    ht = ha.read_text(encoding="utf-8", errors="replace")
    st = sw.read_text(encoding="utf-8", errors="replace")
    dt = dm.read_text(encoding="utf-8", errors="replace")
    print(f"\n=== {label} ===")
    print("  embedded SW cache:", emb_cache(ha))
    print("  app SW_CACHE:    ", grep_val(ht, r"SW_CACHE='([^']+)'"))
    print("  sw_presale.js:   ", grep_val(st, r"CACHE_NAME = '([^']+)'"))
    print("  PWA_BUILD:       ", grep_val(ht, r"PWA_BUILD='([^']+)'"))
    print("  updateViaCache:  ", "none" if "updateViaCache:'none'" in ht else "imports")
    print("  pwa-boot route:  ", "ServePwaBootHtml" in dt and 'ElseIf cPath == "/pwa-boot.html"' in dt)
    if 'max-age=31536000' in dt and "pwa-boot" in dt:
        print("  boot cache hdr:  immutable 1y (J style)")
    elif "pwa-boot" in dt:
        print("  boot cache hdr:  no-store (X style)")
    print("  SHELL_MAX_AGE:   ", "yes" if "SHELL_MAX_AGE" in st else "no")
    print("  shell offline UI:", "ui-shell-offline" in ht)
