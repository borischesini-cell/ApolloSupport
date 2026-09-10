#!/usr/bin/env python3
"""
Pruebas internas de control remoto (teclado/mouse routing + inyección).
No habla con prod. Ejecutar desde la raíz:

  python scripts/test_remote_control.py
"""
from __future__ import annotations

import ast
import asyncio
import ctypes
import re
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
PASSED = 0
FAILED = 0


def ok(msg: str) -> None:
    global PASSED
    PASSED += 1
    print(f"  PASS  {msg}")


def fail(msg: str, exc: BaseException | None = None) -> None:
    global FAILED
    FAILED += 1
    print(f"  FAIL  {msg}")
    if exc:
        traceback.print_exception(type(exc), exc, exc.__traceback__)


class FakeWS:
    def __init__(self, name: str):
        self.name = name
        self.sent: List[Any] = []

    async def send_json(self, data):
        self.sent.append(data)


def _extract_async_method(py_path: Path, class_name: str, method_name: str):
    tree = ast.parse(py_path.read_text(encoding="utf-8", errors="replace"))
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for item in node.body:
                if isinstance(item, ast.AsyncFunctionDef) and item.name == method_name:
                    return item
    raise RuntimeError(f"No se encontró {class_name}.{method_name} en {py_path}")


def build_connection_manager_stub():
    """Carga ConnectionManager.send_json_to_device real sin importar FastAPI/DB."""
    method_ast = _extract_async_method(
        ROOT / "backend" / "main.py", "ConnectionManager", "send_json_to_device"
    )
    class_ast = ast.Module(
        body=[
            ast.ClassDef(
                name="ConnectionManagerStub",
                bases=[],
                keywords=[],
                body=[
                    ast.FunctionDef(
                        name="__init__",
                        args=ast.arguments(
                            posonlyargs=[],
                            args=[ast.arg(arg="self")],
                            kwonlyargs=[],
                            kw_defaults=[],
                            defaults=[],
                        ),
                        body=[
                            ast.parse("self.write_locks = {}").body[0],
                            ast.parse("self.device_sessions = {}").body[0],
                            ast.parse("self.selected_sessions = {}").body[0],
                            ast.parse("self.active_connections = {}").body[0],
                        ],
                        decorator_list=[],
                    ),
                    method_ast,
                ],
                decorator_list=[],
            )
        ],
        type_ignores=[],
    )
    ast.fix_missing_locations(class_ast)
    ns: dict = {"asyncio": asyncio}
    exec(compile(class_ast, str(ROOT / "backend" / "main.py"), "exec"), ns)
    return ns["ConnectionManagerStub"]()


