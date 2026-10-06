"""
Apollo Centinela - Service Wrapper
===================================
Corre como Windows Service (Session 0, SYSTEM).
- Mantiene la conexion WebSocket con el backend SIEMPRE (incluso sin usuario logueado)
- Cuando detecta un usuario activo, lanza ApolloCentinela.exe en esa sesion (tray icon)
- Si el companion cae, lo reinicia automaticamente
- Si el usuario cierra sesion, mata el companion y espera el siguiente login
"""
import sys
import os
import asyncio
import ctypes
import ctypes.wintypes
import subprocess
import threading
import time
import json
import websockets
import socket
import platform
import psutil
import logging
import logging.handlers

# ── Configuracion ─────────────────────────────────────────────────────────────
SERVICE_NAME    = "ApolloCentinela"
__version__     = "3.3.39"
SERVICE_MUTEX_NAME = "Global\\ApolloCentinelaService"
ERROR_ALREADY_EXISTS = 183
BASE_DIR        = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_DIR      = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport")
CONFIG_FILE     = os.path.join(CONFIG_DIR, "centinela.dat")
LEGACY_CONFIG   = os.path.join(CONFIG_DIR, "centinela_config.json")
LOG_FILE        = os.path.join(CONFIG_DIR, "service.log")
COMPANION_EXE   = os.path.normpath(os.path.join(BASE_DIR, "ApolloCentinela.exe"))
# Nombres de ejecutables legacy / copias sueltas (ej. c:\Gescom28\) que deben cerrarse al actualizar
COMPANION_IMAGE_NAMES = frozenset({
    "apollocentinela.exe",
    "apollo_centinela.exe",
    "apollegescombeta.exe",
    "apollegescom.exe",
    "apollosoporte.exe",
    "apollosupport.exe",
})
os.makedirs(CONFIG_DIR, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
logger = logging.getLogger("ApolloSvc")
logger.setLevel(logging.INFO)
_handler = logging.handlers.RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=3, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logger.addHandler(_handler)

# ── Config local ──────────────────────────────────────────────────────────────
import base64

def xor_crypt(data: str, key: str = "Ap0ll0$ecr3t_2026!") -> str:
    key_len = len(key)
    return "".join(chr(ord(c) ^ ord(key[i % key_len])) for i, c in enumerate(data))

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                content = f.read()
            decrypted = xor_crypt(base64.b64decode(content.encode()).decode())
            return json.loads(decrypted)
        except Exception:
            pass
            
    if os.path.exists(LEGACY_CONFIG):
        try:
            with open(LEGACY_CONFIG, "r") as f:
                return json.load(f)
        except Exception:
            pass
    import random
    cfg = {
        "device_name": socket.gethostname(),
        "client_id": random.randint(100000, 999999),
        "license_key": "",
        "base_ws_url": "wss://support.ultimate.net.ar/api/ws/centinela"
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f)
    return cfg

# ── WinAPI: lanzar proceso en sesion interactiva del usuario ──────────────────
WTSAPI32  = ctypes.windll.wtsapi32
KERNEL32  = ctypes.windll.kernel32
ADVAPI32  = ctypes.windll.advapi32
USERENV   = ctypes.windll.userenv
WTSAPI32.WTSQueryUserToken.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.HANDLE)]
WTSAPI32.WTSQueryUserToken.restype = ctypes.wintypes.BOOL

# KERNEL32
KERNEL32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]
KERNEL32.CloseHandle.restype = ctypes.wintypes.BOOL

KERNEL32.OpenProcess.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.BOOL, ctypes.wintypes.DWORD]
KERNEL32.OpenProcess.restype = ctypes.wintypes.HANDLE

KERNEL32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE

KERNEL32.WTSGetActiveConsoleSessionId.argtypes = []
KERNEL32.WTSGetActiveConsoleSessionId.restype = ctypes.wintypes.DWORD

KERNEL32.GetProcessId.argtypes = [ctypes.wintypes.HANDLE]
KERNEL32.GetProcessId.restype = ctypes.wintypes.DWORD

KERNEL32.GetExitCodeProcess.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(ctypes.wintypes.DWORD)]
KERNEL32.GetExitCodeProcess.restype = ctypes.wintypes.BOOL

KERNEL32.ProcessIdToSessionId.argtypes = [ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.DWORD)]
KERNEL32.ProcessIdToSessionId.restype = ctypes.wintypes.BOOL

KERNEL32.WaitForSingleObject.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD]
KERNEL32.WaitForSingleObject.restype = ctypes.wintypes.DWORD

KERNEL32.TerminateProcess.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.UINT]
KERNEL32.TerminateProcess.restype = ctypes.wintypes.BOOL

# ADVAPI32
ADVAPI32.OpenProcessToken.argtypes = [ctypes.wintypes.HANDLE, ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.HANDLE)]
ADVAPI32.OpenProcessToken.restype = ctypes.wintypes.BOOL

ADVAPI32.LookupPrivilegeValueW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int64)]
ADVAPI32.LookupPrivilegeValueW.restype = ctypes.wintypes.BOOL

ADVAPI32.AdjustTokenPrivileges.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.BOOL,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_void_p
]
ADVAPI32.AdjustTokenPrivileges.restype = ctypes.wintypes.BOOL

ADVAPI32.DuplicateTokenEx.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(ctypes.wintypes.HANDLE)
]
ADVAPI32.DuplicateTokenEx.restype = ctypes.wintypes.BOOL

ADVAPI32.SetTokenInformation.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.c_int,
    ctypes.c_void_p,
    ctypes.wintypes.DWORD
]
ADVAPI32.SetTokenInformation.restype = ctypes.wintypes.BOOL

ADVAPI32.CreateProcessAsUserW.argtypes = [
    ctypes.wintypes.HANDLE,
    ctypes.wintypes.LPCWSTR,
    ctypes.wintypes.LPWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.wintypes.BOOL,
    ctypes.wintypes.DWORD,
    ctypes.c_void_p,
    ctypes.wintypes.LPCWSTR,
    ctypes.c_void_p,
    ctypes.c_void_p
]
ADVAPI32.CreateProcessAsUserW.restype = ctypes.wintypes.BOOL

# USERENV
USERENV.CreateEnvironmentBlock.argtypes = [ctypes.POINTER(ctypes.c_void_p), ctypes.wintypes.HANDLE, ctypes.wintypes.BOOL]
USERENV.CreateEnvironmentBlock.restype = ctypes.wintypes.BOOL

USERENV.DestroyEnvironmentBlock.argtypes = [ctypes.c_void_p]
USERENV.DestroyEnvironmentBlock.restype = ctypes.wintypes.BOOL

class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb",              ctypes.wintypes.DWORD),
        ("lpReserved",      ctypes.wintypes.LPWSTR),
        ("lpDesktop",       ctypes.wintypes.LPWSTR),
        ("lpTitle",         ctypes.wintypes.LPWSTR),
        ("dwX",             ctypes.wintypes.DWORD),
        ("dwY",             ctypes.wintypes.DWORD),
        ("dwXSize",         ctypes.wintypes.DWORD),
        ("dwYSize",         ctypes.wintypes.DWORD),
        ("dwXCountChars",   ctypes.wintypes.DWORD),
        ("dwYCountChars",   ctypes.wintypes.DWORD),
        ("dwFillAttribute", ctypes.wintypes.DWORD),
        ("dwFlags",         ctypes.wintypes.DWORD),
        ("wShowWindow",     ctypes.wintypes.WORD),
        ("cbReserved2",     ctypes.wintypes.WORD),
        ("lpReserved2",     ctypes.POINTER(ctypes.c_byte)),
        ("hStdInput",       ctypes.wintypes.HANDLE),
        ("hStdOutput",      ctypes.wintypes.HANDLE),
        ("hStdError",       ctypes.wintypes.HANDLE),
    ]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess",    ctypes.wintypes.HANDLE),
        ("hThread",     ctypes.wintypes.HANDLE),
        ("dwProcessId", ctypes.wintypes.DWORD),
        ("dwThreadId",  ctypes.wintypes.DWORD),
    ]

def get_active_session_id():
    """
    Retorna el ID de la primera sesion WTS activa con un usuario logueado.
    - En PC de escritorio: generalmente Session 1 (consola).
    - En Windows Server con RDP: puede ser Session 2, 3, etc.
    WTSGetActiveConsoleSessionId() solo devuelve la sesion de consola FISICA,
    que en servidores RDP esta vacia. Usamos WTSEnumerateSessions para encontrar
    la sesion real del usuario.
    """
    # Tipos de sesion WTS relevantes
    WTS_CURRENT_SERVER_HANDLE = None
    WTSActive = 0  # Estado activo

    class WTS_SESSION_INFO(ctypes.Structure):
        _fields_ = [
            ("SessionId",     ctypes.wintypes.DWORD),
            ("pWinStationName", ctypes.c_wchar_p),
            ("State",         ctypes.c_int),
        ]

    pSessionInfo = ctypes.POINTER(WTS_SESSION_INFO)()
    count = ctypes.wintypes.DWORD(0)

    if not WTSAPI32.WTSEnumerateSessionsW(
        WTS_CURRENT_SERVER_HANDLE, 0, 1,
        ctypes.byref(pSessionInfo), ctypes.byref(count)
    ):
        # Fallback a consola si la enumeración falla
        return KERNEL32.WTSGetActiveConsoleSessionId()

    best_session = 0xFFFFFFFF
    try:
        for i in range(count.value):
            s = pSessionInfo[i]
            if s.State == WTSActive and s.SessionId != 0:
                # Verificar que haya un usuario real en esta sesion
                user_token = ctypes.wintypes.HANDLE()
                if WTSAPI32.WTSQueryUserToken(s.SessionId, ctypes.byref(user_token)):
                    KERNEL32.CloseHandle(user_token)
                    best_session = s.SessionId
                    break  # Tomar la primera sesion activa con usuario
    finally:
        WTSAPI32.WTSFreeMemory(pSessionInfo)

    # Si no encontramos ninguna sesion RDP activa, fallback a consola
    if best_session == 0xFFFFFFFF:
        best_session = KERNEL32.WTSGetActiveConsoleSessionId()

    return best_session

