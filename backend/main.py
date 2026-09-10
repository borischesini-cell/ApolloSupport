import os
import sys
# Asegurar que el directorio de este script esté en el sys.path para resolución robusta de paquetes ('core', 'models', etc.)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import logging.handlers

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LOGGING ESTRUCTURADO
# - Archivo rotativo diario, retención 30 días
# - Formato: timestamp | level | módulo | mensaje
# - Salida simultánea a consola y archivo
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_formatter = logging.Formatter(
    fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Handler de archivo rotativo diario (solo WARNING+ para no llenar disco)
file_handler = logging.handlers.RotatingFileHandler(
    filename=os.path.join(LOG_DIR, "apollo.log"),
    maxBytes=10 * 1024 * 1024,  # 10 MB por archivo
    backupCount=5,              # Retener 5 archivos históricos (50 MB total max)
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)  # Cambiado a INFO temporalmente para capturar logs de WebSocket

# Handler de consola (INFO+ para seguimiento en tiempo real)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Logger raíz de la aplicación
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

# Silenciar loggers ruidosos de librerías externas
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.ERROR)   # Silencia cada request HTTP
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("apollo")
logger.info("=== ApolloSupport Backend iniciando ===")

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, File, UploadFile, Body
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import text
from typing import List, Dict, Any, Optional
from jose import JWTError, jwt
from datetime import datetime
import shutil
import asyncio

import subprocess
import tempfile
import time
from cryptography.fernet import Fernet

from collections import deque
import uuid
from datetime import timedelta

from database import engine, Base, get_db, SessionLocal
import models
import schemas
import auth
import httpx
from core.erp_bridge import ERPBridge

BACKEND_VERSION = "3.2.6"
BACKEND_BUILD = "2026-06-02"
BACKEND_VERSION_TAG = "WebCodecs-HD"

# Instanciamos la Aplicación FastAPI
app = FastAPI(
    title="ApolloSupport API",
    description="Motor Central Seguro para Master IS.",
    version=BACKEND_VERSION,
    docs_url="/documentacion"
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    logger.info("="*60)
    logger.info("APOLLO BACKEND v%s build %s (%s)", BACKEND_VERSION, BACKEND_BUILD, BACKEND_VERSION_TAG)
    logger.info("="*60)
    try:
        print("\n" + "="*60)
        print(f"APOLLO BACKEND v{BACKEND_VERSION} build {BACKEND_BUILD} ({BACKEND_VERSION_TAG})")
        print("="*60 + "\n")
    except Exception:
        pass

@app.get("/api/hq-test")
def test_hq_endpoint():
    return {
        "status": "OK",
        "mensaje": "Backend Apollo activo",
        "version": BACKEND_VERSION,
        "build": BACKEND_BUILD,
        "tag": BACKEND_VERSION_TAG,
    }


@app.get("/api/version")
def get_app_version():
    """Versión desplegada del backend (pública, sin auth)."""
    return {
        "component": "backend",
        "version": BACKEND_VERSION,
        "build": BACKEND_BUILD,
        "tag": BACKEND_VERSION_TAG,
    }

from fastapi import Request
from fastapi.responses import JSONResponse
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception | %s %s | %s",
        request.method, request.url,
        traceback.format_exc()
    )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

# Configuración Global
from dotenv import load_dotenv
load_dotenv()
API_URL = os.environ.get("API_URL", "http://localhost:8001/api")

# Asegurar directorios base
for d in ["temp_files", "uploads", "temp_files/uploads"]:
    if not os.path.exists(d): 
        os.makedirs(d)

app.mount("/api/temp", StaticFiles(directory="temp_files"), name="static_temp")
app.mount("/uploads", StaticFiles(directory="uploads"), name="static_uploads")
os.makedirs("updates", exist_ok=True)
app.mount("/updates", StaticFiles(directory="updates"), name="static_updates")

models.Base.metadata.create_all(bind=engine)

def _ensure_centinela_assist_id_column():
    """Agrega centinela_devices.assist_id si falta (ID que muestra ApolloSoporte)."""
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE centinela_devices ADD COLUMN IF NOT EXISTS assist_id VARCHAR"
            ))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_centinela_devices_assist_id ON centinela_devices (assist_id)"
            ))
    except Exception as e:
        logger.warning("[SCHEMA] No se pudo asegurar columna assist_id: %s", e)

_ensure_centinela_assist_id_column()

async def server_ping_loop(device_id: int):
    """ Mantiene viva la conexión WebSocket enviando un ping cada 20 segundos. """
    while True:
        await asyncio.sleep(20)
        try:
            # send_json_safe ya maneja el lock y errores
            success = await manager.send_json_safe(device_id, {"type": "ping"})
            if not success: break
        except Exception: break


def _db_cleanup_device_on_idle_viewers(device_id: int):
    """ Libera el dispositivo en la base de datos si no hay técnicos conectados. """
    db_clean = SessionLocal()
    try:
        dev = db_clean.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if dev and dev.current_technician_id is not None:
            logger.info(f"[CLEANUP] Autoliberando dispositivo '{dev.device_name}' (ID: {device_id}) en DB por inactividad de espectadores.")
            dev.current_technician_id = None
            dev.session_start = None
            db_clean.commit()
    except Exception as db_err:
        logger.error(f"[CLEANUP DB ERROR] Error liberando dispositivo {device_id}: {db_err}")
    finally:
        db_clean.close()


async def periodic_viewer_cleanup():
    logger.info("[CLEANUP] Tarea periódica de monitoreo de espectadores iniciada.")
    while True:
        try:
            await asyncio.sleep(4.0)
            now = datetime.utcnow()
            stale_threshold = 8.0
            
            # Limpiar espectadores inactivos para todos los dispositivos activos
            for device_id in list(manager.active_connections.keys()):
                if True:
                    viewers_dict = manager.device_viewers.setdefault(device_id, {})
                    to_delete = []
                    active_viewers = []
                    
                    for u_id, (u_name, last_seen) in viewers_dict.items():
                        if (now - last_seen).total_seconds() > stale_threshold:
                            to_delete.append(u_id)
                        else:
                            active_viewers.append(u_name)
                            
                    if to_delete:
                        for u_id in to_delete:
                            if u_id in viewers_dict:
                                del viewers_dict[u_id]
                        
                    # Notificar al cliente con la lista actualizada de técnicos activos (que puede estar vacía)
                    # OJO: Si hay viewers por WS, no enviar array vacio, usar un placeholder
                    final_viewers = list(active_viewers)
                    has_ws_viewers = (device_id in manager.viewer_connections and len(manager.viewer_connections[device_id]) > 0) or manager.has_hq_viewers(device_id)
                    try:
                        from session_recorder import recorder_manager
                        if recorder_manager.is_recording_device(device_id):
                            has_ws_viewers = True
                            if "Grabador Agenda" not in final_viewers:
                                final_viewers.append("Grabador Agenda")
                    except Exception:
                        pass
                    
                    if len(final_viewers) == 0 and has_ws_viewers:
                        final_viewers = ["Soporte Web (WS)"]

                    if to_delete or has_ws_viewers:
                        await manager.send_json_safe(device_id, {
                            "type": "active_technicians",
                            "technicians": final_viewers
                        })
                        manager.last_viewer_notification[device_id] = now

                    # Autoliberación de PC en DB si no quedan espectadores activos (ni standard WS, ni HQ WS, ni HTTP polling)
                    if len(viewers_dict) == 0 and not has_ws_viewers:
                        await asyncio.to_thread(_db_cleanup_device_on_idle_viewers, device_id)
        except Exception as e:
            logger.error(f"[CLEANUP ERROR] Error en limpieza periódica de espectadores: {e}")

# Resetear estado online de dispositivos al iniciar el servidor
@app.on_event("startup")
def startup_event():
    # Iniciar tareas asíncronas periódicas
    asyncio.get_event_loop().create_task(periodic_viewer_cleanup())
    asyncio.get_event_loop().create_task(periodic_orphan_session_cleanup())
    asyncio.get_event_loop().create_task(periodic_zombie_cleanup())
    try:
        from agenda import periodic_agenda_worker as _agenda_worker
        asyncio.get_event_loop().create_task(_agenda_worker())
        logger.info("[STARTUP] Agenda worker programado")
    except Exception as e:
        logger.error("[STARTUP] No se pudo iniciar agenda worker: %s", e)

    db = SessionLocal()
    try:
        db.query(models.CentinelaDevice).update({
            models.CentinelaDevice.is_online: False,
            models.CentinelaDevice.current_technician_id: None,
            models.CentinelaDevice.session_start: None
        })
        db.commit()
        logger.info("[STARTUP] Reset de estado online y liberación de dispositivos completado.")

        # Cerrar sesiones huérfanas que quedaron abiertas del reinicio anterior
        _close_orphaned_sessions(db)
    except Exception as e:
        logger.error("[STARTUP] Error al resetear estados de dispositivos: %s", e)
    finally:
        db.close()


def _close_orphaned_sessions(db: Session):
    """
    Cierra SupportSessions cuyo end_time es NULL y el dispositivo no se vio
    en los últimos 10 minutos. Esto cubre el caso en que el técnico cierra
    el navegador sin hacer clic en 'Cerrar Conexión'.
    """
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        orphans = db.query(models.SupportSession).filter(
            models.SupportSession.end_time == None
        ).all()

        closed = 0
        for s in orphans:
            device = db.query(models.CentinelaDevice).filter(
                models.CentinelaDevice.id == s.device_id
            ).first()
            # Si el dispositivo no existe o no se vio en 10 min â†’ cerrar sesión
            if device is None or (device.last_seen and device.last_seen < cutoff):
                s.end_time = datetime.utcnow()
                closed += 1

        if closed:
            db.commit()
            logger.warning("[ORPHAN] Cerradas %d sesiones huérfanas al iniciar.", closed)
    except Exception as e:
        logger.error("[ORPHAN] Error cerrando sesiones huérfanas: %s", e)


def _db_run_orphan_session_cleanup():
    db = SessionLocal()
    try:
        _close_orphaned_sessions(db)
    except Exception as e:
        logger.error("[ORPHAN] Error en ciclo periódico: %s", e)
    finally:
        db.close()


async def periodic_orphan_session_cleanup():
    """
    Tarea periódica que cierra sesiones de soporte huérfanas cada 5 minutos.
    Una sesión es huérfana si end_time=NULL y el agente no se vio en 10+ minutos.
    """
    logger.info("[ORPHAN] Tarea de limpieza de sesiones huérfanas iniciada.")
    while True:
        await asyncio.sleep(300)  # Cada 5 minutos
        await asyncio.to_thread(_db_run_orphan_session_cleanup)


def _db_run_zombie_cleanup():
    db = SessionLocal()
    try:
        online_devices = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.is_online == True).all()
        updated = 0
        for dev in online_devices:
            if dev.id not in manager.active_connections:
                dev.is_online = False
                dev.current_technician_id = None
                dev.session_start = None
                updated += 1
        if updated > 0:
            db.commit()
            logger.info(f"[ZOMBIE-CLEANUP] Corregidos {updated} dispositivos zombie en DB.")
    except Exception as e:
        logger.error("[ZOMBIE-CLEANUP] Error en ciclo de limpieza: %s", e)
    finally:
        db.close()


async def periodic_zombie_cleanup():
    """
    Tarea periódica que sincroniza el estado online de la base de datos con las conexiones Websocket activas.
    Si un dispositivo figura como online en la DB pero NO está en manager.active_connections,
    lo marca como offline (is_online=False).
    """
    logger.info("[ZOMBIE-CLEANUP] Tarea periódica de limpieza de conexiones zombie iniciada.")
    while True:
        await asyncio.sleep(30)
        await asyncio.to_thread(_db_run_zombie_cleanup)


# ==========================================
# CONFIGURACIÓN DE SEGURIDAD (OAUTH2)
# ==========================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """ 
    Filtro de Seguridad: Revisa si el usuario trajo su llave (JWT).
    Se usa inyectándolo en las rutas que queramos proteger.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o sesión expirada.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.email == email).first()
    if user is None or not user.activo:
        raise credentials_exception
    return user

