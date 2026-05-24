import asyncio
import websockets
import json
import psutil
import socket
import platform
import threading
import random
import tkinter as tk
import pyautogui
import base64
import io
from PIL import Image
import os
import ctypes
import pystray

# --- HELPERS DE ALTA PRECISIÓN PARA 50 FPS ---
try:
    _winmm = ctypes.windll.winmm
    def _set_high_res_timer(enable: bool):
        """Habilita/deshabilita el timer de 1ms en Windows para FPS estables."""
        if enable: _winmm.timeBeginPeriod(1)
        else: _winmm.timeEndPeriod(1)
except:
    def _set_high_res_timer(enable: bool): pass
# ---------------------------------------------
from pystray import MenuItem as item
import requests
import subprocess
import winreg
import datetime
import time

import logging
import logging.handlers
import mss

# ==============================================================================
# CONFIGURACION Y VERSIONADO
# ==============================================================================
CLIENT_VERSION = "3.1.0"
BUILD_DATE     = "2026-05-15 19:58"  # <--- SE ACTUALIZA MANUALMENTE EN CADA RELEASE
# ==============================================================================

class _CentinelaFilter(logging.Filter):
    """Pasa TODO lo del logger 'centinela'; del resto solo WARNING+.
    Evita que websockets/PIL/asyncio escriban en disco a nivel DEBUG.
    """
    def filter(self, record):
        return record.name == 'centinela' or record.levelno >= logging.WARNING


def _setup_logging():
    log_dir = os.path.join(
        os.environ.get("PROGRAMDATA", os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__)))),
        "ApolloSupport"
    )
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "centinela.log")

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    _f = _CentinelaFilter()

    # RotaciÃ³n diaria, guarda 7 dÃ­as
    fh = logging.handlers.TimedRotatingFileHandler(log_file, when="midnight", backupCount=7, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(_f)

    # Consola (Ãºtil al ejecutar manualmente)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.addFilter(_f)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)  # dejar todo pasar â€” el Filter hace el filtrado real
    root.addHandler(fh)
    root.addHandler(ch)

    return log_file


_LOG_FILE = _setup_logging()
logger = logging.getLogger("centinela")
logger.setLevel(logging.DEBUG)   # el logger propio en DEBUG, root en WARNING silencia el resto
logger.info("=" * 60)
logger.info("Apollo Centinela iniciando - log en: %s", _LOG_FILE)
logger.info("=" * 60)

# ==========================================
# HELPERS DE INPUT WIN32
# Usan keybd_event (API legacy) que funciona desde Session 0 (servicio)
# y puede cruzar de Session 0 â†’ Session 1 (usuario interactivo).
# SendInput NO funciona desde Session 0 por el aislamiento de UIPI.
# ==========================================
def _hotkey(*vk_codes):
    """Presiona y suelta una secuencia de VK codes via keybd_event.
    Ejemplos: _hotkey(0x11, 0x56)  â†’ Ctrl+V
              _hotkey(0x10, 0x25)  â†’ Shift+LeftArrow
    """
    _u32 = ctypes.windll.user32
    KEYEVENTF_KEYUP = 0x0002
    # Press down en orden
    for vk in vk_codes:
        _u32.keybd_event(vk, 0, 0, 0)
    # Release en orden inverso
    for vk in reversed(vk_codes):
        _u32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

def _set_clipboard_win32(text: str):
    """Pone texto en el portapapeles usando OpenClipboard/SetClipboardData.
    No requiere pyperclip ni Tkinter â€” funciona en Session 0 y Session 1.
    """
    _k32 = ctypes.windll.kernel32
    _u32 = ctypes.windll.user32
    CF_UNICODETEXT = 13
    GMEM_MOVEABLE = 0x0002
    text_bytes = text.encode("utf-16-le") + b"\x00\x00"
    h_mem = _k32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
    if not h_mem:
        raise MemoryError("GlobalAlloc fallÃ³")
    ptr = _k32.GlobalLock(h_mem)
    ctypes.memmove(ptr, text_bytes, len(text_bytes))
    _k32.GlobalUnlock(h_mem)
    if _u32.OpenClipboard(None):
        _u32.EmptyClipboard()
        _u32.SetClipboardData(CF_UNICODETEXT, h_mem)
        _u32.CloseClipboard()
    else:
        _k32.GlobalFree(h_mem)
        raise OSError("No se pudo abrir el portapapeles")

# ==========================================
# CONFIGURACIÃ“N Y PERSISTENCIA LOCAL
# ==========================================
SERVICE_NAME = "ApolloCentinela"
SERVICE_DISPLAY = "Apollo Centinela Agent"

# Usar AppData\Roaming para que el servicio (que corre como SYSTEM en Session 0)
# pueda leer/escribir la configuraciÃ³n sin depender del directorio de trabajo
def get_config_path():
    appdata = os.environ.get("PROGRAMDATA", os.environ.get("APPDATA", os.path.dirname(os.path.abspath(__file__))))
    config_dir = os.path.join(appdata, "ApolloSupport")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, "centinela_config.json")

CONFIG_FILE = get_config_path()

def load_local_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except: return None
    return None

def save_local_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# ==========================================
# PUNTEO WEB AL SERVIDOR CENTRAL DE MASTER IS
# ==========================================
# Identificadores Ãšnicos
LOCAL_CFG = load_local_config()
if not LOCAL_CFG:
    # Si es la primera vez, autodetectamos los datos silenciosamente para flujo Hands-Free remoto sin preguntar nada en la PC del cliente
    import socket
    try:
        hostname = socket.gethostname()
    except:
        hostname = "PC-CENTINELA"
    
    dev_name = hostname if hostname else f"PC-{os.getlogin()}"
    
    LOCAL_CFG = {
        "device_name": dev_name, 
        "client_id": random.randint(100000, 999999), 
        "license_key": "", # Inicia vacÃ­o para quedar en espera de asignaciÃ³n remota automÃ¡tica
        "base_ws_url": "wss://support.ultimate.net.ar/api/ws/centinela" # URL por defecto (ProducciÃ³n)
    }
    save_local_config(LOCAL_CFG)

CLIENT_ID = LOCAL_CFG.get("client_id")
DEVICE_NAME = LOCAL_CFG.get("device_name", "Desconocido")
LIC_KEY = LOCAL_CFG.get("license_key", "DEMO-KEY")
BASE_WS_URL = LOCAL_CFG.get("base_ws_url", "wss://support.ultimate.net.ar/api/ws/centinela")

def get_alt_remote_id():
    import os, re
    # Check RustDesk
    dirs = [
        os.path.join(os.environ.get("APPDATA", ""), "RustDesk", "config"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "RustDesk", "config"),
        r"C:\Windows\System32\config\systemprofile\AppData\Roaming\RustDesk\config",
        r"C:\Windows\SysWOW64\config\systemprofile\AppData\Roaming\RustDesk\config"
    ]
    filenames = ["RustDesk.toml", "RustDesk_local.toml", "rustdesk.toml", "RustDesk2.toml"]
    
    rustdesk_paths = []
    for d in dirs:
        for f in filenames:
            rustdesk_paths.append(os.path.join(d, f))
            
    for p in rustdesk_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("id ="):
                            m = re.search(r"id\s*=\s*'([^']+)'", line)
                            if m: return m.group(1)
            except: pass
            
    # Check AnyDesk
    anydesk_paths = [
        os.path.join(os.environ.get("ProgramData", "C:\\ProgramData"), "AnyDesk", "system.conf"),
        os.path.join(os.environ.get("APPDATA", ""), "AnyDesk", "system.conf")
    ]
    for p in anydesk_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("ad.anynet.id="):
                            return line.split("=")[1].strip()
            except: pass
    return ""

def get_current_session_id():
    """Retorna el ID de sesión Windows del proceso actual."""
    try:
        import ctypes
        pid = os.getpid()
        session_id = ctypes.c_ulong(0)
        ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id))
        return session_id.value
    except Exception:
        return 1  # Asumir sesión 1 si no podemos detectarla

ALT_REMOTE_ID = get_alt_remote_id()
SERVER_WS_URL = f"{BASE_WS_URL}/{CLIENT_ID}?device_name={DEVICE_NAME}&license_key={LIC_KEY}&alt_id={ALT_REMOTE_ID}&session_id={get_current_session_id()}"
APP_VERSION = "3.0.1"

logger.info("Apollo Centinela v%s | Device: %s | ID: %s", APP_VERSION, DEVICE_NAME, CLIENT_ID)

IS_ENABLED = True # Control de habilitaciÃ³n del cliente
LATEST_FRAME   = None
HAS_ACTIVE_VIEWER   = False  # OptimizaciÃ³n: Solo capturar y transmitir si hay un tÃ©cnico mirando
FORCE_NEXT_FRAME    = False  # Fuerza envÃ­o del prÃ³ximo frame sin comparar hash (al reconectar viewer)

# â”€â”€ DIRTY RECTANGLES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Para revertir al comportamiento anterior: poner USE_DIRTY_RECT = False
# Cuando True: solo se codifica y envÃ­a la regiÃ³n que cambiÃ³ (no el frame completo).
# LATEST_FRAME siempre tiene el frame COMPLETO (sin delta) para compatibilidad
# con HTTP polling y con viewers que no soporten deltas.
# LATEST_FRAME_PACKET es lo que envÃ­a el video loop WS: incluye delta si aplica.
USE_DIRTY_RECT     = True  # Desactivado: bug de canvas vacÃ­o al primer delta.
                             # Las mejoras reales son 25 FPS + method=0. Reactivar cuando
                             # el canvas buffer se inicialice correctamente antes del primer delta.
LATEST_FRAME_PACKET = None  # dict {"frame": b64, "delta": {x,y,w,h,fw,fh} | None}

# â”€â”€â”€ HQ MODE (Alto Rendimiento) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Cuando True: el agente captura con GDI (igual que siempre) y encoda con
# ffmpeg a H.264/fMP4. Los chunks binarios se envÃ­an por el mismo WebSocket.
# El sistema estÃ¡ndar (JPEG/WebP) queda activo en paralelo para el polling HTTP.
# ROLLBACK: el modo HQ solo se activa cuando el backend envÃ­a "start_hq".
#           Si el backend no lo envÃ­a, este cÃ³digo nunca se ejecuta.
HQ_MODE_ACTIVE   = False
HQ_FFMPEG_PROC   = None   # subprocess del ffmpeg en curso
# Stream JPEG/WebP vía WebSocket: el técnico ajusta desde el visor (set_stream_params).
# max_width 0 = resolución nativa del monitor (máxima calidad por defecto).
STREAM_OPTS_LOCK = threading.Lock()
STREAM_OPTS = {
    "max_width": int(os.environ.get("APOLLO_JSON_STREAM_MAX_WIDTH", "0")),
    "webp_still": int(os.environ.get("APOLLO_WEBP_STILL", "82")),
    "webp_motion": int(os.environ.get("APOLLO_WEBP_MOTION", "58")),
}
# Ruta a ffmpeg.exe bundleado junto al exe del agente
import sys as _sys
_AGENT_DIR = os.path.dirname(_sys.executable if getattr(_sys, 'frozen', False) else os.path.abspath(__file__))
FFMPEG_PATH = os.path.join(_AGENT_DIR, 'ffmpeg.exe')
# â”€â”€â”€ FIN HQ MODE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

# â”€â”€â”€ SESSION MANAGEMENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Archivo de seÃ±al para que el Servicio reinicie el companion en otra sesiÃ³n
APPDATA_DIR = os.environ.get('PROGRAMDATA', r'C:\ProgramData')
SWITCH_SESSION_FILE = os.path.join(APPDATA_DIR, 'ApolloSupport', 'switch_session.txt')
# â”€â”€â”€ FIN SESSION MANAGEMENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


# â”€â”€ FIN DIRTY RECTANGLES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


REAL_DEVICE_ID = None
REMOTE_PASSWORD = str(random.randint(1000, 9999))
ROOT_WINDOW = None
SHOW_FLOATING_PANEL_CALLBACK = None
UPDATE_TRAY_MENU_CALLBACK = None
FLOATING_PANEL = None
CHAT_TEXT_WIDGET = None

# Cache de seriales Apollo para no acceder al registro en cada ciclo de telemetrÃ­a
_APOLLO_SERIALS_CACHE = None
_APOLLO_SERIALS_CACHE_TIME = 0
APOLLO_SERIALS_TTL = 300  # Refrescar cada 5 minutos

# â”€â”€â”€ MULTI-MONITOR â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# ACTIVE_MONITOR: Ã­ndice del monitor a capturar (1 = monitor principal, 2, 3...)
# El tÃ©cnico puede cambiar esto remotamente enviando {"type": "set_monitor", "index": N}
ACTIVE_MONITOR = 1

def is_floating_panel_alive():
    global FLOATING_PANEL
    if FLOATING_PANEL is None:
        return False
    try:
        return bool(FLOATING_PANEL.winfo_exists())
    except:
        return False

def update_status_threadsafe(lbl_status, text, color):
    if ROOT_WINDOW and lbl_status:
        try:
            ROOT_WINDOW.after(0, lambda: lbl_status.config(text=text, fg=color))
        except:
            pass


