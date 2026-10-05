"""
-------------------------------------------------------------------------
Esquemas de Pydantic (Validación de Datos)
Proyecto: ApolloSupport
Descripción: Estos modelos aseguran que la información que entra y sale de 
la API tenga el formato correcto y sea segura.
-------------------------------------------------------------------------
"""
from pydantic import BaseModel, EmailStr, field_validator
from typing import List, Optional, Dict, Any
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
    reseller_id: Optional[int] = None

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

class GesActiClientIn(BaseModel):
    """Alta / modi / baja enviada desde GesActi (X:\\Util_Activacion)."""
    codigo: Optional[str] = None
    razon_social: Optional[str] = None
    nombre_fantasia: Optional[str] = None
    identificador_fiscal: Optional[str] = None
    cparte: Optional[str] = None
    version_apollo: Optional[str] = None
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
    cclifac: Optional[str] = None
    deleted: Optional[bool] = False

    @field_validator("fecha_ultimo_pago", "fecha_registro", mode="before")
    @classmethod
    def empty_date_to_none(cls, value):
        if value in (None, "", "None"):
            return None
        return value


class GesActiSyncIn(BaseModel):
    clients: List[GesActiClientIn] = []


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
    last_seen: Optional[datetime] = None
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
    reseller_id: Optional[int] = None

class UserCreate(UserBase):
    password: str
    area_ids: Optional[List[int]] = None

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
    area_ids: Optional[List[int]] = None
    reseller_id: Optional[int] = None

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
    # ticket_id viene en la URL (/tickets/{id}/interventions); no exigir en body
    ticket_id: Optional[int] = None
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
class UserBrief(BaseModel):
    id: int
    nombre: Optional[str] = None
    full_name: Optional[str] = None
    rol: Optional[str] = None
    departamento: Optional[str] = None

    class Config:
        from_attributes = True

class TicketBase(BaseModel):
    client_id: Optional[int] = None
    asunto: str
    descripcion: str
    prioridad: str = "media" # baja, media, alta, critica
    origen: str = "cliente"  # cliente | interno

class TicketAdjunto(BaseModel):
    url: str
    filename: Optional[str] = None
    tipo: Optional[str] = None

class TicketCreate(TicketBase):
    initial_area_id: Optional[int] = None
    assigned_user_id: Optional[int] = None
    adjuntos: Optional[List[TicketAdjunto]] = None

class TicketAssign(BaseModel):
    assigned_user_id: Optional[int] = None

class TicketStatusUpdate(BaseModel):
    estado: str  # nuevo | en_curso | resuelto | bloqueado | entregado

class TicketUpdate(BaseModel):
    """Edición de datos del pedido (si faltó algo al cargar)."""
    client_id: Optional[int] = None
    asunto: Optional[str] = None
    descripcion: Optional[str] = None
    prioridad: Optional[str] = None
    origen: Optional[str] = None
    clear_client: bool = False  # True = quitar cliente (pedido interno)

class TicketOut(TicketBase):
    id: int
    assigned_user_id: Optional[int] = None
    created_by_id: Optional[int] = None
    current_area_id: Optional[int] = None
    estado: str
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    
    cliente: Optional[ClientOut] = None
    area_actual: Optional[AreaOut] = None
    asignado_a: Optional[UserBrief] = None
    creado_por: Optional[UserBrief] = None
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
    windows_session_id: Optional[int] = None
    windows_session_label: Optional[str] = None


class ScheduledRecordingUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    technician_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None
    windows_session_id: Optional[int] = None
    windows_session_label: Optional[str] = None


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
    windows_session_id: Optional[int] = None
    windows_session_label: Optional[str] = None
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


# =======================
# ESQUEMAS PARA RESELLERS
# =======================
class ResellerBase(BaseModel):
    nombre: str
    contacto: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    comision_pct: Optional[float] = 0.0
    notas: Optional[str] = None
    activo: Optional[bool] = True


class ResellerCreate(ResellerBase):
    pass


class ResellerUpdate(BaseModel):
    nombre: Optional[str] = None
    contacto: Optional[str] = None
    email: Optional[str] = None
    telefono: Optional[str] = None
    comision_pct: Optional[float] = None
    notas: Optional[str] = None
    activo: Optional[bool] = None


class ResellerOut(ResellerBase):
    id: int
    fecha_registro: Optional[datetime] = None
    cantidad_clientes: Optional[int] = 0
    cantidad_usuarios: Optional[int] = 0

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════════
# WhatsApp Cloud API — esquemas
# ═══════════════════════════════════════════════════════════════════════════

