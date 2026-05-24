"""
-------------------------------------------------------------------------
Esquemas de Pydantic (Validación de Datos)
Proyecto: ApolloSupport
Descripción: Estos modelos aseguran que la información que entra y sale de 
la API tenga el formato correcto y sea segura.
-------------------------------------------------------------------------
"""
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime, date

# =======================
# ESQUEMAS PARA CLIENTES
# =======================
class ClientBase(BaseModel):
    codigo: Optional[str] = None
    razon_social: str
    nombre_fantasia: Optional[str] = None
    identificador_fiscal: Optional[str] = None
    cparte: Optional[str] = None
    version_apollo: Optional[str] = None
    telefono: Optional[str] = None
    activo: Optional[bool] = True
    
    saldo: Optional[float] = 0.0
    email: Optional[str] = None
    localidad: Optional[str] = None
    fecha_ultimo_pago: Optional[date] = None
    fecha_registro: Optional[date] = None
    vendedor_codigo: Optional[str] = None
    vendedor_nombre: Optional[str] = None
    clasificacion_codigo: Optional[str] = None
    clasificacion_nombre: Optional[str] = None
    extracto: Optional[str] = None
    cclifac: Optional[str] = None
    
    fecha_vencimiento: Optional[datetime] = None
    modulos: Optional[str] = "Base, Facturación"
    apikey_apollo: Optional[str] = None
    remote_password: Optional[str] = None

class ClientCreate(ClientBase):
    pass

    class Config:
        from_attributes = True

class DeviceNotesUpdate(BaseModel):
    notes: str

class CentinelaDeviceBase(BaseModel):
    client_id: Optional[int] = None
    device_name: str
    remote_password: Optional[str] = None
    alt_remote_id: Optional[str] = None

class ProposedClientOut(BaseModel):
    id: int
    codigo: Optional[str] = None
    razon_social: str
    
    class Config:
        from_attributes = True

class CentinelaDeviceOut(CentinelaDeviceBase):
    id: int
    last_seen: datetime
    is_online: bool
    current_technician_id: Optional[int] = None
    session_start: Optional[datetime] = None
    technician_name: Optional[str] = None
    notes: Optional[str] = None
    last_erp_update: Optional[str] = None
    apollo_serials: Optional[List[str]] = None
    proposed_client: Optional[ProposedClientOut] = None
    
    class Config:
        from_attributes = True

class ClientOut(ClientBase):
    id: int
    activo: bool
    devices: List[CentinelaDeviceOut] = []
    
    class Config:
        from_attributes = True

# --- SCHEMAS DE CHAT REMOTO ---
class RemoteChatBase(BaseModel):
    message: str
    sender_type: str # 'tech' o 'client'

class RemoteChatOut(RemoteChatBase):
    id: int
    device_id: int
    technician_id: int
    timestamp: datetime

    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA AREAS
# =======================
class AreaBase(BaseModel):
    nombre: str
    descripcion: Optional[str] = None

class AreaOut(AreaBase):
    id: int
    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA USUARIOS
# =======================
class UserBase(BaseModel):
    nombre: str
    email: EmailStr
    full_name: Optional[str] = "Técnico Apollo"
    rol: str = "soporte"
    celular: Optional[str] = None
    departamento: Optional[str] = None
    profile_picture: Optional[str] = None
    is_online: Optional[bool] = False
    current_task: Optional[str] = None
    current_page: Optional[str] = None
    last_activity: Optional[datetime] = None
    last_login: Optional[datetime] = None

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    rol: Optional[str] = None
    password: Optional[str] = None
    celular: Optional[str] = None
    departamento: Optional[str] = None
    profile_picture: Optional[str] = None
    activo: Optional[bool] = None

class UserStatusUpdate(BaseModel):
    is_online: Optional[bool] = None
    current_task: Optional[str] = None
    current_page: Optional[str] = None

class UserOut(UserBase):
    id: int
    activo: bool
    areas: List[AreaOut] = []
    
    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA INTERVENCIONES
# =======================
class InterventionBase(BaseModel):
    mensaje: Optional[str] = None
    tipo: str = "comentario" # 'comentario', 'transferencia', 'resolucion'
    adjunto_url: Optional[str] = None
    adjunto_tipo: Optional[str] = None # 'audio', 'documento', 'imagen'

class InterventionCreate(InterventionBase):
    ticket_id: int
    to_area_id: Optional[int] = None

class InterventionOut(InterventionBase):
    id: int
    ticket_id: int
    user_id: int
    from_area_id: Optional[int] = None
    to_area_id: Optional[int] = None
    fecha_creacion: datetime
    usuario: UserOut
    area_origen: Optional[AreaOut] = None
    area_destino: Optional[AreaOut] = None

    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA TICKETS (TAREAS)
# =======================
class TicketBase(BaseModel):
    client_id: int
    asunto: str
    descripcion: str
    prioridad: str = "media" # baja, media, alta, critica

class TicketCreate(TicketBase):
    initial_area_id: Optional[int] = None

class TicketOut(TicketBase):
    id: int
    assigned_user_id: Optional[int] = None
    current_area_id: Optional[int] = None
    estado: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    
    cliente: Optional[ClientOut] = None
    area_actual: Optional[AreaOut] = None
    intervenciones: List[InterventionOut] = []
    
    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA LOGIN (JWT)
# =======================
class Token(BaseModel):
    access_token: str
    token_type: str
    usuario: dict

class TokenData(BaseModel):
    email: Optional[str] = None

# =======================
# ESQUEMAS PARA ALERTAS
# =======================
class AlertBase(BaseModel):
    client_id: int
    mensaje: str
    severidad: str = "critica"
    resuelta: bool = False

class AlertCreate(AlertBase):
    pass

class AlertOut(AlertBase):
    id: int
    fecha_creacion: datetime
    
    class Config:
        from_attributes = True

class RemoteChatMessage(RemoteChatBase):
    id: int
    timestamp: datetime
    class Config:
        from_attributes = True

class LicenseBase(BaseModel):
    license_key: str
    client_id: int
    max_devices: int
    expiry_date: datetime
    is_active: bool = True

class LicenseCreate(BaseModel):
    client_id: int
    max_devices: int = 5
    duration_days: int = 365

class License(LicenseBase):
    id: int
    created_at: datetime
    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA AUDITORIA
# =======================
class AccessLogOut(BaseModel):
    id: int
    technician_id: int
    client_id: int
    action: str
    fecha_creacion: datetime
    technician: Optional[UserOut] = None

    class Config:
        from_attributes = True

class SupportSessionBase(BaseModel):
    device_id: int
    technician_id: int
    start_time: datetime
    end_time: Optional[datetime] = None
    commands_run: str
    files_transferred: str
    comments: Optional[str] = None
    ai_report: Optional[str] = None

class SupportSessionOut(SupportSessionBase):
    id: int
    technician: Optional[UserOut] = None

    class Config:
        from_attributes = True

# =======================
# ESQUEMAS PARA REMOTE LOGS (TELEMETRIA LOGS)
# =======================
class RemoteLogBase(BaseModel):
    device_id: Optional[int] = None
    source: str  # 'agent' o 'backend'
    level: str = "INFO"
    message: str

class RemoteLogOut(RemoteLogBase):
    id: int
    timestamp: datetime
    device_name: Optional[str] = None

    class Config:
        from_attributes = True