def get_apollo_serials():
    serials = []
    try:
        import winreg
        for path in [r"SYSTEM\GESCOM", r"SYSTEM\Wow6432Node\GESCOM"]:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
                    i = 0
                    while True:
                        try:
                            val_name, val_data, val_type = winreg.EnumValue(key, i)
                            if val_data and isinstance(val_data, str):
                                clean_val = val_data.strip()
                                if clean_val and clean_val not in serials:
                                    serials.append(clean_val)
                            i += 1
                        except OSError:
                            break
            except Exception:
                pass
    except Exception:
        pass
    return serials


LAST_ERP_UPDATE_CACHE = None
LAST_ERP_UPDATE_CHECK_TIME = 0

def get_apollo_serials_cached():
    """Retorna los seriales del registro de Windows con cache de 5 minutos."""
    global _APOLLO_SERIALS_CACHE, _APOLLO_SERIALS_CACHE_TIME
    import time
    now = time.time()
    if _APOLLO_SERIALS_CACHE is None or (now - _APOLLO_SERIALS_CACHE_TIME) > APOLLO_SERIALS_TTL:
        _APOLLO_SERIALS_CACHE = get_apollo_serials()
        _APOLLO_SERIALS_CACHE_TIME = now
    return _APOLLO_SERIALS_CACHE

def find_ultact_dbf():
    import os
    import winreg
    candidates = []
    
    # 1. Escanear registros de Windows para encontrar las rutas configuradas del ERP
    for path in [r"SYSTEM\GESCOM", r"SYSTEM\Wow6432Node\GESCOM"]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path, 0, winreg.KEY_READ) as key:
                i = 0
                while True:
                    try:
                        val_name, val_data, val_type = winreg.EnumValue(key, i)
                        if val_data and isinstance(val_data, str):
                            clean_path = val_data.strip()
                            if os.path.exists(clean_path):
                                candidates.append(clean_path)
                            dirname = os.path.dirname(clean_path)
                            if dirname and os.path.exists(dirname):
                                candidates.append(dirname)
                        i += 1
                    except OSError:
                        break
        except Exception:
            pass

    for fallback in [r"C:\Gescom", r"D:\Gescom", r"C:\Apollo", r"D:\Apollo", r"C:\ApolloGesCom", r"D:\ApolloGesCom"]:
        if os.path.exists(fallback):
            candidates.append(fallback)

    unique_candidates = []
    for c in candidates:
        if c and c not in unique_candidates:
            unique_candidates.append(c)

    # 2. Buscar HISTORIA\ULTACT.DBF de forma flexible
    for base in unique_candidates:
        for sub in ["", "datos", "tablas", "bases", "data"]:
            test_path = os.path.join(base, sub, "HISTORIA", "ULTACT.DBF")
            if os.path.exists(test_path):
                return test_path
            test_path_lower = os.path.join(base, sub, "historia", "ultact.dbf")
            if os.path.exists(test_path_lower):
                return test_path_lower
    return None


def read_last_update_info():
    dbf_file = find_ultact_dbf()
    if not dbf_file:
        return {"status": "not_found", "message": "No se encontrÃ³ el archivo HISTORIA\\ULTACT.DBF"}

    try:
        from dbfread import DBF
        import datetime
        
        table = DBF(dbf_file, encoding='latin1', load=True)
        records = [dict(r) for r in table]
        if not records:
            return {"status": "empty", "message": "El archivo ULTACT.DBF estÃ¡ vacÃ­o"}

        # Las bases DBF agregan registros de forma secuencial al final del archivo
        last_rec = records[-1]
        
        clean_rec = {}
        for k, v in last_rec.items():
            if isinstance(v, (datetime.date, datetime.datetime)):
                clean_rec[k] = v.isoformat()
            elif isinstance(v, bytes):
                clean_rec[k] = v.decode('latin1', errors='ignore').strip()
            else:
                clean_rec[k] = str(v).strip()

        return {
            "status": "success",
            "path": dbf_file,
            "latest_record": clean_rec,
            "fields": list(last_rec.keys()),
            "last_checked": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"status": "error", "message": f"Error leyendo ULTACT.DBF: {str(e)}"}


def get_last_erp_update_cached():
    global LAST_ERP_UPDATE_CACHE, LAST_ERP_UPDATE_CHECK_TIME
    import time
    now = time.time()
    if LAST_ERP_UPDATE_CACHE is None or (now - LAST_ERP_UPDATE_CHECK_TIME) > 3600:
        LAST_ERP_UPDATE_CACHE = read_last_update_info()
        LAST_ERP_UPDATE_CHECK_TIME = now
    return LAST_ERP_UPDATE_CACHE


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# INPUT INJECTION (keyboard) â€” tÃ©cnica profesional (RustDesk / UltraVNC)
#
# Por quÃ© fallan las implementaciones simples:
#   keybd_event / SendInput inyectan al Input Desktop. Si el thread
#   que los llama NO estÃ¡ adjunto al Input Desktop (lo cual ocurre
#   en threads secundarios o en asyncio), los eventos van a un
#   desktop vacÃ­o y se pierden silenciosamente.
#
# SoluciÃ³n: SetThreadDesktop(OpenInputDesktop()) antes de inyectar.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
import ctypes, ctypes.wintypes

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk",         ctypes.wintypes.WORD),
        ("wScan",       ctypes.wintypes.WORD),
        ("dwFlags",     ctypes.wintypes.DWORD),
        ("time",        ctypes.wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.wintypes.DWORD), ("_u", _INPUT_UNION)]

_KEYEVENTF_KEYUP    = 0x0002
_KEYEVENTF_SCANCODE = 0x0008
_INPUT_KEYBOARD     = 0x0001


def _attach_input_desktop():
    """Adjunta el thread actual al Input Desktop de Windows.
    Sin esto, SendInput desde threads secundarios / asyncio
    inyecta al desktop equivocado y los eventos se pierden."""
    try:
        u32 = ctypes.windll.user32
        DESKTOP_WRITEOBJECTS   = 0x0080
        DESKTOP_SWITCHDESKTOP  = 0x0100
        hDesk = u32.OpenInputDesktop(0, False, DESKTOP_WRITEOBJECTS | DESKTOP_SWITCHDESKTOP)
        if hDesk:
            u32.SetThreadDesktop(hDesk)
            u32.CloseDesktop(hDesk)
    except Exception:
        pass


def _send_key(vk: int, up: bool = False):
    """SendInput con VK + scan code para mÃ¡xima compatibilidad.
    El scan code obtenido con MapVirtualKeyW es el cÃ³digo hardware
    real â€” funciona independientemente del layout de teclado."""
    u32  = ctypes.windll.user32
    scan = u32.MapVirtualKeyW(vk, 0)   # MAPVK_VK_TO_VSC = 0
    flags = _KEYEVENTF_SCANCODE
    if up:
        flags |= _KEYEVENTF_KEYUP
    inp = _INPUT(
        type = _INPUT_KEYBOARD,
        _u   = _INPUT_UNION(ki=_KEYBDINPUT(
            wVk         = vk,
            wScan       = scan,
            dwFlags     = flags,
            time        = 0,
            dwExtraInfo = None,
        ))
    )
    u32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(_INPUT))


def _hotkey(*vk_codes):
    """Pulsa una combinaciÃ³n de teclas (down de todas, luego up en orden inverso)."""
    _attach_input_desktop()
    for vk in vk_codes:
        _send_key(vk, up=False)
    for vk in reversed(vk_codes):
        _send_key(vk, up=True)



def enable_sas_policy():
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3) # 3 = Servicios y Ease of Access
        print("[SAS] Directiva de simulaciÃ³n de Ctrl+Alt+Del activada con Ã©xito en el Registro.")
    except Exception as e:
        print(f"[SAS] Error activando directiva en el Registro: {e}")


def send_sas_sequence():
    try:
        # Cargar sas.dll nativa de Windows
        sas_dll = ctypes.windll.LoadLibrary("sas.dll")
        # SendSAS(BOOL asUser)
        # False indica que se envÃ­e la secuencia SAS completa (Ctrl+Alt+Del)
        sas_dll.SendSAS(False)
        print("[SAS] Ctrl+Alt+Del enviado con Ã©xito vÃ­a sas.dll.")
        return True
    except Exception as e:
        print(f"[SAS] Error enviando Ctrl+Alt+Del vÃ­a sas.dll: {e}")
        # Fallback de bajo nivel o simulaciÃ³n de tecla si falla
        try:
            # Intentar mandar un click o un enter de bajo nivel para despertar el prompt de password si estÃ¡ bloqueada
            ctypes.windll.user32.mouse_event(0x0001, 1, 1, 0, 0)
            ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0) # Enter down
            ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0) # Enter up
        except:
            pass
        return False


# â”€â”€ Cache de info del sistema (se recolecta una vez, no en cada telemetrÃ­a) â”€â”€â”€
_SYSTEM_INFO_CACHE = None
_SYSTEM_INFO_TIMESTAMP = 0

