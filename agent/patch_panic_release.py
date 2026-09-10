"""
Patch centinela.py para agregar _panic_release():
  1. Define la función después de _hotkey()
  2. La llama al unirse el técnico (technician_joined)
  3. La llama al desconectarse el WS (finally del loop principal)
"""
import sys

TARGET = r"p:\ApolloSupport\agent\centinela.py"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

# ─── 1. Insertar _panic_release() justo después de _hotkey() ──────────────────
ANCHOR_1 = "def _set_clipboard_win32(text: str):"
INJECT_1 = """\
def _panic_release():
    \"\"\"Libera todos los modificadores de teclado y botones de mouse que puedan
    haber quedado presionados virtualmente tras un corte de conexion.
    Se llama al conectar/desconectar un tecnico para evitar que el equipo del
    cliente quede con Ctrl/Shift/Alt o un boton del mouse 'trabado'.
    \"\"\"
    try:
        import ctypes, pyautogui
        ku = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        # Shift, Ctrl, Alt, WinLeft, WinRight
        for vk in [0x10, 0x11, 0x12, 0x5B, 0x5C]:
            try:
                ku.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
            except Exception:
                pass
        # Soltar botones del mouse
        for btn in ('left', 'right'):
            try:
                pyautogui.mouseUp(button=btn)
            except Exception:
                pass
        logger.info("[INPUT] panic_release: modificadores y botones liberados")
    except Exception as e:
        logger.warning("[INPUT] panic_release error: %s", e)


"""

if "_panic_release" not in src:
    src = src.replace(ANCHOR_1, INJECT_1 + ANCHOR_1, 1)
    print("[OK] Paso 1: _panic_release() definida")
else:
    print("[--] Paso 1: _panic_release() ya existia, sin cambios")

# ─── 2. Llamar _panic_release() al unirse el técnico ─────────────────────────
ANCHOR_2 = '                            elif data.get("type") == "technician_joined":\n                                name = data.get("name")\n                                HAS_ACTIVE_VIEWER = True\n                                global FORCE_NEXT_FRAME\n                                FORCE_NEXT_FRAME = True  # Forzar frame fresco al conectar/reconectar viewer'

REPLACE_2 = '                            elif data.get("type") == "technician_joined":\n                                name = data.get("name")\n                                HAS_ACTIVE_VIEWER = True\n                                global FORCE_NEXT_FRAME\n                                FORCE_NEXT_FRAME = True  # Forzar frame fresco al conectar/reconectar viewer\n                                _panic_release()  # Liberar cualquier tecla/boton atascado de sesion anterior'

if "_panic_release()  # Liberar cualquier tecla" not in src:
    if ANCHOR_2 in src:
        src = src.replace(ANCHOR_2, REPLACE_2, 1)
        print("[OK] Paso 2: _panic_release() llamada en technician_joined")
    else:
        print("[!!] Paso 2: No se encontro el ancla de technician_joined - revisar manualmente")
else:
    print("[--] Paso 2: llamada ya existia, sin cambios")

# ─── 3. Llamar _panic_release() en el finally del WS (al desconectarse) ───────
ANCHOR_3 = "                finally:\n                    ACTIVE_WEBSOCKET = None\n                    HAS_ACTIVE_VIEWER = False\n                    telemetry_task.cancel()\n                    video_task.cancel()"

REPLACE_3 = "                finally:\n                    _panic_release()  # Liberar teclas/mouse al desconectarse el tecnico\n                    ACTIVE_WEBSOCKET = None\n                    HAS_ACTIVE_VIEWER = False\n                    telemetry_task.cancel()\n                    video_task.cancel()"

if "_panic_release()  # Liberar teclas/mouse al desconectarse" not in src:
    if ANCHOR_3 in src:
        src = src.replace(ANCHOR_3, REPLACE_3, 1)
        print("[OK] Paso 3: _panic_release() llamada en finally (desconexion WS)")
    else:
        print("[!!] Paso 3: No se encontro el ancla del finally - revisar manualmente")
else:
    print("[--] Paso 3: llamada ya existia, sin cambios")

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print("\nArchivo guardado OK.")
