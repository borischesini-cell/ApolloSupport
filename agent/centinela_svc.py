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
__version__     = "3.1.23"
BASE_DIR        = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
CONFIG_DIR      = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport")
CONFIG_FILE     = os.path.join(CONFIG_DIR, "centinela.dat")
LEGACY_CONFIG   = os.path.join(CONFIG_DIR, "centinela_config.json")
LOG_FILE        = os.path.join(CONFIG_DIR, "service.log")
COMPANION_EXE   = os.path.normpath(os.path.join(BASE_DIR, "ApolloCentinela.exe"))
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
        return WTSAPI32.WTSGetActiveConsoleSessionId()

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
        best_session = WTSAPI32.WTSGetActiveConsoleSessionId()

    return best_session

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
    if session_id == 0xFFFFFFFF:
        return None


    user_token = ctypes.wintypes.HANDLE()
    has_user_token = True
    if not WTSAPI32.WTSQueryUserToken(session_id, ctypes.byref(user_token)):
        logger.warning("WTSQueryUserToken fallo (error %d). Cayendo a token SYSTEM para session %d", KERNEL32.GetLastError(), session_id)
        has_user_token = False
        # Usar el token del proceso actual (SYSTEM)
        if not ADVAPI32.OpenProcessToken(KERNEL32.GetCurrentProcess(), 0x02000000, ctypes.byref(user_token)):
            logger.error("OpenProcessToken fallo (error %d)", KERNEL32.GetLastError())
            return None

    dup_token = ctypes.wintypes.HANDLE()
    if not ADVAPI32.DuplicateTokenEx(
        user_token,
        0x02000000,  # MAXIMUM_ALLOWED
        None,
        2,  # SecurityImpersonation
        1,  # TokenPrimary
        ctypes.byref(dup_token),
    ):
        err = KERNEL32.GetLastError()
        KERNEL32.CloseHandle(user_token)
        logger.error("DuplicateTokenEx fallo (error %d)", err)
        return None
    KERNEL32.CloseHandle(user_token)

    if not has_user_token:
        # Habilitar SE_TCB_NAME antes de cambiar el SessionId
        def enable_privilege(priv_name):
            TOKEN_ADJUST_PRIVILEGES = 0x0020
            TOKEN_QUERY = 0x0008
            hToken = ctypes.wintypes.HANDLE()
            if ADVAPI32.OpenProcessToken(KERNEL32.GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(hToken)):
                luid = ctypes.c_int64()
                if ADVAPI32.LookupPrivilegeValueW(None, priv_name, ctypes.byref(luid)):
                    class TOKEN_PRIVILEGES(ctypes.Structure):
                        _fields_ = [("PrivilegeCount", ctypes.c_uint32), ("Privileges", ctypes.c_int64 * 1), ("Attributes", ctypes.c_uint32 * 1)]
                    tp = TOKEN_PRIVILEGES()
                    tp.PrivilegeCount = 1
                    tp.Privileges[0] = luid.value
                    tp.Attributes[0] = 2 # SE_PRIVILEGE_ENABLED
                    ADVAPI32.AdjustTokenPrivileges(hToken, False, ctypes.byref(tp), ctypes.sizeof(tp), None, None)
                KERNEL32.CloseHandle(hToken)
                
        enable_privilege("SeTcbPrivilege")
        enable_privilege("SeAssignPrimaryTokenPrivilege")
        enable_privilege("SeIncreaseQuotaPrivilege")

        # Setear el SessionId en el token duplicado
        session_id_c = ctypes.c_uint32(session_id)
        if not ADVAPI32.SetTokenInformation(
            dup_token,
            12,  # TokenSessionId
            ctypes.byref(session_id_c),
            ctypes.sizeof(session_id_c)
        ):
            logger.error("SetTokenInformation fallo para session %d (error %d)", session_id, KERNEL32.GetLastError())
    
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
    if has_user_token:
        si.lpDesktop = "winsta0\\default"
    else:
        si.lpDesktop = "winsta0\\Winlogon"
        
    si.dwFlags = 0x00000001   # STARTF_USESHOWWINDOW
    si.wShowWindow = 0        # SW_HIDE

    pi = PROCESS_INFORMATION()
    work_dir = os.path.dirname(exe_path)
    app_name = ctypes.create_unicode_buffer(exe_path)
    # lpCommandLine debe ser buffer mutable; con lpApplicationName fijado, el comando puede citar el mismo exe
    cmdline_str = f'"{exe_path}"' if not args else f'"{exe_path}" {args}'
    cmdline = ctypes.create_unicode_buffer(cmdline_str)
    work_buf = ctypes.create_unicode_buffer(work_dir)

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
        KERNEL32.CloseHandle(pi.hThread)
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
_svc_running      = True

