"""
-------------------------------------------------------------------------
Esquemas de Pydantic (Validación de Datos)
Proyecto: ApolloSupport
Descripción: Estos modelos aseguran que la información que entra y sale de 
la API tenga el formato correcto y sea segura.
-------------------------------------------------------------------------
"""
from pydantic import BaseModel, EmailStr, field_validator
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

    @field_validator("fecha_ultimo_pago", "fecha_registro", mode="before")
    @classmethod
    def empty_date_to_none(cls, value):
        if value in (None, "", "None"):
            return None
        return value

    @field_validator("fecha_vencimiento", mode="before")
    @classmethod
    def empty_datetime_to_none(cls, value):
        if value in (None, "", "None"):
            return None
        return value

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
    assist_id: Optional[str] = None
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
    last_support_date: Optional[datetime] = None
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


class OTAProgress(BaseModel):
    device_id: str
    status: str
    progress: int


# =======================
# ESTADOS DE CUENTA CORRIENTE (ClasiCli)
# =======================
class EstadoCuentaCorrienteBase(BaseModel):
    codigo: str
    descripcion: str = ""
    activo: bool = True


class EstadoCuentaCorrienteCreate(EstadoCuentaCorrienteBase):
    pass


class EstadoCuentaCorrienteUpdate(BaseModel):
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


class EstadoCuentaCorrienteOut(EstadoCuentaCorrienteBase):
    id: int
    origen: Optional[str] = "manual"

    class Config:
        from_attributes = True


# =======================
# AGENDA: GRABACIONES + REUNIONES
# =======================
class ScheduledRecordingCreate(BaseModel):
    client_id: int
    device_id: int
    technician_id: int
    scheduled_at: datetime
    duration_minutes: int = 30
    notes: Optional[str] = None


class ScheduledRecordingUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    technician_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ScheduledRecordingOut(BaseModel):
    id: int
    client_id: int
    device_id: int
    technician_id: int
    scheduled_at: datetime
    duration_minutes: int
    status: str
    support_session_id: Optional[int] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    error_message: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
    device_name: Optional[str] = None
    assist_id: Optional[str] = None
    technician_name: Optional[str] = None
    has_video: bool = False
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class ScheduledMeetingCreate(BaseModel):
    client_id: int
    title: str
    agenda: Optional[str] = None
    starts_at: datetime
    duration_minutes: int = 30
    notify_minutes_before: int = 15
    client_email: Optional[str] = None
    client_phone: Optional[str] = None


class ScheduledMeetingUpdate(BaseModel):
    title: Optional[str] = None
    agenda: Optional[str] = None
    starts_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notify_minutes_before: Optional[int] = None
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    status: Optional[str] = None


class ScheduledMeetingOut(BaseModel):
    id: int
    client_id: int
    host_user_id: int
    title: str
    agenda: Optional[str] = None
    starts_at: datetime
    duration_minutes: int
    join_url: str
    status: str
    notify_minutes_before: int
    client_email: Optional[str] = None
    client_phone: Optional[str] = None
    alert_sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    client_name: Optional[str] = None
    host_name: Optional[str] = None

    class Config:
        from_attributes = True


class MeetingShareOut(BaseModel):
    join_url: str
    message: str
    mailto: Optional[str] = None
    wa_url: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