# Accesos Win32 usados al abrir/duplicar tokens
TOKEN_DUPLICATE        = 0x0002
TOKEN_QUERY            = 0x0008
TOKEN_ASSIGN_PRIMARY   = 0x0001
TOKEN_ADJUST_PRIVILEGES = 0x0020
MAXIMUM_ALLOWED        = 0x02000000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TokenSessionId         = 12
SecurityImpersonation  = 2
TokenPrimary           = 1

# KERNEL32.GetCurrentProcess.restype ya esta definida arriba


class WTS_PROCESS_INFOW(ctypes.Structure):
    _fields_ = [
        ("SessionId",     ctypes.wintypes.DWORD),
        ("ProcessId",     ctypes.wintypes.DWORD),
        ("pProcessName",  ctypes.wintypes.LPWSTR),
        ("pUserSid",      ctypes.c_void_p),
    ]


def _enable_privilege(priv_name):
    h_token = ctypes.wintypes.HANDLE()
    if not ADVAPI32.OpenProcessToken(
        KERNEL32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(h_token),
    ):
        return
    try:
        luid = ctypes.c_int64()
        if ADVAPI32.LookupPrivilegeValueW(None, priv_name, ctypes.byref(luid)):
            class TOKEN_PRIVILEGES(ctypes.Structure):
                _fields_ = [
                    ("PrivilegeCount", ctypes.c_uint32),
                    ("Luid", ctypes.c_int64),
                    ("Attributes", ctypes.c_uint32),
                ]
            tp = TOKEN_PRIVILEGES(1, luid.value, 2)
            ADVAPI32.AdjustTokenPrivileges(h_token, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None)
    finally:
        KERNEL32.CloseHandle(h_token)


def _enable_service_token_privileges():
    """Privilegios necesarios para WTSQueryUserToken / winlogon / CreateProcessAsUser."""
    for priv in (
        "SeDebugPrivilege",
        "SeTcbPrivilege",
        "SeAssignPrimaryTokenPrivilege",
        "SeIncreaseQuotaPrivilege",
        "SeImpersonatePrivilege",
    ):
        _enable_privilege(priv)


def _duplicate_primary_token(source_token, session_id=None):
    dup = ctypes.wintypes.HANDLE()
    if not ADVAPI32.DuplicateTokenEx(
        source_token,
        MAXIMUM_ALLOWED,
        None,
        SecurityImpersonation,
        TokenPrimary,
        ctypes.byref(dup),
    ):
        return None
    if session_id is not None:
        sid = ctypes.c_uint32(int(session_id))
        _enable_privilege("SeTcbPrivilege")
        _enable_privilege("SeAssignPrimaryTokenPrivilege")
        _enable_privilege("SeIncreaseQuotaPrivilege")
        if not ADVAPI32.SetTokenInformation(
            dup, TokenSessionId, ctypes.byref(sid), ctypes.sizeof(sid)
        ):
            err = KERNEL32.GetLastError()
            KERNEL32.CloseHandle(dup)
            logger.error("SetTokenInformation(TokenSessionId=%d) fallo (error %d)", session_id, err)
            return None
    return dup


def _open_process_token_from_pid(pid, label):
    """Abre token duplicable de un proceso (winlogon/explorer)."""
    access = PROCESS_QUERY_LIMITED_INFORMATION | 0x1000  # PROCESS_QUERY_INFORMATION
    h_proc = KERNEL32.OpenProcess(access, False, int(pid))
    if not h_proc:
        logger.warning(
            "OpenProcess(%s pid=%d) fallo (error %d)",
            label, pid, KERNEL32.GetLastError(),
        )
        return None
    h_tok = ctypes.wintypes.HANDLE()
    try:
        if not ADVAPI32.OpenProcessToken(
            h_proc, TOKEN_DUPLICATE | TOKEN_QUERY, ctypes.byref(h_tok)
        ):
            logger.warning(
                "OpenProcessToken(%s pid=%d) fallo (error %d)",
                label, pid, KERNEL32.GetLastError(),
            )
            return None
        return h_tok
    finally:
        KERNEL32.CloseHandle(h_proc)


def _token_from_process_in_session(session_id, image_name):
    proc_info = ctypes.POINTER(WTS_PROCESS_INFOW)()
    count = ctypes.wintypes.DWORD(0)
    if not WTSAPI32.WTSEnumerateProcessesW(None, 0, 1, ctypes.byref(proc_info), ctypes.byref(count)):
        return None
    token = None
    want = image_name.lower()
    try:
        for i in range(count.value):
            p = proc_info[i]
            if int(p.SessionId) != int(session_id):
                continue
            name = (p.pProcessName or "").lower()
            if name != want:
                continue
            token = _open_process_token_from_pid(int(p.ProcessId), name)
            if token:
                break
    finally:
        WTSAPI32.WTSFreeMemory(proc_info)
    return token


def _token_from_winlogon_in_session(session_id):
    """(token, from_explorer). Explorer = UI; winlogon = pantalla de login."""
    _enable_service_token_privileges()
    token = _token_from_process_in_session(session_id, "explorer.exe")
    if token:
        logger.info("Token obtenido desde explorer.exe en sesion %d", session_id)
        return token, True
    token = _token_from_process_in_session(session_id, "winlogon.exe")
    if token:
        logger.info("Token obtenido desde winlogon.exe en sesion %d", session_id)
        return token, False
    return None, False


def _session_has_explorer(session_id):
    """True si hay explorer.exe en la sesion (usuario con escritorio visible)."""
    try:
        for p in psutil.process_iter(["name"]):
            try:
                if (p.info.get("name") or "").lower() != "explorer.exe":
                    continue
                if int(p.SessionId) == int(session_id):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, TypeError, ValueError):
                continue
    except Exception as e:
        logger.debug("_session_has_explorer: %s", e)
    tok = _token_from_process_in_session(session_id, "explorer.exe")
    if tok:
        try:
            KERNEL32.CloseHandle(tok)
        except Exception:
            pass
        return True
    return False


def _token_from_service_session(session_id):
    """Token SYSTEM del servicio, reasignado a la sesion destino."""
    h_tok = ctypes.wintypes.HANDLE()
    if not ADVAPI32.OpenProcessToken(
        KERNEL32.GetCurrentProcess(),
        TOKEN_DUPLICATE | TOKEN_QUERY | TOKEN_ASSIGN_PRIMARY,
        ctypes.byref(h_tok),
    ):
        logger.error("OpenProcessToken(SYSTEM) fallo (error %d)", KERNEL32.GetLastError())
        return None
    dup = _duplicate_primary_token(h_tok, session_id)
    KERNEL32.CloseHandle(h_tok)
    if dup:
        logger.info("Token SYSTEM duplicado para sesion %d", session_id)
    return dup


def obtain_launch_token(session_id, force_system=False):
    """
    Devuelve (handle_token_primario, has_user_token) o (None, False).
    has_user_token=True => lanzar con ventana/tray (escritorio default).
    """
    _enable_service_token_privileges()
    if not force_system:
        user_token = ctypes.wintypes.HANDLE()
        if WTSAPI32.WTSQueryUserToken(int(session_id), ctypes.byref(user_token)):
            dup = _duplicate_primary_token(user_token, session_id)
            KERNEL32.CloseHandle(user_token)
            if dup:
                return dup, True

        err = KERNEL32.GetLastError()
        logger.warning(
            "WTSQueryUserToken fallo (error %d) en sesion %d; probando explorer/winlogon/SYSTEM",
            err, session_id,
        )

    wl, from_explorer = _token_from_winlogon_in_session(session_id)
    if wl:
        dup = _duplicate_primary_token(wl, session_id)
        KERNEL32.CloseHandle(wl)
        if dup:
            return dup, bool(from_explorer)

    dup = _token_from_service_session(session_id)
    interactive = _session_has_explorer(session_id)
    return (dup, interactive) if dup else (None, False)