async def test_send_json_routing():
    print("\n[Backend] send_json_to_device routing")
    try:
        mgr = build_connection_manager_stub()
    except Exception as e:
        fail("no se pudo extraer send_json_to_device", e)
        return

    companion = FakeWS("companion_sess1")
    other = FakeWS("other_sess2")
    headless = FakeWS("headless")

    device_id = 811
    mgr.device_sessions[device_id] = {1: companion, 2: other}
    mgr.selected_sessions[device_id] = 1
    mgr.active_connections[device_id] = headless

    # Input debe ir SOLO a la sesión seleccionada (no a other ni headless)
    ok_sent = await mgr.send_json_to_device(device_id, {"type": "key_press", "key": "enter"})
    if ok_sent and companion.sent and not other.sent and not headless.sent:
        ok("key_press -> solo sesión seleccionada")
    else:
        fail(
            f"key_press routing malo: companion={companion.sent} other={other.sent} headless={headless.sent}"
        )

    companion.sent.clear()
    other.sent.clear()
    headless.sent.clear()

    ok_sent = await mgr.send_json_to_device(
        device_id, {"type": "write_text", "text": "hola"}
    )
    if ok_sent and companion.sent == [{"type": "write_text", "text": "hola"}] and not other.sent:
        ok("write_text -> sesión seleccionada")
    else:
        fail(f"write_text routing: {companion.sent}")

    companion.sent.clear()
    other.sent.clear()

    # Comando no-input: broadcast a todas las sesiones en device_sessions
    ok_sent = await mgr.send_json_to_device(device_id, {"type": "get_sessions"})
    if ok_sent and len(companion.sent) == 1 and len(other.sent) == 1:
        ok("get_sessions -> broadcast a device_sessions")
    else:
        fail(f"broadcast: companion={companion.sent} other={other.sent}")

    # Sin selected: fallback active_connections
    mgr2 = build_connection_manager_stub()
    only = FakeWS("only_active")
    mgr2.active_connections[99] = only
    ok_sent = await mgr2.send_json_to_device(99, {"type": "mouse_down", "x": 0.5, "y": 0.5})
    if ok_sent and only.sent:
        ok("mouse_down fallback a active_connections")
    else:
        fail("fallback active_connections falló")

    # Write lock: dos envíos secuenciales no deben cruzarse (smoke)
    mgr3 = build_connection_manager_stub()
    ws = FakeWS("locked")
    mgr3.device_sessions[1] = {5: ws}
    mgr3.selected_sessions[1] = 5

    async def burst():
        await asyncio.gather(
            *[
                mgr3.send_json_to_device(1, {"type": "key_press", "key": str(i)})
                for i in range(20)
            ]
        )

    await burst()
    if len(ws.sent) == 20:
        ok("write_lock + 20 key_press concurrentes entregados")
    else:
        fail(f"esperaba 20 mensajes, got {len(ws.sent)}")


def test_agent_source_contracts():
    print("\n[Agente] contratos de código")
    text = (ROOT / "agent" / "centinela.py").read_text(encoding="utf-8", errors="replace")
    checks = [
        ("def _attach_input_desktop", "attach input desktop"),
        ("GENERIC_ALL", "OpenInputDesktop GENERIC_ALL"),
        ("def _send_unicode_text", "unicode text helper"),
        ("KEYEVENTF_UNICODE", "unicode SendInput flag"),
        ("_EXTENDED_VKS", "extended VK set"),
        ("_attach_input_desktop()", "attach llamado en handlers"),
        ('"key_press"', "handler key_press"),
        ('"key_down"', "handler key_down"),
        ('"write_text"', "handler write_text"),
    ]
    for needle, label in checks:
        if needle in text:
            ok(label)
        else:
            fail(f"falta en centinela.py: {label} ({needle})")

    svc = (ROOT / "agent" / "centinela_svc.py").read_text(encoding="utf-8", errors="replace")
    if "def kill_companions_outside_session" in svc and "kill_companions_outside_session(target_sess" in svc:
        ok("servicio mata companions de otras sesiones")
    else:
        fail("falta kill_companions_outside_session en monitor")


