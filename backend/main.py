import os
import sys
# Asegurar que el directorio de este script estÃ© en el sys.path para resoluciÃ³n robusta de paquetes ('core', 'models', etc.)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import logging.handlers

# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LOGGING ESTRUCTURADO
# - Archivo rotativo diario, retenciÃ³n 30 dÃ­as
# - Formato: timestamp | level | mÃ³dulo | mensaje
# - Salida simultÃ¡nea a consola y archivo
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
    backupCount=5,              # Retener 5 archivos histÃ³ricos (50 MB total max)
    encoding="utf-8"
)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.WARNING)  # Solo errores en archivo â€” INFO va a consola

# Handler de consola (INFO+ para seguimiento en tiempo real)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Logger raÃ­z de la aplicaciÃ³n
logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, console_handler])

# Silenciar loggers ruidosos de librerÃ­as externas
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.ERROR)   # Silencia cada request HTTP
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("websockets").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("apollo")
logger.info("=== ApolloSupport Backend iniciando ===")

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Dict, Any, Optional
from jose import JWTError, jwt
from datetime import datetime
import shutil
import asyncio
import uuid
from datetime import timedelta

from database import engine, Base, get_db, SessionLocal
import models
import schemas
import auth
import httpx
from core.erp_bridge import ERPBridge