def spawn_in_user_session(exe_path, args="", session_id=None):
    """
    Lanza exe_path en la sesion interactiva del usuario usando WTSQueryUserToken.
    Retorna el handle del proceso o None si falla.
    """
    exe_path = os.path.normpath(os.path.abspath(exe_path))
    if not os.path.isfile(exe_path):
        logger.error(
            "Companion EXE no encontrado (error Win32 2 suele ser esto). Ruta esperada: %s | Carpeta servicio: %s",
            exe_path,
            BASE_DIR,
        )
        return None

    if session_id is None:
        session_id = get_active_session_id()
    session_id = normalize_windows_session_id(session_id)
    if session_id == 0xFFFFFFFF:
        session_id = get_console_session_id()
    if session_id == 0xFFFFFFFF:
        session_id = 1

    is_inject_helper = "--inject-helper" in args
    if is_inject_helper:
        # El helper de inyeccion DEBE correr como SYSTEM real (para saltear UIPI y poder
        # operar el UAC / ventanas elevadas). NO usar el token de explorer (integridad media).
        _enable_service_token_privileges()
        dup_token = _token_from_service_session(session_id)
        has_user_token = False
        if not dup_token:
            logger.error("[INJECT] No se pudo obtener token SYSTEM para helper en sesion %d", session_id)
            return None
    else:
        force_sys = "--type-credentials" in args or "--winlogon" in args
        dup_token, has_user_token = obtain_launch_token(session_id, force_system=force_sys)
        if not dup_token:
            logger.error("No se pudo obtener token para lanzar companion en sesion %d", session_id)
            return None

    env_block = ctypes.c_void_p()
    creation_flags = 0
    env_ok = bool(USERENV.CreateEnvironmentBlock(ctypes.byref(env_block), dup_token, False))
    if env_ok:
        creation_flags |= 0x00000400  # CREATE_UNICODE_ENVIRONMENT
    else:
        logger.warning("CreateEnvironmentBlock fallo (error %d), usando entorno heredado", KERNEL32.GetLastError())
        env_block = None

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(STARTUPINFOW)
    spawn_args = args or ""
    explicit_headless = (
        "--type-credentials" in spawn_args.split()
        or "--winlogon" in spawn_args.split()
        or "--headless" in spawn_args.split()
    )
    # Si hay explorer (usuario en RDP/escritorio), NUNCA forzar headless:
    # eso es lo que dejaba el agente online sin tray ni ventana con el ID.
    interactive_desktop = bool(has_user_token) or _session_has_explorer(session_id)
    # El helper de inyeccion SIEMPRE va al escritorio interactivo (winsta0\default),
    # donde aparece el UAC (con PromptOnSecureDesktop=0) y las ventanas elevadas.
    if is_inject_helper:
        interactive_desktop = True
    use_winlogon_desktop = explicit_headless or (
        not interactive_desktop and ("--winlogon" in spawn_args.split() or not has_user_token)
    )

    if use_winlogon_desktop and not interactive_desktop:
        si.lpDesktop = "winsta0\\Winlogon"
    else:
        si.lpDesktop = "winsta0\\default"

    si.dwFlags = 0x00000001   # STARTF_USESHOWWINDOW
    if explicit_headless and not interactive_desktop:
        si.wShowWindow = 0    # SW_HIDE
    else:
        si.wShowWindow = 5    # SW_SHOW — ventana/tray visibles

    pi = PROCESS_INFORMATION()
    work_dir = os.path.dirname(exe_path)
    app_name = ctypes.create_unicode_buffer(exe_path)
    # Solo agregar --headless si es login/winlogon real (sin explorer)
    if "--type-credentials" not in spawn_args.split():
        need_headless = (not interactive_desktop) and (
            ("--winlogon" in spawn_args.split()) or (not has_user_token)
        )
        if need_headless and "--headless" not in spawn_args.split():
            spawn_args = f"{spawn_args} --headless".strip()
        # Con escritorio de usuario: quitar --headless accidental
        if interactive_desktop and not explicit_headless:
            parts = [p for p in spawn_args.split() if p not in ("--headless", "--winlogon")]
            spawn_args = " ".join(parts)
    cmdline_str = f'"{exe_path}"' if not spawn_args else f'"{exe_path}" {spawn_args}'
    cmdline = ctypes.create_unicode_buffer(cmdline_str)
    work_buf = ctypes.create_unicode_buffer(work_dir)

    logger.info(
        "Spawn companion sesion=%d interactive=%s headless_args=%r desktop=%s",
        session_id,
        interactive_desktop,
        spawn_args,
        si.lpDesktop,
    )

    try:
        ok = ADVAPI32.CreateProcessAsUserW(
            dup_token,
            app_name,
            cmdline,
            None,
            None,
            False,
            creation_flags,
            env_block,
            work_buf,
            ctypes.byref(si),
            ctypes.byref(pi),
        )
    finally:
        if env_ok and env_block:
            USERENV.DestroyEnvironmentBlock(env_block)
        KERNEL32.CloseHandle(dup_token)

    if ok:
        global _companion_spawn_grace_until, _companion_spawn_pid
        KERNEL32.CloseHandle(pi.hThread)
        if is_inject_helper:
            # El helper NO es el companion: no tocar el tracking del companion.
            logger.info("[INJECT] Helper SYSTEM lanzado en sesion %d (PID %d)", session_id, pi.dwProcessId)
            return pi.hProcess
        _companion_spawn_pid = int(pi.dwProcessId)
        _companion_spawn_grace_until = time.time() + 20
        logger.info("Companion lanzado en sesion %d (PID %d)", session_id, pi.dwProcessId)
        return pi.hProcess

    err = KERNEL32.GetLastError()
    logger.error(
        "CreateProcessAsUserW fallo (error %d). Ejecutable: %s | Trabajo: %s",
        err,
        exe_path,
        work_dir,
    )
    return None

def is_process_alive(handle):
    """True si el proceso identificado por handle sigue corriendo."""
    if not handle:
        return False
    return KERNEL32.WaitForSingleObject(handle, 0) == 0x00000102  # WAIT_TIMEOUT

# ── Companion monitor thread ──────────────────────────────────────────────────
_companion_handle = None
_last_session     = None
_pinned_session   = None
_svc_running      = True
_last_spawn_was_credentials = False
_pending_post_login = False  # True tras SAS/login: el proximo companion muerto espera shell
_companion_spawn_grace_until = 0.0
_companion_spawn_pid = None  # solo este PID queda protegido durante la gracia
_companion_rapid_failures = 0
_companion_backoff_until = 0.0
_force_relaunch_winlogon = False

APOLLO_DATA_DIR = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport")
SWITCH_SESSION_FILE = os.path.join(APOLLO_DATA_DIR, "switch_session.txt")
INJECT_PWD_FILE = os.path.join(APOLLO_DATA_DIR, "inject_password.txt")
FORCE_SAS_FILE = os.path.join(APOLLO_DATA_DIR, "force_sas.txt")


def get_console_session_id():
    """ID de la sesión Consola (pantalla física / login)."""
    sid = KERNEL32.WTSGetActiveConsoleSessionId()
    if sid == 0xFFFFFFFF:
        return 1
    return int(sid)


def normalize_windows_session_id(raw, fallback=None):
    """
    Valida ID de sesion Windows (evita 65536/0xFFFFFFFF que rompen WTS API).
    """
    if fallback is None:
        fallback = get_console_session_id()
    try:
        sid = int(raw)
    except (TypeError, ValueError):
        logger.warning("[SESSION] session_id no numerico (%r); usando %d", raw, fallback)
        return int(fallback)
    if sid in (0xFFFFFFFF, 0x10000, 65536):
        logger.warning("[SESSION] session_id reservado %d; usando %d", sid, fallback)
        return int(fallback)
    if sid < 1 or sid > 65535:
        logger.warning("[SESSION] session_id fuera de rango %d; usando %d", sid, fallback)
        return int(fallback)
    if not session_exists(sid):
        logger.warning("[SESSION] session_id %d no existe; usando %d", sid, fallback)
        return int(fallback)
    return sid


def session_has_user_token(session_id):
    """True si la sesion tiene un usuario logueado (token interactivo disponible)."""
    tok = ctypes.wintypes.HANDLE()
    ok = bool(WTSAPI32.WTSQueryUserToken(int(session_id), ctypes.byref(tok)))
    if ok:
        KERNEL32.CloseHandle(tok)
    return ok


WTS_ACTIVE = 0
WTS_CONNECTED = 1
WTS_DISCONNECTED = 4
WTS_LISTEN = 6
WTS_INIT = 9


class WTS_SESSION_INFO(ctypes.Structure):
    _fields_ = [
        ("SessionId", ctypes.wintypes.DWORD),
        ("pWinStationName", ctypes.c_wchar_p),
        ("State", ctypes.c_int),
    ]


def _enumerate_wts_sessions():
    p_info = ctypes.POINTER(WTS_SESSION_INFO)()
    count = ctypes.wintypes.DWORD(0)
    if not WTSAPI32.WTSEnumerateSessionsW(None, 0, 1, ctypes.byref(p_info), ctypes.byref(count)):
        return []
    rows = []
    try:
        for i in range(count.value):
            rows.append((int(p_info[i].SessionId), int(p_info[i].State)))
    finally:
        WTSAPI32.WTSFreeMemory(p_info)
    return rows


def session_exists(session_id):
    """True si la sesion Windows existe (evita WTSQueryUserToken error 2)."""
    return get_session_state(session_id) is not None


def get_session_state(session_id):
    """Estado WTS de la sesion, o None si no existe."""
    for sid, state in _enumerate_wts_sessions():
        if sid == int(session_id):
            return state
    return None


def session_suitable_for_companion(session_id, allow_winlogon=False):
    """
    True si tiene sentido mantener el companion en esta sesion.
    RDP desconectada sin token (error 1008) no es apta salvo login/SAS pendiente.
    """
    if get_session_state(session_id) is None:
        return False
    if session_has_user_token(session_id):
        return True
    state = get_session_state(session_id)
    console = get_console_session_id()
    if allow_winlogon:
        if int(session_id) == int(console):
            return True
        if state == WTS_DISCONNECTED:
            return True
        if state in (WTS_CONNECTED, WTS_LISTEN, WTS_INIT) and not session_has_user_token(session_id):
            return True
        return False
    if state == WTS_DISCONNECTED:
        return False
    if int(session_id) == int(console):
        return True
    return False