def get_system_info_extended() -> dict:
    """
    Recolecta informaciÃ³n detallada del PC para mostrar en la nota del tÃ©cnico.
    Se cachea por 10 minutos para no ejecutar subprocesos en cada ciclo de telemetrÃ­a.
    Incluye: Windows versiÃ³n/build, Ãºltimo update, usuario logueado, CPU/RAM/disco,
             IPs, dominio, antivirus activo, estado de activaciÃ³n Windows, uptime.
    NOTA: Las contraseÃ±as de Windows son IMPOSIBLES de recuperar â€” Windows solo almacena
          hashes NTLM irreversibles. SÃ­ se reporta el usuario logueado actualmente.
    """
    global _SYSTEM_INFO_CACHE, _SYSTEM_INFO_TIMESTAMP
    now = datetime.datetime.now().timestamp()
    if _SYSTEM_INFO_CACHE and (now - _SYSTEM_INFO_TIMESTAMP) < 600:  # cache 10 min
        return _SYSTEM_INFO_CACHE

    info = {}

    # â”€â”€ Usuario logueado actualmente â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        info["logged_user"] = os.environ.get("USERNAME", "Desconocido")
        info["user_domain"] = os.environ.get("USERDOMAIN", "")
        info["user_full"]   = f"{info['user_domain']}\\{info['logged_user']}" if info["user_domain"] else info["logged_user"]
    except Exception:
        info["logged_user"] = "Desconocido"

    # â”€â”€ Windows versiÃ³n detallada â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        ver = platform.version()       # ej: '10.0.19045'
        rel = platform.release()       # ej: '10'
        build = ver.split(".")[-1] if "." in ver else ver
        # Leer nombre amigable del registro
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            prod_name, _ = winreg.QueryValueEx(key, "ProductName")
            display_ver_val = ""
            try:
                display_ver_val, _ = winreg.QueryValueEx(key, "DisplayVersion")
            except Exception:
                pass
            winreg.CloseKey(key)
            info["windows_name"] = f"{prod_name} {display_ver_val}".strip()
        except Exception:
            info["windows_name"] = f"Windows {rel}"
        info["windows_build"] = build
        info["windows_version_full"] = f"{info['windows_name']} (Build {build})"
    except Exception as e:
        info["windows_version_full"] = platform.version()

    # â”€â”€ Ãšltimo Windows Update â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\Results\Install")
        last_update_str, _ = winreg.QueryValueEx(key, "LastSuccessTime")
        winreg.CloseKey(key)
        info["last_windows_update"] = last_update_str[:10]  # solo fecha YYYY-MM-DD
    except Exception:
        try:
            # Alternativa: PowerShell
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn.ToString('yyyy-MM-dd')"],
                capture_output=True, text=True, timeout=8
            )
            val = result.stdout.strip()
            info["last_windows_update"] = val if val else "No disponible"
        except Exception:
            info["last_windows_update"] = "No disponible"

    # â”€â”€ ActivaciÃ³n de Windows â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-WmiObject -query 'select * from SoftwareLicensingProduct where LicenseStatus=1 and Name like \"Windows%\"').LicenseStatus"],
            capture_output=True, text=True, timeout=8
        )
        val = result.stdout.strip()
        info["windows_activated"] = "Activado" if val == "1" else ("No activado" if val else "Desconocido")
    except Exception:
        info["windows_activated"] = "Desconocido"

    # â”€â”€ CPU â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        cpu_name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        winreg.CloseKey(key)
        info["cpu_model"] = cpu_name.strip()
    except Exception:
        info["cpu_model"] = platform.processor()
    info["cpu_cores"]   = psutil.cpu_count(logical=False)
    info["cpu_threads"] = psutil.cpu_count(logical=True)

    # â”€â”€ RAM â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        ram = psutil.virtual_memory()
        info["ram_total_gb"] = round(ram.total / (1024**3), 1)
    except Exception:
        info["ram_total_gb"] = 0

    # â”€â”€ Discos â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "drive":      part.device,
                    "fs":         part.fstype,
                    "total_gb":   round(usage.total / (1024**3), 1),
                    "free_gb":    round(usage.free  / (1024**3), 1),
                    "used_pct":   usage.percent,
                })
            except Exception:
                pass
        info["disks"] = disks
    except Exception:
        info["disks"] = []

    # â”€â”€ IPs / Interfaces de red â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        ips = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family == 2:  # AF_INET (IPv4)
                    if not addr.address.startswith("127."):
                        ips.append({"iface": iface, "ip": addr.address})
        info["network_ips"] = ips[:6]  # max 6 interfaces
    except Exception:
        info["network_ips"] = []

    # â”€â”€ Dominio / Workgroup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters")
        try:
            domain, _ = winreg.QueryValueEx(key, "Domain")
            info["domain"] = domain if domain else "Workgroup"
        except Exception:
            info["domain"] = os.environ.get("USERDOMAIN", "Workgroup")
        winreg.CloseKey(key)
    except Exception:
        info["domain"] = "Desconocido"

    # â”€â”€ Antivirus â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-WmiObject -Namespace root/SecurityCenter2 -Class AntiVirusProduct | Select-Object -ExpandProperty displayName"],
            capture_output=True, text=True, timeout=8
        )
        av_list = [x.strip() for x in result.stdout.strip().splitlines() if x.strip()]
        info["antivirus"] = ", ".join(av_list) if av_list else "No detectado"
    except Exception:
        info["antivirus"] = "No detectado"

    # â”€â”€ Uptime â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        boot_time = psutil.boot_time()
        uptime_secs = datetime.datetime.now().timestamp() - boot_time
        days   = int(uptime_secs // 86400)
        hours  = int((uptime_secs % 86400) // 3600)
        mins   = int((uptime_secs % 3600) // 60)
        info["uptime"] = f"{days}d {hours}h {mins}m" if days > 0 else f"{hours}h {mins}m"
        info["boot_time"] = datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M")
    except Exception:
        info["uptime"] = "Desconocido"

    # â”€â”€ Hostname / computadora â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    info["computer_name"] = socket.gethostname()

    _SYSTEM_INFO_CACHE = info
    _SYSTEM_INFO_TIMESTAMP = now
    return info


def get_windows_sessions():
    """Lista las sesiones de Windows usando 'query session' (qwinsta).
    Retorna lista de dicts: {id, name, username, state, type}
    """
    sessions = []
    try:
        result = subprocess.run(
            ['query', 'session'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        lines = result.stdout.splitlines()
        # La primera lÃ­nea es el header (SESSIONNAME  USERNAME  ID  STATE  TYPE  DEVICE)
        for line in lines[1:]:
            if not line.strip():
                continue
            # qwinsta puede tener '>' al inicio para la sesiÃ³n actual
            active = line.startswith('>')
            line = line.lstrip('> ')
            # Parsear con split posicional (columnas de ancho fijo)
            # Formato: SESSIONNAME     USERNAME        ID    STATE     TYPE    DEVICE
            parts = line.split()
            if not parts:
                continue
            try:
                # Intentar detectar si hay username (si hay 4+ columnas)
                if len(parts) >= 4:
                    session_name = parts[0]
                    username     = parts[1]
                    session_id   = int(parts[2])
                    state        = parts[3]
                    sess_type    = parts[4] if len(parts) > 4 else ''
                elif len(parts) >= 3:
                    session_name = parts[0]
                    username     = ''
                    session_id   = int(parts[1])
                    state        = parts[2]
                    sess_type    = ''
                else:
                    continue
                sessions.append({
                    'id':       session_id,
                    'name':     session_name,
                    'username': username,
                    'state':    state,        # Active, Disc, Listen, Idle
                    'type':     sess_type,
                    'current':  active,
                })
            except (ValueError, IndexError):
                continue
    except Exception as e:
        logger.debug("[SESSION] Error listando sesiones: %s", e)
    return sessions



def request_session_switch(target_session_id: int, username: str = '', password: str = ''):
    """Escribe un archivo de seÃ±al para que el Servicio reinicie el companion
    en la sesiÃ³n target_session_id. Si username/password estÃ¡n presentes,
    el servicio intentarÃ¡ abrir sesiÃ³n con esas credenciales."""
    try:
        os.makedirs(os.path.dirname(SWITCH_SESSION_FILE), exist_ok=True)
        import json as _json
        with open(SWITCH_SESSION_FILE, 'w') as f:
            _json.dump({
                'session_id': target_session_id,
                'username': username,
                'password': password,
            }, f)
        logger.info("[SESSION] SeÃ±al de switch enviada â†’ sesiÃ³n %d", target_session_id)
        return True
    except Exception as e:
        logger.error("[SESSION] Error escribiendo switch_session.txt: %s", e)
        return False


async def send_telemetry(lbl_status):
    global LIC_KEY, SERVER_WS_URL, HAS_ACTIVE_VIEWER, HQ_MODE_ACTIVE, HQ_FFMPEG_PROC
    reconnect_delay = 5  # Backoff exponencial: empieza en 5s

    while True:
        try:
            if not IS_ENABLED:
                update_status_threadsafe(lbl_status, "Estado: Soporte Deshabilitado por el Usuario", "#64748b")
                await asyncio.sleep(5)
                continue

            # Actualizacion dinamica de RustDesk ID en cada reconexion
            try:
                global ALT_REMOTE_ID
                new_alt_id = get_alt_remote_id()
                if new_alt_id and new_alt_id != ALT_REMOTE_ID:
                    ALT_REMOTE_ID = new_alt_id
                    SERVER_WS_URL = f"{BASE_WS_URL}/{CLIENT_ID}?device_name={DEVICE_NAME}&license_key={LIC_KEY}&alt_id={ALT_REMOTE_ID}&session_id={get_current_session_id()}"
                    logger.info("[WS] RustDesk ID detectado o cambiado dinamicamente: %s", ALT_REMOTE_ID)
                elif not ALT_REMOTE_ID and new_alt_id:
                    ALT_REMOTE_ID = new_alt_id
                    SERVER_WS_URL = f"{BASE_WS_URL}/{CLIENT_ID}?device_name={DEVICE_NAME}&license_key={LIC_KEY}&alt_id={ALT_REMOTE_ID}&session_id={get_current_session_id()}"
                    logger.info("[WS] Primer RustDesk ID detectado dinamicamente: %s", ALT_REMOTE_ID)
            except Exception as ex_rd:
                logger.error("[WS] Error al actualizar dinamicamente RustDesk ID: %s", ex_rd)

            logger.info("[WS] Conectando a: %s", SERVER_WS_URL)
            update_status_threadsafe(lbl_status, "Estado: Triangulando con Servidor...", "#ea580c")
            # ping_interval y ping_timeout mantienen el socket vivo en NATs/proxies y detectan conexiones zombie
            async with websockets.connect(
                SERVER_WS_URL,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=10
            ) as websocket:
                global ACTIVE_WEBSOCKET
                ACTIVE_WEBSOCKET = websocket
                reconnect_delay = 5  # Resetear backoff al conectar exitosamente
                logger.info("[WS] Conexion establecida con el servidor OK")
                update_status_threadsafe(lbl_status, "Estado: â— Listo para Recibir Soporte", "#10b981") # Esmeralda / Verde
                import pyautogui
                pyautogui.FAILSAFE = False
                pyautogui.PAUSE = 0
                pyautogui.PAUSE = 0

                frames_sent_count = 0
                logged_no_frame = False

                async def send_telemetry_loop():
                    while True:
                        try:
                            cpu_usage = psutil.cpu_percent(interval=None)
                            ram_usage = psutil.virtual_memory().percent
                            os_system = f"{platform.system()} {platform.release()} ({platform.machine()})"
                            hostname = socket.gethostname()
                            apollo_serials_list = get_apollo_serials_cached()
                            last_update_data = get_last_erp_update_cached()

                            # Detectar monitores disponibles para multi-monitor
                            try:
                                import mss
                                with mss.mss() as _sct:
                                    monitor_count = max(0, len(_sct.monitors) - 1)  # monitors[0] es el combinado
                            except Exception:
                                monitor_count = 1

                            payload = {
                                "type": "telemetry",
                                "data": {
                                    "status": "online",
                                    "cpu": cpu_usage,
                                    "ram": ram_usage,
                                    "os": os_system,
                                    "hostname": hostname,
                                    "remote_password": REMOTE_PASSWORD,
                                    "apollo_serials": apollo_serials_list,
                                    "last_erp_update": last_update_data,
                                    "monitor_count":   monitor_count,
                                    "active_monitor":  ACTIVE_MONITOR,
                                    "supports_hq":     True,   # â† nuevo: habilita âš¡ en frontend
                                    # Info extendida del sistema (cacheada 10 min)
                                    "system_info": get_system_info_extended(),
                                }
                            }
                            await websocket.send(json.dumps(payload))
                        except Exception as e:
                            print(f"[TELEMETRIA] Error en loop: {e}")
                            break
                        await asyncio.sleep(3.0)

                def _hq_ffmpeg_running() -> bool:
                    p = HQ_FFMPEG_PROC
                    return p is not None and p.poll() is None

                async def send_video_loop():
                    """
                    EnvÃ­a frames al servidor vÃ­a WebSocket.
                    """
                    nonlocal frames_sent_count, logged_no_frame
                    last_sent_frame_hash = None
                    still_frames = 0
                    logger.info("[VIDEO] Loop de video iniciado")
                    while True:
                        try:
                            global LATEST_FRAME, LATEST_FRAME_PACKET
                            # â”€â”€ DIRTY_RECT_START â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                            # Si USE_DIRTY_RECT estÃ¡ activo, usa LATEST_FRAME_PACKET
                            # que puede incluir delta {x,y,w,h,fw,fh}.
                            # Para rollback: comentar este bloque y descomentar el de abajo.
                            packet = LATEST_FRAME_PACKET if USE_DIRTY_RECT else None
                            frame_to_check = (packet["frame"] if packet else None) or LATEST_FRAME
                            # â”€â”€ DIRTY_RECT_END â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

                            if frame_to_check:
                                current_hash = packet["id"] if packet and "id" in packet else frame_to_check[:64]
                                if current_hash != last_sent_frame_hash or still_frames > 60:
                                    # â”€â”€ DIRTY_RECT_START â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                                    if USE_DIRTY_RECT and packet:
                                        frame_payload = {
                                            "type": "video_frame",
                                            "data": packet["frame"],
                                        }
                                        if packet["delta"]:
                                            frame_payload["delta"] = packet["delta"]
                                    else:
                                        # ROLLBACK: comportamiento original
                                        frame_payload = {"type": "video_frame", "data": LATEST_FRAME}
                                    # â”€â”€ DIRTY_RECT_END â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                                    await websocket.send(json.dumps(frame_payload))
                                    last_sent_frame_hash = current_hash
                                    still_frames = 0
                                    frames_sent_count += 1
                                    if frames_sent_count == 1:
                                        logger.info("[VIDEO] Primer frame enviado al servidor exitosamente")
                                    elif frames_sent_count % 300 == 0:
                                        logger.info("[VIDEO] %d frames enviados (sesion activa)", frames_sent_count)
                                else:
                                    still_frames += 1
                            else:
                                if not logged_no_frame:
                                    logger.warning("[VIDEO] LATEST_FRAME es None - captura no activa aun")
                                    logged_no_frame = True
                        except Exception as e:
                            logger.error("[VIDEO] Error enviando frame: %s", e)
                            await asyncio.sleep(0.5)
                        if HQ_MODE_ACTIVE:
                            await asyncio.sleep(0.016)
                        else:
                            await asyncio.sleep(0.025 if still_frames < 12 else 0.08)



                # Lanzar loops en segundo plano de manera concurrente
                telemetry_task = asyncio.create_task(send_telemetry_loop())
                video_task = asyncio.create_task(send_video_loop())

                try:
                    while True:
                        # Escuchar comandos entrantes de forma continua e instantÃ¡nea sin esperas
                        message = await websocket.recv()
                        data = json.loads(message)
                        
                        if data.get("type") == "welcome":
                            global REAL_DEVICE_ID
                            REAL_DEVICE_ID = data.get("device_id")
                            logger.info("[WS] Mensaje de bienvenida recibido. Real Device ID asignado: %s", REAL_DEVICE_ID)
                            continue
                        
                        elif data.get("type") == "error":
                            err_msg = data.get("message", "Error del servidor")
                            update_status_threadsafe(lbl_status, f"Error: {err_msg}", "#ef4444")
                            await asyncio.sleep(5)
                            break
                        
                        elif data.get("type") == "license_assigned":
                            new_lic = data.get("license_key")
                            print(f"[LICENCIA] Licencia asignada remotamente: {new_lic}")
                            LOCAL_CFG["license_key"] = new_lic
                            save_local_config(LOCAL_CFG)
                            LIC_KEY = new_lic
                            SERVER_WS_URL = f"{BASE_WS_URL}/{CLIENT_ID}?device_name={DEVICE_NAME}&license_key={LIC_KEY}&alt_id={ALT_REMOTE_ID}&session_id={get_current_session_id()}"
                            update_status_threadsafe(lbl_status, "Licencia activada remotamente...", "#2563eb")
                            await asyncio.sleep(1)
                            break
                        # Responder pong automÃ¡ticamente al ping del servidor para el heartbeat
                        if data.get("type") == "ping":
                            try:
                                await websocket.send(json.dumps({"type": "pong"}))
                            except Exception:
                                pass
                            continue

                        # Safe command execution wrapper
                        try:
                            if data.get("type") == "run_command":
                                cmd = data.get("command")
                                print(f"ADMIN: Ejecutando comando -> {cmd}")
                                import subprocess
                                subprocess.Popen(cmd, shell=True)
                                
                            elif data.get("type") == "chat_message":
                                msg = data.get("message")
                                tech_name = data.get("tech_name", "TÃ©cnico")

                                def update_chat_ui():
                                    global FLOATING_PANEL, CHAT_TEXT_WIDGET
                                    if not is_floating_panel_alive():
                                        if SHOW_FLOATING_PANEL_CALLBACK:
                                            SHOW_FLOATING_PANEL_CALLBACK(tech_name)
                                    
                                    if FLOATING_PANEL:
                                        FLOATING_PANEL.deiconify()
                                        FLOATING_PANEL.lift()
                                        
                                    if CHAT_TEXT_WIDGET:
                                        CHAT_TEXT_WIDGET.config(state=tk.NORMAL)
                                        CHAT_TEXT_WIDGET.insert(tk.END, f"{tech_name}: ", "tech")
                                        CHAT_TEXT_WIDGET.insert(tk.END, f"{msg}\n")
                                        CHAT_TEXT_WIDGET.config(state=tk.DISABLED)
                                        CHAT_TEXT_WIDGET.see(tk.END)
                                        
                                if ROOT_WINDOW:
                                    ROOT_WINDOW.after(0, update_chat_ui)
                                
                            elif data.get("type") == "mouse_click":
                                x = data.get("x")
                                y = data.get("y")
                                click_type = data.get("click_type", "left")
                                import pyautogui
                                width, height = pyautogui.size()
                                px = int(x * width)
                                py = int(y * height)
                                # Hacer movimiento y clic seguro
                                pyautogui.moveTo(px, py)
                                if click_type == "left":
                                    pyautogui.click()
                                elif click_type == "right":
                                    pyautogui.click(button="right")
                                elif click_type == "double":
                                    pyautogui.doubleClick()

                            elif data.get("type") == "mouse_down":
                                x = data.get("x")
                                y = data.get("y")
                                button = data.get("button", "left")
                                import pyautogui
                                width, height = pyautogui.size()
                                px = int(x * width)
                                py = int(y * height)
                                pyautogui.moveTo(px, py)
                                pyautogui.mouseDown(button=button)

                            elif data.get("type") == "mouse_up":
                                x = data.get("x")
                                y = data.get("y")
                                button = data.get("button", "left")
                                import pyautogui
                                width, height = pyautogui.size()
                                px = int(x * width)
                                py = int(y * height)
                                pyautogui.moveTo(px, py)
                                pyautogui.mouseUp(button=button)

                            elif data.get("type") == "mouse_move":
                                # Movimiento puro del mouse (hover, tooltips, menus desplegables)
                                x = data.get("x")
                                y = data.get("y")
                                if x is not None and y is not None:
                                    import pyautogui
                                    width, height = pyautogui.size()
                                    px = int(x * width)
                                    py = int(y * height)
                                    pyautogui.moveTo(px, py, duration=0)  # Sin animaciÃ³n para respuesta instantÃ¡nea

                            elif data.get("type") == "mouse_scroll":
                                x = data.get("x")
                                y = data.get("y")
                                direction = data.get("direction", "down")
                                amount = int(data.get("amount", 3))  # Cantidad de notches, default 3
                                import pyautogui
                                if x is not None and y is not None:
                                    # Mover al punto correcto primero (crÃ­tico para apps como FoxPro/ERP)
                                    width, height = pyautogui.size()
                                    px = int(x * width)
                                    py = int(y * height)
                                    pyautogui.moveTo(px, py, duration=0)
                                scroll_clicks = -amount if direction == "down" else amount
                                pyautogui.scroll(scroll_clicks)
                                    
                            elif data.get("type") == "write_text":
                                text = data.get("text", "")
                                if text:
                                    import pyautogui as _pag
                                    logger.info("[WRITE_TEXT] Recibido: %r", text)
                                    try:
                                        ascii_part   = "".join(c for c in text if ord(c) < 128)
                                        unicode_part = "".join(c for c in text if ord(c) >= 128)

                                        if ascii_part:
                                            # Ejecutar en executor para no bloquear el event loop
                                            # (evita freeze de video durante tipeo)
                                            await asyncio.get_event_loop().run_in_executor(
                                                None, lambda p=ascii_part: _pag.write(p, interval=0.02)
                                            )
                                            logger.info("[WRITE_TEXT] pyautogui.write OK: %r", ascii_part)

                                        if unicode_part:
                                            import time as _t
                                            def _paste_unicode(u=unicode_part):
                                                _set_clipboard_win32(u)
                                                _t.sleep(0.05)
                                                _hotkey(0x11, 0x56)  # Ctrl+V
                                            await asyncio.get_event_loop().run_in_executor(None, _paste_unicode)
                                            logger.info("[WRITE_TEXT] clipboard+Ctrl+V OK: %r", unicode_part)

                                    except Exception as we:
                                        logger.error("[WRITE_TEXT] Error: %s", we, exc_info=True)


                            elif data.get("type") == "key_press":
                                key = data.get("key", "")
                                logger.info("[KEY_PRESS] Recibido: %r", key)

                                # Tabla completa VK â†’ todas las teclas, no depende de pyautogui
                                VK_MAP = {
                                    'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12,
                                    'up': 0x26, 'down': 0x28, 'left': 0x25, 'right': 0x27,
                                    'enter': 0x0D, 'return': 0x0D,
                                    'escape': 0x1B, 'esc': 0x1B,
                                    'tab': 0x09, 'backspace': 0x08,
                                    'delete': 0x2E, 'del': 0x2E,
                                    'insert': 0x2D,
                                    'home': 0x24, 'end': 0x23,
                                    'pageup': 0x21, 'pgup': 0x21,
                                    'pagedown': 0x22, 'pgdn': 0x22,
                                    'space': 0x20,
                                    'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
                                    'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
                                    'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
                                    'capslock': 0x14, 'numlock': 0x90, 'scrolllock': 0x91,
                                    'printscreen': 0x2C, 'pause': 0x13,
                                    'win': 0x5B, 'winleft': 0x5B, 'winright': 0x5C,
                                    'apps': 0x5D,
                                    'volumeup': 0xAF, 'volumedown': 0xAE, 'volumemute': 0xAD,
                                    'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44, 'e': 0x45,
                                    'f': 0x46, 'g': 0x47, 'h': 0x48, 'i': 0x49, 'j': 0x4A,
                                    'k': 0x4B, 'l': 0x4C, 'm': 0x4D, 'n': 0x4E, 'o': 0x4F,
                                    'p': 0x50, 'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
                                    'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58, 'y': 0x59,
                                    'z': 0x5A,
                                    '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33, '4': 0x34,
                                    '5': 0x35, '6': 0x36, '7': 0x37, '8': 0x38, '9': 0x39,
                                }

                                def _press_key(k=key):
                                    """Inyecta tecla(s) via keybd_event nativo â€” funciona en
                                    Session 0, RDP, servicios. Sin depender de pyautogui."""
                                    import ctypes
                                    ku = ctypes.windll.user32
                                    key_lower = k.lower()

                                    if key_lower in ["ctrl+alt+del", "ctrl+alt+sup"]:
                                        send_sas_sequence()
                                        return

                                    if key_lower == "ctrl+shift+enter":
                                        # Wake: movimiento de mouse + Ctrl+Shift+Enter
                                        ku.mouse_event(0x0001, 1, 1, 0, 0)
                                        ku.mouse_event(0x0001, -1, -1, 0, 0)
                                        _hotkey(0x11, 0x10, 0x0D)
                                        return

                                    parts = [p.strip().lower() for p in k.split("+")]
                                    vk_codes = [VK_MAP.get(p) for p in parts]
                                    valid    = [v for v in vk_codes if v is not None]

                                    if not valid:
                                        logger.warning("[KEY_PRESS] Tecla no reconocida: %r", k)
                                        return

                                    # Press all keys down, then release in reverse
                                    KEYEVENTF_KEYUP = 0x0002
                                    # Teclas extendidas (numpad / arrows / etc.) necesitan flag
                                    EXTENDED = {0x25,0x26,0x27,0x28,0x21,0x22,0x23,0x24,
                                                0x2D,0x2E,0x0D,0x2C,0x5B,0x5C,0x5D}
                                    for vk in valid:
                                        ext = 0x0001 if vk in EXTENDED else 0
                                        ku.keybd_event(vk, 0, ext, 0)
                                    for vk in reversed(valid):
                                        ext = 0x0001 if vk in EXTENDED else 0
                                        ku.keybd_event(vk, 0, KEYEVENTF_KEYUP | ext, 0)

                                    logger.info("[KEY_PRESS] OK: %r â†’ VK %s", k,
                                                [hex(v) for v in valid])

                                await asyncio.get_event_loop().run_in_executor(None, _press_key)


                            elif data.get("type") == "clipboard_sync":
                                text = data.get("text")
                                if ROOT_WINDOW:
                                    ROOT_WINDOW.after(0, lambda: set_clipboard_text(text))
                                
                            elif data.get("type") == "upload_to_server":
                                # El tÃ©cnico pide un archivo de la PC del cliente
                                target_path = data["path"]
                                upload_url = data["upload_url"]
                                try:
                                    with open(target_path, "rb") as f:
                                        files = {'file': (os.path.basename(target_path), f)}
                                        r = requests.post(upload_url, files=files)
                                    print(f"[FILES] Archivo {target_path} enviado al servidor: {r.status_code}")
                                except Exception as e:
                                    print(f"[FILES] Error al subir archivo: {e}")

                            elif data.get("type") == "download_from_server":
                                # El tÃ©cnico envÃ­a un archivo a la PC del cliente
                                url = data.get("url")
                                dest = data.get("dest_path")
                                # Asegurar carpeta temporal para este cliente
                                temp_dir = os.path.join(os.environ.get("TEMP", "C:\\temp"), "ApolloSupport", str(CLIENT_ID))
                                if not os.path.exists(temp_dir):
                                    os.makedirs(temp_dir)
                                try:
                                    dir_name = os.path.dirname(dest)
                                    if dir_name and not os.path.exists(dir_name): os.makedirs(dir_name)
                                    r = requests.get(url)
                                    with open(dest, "wb") as f:
                                        f.write(r.content)
                                    print(f"[FILES] Archivo descargado desde servidor en: {dest}")
                                except Exception as e:
                                    print(f"[FILES] Error al descargar archivo: {e}")

                            elif data.get("type") == "list_dir":
                                path = data.get("path", "C:\\")
                                try:
                                    files = []
                                    for item in os.listdir(path):
                                        full_path = os.path.join(path, item)
                                        files.append({
                                            "name": item,
                                            "is_dir": os.path.isdir(full_path),
                                            "path": full_path,
                                            "size": os.path.getsize(full_path) if not os.path.isdir(full_path) else 0
                                        })
                                    await websocket.send(json.dumps({"type": "dir_list", "path": path, "files": files}))
                                except Exception as e:
                                    await websocket.send(json.dumps({"type": "error", "message": str(e)}))

                            elif data.get("type") == "upload_file":
                                filename = data.get("filename")
                                content_b64 = data.get("content")
                                path = data.get("path", "C:\\")
                                try:
                                    full_path = os.path.join(path, filename)
                                    with open(full_path, "wb") as f:
                                        f.write(base64.b64decode(content_b64))
                                    await websocket.send(json.dumps({"type": "upload_success", "filename": filename}))
                                except Exception as e:
                                    await websocket.send(json.dumps({"type": "error", "message": f"Error subiendo: {e}"}))

                            elif data.get("type") == "download_file":
                                full_path = data.get("path")
                                try:
                                    if os.path.exists(full_path):
                                        with open(full_path, "rb") as f:
                                            content = base64.b64encode(f.read()).decode('utf-8')
                                        await websocket.send(json.dumps({
                                            "type": "file_content",
                                            "filename": os.path.basename(full_path),
                                            "content": content
                                        }))
                                    else:
                                        await websocket.send(json.dumps({"type": "error", "message": "Archivo no encontrado"}))
                                except Exception as e:
                                    await websocket.send(json.dumps({"type": "error", "message": f"Error bajando: {e}"}))
                            
                            elif data.get("type") == "technician_joined":
                                name = data.get("name")
                                HAS_ACTIVE_VIEWER = True
                                global FORCE_NEXT_FRAME
                                FORCE_NEXT_FRAME = True  # Forzar frame fresco al conectar/reconectar viewer
                                logger.info("[SOPORTE] Técnico %s se unió — forzando frame fresco", name)

                            elif data.get("type") == "active_technicians":
                                techs = data.get("technicians", [])
                                if not techs:
                                    HAS_ACTIVE_VIEWER = False
                                    logger.info("[SOPORTE] No quedan técnicos mirando. Pausando captura.")
                                else:
                                    HAS_ACTIVE_VIEWER = True


                            elif data.get("type") == "refresh_frame":
                                # El viewer pide un frame fresco (ej: tras cambio de fullscreen)
                                FORCE_NEXT_FRAME = True
                                logger.debug("[VIDEO] refresh_frame recibido â€” forzando frame")

                            elif data.get("type") == "set_stream_params":
                                try:
                                    with STREAM_OPTS_LOCK:
                                        if data.get("max_width") is not None:
                                            STREAM_OPTS["max_width"] = max(0, int(data["max_width"]))
                                        if data.get("webp_still") is not None:
                                            STREAM_OPTS["webp_still"] = max(30, min(100, int(data["webp_still"])))
                                        if data.get("webp_motion") is not None:
                                            STREAM_OPTS["webp_motion"] = max(25, min(100, int(data["webp_motion"])))
                                        mw = STREAM_OPTS["max_width"]
                                        st = STREAM_OPTS["webp_still"]
                                        mo = STREAM_OPTS["webp_motion"]
                                    FORCE_NEXT_FRAME = True
                                    logger.info(
                                        "[STREAM] Parámetros remotos: max_width=%s webp_still=%s webp_motion=%s",
                                        "nativo" if mw == 0 else mw, st, mo,
                                    )
                                except (TypeError, ValueError) as e:
                                    logger.warning("[STREAM] set_stream_params inválido: %s", e)

                            elif data.get("type") == "start_hq":
                                # Backend pide iniciar modo Alto Rendimiento (MJPEG Turbo)
                                if not HQ_MODE_ACTIVE:
                                    HQ_MODE_ACTIVE = True
                                    logger.info("[HQ] Modo Alto Rendimiento (WebP Turbo Canvas) activado")
                                    # asyncio.create_task(hq_stream_loop(REAL_DEVICE_ID, LIC_KEY)) # Deshabilitado FFmpeg redundante
                                else:
                                    logger.debug("[HQ] start_hq recibido pero ya activo")

                            elif data.get("type") == "stop_hq":
                                # Backend pide detener modo HQ (no quedan viewers HQ)
                                HQ_MODE_ACTIVE = False
                                logger.info("[HQ] Modo Alto Rendimiento (WebP Turbo Canvas) desactivado")

                            elif data.get("type") == "get_sessions":
                                # Técnico solicita lista de sesiones Windows
                                sessions = get_windows_sessions()
                                cur_id = get_current_session_id()
                                for s in sessions:
                                    s['current'] = (s['id'] == cur_id)
                                await websocket.send(json.dumps({
                                    "type": "session_list",
                                    "sessions": sessions,
                                    "current_session": cur_id,
                                }))

                            elif data.get("type") == "switch_session":
                                # Técnico quiere cambiar a otra sesión Windows
                                target_id = int(data.get("session_id", 1))
                                cur_id = get_current_session_id()
                                if target_id == cur_id:
                                    logger.info("[SESSION] Ya estamos en sesión %d", target_id)
                                else:
                                    logger.info("[SESSION] Switch → sesión %d", target_id)
                                    ok = request_session_switch(target_id)
                                    if ok:
                                        pass

                        except Exception as cmd_error:
                            logger.error("[CMD ERROR] Error ejecutando %s: %s", data.get('type'), cmd_error, exc_info=True)

                except Exception as e:
                    print(f"Error recibiendo comando: {e}")
                finally:
                    ACTIVE_WEBSOCKET = None
                    HAS_ACTIVE_VIEWER = False
                    telemetry_task.cancel()
                    video_task.cancel()

        except Exception as e:
            if lbl_status:
                try:
                    lbl_status.config(text=f"Estado: Buscando Servidor Web...", fg="#ef4444")
                except Exception:
                    pass
            logger.error("[WS] Desconexion. Reintentando en %ds: %s", reconnect_delay, e)
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)  # Backoff exponencial: max 60s


async def hq_stream_loop(device_id: int, license_key: str):
    """Loop de streaming H.264 de Alto Rendimiento — V2 (FPS estables)."""
    global HQ_MODE_ACTIVE, HQ_FFMPEG_PROC
    import subprocess, asyncio, websockets as _ws, struct, ctypes

    if not os.path.exists(FFMPEG_PATH):
        logger.error("[HQ] ffmpeg.exe no encontrado en %s — modo HQ no disponible", FFMPEG_PATH)
        HQ_MODE_ACTIVE = False
        return

    # Habilitar timer de alta resolución en Windows
    _set_high_res_timer(True)
    logger.info("[HQ] Iniciando stream H.264 V2 (50 FPS Mode)")

    base_url = SERVER_WS_URL
    import re
    m = re.match(r'(wss?://[^/]+)', base_url)
    host = m.group(1) if m else 'ws://localhost:8001'
    hq_url = f"{host}/api/ws/centinela/{device_id}?license_key={license_key}&hq=1&device_id={device_id}"

    # Obtener dimensiones reales para captura 1:1
    user32 = ctypes.windll.user32
    sw_raw = user32.GetSystemMetrics(0)
    sh_raw = user32.GetSystemMetrics(1)
    target_w, target_h = sw_raw, sh_raw
    logger.info(f"[HQ] Captura 1:1 activa (FFmpeg escala): {target_w}x{target_h}")

    frame_size_bgr24 = target_w * target_h * 3

    # --- DETECTAR ENCODER DISPONIBLE (GPU > CPU) ---
    def _detect_best_encoder():
        for enc, extra in [
            ('h264_nvenc',  ['-preset', 'p1', '-tune', 'll', '-rc', 'vbr', '-cq', '28']),
            ('h264_amf',    ['-quality', 'speed']),
            ('h264_qsv',    ['-preset', 'veryfast', '-global_quality', '28']),
            ('libx264',     ['-preset', 'ultrafast', '-tune', 'zerolatency', '-crf', '28']),
        ]:
            try:
                test = subprocess.run(
                    [FFMPEG_PATH, '-f', 'lavfi', '-i', 'nullsrc=s=16x16:d=0.1', '-c:v', enc, '-f', 'null', '-'],
                    capture_output=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if test.returncode == 0:
                    return (['-c:v', enc] + extra, enc)
            except: pass
        return (['-c:v', 'libx264', '-preset', 'ultrafast', '-tune', 'zerolatency'], 'libx264-fallback')

    encoder_args, encoder_name = _detect_best_encoder()
    logger.info(f"[HQ] Encoder seleccionado: {encoder_name}")

    TARGET_FPS = 50  # 50 FPS estables y reales
    KEYFRAME_INTERVAL = TARGET_FPS

    ffmpeg_cmd = [
        FFMPEG_PATH, '-y',
        '-probesize', '32',
        '-analyzeduration', '0',
        '-f', 'rawvideo',
        '-vcodec', 'rawvideo',
        '-s', f"{target_w}x{target_h}",
        '-pix_fmt', 'bgr24',
        '-framerate', str(TARGET_FPS),
        '-i', '-',
        '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2', # Asegurar dimensiones pares para H.264
    ] + encoder_args + [
        '-g', str(KEYFRAME_INTERVAL),
        '-keyint_min', str(KEYFRAME_INTERVAL),
        '-sc_threshold', '0',
        '-pix_fmt', 'yuv420p',
        '-f', 'mp4',
        '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
        'pipe:1'
    ]

    log_path = os.path.join(os.path.dirname(_LOG_FILE), 'ffmpeg_hq.log')
    try: hq_log_file = open(log_path, 'wb')
    except: hq_log_file = subprocess.DEVNULL

    try:
        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=hq_log_file, bufsize=10**7)
        HQ_FFMPEG_PROC = proc
    except Exception as e:
        logger.error("[HQ] No se pudo iniciar ffmpeg: %s", e)
        return

    FRAME_TIME = 1.0 / TARGET_FPS

    async def capture_and_feed():
        global HQ_MODE_ACTIVE
        try:
            logger.warning(f"[HQ] Usando motor GDI a {TARGET_FPS} FPS, {target_w}x{target_h}")
            gdi32 = ctypes.windll.gdi32
            hdc_screen = gdi32.CreateDCA(b'DISPLAY', None, None, None)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbm = gdi32.CreateCompatibleBitmap(hdc_screen, target_w, target_h)
            gdi32.SelectObject(hdc_mem, hbm)
            bmi = struct.pack('<IiiHHIIiiII', 40, target_w, -target_h, 1, 24, 0, frame_size_bgr24, 0, 0, 0, 0)

            last_frame_hash_quick = 0
            buf = (ctypes.c_char * frame_size_bgr24)()
            mv_buf = memoryview(buf)
            
            try:
                while HQ_MODE_ACTIVE and proc.poll() is None:
                    t0 = time.perf_counter()
                    gdi32.BitBlt(hdc_mem, 0, 0, target_w, target_h, hdc_screen, 0, 0, 0x00CC0020)
                    gdi32.GetDIBits(hdc_mem, hbm, 0, target_h, buf, bmi, 0)

                    sample = mv_buf[::max(1, frame_size_bgr24 // 1024)][:1024]
                    h = hash(sample.tobytes())
                    
                    if h != last_frame_hash_quick:
                        last_frame_hash_quick = h
                        try:
                            proc.stdin.write(buf.raw)
                        except: break
                    
                    elapsed = time.perf_counter() - t0
                    await asyncio.sleep(max(0.001, FRAME_TIME - elapsed))
            finally:
                gdi32.DeleteDC(hdc_mem); gdi32.DeleteDC(hdc_screen); gdi32.DeleteObject(hbm)
        except Exception as e:
            logger.error("[HQ] Error en hilo de captura: %s", e)

    asyncio.create_task(capture_and_feed())

    async def run_with_hq_ws():
        loop = asyncio.get_event_loop()
        try:
            async with _ws.connect(hq_url, ping_interval=20, open_timeout=30.0) as ws_hq:
                logger.info(f"[HQ] Stream conectado al Backend. Enviando {TARGET_FPS} FPS estables...")

                CHUNK_SIZE = 16384
                last_data_time = time.time()

                while HQ_MODE_ACTIVE and proc.poll() is None:
                    # read1() devuelve lo que haya disponible sin esperar llenar buffer
                    try:
                        chunk = await asyncio.wait_for(
                            loop.run_in_executor(None, proc.stdout.read1, CHUNK_SIZE),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        if proc.poll() is not None:
                            break
                        continue
                    except Exception:
                        break

                    if not chunk:
                        if time.time() - last_data_time > 10.0:
                            logger.warning("[HQ] Sin datos de ffmpeg por 10s")
                            break
                        await asyncio.sleep(0.01)
                        continue

                    last_data_time = time.time()
                    try:
                        await ws_hq.send(chunk)
                    except: break
        except Exception as e:
            logger.error("[HQ] Error de red en stream: %s", e)

    try:
        await run_with_hq_ws()
    finally:
        HQ_MODE_ACTIVE = False
        HQ_FFMPEG_PROC = None
        _set_high_res_timer(False)
        try: proc.terminate()
        except: pass
        logger.info(f"[HQ] Stream Finalizado. FFmpeg return code: {proc.poll() if 'proc' in locals() else 'N/A'}")
# ------------- ENVIADOR THREAD-SAFE DE MENSAJES WEBSOCKET -------------
def send_ws_message_threadsafe(payload):
    global ACTIVE_WEBSOCKET, ASYNC_LOOP
    if ACTIVE_WEBSOCKET and ASYNC_LOOP:
        async def send_task():
            try:
                await ACTIVE_WEBSOCKET.send(json.dumps(payload))
            except Exception as e:
                print(f"Error enviando mensaje WS: {e}")
        asyncio.run_coroutine_threadsafe(send_task(), ASYNC_LOOP)

LAST_LOCAL_CLIPBOARD = ""

def set_clipboard_text(text):
    global LAST_LOCAL_CLIPBOARD
    try:
        LAST_LOCAL_CLIPBOARD = text
        # SincronizaciÃ³n nativa de bajo nivel del Portapapeles de Windows (SÃºper robusto y asÃ­ncrono)
        import ctypes
        if ctypes.windll.user32.OpenClipboard(None):
            try:
                ctypes.windll.user32.EmptyClipboard()
                text_bytes = text.encode('utf-16-le') + b'\x00\x00'
                h_global_mem = ctypes.windll.kernel32.GlobalAlloc(0x0002, len(text_bytes))
                if h_global_mem:
                    lp_global_mem = ctypes.windll.kernel32.GlobalLock(h_global_mem)
                    ctypes.memmove(lp_global_mem, text_bytes, len(text_bytes))
                    ctypes.windll.kernel32.GlobalUnlock(h_global_mem)
                    # CF_UNICODETEXT = 13
                    ctypes.windll.user32.SetClipboardData(13, h_global_mem)
            finally:
                ctypes.windll.user32.CloseClipboard()
        
        # SincronizaciÃ³n secundaria en Tkinter
        if ROOT_WINDOW:
            try:
                ROOT_WINDOW.clipboard_clear()
                ROOT_WINDOW.clipboard_append(text)
                ROOT_WINDOW.update()
            except:
                pass
        print("[CLIPBOARD] Portapapeles sincronizado con Ã©xito nativamente en Windows.")
    except Exception as e:
        print(f"[CLIPBOARD] Error en set_clipboard_text: {e}")

def is_running_as_service():
    """
    Detecta si estamos corriendo en Session 0 (servicio Windows sin escritorio).
    Usa ProcessIdToSessionId como mÃ©todo primario â€” es el mÃ¡s confiable:
      Session 0 = proceso de servicio (sin UI)
      Session >= 1 = sesiÃ³n interactiva del usuario (UI permitida)
    """
    try:
        import ctypes
        pid = ctypes.windll.kernel32.GetCurrentProcessId()
        session_id = ctypes.c_ulong(0)
        ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(session_id))
        if session_id.value == 0:
            return True  # Session 0 = definitivamente un servicio
        # Session >= 1: proceso en sesiÃ³n interactiva â†’ tiene UI
        return False
    except Exception:
        return False


def manage_service(action: str):
    """Instala, desinstala, inicia o detiene el servicio de Windows de forma robusta."""
    import subprocess
    import sys

    if getattr(sys, 'frozen', False):
        exe_path = f'"{sys.executable}"'
    else:
        python_exe = sys.executable
        # Preferir pythonw.exe para no abrir consola
        pythonw = python_exe.replace('python.exe', 'pythonw.exe')
        if not os.path.exists(pythonw):
            pythonw = python_exe
        script = os.path.abspath(__file__)
        exe_path = f'"{pythonw}" "{script}"'

    def run_sc(*args):
        # Usar la ruta completa a sc.exe de System32 para evitar redirecciÃ³n WoW64
        # cuando el proceso es 32-bit corriendo en Windows 64-bit
        windir = os.environ.get('SystemRoot', 'C:\\Windows')
        sc_exe = os.path.join(windir, 'System32', 'sc.exe')
        # Si el proceso es x86 en OS x64, acceder a System32 nativo via Sysnative
        sysnative = os.path.join(windir, 'Sysnative', 'sc.exe')
        if os.path.exists(sysnative):
            sc_exe = sysnative
        cmd = [sc_exe] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return result.returncode == 0, result.stdout + result.stderr
        except Exception as e:
            return False, str(e)

    if action == 'install':
        # Borrar instancia previa si existe para evitar conflictos
        run_sc('stop', SERVICE_NAME)
        import time; time.sleep(1)
        run_sc('delete', SERVICE_NAME)
        import time; time.sleep(1)

        ok, out = run_sc(
            'create', SERVICE_NAME,
            'binPath=', exe_path,
            'start=', 'auto',
            'obj=', 'LocalSystem',
            'DisplayName=', SERVICE_DISPLAY
        )
        if ok:
            # PolÃ­tica de recuperaciÃ³n: reiniciar despuÃ©s de 30s en el primer fallo,
            # 60s en el segundo, y 120s en fallos posteriores. Reset contador cada hora.
            run_sc('failure', SERVICE_NAME,
                   'reset=', '3600',
                   'actions=', 'restart/30000/restart/60000/restart/120000')
            run_sc('start', SERVICE_NAME)
            print(f"[SERVICE] Servicio '{SERVICE_DISPLAY}' instalado e iniciado con Ã©xito.")
            return True, "Instalado e iniciado."
        else:
            print(f"[SERVICE] Error instalando: {out}")
            return False, out

    elif action == 'uninstall':
        run_sc('stop', SERVICE_NAME)
        import time; time.sleep(2)
        ok, out = run_sc('delete', SERVICE_NAME)
        print(f"[SERVICE] Desinstalado: {out}")
        return ok, out

    elif action == 'start':
        ok, out = run_sc('start', SERVICE_NAME)
        return ok, out

    elif action == 'stop':
        ok, out = run_sc('stop', SERVICE_NAME)
        return ok, out

    return False, 'AcciÃ³n desconocida'


def run_background_worker(lbl_status):
    # Loop asÃ­ncrono para mantener vivo WebSockets
    global ASYNC_LOOP
    ASYNC_LOOP = asyncio.new_event_loop()
    asyncio.set_event_loop(ASYNC_LOOP)
    ASYNC_LOOP.run_until_complete(send_telemetry(lbl_status))

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def ensure_and_start_embedded_rustdesk():
    return  # DESHABILITADO POR COMPLETO
    import sys, os, subprocess, shutil
    
    # 1. Determinar si estamos en PyInstaller
    if not getattr(sys, 'frozen', False):
        logger.info("[EMBEDDED-RD] Corriendo en modo dev, omitiendo extraccion")
        return
        
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    src_path = os.path.join(base_dir, 'rustdesk.exe')
    
    if not os.path.exists(src_path):
        logger.warning("[EMBEDDED-RD] No se encontro rustdesk.exe embebido")
        return
        
    # Carpeta destino
    dest_dir = r"C:\ProgramData\ApolloSupport\bin"
    if not os.path.exists(dest_dir):
        os.makedirs(dest_dir, exist_ok=True)
        
    dest_path = os.path.join(dest_dir, 'rustdesk.exe')
    
    # Copiar si no existe o si difiere en tamaño
    try:
        if not os.path.exists(dest_path) or os.path.getsize(src_path) != os.path.getsize(dest_path):
            logger.info("[EMBEDDED-RD] Extrayendo rustdesk.exe...")
            shutil.copy2(src_path, dest_path)
    except Exception as e:
        logger.error("[EMBEDDED-RD] Error extrayendo: %s", e)
        
    # 2. Iniciar si no está corriendo
    try:
        # Usar tasklist para ver si ya corre y evitar dependencia psutil si falla
        output = subprocess.check_output('tasklist /FI "IMAGENAME eq rustdesk.exe"', shell=True).decode('utf-8', errors='ignore')
        if 'rustdesk.exe' in output.lower():
            logger.info("[EMBEDDED-RD] RustDesk ya esta corriendo")
            return
    except Exception as e:
        logger.warning("[EMBEDDED-RD] No se pudo verificar si corre: %s", e)
        
    # Iniciar como proceso silencioso en segundo plano
    try:
        logger.info("[EMBEDDED-RD] Iniciando rustdesk.exe en segundo plano...")
        subprocess.Popen([dest_path, "--service"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=0x08000000) # CREATE_NO_WINDOW
    except Exception as e:
        logger.error("[EMBEDDED-RD] Error al iniciar: %s", e)

def main():
    import sys
    
    # Asegurar el motor embebido de RustDesk (DESHABILITADO POR COMPLETO)
    # try:
    #     ensure_and_start_embedded_rustdesk()
    # except Exception as e:
    #     logger.error("[EMBEDDED-RD] Fallo critico en modulo embebido: %s", e)

    # â”€â”€ Instancia Ãºnica: solo puede correr UN companion por sesiÃ³n de usuario â”€â”€
    # Si ya hay uno corriendo, este nuevo proceso sale silenciosamente.
    # Esto evita duplicados cuando tanto el service wrapper como el instalador
    # intentan lanzar el companion al mismo tiempo.
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "Global\\ApolloCentinelaCompanion")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Ya hay una instancia corriendo â€” salir sin hacer nada
        ctypes.windll.kernel32.CloseHandle(_mutex)
        sys.exit(0)

    # --- CLI: soporte para instalaciÃ³n/gestiÃ³n del servicio desde lÃ­nea de comandos ---
    # Uso: ApolloCentinela.exe --install | --uninstall | --start | --stop
    args = sys.argv[1:]
    if args:
        action_map = {
            '--install': 'install', '-install': 'install',
            '--uninstall': 'uninstall', '-uninstall': 'uninstall',
            '--start': 'start', '-start': 'start',
            '--stop': 'stop', '-stop': 'stop',
        }
        action = action_map.get(args[0].lower())
        if action:
            # Para instalar/desinstalar se requieren permisos de administrador
            if not is_admin():
                # Re-lanzar con UAC elevation
                script = sys.executable if getattr(sys, 'frozen', False) else __file__
                ctypes.windll.shell32.ShellExecuteW(None, 'runas', script, ' '.join(sys.argv[1:]), None, 1)
                sys.exit(0)
            ok, msg = manage_service(action)
            print(f"[SERVICE] {action}: ok={ok} {msg}")
            sys.exit(0 if ok else 1)

    # NOTA: El companion NO se auto-eleva a admin.
    # El servicio lo lanza con CreateProcessAsUserW (token del usuario, sin elevar).
    # Ejecutar como admin elevado causaba ghost tray icons y posibles problemas
    # de input injection entre procesos de distinta integridad.



    # Intentar habilitar la polÃ­tica de SAS en el registro de Windows
    enable_sas_policy()

    # --- MODO SERVICIO / HEADLESS: si estamos en Session 0, no mostrar UI ---
    # ApolloCentinelaService.exe (el service wrapper) no llega aquÃ­ â€”
    # este bloque solo protege si por alguna razÃ³n este EXE se carga en Session 0.
    if is_running_as_service():
        print("[CENTINELA] Detectado Session 0. El companion no debe correr aquÃ­. Saliendo.")
        return  # El service wrapper (centinela_svc.py) maneja la conexiÃ³n en Session 0

    # ------------- UI ESTILO TEAMVIEWER (TKinter) -------------
    try:
        root = tk.Tk()
    except Exception as ui_error:
        print(f"[CENTINELA] No se pudo inicializar Tkinter: {ui_error}. Iniciando en modo Headless...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(send_telemetry(None))
        except (KeyboardInterrupt, SystemExit):
            pass
        return

    root.title("ApolloSoporte")
    root.geometry("340x400")
    root.resizable(False, False)
    root.configure(bg="#ffffff")

    # Guardar referencia global del ROOT y Callback de la notificaciÃ³n
    global ROOT_WINDOW, SHOW_FLOATING_PANEL_CALLBACK
    ROOT_WINDOW = root

    # Cargar icono de la ventana de forma segura
    try:
        if hasattr(sys, '_MEIPASS'):
            icon_path = os.path.join(sys._MEIPASS, 'apollo_logo.ico')
        else:
            icon_path = os.path.join(os.path.dirname(__file__), 'apollo_logo.ico')
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception as e:
        print(f"Error cargando icono: {e}")

    # TÃ­tulo Corporativo
    lbl_title = tk.Label(root, text="ApolloGesCom", font=("Arial", 16, "bold"), bg="#ffffff", fg="#f59e0b")
    lbl_title.pack(pady=(15, 2))

    lbl_subtitle = tk.Label(root, text="Módulo de Asistencia Activa", font=("Arial", 9), bg="#ffffff", fg="#64748b")
    lbl_subtitle.pack(pady=(0, 5))

    # Info de Compilación (Pedido por usuario para control de versiones)
    lbl_build = tk.Label(root, text=f"Versión: {CLIENT_VERSION} | Build: {BUILD_DATE}", font=("Arial", 7), bg="#ffffff", fg="#94a3b8")
    lbl_build.pack(pady=(0, 10))

    lbl_info = tk.Label(root, text="Dicte este ID al técnico por teléfono:", font=("Arial", 10, "bold"), bg="#ffffff", fg="#334155")
    lbl_info.pack()

    # ID Formateado XXL
    lbl_id = tk.Label(root, text=f"{str(CLIENT_ID)[:3]} {str(CLIENT_ID)[3:]}", font=("Courier", 26, "bold"), bg="#f8fafc", fg="#0f172a", relief="groove", borderwidth=2, padx=10, pady=3)
    lbl_id.pack(pady=5)

    # PIN de Soporte
    lbl_pin_info = tk.Label(root, text=f"PIN de Soporte: {REMOTE_PASSWORD}", font=("Arial", 12, "bold"), bg="#ffffff", fg="#16a34a")
    lbl_pin_info.pack(pady=5)

    # Status Bar
    lbl_status = tk.Label(root, text="Estado: Iniciando motor...", font=("Arial", 9, "bold"), bg="#ffffff", fg="#ea580c")
    lbl_status.pack(side=tk.BOTTOM, pady=10)

    # FunciÃ³n para instalar como servicio de Windows (usa manage_service robusta)
    def install_as_service():
        if not is_admin():
            ctypes.windll.user32.MessageBoxW(0, "Se requieren permisos de Administrador. El programa se relanzarÃ¡ con privilegios elevados.", "ApolloSupport", 0x40)
            script = sys.executable if getattr(sys, 'frozen', False) else __file__
            ctypes.windll.shell32.ShellExecuteW(None, 'runas', script, '--install', None, 1)
            return
        try:
            lbl_status.config(text="Estado: Instalando Servicio...", fg="#2563eb")
            root.update()
            ok, msg = manage_service('install')
            if ok:
                lbl_status.config(text="Estado: âœ… Servicio Instalado y Activo", fg="#16a34a")
                ctypes.windll.user32.MessageBoxW(
                    0,
                    f"Â¡Servicio instalado correctamente!\n\nAhora el Centinela se iniciarÃ¡ automÃ¡ticamente con Windows, incluso tras reinicios.\n\nServicio: {SERVICE_DISPLAY}",
                    "ApolloSupport - Servicio Instalado", 0x40
                )
            else:
                lbl_status.config(text="Estado: Error instalando servicio", fg="#ef4444")
                ctypes.windll.user32.MessageBoxW(0, f"Error al instalar el servicio:\n{msg}", "ApolloSupport", 0x10)
        except Exception as e:
            ctypes.windll.user32.MessageBoxW(0, f"Error inesperado: {e}", "ApolloSupport", 0x10)

    # BotÃ³n para registrar como servicio de Windows
    btn_service = tk.Button(
        root, 
        text="âš™ï¸ Instalar como Servicio Windows", 
        font=("Arial", 10, "bold"), 
        bg="#0284c7", # Azul premium
        fg="#ffffff", 
        activebackground="#0369a1", 
        activeforeground="#ffffff", 
        relief="flat", 
        cursor="hand2",
        padx=10, 
        pady=5, 
        command=install_as_service
    )
    btn_service.pack(pady=5)

    # Arrancar el Socket sin frizar la pantallita
    t = threading.Thread(target=run_background_worker, args=(lbl_status,), daemon=True)
    t.start()

    # --- TRAY ICON LOGIC ---
    def set_enabled(icon, item):
        global IS_ENABLED
        IS_ENABLED = not IS_ENABLED
        lbl_status.config(text=f"Estado: {'Habilitado' if IS_ENABLED else 'Deshabilitado por usuario'}")

    def on_quit(icon, item):
        icon.stop()
        root.destroy()

    def show_window(icon=None, item=None):
        root.deiconify()
        root.state('normal')
        root.lift()

    def minimize_to_tray():
        root.withdraw()

    # Interceptar el botÃ³n de cerrar (X) para que se minimice al tray
    root.protocol('WM_DELETE_WINDOW', minimize_to_tray)

    # Interceptar la minimizaciÃ³n estÃ¡ndar de Windows (-)
    root.bind("<Configure>", lambda event: root.withdraw() if root.state() == 'iconic' else None)

    # Cargar el icono de tray PNG
    try:
        if hasattr(sys, '_MEIPASS'):
            logo_png_path = os.path.join(sys._MEIPASS, 'apollo_logo.png')
        else:
            logo_png_path = os.path.join(os.path.dirname(__file__), 'apollo_logo.png')
            
        if os.path.exists(logo_png_path):
            icon_img = Image.open(logo_png_path)
        else:
            icon_img = Image.new('RGB', (64, 64), color=(245, 158, 11))
    except Exception as e:
        icon_img = Image.new('RGB', (64, 64), color=(245, 158, 11))

    def update_tray_menu(techs):
        global IS_ENABLED
        try:
            menu_items = [
                item('Abrir Soporte', show_window, default=True),
                item('Soporte Habilitado', set_enabled, checked=lambda item: IS_ENABLED),
                item('Chat con TÃ©cnico', lambda: open_chat_menu())
            ]
            if techs:
                menu_items.append(item('--- TÃ©cnicos Conectados ---', lambda: None, enabled=False))
                for tech in techs:
                    menu_items.append(item(f'  â— {tech}', lambda: None, enabled=False))
            menu_items.append(item('Salir', on_quit))
            
            tray_icon.menu = pystray.Menu(*menu_items)
            if techs:
                tray_icon.title = f"ApolloSupport - TÃ©cnicos: {', '.join(techs)}"
            else:
                tray_icon.title = "ApolloSupport: Asistencia Activa"
        except Exception as e:
            print(f"Error actualizando menÃº de tray: {e}")

    def open_chat_menu():
        global FLOATING_PANEL
        if not is_floating_panel_alive():
            if SHOW_FLOATING_PANEL_CALLBACK:
                root.after(0, lambda: SHOW_FLOATING_PANEL_CALLBACK("TÃ©cnico"))
        else:
            root.after(0, lambda: (FLOATING_PANEL.deiconify(), FLOATING_PANEL.lift()))

    tray_icon = pystray.Icon("ApolloSupport", icon_img, "ApolloSupport: Asistencia Activa", menu=pystray.Menu(
        item('Abrir Soporte', show_window, default=True),
        item('Soporte Habilitado', set_enabled, checked=lambda item: IS_ENABLED),
        item('Chat con TÃ©cnico', lambda: open_chat_menu()),
        item('Salir', on_quit)
    ), action=lambda icon: show_window(icon, None))
    
    global UPDATE_TRAY_MENU_CALLBACK
    UPDATE_TRAY_MENU_CALLBACK = update_tray_menu
    
    threading.Thread(target=tray_icon.run, daemon=True).start()

    # --- POPUP FLOTANTE CONTROLADO CON CHAT INTEGRADO ---

    def show_floating_panel(name):
        global IS_ENABLED, FLOATING_PANEL, CHAT_TEXT_WIDGET
        if is_floating_panel_alive():
            try:
                FLOATING_PANEL.destroy()
            except:
                pass
        FLOATING_PANEL = None
        
        # Panel flotante elegante tipo TeamViewer / AnyDesk con Chat integrado
        top = tk.Toplevel(root)
        FLOATING_PANEL = top
        top.title("Soporte Apollo GesCom - Chat")
        top.overrideredirect(False) # Bordes estÃ¡ndar para mover, minimizar y cerrar libremente
        top.protocol("WM_DELETE_WINDOW", lambda: top.withdraw())
        
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        width = 320
        height = 320 # MÃ¡s alto para incluir el historial de chat
        x = screen_width - width - 25
        y = screen_height - height - 55
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.configure(bg="#0f172a") # Slate 900
        
        # Borde coloreado para estÃ©tica premium
        border_frame = tk.Frame(top, bg="#f59e0b", bd=1)
        border_frame.pack(fill=tk.BOTH, expand=True)
        
        inner_frame = tk.Frame(border_frame, bg="#0f172a")
        inner_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Cabecera con tÃ­tulo y botÃ³n de desconexiÃ³n rÃ¡pida
        header_frame = tk.Frame(inner_frame, bg="#1e293b")
        header_frame.pack(fill=tk.X)
        
        lbl_title = tk.Label(
            header_frame, 
            text="Soporte Apollo GesCom", 
            font=("Arial", 9, "bold"), 
            bg="#1e293b", 
            fg="#f59e0b"
        )
        lbl_title.pack(side=tk.LEFT, padx=8, pady=6)
        
        def user_disconnect():
            global IS_ENABLED, FLOATING_PANEL
            IS_ENABLED = False
            top.destroy()
            FLOATING_PANEL = None
            lbl_status.config(text="Estado: Desconectado por usuario", fg="#ef4444")
            # Enviar notificaciÃ³n de desconexiÃ³n al servidor si es posible
            send_ws_message_threadsafe({"type": "client_disconnect"})
            threading.Thread(target=lambda: ctypes.windll.user32.MessageBoxW(0, "Ha cancelado la sesiÃ³n del tÃ©cnico de soporte.", "ApolloSupport", 0x40)).start()

        btn_disc = tk.Button(
            header_frame, 
            text="âœ• Desconectar", 
            font=("Arial", 8, "bold"), 
            bg="#ef4444", 
            fg="#ffffff", 
            activebackground="#dc2626", 
            activeforeground="#ffffff", 
            relief="flat", 
            cursor="hand2",
            padx=6, 
            pady=1, 
            command=user_disconnect
        )
        btn_disc.pack(side=tk.RIGHT, padx=8, pady=4)
        
        # Info del tÃ©cnico
        lbl_tech = tk.Label(
            inner_frame, 
            text=f"ðŸ‘¨â€ðŸ’» TÃ©cnico conectado: {name}", 
            font=("Arial", 8, "bold"), 
            bg="#0f172a", 
            fg="#10b981",
            anchor="w"
        )
        lbl_tech.pack(fill=tk.X, padx=10, pady=(6, 2))
        
        # Historial de Chat
        chat_frame = tk.Frame(inner_frame, bg="#020617")
        chat_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
        
        chat_text = tk.Text(
            chat_frame, 
            bg="#020617", 
            fg="#e2e8f0", 
            font=("Arial", 8), 
            wrap=tk.WORD, 
            bd=0, 
            highlightthickness=0,
            state=tk.DISABLED
        )
        chat_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=4)
        CHAT_TEXT_WIDGET = chat_text
        
        # Agregar scrollbar
        scrollbar = tk.Scrollbar(chat_frame, command=chat_text.yview, width=8, bg="#020617", bd=0, highlightthickness=0)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        chat_text.config(yscrollcommand=scrollbar.set)
        
        # Formatear estilos de texto (Tags)
        chat_text.tag_config("tech", fg="#f59e0b", font=("Arial", 8, "bold"))
        chat_text.tag_config("client", fg="#10b981", font=("Arial", 8, "bold"))
        chat_text.tag_config("system", fg="#94a3b8", font=("Arial", 8, "italic"))
        
        def append_to_chat(sender, message, sender_type):
            chat_text.config(state=tk.NORMAL)
            if sender_type == "tech":
                chat_text.insert(tk.END, f"{sender}: ", "tech")
            elif sender_type == "client":
                chat_text.insert(tk.END, f"TÃº: ", "client")
            else:
                chat_text.insert(tk.END, f"", "system")
            chat_text.insert(tk.END, f"{message}\n")
            chat_text.config(state=tk.DISABLED)
            chat_text.see(tk.END)

    def _capture_gdi():
        """Captura pantalla via CreateDC('DISPLAY') â€” accede al framebuffer
        real del adaptador, funciona en sesiones RDP/WDDM de Windows Server."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            gdi32  = ctypes.windll.gdi32

            user32.GetSystemMetrics.argtypes = [ctypes.c_int]
            user32.GetSystemMetrics.restype = ctypes.c_int

            # Dimensiones de pantalla virtual (soporta multi-monitor)
            w = user32.GetSystemMetrics(78)   # SM_CXVIRTUALSCREEN
            h = user32.GetSystemMetrics(79)   # SM_CYVIRTUALSCREEN
            x = user32.GetSystemMetrics(76)   # SM_XVIRTUALSCREEN
            y = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
            if w <= 0 or h <= 0:
                w = user32.GetSystemMetrics(0)   # SM_CXSCREEN
                h = user32.GetSystemMetrics(1)   # SM_CYSCREEN
                x = y = 0

            if w <= 0 or h <= 0: return None

            # Definir tipos para 64-bit safety & 32-bit stability
            gdi32.CreateDCA.restype = ctypes.c_void_p
            gdi32.CreateDCA.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_void_p]
            user32.GetDesktopWindow.restype = ctypes.c_void_p
            user32.GetWindowDC.argtypes = [ctypes.c_void_p]
            user32.GetWindowDC.restype = ctypes.c_void_p
            user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
            gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
            gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
            gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
            gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            gdi32.SelectObject.restype = ctypes.c_void_p
            gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
            gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
            gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
            gdi32.DeleteDC.argtypes = [ctypes.c_void_p]

            hdc_s_raw = gdi32.CreateDCA(b"DISPLAY", None, None, None)
            use_release_dc = False
            hwnd = None
            if not hdc_s_raw:
                hwnd_raw = user32.GetDesktopWindow()
                hdc_s_raw = user32.GetWindowDC(hwnd_raw)
                if not hdc_s_raw: return None
                hwnd = ctypes.c_void_p(hwnd_raw)
                use_release_dc = True
            
            hdc_s = ctypes.c_void_p(hdc_s_raw)
            hdc_m_raw = gdi32.CreateCompatibleDC(hdc_s)
            if not hdc_m_raw:
                if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
                else: gdi32.DeleteDC(hdc_s)
                return None
            
            hdc_m = ctypes.c_void_p(hdc_m_raw)
            hbm_raw = gdi32.CreateCompatibleBitmap(hdc_s, w, h)
            if not hbm_raw:
                gdi32.DeleteDC(hdc_m)
                if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
                else: gdi32.DeleteDC(hdc_s)
                return None
            
            hbm = ctypes.c_void_p(hbm_raw)
            gdi32.SelectObject(hdc_m, hbm)
            gdi32.BitBlt(hdc_m, 0, 0, w, h, hdc_s, x, y, 0x00CC0020)

            class _BIH(ctypes.Structure):
                _fields_ = [("biSize",ctypes.c_uint32),("biWidth",ctypes.c_int32),
                             ("biHeight",ctypes.c_int32),("biPlanes",ctypes.c_uint16),
                             ("biBitCount",ctypes.c_uint16),("biCompression",ctypes.c_uint32),
                             ("biSizeImage",ctypes.c_uint32),("biXPPM",ctypes.c_int32),
                             ("biYPPM",ctypes.c_int32),("biClrUsed",ctypes.c_uint32),
                             ("biClrImportant",ctypes.c_uint32)]

            bmi = _BIH(biSize=ctypes.sizeof(_BIH), biWidth=w, biHeight=-h,
                       biPlanes=1, biBitCount=32, biCompression=0)
            buf = (ctypes.c_byte * (w * h * 4))()
            gdi32.GetDIBits(hdc_m, hbm, 0, h, buf, ctypes.byref(bmi), 0)

            gdi32.DeleteObject(hbm)
            gdi32.DeleteDC(hdc_m)
            if use_release_dc: user32.ReleaseDC(hwnd, hdc_s)
            else: gdi32.DeleteDC(hdc_s)

            img = Image.frombuffer("RGBX", (w, h), bytes(buf), "raw", "BGRX", 0, 1)
            return img.convert("RGB")
        except Exception as _ge:
            logger.warning("[CAPTURA] GDI error: %s", _ge)
            return None

    def capture_screenshot_thread_func():
        import time
        import hashlib
        import io as _io
        import mss as _mss
        from PIL import Image, ImageGrab
        global LATEST_FRAME, ACTIVE_MONITOR, HQ_MODE_ACTIVE
        last_pixel_hash = None
        motion_frames = 0
        frames_captured = 0
        gdi_failures = 0
        prev_screenshot_dr = None  # DIRTY_RECT: frame anterior para comparaciÃ³n
        _FRAME_BUDGET = 0.08  # ~12 FPS objetivo en captura estÃ¡ndar para ahorrar CPU

        logger.info("[CAPTURA] Thread de captura de pantalla iniciado")

        # Inicializar mss UNA sola vez fuera del loop.
        sct = None
        use_gdi = True
        try:
            sct = _mss.mss()
            logger.info("[CAPTURA] mss inicializado OK (%d monitores detectados)", len(sct.monitors) - 1)
        except Exception as e:
            logger.warning("[CAPTURA] mss no disponible (%s), usando PIL.ImageGrab como fallback", e)
            use_imagegrab = True

        def _is_black_frame(img: 'Image') -> bool:
            """Detecta si el frame es negro (pantalla apagada/sesion inactiva)."""
            try:
                w, h = img.size
                cx, cy = w // 2, h // 2
                pixels = [img.getpixel((cx + dx*20, cy + dy*20))
                          for dx in range(-2, 3) for dy in range(-2, 3)
                          if 0 < cx+dx*20 < w and 0 < cy+dy*20 < h]
                avg = sum(sum(p[:3]) for p in pixels) / (len(pixels) * 3) if pixels else 0
                return avg < 5  # Casi negro
            except Exception:
                return False

        def _capture_printwindow_fallback() -> 'Image | None':
            """Captura usando PrintWindow + BitBlt cuando MSS devuelve pantalla negra.
            Funciona con ventanas minimizadas y sesiones RDP en ciertas condiciones."""
            try:
                import ctypes
                from ctypes import wintypes
                gdi32 = ctypes.windll.gdi32
                user32 = ctypes.windll.user32
                
                # --- PARCHE 64-BIT SAFETY ---
                user32.GetSystemMetrics.argtypes = [ctypes.c_int]
                user32.GetSystemMetrics.restype = ctypes.c_int
                user32.GetDesktopWindow.argtypes = []
                user32.GetDesktopWindow.restype = ctypes.c_void_p
                user32.GetDC.argtypes = [ctypes.c_void_p]
                user32.GetDC.restype = ctypes.c_void_p
                user32.ReleaseDC.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                user32.ReleaseDC.restype = ctypes.c_int
                
                gdi32.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
                gdi32.CreateCompatibleDC.restype = ctypes.c_void_p
                gdi32.CreateCompatibleBitmap.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
                gdi32.CreateCompatibleBitmap.restype = ctypes.c_void_p
                gdi32.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
                gdi32.SelectObject.restype = ctypes.c_void_p
                gdi32.BitBlt.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32]
                gdi32.BitBlt.restype = ctypes.c_int
                gdi32.GetDIBits.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
                gdi32.GetDIBits.restype = ctypes.c_int
                gdi32.DeleteObject.argtypes = [ctypes.c_void_p]
                gdi32.DeleteObject.restype = ctypes.c_int
                gdi32.DeleteDC.argtypes = [ctypes.c_void_p]
                gdi32.DeleteDC.restype = ctypes.c_int
                # -----------------------------

                hwnd = user32.GetDesktopWindow()
                
                w = user32.GetSystemMetrics(0)
                h = user32.GetSystemMetrics(1)
                if w <= 0 or h <= 0: return None
                
                hdc_screen = user32.GetDC(hwnd)
                if not hdc_screen: return None
                
                hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
                if not hdc_mem:
                    user32.ReleaseDC(hwnd, hdc_screen)
                    return None
                    
                hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, w, h)
                if not hbmp:
                    gdi32.DeleteDC(hdc_mem)
                    user32.ReleaseDC(hwnd, hdc_screen)
                    return None
                    
                gdi32.SelectObject(hdc_mem, hbmp)
                SRCCOPY = 0xCC0020
                gdi32.BitBlt(hdc_mem, 0, 0, w, h, hdc_screen, 0, 0, SRCCOPY)
                
                bmi = (ctypes.c_uint32 * 40)()
                bmi[0] = 40
                bmi[1] = w; bmi[2] = -h
                bmi[3] = 1; bmi[4] = 32
                buf = (ctypes.c_char * (w * h * 4))()
                gdi32.GetDIBits(hdc_mem, hbmp, 0, h, buf, ctypes.cast(bmi, ctypes.POINTER(ctypes.c_uint32)), 0)
                img = Image.frombuffer('RGBA', (w, h), bytes(buf), 'raw', 'BGRA')
                
                gdi32.DeleteObject(hbmp)
                gdi32.DeleteDC(hdc_mem)
                user32.ReleaseDC(hwnd, hdc_screen)
                return img.convert('RGB')
            except Exception as e:
                logger.debug("[CAPTURA] PrintWindow fallback fallo: %s", e)
                return None

        while True:
            # OPTIMIZACIÓN EXTREMA: Si no hay técnicos activos ni modo HQ, pausar la captura
            # de pantalla local para ahorrar 100% de CPU y RAM.
            if not HAS_ACTIVE_VIEWER and not HQ_MODE_ACTIVE:
                time.sleep(1.0)
                continue

            if IS_ENABLED:
                _t0 = time.perf_counter()

                try:
                    screenshot = None
                    if use_gdi:
                        screenshot = _capture_gdi()
                        if screenshot is None:
                            gdi_failures += 1
                            if gdi_failures % 30 == 1:
                                logger.warning("[CAPTURA] GDI no disponible en esta sesion, usando mss/ImageGrab")
                            use_gdi = False

                    if not use_gdi:
                        if use_imagegrab or sct is None:
                            screenshot = ImageGrab.grab()
                        else:
                            monitor_idx = ACTIVE_MONITOR
                            if monitor_idx >= len(sct.monitors):
                                monitor_idx = 1
                            monitor = sct.monitors[monitor_idx]
                            sct_img = sct.grab(monitor)
                            screenshot = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                            # Fallback si la captura es negra (ventana minimizada / RDP inactivo)
                            if _is_black_frame(screenshot):
                                alt = _capture_printwindow_fallback()
                                if alt and not _is_black_frame(alt):
                                    screenshot = alt

                    with STREAM_OPTS_LOCK:
                        mw_cap = STREAM_OPTS["max_width"]
                        w_still = STREAM_OPTS["webp_still"]
                        w_motion = STREAM_OPTS["webp_motion"]
                    if mw_cap and screenshot is not None:
                        fw, fh = screenshot.size
                        if fw > mw_cap:
                            nh = max(1, int(round(fh * mw_cap / fw)))
                            screenshot = screenshot.resize(
                                (mw_cap, nh), Image.Resampling.BILINEAR
                            )

                    diff_bbox = None
                    if prev_screenshot_dr is not None:
                        from PIL import ImageChops as _IChops
                        diff_bbox = _IChops.difference(screenshot, prev_screenshot_dr).getbbox()
                        
                        if diff_bbox is None and not FORCE_NEXT_FRAME:
                            elapsed = time.perf_counter() - _t0
                            time.sleep(max(0.002, _FRAME_BUDGET - elapsed))
                            continue
                            
                    FORCE_NEXT_FRAME = False

                    motion_frames = min(motion_frames + 1, 10)

                    # Para revertir: borrar este bloque y descomentar el bloque
                    # ROLLBACK que estÃ¡ debajo marcado con DIRTY_RECT_ROLLBACK.
                    #
                    # LÃ³gica:
                    # 1. Si tenemos frame anterior: detectar el rectÃ¡ngulo sucio
                    #    usando ImageChops.difference().getbbox() â€” O(pixels), nativo PIL.
                    # 2. Si el rect sucio cubre < 65% del Ã¡rea total: encodear solo el crop.
                    # 3. Si cubre â‰¥ 65% (o es el primer frame): encodear frame completo.
                    # 4. LATEST_FRAME siempre = frame completo (HTTP polling sin cambios).
                    # 5. LATEST_FRAME_PACKET = {"frame": ..., "delta": {...} | None}
                    webp_quality = w_motion if motion_frames > 4 else w_still
                    delta_meta   = None
                    encode_img   = screenshot  # por defecto: frame completo

                    if USE_DIRTY_RECT and diff_bbox:
                        x1, y1, x2, y2 = diff_bbox
                        fw, fh = screenshot.size
                        dw, dh = x2 - x1, y2 - y1
                        # Solo mandar delta si ahorra más del 35% del área
                        if (dw * dh) < (fw * fh * 0.65):
                            encode_img = screenshot.crop(diff_bbox)
                            delta_meta = {"x": x1, "y": y1,
                                          "w": dw, "h": dh,
                                          "fw": fw, "fh": fh}
                            logger.debug("[DR] delta %dx%d @ (%d,%d) — %.0f%% del frame",
                                         dw, dh, x1, y1, 100.0*dw*dh/(fw*fh))

                    prev_screenshot_dr = screenshot  # Guardar para prÃ³xima comparaciÃ³n

                    img_byte_arr = _io.BytesIO()
                    try:
                        # method=0: encode ~5ms (vs method=4: ~50ms). Ligero aumento de tamaÃ±o
                        # pero la ganancia de latencia es enorme. Para revertir: method=4.
                        encode_img.save(img_byte_arr, format='WEBP', quality=webp_quality, method=0)
                    except Exception:
                        img_byte_arr = _io.BytesIO()
                        jq = w_motion if motion_frames > 4 else w_still
                        jpeg_quality = max(35, min(92, int(jq * 0.58)))
                        encode_img.save(img_byte_arr, format='JPEG', quality=jpeg_quality, optimize=True)

                    encoded_b64 = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')

                    if delta_meta:
                        LATEST_FRAME_PACKET = {"frame": encoded_b64, "delta": delta_meta, "id": time.perf_counter()}
                    else:
                        LATEST_FRAME = encoded_b64
                        LATEST_FRAME_PACKET = {"frame": encoded_b64, "delta": None, "id": time.perf_counter()}

                    # â”€â”€ DIRTY_RECT_END â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

                    # â”€â”€ DIRTY_RECT_ROLLBACK (descomentar para revertir) â”€â”€â”€â”€â”€â”€â”€â”€
                    # webp_quality = 55 if motion_frames > 4 else 80
                    # img_byte_arr = _io.BytesIO()
                    # try:
                    #     screenshot.save(img_byte_arr, format='WEBP', quality=webp_quality, method=4)
                    # except Exception:
                    #     img_byte_arr = _io.BytesIO()
                    #     jpeg_quality = 45 if motion_frames > 4 else 75
                    #     screenshot.save(img_byte_arr, format='JPEG', quality=jpeg_quality, optimize=True)
                    # LATEST_FRAME = base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')
                    # â”€â”€ FIN ROLLBACK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

                    frames_captured += 1
                    if frames_captured == 1:
                        logger.info("[CAPTURA] Primer frame capturado OK")
                    elif frames_captured % 500 == 0:
                        logger.info("[CAPTURA] %d frames capturados", frames_captured)

                    motion_frames = max(motion_frames - 1, 0)

                except Exception as e:
                    logger.error("[CAPTURA] Error: %s", e)
                    if not use_imagegrab and not use_gdi:
                        logger.warning("[CAPTURA] Cambiando a PIL.ImageGrab como fallback")
                        use_imagegrab = True
                    elif use_imagegrab and not use_gdi:
                        logger.warning("[CAPTURA] PIL.ImageGrab falla, cambiando a GDI nativo")
                        use_gdi = True
                        use_imagegrab = False
                    time.sleep(1.0)
            else:
                LATEST_FRAME = None
                motion_frames = 0
                last_pixel_hash = None

            # Sleep dinámico: mantiene ~30 FPS (HQ Turbo) o ~12 FPS (Estándar) descontando el tiempo de encode
            _current_budget = 0.033 if HQ_MODE_ACTIVE else _FRAME_BUDGET
            _elapsed = time.perf_counter() - _t0
            time.sleep(max(0.002, _current_budget - _elapsed))

    threading.Thread(target=capture_screenshot_thread_func, daemon=True).start()

    def monitor_clipboard_changes():
        global LAST_LOCAL_CLIPBOARD
        if IS_ENABLED:
            try:
                current_clipboard = root.clipboard_get()
                if current_clipboard and current_clipboard != LAST_LOCAL_CLIPBOARD:
                    LAST_LOCAL_CLIPBOARD = current_clipboard
                    # Enviar el portapapeles local al servidor de forma asÃ­ncrona y segura
                    send_ws_message_threadsafe({
                        "type": "clipboard_sync",
                        "text": current_clipboard
                    })
                    print("[CLIPBOARD] Portapapeles local del cliente sincronizado al servidor.")
            except Exception:
                pass
        root.after(1000, monitor_clipboard_changes)

    monitor_clipboard_changes()

    root.mainloop()

if __name__ == "__main__":
    main()




