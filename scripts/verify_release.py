#!/usr/bin/env python3
"""
Verificaciones pre-deploy de ApolloSupport (control remoto).
Ejecutar desde la raíz del repo: python scripts/verify_release.py
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERRORS: list[str] = []
WARNINGS: list[str] = []


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def fail(msg: str) -> None:
    ERRORS.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg: str) -> None:
    WARNINGS.append(msg)
    print(f"  WARN  {msg}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def check_syntax_py(path: Path) -> None:
    try:
        ast.parse(read_text(path), filename=str(path))
        ok(f"sintaxis Python: {path.relative_to(ROOT)}")
    except SyntaxError as e:
        fail(f"sintaxis {path}: {e}")


def check_versions_aligned() -> None:
    expected = None
    m = re.search(r'CLIENT_VERSION\s*=\s*"([\d.]+)"', read_text(ROOT / "agent" / "centinela.py"))
    if m:
        expected = m.group(1)
    else:
        fail("no se encontró CLIENT_VERSION en agent/centinela.py")
        return

    files = {
        "agent/centinela_svc.py": r'__version__\s*=\s*"([\d.]+)"',
        "frontend/package.json": r'"version":\s*"([\d.]+)"',
        "frontend/src/version.ts": r"APP_VERSION\s*=\s*'([\d.]+)'",
        "backend/updates/version.json": r'"version":\s*"([\d.]+)"',
    }
    for rel, pat in files.items():
        p = ROOT / rel.replace("/", "\\") if False else ROOT / rel
        text = read_text(p)
        mm = re.search(pat, text)
        if not mm:
            fail(f"versión no encontrada en {rel}")
        elif mm.group(1) != expected:
            fail(f"{rel} tiene {mm.group(1)}, esperado {expected}")
        else:
            ok(f"versión {expected} en {rel}")


def check_agent_flags() -> None:
    text = read_text(ROOT / "agent" / "centinela.py")
    if "USE_DIRTY_RECT     = True" in text:
        fail("USE_DIRTY_RECT=True — riesgo de cuadraditos en el visor")
    elif "USE_DIRTY_RECT     = False" in text:
        ok("USE_DIRTY_RECT=False")
    else:
        warn("USE_DIRTY_RECT no reconocido")

    if re.search(r"if HQ_MODE_ACTIVE:\s*\n\s*await asyncio\.sleep.*\n\s*continue", text):
        fail("video loop hace continue con HQ_MODE_ACTIVE — pantalla negra si H.264 falla")
    else:
        ok("video loop no corta WebP solo por HQ_MODE_ACTIVE")

    if "FORCE_NEXT_FRAME" in text and "if FORCE_NEXT_FRAME:" in text:
        ok("FORCE_NEXT_FRAME en captura")
    else:
        warn("revisar FORCE_NEXT_FRAME en captura")


def check_service_session_guards() -> None:
    text = read_text(ROOT / "agent" / "centinela_svc.py")
    for needle in (
        "def normalize_windows_session_id",
        "WTSQueryUserToken.argtypes",
        "session_suitable_for_companion",
        "no apta (desconectada",
    ):
        if needle in text:
            ok(f"centinela_svc: {needle[:40]}...")
        else:
            fail(f"falta en centinela_svc: {needle}")


def check_frontend_hq() -> None:
    text = read_text(ROOT / "frontend" / "src" / "App.tsx")
    if "remoteCanvasBaseReadyRef" in text:
        ok("canvas base para deltas")
    else:
        warn("sin remoteCanvasBaseReadyRef")

    if "5000)" in text and "Sin video HD en 5" in text or "Sin video HD en" in text:
        ok("fallback HD configurado")
    elif "12000)" in text and "fallback" in text.lower():
        warn("fallback HD aún en 12s — considerar 5s")
    else:
        warn("revisar timeout fallback HD")

    if 'includes(\'disc\')' in text or 'includes("disc")' in text:
        ok("bloqueo UI sesiones Disc")
    else:
        warn("sin bloqueo explícito de sesiones Disc en UI")


def check_dangerous_patches() -> None:
    patch = ROOT / "patch.py"
    if patch.exists() and "USE_DIRTY_RECT     = True" in read_text(patch):
        warn("patch.py reactiva USE_DIRTY_RECT — no ejecutar en producción")


def check_dist_exists() -> None:
    dist = ROOT / "frontend" / "dist" / "index.html"
    if dist.exists():
        ok("frontend/dist/index.html presente")
    else:
        warn("ejecutar build_frontend.bat antes de subir el portal")


def check_remote_input_guards() -> None:
    text = read_text(ROOT / "agent" / "centinela.py")
    for needle in ("def _send_unicode_text", "GENERIC_ALL", "_EXTENDED_VKS"):
        if needle in text:
            ok(f"input agent: {needle}")
        else:
            fail(f"falta input agent: {needle}")

    main_txt = read_text(ROOT / "backend" / "main.py")
    if "input_types" in main_txt and "write_locks[device_id]" in main_txt:
        ok("send_json_to_device usa lock + input_types")
    else:
        fail("send_json_to_device sin lock/input_types")

    fe = read_text(ROOT / "frontend" / "src" / "App.tsx")
    if "stealRemoteKeyboardFocus" in fe:
        ok("frontend stealRemoteKeyboardFocus")
    else:
        fail("falta stealRemoteKeyboardFocus en App.tsx")


def main() -> int:
    print("ApolloSupport — verify_release\n")
    print("[Python agente]")
    check_syntax_py(ROOT / "agent" / "centinela.py")
    check_syntax_py(ROOT / "agent" / "centinela_svc.py")

    print("\n[Versiones]")
    check_versions_aligned()

    print("\n[Flags críticos]")
    check_agent_flags()
    check_service_session_guards()
    check_frontend_hq()
    check_dangerous_patches()
    check_remote_input_guards()

    print("\n[Build]")
    check_dist_exists()

    print("\n--- Resumen ---")
    print(f"Errores: {len(ERRORS)} | Advertencias: {len(WARNINGS)}")
    for e in ERRORS:
        print(f"  - {e}")
    return 1 if ERRORS else 0


if __name__ == "__main__":
    sys.exit(main())