def resolve_session_with_logged_user(preferred_sess):
    """
    Tras login, el usuario suele quedar en Consola (ej. 1) aunque el tecnico
    haya pedido sesion RDP desconectada (ej. 24). Busca la sesion con token real.
    """
    global _pinned_session
    candidates = []
    for sid in (preferred_sess, get_console_session_id(), get_active_session_id()):
        if sid in (None, 0xFFFFFFFF):
            continue
        if sid not in candidates:
            candidates.append(int(sid))

    for sid in candidates:
        if not session_exists(sid):
            logger.warning("[LOGIN] Sesion %d no existe en el servidor", sid)
            continue
        if session_has_user_token(sid):
            if sid != preferred_sess:
                logger.info(
                    "[LOGIN] Usuario logueado en sesion %d (pedida=%d) — ajustando destino",
                    sid, preferred_sess,
                )
            _pinned_session = sid
            return sid

    if not session_exists(preferred_sess):
        console = get_console_session_id()
        logger.warning(
            "[LOGIN] Sesion %d invalida (error 2); usando consola %d",
            preferred_sess, console,
        )
        _pinned_session = console
        return console
    return preferred_sess


def process_switch_session_signal():
    """Reinicia el companion en otra sesion Windows (y opcionalmente inyecta login)."""
    global _companion_handle, _last_session, _pinned_session, _last_spawn_was_credentials, _pending_post_login
    if not os.path.isfile(SWITCH_SESSION_FILE):
        return False
    switch_ok = False
    try:
        with open(SWITCH_SESSION_FILE, encoding="utf-8") as f:
            raw = f.read().strip()
        if not raw:
            logger.warning("[SWITCH] switch_session.txt vacio; ignorando")
            return False
        switch_data = json.loads(raw)
        raw_sess = switch_data.get("session_id", -1)
        if raw_sess in (-1, None, ""):
            return False
        target_sess = normalize_windows_session_id(raw_sess)
        username = switch_data.get("username", "") or ""
        password = switch_data.get("password", "") or ""
        domain = switch_data.get("domain", "") or ""
        logger.info(
            "[SWITCH] Cambio de sesion solicitado -> %d (login=%s); terminando companion actual",
            target_sess, bool(password),
        )

        allow_wl = bool(password)
        if not session_suitable_for_companion(target_sess, allow_winlogon=allow_wl):
            fallback = resolve_companion_session_id()
            logger.warning(
                "[SWITCH] Sesion %d no apta (desconectada/sin token); redirigiendo a %d",
                target_sess, fallback,
            )
            target_sess = int(fallback)

        if password:
            os.makedirs(APOLLO_DATA_DIR, exist_ok=True)
            with open(INJECT_PWD_FILE, "w", encoding="utf-8") as f:
                json.dump({"username": username, "domain": domain, "password": password}, f)
            with open(FORCE_SAS_FILE, "w", encoding="utf-8") as f:
                f.write("1")

        kill_stale_companion_processes(session_id=int(target_sess))
        spawn_args = "--type-credentials" if password else ""
        new_handle = spawn_in_user_session(COMPANION_EXE, args=spawn_args, session_id=target_sess)
        if not new_handle:
            logger.error(
                "[SWITCH] spawn_in_user_session fallo para sesion %d; companion actual intacto (reintento)",
                target_sess,
            )
            return False

        prev_sess = _last_session
        old_handle = _companion_handle
        _companion_handle = None
        if old_handle:
            KERNEL32.TerminateProcess(old_handle, 0)
            KERNEL32.CloseHandle(old_handle)
            time.sleep(0.5)
        if prev_sess and int(prev_sess) != int(target_sess):
            kill_stale_companion_processes(session_id=int(prev_sess))

        _companion_handle = new_handle
        _last_session = target_sess
        _pinned_session = target_sess
        _last_spawn_was_credentials = bool(password)
        if password:
            _pending_post_login = True
        logger.info("[SWITCH] Companion lanzado en sesion %d (args=%r)", target_sess, spawn_args or "(normal)")

        switch_ok = True
        return True
    except Exception as switch_err:
        logger.error("[SWITCH] Error procesando switch: %s", switch_err)
        return False
    finally:
        if switch_ok and os.path.exists(SWITCH_SESSION_FILE):
            try:
                os.remove(SWITCH_SESSION_FILE)
            except OSError:
                pass


def find_session_with_user_token():
    """
    Mejor sesion con usuario logueado.
    Prioridad: Active + explorer (escritorio visible) > Active > otras.
    Evita anclarse a una sesion vieja (ej. 2) y matar el companion del
    RDP/AnyDesk donde el usuario esta mirando (ej. 8).
    """
    scored = []
    for sid, state in _enumerate_wts_sessions():
        if sid == 0:
            continue
        if not session_has_user_token(sid):
            continue
        score = 0
        if state == WTS_ACTIVE:
            score += 100
        elif state == WTS_CONNECTED:
            score += 40
        elif state == WTS_DISCONNECTED:
            score += 5
        if _session_has_explorer(sid):
            score += 50
        if find_companion_pid_in_session(sid):
            score += 35
        scored.append((score, int(sid)))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    best_score, best_sid = scored[0]
    logger.info(
        "[SESSION] Mejor sesion usuario=%d score=%d (candidatos=%s)",
        best_sid, best_score, scored[:5],
    )
    return best_sid


def adopt_visible_companion_session(current_target):
    """
    Si el companion ya corre en otra sesion Active con escritorio (usuario
    abrio el acceso directo ahi), adoptar esa sesion en lugar de matarlo.
    """
    best = None
    best_score = -1
    for sid, state in _enumerate_wts_sessions():
        if sid == 0 or int(sid) == int(current_target):
            continue
        if state != WTS_ACTIVE:
            continue
        if not find_companion_pid_in_session(sid):
            continue
        score = 50
        if _session_has_explorer(sid):
            score += 50
        if session_has_user_token(sid):
            score += 20
        if score > best_score:
            best_score = score
            best = int(sid)
    return best


def resolve_companion_session_id():
    """
    Sesion donde debe correr el companion (UI + captura).
    - Switch manual: _pinned_session (salvo que no tenga escritorio y haya otra Active)
    - Usuario logueado: mejor sesion Active+explorer
    - Sin login: consola / Winlogon
    """
    global _pinned_session
    best = find_session_with_user_token()

    if _pinned_session not in (None, 0xFFFFFFFF):
        allow_wl = _pending_post_login or _last_spawn_was_credentials
        pin = int(_pinned_session)
        pin_ok = session_has_user_token(pin) or session_suitable_for_companion(
            pin, allow_winlogon=allow_wl
        )
        # Pin sin explorer + otra sesion Active con escritorio => el usuario esta alla
        if (
            pin_ok
            and best is not None
            and int(best) != pin
            and not allow_wl
            and not _session_has_explorer(pin)
            and _session_has_explorer(best)
            and get_session_state(best) == WTS_ACTIVE
        ):
            logger.warning(
                "[SESSION] Pin %d sin escritorio visible; usuario en sesion %d — redirigiendo",
                pin, best,
            )
            _pinned_session = int(best)
            return int(best)
        if session_has_user_token(pin):
            return pin
        if session_suitable_for_companion(pin, allow_winlogon=allow_wl):
            return pin
        if best is not None and not allow_wl:
            logger.warning(
                "[SESSION] Sesion %d sin token; usuario activo en %d — redirigiendo",
                pin, best,
            )
            _pinned_session = int(best)
            return int(best)
        logger.warning(
            "[SESSION] Sesion %d no apta (desconectada/sin token); desanclando",
            pin,
        )
        _pinned_session = None

    if best is not None:
        return int(best)

    active = get_active_session_id()
    if active != 0xFFFFFFFF and session_has_user_token(active):
        return int(active)

    return get_console_session_id()


def _relaunch_companion_after_login(target_sess):
    """Tras inyectar credenciales, esperar shell y relanzar companion con token de usuario."""
    global _companion_handle, _last_session, _last_spawn_was_credentials, _pending_post_login
    logger.info("[LOGIN] Post-login: esperando shell (sesion pedida=%d)", target_sess)
    _last_spawn_was_credentials = False
    _pending_post_login = False
    kill_stale_companion_processes(session_id=target_sess)
    for attempt in range(25):
        wait_s = 3 if attempt < 3 else 2
        time.sleep(wait_s)
        if session_has_user_token(target_sess):
            logger.info("[LOGIN] Token OK en sesion %d (intento %d)", target_sess, attempt + 1)
            break
        if resolve_session_with_logged_user(target_sess) != target_sess:
            target_sess = _pinned_session
            logger.info("[LOGIN] Token detectado en sesion %d tras re-scan", target_sess)
            break
        logger.info("[LOGIN] Sin token en sesion %d (intento %d/25)", target_sess, attempt + 1)

    launch_sess = resolve_session_with_logged_user(target_sess)
    _companion_handle = spawn_in_user_session(COMPANION_EXE, session_id=launch_sess)
    _last_session = launch_sess
    if _companion_handle:
        logger.info("[LOGIN] Companion relanzado en sesion %d (escritorio usuario)", launch_sess)
    else:
        logger.error("[LOGIN] Fallo relanzar companion en sesion %d tras login", launch_sess)
    return _companion_handle


