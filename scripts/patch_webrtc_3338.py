"""Patch 3.3.8 WebRTC: centinela.py (bytes, CRLF) - version bump + log_fn en call site."""
import ast
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "agent" / "centinela.py"
STAMP = "20261005"

REPLACEMENTS = [
    (
        b'CLIENT_VERSION = "3.3.37"',
        b'CLIENT_VERSION = "3.3.38"',
        1,
    ),
    (
        b"asyncio.create_task(handle_webrtc_message(data, _rtc_emit))",
        b"asyncio.create_task(handle_webrtc_message(data, _rtc_emit, emit_bitacora_log))",
        1,
    ),
]


def main() -> int:
    data = TARGET.read_bytes()
    original = data

    for old, new, expected in REPLACEMENTS:
        count = data.count(old)
        assert count == expected, f"ancla no unica ({count} != {expected}): {old[:60]!r}"
        data = data.replace(old, new)

    assert data != original, "sin cambios"
    # AST verify: el archivo sigue parseando
    ast.parse(data.decode("utf-8"))

    backup = TARGET.with_name(TARGET.name + f".bak_C_webrtc338_{STAMP}")
    if not backup.exists():
        shutil.copy2(TARGET, backup)
        print(f"[OK] backup: {backup.name}")
    TARGET.write_bytes(data)
    print(f"[OK] patch aplicado: {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