class WhatsAppAccountBase(BaseModel):
    client_id: int
    business_id: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    allowed_categories: Optional[str] = "UTILITY,SERVICE"
    monthly_message_quota: Optional[int] = None
    rate_currency: Optional[str] = "USD"
    rate_overrides: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    erp_send_enabled: bool = False
    erp_invoice_template: Optional[str] = None
    erp_invoice_language: Optional[str] = None


class WhatsAppAccountCreate(WhatsAppAccountBase):
    access_token: Optional[str] = None   # se cifra al guardar, nunca se devuelve
    pin: Optional[str] = None


class WhatsAppAccountUpdate(BaseModel):
    client_id: Optional[int] = None
    business_id: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    access_token: Optional[str] = None
    pin: Optional[str] = None
    status: Optional[str] = None
    allowed_categories: Optional[str] = None
    monthly_message_quota: Optional[int] = None
    rate_currency: Optional[str] = None
    rate_overrides: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    erp_send_enabled: Optional[bool] = None
    erp_invoice_template: Optional[str] = None
    erp_invoice_language: Optional[str] = None


class WhatsAppAccountOut(BaseModel):
    id: int
    client_id: int
    client_name: Optional[str] = None
    business_id: Optional[str] = None
    waba_id: Optional[str] = None
    phone_number_id: Optional[str] = None
    display_phone_number: Optional[str] = None
    verified_name: Optional[str] = None
    status: Optional[str] = None
    registration_state: Optional[str] = None
    quality_rating: Optional[str] = None
    messaging_limit_tier: Optional[str] = None
    allowed_categories: Optional[str] = None
    monthly_message_quota: Optional[int] = None
    messages_sent_this_month: int = 0
    period_start: Optional[date] = None
    rate_currency: Optional[str] = None
    rate_overrides: Optional[Dict[str, float]] = None
    notes: Optional[str] = None
    has_token: bool = False
    webhook_verify_token: Optional[str] = None
    erp_send_enabled: bool = False
    erp_invoice_template: Optional[str] = None
    erp_invoice_language: Optional[str] = None
    created_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WhatsAppTemplateCreate(BaseModel):
    name: str
    language: str = "es"
    category: str = "UTILITY"
    header_text: Optional[str] = None
    body_text: str
    footer_text: Optional[str] = None
    buttons: Optional[List[Dict[str, Any]]] = None
    push_to_meta: bool = True


class WhatsAppTemplateOut(BaseModel):
    id: int
    account_id: int
    name: str
    language: str
    category: str
    status: str
    header_text: Optional[str] = None
    body_text: Optional[str] = None
    footer_text: Optional[str] = None
    buttons_json: Optional[str] = None
    meta_template_id: Optional[str] = None
    rejection_reason: Optional[str] = None
    usage_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WhatsAppSendRequest(BaseModel):
    to: str
    type: str = "text"                       # text|template|image|document|audio
    body: Optional[str] = None               # texto del mensaje
    template_name: Optional[str] = None
    language: Optional[str] = "es"
    components: Optional[List[Dict[str, Any]]] = None
    media_url: Optional[str] = None          # https o id de media ya subida
    media_id: Optional[str] = None
    filename: Optional[str] = None
    caption: Optional[str] = None
    contact_name: Optional[str] = None
    ref_ticket_id: Optional[int] = None      # trazabilidad hacia tickets


class WhatsAppMessageOut(BaseModel):
    id: int
    account_id: int
    client_id: Optional[int] = None
    conversation_id: Optional[int] = None
    source_channel: Optional[str] = None
    direction: str
    contact_phone: str
    contact_name: Optional[str] = None
    message_type: str
    body_text: Optional[str] = None
    template_name: Optional[str] = None
    media_url: Optional[str] = None
    meta_message_id: Optional[str] = None
    status: str
    error_code: Optional[str] = None
    error_title: Optional[str] = None
    pricing_category: Optional[str] = None
    billable: bool = False
    cost_amount: Optional[float] = None
    erp_serial: Optional[str] = None
    erp_operator: Optional[str] = None
    erp_doc_ref: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: Optional[datetime] = None
    wa_timestamp: Optional[datetime] = None
    status_updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WhatsAppConversationOut(BaseModel):
    id: int
    account_id: int
    client_name: Optional[str] = None
    contact_phone: str
    contact_name: Optional[str] = None
    category: str
    billable: bool = False
    status: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    last_inbound_at: Optional[datetime] = None
    message_count: int = 0
    outbound_count: int = 0
    inbound_count: int = 0
    first_message_preview: Optional[str] = None
    is_open: bool = False

    class Config:
        from_attributes = True