def companion_monitor():
    """
    Vigila el companion en la sesión correcta (RDP o Consola).
    Respeta _pinned_session tras un switch para no volver a la sesión RDP vieja.
    """
    global _companion_handle, _last_session, _pinned_session, _last_spawn_was_credentials, _pending_post_login
    global _companion_rapid_failures, _companion_backoff_until
    global _force_relaunch_winlogon

    time.sleep(0.3)  # soltar handles del instalador; no bloquear el primer spawn

    while _svc_running:
        if _force_relaunch_winlogon:
            _force_relaunch_winlogon = False
            logger.info("[SAS] Reiniciando companion en Winlogon (Ctrl+Alt+Del) para ver login...")
            target_sess = resolve_companion_session_id()
            kill_stale_companion_processes(session_id=target_sess)
            if _companion_handle:
                try:
                    KERNEL32.TerminateProcess(_companion_handle, 0)
                    KERNEL32.CloseHandle(_companion_handle)
                except: pass
                _companion_handle = None

            # --winlogon: captura + WS en escritorio de login (NO --type-credentials,
            # que solo inyecta password y sale sin video).
            _companion_handle = spawn_in_user_session(
                COMPANION_EXE, args="--winlogon --headless", session_id=target_sess
            )
            _last_session = target_sess
            _last_spawn_was_credentials = False
            _pending_post_login = False
            continue

        process_switch_session_signal()

        if time.time() < _companion_backoff_until:
            time.sleep(2)
            continue

        target_sess = resolve_companion_session_id()

        # Si el usuario abrio el companion en otra sesion Active (AnyDesk/RDP),
        # adoptar esa en vez de matarlo por "fuera de sesion".
        adopted = adopt_visible_companion_session(target_sess)
        if adopted is not None:
            logger.warning(
                "[SESSION] Companion visible en sesion %d (target era %d) — adoptando",
                adopted, target_sess,
            )
            _pinned_session = adopted
            target_sess = adopted

        # Evitar pelea Consola vs AnyDesk: un solo companion en la sesion elegida
        keep_alive_pid = _pid_from_handle(_companion_handle) if is_process_alive(_companion_handle) else _companion_spawn_pid
        kill_companions_outside_session(target_sess, keep_pid=keep_alive_pid)

        companion_alive = is_process_alive(_companion_handle)

        # Si hay escritorio de usuario pero el companion quedo headless (online sin
        # tray/ventana), reemplazarlo solos — el cliente no debe hacer taskkill.
        if companion_alive and _session_has_explorer(target_sess):
            alive_pid = _pid_from_handle(_companion_handle) or _companion_spawn_pid
            if alive_pid and companion_cmdline_is_headless(alive_pid):
                logger.warning(
                    "[UI] Companion headless con explorer en sesion %d (pid=%s) — relanzando UI",
                    target_sess, alive_pid,
                )
                try:
                    KERNEL32.TerminateProcess(_companion_handle, 0)
                    KERNEL32.CloseHandle(_companion_handle)
                except Exception:
                    pass
                _companion_handle = None
                kill_stale_companion_processes(session_id=target_sess)
                time.sleep(0.3)
                _companion_handle = spawn_in_user_session(COMPANION_EXE, session_id=target_sess)
                _last_session = target_sess
                companion_alive = is_process_alive(_companion_handle)

        if not companion_alive:
            if _companion_handle:
                _log_companion_exit(_companion_handle)
                KERNEL32.CloseHandle(_companion_handle)
                _companion_handle = None

            if attach_companion_in_session(target_sess):
                _last_session = target_sess
                _companion_rapid_failures = 0
            else:
                post_login = _last_spawn_was_credentials or _pending_post_login
                if post_login:
                    _relaunch_companion_after_login(target_sess)
                    _companion_rapid_failures = 0
                else:
                    if not session_suitable_for_companion(target_sess, allow_winlogon=False):
                        logger.warning(
                            "[SESSION] No se lanzara companion en sesion %d (sin token/desconectada)",
                            target_sess,
                        )
                        _companion_rapid_failures = 0
                        time.sleep(5)
                        continue

                    logger.info("Companion ausente — relanzando en sesion %d (pinned=%s)", target_sess, _pinned_session)
                    kill_stale_companion_processes(
                        keep_pid=_companion_spawn_pid, session_id=target_sess
                    )
                    time.sleep(0.2)
                    _companion_handle = spawn_in_user_session(COMPANION_EXE, session_id=target_sess)
                    _last_session = target_sess
                    if _companion_handle:
                        logger.info("Companion relanzado OK en sesion %d", target_sess)
                        time.sleep(0.5)
                        if is_process_alive(_companion_handle):
                            _companion_rapid_failures = 0
                        elif attach_companion_in_session(target_sess):
                            _companion_rapid_failures = 0
                        else:
                            _companion_rapid_failures += 1
                    elif attach_companion_in_session(target_sess):
                        _companion_rapid_failures = 0
                    else:
                        logger.error("Fallo relanzar companion en sesion %d", target_sess)
                        _companion_rapid_failures += 1
                        if not session_has_user_token(target_sess):
                            _last_spawn_was_credentials = False
                            _pending_post_login = False

                    if _companion_rapid_failures >= 3:
                        logger.warning(
                            "[SESSION] %d fallos seguidos en sesion %d; backoff 30s y desanclar",
                            _companion_rapid_failures, target_sess,
                        )
                        _pinned_session = None
                        _companion_backoff_until = time.time() + 30
                        _companion_rapid_failures = 0
        else:
            _last_session = target_sess
            _companion_rapid_failures = 0

        time.sleep(2)


def get_windows_sessions():
    """Lista las sesiones de Windows usando 'query session' (qwinsta).
    Retorna lista de dicts: {id, name, username, state, type}
    """
    sessions = []
    try:
        result = subprocess.run(
            ['query', 'session'],
            capture_output=True, text=True, errors='replace', timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        lines = result.stdout.splitlines()
        for line in lines[1:]:
            if not line.strip():
                continue
            active = line.startswith('>')
            line = line.lstrip('> ')
            parts = line.split()
            if not parts:
                continue
            try:
                if len(parts) >= 4 and not str(parts[1]).isdigit():
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
                    sess_type    = parts[3] if len(parts) > 3 else ''
                else:
                    continue
                if session_id < 1 or session_id > 65535:
                    continue
                sessions.append({
                    'id':       session_id,
                    'name':     session_name,
                    'username': username,
                    'state':    state,
                    'type':     sess_type,
                    'current':  active,
                })
            except (ValueError, IndexError):
                continue
    except Exception as e:
        logger.debug("[SESSION] Error listando sesiones: %s", e)
    return sessions


# ── WebSocket headless (mantiene el device ONLINE aunque no haya usuario) ─────
async def headless_ws_loop():
    """
    Conexion WebSocket minima en Session 0:
    - Envia telemetria basica cada 5s (status=online, cpu, ram, hostname)
    - Responde pings del backend
    No hace captura de pantalla ni control (eso lo hace el companion en sesion de usuario)
    """
    cfg             = load_config()
    client_id       = cfg.get("client_id")
    device_name     = cfg.get("device_name", socket.gethostname())
    license_key     = cfg.get("license_key", "")
    base_ws_url     = cfg.get("base_ws_url", "wss://support.ultimate.net.ar/api/ws/centinela")
    ws_url          = f"{base_ws_url}/{client_id}?device_name={device_name}&license_key={license_key}"
    reconnect_delay = 5

    while _svc_running:
        try:
            logger.info("[WS] Conectando a %s", ws_url)
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=30, close_timeout=10) as ws:
                reconnect_delay = 5
                logger.info("[WS] Conectado")

                async def send_telemetry():
                    while _svc_running:
                        try:
                            payload = {
                                "type": "telemetry",
                                "data": {
                                    "status":   "online",
                                    "cpu":      psutil.cpu_percent(interval=None),
                                    "ram":      psutil.virtual_memory().percent,
                                    "os":       f"{platform.system()} {platform.release()}",
                                    "hostname": socket.gethostname(),
                                    "service_mode": True,  # Flag: companion maneja video
                                }
                            }
                            await ws.send(json.dumps(payload))
                        except Exception:
                            break
                        await asyncio.sleep(5)

                telem_task = asyncio.create_task(send_telemetry())
                try:
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        if data.get("type") == "ping":
                            await ws.send(json.dumps({"type": "pong"}))
                        elif data.get("type") == "get_sessions":
                            sessions = get_windows_sessions()
                            for s in sessions:
                                s['current'] = False
                            await ws.send(json.dumps({
                                "type": "session_list",
                                "sessions": sessions,
                                "current_session": 0,
                            }))
                        elif data.get("type") == "login_session":
                            session_id = int(data.get("session_id") or 0)
                            username = data.get("username", "") or ""
                            password = data.get("password", "") or ""
                            domain = data.get("domain", "") or ""
                            
                            if not session_id:
                                for s in get_windows_sessions():
                                    if str(s.get("name", "")).lower() == "console":
                                        session_id = int(s["id"])
                                        break
                                if not session_id:
                                    session_id = 1
                            
                            logger.info("[WS-HEADLESS] login_session recibido en Session 0 -> sesion %d, username=%s", session_id, username)
                            try:
                                os.makedirs(os.path.dirname(SWITCH_SESSION_FILE), exist_ok=True)
                                with open(SWITCH_SESSION_FILE, 'w', encoding='utf-8') as sf:
                                    json.dump({
                                        'session_id': session_id,
                                        'username': username,
                                        'password': password,
                                        'domain': domain,
                                    }, sf)
                                logger.info("[WS-HEADLESS] SWITCH_SESSION_FILE escrito con exito")
                                await ws.send(json.dumps({
                                    "type": "login_result",
                                    "success": True,
                                    "session_id": session_id,
                                    "error": "",
                                }))
                            except Exception as e:
                                logger.error("[WS-HEADLESS] Error escribiendo SWITCH_SESSION_FILE: %s", e)
                                await ws.send(json.dumps({
                                    "type": "login_result",
                                    "success": False,
                                    "session_id": session_id,
                                    "error": f"Error escribiendo senal de switch: {str(e)}",
                                }))
                        elif data.get("type") == "license_assigned":
                            cfg["license_key"] = data.get("license_key", "")
                            with open(CONFIG_FILE, "w") as f:
                                json.dump(cfg, f)
                            license_key = cfg["license_key"]
                            logger.info("[LICENCIA] Asignada remotamente: %s", license_key)
                except Exception as e:
                    logger.debug("[WS] Desconectado: %s", e)
                finally:
                    telem_task.cancel()

        except Exception as e:
            logger.warning("[WS] Error: %s. Reintentando en %ds", e, reconnect_delay)

        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 60)

