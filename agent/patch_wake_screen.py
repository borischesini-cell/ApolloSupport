"""
Patch centinela.py para agregar _wake_screen_and_restore_windows() y el handler 'wake_screen'.
"""
import os

TARGET = r"p:\ApolloSupport\agent\centinela.py"

with open(TARGET, "r", encoding="utf-8") as f:
    src = f.read()

# ─── 1. Definir _wake_screen_and_restore_windows() ───────────────────────────
ANCHOR_1 = "def _panic_release():"
INJECT_1 = """\
def _wake_screen_and_restore_windows():
    \"\"\"Restaura ventanas minimizadas en Windows y despierta el motor de renderizado
    de pantalla (DWM/GDI) para evitar que la captura quede en negro si la ventana
    o la sesion de Windows estan minimizadas.
    \"\"\"
    try:
        import ctypes
        u32 = ctypes.windll.user32
        KEYEVENTF_KEYUP = 0x0002
        VK_SHIFT = 0x10
        VK_LWIN = 0x5B
        VK_M = 0x4D
        SW_RESTORE = 9

        # 1. Enviar Win + Shift + M para des-minimizar todas las ventanas
        u32.keybd_event(VK_LWIN, 0, 0, 0)
        u32.keybd_event(VK_SHIFT, 0, 0, 0)
        u32.keybd_event(VK_M, 0, 0, 0)
        u32.keybd_event(VK_M, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
        u32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)

        # 2. Enumerar ventanas minimizadas e intentar restaurarlas
        def _enum_cb(hwnd, lparam):
            try:
                if u32.IsWindowVisible(hwnd) and u32.IsIconic(hwnd):
                    u32.ShowWindow(hwnd, SW_RESTORE)
            except Exception:
                pass
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        enum_proc = WNDENUMPROC(_enum_cb)
        u32.EnumWindows(enum_proc, 0)

        # 3. Enviar evento de tecla inocuo (Shift UP) para despertar renderizado de pantalla DWM
        u32.keybd_event(VK_SHIFT, 0, 0, 0)
        u32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)

        global FORCE_NEXT_FRAME
        FORCE_NEXT_FRAME = True

        logger.info("[DESKTOP] _wake_screen_and_restore_windows: Pantalla despertada y ventanas restauradas")
    except Exception as e:
        logger.warning("[DESKTOP] _wake_screen_and_restore_windows error: %s", e)


"""

if "_wake_screen_and_restore_windows" not in src:
    src = src.replace(ANCHOR_1, INJECT_1 + ANCHOR_1, 1)
    print("[OK] Paso 1: _wake_screen_and_restore_windows() definida")
else:
    print("[--] Paso 1: _wake_screen_and_restore_windows() ya existia")

# ─── 2. Agregar handler del comando 'wake_screen' / 'restore_windows' ────────
ANCHOR_2 = '                            elif data.get("type") == "refresh_frame":'
INJECT_2 = """\
                            elif data.get("type") in ("wake_screen", "restore_windows"):
                                logger.info("[COMMAND] Peticion para restaurar/despertar pantalla minimizada")
                                _wake_screen_and_restore_windows()
                                _panic_release()
                                global FORCE_NEXT_FRAME
                                FORCE_NEXT_FRAME = True
                                try:
                                    await websocket.send(json.dumps({"type": "screen_woken", "success": True}))
                                except Exception:
                                    pass

"""

if '"wake_screen"' not in src:
    if ANCHOR_2 in src:
        src = src.replace(ANCHOR_2, INJECT_2 + ANCHOR_2, 1)
        print("[OK] Paso 2: Handler WS wake_screen agregado")
    else:
        print("[!!] Paso 2: No se encontro ANCHOR_2 en centinela.py")
else:
    print("[--] Paso 2: Handler WS wake_screen ya existia")

with open(TARGET, "w", encoding="utf-8") as f:
    f.write(src)

print("Patch wake_screen finalizado correctamente.")
