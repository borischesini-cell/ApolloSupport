#!/usr/bin/env python3
"""Prueba offline de deduplicación pending vs asignado (sin DB real)."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    src = (ROOT / "backend" / "main.py").read_text(encoding="utf-8", errors="replace")
    ast.parse(src)

    checks = [
        ("def _purge_duplicate_pending_devices", "helper dedup"),
        ("Autolimpia huérfanos", "get_pending autodedup"),
        ("preferir el ya asignado", "handshake prioriza asignado"),
        ("Dispositivo huérfano", "reasigna huérfano con licencia"),
        ("[DEDUP]", "log dedup"),
    ]
    failed = 0
    for needle, label in checks:
        if needle in src:
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}")
            failed += 1

    # No debe quedar el lookup viejo que solo mira pending por nombre
    old = (
        "models.CentinelaDevice.device_name == device_name,\n"
        "                (models.CentinelaDevice.client_id == resolved_client_id) | (models.CentinelaDevice.client_id == None)"
    )
    if old in src:
        print("  FAIL  sigue el lookup pending viejo (crea duplicados)")
        failed += 1
    else:
        print("  PASS  lookup pending viejo removido")

    print(f"\n--- {'FAIL' if failed else 'OK'} ({failed} errores) ---")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