def companion_monitor():
    """
    Hilo que vigila la sesion activa del usuario y mantiene el companion vivo.
    - Si hay usuario y el companion murio: lo reinicia.
    - Si el usuario cerro sesion: mata el companion.
    NOTA: NO reinicia por cambio de session_id (WTSEnumerateSessionsW puede
    ser inconsistente entre llamadas en servidores RDP multi-sesion).
    """
    global _companion_handle, _last_session

    while _svc_running:
        # --- SOPORTE DE SWITCH_SESSION.TXT ---
        SWITCH_SESSION_FILE = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport", "switch_session.txt")
        if os.path.isfile(SWITCH_SESSION_FILE):
            try:
                with open(SWITCH_SESSION_FILE) as f:
                    switch_data = json.load(f)
                target_sess = int(switch_data.get("session_id", -1))
                if target_sess != -1:
                    logger.info("[SWITCH] Detectada solicitud de cambio de sesion a %d", target_sess)
                    # Matar companion actual
                    if _companion_handle:
                        KERNEL32.TerminateProcess(_companion_handle, 0)
                        KERNEL32.CloseHandle(_companion_handle)
                        _companion_handle = None
                    
                    # Lanzar en la sesion destino
                    _companion_handle = spawn_in_user_session(COMPANION_EXE, session_id=target_sess)
                    _last_session = target_sess
                    
                    # Eliminar archivo de señal
                    os.remove(SWITCH_SESSION_FILE)
            except Exception as switch_err:
                logger.error("[SWITCH] Error procesando switch: %s", switch_err)
                if os.path.exists(SWITCH_SESSION_FILE):
                    try: os.remove(SWITCH_SESSION_FILE)
                    except: pass

        session_id = get_active_session_id()
        has_user   = session_id != 0xFFFFFFFF


        if has_user:
            companion_alive = is_process_alive(_companion_handle)

            if not companion_alive:
                # Companion caido o nunca lanzado → lanzar ahora
                if _companion_handle:
                    KERNEL32.CloseHandle(_companion_handle)
                    _companion_handle = None

                logger.info("Companion muerto o ausente — relanzando en sesion %d", session_id)
                time.sleep(3)  # Dar tiempo a que el escritorio del usuario cargue
                _companion_handle = spawn_in_user_session(COMPANION_EXE)
                _last_session = session_id
            else:
                # Companion vivo — solo actualizar la sesion registrada
                _last_session = session_id
        else:
            # Sin usuario: matar companion si estaba corriendo
            if _companion_handle:
                KERNEL32.TerminateProcess(_companion_handle, 0)
                KERNEL32.CloseHandle(_companion_handle)
                _companion_handle = None
                _last_session     = None
                logger.info("Usuario cerro sesion — companion terminado")

        time.sleep(10)


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