class WhatsAppBillingRow(BaseModel):
    account_id: int
    client_id: int
    client_name: Optional[str] = None
    display_phone_number: Optional[str] = None
    sent_total: int = 0
    delivered_total: int = 0
    read_total: int = 0
    failed_total: int = 0
    inbound_total: int = 0
    utility_msgs: int = 0
    marketing_msgs: int = 0
    authentication_msgs: int = 0
    service_msgs: int = 0
    conversations_total: int = 0
    cost_amount: float = 0.0
    currency: str = "USD"


class WhatsAppBillingReport(BaseModel):
    period_start: date
    period_end: date
    rows: List[WhatsAppBillingRow]
    total_cost: float = 0.0
    currency: str = "USD"
    rates: Dict[str, float] = {}


class WhatsAppBillingPeriodOut(BaseModel):
    id: int
    account_id: int
    client_id: int
    client_name: Optional[str] = None
    display_phone_number: Optional[str] = None
    period_start: date
    period_end: date
    sent_total: int = 0
    delivered_total: int = 0
    read_total: int = 0
    failed_total: int = 0
    inbound_total: int = 0
    utility_msgs: int = 0
    marketing_msgs: int = 0
    authentication_msgs: int = 0
    service_msgs: int = 0
    conversations_total: int = 0
    cost_amount: float = 0.0
    currency: str = "USD"
    markup_pct: float = 0.0
    amount_to_invoice: float = 0.0
    status: str
    closed_at: Optional[datetime] = None
    invoice_ref: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


# ═════════════════════════════════════════════════════════════════════════════
# Canal ERP (ApolloGesCom): el puesto pide credenciales y envía comprobantes
# ═════════════════════════════════════════════════════════════════════════════

class WhatsAppErpBootstrapIn(BaseModel):
    serial: str                              # l_number de la licencia ApolloGesCom
    operator: Optional[str] = None           # usuario del ERP en el puesto
    codigo: Optional[str] = None             # CCOD; si se omite se toma de serial[:4]


class WhatsAppErpBootstrapOut(BaseModel):
    status: str                              # ok | sin_linea | deshabilitado
    client_code: str
    api_key: Optional[str] = None            # se muestra una vez: es el secreto HMAC
    serial: Optional[str] = None
    account_id: Optional[int] = None
    display_phone_number: Optional[str] = None
    erp_send_enabled: bool = False
    invoice_template: Optional[str] = None
    invoice_language: Optional[str] = None
    use_cloud_api: bool = False              # False = que el puesto siga con el bridge
    signature_prefix: str = "apollo-wa-erp-v1"
    max_pdf_mb: float = 8.0


class WhatsAppErpSendIn(BaseModel):
    """Envío de un comprobante: el PDF viaja en base64 y Support lo sube a Meta."""
    to: str
    filename: Optional[str] = None
    media_b64: Optional[str] = None          # PDF del puesto; si va por link, media_url
    media_url: Optional[str] = None
    caption: Optional[str] = None            # texto libre sólo si el cliente escribió en 24 h
    doc_ref: Optional[str] = None            # FA A 0001-00000123
    template_vars: Optional[List[str]] = None
    template_name: Optional[str] = None
    language: Optional[str] = None
    mode: str = "auto"                       # auto | template | document
    serial: Optional[str] = None
    operator: Optional[str] = None
    contact_name: Optional[str] = None
    idempotency_key: Optional[str] = None


class WhatsAppErpSendOut(BaseModel):
    message_id: int
    meta_message_id: Optional[str] = None
    status: str
    channel_used: str                        # template | document
    pricing_category: Optional[str] = None
    billable: bool = False
    cost_amount: Optional[float] = None
    duplicate: bool = False                  # idempotency_key ya existente: no se reenvió
    detail: Optional[str] = None


class WhatsAppErpUsageRow(BaseModel):
    id: int
    created_at: Optional[datetime] = None
    serial: Optional[str] = None
    operator: Optional[str] = None
    doc_ref: Optional[str] = None
    contact_phone: str
    template_name: Optional[str] = None
    message_type: Optional[str] = None
    status: str
    pricing_category: Optional[str] = None
    billable: bool = False
    cost_amount: Optional[float] = None

    class Config:
        from_attributes = True


class WhatsAppErpUsageReport(BaseModel):
    client_id: int
    client_name: Optional[str] = None
    period_start: date
    period_end: date
    sent_total: int = 0
    billable_total: int = 0
    cost_amount: float = 0.0
    markup_pct: float = 0.0
    amount_to_invoice: float = 0.0
    currency: str = "USD"
    by_serial: Dict[str, int] = {}
    rows: List[WhatsAppErpUsageRow] = []
