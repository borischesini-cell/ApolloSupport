from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, Date, Float, Table
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
    rol = Column(String, default="soporte") # 'admin', 'soporte', 'desarrollo'
    activo = Column(Boolean, default=True)
    expo_push_token = Column(String, nullable=True)
    
    # Nuevos campos de perfil y control de personal
    celular = Column(String, nullable=True)
    departamento = Column(String, nullable=True) # 'Desarrollo', 'Atención al Cliente', 'Caja', 'Finanzas'
    profile_picture = Column(Text, nullable=True) # Base64 encoded image
    is_online = Column(Boolean, default=False)
    current_task = Column(String, nullable=True)
    current_page = Column(String, nullable=True)
    last_activity = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relaciones
    areas = relationship("Area", secondary=user_areas, back_populates="usuarios")
    tickets_asignados = relationship("Ticket", back_populates="asignado_a")
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
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    current_area_id = Column(Integer, ForeignKey("areas.id"), nullable=True)
    
    asunto = Column(String, nullable=False)
    descripcion = Column(Text, nullable=False)
    estado = Column(String, default="nuevo") # 'nuevo', 'en_curso', 'resuelto', 'bloqueado'
    prioridad = Column(String, default="media") 
    
    fecha_creacion = Column(DateTime, default=datetime.datetime.utcnow)
    fecha_actualizacion = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relaciones
    cliente = relationship("Client", back_populates="tickets")
    asignado_a = relationship("User", back_populates="tickets_asignados")
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
    """Cola de notificaciones (email / push / agent / internal)."""
    __tablename__ = "notification_outbox"
    id = Column(Integer, primary_key=True, index=True)
    channel = Column(String, nullable=False)  # email|push|agent|internal
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