def test_injection_helpers_mocked():
    """Ejecuta helpers de inyección con user32 mockeado (sin teclear en el IDE)."""
    print("\n[Agente] inyección mockeada")
    src = (ROOT / "agent" / "centinela.py").read_text(encoding="utf-8", errors="replace")

    # Extraer bloque de estructuras + helpers entre class _KEYBDINPUT y enable_sas_policy
    m = re.search(
        r"(class _KEYBDINPUT\(ctypes\.Structure\):.*?)\ndef enable_sas_policy\(",
        src,
        re.S,
    )
    if not m:
        fail("no se pudo extraer bloque INPUT helpers de centinela.py")
        return

    # Quitar la segunda def _hotkey duplicada del inicio del archivo: el bloque ya trae _hotkey
    block = m.group(1)
    import ctypes.wintypes  # noqa: F401 — requerido por las structs del agente
    ns: dict = {"ctypes": ctypes}
    try:
        exec(compile(block, "centinela_input_helpers.py", "exec"), ns)
    except Exception as e:
        fail("exec helpers de inyección", e)
        return

    for name in ("_attach_input_desktop", "_send_key", "_send_unicode_text", "_hotkey"):
        if name not in ns:
            fail(f"helper no definido: {name}")
            return

    calls = {"keybd_event": [], "SendInput": [], "OpenInputDesktop": [], "SetThreadDesktop": []}

    class FakeUser32:
        def OpenInputDesktop(self, *a, **k):
            calls["OpenInputDesktop"].append(a)
            return 12345

        def SetThreadDesktop(self, h):
            calls["SetThreadDesktop"].append(h)
            return 1

        def CloseDesktop(self, h):
            return 1

        def MapVirtualKeyW(self, vk, mode):
            return 0x1C if vk == 0x0D else (vk & 0xFF)

        def keybd_event(self, vk, scan, flags, extra):
            calls["keybd_event"].append((vk, flags))

        def SendInput(self, n, ref, size):
            calls["SendInput"].append(n)
            return n

    fake = FakeUser32()
    with patch.object(ctypes, "windll", SimpleNamespace(user32=fake)):
        attached = ns["_attach_input_desktop"]()
        if attached and calls["OpenInputDesktop"] and calls["SetThreadDesktop"]:
            ok("_attach_input_desktop abre desktop y SetThreadDesktop")
        else:
            fail(f"attach falló: {calls}")

        calls["keybd_event"].clear()
        ns["_send_key"](0x0D, up=False)  # Enter down
        ns["_send_key"](0x0D, up=True)
        if len(calls["keybd_event"]) >= 2:
            ok("_send_key usa keybd_event down+up")
        else:
            fail(f"_send_key no llamó keybd_event: {calls['keybd_event']}")

        calls["SendInput"].clear()
        ns["_send_unicode_text"]("ab")
        # 2 chars * (down+up) = 4 SendInput
        if len(calls["SendInput"]) >= 4:
            ok("_send_unicode_text emite SendInput por carácter")
        else:
            fail(f"unicode SendInput count={len(calls['SendInput'])}")

        calls["keybd_event"].clear()
        ns["_hotkey"](0x11, 0x56)  # Ctrl+V
        if len(calls["keybd_event"]) >= 4:
            ok("_hotkey Ctrl+V = 4 edges")
        else:
            fail(f"_hotkey edges={calls['keybd_event']}")


def test_frontend_focus_contract():
    print("\n[Frontend] foco teclado remoto")
    text = (ROOT / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8", errors="replace")
    if "stealRemoteKeyboardFocus" in text and "active.blur()" in text:
        ok("stealRemoteKeyboardFocus definido y hace blur")
    else:
        fail("falta stealRemoteKeyboardFocus / blur")

    if "stealRemoteKeyboardFocus(e.currentTarget)" in text:
        ok("handleMouseDown llama stealRemoteKeyboardFocus")
    else:
        fail("handleMouseDown no roba foco")

    # canvas/video/img focusables
    if text.count("tabIndex={0}") >= 2:
        ok("elementos del visor con tabIndex=0")
    else:
        fail("pocos tabIndex=0 en visor")

    # Guardia INPUT sigue existiendo (TECLADO no debe spamear key_down)
    if "activeEl.tagName === 'INPUT'" in text:
        ok("keydown ignora INPUT/TEXTAREA (campo TECLADO)")
    else:
        fail("falta guardia INPUT en keydown")


def test_syntax():
    print("\n[Sintaxis]")
    for rel in (
        "agent/centinela.py",
        "agent/centinela_svc.py",
        "backend/main.py",
    ):
        path = ROOT / rel
        try:
            ast.parse(path.read_text(encoding="utf-8", errors="replace"))
            ok(rel)
        except SyntaxError as e:
            fail(f"sintaxis {rel}", e)


def main() -> int:
    print("ApolloSupport — test_remote_control (offline)\n")
    test_syntax()
    test_agent_source_contracts()
    test_frontend_focus_contract()
    test_injection_helpers_mocked()
    asyncio.run(test_send_json_routing())

    print("\n--- Resumen ---")
    print(f"PASS: {PASSED}  FAIL: {FAILED}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