# ── OTA Auto-Updater ────────────────────────────────────────────────────────
def parse_version(v_str):
    return [int(x) for x in v_str.split('.') if x.isdigit()]

def _sc_exe_path():
    windir = os.environ.get('SystemRoot', 'C:\\Windows')
    sc_exe = os.path.join(windir, 'System32', 'sc.exe')
    sysnative = os.path.join(windir, 'Sysnative', 'sc.exe')
    if os.path.exists(sysnative):
        sc_exe = sysnative
    return sc_exe

def _run_hidden(cmd):
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    try:
        subprocess.run(cmd, capture_output=True, timeout=20, creationflags=flags)
    except Exception as e:
        logger.debug("[UPDATE] cmd falló %s: %s", cmd, e)

def _pid_from_handle(handle):
    if not handle:
        return None
    try:
        pid = KERNEL32.GetProcessId(handle)
        return int(pid) if pid else None
    except Exception:
        return None


def _log_companion_exit(handle):
    if not handle:
        return
    code = ctypes.c_ulong()
    if KERNEL32.GetExitCodeProcess(handle, ctypes.byref(code)):
        ec = int(code.value)
        if ec == 259:  # STILL_ACTIVE
            return
        hint = ""
        if ec == 0:
            hint = " (mutex/duplicado)"
        elif ec == 1:
            hint = " (terminado/kill o error inicio)"
        logger.info("Companion termino con exit=%d%s", ec, hint)


def get_process_session_id(pid):
    sid = ctypes.c_ulong(0)
    if KERNEL32.ProcessIdToSessionId(ctypes.c_ulong(int(pid)), ctypes.byref(sid)):
        return int(sid.value)
    return None


def _is_inject_helper_pid(pid):
    """True si el proceso es el helper de inyeccion SYSTEM (--inject-helper), NO el companion.
    Comparten el mismo .exe, asi que hay que distinguirlos por la linea de comandos."""
    try:
        cmd = psutil.Process(int(pid)).cmdline() or []
        return "--inject-helper" in " ".join(str(x) for x in cmd).lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return False
    except Exception:
        return False


