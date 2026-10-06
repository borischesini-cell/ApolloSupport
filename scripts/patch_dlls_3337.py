# -*- coding: utf-8 -*-
"""Patch 3.3.37: separar DLLs de VC++ Runtime por arquitectura.

Bug 3.3.36: ApolloSetup_x86.iss copiaba dlls\\vcruntime140.dll y msvcp140.dll
(x64, 0x8664) al {app} de PCs de 32 bits -> "Imagen incorrecta" al arrancar
ApolloCentinela.exe (Windows resuelve DLLs primero en la carpeta del exe).

Fix:
- dlls\\x64\\  <- las 3 DLLs x64 actuales (vcruntime140, vcruntime140_1, msvcp140)
- dlls\\x86\\  <- vcruntime140.dll + msvcp140.dll tomadas de SysWOW64 (0x14c)
- x64.iss apunta a dlls\\x64\\..., x86.iss apunta a dlls\\x86\\...
- Bump a 3.3.37 en centinela.py, centinela_svc.py y los 3 .iss

Backups: <archivo>.bak_C_dlls337_20261005 (C = letra de unidad del repo local).
"""
import ast
import os
import shutil
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = os.path.join(ROOT, "agent")
DLLS = os.path.join(AGENT, "installer", "dlls")
SYSWOW64 = r"C:\Windows\SysWOW64"
BAK = ".bak_C_dlls337_20261005"
OLD_VER = b'"3.3.36"'
NEW_VER = b'"3.3.37"'


def pe_machine(p):
    with open(p, "rb") as f:
        d = f.read(0x800)
    assert d[:2] == b"MZ", "no es PE: %s" % p
    pe = struct.unpack_from("<I", d, 0x3C)[0]
    assert d[pe:pe + 4] == b"PE\0\0", "no es PE: %s" % p
    return struct.unpack_from("<H", d, pe + 4)[0]


def backup(p):
    b = p + BAK
    if not os.path.exists(b):
        shutil.copy2(p, b)
    return b


def patch_bytes(path, replacements, must_counts):
    with open(path, "rb") as f:
        data = f.read()
    backup(path)
    for old, new in replacements:
        n = data.count(old)
        assert n == must_counts[old], "%s: %r aparece %d veces (esperado %d)" % (
            path, old, n, must_counts[old])
        data = data.replace(old, new)
    with open(path, "wb") as f:
        f.write(data)
    return data


def main():
    # --- 1. Reordenar DLLs ---
    x64_dir = os.path.join(DLLS, "x64")
    x86_dir = os.path.join(DLLS, "x86")
    os.makedirs(x64_dir, exist_ok=True)
    os.makedirs(x86_dir, exist_ok=True)
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
        src = os.path.join(DLLS, name)
        dst = os.path.join(x64_dir, name)
        assert os.path.exists(src), "falta %s" % src
        if not os.path.exists(dst):
            shutil.move(src, dst)
    for name in ("vcruntime140.dll", "msvcp140.dll"):
        src = os.path.join(SYSWOW64, name)
        dst = os.path.join(x86_dir, name)
        assert os.path.exists(src), "falta %s (necesitas el VC++ redist x86)" % src
        if not os.path.exists(dst):
            shutil.copy2(src, dst)
    # Asertos de arquitectura
    for name in ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll"):
        assert pe_machine(os.path.join(x64_dir, name)) == 0x8664, "%s no es x64" % name
    for name in ("vcruntime140.dll", "msvcp140.dll"):
        assert pe_machine(os.path.join(x86_dir, name)) == 0x14C, "%s no es x86" % name

    # --- 2. Patches .iss ---
    iss_dir = os.path.join(AGENT, "installer")
    patch_bytes(
        os.path.join(iss_dir, "ApolloSetup_x64.iss"),
        [
            (b'Source: "dlls\\vcruntime140.dll";',   b'Source: "dlls\\x64\\vcruntime140.dll";'),
            (b'Source: "dlls\\vcruntime140_1.dll";', b'Source: "dlls\\x64\\vcruntime140_1.dll";'),
            (b'Source: "dlls\\msvcp140.dll";',       b'Source: "dlls\\x64\\msvcp140.dll";'),
            (b'#define MyAppVersion   "3.3.36"',     b'#define MyAppVersion   "3.3.37"'),
        ],
        {
            b'Source: "dlls\\vcruntime140.dll";':   1,
            b'Source: "dlls\\vcruntime140_1.dll";': 1,
            b'Source: "dlls\\msvcp140.dll";':       1,
            b'#define MyAppVersion   "3.3.36"':     1,
        },
    )
    patch_bytes(
        os.path.join(iss_dir, "ApolloSetup_x86.iss"),
        [
            (b'Source: "dlls\\vcruntime140.dll";', b'Source: "dlls\\x86\\vcruntime140.dll";'),
            (b'Source: "dlls\\msvcp140.dll";',     b'Source: "dlls\\x86\\msvcp140.dll";'),
            (b'#define MyAppVersion   "3.3.36"',   b'#define MyAppVersion   "3.3.37"'),
        ],
        {
            b'Source: "dlls\\vcruntime140.dll";': 1,
            b'Source: "dlls\\msvcp140.dll";':     1,
            b'#define MyAppVersion   "3.3.36"':   1,
        },
    )
    patch_bytes(
        os.path.join(iss_dir, "ApolloSetup.iss"),
        [
            (b'#define MyAppVersion   "3.3.36"', b'#define MyAppVersion   "3.3.37"'),
        ],
        {b'#define MyAppVersion   "3.3.36"': 1},
    )

    # --- 3. Bump de version en los .py (bytes, CRLF-safe) ---
    for rel, old, new in (
        ("centinela.py", b'CLIENT_VERSION = "3.3.36"', b'CLIENT_VERSION = "3.3.37"'),
        ("centinela_svc.py", b'__version__     = "3.3.36"', b'__version__     = "3.3.37"'),
    ):
        p = os.path.join(AGENT, rel)
        patch_bytes(p, [(old, new)], {old: 1})

    # --- 4. AST verify de los .py ---
    for rel in ("centinela.py", "centinela_svc.py"):
        p = os.path.join(AGENT, rel)
        with open(p, "rb") as f:
            tree = ast.parse(f.read())
        vers = {
            getattr(node, "id", getattr(node, "arg", None))
            for node in ast.walk(tree)
        }
        assert tree is not None
        print("AST OK:", rel)

    print("PATCH 3.3.37 OK")
    print("  dlls\\x64:", sorted(os.listdir(x64_dir)))
    print("  dlls\\x86:", sorted(os.listdir(x86_dir)))


if __name__ == "__main__":
    sys.exit(main())