async def perform_update(url):
    import urllib.request
    import tempfile
    import shutil
    try:
        temp_dir = tempfile.gettempdir()
        installer_path = os.path.join(temp_dir, "ApolloSetup_update.exe")
        
        logger.info(f"[OTA] Descargando actualizacion desde {url}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        with urllib.request.urlopen(req, timeout=30) as response, open(installer_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        logger.info("[OTA] Descarga completada. Ejecutando instalacion silenciosa y cerrando servicio...")
        
        # Ejecutar el instalador desatendido de InnoSetup (se reiniciara el servicio solo)
        subprocess.Popen([installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        
        # Nos cerramos a nosotros mismos para liberar archivos y dejar que el instalador pise los .exe
        sys.exit(0)
    except Exception as e:
        logger.error(f"[OTA] Error aplicando actualizacion: {e}")

async def update_checker_loop():
    while True:
        try:
            # Esperar 2 minutos despues de arrancar antes de la primera comprobacion
            await asyncio.sleep(120)
            
            cfg = load_config()
            if cfg and 'base_ws_url' in cfg:
                base_url = cfg['base_ws_url'].replace('wss://', 'https://').replace('ws://', 'http://').split('/api/ws')[0]
                api_url = f"{base_url}/api/centinela/update_check"
                
                import urllib.request
                req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = json.loads(response.read().decode())
                
                remote_version = data.get("version", "0.0.0")
                download_url = data.get("url", "")
                
                if parse_version(remote_version) > parse_version(__version__) and download_url:
                    logger.info(f"[OTA] Nueva version {remote_version} detectada (Actual: {__version__}). Iniciando update...")
                    await perform_update(download_url)
        except Exception as e:
            logger.debug(f"[OTA] Chequeo de version fallido: {e}")
            
        # Comprobar cada 12 horas
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
    logger.info("=== Apollo Centinela Service iniciando ===")
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

    monitor_thread = threading.Thread(target=companion_monitor, daemon=True)
    monitor_thread.start()

    updater_thread = threading.Thread(target=lambda: asyncio.run(update_checker_loop()), daemon=True)
    updater_thread.start()

    # Mantener el proceso vivo (el monitor corre en el hilo daemon)
    try:
        while _svc_running:
            time.sleep(1)
            
            # --- SAS SIGNAL CHECK ---
            force_sas_file = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport", "force_sas.txt")
            if os.path.isfile(force_sas_file):
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
                    sas_dll = ctypes.windll.LoadLibrary("sas.dll")
                    sas_dll.SendSAS(False)
                    logger.info("[SAS] Monitor despertado y SendSAS(False) ejecutado.")
                    
                    # Restaurar estado
                    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
                except Exception as e:
                    logger.error(f"[SAS] Error ejecutando SendSAS: {e}")
                    
            # --- LOGIN INJECTION SIGNAL CHECK ---
            inject_pwd_file = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport", "inject_password.txt")
            if os.path.isfile(inject_pwd_file):
                logger.info("[LOGIN] Detectado signal inject_password.txt. Delegando al Companion en Winlogon...")
                try:
                    # Usamos spawn_in_user_session para lanzar el companion dentro del desktop de Winlogon
                    # Esto garantiza que el proceso tiene acceso interactivo para inyectar teclas.
                    spawn_in_user_session(COMPANION_EXE, args="--type-credentials")
                except Exception as e:
                    logger.error(f"[LOGIN] Error lanzando companion para login: {e}")
                    
            # --- OTA UPDATE SIGNAL CHECK ---
            force_ota_file = os.path.join(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "ApolloSupport", "force_ota.txt")
            if os.path.isfile(force_ota_file):
                logger.info("[OTA] Detectado archivo signal force_ota.txt. Forzando actualizacion...")
                try:
                    os.remove(force_ota_file)
                except:
                    pass
                
                cfg = load_config()
                if cfg and 'base_ws_url' in cfg:
                    base_url = cfg['base_ws_url'].replace('wss://', 'https://').replace('ws://', 'http://').split('/api/ws')[0]
                    api_url = f"{base_url}/api/centinela/update_check"
                    
                    import urllib.request
                    try:
                        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                        with urllib.request.urlopen(req, timeout=10) as response:
                            data = json.loads(response.read().decode())
                        download_url = data.get("url", "")
                        if download_url:
                            # Lanzar en thread separado
                            threading.Thread(target=lambda: asyncio.run(perform_update(download_url)), daemon=True).start()
                    except Exception as e:
                        logger.error(f"[OTA] Error comprobando API para force update: {e}")
                        
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        _svc_running = False
        if _companion_handle:
            KERNEL32.TerminateProcess(_companion_handle, 0)
        logger.info("=== Apollo Centinela Service detenido ===")

if __name__ == "__main__":
    run_as_service()


# ¿Cómo lo usarás tú a partir de mañana?
# Haces un cambio groso en el código.
# Abres centinela_svc.py y cambias arriba de todo __version__ = "3.1.23".
# Le das doble clic a tu .bat mágico para generar el instalador.
# Agarras el nuevo ApolloSetup_v3.1.3.exe (Universal), lo renombras simplemente a ApolloSetup.exe y lo subes a la carpeta updates/ de tu servidor.
# Editas el version.json del servidor y le pones "version": "3.1.3".
# Te sientas a tomar un café. En las próximas 12 horas, todos los clientes del país se habrán actualizado solos, sin que les salte ni un solo cartelito en la pantalla.