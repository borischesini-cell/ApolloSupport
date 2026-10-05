from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Date, Float, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base
import datetime

# Tabla intermedia para Relación Muchos-a-Muchos: Usuarios <-> Áreas
user_areas = Table(
    "user_areas",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column("area_id", Integer, ForeignKey("areas.id"), primary_key=True)
)

class Area(Base):
    """
    Representa las áreas operativas de la oficina: Atención al Cliente, Desarrollo, Finanzas.
    """
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True, nullable=False)
    descripcion = Column(String)
    
    # Relación con usuarios a través de la tabla intermedia
    usuarios = relationship("User", secondary=user_areas, back_populates="areas")
    # Tareas que están actualmente en esta área
    tickets_actuales = relationship("Ticket", back_populates="area_actual")

class Reseller(Base):
    """Revendedor / empresa externa con clientes y usuarios propios."""
    __tablename__ = "resellers"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, nullable=False, index=True)
    contacto = Column(String, nullable=True)
    email = Column(String, nullable=True)
    telefono = Column(String, nullable=True)
    comision_pct = Column(Float, default=0.0)
    notas = Column(Text, nullable=True)
    activo = Column(Boolean, default=True)
    fecha_registro = Column(DateTime, default=datetime.datetime.utcnow)

    clientes = relationship("Client", back_populates="reseller")
    usuarios = relationship("User", back_populates="reseller")