async def send_push_notification(expo_token: str, title: str, body: str):
    """ Envía una notificación Push a través de los servidores de Expo. """
    url = "https://exp.host/--/api/v2/push/send"
    payload = {
        "to": expo_token,
        "title": title,
        "body": body,
        "sound": "default",
        "data": {"type": "alert"}
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
        except Exception as e:
            logger.error("Error enviando Push: {e}")
            return False

# ==========================================
# RUTA DE LOGIN (Generar Token)
# ==========================================
@app.post("/api/token", response_model=schemas.Token, tags=["Seguridad"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Buscamos el email
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    
    # Comprobamos la clave encriptada cruzándola con la tipeada
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Actualizar estado de login
    user.is_online = True
    user.last_login = datetime.utcnow()
    user.last_activity = datetime.utcnow()
    user.current_page = "Dashboard"
    user.current_task = "Inició sesión"
    db.commit()
    
    # Otorgamos el token de pase
    access_token = auth.create_access_token(data={"sub": user.email, "rol": user.rol})
    
    return {
        "access_token": access_token, 
        "token_type": "bearer", 
        "usuario": {
            "nombre": user.nombre, 
            "rol": user.rol, 
            "email": user.email,
            "id": user.id,
            "full_name": user.full_name,
            "departamento": user.departamento,
            "profile_picture": user.profile_picture,
            "celular": user.celular
        }
    }

@app.get("/api/public/users", response_model=List[Dict[str, Any]], tags=["Seguridad"])
def obtener_usuarios_publicos(db: Session = Depends(get_db)):
    """ Retorna una lista pública de nombres y correos de los usuarios activos para sugerencias de autocompletado """
    users = db.query(models.User).filter(models.User.activo == True).order_by(models.User.nombre.asc()).all()
    return [{"email": u.email, "nombre": u.nombre} for u in users]

@app.post("/api/test-db-write", tags=["Soporte"])
def test_db_write(db: Session = Depends(get_db)):
    try:
        import models
        models_file = getattr(models, "__file__", "unknown")
        has_session = hasattr(models, "SupportSession")
        user = db.query(models.User).filter(models.User.id == 1).first()
        device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == 753).first()
        log = models.AccessLog(technician_id=1, client_id=91, action="TEST DIAGNOSTICO")
        db.add(log)
        db.commit()
        return {
            "status": "ok", 
            "user": user.nombre, 
            "device": device.device_name,
            "models_file": models_file,
            "has_SupportSession": has_session
        }
    except Exception as e:
        import traceback
        return {"status": "error", "error": str(e), "traceback": traceback.format_exc()}

# ==========================================
# RUTAS DE CLIENTES (Protegidas)
# ==========================================
@app.post("/api/clients/", response_model=schemas.ClientOut, tags=["Clientes"])
def crear_cliente(cliente: schemas.ClientCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    import erp_licensing as _el
    payload = cliente.model_dump()
    payload = _apply_clasificacion_from_catalog(db, payload)
    codigo = (payload.get("codigo") or "").strip().upper()
    if codigo.isdigit():
        codigo = codigo.zfill(4)[:4]
    if codigo:
        payload["codigo"] = codigo
        if db.query(models.Client).filter(models.Client.codigo == codigo).first():
            raise HTTPException(status_code=400, detail=f"El número de cliente ya existe ({codigo})")
        versi = (payload.get("version_apollo") or "E")[:1].upper()
        payload["version_apollo"] = versi
        if versi in "ESRP" and not _el.check_client_code_version(codigo, versi):
            raise HTTPException(status_code=400, detail="El número de Cliente (Serie) no coincide con la Versión de AGC.")
        import cligesco_dbf
        if cligesco_dbf.code_exists(codigo):
            raise HTTPException(status_code=400, detail=f"El número de cliente ya existe en CLIGESCO.DBF ({codigo})")
        try:
            cligesco_dbf.upsert_client(payload, create=True)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo grabar CLIGESCO.DBF: {e}")
    db_client = models.Client(**payload)
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.get("/api/clients/", response_model=List[schemas.ClientOut], tags=["Clientes"])
def obtener_clientes(skip: int = 0, limit: int = 5000, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Client).options(joinedload(models.Client.devices).joinedload(models.CentinelaDevice.technician)).order_by(models.Client.codigo.asc().nulls_last(), models.Client.razon_social.asc()).offset(skip).limit(limit).all()

@app.get("/api/clients/next-code", tags=["Clientes"])
def siguiente_codigo_gesacti(version: str = "E", db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Sugiere el próximo código de 4 caracteres según la versión GesActi (E/S/R/P)."""
    versi = (version or "E").upper()[:1]
    codes = [c[0] for c in db.query(models.Client.codigo).filter(models.Client.codigo.isnot(None)).all() if c[0]]
    try:
        import cligesco_dbf
        codes = list({*(c.strip().upper() for c in codes), *cligesco_dbf.list_codes()})
    except Exception:
        pass
    matching = [c.strip().upper().ljust(4)[:4] for c in codes if erp_licensing.check_client_code_version(c, versi)]
    def bump(code: str) -> str:
        raw = code.strip()
        if raw.isdigit():
            return str(int(raw) + 1).zfill(4)[:4]
        prefix, digits = "", ""
        for ch in raw:
            if ch.isdigit():
                digits += ch
            elif not digits:
                prefix += ch
        if digits:
            nxt = str(int(digits) + 1).zfill(len(digits))
            return (prefix + nxt).ljust(4)[:4]
        return raw

    if matching:
        matching.sort()
        suggested = bump(matching[-1])
        while suggested in {x.strip().upper() for x in codes} or not erp_licensing.check_client_code_version(suggested, versi):
            suggested = bump(suggested)
            if suggested == matching[-1]:
                break
    else:
        suggested = {"E": "0001", "S": "M001", "R": "R001", "P": "V001"}.get(versi, "0001")
    return {"codigo": suggested, "version": versi}

@app.post("/api/clients/sync", tags=["Clientes"])
def sincronizar_clientes_dbf(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Sincroniza CLIGESCO.DBF y luego refresca saldos desde Ventas\\Clientes.CSaldo."""
    try:
        from sync_dbf_to_postgres import sync_data
        sync_data()
        saldos = _sync_saldos_from_clientes_erp(db)
        return {
            "status": "success",
            "message": "Sincronización DBF + saldos ERP (Clientes:CSaldo) completada.",
            "saldos": saldos,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la sincronización: {str(e)}")


def _sync_saldos_from_clientes_erp(db: Session) -> dict:
    """
    Actualiza clients.saldo y fecha_ultimo_pago desde Ventas\\Clientes (CSaldo / CULPA),
    matcheando por CCLIFAC (código de facturación ERP).
    """
    saldos = ERPBridge.browse_clientes_saldos()
    updated = 0
    skipped = 0
    for cli in db.query(models.Client).filter(models.Client.cclifac.isnot(None)).all():
        fac = str(cli.cclifac or "").strip()
        if not fac:
            skipped += 1
            continue
        keys = [fac]
        if fac.isdigit():
            keys.extend([fac.zfill(7), fac.lstrip("0") or "0", fac.zfill(5)])
        hit = None
        for k in keys:
            if k in saldos:
                hit = saldos[k]
                break
        if not hit:
            skipped += 1
            continue
        cli.saldo = float(hit.get("saldo") or 0.0)
        if hit.get("fecha_ultimo_pago") is not None:
            cli.fecha_ultimo_pago = hit["fecha_ultimo_pago"]
        updated += 1
    db.commit()
    return {"updated": updated, "skipped": skipped, "erp_clientes": len(saldos)}


@app.post("/api/clients/sync-saldos-erp", tags=["Clientes"])
def sincronizar_saldos_erp(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Refresca saldos desde Clientes:CSaldo (sin tocar el resto de datos DBF)."""
    try:
        return {"status": "success", **_sync_saldos_from_clientes_erp(db)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sincronizando saldos ERP: {str(e)}")


# ==========================================
# ESTADOS DE CUENTA CORRIENTE (ClasiCli ERP)
# ==========================================
def _normalize_estado_codigo(codigo: str) -> str:
    c = (codigo or "").strip().upper()
    if c.isdigit() and len(c) < 5:
        c = c.zfill(5)
    return c[:10]


def _apply_clasificacion_from_catalog(db: Session, payload: dict) -> dict:
    """Normaliza CCLAS y completa CNOMCLAS desde el catálogo de estados."""
    cod = _normalize_estado_codigo(payload.get("clasificacion_codigo") or "")
    if not cod:
        payload["clasificacion_codigo"] = None
        return payload
    payload["clasificacion_codigo"] = cod
    row = db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.codigo == cod).first()
    if row:
        payload["clasificacion_nombre"] = (row.descripcion or "").strip()
    elif not (payload.get("clasificacion_nombre") or "").strip():
        payload["clasificacion_nombre"] = cod
    return payload


@app.get("/api/estados-cuenta-corriente", response_model=List[schemas.EstadoCuentaCorrienteOut], tags=["Estados Cta Cte"])
def listar_estados_cuenta_corriente(
    solo_activos: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.EstadoCuentaCorriente)
    if solo_activos:
        q = q.filter(models.EstadoCuentaCorriente.activo == True)  # noqa: E712
    return q.order_by(models.EstadoCuentaCorriente.codigo.asc()).all()


@app.post("/api/estados-cuenta-corriente", response_model=schemas.EstadoCuentaCorrienteOut, tags=["Estados Cta Cte"])
def crear_estado_cuenta_corriente(
    data: schemas.EstadoCuentaCorrienteCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    codigo = _normalize_estado_codigo(data.codigo)
    if not codigo:
        raise HTTPException(status_code=400, detail="El código es obligatorio.")
    if db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.codigo == codigo).first():
        raise HTTPException(status_code=400, detail=f"Ya existe el estado {codigo}.")
    row = models.EstadoCuentaCorriente(
        codigo=codigo,
        descripcion=(data.descripcion or "").strip()[:60],
        activo=bool(data.activo),
        origen="manual",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.put("/api/estados-cuenta-corriente/{estado_id}", response_model=schemas.EstadoCuentaCorrienteOut, tags=["Estados Cta Cte"])
def actualizar_estado_cuenta_corriente(
    estado_id: int,
    data: schemas.EstadoCuentaCorrienteUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.id == estado_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Estado no encontrado.")
    payload = data.model_dump(exclude_unset=True)
    if "descripcion" in payload and payload["descripcion"] is not None:
        row.descripcion = str(payload["descripcion"]).strip()[:60]
    if "activo" in payload and payload["activo"] is not None:
        row.activo = bool(payload["activo"])
    # Propagar nombre a clientes que usan este código
    if "descripcion" in payload:
        db.query(models.Client).filter(models.Client.clasificacion_codigo == row.codigo).update(
            {models.Client.clasificacion_nombre: row.descripcion},
            synchronize_session=False,
        )
    db.commit()
    db.refresh(row)
    return row


@app.delete("/api/estados-cuenta-corriente/{estado_id}", tags=["Estados Cta Cte"])
def eliminar_estado_cuenta_corriente(
    estado_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.id == estado_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Estado no encontrado.")
    usados = db.query(models.Client).filter(models.Client.clasificacion_codigo == row.codigo).count()
    if usados:
        row.activo = False
        db.commit()
        return {"status": "deactivated", "codigo": row.codigo, "clientes": usados, "message": "Estado en uso: se desactivó."}
    db.delete(row)
    db.commit()
    return {"status": "deleted", "codigo": row.codigo}


@app.post("/api/estados-cuenta-corriente/sync-erp", tags=["Estados Cta Cte"])
def sync_estados_cuenta_corriente_erp(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Importa/actualiza el catálogo desde Ventas\\ClasiCli del ERP."""
    try:
        items = ERPBridge.get_estados_cuenta_corriente()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo leer ClasiCli del ERP: {e}")

    # Asegurar NORMAL (00001) si el ERP no lo trae pero hay clientes con ese código
    codes_erp = {i["codigo"] for i in items}
    if "00001" not in codes_erp:
        items.append({"codigo": "00001", "descripcion": "NORMAL"})

    inserted = updated = 0
    for item in items:
        codigo = _normalize_estado_codigo(item.get("codigo") or "")
        if not codigo:
            continue
        desc = (item.get("descripcion") or "").strip()[:60]
        row = db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.codigo == codigo).first()
        if row:
            row.descripcion = desc or row.descripcion
            row.activo = True
            row.origen = "erp"
            updated += 1
        else:
            db.add(models.EstadoCuentaCorriente(
                codigo=codigo,
                descripcion=desc or codigo,
                activo=True,
                origen="erp",
            ))
            inserted += 1
    db.commit()

    # Completar nombres vacíos en clientes según catálogo
    catalog = {
        e.codigo: e.descripcion
        for e in db.query(models.EstadoCuentaCorriente).filter(models.EstadoCuentaCorriente.activo == True).all()  # noqa: E712
    }
    filled = 0
    for cli in db.query(models.Client).filter(models.Client.clasificacion_codigo.isnot(None)).all():
        cod = (cli.clasificacion_codigo or "").strip()
        if not cod:
            continue
        if cod.isdigit() and len(cod) < 5:
            cod = cod.zfill(5)
            cli.clasificacion_codigo = cod
        nombre = catalog.get(cod)
        if nombre and (not cli.clasificacion_nombre or not str(cli.clasificacion_nombre).strip()):
            cli.clasificacion_nombre = nombre
            filled += 1
    db.commit()
    return {
        "status": "success",
        "from_erp": len(items),
        "inserted": inserted,
        "updated": updated,
        "clientes_nombre_completado": filled,
    }


@app.put("/api/clients/{client_id}", response_model=schemas.ClientOut, tags=["Clientes"])
def actualizar_cliente(client_id: int, cliente: schemas.ClientCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    payload = cliente.model_dump()
    payload = _apply_clasificacion_from_catalog(db, payload)
    for key, value in payload.items():
        setattr(db_client, key, value)

    if db_client.codigo:
        payload["codigo"] = db_client.codigo
        try:
            import cligesco_dbf
            cligesco_dbf.upsert_client(payload, create=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo actualizar CLIGESCO.DBF: {e}")
    
    db.commit()
    db.refresh(db_client)
    return db_client

@app.delete("/api/clients/{client_id}", tags=["Clientes"])
def eliminar_cliente(client_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    db_client.activo = not db_client.activo
    if db_client.codigo:
        try:
            import cligesco_dbf
            cligesco_dbf.set_activo(db_client.codigo, db_client.activo)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo actualizar CACTI en CLIGESCO.DBF: {e}")
    db.commit()
    return {"status": "success", "activo": db_client.activo}

# ==========================================
# RUTAS DE INTEGRACIÓN ERP (XaGesApi)
# ==========================================
@app.get("/api/erp/clientes/{client_id_or_code}/saldo", tags=["Integración ERP"])
def obtener_saldo_erp_real(client_id_or_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Obtiene el saldo real del cliente directamente desde el ERP local en tiempo real y actualiza el caché de PostgreSQL.
    """
    # Intentar buscar primero por ID de cliente, de lo contrario buscar por su código ERP (CCLIFAC) o código de licencias (CCOD)
    db_client = None
    if client_id_or_code.isdigit():
        db_client = db.query(models.Client).filter(models.Client.id == int(client_id_or_code)).first()
        
    if not db_client:
        db_client = db.query(models.Client).filter(
            (models.Client.cclifac == client_id_or_code) | 
            (models.Client.codigo == client_id_or_code)
        ).first()
        
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no registrado en el sistema local.")
        
    if not db_client.cclifac:
        raise HTTPException(status_code=400, detail="El cliente seleccionado no posee un código de cliente de facturación del ERP (CCLIFAC) asociado.")
        
    try:
        cuenta = ERPBridge.get_client_account(db_client.cclifac)
        saldo_real = cuenta["saldo"]
        fecha_pago = cuenta["fecha_ultimo_pago"]

        db_client.saldo = saldo_real
        if fecha_pago is not None:
            db_client.fecha_ultimo_pago = fecha_pago
        db.commit()
        
        return {
            "cliente_id": db_client.id,
            "codigo": db_client.codigo,
            "cclifac": db_client.cclifac,
            "razon_social": db_client.razon_social,
            "saldo_local": db_client.saldo,
            "saldo_real_erp": saldo_real,
            "fecha_ultimo_pago": db_client.fecha_ultimo_pago.isoformat() if db_client.fecha_ultimo_pago else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando el motor ERP de Harbour: {str(e)}")

@app.get("/api/erp/clientes/{client_id_or_code}/extracto", tags=["Integración ERP"])
def obtener_extracto_erp_real(client_id_or_code: str, desde: Optional[str] = None, hasta: Optional[str] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Obtiene el extracto de cuenta corriente detallado del cliente desde el ERP de manera interactiva.
    """
    db_client = None
    if client_id_or_code.isdigit():
        db_client = db.query(models.Client).filter(models.Client.id == int(client_id_or_code)).first()
        
    if not db_client:
        db_client = db.query(models.Client).filter(
            (models.Client.cclifac == client_id_or_code) | 
            (models.Client.codigo == client_id_or_code)
        ).first()
        
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no registrado en el sistema local.")
        
    if not db_client.cclifac:
        raise HTTPException(status_code=400, detail="El cliente seleccionado no posee un código de cliente de facturación del ERP (CCLIFAC) asociado.")
        
    try:
        extracto = ERPBridge.get_client_extracto(db_client.cclifac, desde, hasta)
        return {
            "cliente_id": db_client.id,
            "codigo": db_client.codigo,
            "cclifac": db_client.cclifac,
            "razon_social": db_client.razon_social,
            "extracto": extracto
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando el extracto en el motor ERP de Harbour: {str(e)}")

@app.get("/api/erp/clientes/{client_id_or_code}/lic-facturadas", tags=["Integración ERP"])
def obtener_lic_facturadas_erp(client_id_or_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """Licencias/artículos facturados (LisArtC), igual que GesActi → Lic Facturadas."""
    db_client = None
    if client_id_or_code.isdigit():
        db_client = db.query(models.Client).filter(models.Client.id == int(client_id_or_code)).first()
    if not db_client:
        db_client = db.query(models.Client).filter(
            (models.Client.cclifac == client_id_or_code) |
            (models.Client.codigo == client_id_or_code)
        ).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no registrado en el sistema local.")
    if not db_client.cclifac:
        raise HTTPException(status_code=400, detail="El cliente seleccionado no posee un código de cliente de facturación del ERP (CCLIFAC) asociado.")
    try:
        items = ERPBridge.get_client_lic_facturadas(db_client.cclifac)
        return {
            "cliente_id": db_client.id,
            "codigo": db_client.codigo,
            "cclifac": db_client.cclifac,
            "razon_social": db_client.razon_social,
            "items": items,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando LisArtC en el ERP: {str(e)}")

@app.get("/api/erp/comprobantes/{hash_fac}/pdf", tags=["Integración ERP"])
def obtener_pdf_comprobante(hash_fac: str, current_user: models.User = Depends(get_current_user)):
    """
    Genera y descarga el PDF oficial del ERP para un comprobante en tiempo real.
    """
    try:
        from fastapi import Response
        filename, pdf_bytes = ERPBridge.get_voucher_pdf(hash_fac)
        
        headers = {
            "Content-Disposition": f'inline; filename="{filename}"'
        }
        return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando el comprobante PDF: {str(e)}")

# ==========================================
# RUTAS DE LICENCIAS
# ==========================================
@app.get("/api/licenses", tags=["Licencias"])
def get_licenses(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.License).all()

@app.post("/api/licenses", tags=["Licencias"])
def create_license(lic_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    client_id = lic_data.get("client_id")
    max_devices = lic_data.get("max_devices", 5)
    duration_days = lic_data.get("duration_days", 365)
    
    new_key = f"APOLLO-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}"
    expiry = datetime.now() + timedelta(days=duration_days)
    
    new_lic = models.License(
        license_key=new_key,
        client_id=client_id,
        max_devices=max_devices,
        expiry_date=expiry,
        is_active=True
    )
    db.add(new_lic)
    db.commit()
    db.refresh(new_lic)
    return new_lic

# ==========================================
# RUTAS DE LICENCIAS ERP (CONEXIÓN MYSQL)
# ==========================================
import erp_licensing

@app.get("/api/erp-licenses/summary", tags=["Licencias ERP"])
def get_erp_licenses_summary(current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_license_panel_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/client/{client_code}", tags=["Licencias ERP"])
def get_erp_licenses_by_client(client_code: str, current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_licenses_by_client(client_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/terminals/{serial}", tags=["Licencias ERP"])
def get_erp_license_terminals(serial: str, current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_terminals_by_license(serial)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/reports/{serial}", tags=["Licencias ERP"])
def get_erp_license_reports(
    serial: str,
    date_from: str = None,
    date_to: str = None,
    current_user: models.User = Depends(get_current_user),
):
    """Reportes de uso (misi_report), mismo flujo que GesActi → Licencias → Reportes."""
    try:
        return erp_licensing.fetch_reports_by_serial(serial, date_from, date_to)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/reports/{report_id}/nodes", tags=["Licencias ERP"])
def get_erp_report_nodes(report_id: int, current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_report_nodes(report_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/reports/{report_id}/system", tags=["Licencias ERP"])
def get_erp_report_system(report_id: int, current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_report_system(report_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/management", tags=["Licencias ERP"])
def save_erp_license_management(data: dict, current_user: models.User = Depends(get_current_user)):
    serial = data.get("serial")
    m_down = data.get("m_down", False)
    m_newdate = data.get("m_newdate")
    m_tipmsg = data.get("m_tipmsg", 1)
    m_showmode = data.get("m_showmode", "01")
    m_text = data.get("m_text", "")
    
    if not serial:
        raise HTTPException(status_code=400, detail="El campo 'serial' es obligatorio.")
        
    try:
        return erp_licensing.save_license_management(serial, m_down, m_newdate, m_tipmsg, m_showmode, m_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/management/bulk", tags=["Licencias ERP"])
def save_erp_license_management_bulk(data: dict, current_user: models.User = Depends(get_current_user)):
    """Monitoreo masivo GesActi: cartel/corte sobre licencias activas de clientes marcados."""
    client_codes = data.get("client_codes") or []
    if not client_codes:
        raise HTTPException(status_code=400, detail="Indique client_codes (codigos de 4 digitos).")
    try:
        return erp_licensing.save_license_management_for_clients(
            client_codes,
            data.get("m_down", False),
            data.get("m_newdate"),
            data.get("m_tipmsg", 1),
            data.get("m_showmode", "01"),
            data.get("m_text", ""),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/erp-licenses/toggle/{serial}", tags=["Licencias ERP"])
def toggle_erp_license_status(serial: str, data: dict, current_user: models.User = Depends(get_current_user)):
    is_desact = data.get("l_desact", False)
    try:
        return erp_licensing.toggle_license_status(serial, is_desact)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/erp-licenses/extension/{serial}", tags=["Licencias ERP"])
def update_erp_license_extension(serial: str, data: dict, current_user: models.User = Depends(get_current_user)):
    days = data.get("days", 30)
    expiry_date = data.get("expiry_date")
    try:
        return erp_licensing.update_license_auto_ext(serial, days, expiry_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/deactivate-node", tags=["Licencias ERP"])
def deactivate_erp_license_node(data: dict, current_user: models.User = Depends(get_current_user)):
    serial = data.get("serial")
    t_id_enc = data.get("t_id_enc")
    t_user_enc = data.get("t_user_enc")
    t_path_enc = data.get("t_path_enc")
    
    if not all([serial, t_id_enc, t_user_enc, t_path_enc]):
        raise HTTPException(status_code=400, detail="Faltan parámetros obligatorios.")
        
    try:
        return erp_licensing.deactivate_terminal_node(serial, t_id_enc, t_user_enc, t_path_enc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/modules", tags=["Licencias ERP"])
def get_erp_license_modules(current_user: models.User = Depends(get_current_user)):
    return erp_licensing.load_gesacti_modules()

@app.post("/api/erp-licenses/generate-serial", tags=["Licencias ERP"])
def generate_erp_serial(data: dict, current_user: models.User = Depends(get_current_user)):
    """Genera el número de serie con el mismo algoritmo que GesActi (CalculaNuevoSerial)."""
    try:
        serial = erp_licensing.generate_gesacti_serial(
            data.get("client_code") or data.get("l_cli") or "",
            data.get("expiry_date") or data.get("l_date") or "",
            data.get("module_nums") or data.get("modules") or [],
            bool(data.get("all_modules") or data.get("todos")),
        )
        return {"l_number": serial, "status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/new-serial", tags=["Licencias ERP"])
def create_new_erp_serial(data: dict, current_user: models.User = Depends(get_current_user)):
    l_number = data.get("l_number")
    l_date = data.get("l_date")
    l_peri2016 = data.get("l_peri2016", 30)
    l_raso = data.get("l_raso", "")
    l_nomfa = data.get("l_nomfa", "")
    l_cuit = data.get("l_cuit", "")
    l_tele = data.get("l_tele", "")
    l_locali = data.get("l_locali", "")
    
    if not all([l_number, l_date]):
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios ('l_number' y 'l_date').")
        
    try:
        return erp_licensing.register_new_serial(
            l_number, l_date, l_peri2016, l_raso, l_nomfa, l_cuit, l_tele, l_locali
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/templates", tags=["Licencias ERP"])
def get_erp_license_templates(current_user: models.User = Depends(get_current_user)):
    try:
        return erp_licensing.fetch_messages_templates()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/templates", tags=["Licencias ERP"])
def save_erp_license_template(data: dict, current_user: models.User = Depends(get_current_user)):
    try:
        m_num = int(data.get("m_num") or data.get("id") or 0)
        if m_num < 1:
            raise HTTPException(status_code=400, detail="m_num debe ser >= 1")
        return erp_licensing.save_message_template(
            m_num,
            data.get("m_des") or data.get("label") or "",
            data.get("m_text") or data.get("text") or "",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/activation-requests", tags=["Licencias ERP"])
def get_erp_activation_requests(pending_only: bool = True, current_user: models.User = Depends(get_current_user)):
    """Activaciones pendientes OnLine (misi_request), como ActiPenOL de GesActi."""
    try:
        return erp_licensing.fetch_activation_requests(pending_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/activation-requests/{key_id}/resolve", tags=["Licencias ERP"])
def resolve_erp_activation_request(key_id: int, data: dict, current_user: models.User = Depends(get_current_user)):
    """Activar / Denegar / Pendiente / c/mensaje / c/fecha (ActivarNormal)."""
    try:
        return erp_licensing.resolve_activation_request(
            key_id,
            data.get("state") or data.get("r_state"),
            data.get("message") or data.get("r_message"),
            data.get("new_date") or data.get("expiry_date"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/erp-licenses/extensions", tags=["Licencias ERP"])
def get_erp_pending_extensions(pending_only: bool = True, current_user: models.User = Depends(get_current_user)):
    """Extensiones OnLine pendientes (misi_extension), como ExtenOl de GesActi."""
    try:
        return erp_licensing.fetch_pending_extensions(pending_only)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/erp-licenses/extensions/{key_id}/approve", tags=["Licencias ERP"])
def approve_erp_extension(key_id: int, data: dict = Body(default={}), current_user: models.User = Depends(get_current_user)):
    """Generar extensión: actualiza licencia y e_newdate."""
    data = data or {}
    try:
        return erp_licensing.approve_extension(key_id, data.get("new_date") or data.get("e_newdate"))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==========================================
# RUTAS DE DISPOSITIVOS ANDROID (misi_licand)
# ==========================================

@app.get("/api/android-devices/summary", tags=["Dispositivos Android"])
def get_android_devices_summary(current_user: models.User = Depends(get_current_user)):
    """
    Devuelve el resumen de dispositivos Android activos agrupado por cliente y por tipo de app.
    Cada elemento tiene el código de cliente (4 dígitos) y un dict de apps con cantidades.
    """
    try:
        return erp_licensing.fetch_android_devices_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando dispositivos Android: {str(e)}")

@app.get("/api/android-devices/client/{client_code}", tags=["Dispositivos Android"])
def get_android_devices_by_client(client_code: str, current_user: models.User = Depends(get_current_user)):
    """
    Devuelve todos los dispositivos Android registrados para el cliente con el código dado (primeros 4 chars del serial).
    """
    try:
        return erp_licensing.fetch_android_devices_by_client(client_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando dispositivos del cliente {client_code}: {str(e)}")

@app.post("/api/android-devices/toggle", tags=["Dispositivos Android"])
def toggle_android_device(data: dict, current_user: models.User = Depends(get_current_user)):
    """Habilita o inhabilita un dispositivo (Android o PC/navegador TCK) en misi_licand."""
    key_id = data.get("id") or data.get("KeyId")
    if not key_id:
        raise HTTPException(status_code=400, detail="Falta id del dispositivo.")
    habilitado = data.get("habilitado")
    if habilitado is None:
        habilitado = data.get("status", 1)
    try:
        return erp_licensing.toggle_android_device(int(key_id), bool(int(habilitado)))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo cambiar el estado: {e}")

# ==========================================
# RUTAS DE AREAS (NUEVO)
# ==========================================

@app.get("/api/areas", response_model=List[schemas.AreaOut], tags=["Configuración"])
def obtener_areas(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Area).all()

# ==========================================
# RUTAS DE USUARIOS / ABM / PERFIL (NUEVO)
# ==========================================
@app.get("/api/users", response_model=List[schemas.UserOut], tags=["Usuarios"])
def obtener_usuarios(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Retorna todos los usuarios ordenados por si están online primero """
    return db.query(models.User).order_by(models.User.is_online.desc(), models.User.nombre.asc()).all()

@app.get("/api/users/me", response_model=schemas.UserOut, tags=["Usuarios"])
def obtener_perfil_propio(current_user: models.User = Depends(get_current_user)):
    """ Retorna el perfil del usuario logueado """
    return current_user

@app.post("/api/users", response_model=schemas.UserOut, tags=["Usuarios"])
def crear_usuario(user_data: schemas.UserCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ ABM: Crea un nuevo usuario en el sistema. Solo administradores. """
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Permiso denegado. Solo administradores.")
        
    email_exists = db.query(models.User).filter(models.User.email == user_data.email).first()
    if email_exists:
        raise HTTPException(status_code=400, detail="El email ya está registrado.")
        
    hashed = auth.get_password_hash(user_data.password)
    db_user = models.User(
        nombre=user_data.nombre,
        email=user_data.email,
        hashed_password=hashed,
        full_name=user_data.full_name,
        rol=user_data.rol,
        celular=user_data.celular,
        departamento=user_data.departamento,
        profile_picture=user_data.profile_picture,
        activo=True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.put("/api/users/{user_id}", response_model=schemas.UserOut, tags=["Usuarios"])
def actualizar_usuario(user_id: int, user_data: schemas.UserUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ ABM: Actualiza un usuario. Los administradores pueden actualizar a cualquiera. 
        Los usuarios comunes solo pueden actualizar su propio perfil. """
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    if current_user.rol != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="No tienes permisos para modificar este perfil.")
        
    update_data = user_data.model_dump(exclude_unset=True)
    
    if "password" in update_data and update_data["password"]:
        db_user.hashed_password = auth.get_password_hash(update_data["password"])
        del update_data["password"]
        
    # El usuario común no puede cambiarse el rol ni el estado activo
    if current_user.rol != "admin":
        if "rol" in update_data:
            del update_data["rol"]
        if "activo" in update_data:
            del update_data["activo"]
            
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    db.commit()
    db.refresh(db_user)
    return db_user

@app.delete("/api/users/{user_id}", tags=["Usuarios"])
def toggle_activo_usuario(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ ABM: Activa o desactiva un usuario. Solo administradores. """
    if current_user.rol != "admin":
        raise HTTPException(status_code=403, detail="Permiso denegado. Solo administradores.")
        
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="No puedes desactivarte a ti mismo.")
        
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
        
    db_user.activo = not db_user.activo
    db.commit()
    return {"status": "success", "activo": db_user.activo}

@app.post("/api/users/status", response_model=schemas.UserOut, tags=["Usuarios"])
def actualizar_estado_usuario(status_data: schemas.UserStatusUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Actualiza el estado en línea, tarea actual y página actual del usuario logueado en tiempo real """
    current_user.is_online = True
    current_user.last_activity = datetime.utcnow()
    
    if status_data.is_online is not None:
        current_user.is_online = status_data.is_online
    if status_data.current_task is not None:
        current_user.current_task = status_data.current_task
    if status_data.current_page is not None:
        current_user.current_page = status_data.current_page
        
    db.commit()
    db.refresh(current_user)
    return current_user

@app.post("/api/users/logout", tags=["Usuarios"])
def logout_usuario(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Marca al usuario como desconectado (offline) """
    current_user.is_online = False
    current_user.current_task = ""
    current_user.current_page = ""
    db.commit()
    return {"status": "success", "message": "Sesión cerrada correctamente."}

# ==========================================
# RUTAS DE TICKETS (TAREAS)
# ==========================================
@app.post("/api/tickets/", response_model=schemas.TicketOut, tags=["Tickets"])
def crear_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    cliente = db.query(models.Client).filter(models.Client.id == ticket.client_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="El cliente especificado no existe.")
        
    area_id = ticket.initial_area_id
    if not area_id:
        # Default a 'Atención al Cliente'
        area = db.query(models.Area).filter(models.Area.nombre == "Atención al Cliente").first()
        area_id = area.id if area else None

    db_ticket = models.Ticket(
        client_id=ticket.client_id,
        asunto=ticket.asunto,
        descripcion=ticket.descripcion,
        prioridad=ticket.prioridad,
        current_area_id=area_id
    )
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    return db_ticket

@app.get("/api/tickets/", response_model=List[schemas.TicketOut], tags=["Tickets"])
def obtener_tickets(skip: int = 0, limit: int = 100, area_id: Optional[int] = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.Ticket).options(
        joinedload(models.Ticket.cliente),
        joinedload(models.Ticket.area_actual),
        selectinload(models.Ticket.intervenciones).joinedload(models.Intervention.usuario),
        selectinload(models.Ticket.intervenciones).joinedload(models.Intervention.area_origen),
        selectinload(models.Ticket.intervenciones).joinedload(models.Intervention.area_destino)
    )
    if area_id:
        query = query.filter(models.Ticket.current_area_id == area_id)
    
    return query.offset(skip).limit(limit).all()

# ==========================================
# RUTAS DE INTERVENCIONES (HISTORIAL)
# ==========================================
@app.post("/api/tickets/{ticket_id}/interventions", response_model=schemas.InterventionOut, tags=["Tickets"])
async def crear_intervencion(
    ticket_id: int, 
    intervencion: schemas.InterventionCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(get_current_user)
):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
    
    from_area_id = ticket.current_area_id
    to_area_id = intervencion.to_area_id
    
    # Crear la intervención
    db_intervention = models.Intervention(
        ticket_id=ticket_id,
        user_id=current_user.id,
        from_area_id=from_area_id,
        to_area_id=to_area_id,
        mensaje=intervencion.mensaje,
        tipo=intervencion.tipo,
        adjunto_url=intervencion.adjunto_url,
        adjunto_tipo=intervencion.adjunto_tipo
    )
    
    # Si es una transferencia, actualizamos el área del ticket
    if intervencion.tipo == "transferencia" and to_area_id:
        ticket.current_area_id = to_area_id
    
    db.add(db_intervention)
    db.commit()
    db.refresh(db_intervention)
    return db_intervention

@app.post("/api/upload", tags=["Utilidades"])
async def upload_file(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    """ Sube un archivo (audio, imagen, doc) al servidor para adjuntar a una intervención. """
    temp_dir = "temp_files/uploads"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)
    
    file_path = os.path.join(temp_dir, f"{datetime.now().timestamp()}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"url": f"/api/temp/uploads/{os.path.basename(file_path)}", "filename": file.filename}

# Integrar StaticFiles para las subidas temporales (ya montado vía /api/temp, pero damos ruta directa)
# app.mount("/api/temp/uploads", StaticFiles(directory="temp_files/uploads"), name="temp_uploads")

# ==========================================
# IA COPILOTO (Actualizado para Intervenciones)
# ==========================================
@app.get("/api/ai/analyze-ticket/{ticket_id}", tags=["IA Copiloto"])
async def analyze_ticket_ai(ticket_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    import os
    import httpx
    import json
    
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket no encontrado")
        
    # Obtener el cliente asociado
    client = db.query(models.Client).filter(models.Client.id == ticket.client_id).first()
    client_name = client.razon_social if client else "Cliente Desconocido"
    client_modules = client.modulos if client else "Base, Facturación"
    client_version = client.version_apollo if client else "Desconocida"
    
    # Historial de intervenciones
    historial = []
    for inv in ticket.intervenciones:
        rol_usuario = inv.usuario.rol if inv.usuario else "Sistema"
        nombre_usuario = inv.usuario.full_name if inv.usuario else "Sistema"
        destino_msg = f" -> Transferencia a {inv.area_destino.nombre}" if inv.area_destino else ""
        mensaje_texto = inv.mensaje if inv.mensaje else "[Mensaje Vacío u Adjunto]"
        historial.append(
            f"[{inv.fecha_creacion.strftime('%Y-%m-%d %H:%M')}] {nombre_usuario} ({rol_usuario}){destino_msg}: {mensaje_texto}"
        )
    
    historial_texto = "\n".join(historial) if historial else "No hay comentarios previos."
    
    prompt = f"""
Actúa como "Apollo AI Copilot", el arquitecto principal de soluciones de Apollo ERP (Sistemas de Gestión Comercial GesCom basados en bases de datos FoxPro/DBF, impresoras fiscales, spoolers de impresión de Windows, y terminales de red local).

Tu objetivo es analizar un ticket de soporte de un cliente de Apollo ERP para ayudar al personal de Atención al Cliente y mejorar la comunicación con el área de Desarrollo.

=== INFORMACIÓN DEL CLIENTE ===
Empresa: {client_name}
Versión de Apollo ERP: {client_version}
Módulos Habilitados: {client_modules}

=== DETALLE DEL TICKET ===
Asunto: {ticket.asunto}
Descripción Original: {ticket.descripcion}
Estado Actual: {ticket.estado}
Prioridad: {ticket.prioridad}

=== HISTORIAL DE INTERVENCIONES ===
{historial_texto}

=== INSTRUCCIONES DE RESPUESTA ===
Genera una respuesta en formato JSON estrictamente válido que contenga la clave "analysis". El valor de "analysis" debe ser un texto formateado con Markdown claro, premium y elegante, estructurado exactamente en los siguientes 4 bloques:

1. ðŸ” **Diagnóstico y Causa Raíz Estructurada**: Analiza el problema considerando si es de red local, permisos de Windows, tablas de FoxPro (.dbf/.cdx corruptas, necesidad de reindexar), Spooler de impresión, o un bug del sistema.
2. ðŸ› ï¸ **Plan de Acción de Soporte**: Pasos paso a paso prácticos para que el agente de soporte intente solucionar el problema de inmediato en la PC del cliente de forma remota (por ejemplo, reiniciar spooler, limpiar temporales, revisar registros de Windows, etc.).
3. ðŸ’» **Pase Técnico Consolidado para Desarrollo**: Un informe súper formal y estructurado para el sector de Programación si el ticket debe ser derivado. Incluye: Tablas involucradas estimadas (ej: FACTURAS.DBF, HISTORIA\\ULTACT.DBF, etc.), comportamiento esperado, comportamiento observado, y líneas de código o validaciones lógicas que sospechas que fallan.
4. âœ‰ï¸ **Borrador de Respuesta Empática para el Cliente**: Un borrador cordial, tranquilizador y profesional dirigido al cliente (menciona a "{client_name}" y saluda como el Equipo de Soporte de Apollo).

Asegúrate de que la salida sea un objeto JSON válido con el campo "analysis" conteniendo todo el Markdown para evitar problemas de parseo.
"""

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        # Modo de demostración de súper alta calidad con análisis dinámico adaptado al ticket actual
        # De esta forma, incluso sin API Key, el personal recibe una herramienta súper útil.
        sintomas_especificos = ""
        dbfs_sospechosas = "TABLAS.DBF, INDICES.CDX"
        if "imp" in ticket.asunto.lower() or "impr" in ticket.asunto.lower() or "factur" in ticket.asunto.lower() or "ticket" in ticket.asunto.lower():
            sintomas_especificos = "Falla de comunicación con controlador fiscal o impresora térmica. El spooler de Windows suele acumular trabajos corruptos."
            dbfs_sospechosas = "FACTURAS.DBF, COMPROBANTES.DBF"
        elif "usuario" in ticket.asunto.lower() or "permis" in ticket.asunto.lower() or "log" in ticket.asunto.lower():
            sintomas_especificos = "Conflicto de autenticación o bloqueo de archivos de sesión de usuario en red compartida."
            dbfs_sospechosas = "USERG.DBF, ACCESO.DBF"
        else:
            sintomas_especificos = "Inconsistencia lógica de datos o índice FoxPro (.CDX) desincronizado por desconexión de terminal de red."
            dbfs_sospechosas = "HISTORIA\\ULTACT.DBF, CLIENTES.DBF"

        analysis_mock = f"""### ðŸ¤– Análisis Copiloto IA (Modo Demostración)
> [!NOTE]
> Para activar la Inteligencia Artificial generativa real con Gemini, define `GEMINI_API_KEY` en tu archivo `.env` del backend.

#### ðŸ” 1. Diagnóstico y Posible Causa Raíz
* **Sintomatología:** El ticket titulado **"{ticket.asunto}"** para la empresa **{client_name}** indica un conflicto operativo que afecta a los módulos activos: `{client_modules}`.
* **Causa Estimada:** {sintomas_especificos}
* **Comportamiento Observado:** Error en tiempo de ejecución o pantalla bloqueada debido a bloqueo exclusivo de archivos en red local (SMB v2/v3).

#### ðŸ› ï¸ 2. Plan de Acción de Soporte (Atención al Cliente)
1. **Comandos Remotos:** Utiliza las herramientas remotas integradas en este panel para acelerar el soporte:
   * Haz clic en **"Reiniciar Spooler"** si se trata de un problema de impresión atascada.
   * Haz clic en **"Limpiar Temporales"** para liberar archivos de caché de FoxPro en la máquina cliente (`%TEMP%`).
2. **Chequeo de Archivos Bloqueados:** Accede al servidor del cliente y verifica si el archivo DBF de interés está retenido por alguna sesión inactiva.

#### ðŸ’» 3. Pase Técnico Consolidado para Desarrollo
* **Origen de Derivación:** Sector Atención al Cliente -> Desarrollo.
* **Componentes de Interés:**
  * **Tablas de datos sospechosas:** `{dbfs_sospechosas}` en la ruta de tablas del cliente.
  * **Comportamiento Esperado:** Flujo lógico continuo sin colisiones transaccionales de FoxPro.
  * **Sugerencia de Código:** Verificar si hay sentencias `SET EXCLUSIVE OFF` faltantes o manejo de reintentos `LOCK()` en bloqueos de registros.

#### âœ‰ï¸ 4. Borrador de Respuesta Empática para el Cliente
*"Estimado cliente de **{client_name}**, buenas tardes. Le saluda el equipo de Soporte de Apollo. Hemos registrado su reporte sobre: **'{ticket.asunto}'**. Nuestros analistas ya están validando la situación y nos contactaremos a la brevedad para acceder de forma remota o aplicar la corrección necesaria en sus terminales. Agradecemos enormemente su paciencia."*
"""
        return {"analysis": analysis_mock, "confidence": 1.0}

    # Llamada real a la API de Google Gemini (gemini-2.5-flash)
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": {
                    "type": "OBJECT",
                    "properties": {
                        "analysis": {"type": "STRING"}
                    },
                    "required": ["analysis"]
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=payload, timeout=30.0)
            if response.status_code == 200:
                result = response.json()
                text_content = result["candidates"][0]["content"]["parts"][0]["text"]
                parsed_res = json.loads(text_content)
                return {"analysis": parsed_res.get("analysis", "No se obtuvo análisis del modelo."), "confidence": 0.95}
            else:
                return {
                    "analysis": f"âš ï¸ Error en API de Gemini (Código {response.status_code}): {response.text}",
                    "confidence": 0.0
                }
    except Exception as e:
        return {
            "analysis": f"âŒ Error al contactar con el Copiloto IA de Google Gemini: {str(e)}",
            "confidence": 0.0
        }

# ==========================================
# (Resto de Centinela se mantiene igual...)
# ==========================================

# ==========================================
# CENTINELA (WEBSOCKETS DE AGENTES REMOTOS)
# ==========================================
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Query
from database import engine, Base, get_db, SessionLocal
from typing import Dict, List, Any
from datetime import datetime

class ConnectionManager:
    def __init__(self):
        # active_connections[device_id] = WebSocket
        self.active_connections: Dict[int, WebSocket] = {}
        # active_clients[client_id] = list of device_ids
        self.active_clients: Dict[int, List[int]] = {}
        # client_telemetry[device_id] = last info
        self.client_telemetry: Dict[int, dict] = {}
        # client_frames[device_id] = last base64
        self.client_frames: Dict[int, str] = {}
        # client_alerts[device_id] = active alerts
        self.client_alerts: Dict[int, List[str]] = {}
        # client_files[device_id] = temp results
        self.client_files: Dict[int, Any] = {}
        # session_info[device_id] = {"tech_name": ..., "start_time": ...}
        self.session_info: Dict[int, dict] = {}
        # client_clipboard[device_id] = last copied text from client
        self.client_clipboard: Dict[int, str] = {}
        # client_sessions[device_id] = list of Windows sessions
        self.client_sessions: Dict[int, list] = {}
        # write_locks[device_id] = asyncio.Lock()
        self.write_locks: Dict[int, asyncio.Lock] = {}
        # frame_buffer per device (last 30 frames)
        self.frame_buffer: Dict[int, deque] = {}
        # device_viewers[device_id] = {user_id: (user_name, last_seen_datetime)}
        self.device_viewers: Dict[int, Dict[int, tuple]] = {}
        # last_viewer_notification[device_id] = last notification sent datetime
        self.last_viewer_notification: Dict[int, datetime] = {}
        # Multi-session tracking for Terminal Server scenario
        self.device_sessions: Dict[int, Dict[int, WebSocket]] = {}
        self.selected_sessions: Dict[int, int] = {}
        self.requested_sessions: Dict[int, int] = {}
        self.switch_requested_at: Dict[int, datetime] = {}
        # â”€â”€â”€ VIEWER WEBSOCKETS (estándar) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # viewer_connections[device_id] = {ws_id: WebSocket}
        self.viewer_connections: Dict[int, Dict[str, WebSocket]] = {}
        self.viewer_write_locks: Dict[str, asyncio.Lock] = {}  # lock por ws_id individual
        # â”€â”€â”€ HQ VIEWER WEBSOCKETS (binary H.264) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # hq_viewer_connections[device_id] = {ws_id: WebSocket}
        # Forward raw H.264/fMP4 bytes directamente del agente al browser (MSE).
        # Sistema completamente independiente del path estándar (no toca nada existente).
        self.hq_viewer_connections: Dict[int, Dict[str, WebSocket]] = {}
        self.hq_viewer_write_locks: Dict[str, asyncio.Lock] = {}
        # Visor pidió HQ vía WS estándar (start_hq) — no requiere /viewer/{id}/hq
        self.hq_wanted: set[int] = set()

    async def _complete_session_switch(self, device_id: int, session_id: int, websocket: WebSocket, reason: str):
        """Cierra el switch pendiente y avisa al panel (login suele caer en Consola, no en la sesion RDP pedida)."""
        self.selected_sessions[device_id] = session_id
        self.active_connections[device_id] = websocket
        self.requested_sessions.pop(device_id, None)
        self.switch_requested_at.pop(device_id, None)
        backend_remote_log(
            device_id,
            f"[SESSION-SWITCH] Completado en sesión {session_id} ({reason})",
            "INFO",
        )
        await self.notify_viewers_session_switched(device_id, session_id)
        await self.notify_agent_viewers_watching(device_id)
        if self.wants_hq_stream(device_id):
            await self.send_json_safe(device_id, {"type": "start_hq", "device_id": device_id})

    async def notify_agent_viewers_watching(self, device_id: int):
        """Tras reconexion del agente: reactivar captura si hay tecnicos mirando (evita pantalla negra)."""
        if not self.has_any_viewers(device_id):
            return
        now = datetime.utcnow()
        active_viewers = []
        for _uid, (u_name, last_seen) in self.device_viewers.get(device_id, {}).items():
            if (now - last_seen).total_seconds() <= 30:
                active_viewers.append(u_name)
        if self.viewer_connections.get(device_id) or self.has_hq_viewers(device_id):
            active_viewers.append("Soporte Web (WS)")
        tech_name = active_viewers[0] if active_viewers else "Soporte"
        await self.send_json_safe(device_id, {"type": "technician_joined", "name": tech_name})
        await self.send_json_safe(device_id, {"type": "active_technicians", "technicians": active_viewers})
        await self.send_json_safe(device_id, {"type": "refresh_frame"})
        self.last_viewer_notification[device_id] = now
        logger.info("[WS] Agente %s notificado: viewers activos (%s)", device_id, active_viewers)

    async def push_to_viewers(self, device_id: int, payload: dict):
        """Envía un mensaje JSON a todos los viewers estándar conectados a este device."""
        viewers = list(self.viewer_connections.get(device_id, {}).items())
        for ws_id, ws in viewers:
            try:
                lock = self.viewer_write_locks.get(ws_id)
                if lock:
                    async with lock:
                        await ws.send_json(payload)
                else:
                    await ws.send_json(payload)
            except Exception:
                pass

    async def connect(self, device_id: int, client_id: int, websocket: WebSocket, session_id: int = None):
        # 1. Registrar en el diccionario de sesiones
        if device_id not in self.device_sessions:
            self.device_sessions[device_id] = {}
        
        if session_id is not None:
            sessions_before_connect = set(self.device_sessions.get(device_id, {}).keys())
            # Si esta sesion ya tenia conexion activa, la cerramos limpiamente para evitar duplicidad en la misma sesion
            if session_id in self.device_sessions[device_id]:
                old_ws = self.device_sessions[device_id][session_id]
                try:
                    logger.warning(f"[WS-CONFLICT] Dispositivo {device_id} Sesion {session_id} ya tenia conexion activa. Cerrando la vieja.")
                    await old_ws.close(code=4009)
                except Exception:
                    pass
            self.device_sessions[device_id][session_id] = websocket
            
            # Autopromoción: Si no hay ninguna seleccionada, o si la seleccionada es Session 0 (servicio sin GUI) y conecta una sesión interactiva (>0), o si es la sesión solicitada, la seleccionamos como activa.
            current_selected = self.selected_sessions.get(device_id)
            requested_session = self.requested_sessions.get(device_id)
            
            promoted = (
                device_id not in self.selected_sessions
                or (current_selected == 0 and session_id != 0)
                or session_id == requested_session
            )
            if promoted:
                self.selected_sessions[device_id] = session_id
                logger.info(
                    "[WS-PROMOTION] Promoviendo sesion %s como activa (antes=%s, pedida=%s)",
                    session_id, current_selected, requested_session,
                )

            if requested_session is not None and session_id is not None:
                sessions_map = self.device_sessions.get(device_id, {})
                if session_id == requested_session:
                    await self._complete_session_switch(
                        device_id, session_id, websocket, "coincide con la solicitada"
                    )
                elif (
                    requested_session not in sessions_before_connect
                    and session_id not in sessions_before_connect
                ):
                    # Tras login: agente en Consola (1) pero el panel esperaba RDP (24) sin WS
                    await self._complete_session_switch(
                        device_id,
                        session_id,
                        websocket,
                        f"sesión {session_id} conectó; {requested_session} sin agente",
                    )
        else:
            # Fallback si no tiene session_id (agentes viejos)
            # Evitar colisión de múltiples agentes en el mismo ID de dispositivo
            if device_id in self.active_connections:
                old_ws = self.active_connections[device_id]
                try:
                    logger.warning(f"[WS-CONFLICT] Dispositivo {device_id} ya tenia conexion activa (sin session_id). Cerrando la vieja.")
                    await old_ws.close(code=4009)
                except Exception:
                    pass
        
        # 2. La conexion "activa" principal (la que recibe comandos y de la que aceptamos frames)
        # es la de la sesion seleccionada (o la conexion de fallback)
        current_selected = self.selected_sessions.get(device_id)
        if current_selected is not None and current_selected in self.device_sessions[device_id]:
            self.active_connections[device_id] = self.device_sessions[device_id][current_selected]
        else:
            self.active_connections[device_id] = websocket
            
        if client_id not in self.active_clients:
            self.active_clients[client_id] = []
        if device_id not in self.active_clients[client_id]:
            self.active_clients[client_id].append(device_id)

        if self.active_connections.get(device_id) == websocket and self.has_any_viewers(device_id):
            await self.notify_agent_viewers_watching(device_id)

    def disconnect(self, device_id: int, client_id: int, websocket: WebSocket = None):
        # Encontrar y remover de device_sessions
        session_to_remove = None
        if device_id in self.device_sessions:
            for s_id, ws in list(self.device_sessions[device_id].items()):
                if ws == websocket:
                    session_to_remove = s_id
                    self.device_sessions[device_id].pop(s_id, None)
                    logger.info(f"[WS-DISCONNECT] Removiendo conexion de sesion {s_id} para device {device_id}")
                    break
                    
            if not self.device_sessions[device_id]:
                self.device_sessions.pop(device_id, None)
                self.selected_sessions.pop(device_id, None)
            elif session_to_remove == self.selected_sessions.get(device_id):
                pending = self.requested_sessions.get(device_id)
                if pending is not None:
                    logger.info(
                        "[WS-SWITCH] Sesion activa %s desconectada durante cambio pendiente a %s (device %s)",
                        session_to_remove, pending, device_id,
                    )
                    self.selected_sessions.pop(device_id, None)
                    if device_id in self.active_connections:
                        del self.active_connections[device_id]
                else:
                    any_session = next(iter(self.device_sessions[device_id].keys()))
                    self.selected_sessions[device_id] = any_session
                    logger.info(f"[WS-SWITCH] Sesion seleccionada cambio a {any_session} tras desconexion de la activa")
        
        # Si ya no quedan conexiones en absoluto para este dispositivo, limpiar active_connections
        if device_id not in self.device_sessions or not self.device_sessions[device_id]:
            if device_id in self.active_connections:
                del self.active_connections[device_id]
        else:
            # Si quedan sesiones, actualizar active_connections con la seleccionada
            sel_sess = self.selected_sessions.get(device_id)
            if sel_sess in self.device_sessions[device_id]:
                self.active_connections[device_id] = self.device_sessions[device_id][sel_sess]

        if client_id in self.active_clients:
            # Solo remover del panel si no queda NINGUNA sesion activa para este dispositivo
            if device_id not in self.device_sessions or not self.device_sessions[device_id]:
                if device_id in self.active_clients[client_id]:
                    self.active_clients[client_id].remove(device_id)
                    
        # Limpiar otros buffers solo si se perdieron todas las conexiones de este device
        if device_id not in self.device_sessions or not self.device_sessions[device_id]:
            if device_id in self.client_frames:
                del self.client_frames[device_id]
            if device_id in self.session_info:
                del self.session_info[device_id]
            if device_id in self.client_telemetry:
                del self.client_telemetry[device_id]
            if device_id in self.client_alerts:
                del self.client_alerts[device_id]
            if device_id in self.client_clipboard:
                del self.client_clipboard[device_id]
            if device_id in self.write_locks:
                del self.write_locks[device_id]
            if device_id in self.device_viewers:
                del self.device_viewers[device_id]
            if device_id in self.last_viewer_notification:
                del self.last_viewer_notification[device_id]


    async def send_json_safe(self, device_id: int, data: dict) -> bool:
        """Envía JSON al agente usando la misma resolución de sesión que send_json_to_device.

        Antes solo miraba active_connections; si quedaba apuntando a un WS muerto
        (p. ej. tras cambio de sesión Windows), technician_joined/refresh_frame nunca
        llegaban y el visor quedaba en negro con el agente 'online' en DB.
        """
        return await self.send_json_to_device(device_id, data)

    async def send_command(self, client_id: int, command: str):
        """ Envía un comando arbitrario al agente Centinela vía WebSocket de forma segura. """
        return await self.send_json_safe(client_id, {
            "type": "run_command",
            "command": command
        })

    async def send_json_to_device(self, device_id: int, data: dict) -> bool:
        """Envía JSON al agente. Input (teclado/mouse) va a la sesión seleccionada
        con el mismo write_lock que pings/telemetry (evita corromper el WS)."""
        if device_id not in self.write_locks:
            self.write_locks[device_id] = asyncio.Lock()

        cmd_type = (data.get("type") or "") if isinstance(data, dict) else ""
        input_types = {
            "key_press", "key_down", "key_up", "write_text",
            "mouse_click", "mouse_down", "mouse_up", "mouse_move", "mouse_scroll",
            "clipboard_sync", "clipboard_files", "clipboard_files_sync",
        }

        sessions = self.device_sessions.get(device_id, {})
        targets = []
        if cmd_type in input_types:
            sel = self.selected_sessions.get(device_id)
            if sel is not None and sel in sessions:
                targets = [sessions[sel]]
            elif device_id in self.active_connections:
                targets = [self.active_connections[device_id]]
            else:
                targets = list(sessions.values())
        else:
            targets = list(sessions.values())
            if not targets and device_id in self.active_connections:
                targets = [self.active_connections[device_id]]

        if not targets:
            return False

        async with self.write_locks[device_id]:
            sent = False
            for ws in targets:
                try:
                    await ws.send_json(data)
                    sent = True
                except Exception:
                    pass
            return sent

    async def handle_session_switch(self, device_id: int, cmd: dict):
        """Marca sesión destino, limpia frames viejos y notifica viewers (antes de mandar cmd al agente)."""
        target_session_id = int(cmd.get("session_id", -1))
        if target_session_id == -1:
            return
        backend_remote_log(
            device_id,
            f"[SESSION-SWITCH] Solicitud cambio a sesión Windows {target_session_id} "
            f"(sesiones WS conectadas: {list(self.device_sessions.get(device_id, {}).keys())})",
            "INFO",
        )
        self.requested_sessions[device_id] = target_session_id
        self.switch_requested_at[device_id] = datetime.utcnow()
        self.client_frames.pop(device_id, None)
        self.frame_buffer.pop(device_id, None)

        if self.wants_hq_stream(device_id):
            await self.send_json_safe(device_id, {"type": "stop_hq"})

        sessions = self.device_sessions.get(device_id, {})
        if target_session_id in sessions:
            self.selected_sessions[device_id] = target_session_id
            self.active_connections[device_id] = sessions[target_session_id]
            logger.info("[WS-SWITCH] Cambio instantaneo device %s -> sesion %s", device_id, target_session_id)
            await self.send_json_safe(device_id, {"type": "refresh_frame"})
            backend_remote_log(
                device_id,
                f"[SESSION-SWITCH] Cambio instantáneo a sesión {target_session_id} (ya conectada por WS)",
                "INFO",
            )
            await self.notify_viewers_session_switched(device_id, target_session_id)
            if self.wants_hq_stream(device_id):
                await self.send_json_safe(device_id, {"type": "start_hq", "device_id": device_id})
        else:
            logger.info(
                "[WS-SWITCH] Sesion %s no conectada; reinicio de companion (device %s)",
                target_session_id, device_id,
            )
            backend_remote_log(
                device_id,
                f"[SESSION-SWITCH] Sesión {target_session_id} sin WS; se pide reinicio del companion al agente",
                "WARNING",
            )
            for v_ws in list(self.viewer_connections.get(device_id, {}).values()):
                try:
                    await v_ws.send_json({
                        "type": "session_switching",
                        "target_session_id": target_session_id,
                    })
                except Exception:
                    pass
            asyncio.create_task(self._session_switch_watchdog(device_id, target_session_id))

    async def notify_viewers_session_switched(self, device_id: int, session_id: int):
        self.requested_sessions.pop(device_id, None)
        self.switch_requested_at.pop(device_id, None)
        backend_remote_log(
            device_id,
            f"[SESSION-SWITCH] Completado — viewers notificados (sesión activa {session_id})",
            "INFO",
        )
        for v_ws in list(self.viewer_connections.get(device_id, {}).values()):
            try:
                await v_ws.send_json({"type": "session_switched", "session_id": session_id})
            except Exception as e:
                logger.error("[WS-SWITCH] Error notifying viewer: %s", e)

    async def notify_viewers_session_switch_failed(self, device_id: int, error: str):
        self.requested_sessions.pop(device_id, None)
        self.switch_requested_at.pop(device_id, None)
        for v_ws in list(self.viewer_connections.get(device_id, {}).values()):
            try:
                await v_ws.send_json({"type": "session_switch_failed", "error": error})
            except Exception:
                pass

    async def _session_switch_watchdog(self, device_id: int, target_session_id: int, timeout_sec: float = 20.0):
        await asyncio.sleep(timeout_sec)
        if self.requested_sessions.get(device_id) != target_session_id:
            return
        logger.warning(
            "[WS-SWITCH] Timeout esperando sesion %s en device %s",
            target_session_id, device_id,
        )
        backend_remote_log(
            device_id,
            f"[SESSION-SWITCH] TIMEOUT esperando sesión {target_session_id}",
            "ERROR",
        )
        await self.notify_viewers_session_switch_failed(
            device_id,
            "Tiempo de espera agotado al cambiar de sesión. Verifique que el agente esté actualizado.",
        )

    async def push_frame_to_viewers(self, device_id: int, frame_data: str, delta: dict = None):
        """
        Envía el frame recién llegado del agente a TODOS los técnicos que tienen
        abierto un WebSocket de vista en tiempo real para este dispositivo.
        Opera de forma no-bloqueante: si un viewer falla, se elimina silenciosamente.
        DIRTY_RECT: si delta está presente, se reenvía al viewer para composición.
        """
        try:
            from session_recorder import recorder_manager
            await recorder_manager.ingest_frame(device_id, frame_data, delta)
        except Exception:
            pass

        if device_id not in self.viewer_connections:
            return

        # Log before sending frame to viewers
        logger.info("[FRAME SEND] device_id=%d viewers=%d delta=%s", device_id, len(self.viewer_connections.get(device_id, {})), bool(delta))

        # DIRTY_RECT_START: incluir delta en payload si el agente lo envió
        payload = {"type": "frame", "frame": frame_data}
        if delta:
            payload["delta"] = delta
        # DIRTY_RECT_END
        dead_viewers = []

        # Ensure circular buffer exists for this device
        if device_id not in self.frame_buffer:
            self.frame_buffer[device_id] = deque(maxlen=30)
        # Store the current frame in the buffer
        self.frame_buffer[device_id].append(frame_data)
        logger.debug("[BUFFER] device_id=%d buffer_len=%d", device_id, len(self.frame_buffer[device_id]))

        for ws_id, ws in list(self.viewer_connections[device_id].items()):
            lock = self.viewer_write_locks.get(ws_id)
            if lock is None:
                lock = asyncio.Lock()
                self.viewer_write_locks[ws_id] = lock
            try:
                async with lock:
                    await ws.send_json(payload)
            except Exception:
                dead_viewers.append(ws_id)

        for ws_id in dead_viewers:
            logger.info("[VIEWER CLEANUP] Removing dead viewer %s from device %d", ws_id, device_id)
            if device_id in self.viewer_connections:
                self.viewer_connections[device_id].pop(ws_id, None)
                if not self.viewer_connections[device_id]:
                    self.viewer_connections.pop(device_id, None)
            self.viewer_write_locks.pop(ws_id, None)
            logger.debug("[VIEWER] Viewer %s desconectado de device %d", ws_id, device_id)

    def add_viewer(self, device_id: int, ws_id: str, ws: WebSocket):
        if device_id not in self.viewer_connections:
            self.viewer_connections[device_id] = {}
        self.viewer_connections[device_id][ws_id] = ws
        logger.info("[VIEWER] Viewer %s conectado a device %d (total: %d)",
                    ws_id, device_id, len(self.viewer_connections[device_id]))

    def remove_viewer(self, device_id: int, ws_id: str):
        if device_id in self.viewer_connections:
            self.viewer_connections[device_id].pop(ws_id, None)
            if not self.viewer_connections[device_id]:
                del self.viewer_connections[device_id]

    # ——— HQ VIEWER MANAGEMENT ——————————————————————————————————————————————————————
    def add_hq_viewer(self, device_id: int, ws_id: str, ws: WebSocket):
        if device_id not in self.hq_viewer_connections:
            self.hq_viewer_connections[device_id] = {}
        self.hq_viewer_connections[device_id][ws_id] = ws

    def remove_hq_viewer(self, device_id: int, ws_id: str):
        if device_id in self.hq_viewer_connections:
            self.hq_viewer_connections[device_id].pop(ws_id, None)
            if not self.hq_viewer_connections[device_id]:
                del self.hq_viewer_connections[device_id]

    def has_hq_viewers(self, device_id: int) -> bool:
        return bool(self.hq_viewer_connections.get(device_id))

    def wants_hq_stream(self, device_id: int) -> bool:
        return device_id in self.hq_wanted or self.has_hq_viewers(device_id)

    def has_any_viewers(self, device_id: int) -> bool:
        try:
            from session_recorder import recorder_manager
            if recorder_manager.is_recording_device(device_id):
                return True
        except Exception:
            pass
        return bool(self.viewer_connections.get(device_id)) or self.has_hq_viewers(device_id)

    async def _send_hq_bytes_to_viewer(self, ws_id: str, ws: WebSocket, chunk: bytes, locks: Dict[str, asyncio.Lock]):
        lock = locks.get(ws_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[ws_id] = lock
        async with lock:
            await ws.send_bytes(chunk)

    async def push_hq_chunk_to_viewers(self, device_id: int, chunk: bytes):
        """Forward binary H.264 del agente HQ a viewers (WS estándar y/o /hq legacy)."""
        if not hasattr(self, "_chunk_counts"):
            self._chunk_counts = {}
        self._chunk_counts[device_id] = self._chunk_counts.get(device_id, 0) + 1

        std_viewers = self.viewer_connections.get(device_id, {})
        hq_viewers = self.hq_viewer_connections.get(device_id, {})
        if not std_viewers and not hq_viewers:
            if self._chunk_counts[device_id] % 100 == 1:
                backend_remote_log(
                    device_id,
                    f"[BACKEND-TRANSMISIÓN] H.264 chunk #{self._chunk_counts[device_id]} ({len(chunk)} bytes) "
                    f"sin visor conectado — enviando stop_hq al agente",
                    "WARNING",
                )
                if device_id in self.hq_wanted:
                    self.hq_wanted.discard(device_id)
                asyncio.create_task(self.send_json_safe(device_id, {"type": "stop_hq"}))
            return

        viewers_count = len(std_viewers) + len(hq_viewers)
        if self._chunk_counts[device_id] <= 5 or self._chunk_counts[device_id] % 100 == 0:
            logger.info(
                "[HQ-FORWARD] chunk #%d (%d bytes) device %d → %d viewer(s) (std=%d hq=%d)",
                self._chunk_counts[device_id], len(chunk), device_id, viewers_count,
                len(std_viewers), len(hq_viewers),
            )
        else:
            logger.debug("[HQ-FORWARD] chunk #%d (%d bytes) device %d", self._chunk_counts[device_id], len(chunk), device_id)

        if self._chunk_counts[device_id] % 100 == 1:
            backend_remote_log(
                device_id,
                f"[BACKEND-TRANSMISIÓN] Reenviando H.264 #{self._chunk_counts[device_id]} ({len(chunk)} bytes) "
                f"a {viewers_count} visor(es) (std={len(std_viewers)}, hq={len(hq_viewers)})",
                "INFO",
            )

        dead_std: list[str] = []
        for ws_id, ws in list(std_viewers.items()):
            try:
                await self._send_hq_bytes_to_viewer(ws_id, ws, chunk, self.viewer_write_locks)
            except Exception as e:
                logger.error("[HQ-FORWARD-ERROR] std viewer %s: %s", ws_id, e)
                dead_std.append(ws_id)
        for ws_id in dead_std:
            std_viewers.pop(ws_id, None)
            self.viewer_write_locks.pop(ws_id, None)

        dead_hq: list[str] = []
        for ws_id, ws in list(hq_viewers.items()):
            try:
                await self._send_hq_bytes_to_viewer(ws_id, ws, chunk, self.hq_viewer_write_locks)
            except Exception as e:
                logger.error("[HQ-FORWARD-ERROR] hq viewer %s: %s", ws_id, e)
                dead_hq.append(ws_id)
        for ws_id in dead_hq:
            hq_viewers.pop(ws_id, None)
            self.hq_viewer_write_locks.pop(ws_id, None)

        if not std_viewers and not hq_viewers:
            if device_id in self.viewer_connections and not self.viewer_connections[device_id]:
                del self.viewer_connections[device_id]
            if device_id in self.hq_viewer_connections and not self.hq_viewer_connections[device_id]:
                del self.hq_viewer_connections[device_id]


manager = ConnectionManager()

# Agenda: grabaciones + videoconferencias Jitsi
from agenda import setup_agenda, periodic_agenda_worker
setup_agenda(app, manager, get_current_user, send_push_notification)


@app.websocket("/api/ws/viewer/{device_id}")
async def websocket_viewer(websocket: WebSocket, device_id: int, token: str = Query("")):
    await websocket.accept()
    logger.info(f"[WS-STABLE] Conexión establecida para device {device_id}. Validando...")

    # Validación diferida
    try:
        if not token:
            await websocket.send_json({"type": "error", "message": "Token ausente"})
            await websocket.close(code=4001); return
            
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM], options={"leeway": 60})
        email = payload.get("sub")
        if not email:
            await websocket.send_json({"type": "error", "message": "Token inválido"})
            await websocket.close(code=4001); return
    except JWTError as e:
        logger.warning(f"[WS] Rechazo por JWT: {e}")
        await websocket.send_json({"type": "error", "message": f"Sesión expirada: {e}"})
        await websocket.close(code=4001); return

    ws_id = str(uuid.uuid4())
    manager.add_viewer(device_id, ws_id, websocket)

    # Limpiar switch pendiente viejo (evita pantalla negra si falló un cambio de sesión anterior)
    stale_at = manager.switch_requested_at.get(device_id)
    if stale_at and (datetime.utcnow() - stale_at).total_seconds() > 12.0:
        manager.requested_sessions.pop(device_id, None)
        manager.switch_requested_at.pop(device_id, None)
        logger.info("[WS-SWITCH] Switch pendiente expirado al conectar viewer (device %s)", device_id)

    # Notificar al agente que hay un técnico mirando → activa HAS_ACTIVE_VIEWER en el agente
    # Sin esto, el agente nuevo nunca envía frames (espera este mensaje para empezar)
    await manager.send_json_safe(device_id, {
        "type": "technician_joined",
        "name": email
    })
    # También actualizar active_technicians para compatibilidad con agentes viejos
    await manager.send_json_safe(device_id, {
        "type": "active_technicians",
        "technicians": [email]
    })

    # Enviar el último frame disponible inmediatamente al conectar (no esperar al próximo)
    last_frame = manager.client_frames.get(device_id)
    if last_frame:
        try:
            await websocket.send_json({"type": "frame", "frame": last_frame})
        except Exception:
            pass

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive(), timeout=30.0)
                # Puede ser text (JSON) o ping simple
                text = raw.get("text", "") or ""
                if not text:
                    continue
                if text == "ping":
                    await websocket.send_text("pong")
                    continue
                # Intentar parsear como JSON para forwardear al agente
                try:
                    cmd = json.loads(text)
                    cmd_type = cmd.get("type", "")
                    # Comandos que el viewer puede enviar al agente
                    FORWARDED_CMDS = {
                        "get_sessions", "switch_session", "login_session",
                        "set_monitor", "refresh_frame", "mouse_click",
                        "mouse_move", "mouse_scroll", "key_press",
                        "key_down", "key_up", "write_text", "set_clipboard",
                        "set_stream_params", "start_hq", "stop_hq"
                    }
                    if cmd_type in FORWARDED_CMDS:
                        if cmd_type == "start_hq":
                            manager.hq_wanted.add(device_id)
                        elif cmd_type == "stop_hq":
                            manager.hq_wanted.discard(device_id)
                        if cmd_type == "switch_session":
                            await manager.handle_session_switch(device_id, cmd)
                            if not await manager.send_json_to_device(device_id, cmd):
                                backend_remote_log(
                                    device_id,
                                    "[SESSION-SWITCH] No se pudo enviar switch_session al agente (sin WS activo)",
                                    "ERROR",
                                )
                        elif cmd_type == "login_session" and cmd.get("password"):
                            target_session_id = int(cmd.get("session_id") or 1)
                            manager.requested_sessions[device_id] = target_session_id
                            manager.switch_requested_at[device_id] = datetime.utcnow()
                            manager.client_frames.pop(device_id, None)
                            manager.frame_buffer.pop(device_id, None)
                            for v_ws in list(manager.viewer_connections.get(device_id, {}).values()):
                                try:
                                    await v_ws.send_json({
                                        "type": "session_switching",
                                        "target_session_id": target_session_id,
                                    })
                                except Exception:
                                    pass
                            asyncio.create_task(
                                manager._session_switch_watchdog(device_id, target_session_id)
                            )
                            backend_remote_log(
                                device_id,
                                f"[SESSION-SWITCH] login_session con credenciales -> sesión {target_session_id}",
                                "INFO",
                            )
                            if not await manager.send_json_to_device(device_id, cmd):
                                backend_remote_log(
                                    device_id,
                                    "[SESSION-SWITCH] login_session no llegó al agente (sin WS)",
                                    "ERROR",
                                )
                        else:
                            await manager.send_json_to_device(device_id, cmd)
                except Exception:
                    pass
            except asyncio.TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("[VIEWER] Viewer WS cerrado: %s", e)
    finally:
        manager.remove_viewer(device_id, ws_id)
        # Si ya no queda ningún viewer mirando, notificar al agente para que deje de capturar
        remaining = len(manager.viewer_connections.get(device_id, {}))
        if remaining == 0:
            await manager.send_json_safe(device_id, {
                "type": "active_technicians",
                "technicians": []
            })
            if not manager.has_hq_viewers(device_id) and device_id in manager.hq_wanted:
                manager.hq_wanted.discard(device_id)
                await manager.send_json_safe(device_id, {"type": "stop_hq"})


# ——————————————————————————————————————————————————————————————————————————————
# VIEWER HQ WebSocket — Alto Rendimiento (H.264 binario va MSE)
# Completamente independiente del sistema estándar. No toca nada existente.
# El agente envía chunks binarios H.264/fMP4 que se forwardean aquí sin modificación.
# ——————————————————————————————————————————————————————————————————————————————
@app.websocket("/api/ws/viewer/{device_id}/hq")
async def websocket_viewer_hq(websocket: WebSocket, device_id: int, token: str = Query("")):
    """WebSocket de PUSH de video H.264 (Alto Rendimiento).
    El browser usa MediaSource Extensions para decode hardware en tiempo real.
    El agente envía binary fMP4 chunks vía su WS normal; el backend los forwarda aquí.
    """
    logger.info(f"[WS-HANDSHAKE] Intento de conexion VIEWER-HQ para device {device_id}")
    backend_remote_log(device_id, "[WS-CONEXIÓN] Solicitud de WebSocket HQ entrante del visor", "INFO")
    await websocket.accept()

    try:
        # 60s leeway para evitar rechazos por clock-drift
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM], options={"leeway": 60})
        if not payload.get("sub"):
            logger.warning(f"[HQ] Viewer HQ rechazo conexión de device {device_id}: token sin 'sub'")
            backend_remote_log(device_id, "[WS-CONEXIÓN] Rechazada conexión VIEWER-HQ: Token sin claim 'sub'", "ERROR")
            await websocket.close(code=4001); return
    except JWTError as e:
        logger.warning(f"[HQ] Viewer HQ rechazo conexión de device {device_id} por JWTError: {e}")
        backend_remote_log(device_id, f"[WS-CONEXIÓN] Rechazada conexión VIEWER-HQ: Error de token ({e})", "ERROR")
        await websocket.close(code=4001); return

    ws_id = str(uuid.uuid4())
    manager.add_hq_viewer(device_id, ws_id, websocket)
    logger.info("[HQ] Viewer HQ conectado: device=%d ws=%s", device_id, ws_id)
    backend_remote_log(device_id, f"[WS-CONEXIÓN] Visor HQ conectado con éxito (ws_id={ws_id})", "INFO")

    # Notificar al agente que hay un viewer HQ (para que inicie el stream ffmpeg)
    backend_remote_log(device_id, "[COMANDO] Enviando solicitud 'start_hq' al agente a través del WebSocket de control", "INFO")
    await manager.send_json_safe(device_id, {"type": "start_hq", "device_id": device_id})

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if msg == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                try:
                    await websocket.send_text("ping")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("[HQ] Viewer HQ cerrado: %s", e)
    finally:
        manager.remove_hq_viewer(device_id, ws_id)
        logger.info("[HQ] Viewer HQ desconectado: device=%d", device_id)
        backend_remote_log(device_id, f"[WS-CONEXIÓN] Visor HQ desconectado (ws_id={ws_id})", "INFO")
        # Si no quedan viewers HQ, decirle al agente que detenga ffmpeg
        if not manager.has_hq_viewers(device_id):
            backend_remote_log(device_id, "[COMANDO] Enviando 'stop_hq' al agente porque no quedan visores activos", "INFO")
            await manager.send_json_safe(device_id, {"type": "stop_hq"})




# ——————————————————————————————————————————————————————————————————————————————
# AGENTE HQ WebSocket — recibe chunks binarios H.264 del agente (endpoint separado)
# El agente abre UNA segunda conexión WS aquí cuando HQ se activa.
# Sin tocar /api/ws/centinela/{id} que queda 100% intacto.
# ——————————————————————————————————————————————————————————————————————————————
# Se eliminó la ruta separada de HQ para evitar bloqueos de NGINX


# ==========================================
# ROBUST THREAD-SAFE DB OPERATIONS FOR WEBSOCKET
# ==========================================

def _purge_duplicate_pending_devices(db, keep: models.CentinelaDevice) -> int:
    """Elimina filas pendientes (client_id NULL) que representan el mismo PC que `keep`.
    Evita el fantasma 'arriba sin asignar' cuando ya está bajo un cliente."""
    if keep is None or keep.id is None:
        return 0
    from sqlalchemy import or_

    clauses = []
    if keep.assist_id:
        clauses.append(models.CentinelaDevice.assist_id == keep.assist_id)
    if keep.alt_remote_id:
        clauses.append(models.CentinelaDevice.alt_remote_id == keep.alt_remote_id)
    # Mismo hostname solo si el keeper ya está asignado (evita borrar otro pending distinto)
    if keep.device_name and keep.client_id is not None:
        clauses.append(models.CentinelaDevice.device_name == keep.device_name)
    if not clauses:
        return 0

    dupes = (
        db.query(models.CentinelaDevice)
        .filter(
            models.CentinelaDevice.id != keep.id,
            models.CentinelaDevice.client_id == None,
            or_(*clauses),
        )
        .all()
    )
    removed = 0
    for d in dupes:
        try:
            did = d.id
            db.query(models.SupportSession).filter(models.SupportSession.device_id == did).delete(synchronize_session=False)
            db.query(models.RemoteChat).filter(models.RemoteChat.device_id == did).delete(synchronize_session=False)
            db.query(models.RemoteLog).filter(models.RemoteLog.device_id == did).delete(synchronize_session=False)
            db.delete(d)
            removed += 1
            logger.info(
                "[DEDUP] Pending duplicado eliminado id=%s name=%s assist=%s (keep=%s client=%s)",
                did, d.device_name, d.assist_id, keep.id, keep.client_id,
            )
            # Limpiar manager si estaba conectado como huérfano
            try:
                if did in manager.active_connections:
                    manager.disconnect(did, None)
            except Exception:
                pass
        except Exception as e:
            logger.warning("[DEDUP] No se pudo borrar pending id=%s: %s", getattr(d, "id", None), e)
    if removed:
        db.commit()
    return removed


def handle_centinela_handshake(client_id_param: int, device_name: str, license_key: str, hq: str, device_id_param: int, alt_id: str = None) -> dict:
    """
    Realiza las consultas y registros en base de datos para la conexión del agente de forma segura y en su propio hilo.
    """
    db = SessionLocal()
    try:
        if hq == "1":
            target_device_id = device_id_param or client_id_param
            device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == target_device_id).first()
            if not device:
                logger.warning("[HQ-AUTH] Rechazo HQ: device_id=%s no encontrado en DB", target_device_id)
                return {"status": "close", "code": 4001}
            if license_key:
                lic = db.query(models.License).filter(models.License.license_key == license_key).first()
                # Solo rechazar si la licencia NO existe en absoluto.
                # No rechazar por mismatch de client_id: puede ocurrir en dispositivos
                # pendientes de asignación o recién reasignados (device.client_id transiente).
                if not lic:
                    logger.warning("[HQ-AUTH] Rechazo HQ: license_key=%s no existe en DB", license_key)
                    return {"status": "close", "code": 4001}
            logger.info("[HQ-AUTH] Agente HQ autorizado: device_id=%s", target_device_id)
            return {"status": "ok", "device_id": target_device_id, "client_id": device.client_id}

        # --- Flujo Estándar (No HQ) ---
        is_pending = False
        lic = None
        if not license_key:
            is_pending = True
        else:
            lic = db.query(models.License).filter(models.License.license_key == license_key).first()
            if not lic or not lic.is_active or (lic.expiry_date and lic.expiry_date < datetime.utcnow()):
                is_pending = True

        if not is_pending and lic:
            resolved_client_id = lic.client_id
            # Validar cupo
            devices_count = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.client_id == lic.client_id).count()
            existing_device = db.query(models.CentinelaDevice).filter(
                models.CentinelaDevice.client_id == lic.client_id, 
                models.CentinelaDevice.device_name == device_name
            ).first()
            
            if not existing_device and devices_count >= lic.max_devices:
                return {"status": "error", "message": "Límite de dispositivos excedido", "code": 1008}
        else:
            resolved_client_id = None

        # Buscar dispositivo existente (evitar duplicados: mismo PC en pendientes + asignado)
        device = None
        assist_str = str(client_id_param) if client_id_param else None

        # 1) Por assist_id (ID que muestra ApolloSoporte) — preferir el ya asignado
        if assist_str:
            candidates = (
                db.query(models.CentinelaDevice)
                .filter(models.CentinelaDevice.assist_id == assist_str)
                .order_by(
                    models.CentinelaDevice.client_id.is_(None).asc(),  # asignados primero
                    models.CentinelaDevice.id.desc(),
                )
                .all()
            )
            if candidates:
                device = candidates[0]

        # 2) Por AnyDesk / RustDesk alt_id
        if not device and alt_id:
            candidates = (
                db.query(models.CentinelaDevice)
                .filter(models.CentinelaDevice.alt_remote_id == alt_id)
                .order_by(
                    models.CentinelaDevice.client_id.is_(None).asc(),
                    models.CentinelaDevice.id.desc(),
                )
                .all()
            )
            if candidates:
                device = candidates[0]

        # 3) Por nombre + cliente (licenciado) o nombre sin cliente (pendiente)
        if not device:
            if not is_pending and resolved_client_id is not None:
                device = db.query(models.CentinelaDevice).filter(
                    models.CentinelaDevice.client_id == resolved_client_id,
                    models.CentinelaDevice.device_name == device_name,
                ).first()
            if not device:
                # Cualquier fila con mismo hostname (asignada o pendiente)
                device = (
                    db.query(models.CentinelaDevice)
                    .filter(models.CentinelaDevice.device_name == device_name)
                    .order_by(
                        models.CentinelaDevice.client_id.is_(None).asc(),
                        models.CentinelaDevice.id.desc(),
                    )
                    .first()
                )

        if not device:
            # Solo crear pendiente/nuevo si no hay ningún rastro del PC
            device = models.CentinelaDevice(
                client_id=resolved_client_id,
                device_name=device_name,
                is_online=True,
                alt_remote_id=alt_id,
                assist_id=assist_str,
            )
            db.add(device)
            db.commit()
            db.refresh(device)
        else:
            device.is_online = True
            device.last_seen = datetime.utcnow()
            if alt_id:
                device.alt_remote_id = alt_id
            if assist_str:
                device.assist_id = assist_str
            # Si conectó con licencia válida, asegurar client_id (recupera huérfanos)
            if not is_pending and resolved_client_id is not None and device.client_id is None:
                device.client_id = resolved_client_id
                logger.info(
                    "[WS-HANDSHAKE] Dispositivo huérfano %s (%s) reasignado a client_id=%s",
                    device.id, device_name, resolved_client_id,
                )
            db.commit()

            # Limpiar duplicados pendientes del mismo PC (mismo assist / nombre / alt)
            _purge_duplicate_pending_devices(db, device)

        # Si es conexión pendiente pero el device ya está asignado, devolver su client_id real
        out_client_id = resolved_client_id if resolved_client_id is not None else device.client_id
        return {"status": "ok", "device_id": device.id, "client_id": out_client_id}
    except Exception as e:
        logger.error("[WS-INIT-DB] Error: %s", e)
        return {"status": "exception", "error": str(e)}
    finally:
        db.close()


def save_chat_message(device_id: int, message: str):
    db = SessionLocal()
    try:
        dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        new_chat = models.RemoteChat(
            device_id=device_id,
            technician_id=dev.current_technician_id if dev else None,
            message=message,
            sender_type='client'
        )
        db.add(new_chat)
        db.commit()
        logger.info("[CHAT] Mensaje recibido y guardado en DB del cliente")
    except Exception as e:
        logger.error(f"[DB] Error guardando chat: {e}")
    finally:
        db.close()


def save_remote_log(device_id: int, message: str, level: str):
    db = SessionLocal()
    try:
        new_log = models.RemoteLog(
            device_id=device_id,
            source="agent",
            level=level,
            message=message
        )
        db.add(new_log)
        db.commit()
        logger.info(f"[DB LOG PC-{device_id}]: {message}")
    except Exception as e:
        logger.error(f"Error guardando log en DB: {e}")
    finally:
        db.close()


def backend_remote_log(device_id: int, message: str, level: str = "INFO"):
    db = SessionLocal()
    try:
        new_log = models.RemoteLog(
            device_id=device_id,
            source="backend",
            level=level,
            message=message
        )
        db.add(new_log)
        db.commit()
        logger.info(f"[BACKEND DB LOG PC-{device_id}]: {message}")
    except Exception as e:
        logger.error(f"Error guardando backend log en DB: {e}")
    finally:
        db.close()


def save_device_telemetry(device_id: int, telemetry: dict):
    db = SessionLocal()
    try:
        dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if dev:
            if "remote_password" in telemetry:
                dev.remote_password = telemetry["remote_password"]
            if "last_erp_update" in telemetry:
                val = telemetry["last_erp_update"]
                if isinstance(val, dict):
                    import json
                    dev.last_erp_update = json.dumps(val)
                else:
                    dev.last_erp_update = str(val)
            db.commit()
    except Exception as db_err:
        logger.error(f"[DB] Error guardando telemetria: {db_err}")
        db.rollback()
    finally:
        db.close()


def save_windows_credentials(device_id: int, win_user: str, win_pass: str):
    db = SessionLocal()
    try:
        dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if dev:
            cred_info = f"--- CREDENCIALES DE WINDOWS REGISTRADAS ---\nUsuario: {win_user or 'No reportado'}\nClave: {win_pass or 'Sin clave'}\nFecha: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC\n--------------------------------------------"
            current_notes = dev.notes or ""
            if "--- CREDENCIALES DE WINDOWS REGISTRADAS ---" in current_notes:
                lines = current_notes.split("\n")
                clean_lines = []
                skip = False
                for line in lines:
                    if "--- CREDENCIALES DE WINDOWS REGISTRADAS ---" in line:
                        skip = True
                    elif "--------------------------------------------" in line and skip:
                        skip = False
                        continue
                    if not skip:
                        clean_lines.append(line)
                current_notes = "\n".join(clean_lines).strip()
            dev.notes = (cred_info + "\n" + current_notes).strip()
            db.commit()
    except Exception as db_err:
        logger.error(f"[DB] Error guardando credenciales de Windows: {db_err}")
        db.rollback()
    finally:
        db.close()


def save_alerts_and_get_users(client_id: int, device_name: str, telemetry: dict) -> tuple[list[str], list[str]]:
    alerts = []
    tokens = []
    db = SessionLocal()
    try:
        if telemetry.get("cpu", 0) > 85:
            msg = f"CPU Crítico ({device_name}): {telemetry['cpu']}%"
            alerts.append(msg)
            db.add(models.Alert(client_id=client_id, mensaje=msg, severidad="critica"))
        if telemetry.get("ram", 0) > 90:
            msg = f"RAM Saturada ({device_name}): {telemetry['ram']}%"
            alerts.append(msg)
            db.add(models.Alert(client_id=client_id, mensaje=msg, severidad="critica"))

        if alerts:
            db.commit()
            users_with_token = db.query(models.User).filter(models.User.expo_push_token != None).all()
            tokens = [u.expo_push_token for u in users_with_token]
    except Exception as db_err:
        logger.error(f"[DB] Error guardando alertas: {db_err}")
        db.rollback()
    finally:
        db.close()
    return alerts, tokens


def update_last_seen(device_id: int):
    db = SessionLocal()
    try:
        dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if dev:
            dev.last_seen = datetime.utcnow()
            db.commit()
    except Exception:
        pass
    finally:
        db.close()


def set_device_offline(device_id: int):
    db = SessionLocal()
    try:
        dev = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if dev:
            dev.is_online = False
            dev.current_technician_id = None
            dev.session_start = None
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


@app.websocket("/api/ws/centinela/{client_id}")
async def websocket_centinela(websocket: WebSocket, client_id: int, device_name: str = "Desconocido", license_key: str = Query(""), hq: str = Query(None), device_id: int = Query(None), alt_id: str = Query(None), session_id: int = Query(None)):
    await websocket.accept()
    logger.info(f"[WS-HANDSHAKE] Intento de conexion AGENTE device_id={device_id} name={device_name} alt_id={alt_id} session_id={session_id}")
    
    # Delegar la lógica pesada de la base de datos del handshake a un hilo secundario
    res = await asyncio.to_thread(handle_centinela_handshake, client_id, device_name, license_key, hq, device_id, alt_id)
    
    if res["status"] == "close":
        await websocket.close(code=res["code"])
        return
    elif res["status"] == "error":
        await websocket.send_text(json.dumps({"type": "error", "message": res["message"]}))
        await websocket.close(code=res["code"])
        return
    elif res["status"] == "exception":
        await websocket.close(code=1011) # Error interno del servidor
        return
        
    device_id = res["device_id"]
    resolved_client_id = res["client_id"]
    
    if hq == "1":
        logger.info("[HQ-AGENT] Agente HQ conectado: device=%d", device_id)
        backend_remote_log(device_id, "[WS-CONEXIÓN] Agente remoto se conectó con éxito al WebSocket de alta velocidad (HQ)", "INFO")
        try:
            total_chunks = 0
            total_bytes = 0
            while True:
                try:
                    chunk = await asyncio.wait_for(websocket.receive_bytes(), timeout=30.0)
                    if chunk:
                        total_chunks += 1
                        total_bytes += len(chunk)
                        if total_chunks == 1:
                            backend_remote_log(device_id, f"[TRÁFICO] Recibido primer chunk binario del agente HQ de {len(chunk)} bytes", "INFO")
                        if total_chunks % 50 == 0:
                            backend_remote_log(device_id, f"[TRÁFICO] Recibidos {total_chunks} chunks binarios (total: {total_bytes} bytes) desde el agente", "INFO")
                        
                        if total_chunks % 50 == 0 or total_chunks <= 5: # log first few and every 50th chunk
                            logger.info("[HQ-AGENT] Recibido chunk #%d de %d bytes (total: %d bytes) del device %d", total_chunks, len(chunk), total_bytes, device_id)
                        asyncio.create_task(manager.push_hq_chunk_to_viewers(device_id, chunk))
                except asyncio.TimeoutError:
                    try:
                        logger.debug("[HQ-AGENT] Tiempo de espera inactivo. Enviando ping al agente %d", device_id)
                        await websocket.send_text("ping")
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.debug("[HQ-AGENT] Cerrado: %s", e)
            backend_remote_log(device_id, f"[WS-CONEXIÓN] Error en WebSocket HQ del agente: {e}", "ERROR")
        finally:
            logger.info("[HQ-AGENT] Agente HQ desconectado: device=%d", device_id)
            backend_remote_log(device_id, "[WS-CONEXIÓN] Agente HQ desconectado del WebSocket de alta velocidad", "WARNING")
        return

    # --- Flujo Estándar (No HQ) ---
    logger.info("[WS] Nueva conexion entrante client_id=%s, device=%s", resolved_client_id, device_name)
    
    try:
        # Loop principal sin DB en el hilo principal
        ping_task = asyncio.create_task(server_ping_loop(device_id))
        await manager.connect(device_id, resolved_client_id, websocket, session_id=session_id)

        # Enviar mensaje de bienvenida con el device_id real y client_id a la conexión
        try:
            await websocket.send_json({
                "type": "welcome",
                "device_id": device_id,
                "client_id": resolved_client_id
            })
            logger.info("[WS-WELCOME] Mensaje de bienvenida enviado al agente: device_id=%s, client_id=%s", device_id, resolved_client_id)
        except Exception as welcome_err:
            logger.error("[WS-WELCOME] Error al enviar mensaje de bienvenida: %s", welcome_err)

        # Notificar al agente inmediatamente si hay viewers conectados
        try:
            active_viewers = []
            if device_id in manager.viewer_connections and len(manager.viewer_connections[device_id]) > 0:
                active_viewers.append("Soporte (WS)")
            if device_id in manager.device_viewers:
                now = datetime.utcnow()
                for u_id, (u_name, last_seen) in manager.device_viewers[device_id].items():
                    if (now - last_seen).total_seconds() <= 8.0:
                        if u_name not in active_viewers:
                            active_viewers.append(u_name)
            
            if active_viewers:
                await websocket.send_json({
                    "type": "active_technicians",
                    "technicians": active_viewers
                })
                logger.info("[WS-WELCOME] Agente notificado de viewers activos inmediatamente: %s", active_viewers)
            if manager.has_any_viewers(device_id):
                await manager.notify_agent_viewers_watching(device_id)
        except Exception as welcome_notify_err:
            logger.error("[WS-WELCOME] Error al notificar al agente de viewers activos: %s", welcome_notify_err)


        try:
            while True:
                try:
                    # Timeout ampliado a 45s: tolera picos de CPU/red sin desconectar prematuramente
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=45.0)
                except asyncio.TimeoutError:
                    logger.warning("[HEARTBEAT] Sin senales del dispositivo. Forzando desconexion.")
                    raise WebSocketDisconnect()

                try:
                    is_active_session = True
                    if device_id in manager.selected_sessions:
                        active_ws = manager.device_sessions.get(device_id, {}).get(manager.selected_sessions[device_id])
                        if active_ws and active_ws != websocket:
                            is_active_session = False

                    if data["type"] in ["screen_frame", "video_frame"]:
                        frame_session_id = None
                        for s_id, ws in manager.device_sessions.get(device_id, {}).items():
                            if ws == websocket:
                                frame_session_id = s_id
                                break

                        pending_switch = manager.requested_sessions.get(device_id)
                        if pending_switch is not None:
                            switch_age = None
                            switch_started = manager.switch_requested_at.get(device_id)
                            if switch_started is not None:
                                switch_age = (datetime.utcnow() - switch_started).total_seconds()

                            if frame_session_id == pending_switch:
                                is_active_session = True
                                asyncio.create_task(
                                    manager._complete_session_switch(
                                        device_id,
                                        pending_switch,
                                        websocket,
                                        "frames en sesión solicitada",
                                    )
                                )
                            elif frame_session_id is not None:
                                pending_ws = manager.device_sessions.get(device_id, {}).get(pending_switch)
                                if pending_ws is None or (switch_age is not None and switch_age > 12.0):
                                    is_active_session = True
                                    asyncio.create_task(
                                        manager._complete_session_switch(
                                            device_id,
                                            frame_session_id,
                                            websocket,
                                            f"frames en sesión {frame_session_id} (esperaba {pending_switch})",
                                        )
                                    )
                                else:
                                    is_active_session = False
                            else:
                                is_active_session = False
                        elif not is_active_session:
                            for s_id, ws in manager.device_sessions.get(device_id, {}).items():
                                if ws == websocket:
                                    manager.selected_sessions[device_id] = s_id
                                    manager.active_connections[device_id] = ws
                                    is_active_session = True
                                    logger.info(
                                        "[WS-AUTOPROMOTE] Sesion %s promovida (device %s)",
                                        s_id, device_id,
                                    )
                                    break

                        if is_active_session:
                            frame_data = data.get("image") or data.get("data")
                            delta = data.get("delta")  # None si es frame completo
                            if not delta:  # Solo sobreescribir cache con frames completos
                                manager.client_frames[device_id] = frame_data
                            # PUSH INMEDIATO a todos los viewers WS conectados
                            asyncio.create_task(manager.push_frame_to_viewers(device_id, frame_data, delta))


                    elif data["type"] == "chat_message":
                        msg = data.get("message")
                        # Offload DB call a hilo secundario
                        asyncio.create_task(asyncio.to_thread(save_chat_message, device_id, msg))

                    elif data["type"] == "remote_log":
                        log_msg = data.get("msg", "")
                        level = data.get("level", "DEBUG")
                        
                        active_agents = len(manager.active_connections) if hasattr(manager, 'active_connections') else 0
                        active_viewers = len(manager.viewer_connections) if hasattr(manager, 'viewer_connections') else 0
                        
                        backend_info = f" | [BACKEND STATS]: Agentes Activos={active_agents}, Tecnicos Activos={active_viewers}"
                        final_msg = f"{log_msg}{backend_info}"
                        
                        # Offload DB call a hilo secundario
                        asyncio.create_task(asyncio.to_thread(save_remote_log, device_id, final_msg, level))

                    elif data["type"] == "clipboard_sync":
                        text = data.get("text", "")
                        manager.client_clipboard[device_id] = text
                        logger.debug("[CLIPBOARD] Datos recibidos")

                    elif data["type"] == "session_list":
                        sessions = data.get("sessions", [])
                        manager.client_sessions[device_id] = sessions
                        # Forwardear a todos los viewers conectados
                        asyncio.create_task(manager.push_to_viewers(device_id, {
                            "type": "session_list",
                            "sessions": sessions
                        }))
                        logger.debug("[SESSION] %d sesiones recibidas para device %d", len(sessions), device_id)

                    elif data["type"] == "telemetry":
                        telemetry = data["data"]
                        manager.client_telemetry[device_id] = telemetry

                        # --- ACTUALIZAR CONTRASEÑA DE SOPORTE Y ULTIMA ACTUALIZACION ERP EN DB ---
                        if "remote_password" in telemetry or "last_erp_update" in telemetry:
                            asyncio.create_task(asyncio.to_thread(save_device_telemetry, device_id, telemetry))

                        # --- ACTUALIZAR USUARIO/PASSWORD DE WINDOWS ---
                        win_user = telemetry.get("windows_user") or telemetry.get("windows_username") or telemetry.get("win_user")
                        win_pass = telemetry.get("windows_password") or telemetry.get("windows_pass") or telemetry.get("win_pass")
                        if win_user or win_pass:
                            asyncio.create_task(asyncio.to_thread(save_windows_credentials, device_id, win_user, win_pass))

                        # --- PROACTIVE ALERT LOGIC ---
                        async def handle_alerts():
                            alerts, tokens = await asyncio.to_thread(save_alerts_and_get_users, resolved_client_id, device_name, telemetry)
                            for token in tokens:
                                asyncio.create_task(send_push_notification(token, f"ALERTA {device_name}", "\n".join(alerts)))
                            manager.client_alerts[device_id] = alerts

                        asyncio.create_task(handle_alerts())

                    elif data["type"] in ["file_list", "file_content", "dir_list"]:
                        manager.client_files[device_id] = data

                    elif data["type"] in ["pong", "ping_ack"]:
                        # Heartbeat: el agente respondió al ping, actualizar last_seen de forma no bloqueante
                        asyncio.create_task(asyncio.to_thread(update_last_seen, device_id))

                except WebSocketDisconnect:
                    raise
                except Exception as msg_err:
                    logger.info(
                        "[WS] Error procesando mensaje %r de %r: %s",
                        data.get("type"),
                        device_name,
                        msg_err,
                    )
        finally:
            ping_task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error WS: {e}")
    finally:
        # Poner offline en DB de forma asíncrona no bloqueante
        await asyncio.to_thread(set_device_offline, device_id)
        manager.disconnect(device_id, resolved_client_id, websocket=websocket)




@app.get("/api/centinelas/activos", tags=["Centinela"])
def get_centinelas_activos(current_user: models.User = Depends(get_current_user)):
    """ React consulta por acá qué PCs maestras están encendidas y corriendo el programa Centinela. """
    return manager.client_telemetry

@app.get("/api/centinelas/devices/{device_id}/frame", tags=["Centinela"])
async def get_centinela_frame(device_id: int, current_user: models.User = Depends(get_current_user)):
    """ Devuelve el último frame capturado para un dispositivo específico y registra al técnico conectado. """
    now = datetime.utcnow()
    if device_id not in manager.device_viewers:
        manager.device_viewers[device_id] = {}
        
    manager.device_viewers[device_id][current_user.id] = (current_user.full_name or current_user.nombre or current_user.email or "Soporte", now)
    
    last_notify = manager.last_viewer_notification.get(device_id)
    if not last_notify or (now - last_notify).total_seconds() > 1.0:
        stale_threshold = 5.0
        active_viewers = []
        to_delete = []
        for u_id, (u_name, last_seen) in manager.device_viewers[device_id].items():
            if (now - last_seen).total_seconds() > stale_threshold:
                to_delete.append(u_id)
            else:
                active_viewers.append(u_name)
        for u_id in to_delete:
            del manager.device_viewers[device_id][u_id]

        # Evitar pausar captura si hay viewers activos vía WebSockets (normal o HQ)
        has_ws_viewers = (device_id in manager.viewer_connections and len(manager.viewer_connections[device_id]) > 0) or \
                         (device_id in manager.hq_viewer_connections and len(manager.hq_viewer_connections[device_id]) > 0)
        if has_ws_viewers:
            active_viewers.append("Soporte Web (WS)")
            
        await manager.send_json_safe(device_id, {
            "type": "active_technicians",
            "technicians": active_viewers
        })
        manager.last_viewer_notification[device_id] = now
        
    frame = manager.client_frames.get(device_id)
    return {"frame": frame}


@app.get("/api/centinelas/devices/{device_id}/windows-sessions", tags=["Centinela"])
async def get_device_windows_sessions(
    device_id: int,
    refresh: bool = False,
    current_user: models.User = Depends(get_current_user),
):
    """Lista de sesiones Windows (Consola + RDP). Opcionalmente pide refresh al agente."""
    if refresh and device_id in manager.active_connections:
        await manager.send_json_safe(device_id, {"type": "get_sessions"})
    sessions = manager.client_sessions.get(device_id, [])
    return {"sessions": sessions, "device_id": device_id}

@app.get("/api/centinelas/alertas", tags=["Centinela"])
def get_centinelas_alertas(current_user: models.User = Depends(get_current_user)):
    """ Devuelve todas las alertas activas de todos los centinelas. """
    return manager.client_alerts

@app.get("/api/centinelas/alertas/historial", response_model=List[schemas.AlertOut], tags=["Centinela"])
def get_alertas_historial(limit: int = 50, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Devuelve el historial persistente de alertas almacenadas en la base de datos. """
    return db.query(models.Alert).order_by(models.Alert.fecha_creacion.desc()).limit(limit).all()

@app.delete("/api/centinelas/devices/{device_id}", tags=["Centinela"])
def delete_centinela_device(device_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Elimina un dispositivo Centinela de la base de datos para liberar cupo de licencia. """
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    
    # Si está conectado actualmente, desconectarlo del manager
    try:
        manager.disconnect(device_id, device.client_id)
    except Exception as e:
        logger.error(f"Error al desconectar manager durante eliminación: {e}")
    
    # Eliminar registros dependientes manualmente para evitar IntegrityError (ForeingKey)
    db.query(models.SupportSession).filter(models.SupportSession.device_id == device_id).delete(synchronize_session=False)
    db.query(models.RemoteChat).filter(models.RemoteChat.device_id == device_id).delete(synchronize_session=False)
    db.query(models.RemoteLog).filter(models.RemoteLog.device_id == device_id).delete(synchronize_session=False)

    db.delete(device)
    db.commit()
    return {"status": "success", "message": "Dispositivo eliminado correctamente"}

@app.put("/api/centinelas/devices/{device_id}/notes", tags=["Centinela"])
def update_centinela_device_notes(device_id: int, payload: schemas.DeviceNotesUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Actualiza las notas/recordatorios persistentes de un dispositivo Centinela. """
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
    
    device.notes = payload.notes
    db.commit()
    return {"status": "success", "message": "Notas actualizadas correctamente", "notes": device.notes}


@app.get("/api/centinelas/pending", response_model=List[schemas.CentinelaDeviceOut], tags=["Centinela"])
def get_pending_centinelas(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Devuelve dispositivos pendientes de licencia.
    Autolimpia huérfanos que ya tienen gemelo asignado (mismo assist_id / alt / hostname). """
    devices = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.client_id == None).all()

    # Autodedup: si hay un PC asignado con mismo assist/alt/nombre, borrar el pending
    cleaned = []
    for dev in list(devices):
        twin = None
        if dev.assist_id:
            twin = (
                db.query(models.CentinelaDevice)
                .filter(
                    models.CentinelaDevice.assist_id == dev.assist_id,
                    models.CentinelaDevice.client_id != None,
                    models.CentinelaDevice.id != dev.id,
                )
                .first()
            )
        if not twin and dev.alt_remote_id:
            twin = (
                db.query(models.CentinelaDevice)
                .filter(
                    models.CentinelaDevice.alt_remote_id == dev.alt_remote_id,
                    models.CentinelaDevice.client_id != None,
                    models.CentinelaDevice.id != dev.id,
                )
                .first()
            )
        if not twin and dev.device_name:
            twin = (
                db.query(models.CentinelaDevice)
                .filter(
                    models.CentinelaDevice.device_name == dev.device_name,
                    models.CentinelaDevice.client_id != None,
                    models.CentinelaDevice.id != dev.id,
                )
                .first()
            )
        if twin:
            _purge_duplicate_pending_devices(db, twin)
            continue
        cleaned.append(dev)

    devices = cleaned

    for dev in devices:
        telemetry = manager.client_telemetry.get(dev.id, {})
        serials = telemetry.get("apollo_serials", [])
        dev.apollo_serials = serials
        dev.proposed_client = None

        # Enriquecer con datos de telemetría en vivo para identificación
        dev.os           = telemetry.get("os", None)
        dev.cpu          = telemetry.get("cpu", None)
        dev.ram          = telemetry.get("ram", None)
        dev.system_info  = telemetry.get("system_info", None)
        
        if serials:
            for serial in serials:
                if len(serial) >= 4:
                    client_code = serial[:4]
                    proposed = db.query(models.Client).filter(models.Client.codigo == client_code).first()
                    if proposed:
                        dev.proposed_client = proposed
                        break
    return devices


@app.post("/api/centinelas/devices/{device_id}/assign/{client_id}", tags=["Centinela"])
async def assign_centinela_license(device_id: int, client_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Asigna un dispositivo pendiente a un cliente y le envía su nueva licencia de forma segura por WebSocket. """
    import uuid
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")
        
    client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    # Buscar o auto-generar licencia para este cliente (300 PCs, sin vencimiento por defecto)
    lic = db.query(models.License).filter(models.License.client_id == client_id).first()
    if not lic:
        new_key = f"APOLLO-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:4].upper()}"
        lic = models.License(
            license_key=new_key,
            client_id=client_id,
            max_devices=300,
            expiry_date=None,
            is_active=True
        )
        db.add(lic)
        db.commit()
        db.refresh(lic)
        logger.info("[ASSIGN] Licencia autogenerada")
        
    # Validar cupo de dispositivos del cliente
    devices_count = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.client_id == client_id).count()
    if devices_count >= lic.max_devices:
        raise HTTPException(status_code=400, detail="Límite de dispositivos excedido para la licencia de este cliente")
        
    # Asignar dispositivo
    device.client_id = client_id
    db.commit()
    
    # Enviar por WebSocket la licencia asignada al dispositivo para que la guarde localmente
    await manager.send_json_safe(device_id, {
        "type": "license_assigned",
        "license_key": lic.license_key
    })
    
    # Actualizar la conexión interna del manager
    if device_id in manager.active_connections:
        # Retirar del cliente anterior si existía
        for cid, dev_list in list(manager.active_clients.items()):
            if device_id in dev_list:
                dev_list.remove(device_id)
        # Asignar al nuevo cliente en el manager
        if client_id not in manager.active_clients:
            manager.active_clients[client_id] = []
        if device_id not in manager.active_clients[client_id]:
            manager.active_clients[client_id].append(device_id)
        
    return {"status": "success", "message": f"Dispositivo asignado exitosamente a {client.razon_social}", "license_key": lic.license_key}


@app.post("/api/users/push-token", tags=["Seguridad"])
async def register_push_token(token_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Registra el token de Expo Push del dispositivo del usuario. """
    token = token_data.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token no proporcionado")
    
    current_user.expo_push_token = token
    db.commit()
    return {"status": "ok", "message": "Token registrado correctamente"}

def log_session_command(device_id: int, technician_id: int, command: str, db: Session):
    # Buscar sesión activa para este técnico en este dispositivo (end_time es None)
    session = db.query(models.SupportSession).filter(
        models.SupportSession.device_id == device_id,
        models.SupportSession.technician_id == technician_id,
        models.SupportSession.end_time == None
    ).order_by(models.SupportSession.start_time.desc()).first()
    
    if session:
        import json
        try:
            cmds = json.loads(session.commands_run) if session.commands_run else []
        except Exception as e:
            logger.error("Error parsing commands list: %s", e)
            cmds = []
        
        # Añadir timestamp local y comando
        cmds.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "cmd": command
        })
        session.commands_run = json.dumps(cmds)
        db.commit()

def log_session_file(device_id: int, technician_id: int, file_info: str, db: Session):
    session = db.query(models.SupportSession).filter(
        models.SupportSession.device_id == device_id,
        models.SupportSession.technician_id == technician_id,
        models.SupportSession.end_time == None
    ).order_by(models.SupportSession.start_time.desc()).first()
    
    if session:
        import json
        try:
            files = json.loads(session.files_transferred) if session.files_transferred else []
        except Exception as e:
            logger.error("Error parsing files list: %s", e)
            files = []
        
        files.append({
            "time": datetime.utcnow().strftime("%H:%M:%S"),
            "file": file_info
        })
        session.files_transferred = json.dumps(files)
        db.commit()

@app.post("/api/centinelas/devices/{device_id}/command", tags=["Centinela"])
async def send_centinela_command(device_id: int, command_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Envía una orden remota a un dispositivo específico. """
    cmd = command_data.get("command")
    if not cmd:
        raise HTTPException(status_code=400, detail="Falta el comando.")
    
    # Obtener el dispositivo para saber el client_id (para auditoría)
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device: raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    if device_id not in manager.active_connections:
        raise HTTPException(status_code=404, detail="Dispositivo offline")

    await manager.send_json_safe(device_id, {"type": "run_command", "command": cmd})
    
    # Grabar Auditoría
    log = models.AccessLog(
        technician_id=current_user.id,
        client_id=device.client_id,
        action=f"COMANDO en {device.device_name}: {cmd}"
    )
    db.add(log)
    
    # Loguear en la sesión activa si existe
    try:
        log_session_command(device_id, current_user.id, cmd, db)
    except Exception as e:
        logger.error("Error logging session command: %s", e)

    db.commit()
    return {"status": "success"}

@app.post("/api/centinelas/devices/{device_id}/control", tags=["Centinela"])
async def send_centinela_control(device_id: int, control_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Envía una acción de ratón o teclado (clics, textos, teclas especiales) al dispositivo. """
    has_ws = bool(manager.device_sessions.get(device_id)) or device_id in manager.active_connections
    if not has_ws:
        raise HTTPException(status_code=404, detail="Dispositivo offline")
    cmd_type = control_data.get("type")
    if cmd_type == "switch_session":
        await manager.handle_session_switch(device_id, control_data)
    elif cmd_type == "login_session" and control_data.get("password"):
        target_session_id = int(control_data.get("session_id") or 1)
        manager.requested_sessions[device_id] = target_session_id
        manager.switch_requested_at[device_id] = datetime.utcnow()
        manager.client_frames.pop(device_id, None)
        manager.frame_buffer.pop(device_id, None)
        backend_remote_log(
            device_id,
            f"[SESSION-SWITCH] login_session (HTTP) -> sesión {target_session_id}",
            "INFO",
        )
        for v_ws in list(manager.viewer_connections.get(device_id, {}).values()):
            try:
                await v_ws.send_json({
                    "type": "session_switching",
                    "target_session_id": target_session_id,
                })
            except Exception:
                pass
        asyncio.create_task(manager._session_switch_watchdog(device_id, target_session_id))
    if not await manager.send_json_to_device(device_id, control_data):
        backend_remote_log(device_id, f"[CONTROL] Comando {cmd_type} no entregado al agente", "WARNING")
    return {"status": "success"}

@app.post("/api/centinelas/devices/{device_id}/chat", tags=["Centinela"])
async def send_centinela_chat(device_id: int, chat_data: schemas.RemoteChatBase, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Envía chat a un dispositivo específico y lo guarda en el historial. """
    msg = chat_data.message
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device: raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    # Guardar en DB
    new_chat = models.RemoteChat(
        device_id=device_id,
        technician_id=current_user.id,
        message=msg,
        sender_type='tech'
    )
    db.add(new_chat)
    db.commit()

    if device_id in manager.active_connections:
        await manager.send_json_safe(device_id, {
            "type": "chat_message", 
            "message": msg, 
            "tech_name": current_user.full_name or current_user.nombre
        })
        return {"status": "ok"}
    return {"status": "saved_offline", "message": "Mensaje guardado pero dispositivo offline"}

@app.get("/api/centinelas/devices/{device_id}/chat", response_model=List[schemas.RemoteChatOut], tags=["Centinela"])
def get_centinela_chat_history(device_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Recupera los últimos 50 mensajes de chat entre técnicos y este dispositivo. """
    return db.query(models.RemoteChat).filter(models.RemoteChat.device_id == device_id).order_by(models.RemoteChat.timestamp.asc()).limit(50).all()

@app.post("/api/centinelas/devices/{device_id}/clipboard", tags=["Centinela"])
async def sync_centinela_clipboard(device_id: int, clip_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Sincroniza el portapapeles con un dispositivo específico. """
    text = clip_data.get("text")
    if device_id in manager.active_connections:
        await manager.send_json_safe(device_id, {"type": "clipboard_sync", "text": text})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Dispositivo offline")

@app.get("/api/centinelas/devices/{device_id}/clipboard", tags=["Centinela"])
def get_centinela_clipboard(device_id: int, current_user: models.User = Depends(get_current_user)):
    """ Recupera el último texto del portapapeles reportado por el cliente. """
    text = manager.client_clipboard.get(device_id, "")
    return {"text": text}

@app.get("/api/centinelas/devices/{device_id}/files", tags=["Centinela"])
async def get_centinela_files(device_id: int, path: str = "C:\\", current_user: models.User = Depends(get_current_user)):
    """ Solicita al agente listar un directorio y devuelve la lista de archivos. """
    if device_id in manager.active_connections:
        # Limpiar caché previa para forzar lectura fresca
        if device_id in manager.client_files:
            del manager.client_files[device_id]
            
        await manager.send_json_safe(device_id, {
            "type": "list_dir",
            "path": path
        })
        
        # Esperar brevemente a que el agente responda vía WebSocket (máximo 1.5s)
        for _ in range(15):
            await asyncio.sleep(0.1)
            cached = manager.client_files.get(device_id)
            if cached and cached.get("type") == "dir_list" and cached.get("path") == path:
                return cached
                
        # Retornar lo que tengamos en cache si no llegó a tiempo
        cached = manager.client_files.get(device_id)
        if cached:
            return cached
            
    return {"status": "loading", "path": path, "files": []}

@app.get("/api/centinelas/devices/{device_id}/files/download", tags=["Centinela"])
async def request_file_download(device_id: int, path: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Solicita al agente que suba un archivo al servidor y lo descarga directamente. """
    from fastapi.responses import FileResponse
    
    if device_id not in manager.active_connections:
        raise HTTPException(status_code=404, detail="Dispositivo offline")

    # Limpiar estado previo
    if device_id in manager.client_files:
        try:
            del manager.client_files[device_id]
        except:
            pass

    # Enviar solicitud al agente
    await manager.send_json_safe(device_id, {
        "type": "upload_to_server", 
        "path": path,
        "upload_url": f"{API_URL.replace('/api', '')}/api/centinelas/devices/{device_id}/files/receive"
    })

    # Esperar hasta 15 segundos a que el agente suba el archivo
    filename = os.path.basename(path)
    for _ in range(150):
        await asyncio.sleep(0.1)
        status = manager.client_files.get(device_id)
        if status and status.get("status") == "ready" and status.get("filename") == filename:
            file_path = os.path.join("temp_files", f"{device_id}_{filename}")
            if os.path.exists(file_path):
                try:
                    log_session_file(device_id, current_user.id, f"Descarga: {filename} (Ruta: {path})", db)
                except Exception as e:
                    logger.error("Error logging downloaded file: %s", e)
                return FileResponse(file_path, filename=filename)

    raise HTTPException(status_code=408, detail="Tiempo de espera agotado. El agente no pudo transmitir el archivo.")

@app.post("/api/centinelas/devices/{device_id}/files/receive", tags=["Centinela"])
async def receive_file_from_agent(device_id: int, file: UploadFile = File(...)):
    """ Endpoint donde el agente sube el archivo solicitado por el técnico. """
    temp_dir = "temp_files"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)
    
    file_path = os.path.join(temp_dir, f"{device_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    manager.client_files[device_id] = {"status": "ready", "filename": file.filename, "download_path": f"/api/temp/{device_id}_{file.filename}"}
    return {"status": "ok"}

@app.post("/api/centinelas/devices/{device_id}/files/upload", tags=["Centinela"])
async def upload_file_to_agent(device_id: int, file: UploadFile = File(...), dest_path: str = "C:\\ApolloTemp", db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ El técnico sube un archivo para enviar a la PC del cliente. """
    temp_dir = "temp_files"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)
    
    save_path = os.path.join(temp_dir, f"out_{device_id}_{file.filename}")
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if device_id in manager.active_connections:
        await manager.send_json_safe(device_id, {
            "type": "download_from_server",
            "url": f"{API_URL.replace('/api', '')}/api/temp/out_{device_id}_{file.filename}",
            "dest_path": os.path.join(dest_path, file.filename)
        })
        try:
            log_session_file(device_id, current_user.id, f"Subida: {file.filename} (Destino: {dest_path})", db)
        except Exception as e:
            logger.error("Error logging uploaded file: %s", e)
        return {"status": "dispatch_sent"}
    raise HTTPException(status_code=404, detail="Dispositivo offline")

@app.post("/api/centinelas/devices/{device_id}/verify-password", tags=["Centinela"])
async def verify_remote_password(device_id: int, data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Verifica el PIN de un dispositivo y registra el inicio de sesión del técnico. """
    try:
        # LOGS DE DEPURACION AL DISCO Y CONSOLA
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_verify.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.utcnow().isoformat()} - VERIFY REMOTE PASSWORD ---\n")
            f.write(f"Device ID: {device_id}\n")
            f.write(f"Current User: {current_user.nombre if current_user else 'None'}\n")
            f.write(f"Models module loaded from: {getattr(models, '__file__', 'unknown')}\n")
            f.write(f"Attributes in models module: {dir(models)}\n")
            f.write(f"Has SupportSession: {hasattr(models, 'SupportSession')}\n")
        
        logger.debug("[VERIFY] Modelos cargados")
        logger.debug("[VERIFY] Modelos cargados")

        password = data.get("password")
        device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
        if not device: raise HTTPException(status_code=404, detail="PC no encontrada")
        
        db_password = str(device.remote_password).strip() if device.remote_password else ""
        input_password = str(password).strip() if password is not None else ""
        
        if not db_password or db_password == input_password:
            # Si no tiene clave, entra directo (requisito USER)
            device.current_technician_id = current_user.id
            device.session_start = datetime.utcnow()
            device.last_support_date = datetime.utcnow()
            db.add(models.AccessLog(technician_id=current_user.id, client_id=device.client_id, action=f"CONEXIÓN REMOTA: {device.device_name}"))
            
            # Cerrar cualquier sesión previa de este técnico en este dispositivo que haya quedado colgada (sin end_time)
            if hasattr(models, "SupportSession"):
                previous_active = db.query(models.SupportSession).filter(
                    models.SupportSession.device_id == device_id,
                    models.SupportSession.technician_id == current_user.id,
                    models.SupportSession.end_time == None
                ).all()
                for s in previous_active:
                    s.end_time = datetime.utcnow()
                
                # Crear la nueva sesión de soporte activo
                new_session = models.SupportSession(
                    device_id=device_id,
                    technician_id=current_user.id,
                    start_time=datetime.utcnow(),
                    commands_run="[]",
                    files_transferred="[]"
                )
                db.add(new_session)
                db.commit()
                session_id = new_session.id
            else:
                db.commit()
                session_id = None
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write("WARNING: SupportSession class is missing from models module. Skipping sessions table write.\n")
            
            # Notificar al Agente que un técnico ha entrado (todas las sesiones WS vivas)
            await manager.send_json_safe(device_id, {
                "type": "technician_joined",
                "name": current_user.full_name or current_user.nombre,
            })
            await manager.send_json_safe(device_id, {"type": "refresh_frame"})
            return {"status": "ok", "session_id": session_id}
        else:
            raise HTTPException(status_code=400, detail="PIN de acceso remoto incorrecto.")
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        # Log error
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug_verify.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"CRITICAL ERROR: {str(e)}\n{tb}\n")
        logger.critical("[VERIFY] Error critico en verify_remote_password")
        
        raise HTTPException(
            status_code=500, 
            detail=f"Error interno (Debug Info):\nMsg: {str(e)}\nPath: {getattr(models, '__file__', 'unknown')}\nHasSession: {hasattr(models, 'SupportSession')}\nTraceback: {tb}"
        )

@app.post("/api/centinelas/devices/{device_id}/end-session", tags=["Centinela"])
async def end_remote_session(device_id: int, payload: dict = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Finaliza la sesión actual de un técnico en una PC y graba el reporte con IA. """
    comments = payload.get("comment", "") if payload else ""
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    
    if device:
        device.current_technician_id = None
        device.session_start = None
        db.add(models.AccessLog(technician_id=current_user.id, client_id=device.client_id, action=f"SESIÓN FINALIZADA: {device.device_name}"))
        db.commit()
        
    # Buscar sesión activa de soporte
    session = db.query(models.SupportSession).filter(
        models.SupportSession.device_id == device_id,
        models.SupportSession.technician_id == current_user.id,
        models.SupportSession.end_time == None
    ).order_by(models.SupportSession.start_time.desc()).first()
    
    if session:
        session.end_time = datetime.utcnow()
        session.comments = comments
        duration = session.end_time - session.start_time
        duration_seconds = int(duration.total_seconds())
        
        # Generar reporte automático con IA o Fallback offline
        import json
        try:
            cmds_list = json.loads(session.commands_run) if session.commands_run else []
            cmds_desc = ", ".join([c.get("cmd") for c in cmds_list]) if cmds_list else "Ninguno"
        except:
            cmds_desc = "Ninguno"
            
        try:
            files_list = json.loads(session.files_transferred) if session.files_transferred else []
            files_desc = ", ".join([f.get("file") for f in files_list]) if files_list else "Ninguno"
        except:
            files_desc = "Ninguno"
            
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key:
            try:
                prompt = f"""
Actúa como un Coordinador Técnico de TI Inteligente. Resume de forma ejecutiva en un reporte estructurado y elegante en español lo que un operador de soporte técnico realizó en una PC cliente de Apollo ERP basándote en las siguientes acciones:

- Comandos Ejecutados: {cmds_desc}
- Archivos Transferidos: {files_desc}
- Comentario Manual del Operador: "{comments}"

Instrucciones: Genera una lista compacta y profesional en español (en formato Markdown, máx 4 viñetas) resumiendo las intervenciones clave y confirmando la resolución. No uses preámbulos.
"""
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}"
                headers = {"Content-Type": "application/json"}
                payload_gemini = {
                    "contents": [{
                        "parts": [{"text": prompt}]
                    }]
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(url, headers=headers, json=payload_gemini, timeout=15.0)
                    if resp.status_code == 200:
                        res_json = resp.json()
                        ai_text = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                        session.ai_report = ai_text
                    else:
                        session.ai_report = f"Generación automática por IA: El operador ejecutó {cmds_desc} y transfirió {files_desc}."
            except Exception as e:
                session.ai_report = f"Generación automática (Falla de API): El operador ejecutó {cmds_desc} y transfirió {files_desc}."
        else:
            # Fallback offline
            bullet_points = []
            if "spooler" in cmds_desc.lower() or "stop" in cmds_desc.lower():
                bullet_points.append("* ðŸ”„ **Reinicio del Spooler de Windows:** Se restableció la cola de impresión de Windows para liberar documentos retenidos.")
            if "temp" in cmds_desc.lower() or "del" in cmds_desc.lower():
                bullet_points.append("* ðŸ§¹ **Limpieza del Sistema:** Se eliminaron archivos temporales y de caché en %TEMP% para corregir bloqueos.")
            if files_desc != "Ninguno":
                bullet_points.append(f"* ðŸ“ **Transferencia de Archivos:** Se gestionaron transferencias de archivos: {files_desc}.")
            if comments:
                bullet_points.append(f"* ðŸ’¬ **Notas del Técnico:** \"{comments}\"")
                
            if not bullet_points:
                bullet_points.append("* ðŸ” **Monitoreo Remoto:** Se mantuvo sesión activa de inspección de la terminal sin comandos intrusivos.")
                if comments:
                    bullet_points.append(f"* ðŸ’¬ **Notas del Técnico:** \"{comments}\"")
                    
            session.ai_report = "\n".join(bullet_points)
            
        db.commit()
        return {
            "status": "ok",
            "session_id": session.id,
            "duration": duration_seconds,
            "comments": session.comments,
            "ai_report": session.ai_report,
            "commands_run": session.commands_run,
            "files_transferred": session.files_transferred
        }
    return {"status": "ok"}


@app.post("/api/centinelas/devices/{device_id}/release-session", tags=["Centinela"])
async def release_device_session(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Libera sesión remota colgada: quita técnico asignado y cierra SupportSessions abiertas."""
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    now = datetime.utcnow()
    open_sessions = db.query(models.SupportSession).filter(
        models.SupportSession.device_id == device_id,
        models.SupportSession.end_time == None,
    ).all()
    for session in open_sessions:
        session.end_time = now
        if not session.comments:
            session.comments = (
                f"Liberado por {current_user.full_name or current_user.nombre or current_user.email}"
            )

    prev_tech = device.current_technician_id
    device.current_technician_id = None
    device.session_start = None

    db.add(models.AccessLog(
        technician_id=current_user.id,
        client_id=device.client_id,
        action=f"LIBERAR SESIÓN: {device.device_name} (tech previo={prev_tech})",
    ))
    db.commit()

    manager.requested_sessions.pop(device_id, None)
    manager.switch_requested_at.pop(device_id, None)
    if device_id in manager.device_viewers:
        manager.device_viewers[device_id].clear()

    await manager.send_json_safe(device_id, {"type": "active_technicians", "technicians": []})
    backend_remote_log(
        device_id,
        f"[ADMIN] Sesión liberada por {current_user.email} (cerradas={len(open_sessions)})",
        "INFO",
    )

    return {
        "status": "success",
        "closed_sessions": len(open_sessions),
        "message": "Sesión liberada correctamente",
    }


@app.post("/api/centinelas/devices/{device_id}/force-refresh", tags=["Centinela"])
async def force_refresh_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Cancela switch pendiente y fuerza al agente a reanudar captura de pantalla."""
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    manager.requested_sessions.pop(device_id, None)
    manager.switch_requested_at.pop(device_id, None)
    manager.client_frames.pop(device_id, None)

    ws_sessions = list(manager.device_sessions.get(device_id, {}).keys())
    tech_name = current_user.full_name or current_user.nombre or current_user.email or "Soporte"

    sent_join = await manager.send_json_safe(device_id, {
        "type": "technician_joined",
        "name": tech_name,
    })
    await manager.send_json_safe(device_id, {
        "type": "active_technicians",
        "technicians": [tech_name],
    })
    sent_refresh = await manager.send_json_safe(device_id, {"type": "refresh_frame"})
    await manager.send_json_safe(device_id, {"type": "wake_screen"})

    backend_remote_log(
        device_id,
        f"[ADMIN] Force refresh por {current_user.email} | ws_sessions={ws_sessions} sent={bool(sent_join or sent_refresh)}",
        "INFO",
    )

    return {
        "status": "success",
        "agent_ws_sessions": ws_sessions,
        "commands_sent": bool(sent_join or sent_refresh),
        "message": (
            "Comandos enviados al agente"
            if (sent_join or sent_refresh)
            else "Agente sin WebSocket activo — reiniciar Centinela en la PC cliente"
        ),
    }


@app.get("/api/centinelas/devices/{device_id}/last-session", tags=["Centinela"])
def get_device_last_session(device_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Obtiene la última sesión de soporte completada para un dispositivo específico. """
    session = db.query(models.SupportSession).filter(
        models.SupportSession.device_id == device_id,
        models.SupportSession.end_time != None
    ).order_by(models.SupportSession.end_time.desc()).first()
    
    if not session:
        return None
        
    return {
        "id": session.id,
        "technician_name": session.technician.full_name if session.technician else "Desconocido",
        "end_time": session.end_time.isoformat() if session.end_time else None,
        "comments": session.comments,
        "ai_report": session.ai_report,
        "duration": session.duration_seconds,
        "commands_run": session.commands_run,
        "files_transferred": session.files_transferred
    }

@app.patch("/api/centinelas/devices/{device_id}", tags=["Centinela"])
async def update_device_settings(device_id: int, data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Permite al técnico cambiar el PIN u otros ajustes de una PC específica. """
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device: raise HTTPException(status_code=404, detail="PC no encontrada")
    
    if "remote_password" in data:
        device.remote_password = data["remote_password"]
    
    db.commit()
    return {"status": "ok", "message": "Ajustes de dispositivo actualizados."}

@app.get("/api/clients/{client_id}/audit-logs", response_model=List[schemas.AccessLogOut], tags=["Clientes"])
def get_client_audit_logs(client_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Obtiene el historial de intervenciones técnicas para un cliente. """
    return db.query(models.AccessLog).filter(models.AccessLog.client_id == client_id).order_by(models.AccessLog.fecha_creacion.desc()).all()


@app.post("/api/centinelas/logs/frontend", tags=["Centinela"])
def log_frontend_event(device_id: int, message: str, level: str = "INFO", db: Session = Depends(get_db)):
    new_log = models.RemoteLog(
        device_id=device_id,
        source="frontend",
        level=level,
        message=message
    )
    db.add(new_log)
    db.commit()
    return {"status": "ok"}


@app.get("/api/centinelas/logs", response_model=List[schemas.RemoteLogOut], tags=["Centinela"])
def get_centinela_logs(
    device_id: Optional[int] = Query(None),
    source: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """ Obtiene la bitácora de logs de telemetría de todos los dispositivos o filtrado por dispositivo. """
    query = db.query(
        models.RemoteLog.id,
        models.RemoteLog.device_id,
        models.RemoteLog.source,
        models.RemoteLog.level,
        models.RemoteLog.message,
        models.RemoteLog.timestamp,
        models.CentinelaDevice.device_name.label("device_name")
    ).outerjoin(
        models.CentinelaDevice, models.RemoteLog.device_id == models.CentinelaDevice.id
    )

    if device_id is not None:
        query = query.filter(models.RemoteLog.device_id == device_id)
    if source:
        query = query.filter(models.RemoteLog.source == source)
    if level:
        query = query.filter(models.RemoteLog.level == level)

    results = query.order_by(models.RemoteLog.id.desc()).limit(limit).all()
    
    return [
        {
            "id": r.id,
            "device_id": r.device_id,
            "source": r.source,
            "level": r.level,
            "message": r.message,
            "timestamp": r.timestamp,
            "device_name": r.device_name if r.device_id else "Servidor Backend"
        }
        for r in results
    ]


@app.post("/api/centinelas/logs/clear", tags=["Centinela"])
def clear_centinela_logs(
    device_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """ Permite limpiar la bitácora de logs. Si se pasa device_id, solo limpia ese dispositivo. """
    try:
        query = db.query(models.RemoteLog)
        if device_id is not None:
            query = query.filter(models.RemoteLog.device_id == device_id)
            msg = f"Logs eliminados para el dispositivo ID {device_id}."
        else:
            msg = "Bitácora completa de logs eliminada."
        
        query.delete(synchronize_session=False)
        db.commit()
        return {"status": "success", "message": msg}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error al limpiar logs: {str(e)}")







@app.post("/api/centinela/ota_progress")
async def ota_progress(payload: schemas.OTAProgress):
    try:
        device_id = int(payload.device_id)
        if device_id in manager.client_telemetry:
            manager.client_telemetry[device_id]["ota_status"] = payload.status
            manager.client_telemetry[device_id]["ota_progress"] = payload.progress
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

from fastapi.responses import FileResponse

@app.post("/api/centinela/{device_id}/force_update")
async def force_update(device_id: int):
    if device_id in manager.active_connections:
        ws = manager.active_connections[device_id]
        try:
            await ws.send_json({"type": "command", "action": "force_update"})
            return {"status": "ok", "message": "Command sent"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Agent not connected"}

@app.get("/api/centinela/download_update")
def download_update():
    file_path = os.path.join("updates", "ApolloSetup.exe")
    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="application/octet-stream", filename="ApolloSetup.exe")
    return {"error": "File not found"}

@app.get("/api/centinela/update_check")
def check_update():
    version_file = os.path.join("updates", "version.json")
    if os.path.exists(version_file):
        try:
            with open(version_file, "r") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}
    return {"version": "0.0.0", "url": ""}



# ==========================================
# RUTAS DE BACKUP Y RESTORE ENCRIPTADO
# ==========================================
BACKUP_ENCRYPTION_KEY = b'G1yB-o_x3t1U7pM7M3o1I9_z1Y0XqPzG1yB-o_x3t1U='
cipher_suite = Fernet(BACKUP_ENCRYPTION_KEY)

def get_pg_dump_path():
    possible_paths = [
        "pg_dump", 
        r"C:\Program Files\PostgreSQL\15\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\14\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\13\bin\pg_dump.exe",
        r"C:\Program Files\PostgreSQL\12\bin\pg_dump.exe",
    ]
    for path in possible_paths:
        if path == "pg_dump":
            try:
                subprocess.run(["pg_dump", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return "pg_dump"
            except:
                continue
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No se encontr pg_dump en el servidor.")

def get_psql_path():
    possible_paths = [
        "psql", 
        r"C:\Program Files\PostgreSQL\15\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\14\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\13\bin\psql.exe",
        r"C:\Program Files\PostgreSQL\12\bin\psql.exe",
    ]
    for path in possible_paths:
        if path == "psql":
            try:
                subprocess.run(["psql", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return "psql"
            except:
                continue
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No se encontr psql en el servidor.")

@app.get("/api/backup")
def backup_database(current_user: models.User = Depends(get_current_user)):
    from database import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    if current_user.rol != 'admin':
        raise HTTPException(status_code=403, detail="Solo administradores pueden hacer backups.")
    
    try:
        pg_dump = get_pg_dump_path()
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        fd_raw, raw_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd_raw)
        
        fd_enc, enc_path = tempfile.mkstemp(suffix=".apbk")
        os.close(fd_enc)
        
        cmd = [
            pg_dump,
            "-h", DB_HOST,
            "-p", str(DB_PORT),
            "-U", DB_USER,
            "-d", DB_NAME,
            "--clean",
            "--if-exists",
            "-F", "p", 
            "-f", raw_path
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"pg_dump fall: {result.stderr}")
            
        with open(raw_path, "rb") as f_in:
            raw_data = f_in.read()
            
        encrypted_data = cipher_suite.encrypt(raw_data)
        
        with open(enc_path, "wb") as f_out:
            f_out.write(encrypted_data)
            
        os.remove(raw_path)
        
        filename = f"ApolloBackup_{time.strftime('%Y%m%d_%H%M%S')}.apbk"
        return FileResponse(enc_path, filename=filename, media_type="application/octet-stream")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/restore")
async def restore_database(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    from database import DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME
    if current_user.rol != 'admin':
        raise HTTPException(status_code=403, detail="Solo administradores pueden restaurar backups.")
    
    if not file.filename.endswith(".apbk"):
        raise HTTPException(status_code=400, detail="Formato de archivo invǭlido. Debe ser un backup de Apollo (.apbk).")
        
    try:
        psql = get_psql_path()
        env = os.environ.copy()
        env['PGPASSWORD'] = DB_PASSWORD
        
        encrypted_data = await file.read()
        
        try:
            raw_data = cipher_suite.decrypt(encrypted_data)
        except Exception:
            raise HTTPException(status_code=400, detail="El archivo estǭ corrupto o la clave no coincide.")
        
        fd_raw, raw_path = tempfile.mkstemp(suffix=".sql")
        os.close(fd_raw)
        
        with open(raw_path, "wb") as f_out:
            f_out.write(raw_data)
            
        cmd = [
            psql,
            "-h", DB_HOST,
            "-p", str(DB_PORT),
            "-U", DB_USER,
            "-d", DB_NAME,
            "-f", raw_path
        ]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        os.remove(raw_path)
        
        if result.returncode != 0:
            raise Exception(f"La restauracin fall (psql error): {result.stderr}")
            
        return {"status": "ok", "message": "Base de datos restaurada con Ǹxito."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