# Instanciamos la AplicaciÃ³n FastAPI
app = FastAPI(
    title="ApolloSupport API",
    description="Motor Central Seguro para Master IS.",
    version="1.0.0",
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
    logger.info("APOLLO BACKEND V3.1 - CON SOPORTE HQ ACTIVADO")
    logger.info("="*60)
    try:
        print("\n" + "="*60)
        print("APOLLO BACKEND V3.1 - CON SOPORTE HQ ACTIVADO")
        print("="*60 + "\n")
    except Exception:
        pass

@app.get("/api/hq-test")
def test_hq_endpoint():
    return {
        "status": "OK", 
        "mensaje": "El nuevo backend esta corriendo perfectamente!", 
        "version": "3.1-HQ"
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

# ConfiguraciÃ³n Global
API_URL = "http://localhost:8001/api"

# Asegurar directorios base
for d in ["temp_files", "uploads", "temp_files/uploads"]:
    if not os.path.exists(d): 
        os.makedirs(d)

app.mount("/api/temp", StaticFiles(directory="temp_files"), name="static_temp")
app.mount("/uploads", StaticFiles(directory="uploads"), name="static_uploads")

models.Base.metadata.create_all(bind=engine)

async def server_ping_loop(device_id: int):
    """ Mantiene viva la conexiÃ³n WebSocket enviando un ping cada 20 segundos. """
    while True:
        await asyncio.sleep(20)
        try:
            # send_json_safe ya maneja el lock y errores
            success = await manager.send_json_safe(device_id, {"type": "ping"})
            if not success: break
        except Exception: break


async def periodic_viewer_cleanup():
    logger.info("[CLEANUP] Tarea periÃ³dica de monitoreo de espectadores iniciada.")
    while True:
        try:
            await asyncio.sleep(4.0)
            now = datetime.utcnow()
            stale_threshold = 8.0
            
            # Limpiar espectadores inactivos para todos los dispositivos activos
            for device_id in list(manager.active_connections.keys()):
                if device_id in manager.device_viewers:
                    viewers_dict = manager.device_viewers[device_id]
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
                        
                        # Notificar al cliente con la lista actualizada de tÃ©cnicos activos (que puede estar vacÃ­a)
                        await manager.send_json_safe(device_id, {
                            "type": "active_technicians",
                            "technicians": active_viewers
                        })
                        manager.last_viewer_notification[device_id] = now

                    # AutoliberaciÃ³n de PC en DB si no quedan espectadores activos (ni standard ni HQ)
                    # y estÃ¡ marcada como ocupada
                    if len(viewers_dict) == 0 and not manager.has_hq_viewers(device_id):
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
        except Exception as e:
            logger.error("[CLEANUP ERROR] Error en limpieza periÃ³dica de espectadores: {e}")

# Resetear estado online de dispositivos al iniciar el servidor
@app.on_event("startup")
def startup_event():
    # Iniciar tareas asÃ­ncronas periÃ³dicas
    asyncio.get_event_loop().create_task(periodic_viewer_cleanup())
    asyncio.get_event_loop().create_task(periodic_orphan_session_cleanup())

    db = SessionLocal()
    try:
        db.query(models.CentinelaDevice).update({
            models.CentinelaDevice.is_online: False,
            models.CentinelaDevice.current_technician_id: None,
            models.CentinelaDevice.session_start: None
        })
        db.commit()
        logger.info("[STARTUP] Reset de estado online y liberaciÃ³n de dispositivos completado.")

        # Cerrar sesiones huÃ©rfanas que quedaron abiertas del reinicio anterior
        _close_orphaned_sessions(db)
    except Exception as e:
        logger.error("[STARTUP] Error al resetear estados de dispositivos: %s", e)
    finally:
        db.close()


def _close_orphaned_sessions(db: Session):
    """
    Cierra SupportSessions cuyo end_time es NULL y el dispositivo no se vio
    en los Ãºltimos 10 minutos. Esto cubre el caso en que el tÃ©cnico cierra
    el navegador sin hacer clic en 'Cerrar ConexiÃ³n'.
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
            # Si el dispositivo no existe o no se vio en 10 min â†’ cerrar sesiÃ³n
            if device is None or (device.last_seen and device.last_seen < cutoff):
                s.end_time = datetime.utcnow()
                closed += 1

        if closed:
            db.commit()
            logger.warning("[ORPHAN] Cerradas %d sesiones huÃ©rfanas al iniciar.", closed)
    except Exception as e:
        logger.error("[ORPHAN] Error cerrando sesiones huÃ©rfanas: %s", e)


async def periodic_orphan_session_cleanup():
    """
    Tarea periÃ³dica que cierra sesiones de soporte huÃ©rfanas cada 5 minutos.
    Una sesiÃ³n es huÃ©rfana si end_time=NULL y el agente no se vio en 10+ minutos.
    """
    logger.info("[ORPHAN] Tarea de limpieza de sesiones huÃ©rfanas iniciada.")
    while True:
        await asyncio.sleep(300)  # Cada 5 minutos
        db = SessionLocal()
        try:
            _close_orphaned_sessions(db)
        except Exception as e:
            logger.error("[ORPHAN] Error en ciclo periÃ³dico: %s", e)
        finally:
            db.close()


# ==========================================
# CONFIGURACIÃ“N DE SEGURIDAD (OAUTH2)
# ==========================================
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/token")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """ 
    Filtro de Seguridad: Revisa si el usuario trajo su llave (JWT).
    Se usa inyectÃ¡ndolo en las rutas que queramos proteger.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales invÃ¡lidas o sesiÃ³n expirada.",
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
    """ EnvÃ­a una notificaciÃ³n Push a travÃ©s de los servidores de Expo. """
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
    
    # Comprobamos la clave encriptada cruzÃ¡ndola con la tipeada
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseÃ±a incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Actualizar estado de login
    user.is_online = True
    user.last_login = datetime.utcnow()
    user.last_activity = datetime.utcnow()
    user.current_page = "Dashboard"
    user.current_task = "IniciÃ³ sesiÃ³n"
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
    """ Retorna una lista pÃºblica de nombres y correos de los usuarios activos para sugerencias de autocompletado """
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
    db_client = models.Client(**cliente.model_dump())
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    return db_client

@app.get("/api/clients/", response_model=List[schemas.ClientOut], tags=["Clientes"])
def obtener_clientes(skip: int = 0, limit: int = 5000, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Client).options(joinedload(models.Client.devices).joinedload(models.CentinelaDevice.technician)).order_by(models.Client.codigo.asc().nulls_last(), models.Client.razon_social.asc()).offset(skip).limit(limit).all()

@app.post("/api/clients/sync", tags=["Clientes"])
def sincronizar_clientes_dbf(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Sincroniza los clientes desde el archivo CLIGESCO.DBF local. """
    try:
        from sync_dbf_to_postgres import sync_data
        sync_data()
        return {"status": "success", "message": "SincronizaciÃ³n de clientes DBF completada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error durante la sincronizaciÃ³n: {str(e)}")

@app.put("/api/clients/{client_id}", response_model=schemas.ClientOut, tags=["Clientes"])
def actualizar_cliente(client_id: int, cliente: schemas.ClientCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    for key, value in cliente.model_dump().items():
        setattr(db_client, key, value)
    
    db.commit()
    db.refresh(db_client)
    return db_client

@app.delete("/api/clients/{client_id}", tags=["Clientes"])
def eliminar_cliente(client_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    db_client = db.query(models.Client).filter(models.Client.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    
    db_client.activo = not db_client.activo
    db.commit()
    return {"status": "success", "activo": db_client.activo}

# ==========================================
# RUTAS DE INTEGRACIÃ“N ERP (XaGesApi)
# ==========================================
@app.get("/api/erp/clientes/{client_id_or_code}/saldo", tags=["IntegraciÃ³n ERP"])
def obtener_saldo_erp_real(client_id_or_code: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """
    Obtiene el saldo real del cliente directamente desde el ERP local en tiempo real y actualiza el cachÃ© de PostgreSQL.
    """
    # Intentar buscar primero por ID de cliente, de lo contrario buscar por su cÃ³digo ERP (CCLIFAC) o cÃ³digo de licencias (CCOD)
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
        raise HTTPException(status_code=400, detail="El cliente seleccionado no posee un cÃ³digo de cliente de facturaciÃ³n del ERP (CCLIFAC) asociado.")
        
    try:
        # Obtener saldo real usando el conector de Harbour por CCLIFAC
        saldo_real = ERPBridge.get_client_balance(db_client.cclifac)
        
        # Sincronizar el saldo real de vuelta en PostgreSQL
        db_client.saldo = saldo_real
        db.commit()
        
        return {
            "cliente_id": db_client.id,
            "codigo": db_client.codigo,
            "cclifac": db_client.cclifac,
            "razon_social": db_client.razon_social,
            "saldo_local": db_client.saldo,
            "saldo_real_erp": saldo_real
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error consultando el motor ERP de Harbour: {str(e)}")

@app.get("/api/erp/clientes/{client_id_or_code}/extracto", tags=["IntegraciÃ³n ERP"])
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
        raise HTTPException(status_code=400, detail="El cliente seleccionado no posee un cÃ³digo de cliente de facturaciÃ³n del ERP (CCLIFAC) asociado.")
        
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

@app.get("/api/erp/comprobantes/{hash_fac}/pdf", tags=["IntegraciÃ³n ERP"])
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
# RUTAS DE LICENCIAS ERP (CONEXIÃ“N MYSQL)
# ==========================================
import erp_licensing

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
        raise HTTPException(status_code=400, detail="Faltan parÃ¡metros obligatorios.")
        
    try:
        return erp_licensing.deactivate_terminal_node(serial, t_id_enc, t_user_enc, t_path_enc)
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

# ==========================================
# RUTAS DE AREAS (NUEVO)
# ==========================================
@app.get("/api/areas", response_model=List[schemas.AreaOut], tags=["ConfiguraciÃ³n"])
def obtener_areas(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    return db.query(models.Area).all()

# ==========================================
# RUTAS DE USUARIOS / ABM / PERFIL (NUEVO)
# ==========================================
@app.get("/api/users", response_model=List[schemas.UserOut], tags=["Usuarios"])
def obtener_usuarios(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Retorna todos los usuarios ordenados por si estÃ¡n online primero """
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
        raise HTTPException(status_code=400, detail="El email ya estÃ¡ registrado.")
        
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
        
    # El usuario comÃºn no puede cambiarse el rol ni el estado activo
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
    """ Actualiza el estado en lÃ­nea, tarea actual y pÃ¡gina actual del usuario logueado en tiempo real """
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
    return {"status": "success", "message": "SesiÃ³n cerrada correctamente."}

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
        # Default a 'AtenciÃ³n al Cliente'
        area = db.query(models.Area).filter(models.Area.nombre == "AtenciÃ³n al Cliente").first()
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
    
    # Crear la intervenciÃ³n
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
    
    # Si es una transferencia, actualizamos el Ã¡rea del ticket
    if intervencion.tipo == "transferencia" and to_area_id:
        ticket.current_area_id = to_area_id
    
    db.add(db_intervention)
    db.commit()
    db.refresh(db_intervention)
    return db_intervention

@app.post("/api/upload", tags=["Utilidades"])
async def upload_file(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    """ Sube un archivo (audio, imagen, doc) al servidor para adjuntar a una intervenciÃ³n. """
    temp_dir = "temp_files/uploads"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)
    
    file_path = os.path.join(temp_dir, f"{datetime.now().timestamp()}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"url": f"/api/temp/uploads/{os.path.basename(file_path)}", "filename": file.filename}

# Integrar StaticFiles para las subidas temporales (ya montado vÃ­a /api/temp, pero damos ruta directa)
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
    client_modules = client.modulos if client else "Base, FacturaciÃ³n"
    client_version = client.version_apollo if client else "Desconocida"
    
    # Historial de intervenciones
    historial = []
    for inv in ticket.intervenciones:
        rol_usuario = inv.usuario.rol if inv.usuario else "Sistema"
        nombre_usuario = inv.usuario.full_name if inv.usuario else "Sistema"
        destino_msg = f" -> Transferencia a {inv.area_destino.nombre}" if inv.area_destino else ""
        mensaje_texto = inv.mensaje if inv.mensaje else "[Mensaje VacÃ­o u Adjunto]"
        historial.append(
            f"[{inv.fecha_creacion.strftime('%Y-%m-%d %H:%M')}] {nombre_usuario} ({rol_usuario}){destino_msg}: {mensaje_texto}"
        )
    
    historial_texto = "\n".join(historial) if historial else "No hay comentarios previos."
    
    prompt = f"""
ActÃºa como "Apollo AI Copilot", el arquitecto principal de soluciones de Apollo ERP (Sistemas de GestiÃ³n Comercial GesCom basados en bases de datos FoxPro/DBF, impresoras fiscales, spoolers de impresiÃ³n de Windows, y terminales de red local).

Tu objetivo es analizar un ticket de soporte de un cliente de Apollo ERP para ayudar al personal de AtenciÃ³n al Cliente y mejorar la comunicaciÃ³n con el Ã¡rea de Desarrollo.

=== INFORMACIÃ“N DEL CLIENTE ===
Empresa: {client_name}
VersiÃ³n de Apollo ERP: {client_version}
MÃ³dulos Habilitados: {client_modules}

=== DETALLE DEL TICKET ===
Asunto: {ticket.asunto}
DescripciÃ³n Original: {ticket.descripcion}
Estado Actual: {ticket.estado}
Prioridad: {ticket.prioridad}

=== HISTORIAL DE INTERVENCIONES ===
{historial_texto}

=== INSTRUCCIONES DE RESPUESTA ===
Genera una respuesta en formato JSON estrictamente vÃ¡lido que contenga la clave "analysis". El valor de "analysis" debe ser un texto formateado con Markdown claro, premium y elegante, estructurado exactamente en los siguientes 4 bloques:

1. ðŸ” **DiagnÃ³stico y Causa RaÃ­z Estructurada**: Analiza el problema considerando si es de red local, permisos de Windows, tablas de FoxPro (.dbf/.cdx corruptas, necesidad de reindexar), Spooler de impresiÃ³n, o un bug del sistema.
2. ðŸ› ï¸ **Plan de AcciÃ³n de Soporte**: Pasos paso a paso prÃ¡cticos para que el agente de soporte intente solucionar el problema de inmediato en la PC del cliente de forma remota (por ejemplo, reiniciar spooler, limpiar temporales, revisar registros de Windows, etc.).
3. ðŸ’» **Pase TÃ©cnico Consolidado para Desarrollo**: Un informe sÃºper formal y estructurado para el sector de ProgramaciÃ³n si el ticket debe ser derivado. Incluye: Tablas involucradas estimadas (ej: FACTURAS.DBF, HISTORIA\\ULTACT.DBF, etc.), comportamiento esperado, comportamiento observado, y lÃ­neas de cÃ³digo o validaciones lÃ³gicas que sospechas que fallan.
4. âœ‰ï¸ **Borrador de Respuesta EmpÃ¡tica para el Cliente**: Un borrador cordial, tranquilizador y profesional dirigido al cliente (menciona a "{client_name}" y saluda como el Equipo de Soporte de Apollo).

AsegÃºrate de que la salida sea un objeto JSON vÃ¡lido con el campo "analysis" conteniendo todo el Markdown para evitar problemas de parseo.
"""

    gemini_key = os.getenv("GEMINI_API_KEY")
    if not gemini_key:
        # Modo de demostraciÃ³n de sÃºper alta calidad con anÃ¡lisis dinÃ¡mico adaptado al ticket actual
        # De esta forma, incluso sin API Key, el personal recibe una herramienta sÃºper Ãºtil.
        sintomas_especificos = ""
        dbfs_sospechosas = "TABLAS.DBF, INDICES.CDX"
        if "imp" in ticket.asunto.lower() or "impr" in ticket.asunto.lower() or "factur" in ticket.asunto.lower() or "ticket" in ticket.asunto.lower():
            sintomas_especificos = "Falla de comunicaciÃ³n con controlador fiscal o impresora tÃ©rmica. El spooler de Windows suele acumular trabajos corruptos."
            dbfs_sospechosas = "FACTURAS.DBF, COMPROBANTES.DBF"
        elif "usuario" in ticket.asunto.lower() or "permis" in ticket.asunto.lower() or "log" in ticket.asunto.lower():
            sintomas_especificos = "Conflicto de autenticaciÃ³n o bloqueo de archivos de sesiÃ³n de usuario en red compartida."
            dbfs_sospechosas = "USERG.DBF, ACCESO.DBF"
        else:
            sintomas_especificos = "Inconsistencia lÃ³gica de datos o Ã­ndice FoxPro (.CDX) desincronizado por desconexiÃ³n de terminal de red."
            dbfs_sospechosas = "HISTORIA\\ULTACT.DBF, CLIENTES.DBF"

        analysis_mock = f"""### ðŸ¤– AnÃ¡lisis Copiloto IA (Modo DemostraciÃ³n)
> [!NOTE]
> Para activar la Inteligencia Artificial generativa real con Gemini, define `GEMINI_API_KEY` en tu archivo `.env` del backend.

#### ðŸ” 1. DiagnÃ³stico y Posible Causa RaÃ­z
* **SintomatologÃ­a:** El ticket titulado **"{ticket.asunto}"** para la empresa **{client_name}** indica un conflicto operativo que afecta a los mÃ³dulos activos: `{client_modules}`.
* **Causa Estimada:** {sintomas_especificos}
* **Comportamiento Observado:** Error en tiempo de ejecuciÃ³n o pantalla bloqueada debido a bloqueo exclusivo de archivos en red local (SMB v2/v3).

#### ðŸ› ï¸ 2. Plan de AcciÃ³n de Soporte (AtenciÃ³n al Cliente)
1. **Comandos Remotos:** Utiliza las herramientas remotas integradas en este panel para acelerar el soporte:
   * Haz clic en **"Reiniciar Spooler"** si se trata de un problema de impresiÃ³n atascada.
   * Haz clic en **"Limpiar Temporales"** para liberar archivos de cachÃ© de FoxPro en la mÃ¡quina cliente (`%TEMP%`).
2. **Chequeo de Archivos Bloqueados:** Accede al servidor del cliente y verifica si el archivo DBF de interÃ©s estÃ¡ retenido por alguna sesiÃ³n inactiva.

#### ðŸ’» 3. Pase TÃ©cnico Consolidado para Desarrollo
* **Origen de DerivaciÃ³n:** Sector AtenciÃ³n al Cliente -> Desarrollo.
* **Componentes de InterÃ©s:**
  * **Tablas de datos sospechosas:** `{dbfs_sospechosas}` en la ruta de tablas del cliente.
  * **Comportamiento Esperado:** Flujo lÃ³gico continuo sin colisiones transaccionales de FoxPro.
  * **Sugerencia de CÃ³digo:** Verificar si hay sentencias `SET EXCLUSIVE OFF` faltantes o manejo de reintentos `LOCK()` en bloqueos de registros.

#### âœ‰ï¸ 4. Borrador de Respuesta EmpÃ¡tica para el Cliente
*"Estimado cliente de **{client_name}**, buenas tardes. Le saluda el equipo de Soporte de Apollo. Hemos registrado su reporte sobre: **'{ticket.asunto}'**. Nuestros analistas ya estÃ¡n validando la situaciÃ³n y nos contactaremos a la brevedad para acceder de forma remota o aplicar la correcciÃ³n necesaria en sus terminales. Agradecemos enormemente su paciencia."*
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
                return {"analysis": parsed_res.get("analysis", "No se obtuvo anÃ¡lisis del modelo."), "confidence": 0.95}
            else:
                return {
                    "analysis": f"âš ï¸ Error en API de Gemini (CÃ³digo {response.status_code}): {response.text}",
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
        # device_viewers[device_id] = {user_id: (user_name, last_seen_datetime)}
        self.device_viewers: Dict[int, Dict[int, tuple]] = {}
        # last_viewer_notification[device_id] = last notification sent datetime
        self.last_viewer_notification: Dict[int, datetime] = {}
        # â”€â”€â”€ VIEWER WEBSOCKETS (estÃ¡ndar) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # viewer_connections[device_id] = {ws_id: WebSocket}
        self.viewer_connections: Dict[int, Dict[str, WebSocket]] = {}
        self.viewer_write_locks: Dict[str, asyncio.Lock] = {}  # lock por ws_id individual
        # â”€â”€â”€ HQ VIEWER WEBSOCKETS (binary H.264) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        # hq_viewer_connections[device_id] = {ws_id: WebSocket}
        # Forward raw H.264/fMP4 bytes directamente del agente al browser (MSE).
        # Sistema completamente independiente del path estÃ¡ndar (no toca nada existente).
        self.hq_viewer_connections: Dict[int, Dict[str, WebSocket]] = {}
        self.hq_viewer_write_locks: Dict[str, asyncio.Lock] = {}

    async def push_to_viewers(self, device_id: int, payload: dict):
        """EnvÃ­a un mensaje JSON a todos los viewers estÃ¡ndar conectados a este device."""
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

    async def connect(self, device_id: int, client_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[device_id] = websocket
        if client_id not in self.active_clients:
            self.active_clients[client_id] = []
        if device_id not in self.active_clients[client_id]:
            self.active_clients[client_id].append(device_id)

    def disconnect(self, device_id: int, client_id: int):
        if device_id in self.active_connections:
            del self.active_connections[device_id]
        if client_id in self.active_clients:
            if device_id in self.active_clients[client_id]:
                self.active_clients[client_id].remove(device_id)
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
        """ EnvÃ­a un mensaje JSON a un dispositivo de forma segura y secuencial (evita colisiones concurrentes). """
        if device_id not in self.active_connections:
            return False
        
        if device_id not in self.write_locks:
            self.write_locks[device_id] = asyncio.Lock()
            
        async with self.write_locks[device_id]:
            try:
                await self.active_connections[device_id].send_json(data)
                return True
            except Exception as e:
                logger.error("[WS ERROR] Error en envio seguro")
                return False

    async def send_command(self, client_id: int, command: str):
        """ EnvÃ­a un comando arbitrario al agente Centinela vÃ­a WebSocket de forma segura. """
        return await self.send_json_safe(client_id, {
            "type": "run_command",
            "command": command
        })

    async def push_frame_to_viewers(self, device_id: int, frame_data: str, delta: dict = None):
        """
        EnvÃ­a el frame reciÃ©n llegado del agente a TODOS los tÃ©cnicos que tienen
        abierto un WebSocket de vista en tiempo real para este dispositivo.
        Opera de forma no-bloqueante: si un viewer falla, se elimina silenciosamente.
        DIRTY_RECT: si delta estÃ¡ presente, se reenvÃ­a al viewer para composiciÃ³n.
        """
        if device_id not in self.viewer_connections:
            return

        # DIRTY_RECT_START: incluir delta en payload si el agente lo enviÃ³
        payload = {"type": "frame", "frame": frame_data}
        if delta:
            payload["delta"] = delta
        # DIRTY_RECT_END
        dead_viewers = []

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
            self.viewer_connections[device_id].pop(ws_id, None)
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

    # â”€â”€ HQ VIEWER MANAGEMENT â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    async def push_hq_chunk_to_viewers(self, device_id: int, chunk: bytes):
        """Forward binary H.264/fMP4 chunk del agente a todos los viewers HQ.
        Opera 100% en binario â€” sin base64, sin JSON. Cero overhead.
        """
        if device_id not in self.hq_viewer_connections:
            return
        dead = []
        for ws_id, ws in list(self.hq_viewer_connections[device_id].items()):
            lock = self.hq_viewer_write_locks.get(ws_id)
            if lock is None:
                lock = asyncio.Lock()
                self.hq_viewer_write_locks[ws_id] = lock
            try:
                async with lock:
                    await ws.send_bytes(chunk)
            except Exception:
                dead.append(ws_id)
        for ws_id in dead:
            self.hq_viewer_connections[device_id].pop(ws_id, None)
            self.hq_viewer_write_locks.pop(ws_id, None)
            logger.info("[VIEWER] Viewer HQ %s desconectado de device %d", ws_id, device_id)


manager = ConnectionManager()


@app.websocket("/api/ws/viewer/{device_id}")
async def websocket_viewer(websocket: WebSocket, device_id: int, token: str = Query("")):
    """
    WebSocket de PUSH de video para los navegadores de los tÃ©cnicos.
    - El backend empuja frames en cuanto los recibe del agente (cero polling).
    - El tÃ©cnico puede enviar mensajes de heartbeat para mantener la conexiÃ³n viva.
    - Usa el JWT por query param porque los navegadores no permiten headers en WS nativos.
    """
    # Validar token JWT con log de error detallado
    try:
        # Agregamos 60s de margen (leeway) por si el reloj del server y cliente estan desfasados
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM], options={"leeway": 60})
        email = payload.get("sub")
        if not email:
            logger.warning(f"[WS] Viewer rechazo conexión de device {device_id}: token sin 'sub'")
            await websocket.close(code=4001)
            return
    except JWTError as e:
        logger.warning(f"[WS] Viewer rechazo conexión de device {device_id} por JWTError: {e}")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    ws_id = str(uuid.uuid4())
    manager.add_viewer(device_id, ws_id, websocket)

    # Notificar al agente que hay un tÃ©cnico mirando â†’ activa HAS_ACTIVE_VIEWER en el agente
    # Sin esto, el agente nuevo nunca envÃ­a frames (espera este mensaje para empezar)
    await manager.send_json_safe(device_id, {
        "type": "technician_joined",
        "name": email
    })
    # TambiÃ©n actualizar active_technicians para compatibilidad con agentes viejos
    await manager.send_json_safe(device_id, {
        "type": "active_technicians",
        "technicians": [email]
    })

    # Enviar el Ãºltimo frame disponible inmediatamente al conectar (no esperar al prÃ³ximo)
    last_frame = manager.client_frames.get(device_id)
    if last_frame:
        try:
            await websocket.send_json({"type": "frame", "frame": last_frame})
        except Exception:
            pass

    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive(), timeout=60.0)
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
                        "set_stream_params",
                    }
                    if cmd_type in FORWARDED_CMDS:
                        await manager.send_json_safe(device_id, cmd)
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
        # Si ya no queda ningÃºn viewer mirando, notificar al agente para que deje de capturar
        remaining = len(manager.viewer_connections.get(device_id, {}))
        if remaining == 0:
            await manager.send_json_safe(device_id, {
                "type": "active_technicians",
                "technicians": []
            })


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# VIEWER HQ WebSocket â€” Alto Rendimiento (H.264 binario va MSE)
# Completamente independiente del sistema estÃ¡ndar. No toca nada existente.
# El agente envÃ­a chunks binarios H.264/fMP4 que se forwardean aquÃ­ sin modificaciÃ³n.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@app.websocket("/api/ws/viewer/{device_id}/hq")
async def websocket_viewer_hq(websocket: WebSocket, device_id: int, token: str = Query("")):
    """WebSocket de PUSH de video H.264 (Alto Rendimiento).
    El browser usa MediaSource Extensions para decode hardware en tiempo real.
    El agente envÃ­a binary fMP4 chunks vÃ­a su WS normal; el backend los forwarda aquÃ­.
    """
    try:
        # 60s leeway para evitar rechazos por clock-drift
        payload = jwt.decode(token, auth.SECRET_KEY, algorithms=[auth.ALGORITHM], options={"leeway": 60})
        if not payload.get("sub"):
            logger.warning(f"[HQ] Viewer HQ rechazo conexión de device {device_id}: token sin 'sub'")
            await websocket.close(code=4001); return
    except JWTError as e:
        logger.warning(f"[HQ] Viewer HQ rechazo conexión de device {device_id} por JWTError: {e}")
        await websocket.close(code=4001); return

    await websocket.accept()
    ws_id = str(uuid.uuid4())
    manager.add_hq_viewer(device_id, ws_id, websocket)
    logger.info("[HQ] Viewer HQ conectado: device=%d ws=%s", device_id, ws_id)

    # Notificar al agente que hay un viewer HQ (para que inicie el stream ffmpeg)
    await manager.send_json_safe(device_id, {"type": "start_hq", "device_id": device_id})

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
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
        # Si no quedan viewers HQ, decirle al agente que detenga ffmpeg
        if not manager.has_hq_viewers(device_id):
            await manager.send_json_safe(device_id, {"type": "stop_hq"})




# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# AGENTE HQ WebSocket â€” recibe chunks binarios H.264 del agente (endpoint separado)
# El agente abre UNA segunda conexiÃ³n WS aquÃ­ cuando HQ se activa.
# Sin tocar /api/ws/centinela/{id} que queda 100% intacto.
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Se eliminÃ³ la ruta separada de HQ para evitar bloqueos de NGINX


@app.websocket("/api/ws/centinela/{client_id}")
async def websocket_centinela(websocket: WebSocket, client_id: int, device_name: str = "Desconocido", license_key: str = Query(""), hq: str = Query(None), device_id: int = Query(None)):
    db_init = SessionLocal()
    try:
        if hq == "1":
            target_device_id = device_id or client_id
            try:
                device = db_init.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == target_device_id).first()
                if not device:
                    await websocket.close(code=4001)
                    return
                if license_key:
                    lic = db_init.query(models.License).filter(models.License.license_key == license_key).first()
                    if not lic or (device.client_id is not None and device.client_id != lic.client_id):
                        await websocket.close(code=4001)
                        return
            except Exception: pass
            finally:
                db_init.close()
                db_init = None

            await websocket.accept()
            logger.info("[HQ-AGENT] Agente HQ conectado: device=%d", target_device_id)
            try:
                while True:
                    try:
                        chunk = await asyncio.wait_for(websocket.receive_bytes(), timeout=30.0)
                        if chunk:
                            asyncio.create_task(manager.push_hq_chunk_to_viewers(target_device_id, chunk))
                    except asyncio.TimeoutError:
                        try:
                            await websocket.send_text("ping")
                        except Exception:
                            break
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.debug("[HQ-AGENT] Cerrado: %s", e)
            finally:
                logger.info("[HQ-AGENT] Agente HQ desconectado: device=%d", target_device_id)
            return

        # --- Flujo EstÃ¡ndar (No HQ) ---
        logger.info("[WS] Nueva conexion entrante client_id=%s, device=%s", client_id, device_name)
        
        is_pending = False
        lic = None
        if not license_key:
            is_pending = True
        else:
            lic = db_init.query(models.License).filter(models.License.license_key == license_key).first()
            if not lic or not lic.is_active or (lic.expiry_date and lic.expiry_date < datetime.utcnow()):
                is_pending = True

        if not is_pending and lic:
            client_id = lic.client_id
            # Validar cupo
            devices_count = db_init.query(models.CentinelaDevice).filter(models.CentinelaDevice.client_id == lic.client_id).count()
            existing_device = db_init.query(models.CentinelaDevice).filter(
                models.CentinelaDevice.client_id == lic.client_id, 
                models.CentinelaDevice.device_name == device_name
            ).first()
            
            if not existing_device and devices_count >= lic.max_devices:
                await websocket.accept()
                await websocket.send_text(json.dumps({"type": "error", "message": "LÃ­mite de dispositivos excedido"}))
                await websocket.close(code=1008)
                return
        else:
            client_id = None

        # Buscar o registrar
        if is_pending:
            # Si es pendiente, usamos el client_id (que es el ID aleatorio del agente) 
            # como discriminador secundario para evitar colisiones por nombre de PC duplicado.
            device = db_init.query(models.CentinelaDevice).filter(
                models.CentinelaDevice.device_name == device_name,
                (models.CentinelaDevice.client_id == client_id) | (models.CentinelaDevice.client_id == None)
            ).order_by(models.CentinelaDevice.id.desc()).first()
        else:
            device = db_init.query(models.CentinelaDevice).filter(
                models.CentinelaDevice.client_id == client_id,
                models.CentinelaDevice.device_name == device_name
            ).first()

        if not device:
            device = models.CentinelaDevice(client_id=client_id, device_name=device_name, is_online=True)
            db_init.add(device)
            db_init.commit()
            db_init.refresh(device)
        else:
            device.is_online = True
            device.last_seen = datetime.utcnow()
            db_init.commit()

        device_id = device.id
    except Exception as e:
        logger.error("[WS-INIT] Error: %s", e)
        return
    finally:
        if db_init is not None:
            try:
                db_init.close()
            except Exception:
                pass
    
    try:
        # Loop principal sin DB persistente
        ping_task = asyncio.create_task(server_ping_loop(device_id))
        await manager.connect(device_id, client_id, websocket)

        try:
            while True:
                try:
                    # Timeout ampliado a 45s: tolera picos de CPU/red sin desconectar prematuramente
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=45.0)
                except asyncio.TimeoutError:
                    logger.warning("[HEARTBEAT] Sin senales del dispositivo. Forzando desconexion.")
                    raise WebSocketDisconnect()


                try:
                    if data["type"] in ["screen_frame", "video_frame"]:
                        frame_data = data.get("image") or data.get("data")
                        # DIRTY_RECT_START: extraer delta si el agente lo incluyÃ³
                        delta = data.get("delta")  # None si es frame completo
                        # DIRTY_RECT_END
                        # Guardar en RAM como antes (fallback para el endpoint HTTP)
                        # NOTA: siempre guardamos el frame completo para HTTP polling
                        if not delta:  # Solo sobreescribir cache con frames completos
                            manager.client_frames[device_id] = frame_data
                        # âœ” PUSH INMEDIATO a todos los viewers WS conectados
                        asyncio.create_task(manager.push_frame_to_viewers(device_id, frame_data, delta))

                    elif data["type"] == "chat_message":
                        msg = data.get("message")
                        db_loop = SessionLocal()
                        try:
                            # Buscar el device actual para obtener tÃ©cnico y chat
                            dev = db_loop.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
                            new_chat = models.RemoteChat(
                                device_id=device_id,
                                technician_id=dev.current_technician_id if dev else None,
                                message=msg,
                                sender_type='client'
                            )
                            db_loop.add(new_chat)
                            db_loop.commit()
                            logger.info("[CHAT] Mensaje recibido del cliente")
                        finally:
                            db_loop.close()

                    elif data["type"] == "clipboard_sync":
                        text = data.get("text", "")
                        manager.client_clipboard[device_id] = text
                        logger.debug("[CLIPBOARD] Datos recibidos")

                    elif data["type"] == "session_list":
                        # Agente reporta sesiones de Windows activas
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

                        # --- ACTUALIZAR CONTRASEÃ‘A DE SOPORTE Y ULTIMA ACTUALIZACION ERP EN DB ---
                        if "remote_password" in telemetry or "last_erp_update" in telemetry:
                            db_pass = SessionLocal()
                            try:
                                dev = db_pass.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
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
                                    db_pass.commit()
                            except Exception as db_err:
                                logger.error("[DB] Error guardando en base de datos")
                                db_pass.rollback()
                            finally:
                                db_pass.close()

                        # --- ACTUALIZAR USUARIO/PASSWORD DE WINDOWS REPORTADO POR EL AGENTE ---
                        win_user = telemetry.get("windows_user") or telemetry.get("windows_username") or telemetry.get("win_user")
                        win_pass = telemetry.get("windows_password") or telemetry.get("windows_pass") or telemetry.get("win_pass")

                        if win_user or win_pass:
                            db_win = SessionLocal()
                            try:
                                dev = db_win.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
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
                                    db_win.commit()
                            except Exception as db_err:
                                logger.error("[DB] Error guardando en base de datos")
                                db_win.rollback()
                            finally:
                                db_win.close()

                        # --- PROACTIVE ALERT LOGIC ---
                        alerts = []
                        db_alert = SessionLocal()
                        try:
                            if telemetry.get("cpu", 0) > 85:
                                msg = f"CPU CrÃ­tico ({device_name}): {telemetry['cpu']}%"
                                alerts.append(msg)
                                db_alert.add(models.Alert(client_id=client_id, mensaje=msg, severidad="critica"))
                            if telemetry.get("ram", 0) > 90:
                                msg = f"RAM Saturada ({device_name}): {telemetry['ram']}%"
                                alerts.append(msg)
                                db_alert.add(models.Alert(client_id=client_id, mensaje=msg, severidad="critica"))

                            if alerts:
                                db_alert.commit()
                                users_with_token = db_alert.query(models.User).filter(models.User.expo_push_token != None).all()
                                for u in users_with_token:
                                    asyncio.create_task(send_push_notification(u.expo_push_token, f"ALERTA {device_name}", "\n".join(alerts)))
                        finally:
                            db_alert.close()

                        manager.client_alerts[device_id] = alerts

                    elif data["type"] in ["file_list", "file_content", "dir_list"]:
                        manager.client_files[device_id] = data

                    elif data["type"] in ["pong", "ping_ack"]:
                        # Heartbeat: el agente respondiÃ³ al ping del servidor, estÃ¡ vivo
                        db_pong = SessionLocal()
                        try:
                            dev = db_pong.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
                            if dev:
                                dev.last_seen = datetime.utcnow()
                                db_pong.commit()
                        finally:
                            db_pong.close()

                except WebSocketDisconnect:
                    raise
                except Exception as msg_err:
                    logger.info(
                        "[WS] Error procesando mensaje %r de %r: %s",
                        data.get("type"),
                        device_name,
                        msg_err,
                    )
                    # No romper el loop por errores en mensajes individuales
        finally:
            ping_task.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Error WS: {e}")
    finally:
        # Poner offline en DB y liberar tÃ©cnico

            db_offline = SessionLocal()
            try:
                dev = db_offline.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
                if dev:
                    dev.is_online = False
                    dev.current_technician_id = None
                    dev.session_start = None
                    db_offline.commit()
            except Exception:
                db_offline.rollback()
            finally:
                db_offline.close()
            manager.disconnect(device_id, client_id)



@app.get("/api/centinelas/activos", tags=["Centinela"])
def get_centinelas_activos(current_user: models.User = Depends(get_current_user)):
    """ React consulta por acÃ¡ quÃ© PCs maestras estÃ¡n encendidas y corriendo el programa Centinela. """
    return manager.client_telemetry

@app.get("/api/centinelas/devices/{device_id}/frame", tags=["Centinela"])
async def get_centinela_frame(device_id: int, current_user: models.User = Depends(get_current_user)):
    """ Devuelve el Ãºltimo frame capturado para un dispositivo especÃ­fico y registra al tÃ©cnico conectado. """
    now = datetime.utcnow()
    if device_id not in manager.device_viewers:
        manager.device_viewers[device_id] = {}
        
    manager.device_viewers[device_id][current_user.id] = (current_user.full_name or current_user.nombre or current_user.email or "Soporte", now)
    
    last_notify = manager.last_viewer_notification.get(device_id)
    if not last_notify or (now - last_notify).total_seconds() > 2.0:
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
            
        await manager.send_json_safe(device_id, {
            "type": "active_technicians",
            "technicians": active_viewers
        })
        manager.last_viewer_notification[device_id] = now
        
    frame = manager.client_frames.get(device_id)
    if not frame:
        raise HTTPException(status_code=404, detail="Frame no disponible aÃºn.")
        
    return {"frame": frame}

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
    
    # Si estÃ¡ conectado actualmente, desconectarlo del manager
    manager.disconnect(device_id, device.client_id)
    
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
    """ Devuelve todos los dispositivos que estÃ¡n pendientes de asignaciÃ³n de licencia con seriales, propuestas de clientes y datos del sistema. """
    devices = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.client_id == None).all()
    
    for dev in devices:
        telemetry = manager.client_telemetry.get(dev.id, {})
        serials = telemetry.get("apollo_serials", [])
        dev.apollo_serials = serials
        dev.proposed_client = None

        # Enriquecer con datos de telemetrÃ­a en vivo para identificaciÃ³n
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
    """ Asigna un dispositivo pendiente a un cliente y le envÃ­a su nueva licencia de forma segura por WebSocket. """
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
        raise HTTPException(status_code=400, detail="LÃ­mite de dispositivos excedido para la licencia de este cliente")
        
    # Asignar dispositivo
    device.client_id = client_id
    db.commit()
    
    # Enviar por WebSocket la licencia asignada al dispositivo para que la guarde localmente
    await manager.send_json_safe(device_id, {
        "type": "license_assigned",
        "license_key": lic.license_key
    })
    
    # Actualizar la conexiÃ³n interna del manager
    if device_id in manager.active_connections:
        # Retirar del cliente anterior si existÃ­a
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
    # Buscar sesiÃ³n activa para este tÃ©cnico en este dispositivo (end_time es None)
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
        
        # AÃ±adir timestamp local y comando
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
    """ EnvÃ­a una orden remota a un dispositivo especÃ­fico. """
    cmd = command_data.get("command")
    if not cmd:
        raise HTTPException(status_code=400, detail="Falta el comando.")
    
    # Obtener el dispositivo para saber el client_id (para auditorÃ­a)
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device: raise HTTPException(status_code=404, detail="Dispositivo no encontrado")

    if device_id not in manager.active_connections:
        raise HTTPException(status_code=404, detail="Dispositivo offline")

    await manager.send_json_safe(device_id, {"type": "run_command", "command": cmd})
    
    # Grabar AuditorÃ­a
    log = models.AccessLog(
        technician_id=current_user.id,
        client_id=device.client_id,
        action=f"COMANDO en {device.device_name}: {cmd}"
    )
    db.add(log)
    
    # Loguear en la sesiÃ³n activa si existe
    try:
        log_session_command(device_id, current_user.id, cmd, db)
    except Exception as e:
        logger.error("Error logging session command: %s", e)

    db.commit()
    return {"status": "success"}

@app.post("/api/centinelas/devices/{device_id}/control", tags=["Centinela"])
async def send_centinela_control(device_id: int, control_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ EnvÃ­a una acciÃ³n de ratÃ³n o teclado (clics, textos, teclas especiales) al dispositivo. """
    if device_id not in manager.active_connections:
        raise HTTPException(status_code=404, detail="Dispositivo offline")
    await manager.send_json_safe(device_id, control_data)
    return {"status": "success"}

@app.post("/api/centinelas/devices/{device_id}/chat", tags=["Centinela"])
async def send_centinela_chat(device_id: int, chat_data: schemas.RemoteChatBase, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ EnvÃ­a chat a un dispositivo especÃ­fico y lo guarda en el historial. """
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
    """ Recupera los Ãºltimos 50 mensajes de chat entre tÃ©cnicos y este dispositivo. """
    return db.query(models.RemoteChat).filter(models.RemoteChat.device_id == device_id).order_by(models.RemoteChat.timestamp.asc()).limit(50).all()

@app.post("/api/centinelas/devices/{device_id}/clipboard", tags=["Centinela"])
async def sync_centinela_clipboard(device_id: int, clip_data: dict, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Sincroniza el portapapeles con un dispositivo especÃ­fico. """
    text = clip_data.get("text")
    if device_id in manager.active_connections:
        await manager.send_json_safe(device_id, {"type": "clipboard_sync", "text": text})
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Dispositivo offline")

@app.get("/api/centinelas/devices/{device_id}/clipboard", tags=["Centinela"])
def get_centinela_clipboard(device_id: int, current_user: models.User = Depends(get_current_user)):
    """ Recupera el Ãºltimo texto del portapapeles reportado por el cliente. """
    text = manager.client_clipboard.get(device_id, "")
    return {"text": text}

@app.get("/api/centinelas/devices/{device_id}/files", tags=["Centinela"])
async def get_centinela_files(device_id: int, path: str = "C:\\", current_user: models.User = Depends(get_current_user)):
    """ Solicita al agente listar un directorio y devuelve la lista de archivos. """
    if device_id in manager.active_connections:
        # Limpiar cachÃ© previa para forzar lectura fresca
        if device_id in manager.client_files:
            del manager.client_files[device_id]
            
        await manager.send_json_safe(device_id, {
            "type": "list_dir",
            "path": path
        })
        
        # Esperar brevemente a que el agente responda vÃ­a WebSocket (mÃ¡ximo 1.5s)
        for _ in range(15):
            await asyncio.sleep(0.1)
            cached = manager.client_files.get(device_id)
            if cached and cached.get("type") == "dir_list" and cached.get("path") == path:
                return cached
                
        # Retornar lo que tengamos en cache si no llegÃ³ a tiempo
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
    """ Endpoint donde el agente sube el archivo solicitado por el tÃ©cnico. """
    temp_dir = "temp_files"
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)
    
    file_path = os.path.join(temp_dir, f"{device_id}_{file.filename}")
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    manager.client_files[device_id] = {"status": "ready", "filename": file.filename, "download_path": f"/api/temp/{device_id}_{file.filename}"}
    return {"status": "ok"}

@app.post("/api/centinelas/devices/{device_id}/files/upload", tags=["Centinela"])
async def upload_file_to_agent(device_id: int, file: UploadFile = File(...), dest_path: str = "C:\\ApolloTemp", db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ El tÃ©cnico sube un archivo para enviar a la PC del cliente. """
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
    """ Verifica el PIN de un dispositivo y registra el inicio de sesiÃ³n del tÃ©cnico. """
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
            db.add(models.AccessLog(technician_id=current_user.id, client_id=device.client_id, action=f"CONEXIÃ“N REMOTA: {device.device_name}"))
            
            # Cerrar cualquier sesiÃ³n previa de este tÃ©cnico en este dispositivo que haya quedado colgada (sin end_time)
            if hasattr(models, "SupportSession"):
                previous_active = db.query(models.SupportSession).filter(
                    models.SupportSession.device_id == device_id,
                    models.SupportSession.technician_id == current_user.id,
                    models.SupportSession.end_time == None
                ).all()
                for s in previous_active:
                    s.end_time = datetime.utcnow()
                
                # Crear la nueva sesiÃ³n de soporte activo
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
            
            # Notificar al Agente que un tÃ©cnico ha entrado
            if device_id in manager.active_connections:
                await manager.send_json_safe(device_id, {
                    "type": "technician_joined", 
                    "name": current_user.full_name or current_user.nombre
                })
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
    """ Finaliza la sesiÃ³n actual de un tÃ©cnico en una PC y graba el reporte con IA. """
    comments = payload.get("comment", "") if payload else ""
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    
    if device:
        device.current_technician_id = None
        device.session_start = None
        db.add(models.AccessLog(technician_id=current_user.id, client_id=device.client_id, action=f"SESIÃ“N FINALIZADA: {device.device_name}"))
        db.commit()
        
    # Buscar sesiÃ³n activa de soporte
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
        
        # Generar reporte automÃ¡tico con IA o Fallback offline
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
ActÃºa como un Coordinador TÃ©cnico de TI Inteligente. Resume de forma ejecutiva en un reporte estructurado y elegante en espaÃ±ol lo que un operador de soporte tÃ©cnico realizÃ³ en una PC cliente de Apollo ERP basÃ¡ndote en las siguientes acciones:

- Comandos Ejecutados: {cmds_desc}
- Archivos Transferidos: {files_desc}
- Comentario Manual del Operador: "{comments}"

Instrucciones: Genera una lista compacta y profesional en espaÃ±ol (en formato Markdown, mÃ¡x 4 viÃ±etas) resumiendo las intervenciones clave y confirmando la resoluciÃ³n. No uses preÃ¡mbulos.
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
                        session.ai_report = f"GeneraciÃ³n automÃ¡tica por IA: El operador ejecutÃ³ {cmds_desc} y transfiriÃ³ {files_desc}."
            except Exception as e:
                session.ai_report = f"GeneraciÃ³n automÃ¡tica (Falla de API): El operador ejecutÃ³ {cmds_desc} y transfiriÃ³ {files_desc}."
        else:
            # Fallback offline
            bullet_points = []
            if "spooler" in cmds_desc.lower() or "stop" in cmds_desc.lower():
                bullet_points.append("* ðŸ”„ **Reinicio del Spooler de Windows:** Se restableciÃ³ la cola de impresiÃ³n de Windows para liberar documentos retenidos.")
            if "temp" in cmds_desc.lower() or "del" in cmds_desc.lower():
                bullet_points.append("* ðŸ§¹ **Limpieza del Sistema:** Se eliminaron archivos temporales y de cachÃ© en %TEMP% para corregir bloqueos.")
            if files_desc != "Ninguno":
                bullet_points.append(f"* ðŸ“ **Transferencia de Archivos:** Se gestionaron transferencias de archivos: {files_desc}.")
            if comments:
                bullet_points.append(f"* ðŸ’¬ **Notas del TÃ©cnico:** \"{comments}\"")
                
            if not bullet_points:
                bullet_points.append("* ðŸ” **Monitoreo Remoto:** Se mantuvo sesiÃ³n activa de inspecciÃ³n de la terminal sin comandos intrusivos.")
                if comments:
                    bullet_points.append(f"* ðŸ’¬ **Notas del TÃ©cnico:** \"{comments}\"")
                    
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

@app.get("/api/centinelas/devices/{device_id}/last-session", tags=["Centinela"])
def get_device_last_session(device_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Obtiene la Ãºltima sesiÃ³n de soporte completada para un dispositivo especÃ­fico. """
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
    """ Permite al tÃ©cnico cambiar el PIN u otros ajustes de una PC especÃ­fica. """
    device = db.query(models.CentinelaDevice).filter(models.CentinelaDevice.id == device_id).first()
    if not device: raise HTTPException(status_code=404, detail="PC no encontrada")
    
    if "remote_password" in data:
        device.remote_password = data["remote_password"]
    
    db.commit()
    return {"status": "ok", "message": "Ajustes de dispositivo actualizados."}

@app.get("/api/clients/{client_id}/audit-logs", response_model=List[schemas.AccessLogOut], tags=["Clientes"])
def get_client_audit_logs(client_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    """ Obtiene el historial de intervenciones tÃ©cnicas para un cliente. """
    return db.query(models.AccessLog).filter(models.AccessLog.client_id == client_id).order_by(models.AccessLog.fecha_creacion.desc()).all()