def find_companion_pid_in_session(session_id):
    """PID del companion vivo en la sesion indicada (si existe). Ignora el helper de inyeccion."""
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in COMPANION_IMAGE_NAMES:
                    continue
                pid = proc.info.get("pid")
                if pid and get_process_session_id(pid) == int(session_id) and not _is_inject_helper_pid(pid):
                    return int(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return None


def companion_cmdline_is_headless(pid):
    """True si el companion corre con --headless/--winlogon (sin ventana de ID)."""
    try:
        cmd = psutil.Process(int(pid)).cmdline() or []
        joined = " ".join(str(x) for x in cmd).lower()
        return ("--headless" in joined) or ("--winlogon" in joined)
    except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
        return False


def open_companion_process_handle(pid):
    """Handle con SYNCHRONIZE para vigilar si el proceso sigue vivo."""
    SYNCHRONIZE = 0x00100000
    h = KERNEL32.OpenProcess(SYNCHRONIZE, False, int(pid))
    return h if h else None


def attach_companion_in_session(session_id):
    """Si ya hay companion en la sesion, reutilizar su PID en lugar de relanzar."""
    global _companion_handle, _companion_spawn_pid, _companion_spawn_grace_until
    pid = find_companion_pid_in_session(session_id)
    if not pid:
        return None
    h = open_companion_process_handle(pid)
    if not h:
        return None
    _companion_handle = h
    _companion_spawn_pid = pid
    _companion_spawn_grace_until = time.time() + 20
    logger.info("Companion ya activo en sesion %d (PID %d), reenganchado", session_id, pid)
    return h


def kill_stale_companion_processes(keep_pid=None, session_id=None):
    """Cierra companions duplicados.
    - session_id=None: mata TODOS los companions (salvo keep_pid).
    - session_id=N: solo los de esa sesion.
    """
    global _companion_spawn_grace_until, _companion_spawn_pid
    keep = {os.getpid()}
    if keep_pid:
        keep.add(int(keep_pid))
    if _companion_spawn_pid:
        keep.add(int(_companion_spawn_pid))
    now = time.time()
    in_grace = now < _companion_spawn_grace_until
    target_sess = int(session_id) if session_id is not None else None
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in COMPANION_IMAGE_NAMES:
                    continue
                pid = proc.info.get("pid")
                if pid in keep:
                    continue
                if in_grace and pid == _companion_spawn_pid:
                    continue
                if _is_inject_helper_pid(pid):
                    continue  # nunca matar el helper de inyeccion SYSTEM
                if target_sess is not None:
                    psid = get_process_session_id(pid)
                    if psid is None or int(psid) != target_sess:
                        continue
                proc.kill()
                logger.info(
                    "[KILL] Companion duplicado en sesion %s terminado: %s (pid=%s)",
                    target_sess if target_sess is not None else "todas",
                    name,
                    pid,
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logger.debug("[KILL] kill_stale_companion_processes: %s", e)


def kill_companions_outside_session(keep_session, keep_pid=None):
    """Deja un solo companion: mata los de otras sesiones Windows (AnyDesk vs Consola)."""
    keep = {os.getpid()}
    if keep_pid:
        keep.add(int(keep_pid))
    if _companion_spawn_pid:
        keep.add(int(_companion_spawn_pid))
    keep_sess = int(keep_session)
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name not in COMPANION_IMAGE_NAMES:
                    continue
                pid = proc.info.get("pid")
                if pid in keep:
                    continue
                if _is_inject_helper_pid(pid):
                    continue  # nunca matar el helper de inyeccion SYSTEM
                psid = get_process_session_id(pid)
                if psid is not None and int(psid) == keep_sess:
                    continue
                proc.kill()
                logger.info(
                    "[KILL] Companion fuera de sesion %d terminado: %s (pid=%s sesion=%s)",
                    keep_sess, name, pid, psid,
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        logger.debug("[KILL] kill_companions_outside_session: %s", e)


_inject_helper_handle = None
_service_mutex_handle = None


def find_inject_helper_pid_in_session(session_id):
    """PID del primer helper de inyeccion SYSTEM en la sesion (si existe)."""
    pids = find_all_inject_helper_pids_in_session(session_id)
    return pids[0] if pids else None


def find_all_inject_helper_pids_in_session(session_id):
    """Lista todos los PIDs de helpers de inyeccion SYSTEM en la sesion."""
    result = []
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if (proc.info.get("name") or "").lower() not in COMPANION_IMAGE_NAMES:
                    continue
                pid = proc.info.get("pid")
                if not pid or get_process_session_id(pid) != int(session_id):
                    continue
                if _is_inject_helper_pid(pid):
                    result.append(int(pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return result


def _kill_stale_service_processes(keep_pid=None):
    """Mata procesos de ESTA misma imagen que quedaron vivos en sesion 0
    (zombies de stop/start previos). Nunca toca el PID propio ni procesos de
    otra sesion: en sesion 0 solo corresponde existir al servicio, y los
    companions/helpers corren bajo otro nombre de imagen."""
    try:
        frozen = getattr(sys, "frozen", False)
        my_image = psutil.Process(os.getpid()).name().lower()
    except Exception:
        return
    killed = []
    try:
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pid = proc.info.get("pid")
                if not pid or pid == os.getpid() or (keep_pid and pid == keep_pid):
                    continue
                if frozen:
                    if (proc.info.get("name") or "").lower() != my_image:
                        continue
                else:
                    try:
                        if "centinela_svc" not in " ".join(proc.cmdline()).lower():
                            continue
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                if get_process_session_id(pid) != 0:
                    continue
                proc.kill()
                killed.append(pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    for pid in killed:
        logger.warning("[KILL] Servicio zombie en sesion 0 terminado: pid=%s", pid)


def _acquire_service_mutex():
    """Adquiere el mutex de instancia unica Global\\ApolloCentinelaService.
    Si esta tomado, hay otra instancia viva o un zombie: barre la sesion 0 y
    reintenta (al morir el dueño, Windows libera el mutex automaticamente).
    Devuelve el handle o None si no se pudo adquirir."""
    global _service_mutex_handle
    for attempt in (1, 2):
        h = KERNEL32.CreateMutexW(None, True, SERVICE_MUTEX_NAME)
        err = KERNEL32.GetLastError()
        if not h:
            logger.error("[GUARD] CreateMutex fallo con error %s", err)
            return None
        if err != ERROR_ALREADY_EXISTS:
            _service_mutex_handle = h
            if attempt == 2:
                logger.info("[GUARD] Mutex del servicio adquirido tras limpiar instancia previa")
            return h
        KERNEL32.CloseHandle(h)
        logger.warning("[GUARD] Mutex del servicio ocupado (intento %d): barriendo instancia previa", attempt)
        _kill_stale_service_processes(keep_pid=os.getpid())
        time.sleep(1)
    logger.error("[GUARD] No se pudo adquirir el mutex del servicio; se aborta el arranque")
    return None


def inject_helper_monitor():
    """Mantiene vivo un helper SYSTEM de inyeccion en la sesion del usuario logueado.
    Permite operar el UAC y ventanas elevadas (que el companion de integridad media no puede
    por UIPI). El companion le reenvia la entrada por loopback; si no esta, inyecta directo."""
    global _inject_helper_handle
    time.sleep(6)  # dejar que arranque el companion primero
    while _svc_running:
        try:
            sess = resolve_companion_session_id()
            if sess and sess != 0xFFFFFFFF and session_has_user_token(sess):
                all_helpers = find_all_inject_helper_pids_in_session(sess)
                tracked_pid = _pid_from_handle(_inject_helper_handle) if _inject_helper_handle else None

                if len(all_helpers) > 1:
                    keep = tracked_pid if tracked_pid and tracked_pid in all_helpers else all_helpers[0]
                    for pid in all_helpers:
                        if pid != keep:
                            try:
                                psutil.Process(pid).kill()
                                logger.info("[INJECT] Helper duplicado terminado: PID %d (mantengo PID %d)", pid, keep)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                    all_helpers = [keep]

                if not all_helpers:
                    if _inject_helper_handle:
                        try:
                            KERNEL32.CloseHandle(_inject_helper_handle)
                        except Exception:
                            pass
                        _inject_helper_handle = None
                    h = spawn_in_user_session(COMPANION_EXE, args="--inject-helper", session_id=sess)
                    if h:
                        _inject_helper_handle = h
                    else:
                        logger.warning("[INJECT] No se pudo lanzar helper SYSTEM en sesion %d", sess)
        except Exception as e:
            logger.debug("[INJECT] monitor error: %s", e)
        time.sleep(5)


_ota_update_lock = threading.Lock()


def _update_api_base(cfg):
    base_ws_url = str((cfg or {}).get("base_ws_url") or "")
    if not base_ws_url:
        return ""
    return base_ws_url.replace("wss://", "https://").replace("ws://", "http://").split("/api/ws", 1)[0].rstrip("/")


def _preferred_update_arch():
    return "x64" if ctypes.sizeof(ctypes.c_void_p) == 8 else "x86"


def _resolve_update_url(base_url, data):
    downloads = data.get("downloads") or {}
    selected = downloads.get(_preferred_update_arch()) or downloads.get("combined") or {}
    if isinstance(selected, dict):
        download_url = selected.get("url") or ""
    else:
        download_url = selected if isinstance(selected, str) else ""
    download_url = str(download_url or data.get("url") or "").strip()
    if not download_url:
        return ""
    if download_url.startswith(("http://", "https://")):
        return download_url
    return f"{base_url}/{download_url.lstrip('/')}"


def _fetch_update_info():
    import urllib.request

    cfg = load_config()
    base_url = _update_api_base(cfg)
    if not base_url:
        return "", ""
    api_url = f"{base_url}/api/centinela/update_check"
    request = urllib.request.Request(
        api_url,
        headers={"User-Agent": "ApolloCentinelaService"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("version") or "0.0.0"), _resolve_update_url(base_url, data)


async def perform_update(url):
    import shutil
    import tempfile
    import urllib.request

    if not _ota_update_lock.acquire(blocking=False):
        logger.info("[OTA] Ya hay una actualización en curso")
        return
    try:
        temp_dir = tempfile.gettempdir()
        arch = _preferred_update_arch()
        installer_path = os.path.join(temp_dir, f"ApolloSetup_update_{arch}.exe")
        logger.info("[OTA] Descargando instalador %s desde %s", arch, url)
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "ApolloCentinelaService"},
        )
        with urllib.request.urlopen(request, timeout=180) as response, open(installer_path, "wb") as out_file:
            shutil.copyfileobj(response, out_file)
        if os.path.getsize(installer_path) < 1_000_000:
            raise RuntimeError("Instalador descargado incompleto")
        with open(installer_path, "rb") as installer_file:
            if installer_file.read(2) != b"MZ":
                raise RuntimeError("El archivo descargado no es un ejecutable válido")

        log_path = os.path.join(temp_dir, "ApolloCentinela_setup.log")
        logger.info("[OTA] Lanzando instalador silencioso: %s", installer_path)
        subprocess.Popen(
            [
                installer_path,
                "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                "/CLOSEAPPLICATIONS", "/FORCECLOSEAPPLICATIONS",
                f"/LOG={log_path}",
            ],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
        )
        logger.info("[OTA] Instalador iniciado; el servicio se cerrará para liberar el binario")
        os._exit(0)
    except Exception as e:
        logger.error("[OTA] Error aplicando actualización: %s", e)
        _ota_update_lock.release()


async def update_checker_loop():
    await asyncio.sleep(120)
    while True:
        try:
            remote_version, download_url = _fetch_update_info()
            if parse_version(remote_version) > parse_version(__version__) and download_url:
                logger.info(
                    "[OTA] Nueva versión %s detectada (actual: %s)",
                    remote_version,
                    __version__,
                )
                await perform_update(download_url)
        except Exception as e:
            logger.debug("[OTA] Chequeo de versión fallido: %s", e)
        await asyncio.sleep(12 * 3600)

# ── Loop principal WebSocket ──────────────────────────────────────────────────
async def websocket_loop():
    asyncio.create_task(update_checker_loop())
    await headless_ws_loop()

# ── Entry points ──────────────────────────────────────────────────────────────
def run_as_service():
    """
    Punto de entrada cuando corre como Windows Service.
    SOLO lanza el companion en la sesion del usuario y lo monitorea.
    La conexion WebSocket la maneja UNICAMENTE el companion (centinela.py).
    Tener dos WS connections con el mismo client_id rompia la sesion remota.
    """
    global _svc_running
    logger.info("=== Apollo Centinela Service v%s iniciando ===", __version__)
    _kill_stale_service_processes(keep_pid=os.getpid())
    if not _acquire_service_mutex():
        logger.error("=== Apollo Centinela Service aborta arranque: ya existe una instancia ===")
        return
    _enable_service_token_privileges()
    logger.info("Rol: monitor del companion. La conexion WS la maneja el companion.")
    logger.info(
        "Companion esperado: %s | existe=%s",
        COMPANION_EXE,
        os.path.isfile(COMPANION_EXE),
    )

    # --- Habilitar directiva SAS para poder enviar Ctrl+Alt+Del ---
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "SoftwareSASGeneration", 0, winreg.REG_DWORD, 3) # 3 = Servicios y Ease of Access
        logger.info("[SAS] Directiva de simulacion de Ctrl+Alt+Del activada con exito en el Registro (por el Servicio SYSTEM).")
    except Exception as e:
        logger.error(f"[SAS] Error activando directiva en el Registro: {e}")

    # --- UAC: mostrar el prompt en el escritorio interactivo (no en el Secure Desktop) ---
    # Por defecto Windows dibuja el UAC en un escritorio aislado (Winlogon/Secure Desktop)
    # que NO se puede capturar ni controlar desde la sesion del usuario -> el tecnico ve la
    # pantalla "congelada". PromptOnSecureDesktop=0 hace que el UAC salga en el escritorio
    # normal (winsta0\default), donde el companion SI lo captura y puede operarlo.
    # Compromiso de seguridad: el prompt deja de estar aislado (aceptable en una herramienta
    # de soporte administrada; es lo que hacen TeamViewer/AnyDesk en su modo asistido).
    try:
        import winreg
        uac_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uac_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "PromptOnSecureDesktop", 0, winreg.REG_DWORD, 0)
        logger.info("[UAC] PromptOnSecureDesktop=0: el UAC saldra en el escritorio interactivo (visible para el tecnico).")
    except Exception as e:
        logger.error(f"[UAC] No se pudo ajustar PromptOnSecureDesktop: {e}")

    # Un solo hilo lanza/vigila el companion (evita carrera con kill_stale al arrancar)
    monitor_thread = threading.Thread(target=companion_monitor, daemon=True)
    monitor_thread.start()

    # Hilo que mantiene el helper SYSTEM de inyeccion (UAC / ventanas elevadas)
    inject_thread = threading.Thread(target=inject_helper_monitor, daemon=True)
    inject_thread.start()

    ws_thread = threading.Thread(target=lambda: asyncio.run(websocket_loop()), daemon=True)
    ws_thread.start()

    # Mantener el proceso vivo (el monitor corre en el hilo daemon)
    try:
        while _svc_running:
            time.sleep(1)

            process_switch_session_signal()

            # --- SAS SIGNAL CHECK ---
            force_sas_file = FORCE_SAS_FILE
            if os.path.isfile(force_sas_file):
                global _pending_post_login
                if os.path.isfile(INJECT_PWD_FILE) or _last_spawn_was_credentials:
                    _pending_post_login = True
                    logger.info("[SAS] Ctrl+Alt+Sup con login pendiente (sesion pinned=%s)", _pinned_session)
                logger.info("[SAS] Detectado archivo signal force_sas.txt. Enviando Ctrl+Alt+Del...")
                try:
                    os.remove(force_sas_file)
                except:
                    pass
                try:
                    import ctypes
                    
                    # 1. Despertar monitor (Wake Screen) forzando el estado del sistema
                    ES_CONTINUOUS = 0x80000000
                    ES_DISPLAY_REQUIRED = 0x00000002
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_DISPLAY_REQUIRED)
                    
                    # Mover el mouse un pixel para asegurar
                    ctypes.windll.user32.mouse_event(0x0001, 1, 1, 0, 0)
                    
                    # 2. Inyectar SAS (Ctrl+Alt+Del)
                    sas_dll = None
                    try:
                        # En sistemas 64-bit, el agente 64-bit cargara la sas.dll 64-bit nativa
                        # En sistemas 32-bit, el agente 32-bit cargara la nativa
                        sas_dll = ctypes.windll.LoadLibrary("sas.dll")
                    except OSError:
                        pass
                    
                    if sas_dll:
                        sas_dll.SendSAS.argtypes = [ctypes.c_int]
                        sas_dll.SendSAS(0)
                        logger.info("[SAS] Monitor despertado y SendSAS(0) ejecutado.")
                    else:
                        logger.error("[SAS] No se pudo cargar sas.dll. Compruebe las politicas de Windows.")
                    
                    # Restaurar estado
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                    
                    global _force_relaunch_winlogon
                    _force_relaunch_winlogon = True
                except Exception as e:
                    logger.error(f"[SAS] Error ejecutando SendSAS: {e}")

            # inject_password.txt lo procesa process_switch_session_signal (--type-credentials)
            # No lanzar un segundo companion aquí (provocaba duplicados y TIMEOUT en bitácora).

            # --- OTA UPDATE SIGNAL CHECK ---
            force_ota_file = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport", "force_ota.txt")
            if os.path.isfile(force_ota_file):
                logger.info("[OTA] Detectada solicitud de actualización")
                try:
                    remote_version, download_url = _fetch_update_info()
                    if not download_url:
                        raise RuntimeError("El servidor no publicó un instalador compatible")
                    os.remove(force_ota_file)
                    logger.info("[OTA] Iniciando actualización solicitada a v%s", remote_version)
                    threading.Thread(
                        target=lambda: asyncio.run(perform_update(download_url)),
                        daemon=True,
                        name="CentinelaOTA",
                    ).start()
                except Exception as e:
                    logger.error("[OTA] Error preparando la actualización solicitada: %s", e)
                        
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        _svc_running = False
        if _companion_handle:
            KERNEL32.TerminateProcess(_companion_handle, 0)
        if _inject_helper_handle:
            try:
                KERNEL32.TerminateProcess(_inject_helper_handle, 0)
            except Exception:
                pass
        logger.info("=== Apollo Centinela Service detenido ===")

if __name__ == "__main__":
    # Windows Service: hay que registrarse con el SCM o sc start queda en START_PENDING.
    # Si se ejecuta a mano (consola/debug), StartServiceCtrlDispatcher falla con 1063
    # y corremos el loop directo.
    SERVICE_WIN32_OWN_PROCESS = 0x00000010
    SERVICE_ACCEPT_STOP = 0x00000001
    SERVICE_ACCEPT_SHUTDOWN = 0x00000004
    SERVICE_RUNNING = 0x00000004
    SERVICE_STOP_PENDING = 0x00000003
    SERVICE_STOPPED = 0x00000001
    SERVICE_START_PENDING = 0x00000002
    SERVICE_CONTROL_STOP = 0x00000001
    SERVICE_CONTROL_SHUTDOWN = 0x00000005
    ERROR_FAILED_SERVICE_CONTROLLER_CONNECT = 1063

    class SERVICE_STATUS(ctypes.Structure):
        _fields_ = [
            ("dwServiceType", ctypes.wintypes.DWORD),
            ("dwCurrentState", ctypes.wintypes.DWORD),
            ("dwControlsAccepted", ctypes.wintypes.DWORD),
            ("dwWin32ExitCode", ctypes.wintypes.DWORD),
            ("dwServiceSpecificExitCode", ctypes.wintypes.DWORD),
            ("dwCheckPoint", ctypes.wintypes.DWORD),
            ("dwWaitHint", ctypes.wintypes.DWORD),
        ]

    class SERVICE_TABLE_ENTRYW(ctypes.Structure):
        _fields_ = [
            ("lpServiceName", ctypes.wintypes.LPWSTR),
            ("lpServiceProc", ctypes.c_void_p),
        ]

    ADVAPI32.RegisterServiceCtrlHandlerW.argtypes = [
        ctypes.wintypes.LPCWSTR, ctypes.c_void_p
    ]
    ADVAPI32.RegisterServiceCtrlHandlerW.restype = ctypes.wintypes.HANDLE
    ADVAPI32.SetServiceStatus.argtypes = [
        ctypes.wintypes.HANDLE, ctypes.POINTER(SERVICE_STATUS)
    ]
    ADVAPI32.SetServiceStatus.restype = ctypes.wintypes.BOOL
    ADVAPI32.StartServiceCtrlDispatcherW.argtypes = [ctypes.POINTER(SERVICE_TABLE_ENTRYW)]
    ADVAPI32.StartServiceCtrlDispatcherW.restype = ctypes.wintypes.BOOL

    _status_handle = None
    _svc_status = SERVICE_STATUS()

    def _report_svc_status(state, win32_exit=0, wait_hint=0, checkpoint=0):
        _svc_status.dwServiceType = SERVICE_WIN32_OWN_PROCESS
        _svc_status.dwCurrentState = state
        accepted = 0
        if state == SERVICE_RUNNING:
            accepted = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN
        _svc_status.dwControlsAccepted = accepted
        _svc_status.dwWin32ExitCode = win32_exit
        _svc_status.dwServiceSpecificExitCode = 0
        _svc_status.dwCheckPoint = checkpoint
        _svc_status.dwWaitHint = wait_hint
        if _status_handle:
            ADVAPI32.SetServiceStatus(_status_handle, ctypes.byref(_svc_status))

    HANDLER_FN = ctypes.WINFUNCTYPE(None, ctypes.wintypes.DWORD)

    @HANDLER_FN
    def _service_ctrl_handler(ctrl_code):
        global _svc_running
        if ctrl_code in (SERVICE_CONTROL_STOP, SERVICE_CONTROL_SHUTDOWN):
            logger.info("[SCM] Stop/Shutdown recibido (ctrl=%s)", ctrl_code)
            _report_svc_status(SERVICE_STOP_PENDING, wait_hint=8000, checkpoint=1)
            _svc_running = False

    SERVICE_MAIN_FN = ctypes.WINFUNCTYPE(
        None, ctypes.wintypes.DWORD, ctypes.POINTER(ctypes.wintypes.LPWSTR)
    )

    @SERVICE_MAIN_FN
    def _service_main(argc, argv):
        global _status_handle, _svc_running
        try:
            _status_handle = ADVAPI32.RegisterServiceCtrlHandlerW(
                SERVICE_NAME, _service_ctrl_handler
            )
            if not _status_handle:
                logger.error(
                    "[SCM] RegisterServiceCtrlHandlerW fallo error=%s",
                    KERNEL32.GetLastError(),
                )
                return
            # Reportar RUNNING al toque: si no, sc start queda START_PENDING eterno.
            _report_svc_status(SERVICE_START_PENDING, wait_hint=2000, checkpoint=1)
            _svc_running = True
            _report_svc_status(SERVICE_RUNNING)
            logger.info("[SCM] Servicio RUNNING (v%s)", __version__)
            run_as_service()
        except Exception as e:
            logger.exception("[SCM] ServiceMain error: %s", e)
        finally:
            _svc_running = False
            try:
                _report_svc_status(SERVICE_STOPPED)
            except Exception:
                pass
            logger.info("[SCM] Servicio STOPPED")
            # Los hilos daemon (monitores/WS) pueden quedar colgados al salir y
            # retener el proceso vivo aunque el SCM ya lo reporto STOPPED:
            # os._exit garantiza la muerte real del proceso de servicio.
            os._exit(0)

    # Mantener refs globales (ctypes callbacks)
    globals()["_service_ctrl_handler_ref"] = _service_ctrl_handler
    globals()["_service_main_ref"] = _service_main

    dispatch_table = (SERVICE_TABLE_ENTRYW * 2)()
    dispatch_table[0].lpServiceName = SERVICE_NAME
    dispatch_table[0].lpServiceProc = ctypes.cast(_service_main, ctypes.c_void_p)
    dispatch_table[1].lpServiceName = None
    dispatch_table[1].lpServiceProc = None

    ok = ADVAPI32.StartServiceCtrlDispatcherW(dispatch_table)
    if not ok:
        err = KERNEL32.GetLastError()
        if err == ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
            logger.info("[SCM] Modo interactivo (no SCM) — run_as_service directo")
            run_as_service()
        else:
            logger.error("[SCM] StartServiceCtrlDispatcherW fallo error=%s", err)
            sys.exit(err)