class User(Base):
    """
    Tabla de Usuarios Internos (Agentes, administradores, programadores).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, default="Técnico Apollo")
    rol = Column(String, default="soporte") # 'admin', 'soporte', 'desarrollo', 'reseller'
    activo = Column(Boolean, default=True)
    expo_push_token = Column(String, nullable=True)

    # Nuevos campos de perfil y control de personal
    celular = Column(String, nullable=True)
    departamento = Column(String, nullable=True) # Resumen de actividades: 'Desarrollo / Finanzas'
    profile_picture = Column(Text, nullable=True) # Base64 encoded image
    is_online = Column(Boolean, default=False)
    current_task = Column(String, nullable=True)
    current_page = Column(String, nullable=True)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    reseller_id = Column(Integer, ForeignKey("resellers.id"), nullable=True)

    # Relaciones
    reseller = relationship("Reseller", back_populates="usuarios")
    areas = relationship("Area", secondary=user_areas, back_populates="usuarios")
    # foreign_keys explícito: Ticket apunta a users por dos columnas
    # (assigned_user_id y created_by_id) y SQLAlchemy no puede adivinar.
    tickets_asignados = relationship("Ticket", foreign_keys="Ticket.assigned_user_id",
                                     back_populates="asignado_a")
    intervenciones = relationship("Intervention", back_populates="usuario")

class Client(Base):
    """
    Tabla de Clientes (Empresas que usan ApolloGesCom).
    """
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String, unique=True, index=True, nullable=True)  # CCOD
    razon_social = Column(String, index=True, nullable=False)        # CRASO
    nombre_fantasia = Column(String, nullable=True)                  # CDES
    identificador_fiscal = Column(String, index=True)   # CPART o CUIT
    cparte = Column(String, nullable=True)                           # CPARTE original
    version_apollo = Column(String, nullable=True)                   # CVERSION o similar
    telefono = Column(String, nullable=True)
    activo = Column(Boolean, default=True)                           # CACTI
    
    saldo = Column(Float, default=0.0)                               # CSALDO
    email = Column(String, nullable=True)                            # CEMAIL
    localidad = Column(String, nullable=True)                        # CLOCALIDA
    fecha_ultimo_pago = Column(Date, nullable=True)                  # CULPA
    fecha_registro = Column(Date, nullable=True)                     # CFECHA
    vendedor_codigo = Column(String, nullable=True)                  # CVENDEDOR
    vendedor_nombre = Column(String, nullable=True)                  # CNOMVEN
    clasificacion_codigo = Column(String, nullable=True)             # CCLAS
    clasificacion_nombre = Column(String, nullable=True)             # CNOMCLAS
    extracto = Column(Text, nullable=True)                           # CEXTRACTO (RTF Memo)
    cclifac = Column(String, nullable=True)                          # CCLIFAC (Billing System Client Link)
    
    fecha_vencimiento = Column(DateTime, nullable=True)
    modulos = Column(String, default="Base, Facturación")
    apikey_apollo = Column(String, unique=True, index=True)

    reseller_id = Column(Integer, ForeignKey("resellers.id"), nullable=True)

    reseller = relationship("Reseller", back_populates="clientes")
    devices = relationship("CentinelaDevice", back_populates="cliente")
    tickets = relationship("Ticket", back_populates="cliente")


class EstadoCuentaCorriente(Base):
    """
    Catálogo ERP Ventas\\ClasiCli — Estados de Cuenta Corriente (Cobranzas).
    Código = CCOD, descripción = CDESC. Los clientes lo referencian vía CCLAS.
    """
    __tablename__ = "estados_cuenta_corriente"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(10), unique=True, index=True, nullable=False)
    descripcion = Column(String(60), nullable=False, default="")
    activo = Column(Boolean, default=True)
    origen = Column(String(20), default="manual")  # 'erp' | 'manual'


class Ticket(Base):
    """
    Representa una Tarea o Requerimiento que puede viajar entre áreas.
    """
    __tablename__ = "tickets"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    current_area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    
    asunto = Column(String, nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(String, default="nuevo") # 'nuevo', 'en_curso', 'resuelto', 'bloqueado'
    prioridad = Column(String, default="media")
    origen = Column(String, default="cliente")  # 'cliente' | 'interno'
    
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relaciones
    cliente = relationship("Client", back_populates="tickets")
    asignado_a = relationship("User", foreign_keys=[assigned_user_id], back_populates="tickets_asignados")
    creado_por = relationship("User", foreign_keys=[created_by_id])
    area_actual = relationship("Area", back_populates="tickets_actuales")
    intervenciones = relationship("Intervention", back_populates="ticket", cascade="all, delete-orphan")

class Intervention(Base):
    """
    Registro histórico de cada 'ida y vuelta'. Soporta texto, audios y archivos.
    """
    __tablename__ = "interventions"
    
    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # De qué área a qué área se movió o en cuál se comentó
    from_area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    to_area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    
    mensaje = Column(Text, nullable=True)
    tipo = Column(String, default="comentario") # 'comentario', 'transferencia', 'resolucion'
    
    # Soporte Multimedia
    adjunto_url = Column(String, nullable=True) # Link al archivo/audio en el servidor
    adjunto_tipo = Column(String, nullable=True) # 'audio', 'documento', 'imagen'
    
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relaciones
    ticket = relationship("Ticket", back_populates="intervenciones")
    usuario = relationship("User", back_populates="intervenciones")
    area_origen = relationship("Area", foreign_keys=[from_area_id])
    area_destino = relationship("Area", foreign_keys=[to_area_id])

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    mensaje = Column(String, nullable=False)
    severidad = Column(String, default="critica")
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    resuelta = Column(Boolean, default=False)
    cliente = relationship("Client")

class AccessLog(Base):
    __tablename__ = "access_logs"
    id = Column(Integer, primary_key=True, index=True)
    technician_id = Column(Integer, ForeignKey("users.id"))
    client_id = Column(Integer, ForeignKey("clients.id"))
    action = Column(String)
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    technician = relationship("User")
    cliente = relationship("Client")

class CentinelaDevice(Base):
    __tablename__ = "centinela_devices"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    device_name = Column(String, index=True)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    remote_password = Column(String, nullable=True)
    # ID de asistencia mostrado en ApolloSoporte ("Dicte este ID"): 6 dígitos del config local
    assist_id = Column(String, nullable=True, index=True)
    alt_remote_id = Column(String, nullable=True)
    is_online = Column(Boolean, default=False)
    current_technician_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_start = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    last_erp_update = Column(String, nullable=True)
    last_support_date = Column(DateTime, nullable=True)
    cliente = relationship("Client", back_populates="devices")
    technician = relationship("User")

    @property
    def technician_name(self):
        return self.technician.full_name if self.technician else None

class RemoteChat(Base):
    __tablename__ = "remote_chats"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("centinela_devices.id"))
    technician_id = Column(Integer, ForeignKey("users.id"))
    message = Column(String)
    sender_type = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

class License(Base):
    __tablename__ = "licenses"
    id = Column(Integer, primary_key=True, index=True)
    license_key = Column(String, unique=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"))
    max_devices = Column(Integer, default=5)
    expiry_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class SupportSession(Base):
    __tablename__ = "support_sessions"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("centinela_devices.id"), nullable=False)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    commands_run = Column(Text, default="[]") # JSON string containing list of logged actions/commands
    files_transferred = Column(Text, default="[]") # JSON string containing transferred files
    comments = Column(Text, nullable=True) # Manual notes left by the operator
    ai_report = Column(Text, nullable=True) # AI-generated automatic report of activities

    device = relationship("CentinelaDevice")
    technician = relationship("User")

    @property
    def duration_seconds(self):
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time).total_seconds())
        return 0

class RemoteLog(Base):
    __tablename__ = "remote_logs"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("centinela_devices.id"), nullable=True)
    source = Column(String)  # 'agent' o 'backend'
    level = Column(String, default="INFO")
    message = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)


class ScheduledRecording(Base):
    """Grabación programada del escritorio remoto (Centinela)."""
    __tablename__ = "scheduled_recordings"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("centinela_devices.id"), nullable=False)
    technician_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=30)
    status = Column(String, default="scheduled", index=True)  # scheduled|running|completed|failed|cancelled
    support_session_id = Column(Integer, ForeignKey("support_sessions.id"), nullable=True)
    file_path = Column(String, nullable=True)
    file_size = Column(Integer, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    windows_session_id = Column(Integer, nullable=True)  # qwinsta session id a grabar
    windows_session_label = Column(String, nullable=True)  # ej. "user@rdp-tcp#3"
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    client = relationship("Client")
    device = relationship("CentinelaDevice")
    technician = relationship("User")


class ScheduledMeeting(Base):
    """Videoconferencia agendada (Jitsi)."""
    __tablename__ = "scheduled_meetings"
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    host_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    agenda = Column(Text, nullable=True)
    starts_at = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=30)
    join_url = Column(String, nullable=False)
    status = Column(String, default="scheduled", index=True)  # scheduled|live|completed|cancelled
    notify_minutes_before = Column(Integer, default=15)
    client_email = Column(String, nullable=True)
    client_phone = Column(String, nullable=True)
    alert_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    client = relationship("Client")
    host = relationship("User")


class NotificationOutbox(Base):
    """Cola de notificaciones (email / push / agent / internal / whatsapp)."""
    __tablename__ = "notification_outbox"
    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False)  # email|push|agent|internal|whatsapp
    target = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body = Column(Text, nullable=False)
    send_at = Column(DateTime, nullable=False, index=True)
    sent_at = Column(DateTime, nullable=True)
    status = Column(String, default="pending", index=True)  # pending|sent|failed
    error_message = Column(Text, nullable=True)
    ref_type = Column(String, nullable=True)  # meeting|recording
    ref_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════
# WHATSAPP CLOUD API (oficial) — integración multi-tenant
# Cada cliente tiene SU propia línea (WABA + phone_number), con costos
# separados para facturar a fin de mes.
# ═══════════════════════════════════════════════════════════════════════════

class WhatsAppAccount(Base):
    """Una línea de WhatsApp Business de un cliente, dada de alta por nosotros (Tech Provider)."""
    __tablename__ = "whatsapp_accounts"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    # Identificadores de Meta
    business_id = Column(String, nullable=True)          # Business Manager ID del cliente
    waba_id = Column(String, nullable=True, index=True)  # WhatsApp Business Account ID
    phone_number_id = Column(String, nullable=True, unique=True, index=True)  # id del número en Graph
    display_phone_number = Column(String, nullable=True)  # Ej: +543446675303
    verified_name = Column(String, nullable=True)         # Display name aprobado por Meta

    # Credenciales: el token NUNCA se guarda en claro (ver wa_crypto en whatsapp.py)
    access_token_enc = Column(Text, nullable=True)        # System User Token cifrado (Fernet)
    webhook_verify_token = Column(String, nullable=True)  # challenge propio de la cuenta
    pin = Column(String, nullable=True)                   # 2FA pin para registrar el número

    status = Column(String, default="pending", index=True)  # pending|registered|connected|disabled
    registration_state = Column(String, nullable=True)      # respuesta cruda del register
    quality_rating = Column(String, nullable=True)          # green|yellow|red|messaging_banned
    messaging_limit_tier = Column(String, nullable=True)    # TIER_250 ... UNLIMITED

    # Configuración operativa
    allowed_categories = Column(String, default="UTILITY,SERVICE")  # qué plantillas puede usar
    monthly_message_quota = Column(Integer, nullable=True)          # tope de envíos, None = sin tope
    messages_sent_this_month = Column(Integer, default=0)
    period_start = Column(Date, nullable=True)                      # inicio del período de facturación
    rate_currency = Column(String, default="USD")
    rate_overrides = Column(Text, nullable=True)                    # JSON {"UTILITY":0.0225,...}
    notes = Column(Text, nullable=True)

    # Canal ERP (ApolloGesCom). Sin este flag el puesto no puede usar la línea,
    # aunque tenga una apikey válida: es el control de "quién la utiliza".
    erp_send_enabled = Column(Boolean, default=False, index=True)
    erp_invoice_template = Column(String, nullable=True)   # plantilla aprobada p/ envío en frío
    erp_invoice_language = Column(String, nullable=True)   # código de idioma de esa plantilla

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)
    connected_at = Column(DateTime, nullable=True)

    client = relationship("Client")

    templates = relationship("WhatsAppTemplate", back_populates="account",
                             cascade="all, delete-orphan")
    conversations = relationship("WhatsAppConversation", back_populates="account",
                                cascade="all, delete-orphan")
    messages = relationship("WhatsAppMessage", back_populates="account",
                           cascade="all, delete-orphan")

    @property
    def client_name(self):
        return self.client.razon_social if self.client else None


class WhatsAppTemplate(Base):
    """Plantilla aprobada (o en revisión) por Meta, perteneciente a una cuenta."""
    __tablename__ = "whatsapp_templates"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("whatsapp_accounts.id"), nullable=False, index=True)

    name = Column(String, nullable=False)        # reject lowercase/snake_case exigido por Meta
    language = Column(String, nullable=False, default="es")
    category = Column(String, nullable=False, default="UTILITY")  # UTILITY|MARKETING|AUTHENTICATION|SERVICE
    status = Column(String, default="PENDING", index=True)        # PENDING|APPROVED|REJECTED|DISABLED

    header_text = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)        # con marcadores {{1}} {{2}}
    footer_text = Column(Text, nullable=True)
    buttons_json = Column(Text, nullable=True)     # JSON lista de botones rápidos
    components_json = Column(Text, nullable=True)  # payload completo enviado a Meta

    meta_template_id = Column(String, nullable=True, index=True)
    rejection_reason = Column(Text, nullable=True)
    auto_approved = Column(Boolean, default=False)

    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow,
                        onupdate=datetime.datetime.utcnow)

    account = relationship("WhatsAppAccount", back_populates="templates")

    __table_args__ = (
        # Meta identifica la plantilla por (nombre, idioma) dentro de la WABA
        UniqueConstraint("account_id", "name", "language", name="uq_wa_tpl_account_name_lang"),
    )


class WhatsAppConversation(Base):
    """
    Ventana de conversación de 24 h. Meta factura por mensaje de plantilla,
    pero la ventana sigue definiendo si el cliente puede responder sin costo.
    """
    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("whatsapp_accounts.id"), nullable=False, index=True)

    contact_phone = Column(String, nullable=False, index=True)
    contact_name = Column(String, nullable=True)
    meta_conversation_id = Column(String, nullable=True)

    category = Column(String, default="service")      # service|utility|marketing|authentication
    billable = Column(Boolean, default=False)         # service = no factura
    status = Column(String, default="open", index=True)  # open|expired
    started_at = Column(DateTime, nullable=False, index=True, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True, index=True)   # started_at + 24 h
    last_inbound_at = Column(DateTime, nullable=True)

    message_count = Column(Integer, default=0)
    outbound_count = Column(Integer, default=0)
    inbound_count = Column(Integer, default=0)
    first_message_preview = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    account = relationship("WhatsAppAccount", back_populates="conversations")
    messages = relationship("WhatsAppMessage", back_populates="conversation")

    @property
    def is_open(self):
        return self.status == "open" and (
            self.expires_at is None or self.expires_at > datetime.datetime.utcnow()
        )


class WhatsAppMessage(Base):
    """Bitácora inmutable de cada mensaje enviado o recibido (fuente de la facturación)."""
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("whatsapp_accounts.id"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("whatsapp_conversations.id"), nullable=True, index=True)

    direction = Column(String, nullable=False, index=True)   # inbound|outbound
    contact_phone = Column(String, nullable=False, index=True)
    contact_name = Column(String, nullable=True)

    message_type = Column(String, default="text")  # text|template|image|document|audio|location|button|interactive
    body_text = Column(Text, nullable=True)        # texto legible (body o nombre de plantilla)
    template_name = Column(String, nullable=True)
    payload_json = Column(Text, nullable=True)     # JSON original de Meta

    media_id = Column(String, nullable=True)
    media_url = Column(String, nullable=True)
    media_mime = Column(String, nullable=True)

    meta_message_id = Column(String, nullable=True, index=True)
    status = Column(String, default="queued", index=True)  # queued|sent|delivered|read|failed
    error_code = Column(String, nullable=True)
    error_title = Column(String, nullable=True)

    pricing_category = Column(String, nullable=True)  # utility|marketing|authentication|service
    billable = Column(Boolean, default=False)

    # cost_amount en la moneda de rate_currency de la cuenta, al tipo de lista de Meta
    cost_amount = Column(Float, nullable=True)

    # Origen del envío. client_id va denormalizado (viene de la cuenta) para poder
    # agrupar el consumo por cliente sin joins; los campos erp_* identifican al
    # puesto que disparó el envío: son la justificación del cobro de fin de mes,
    # por eso van en columnas reales y no dentro de payload_json.
    client_id = Column(Integer, nullable=True, index=True)
    source_channel = Column(String, nullable=True, index=True)  # panel|outbox|erp
    erp_serial = Column(String, nullable=True, index=True)      # l_number de la licencia
    erp_operator = Column(String, nullable=True)                # usuario del ERP en el puesto
    erp_doc_ref = Column(String, nullable=True)                 # comprobante enviado (FA A 0001-00000123)
    idempotency_key = Column(String, nullable=True, index=True)  # el puesto repite el envío -> no se duplica

    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    wa_timestamp = Column(DateTime, nullable=True)
    status_updated_at = Column(DateTime, nullable=True)

    account = relationship("WhatsAppAccount", back_populates="messages")
    conversation = relationship("WhatsAppConversation", back_populates="messages")


class WhatsAppWebhookEvent(Base):
    """Cola de eventos crudos recibidos de Meta: permite re-procesar si algo falla."""
    __tablename__ = "whatsapp_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("whatsapp_accounts.id"), nullable=True, index=True)
    phone_number_id = Column(String, nullable=True, index=True)
    event_type = Column(String, nullable=True)   # messages|statuses|message_template_status_update
    payload = Column(Text, nullable=False)       # JSON body completo
    signature_ok = Column(Boolean, nullable=True)
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)


class WhatsAppBillingPeriod(Base):
    """Cierre mensual por cliente: base para la factura de fin de mes."""
    __tablename__ = "whatsapp_billing_periods"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("whatsapp_accounts.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    period_start = Column(Date, nullable=False, index=True)
    period_end = Column(Date, nullable=False)

    sent_total = Column(Integer, default=0)
    delivered_total = Column(Integer, default=0)
    read_total = Column(Integer, default=0)
    failed_total = Column(Integer, default=0)
    inbound_total = Column(Integer, default=0)

    utility_msgs = Column(Integer, default=0)
    marketing_msgs = Column(Integer, default=0)
    authentication_msgs = Column(Integer, default=0)
    service_msgs = Column(Integer, default=0)
    conversations_total = Column(Integer, default=0)

    cost_amount = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    amount_to_invoice = Column(Float, default=0.0)   # con markup aplicado
    markup_pct = Column(Float, default=0.0)

    status = Column(String, default="open", index=True)  # open|closed|invoiced
    closed_at = Column(DateTime, nullable=True)
    invoice_ref = Column(String, nullable=True)          # nº de comprobante emitido
    details_json = Column(Text, nullable=True)           # desglose por día/plantilla
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    account = relationship("WhatsAppAccount")
    client = relationship("Client")

    __table_args__ = (
        # Un cierre por cuenta y período: evita facturar dos veces el mismo mes
        UniqueConstraint("account_id", "period_start", name="uq_wa_billing_account_period"),
    )
