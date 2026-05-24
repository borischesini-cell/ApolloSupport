import { useState, useEffect, useRef, useCallback } from 'react';
import { Ticket, Users, Settings, Bell, Search, Moon, Sun, Monitor, MessageSquare, X, LogOut, ArrowUpRight, Sparkles, FileText, Clipboard, Plus, Folder, Trash2, Menu, DollarSign, CheckCircle2, AlertCircle, Activity, UserPlus, Shield, Phone, MapPin, Mail, Lock, Key, Camera, Edit2, Maximize2, Minimize, Terminal } from 'lucide-react';
import {
  API_URL, getTickets, getClients, createTicket, createClient, updateClient,
  toggleClientStatus, getActiveCentinelas, fetchAiAnalysis, getCentinelaFrame,
  getCentinelaAlerts, runCentinelaCommand, sendCentinelaControl, getAreas,
  addIntervention, uploadFile, deleteCentinelaDevice, getCentinelaClipboard,
  syncClientsFromDbf, updateCentinelaDeviceNotes, getPendingCentinelas, assignCentinelaLicense,
  getUsers, createUser, updateUser, toggleUserStatus, updateUserStatus, logoutUser,
  getClientBalance, getClientExtracto, viewVoucherPdf,
  useViewerWebSocket, type ConnectionQuality, useHqViewerWebSocket,
  REMOTE_STREAM_WORKABLE_FPS, REMOTE_STREAM_COMFORTABLE_FPS, connectionQualityFromFps,
  getCentinelaLogs, clearCentinelaLogs,
} from './api';
import Login from './Login';

const triggerPushNotification = (title: string, body: string, url: string = '/') => {
  if ('Notification' in window && Notification.permission === 'granted') {
    if (navigator.serviceWorker && navigator.serviceWorker.ready) {
      navigator.serviceWorker.ready.then(reg => {
        reg.showNotification(title, {
          body,
          icon: '/icon-192.png',
          badge: '/icon-192.png',
          vibrate: [200, 100, 200],
          data: { url }
        } as any);
      });
    } else {
      new Notification(title, {
        body,
        icon: '/icon-192.png'
      });
    }
  }
};

const stripRtf = (rtf: string): string => {
  if (!rtf) return "";
  let text = rtf;
  // Remove control words and parameters
  text = text.replace(/\\rtf1|\\ansi|\\ansicpg\d+|\\deff\d+|\\deflang\d+/g, "");
  // Remove font tables and color tables
  text = text.replace(/{\\fonttbl.*?}/g, "");
  // Remove stylesheet and colortbl
  text = text.replace(/{\\colortbl.*?}/g, "");
  text = text.replace(/{\\\*\\generator.*?}/g, "");
  // Remove standard RTF formatting tags
  text = text.replace(/\\par/g, "\n");
  text = text.replace(/\\tab/g, "    ");
  text = text.replace(/\\b\s|\\b0/g, "");
  text = text.replace(/\\i\s|\\i0/g, "");
  text = text.replace(/\\cf\d+/g, "");
  text = text.replace(/\\f\d+|\\fs\d+/g, "");
  // Decode hex characters e.g. \'f3 to characters
  text = text.replace(/\\\'([0-9a-f]{2})/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)));
  // Strip any remaining curly braces
  text = text.replace(/{|}/g, "");
  return text.trim();
};

const renderLastErpUpdate = (lastErpUpdateStr: string | null, telemetry: any) => {
  const rawVal = telemetry?.last_erp_update || lastErpUpdateStr;
  if (!rawVal) return null;
  
  try {
    const data = typeof rawVal === 'string' && rawVal.startsWith('{') ? JSON.parse(rawVal) : rawVal;
    if (data && data.status === 'success' && data.latest_record) {
      const rec = data.latest_record;
      const dateKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('fecha') || k.toLowerCase().includes('date') || k.toLowerCase().includes('fec'));
      const dateVal = dateKeys.length > 0 ? rec[dateKeys[0]] : null;
      
      const hourKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('hora') || k.toLowerCase().includes('time') || k.toLowerCase().includes('hor'));
      const hourVal = hourKeys.length > 0 ? rec[hourKeys[0]] : null;
      
      const verKeys = Object.keys(rec).filter(k => k.toLowerCase().includes('ver') || k.toLowerCase().includes('act') || k.toLowerCase().includes('det') || k.toLowerCase().includes('obs'));
      const verVal = verKeys.length > 0 ? rec[verKeys[0]] : null;

      if (dateVal) {
        let cleanDate = String(dateVal).trim();
        if (cleanDate.includes('-')) {
          const parts = cleanDate.split('T')[0].split('-');
          if (parts.length === 3) {
            cleanDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
          }
        }
        
        return (
          <div className="mt-1.5 text-[9px] font-extrabold text-indigo-400 flex items-center gap-1.5 bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 rounded-xl w-fit" title={`Ruta DBF: ${data.path || ''}`}>
            🔄 ERP Act.: <span className="text-white">{cleanDate}</span> {hourVal ? <span className="text-indigo-300 font-medium">({hourVal})</span> : null} {verVal ? <span className="text-indigo-300 font-medium">| {verVal}</span> : null}
          </div>
        );
      }
    }
  } catch (e) {
    return (
      <div className="mt-1.5 text-[9px] font-semibold text-slate-400 bg-slate-500/5 border border-slate-500/10 px-2.5 py-1 rounded-xl w-fit">
        🔄 ERP Act.: {String(rawVal)}
      </div>
    );
  }
  return null;
};

const parseInlineStyles = (text: string) => {
  let parts: any[] = [text];
  
  if (text.includes('**')) {
    const boldRegex = /\*\*(.*?)\*\*/g;
    let match;
    let lastIndex = 0;
    const newParts = [];
    
    while ((match = boldRegex.exec(text)) !== null) {
      const before = text.substring(lastIndex, match.index);
      if (before) newParts.push(before);
      newParts.push(<strong key={match.index} className="font-extrabold text-white">{match[1]}</strong>);
      lastIndex = boldRegex.lastIndex;
    }
    const after = text.substring(lastIndex);
    if (after) newParts.push(after);
    parts = newParts;
  }
  
  return parts.map((part, i) => {
    if (typeof part !== 'string') return part;
    if (part.includes('`')) {
      const codeRegex = /`(.*?)`/g;
      let match;
      let lastIndex = 0;
      const codeParts = [];
      while ((match = codeRegex.exec(part)) !== null) {
        const before = part.substring(lastIndex, match.index);
        if (before) codeParts.push(before);
        codeParts.push(<code key={match.index} className="px-1.5 py-0.5 rounded bg-black/40 text-rose-400 font-mono text-xs">{match[1]}</code>);
        lastIndex = codeRegex.lastIndex;
      }
      const after = part.substring(lastIndex);
      if (after) codeParts.push(after);
      return <span key={i}>{codeParts}</span>;
    }
    return <span key={i}>{part}</span>;
  });
};

const renderAiAnalysisText = (text: string) => {
  if (!text) return null;
  const lines = text.split('\n');
  return (
    <div className="space-y-3.5 text-sm leading-relaxed text-slate-300">
      {lines.map((line, idx) => {
        let cleanLine = line.trim();
        if (cleanLine.startsWith('###')) {
          return <h3 key={idx} className="text-lg font-black text-white mt-5 mb-2 border-b border-white/5 pb-1 flex items-center gap-2">{cleanLine.replace('###', '').trim()}</h3>;
        }
        if (cleanLine.startsWith('####')) {
          return <h4 key={idx} className="text-base font-extrabold text-indigo-400 mt-4 mb-1.5">{cleanLine.replace('####', '').trim()}</h4>;
        }
        if (cleanLine.startsWith('*') || cleanLine.startsWith('-')) {
          const itemText = cleanLine.substring(1).trim();
          return (
            <div key={idx} className="flex items-start gap-2 pl-3 py-0.5">
              <span className="text-indigo-500 mt-1.5 text-xs">●</span>
              <span className="flex-1">{parseInlineStyles(itemText)}</span>
            </div>
          );
        }
        if (cleanLine.startsWith('>')) {
          let alertContent = cleanLine.substring(1).trim();
          let alertType = 'note';
          if (alertContent.includes('[!WARNING]') || alertContent.includes('[!CAUTION]')) {
            alertType = 'warning';
            alertContent = alertContent.replace(/\[!(WARNING|CAUTION)\]/g, '').trim();
          } else if (alertContent.includes('[!NOTE]') || alertContent.includes('[!TIP]') || alertContent.includes('[!IMPORTANT]')) {
            alertType = 'note';
            alertContent = alertContent.replace(/\[!(NOTE|TIP|IMPORTANT)\]/g, '').trim();
          }
          const bgClass = alertType === 'warning' ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' : 'bg-blue-500/10 border-blue-500/20 text-blue-400';
          return (
            <div key={idx} className={`p-4 rounded-2xl border text-xs font-semibold my-4 leading-relaxed ${bgClass}`}>
              {alertContent}
            </div>
          );
        }
        if (cleanLine === '') return <div key={idx} className="h-2" />;
        
        return <p key={idx} className="pl-1 text-slate-300">{parseInlineStyles(cleanLine)}</p>;
      })}
    </div>
  );
};

type StreamPreset = 'auto' | 'max' | 'balanced' | 'speed';

const STREAM_QUALITY_TIERS = [
  { max_width: 1024, webp_still: 54, webp_motion: 36 },
  { max_width: 1280, webp_still: 64, webp_motion: 44 },
  { max_width: 1920, webp_still: 80, webp_motion: 54 },
  { max_width: 0, webp_still: 90, webp_motion: 74 },
] as const;

function streamTierForManualPreset(p: Exclude<StreamPreset, 'auto'>): number {
  switch (p) {
    case 'speed': return 0;
    case 'balanced': return 2;
    case 'max': return 3;
  }
}

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('token'));
  const [userProfile, setUserProfile] = useState<any>(null);
  const [deferredPrompt, setDeferredPrompt] = useState<any>(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const [darkMode, setDarkMode] = useState(true);
  const [activeTab, setActiveTab] = useState('tickets');
  
  // === ESTADOS PARA BITÁCORA DE LOGS (TELEMETRÍA) ===
  const [telemetryLogs, setTelemetryLogs] = useState<any[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsAutoRefresh, setLogsAutoRefresh] = useState(true);
  const [logsFilterDevice, setLogsFilterDevice] = useState<string>('all');
  const [logsFilterLevel, setLogsFilterLevel] = useState<string>('all');
  const [logsFilterSource, setLogsFilterSource] = useState<string>('all');
  const [logsSearchTerm, setLogsSearchTerm] = useState('');

  // === ESTADOS PARA LOGS EN SOPORTE EN VIVO (STANDALONE) ===
  const [isDeviceLogsOpen, setIsDeviceLogsOpen] = useState(false);
  const [deviceLogs, setDeviceLogs] = useState<any[]>([]);
  const [deviceLogsLoading, setDeviceLogsLoading] = useState(false);

  const [globalSearchTerm, setGlobalSearchTerm] = useState('');
  const [licenses, setLicenses] = useState<any[]>([]);
  const [showLicenseModal, setShowLicenseModal] = useState(false);
  const [deviceNotesModal, setDeviceNotesModal] = useState<{ deviceId: number; name: string; notes: string } | null>(null);
  const [licClientId, setLicClientId] = useState<string>("");
  const [licMaxDevices, setLicMaxDevices] = useState<number>(5);
  const [licDurationDays, setLicDurationDays] = useState<number>(365);
  const [pendingDevices, setPendingDevices] = useState<any[]>([]);
  const [assignModal, setAssignModal] = useState<any | null>(null);
  const [assignClientId, setAssignClientId] = useState<string>("");
  const [assignSearchText, setAssignSearchText] = useState<string>("");
  const [showAssignDropdown, setShowAssignDropdown] = useState<boolean>(false);

  const [tickets, setTickets] = useState<any[]>([]);
  const [clients, setClients] = useState<any[]>([]);
  const [centinelas, setCentinelas] = useState<any>({});
  const [loading, setLoading] = useState(true);

  // Estados Modal Crear
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newClientId, setNewClientId] = useState("");
  const [newSubject, setNewSubject] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [newPriority] = useState("media");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Estados Clientes
  const [isClientModalOpen, setIsClientModalOpen] = useState(false);
  const [editingClient, setEditingClient] = useState<any>(null);
  
  // Integración ERP: Extracto de cuenta corriente
  const [showExtractoModal, setShowExtractoModal] = useState<{
    isOpen: boolean;
    client: any;
    data: any[];
    loading: boolean;
    desde: string;
    hasta: string;
  }>({
    isOpen: false,
    client: null,
    data: [],
    loading: false,
    desde: new Date(Date.now() - 150 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    hasta: new Date().toISOString().split('T')[0]
  });

  const handleOpenExtracto = async (client: any, customDesde?: string, customHasta?: string) => {
    const desdeVal = customDesde || showExtractoModal.desde;
    const hastaVal = customHasta || showExtractoModal.hasta;
    
    setShowExtractoModal(prev => ({
      ...prev,
      isOpen: true,
      client,
      data: [],
      loading: true,
      desde: desdeVal,
      hasta: hastaVal
    }));
    
    try {
      const desdeIso = new Date(desdeVal).toISOString();
      const hastaIso = new Date(hastaVal).toISOString();
      const res = await getClientExtracto(client.id, desdeIso, hastaIso);
      setShowExtractoModal(prev => ({
        ...prev,
        data: res.extracto || [],
        loading: false
      }));
    } catch (err: any) {
      alert(err.message || "Error consultando el extracto en el ERP.");
      setShowExtractoModal(prev => ({ ...prev, loading: false }));
    }
  };
  const [clientSearchTerm, setClientSearchTerm] = useState("");
  const [isSyncing, setIsSyncing] = useState(false);
  const [clientActiveTab, setClientActiveTab] = useState('basic');

  // === ESTADOS PARA LICENCIAS ERP (MYSQL) ===
  const [erpLicenses, setErpLicenses] = useState<any[]>([]);
  const [isErpLicensesLoading, setIsErpLicensesLoading] = useState(false);
  const [selectedErpSerial, setSelectedErpSerial] = useState<string | null>(null);
  const [erpTerminals, setErpTerminals] = useState<any[]>([]);
  const [isErpTerminalsLoading, setIsErpTerminalsLoading] = useState(false);
  const [erpTemplates, setErpTemplates] = useState<any[]>([]);
  const [showBannerConfigModal, setShowBannerConfigModal] = useState(false);
  const [bannerForm, setBannerForm] = useState({
    serial: '',
    m_down: false,
    m_newdate: '',
    m_tipmsg: 1,
    m_showmode: '01',
    m_text: ''
  });
  const [showNewSerialForm, setShowNewSerialForm] = useState(false);
  const [newSerialForm, setNewSerialForm] = useState({
    l_number: '',
    l_date: '',
    l_peri2016: 30,
    l_raso: '',
    l_nomfa: '',
    l_cuit: '',
    l_tele: '',
    l_locali: ''
  });

  const loadErpTemplates = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/templates`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpTemplates(data);
      }
    } catch (e) {
      console.error("Error loading ERP templates:", e);
    }
  };

  const loadErpLicenses = async (clientCode: string) => {
    setIsErpLicensesLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/client/${clientCode}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpLicenses(data);
        if (data.length > 0) {
          setSelectedErpSerial(data[0].l_number);
          loadErpTerminals(data[0].l_number);
        } else {
          setSelectedErpSerial(null);
          setErpTerminals([]);
        }
      }
    } catch (e) {
      console.error("Error loading ERP licenses:", e);
    } finally {
      setIsErpLicensesLoading(false);
    }
  };

  const loadErpTerminals = async (serial: string) => {
    setIsErpTerminalsLoading(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/terminals/${serial}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setErpTerminals(data);
      }
    } catch (e) {
      console.error("Error loading ERP terminals:", e);
    } finally {
      setIsErpTerminalsLoading(false);
    }
  };

  const handleToggleErpLicense = async (serial: string, currentDesact: boolean) => {
    const action = currentDesact ? "activar" : "desactivar";
    if (!window.confirm(`¿Está seguro de que desea ${action} la licencia ${serial}?`)) return;
    
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/toggle/${serial}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ l_desact: !currentDesact })
      });
      if (response.ok) {
        setShowNotification(`Licencia ${serial} ha sido ${currentDesact ? 'activada' : 'desactivada'}.`);
        setTimeout(() => setShowNotification(null), 3000);
        loadErpLicenses(clientForm.codigo);
      } else {
        alert("Error al cambiar estado de la licencia.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleSaveBannerConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/management`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(bannerForm)
      });
      if (response.ok) {
        setShowNotification("Configuración de cartel/bloqueo guardada con éxito.");
        setTimeout(() => setShowNotification(null), 3000);
        setShowBannerConfigModal(false);
        loadErpLicenses(clientForm.codigo);
      } else {
        alert("Error al guardar la configuración.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleExtendErpLicense = async (serial: string, days: number, currentExpDate: string) => {
    const newDays = prompt("Ingrese los días permitidos para renovar (auto-extensión):", String(days));
    if (newDays === null) return;
    
    const parsedDays = parseInt(newDays);
    if (isNaN(parsedDays)) {
      alert("Por favor ingrese un número válido.");
      return;
    }

    const changeDate = window.confirm("¿Desea modificar también la fecha de vencimiento?");
    let newExpiryDate = null;
    if (changeDate) {
      const inputDate = prompt("Ingrese la nueva fecha de vencimiento (YYYY-MM-DD):", currentExpDate);
      if (inputDate) {
        newExpiryDate = inputDate;
      }
    }

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/extension/${serial}`, {
        method: "PUT",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ days: parsedDays, expiry_date: newExpiryDate })
      });
      if (response.ok) {
        setShowNotification("Licencia extendida/actualizada correctamente.");
        setTimeout(() => setShowNotification(null), 3000);
        loadErpLicenses(clientForm.codigo);
      } else {
        alert("Error al extender la licencia.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleDeactivateErpNode = async (terminal: any) => {
    if (!window.confirm(`¿Seguro que desea desactivar el nodo PC "${terminal.t_id}" para el usuario "${terminal.t_user}"? Esta acción impedirá que este equipo use la licencia.`)) return;

    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/deactivate-node`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          serial: terminal.t_number,
          t_id_enc: terminal.t_id_enc,
          t_user_enc: terminal.t_user_enc,
          t_path_enc: terminal.t_path_enc
        })
      });
      if (response.ok) {
        setShowNotification(`El nodo "${terminal.t_id}" ha sido desactivado de forma permanente.`);
        setTimeout(() => setShowNotification(null), 3000);
        loadErpTerminals(terminal.t_number);
      } else {
        alert("Error al desactivar el nodo.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const handleCreateNewErpSerial = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/erp-licenses/new-serial`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(newSerialForm)
      });
      if (response.ok) {
        setShowNotification(`Serial ${newSerialForm.l_number} registrado con éxito.`);
        setTimeout(() => setShowNotification(null), 3000);
        setShowNewSerialForm(false);
        loadErpLicenses(clientForm.codigo);
      } else {
        const errData = await response.json();
        alert(errData.detail || "Error al crear el nuevo serial.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    }
  };

  const [clientForm, setClientForm] = useState({
    codigo: '',
    razon_social: '',
    nombre_fantasia: '',
    identificador_fiscal: '',
    cparte: '',
    version_apollo: '',
    telefono: '',
    email: '',
    localidad: '',
    fecha_vencimiento: '',
    modulos: 'Base, Facturación',
    apikey_apollo: '',
    remote_password: '',
    saldo: 0.0,
    vendedor_codigo: '',
    vendedor_nombre: '',
    clasificacion_codigo: '',
    clasificacion_nombre: '',
    extracto: '',
    cclifac: ''
  });

  useEffect(() => {
    if (clientActiveTab === 'erp_licensing' && clientForm.codigo) {
      loadErpLicenses(clientForm.codigo);
      loadErpTemplates();
    }
  }, [clientActiveTab, clientForm.codigo]);

  // Estados Modal Detalle + IA
  const [selectedTicket, setSelectedTicket] = useState<any>(null);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [newMessage, setNewMessage] = useState("");

  // Alertas Proactivas
  const [activeAlerts, setActiveAlerts] = useState<any>({});
  const [showNotification, setShowNotification] = useState<string | null>(null);
  const [nativeConnectionState, setNativeConnectionState] = useState<'idle' | 'connecting' | 'success' | 'error'>('idle');


  // Estados Centinela (Live View Multi-Sesión)
  const standaloneIdInit = new URLSearchParams(window.location.search).get('remote_device_id');
  const [activeSessions, setActiveSessions] = useState<any[]>(
    standaloneIdInit ? [{ id: parseInt(standaloneIdInit), device_name: "Cargando Terminal...", is_online: true }] : []
  );
  const [sessionFrames, setSessionFrames] = useState<Record<string, string>>({});
  const sessionFramesRef = useRef(sessionFrames);
  sessionFramesRef.current = sessionFrames;

  // ─── CALIDAD DE CONEXIÓN EN TIEMPO REAL ─────────────────────────────────
  // Mide FPS real y latencia de entrega de frames para mostrar al técnico
  const frameTimestampsRef = useRef<number[]>([]); // últimos timestamps de frames recibidos
  const [connectionFps, setConnectionFps] = useState<number>(0);
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>('disconnected');
  // wsViewerConnected: true cuando el WebSocket de video está activo (deshabilita el HTTP polling)
  const [wsViewerConnected, setWsViewerConnected] = useState<boolean>(false);
  // ───────────────────────────────────────────────────────────────────────────

  const [sessionCmds, setSessionCmds] = useState<Record<string, any>>({});
  const [sessionFiles, setSessionFiles] = useState<Record<string, any>>({});
  const [sessionChats, setSessionChats] = useState<Record<string, any[]>>({});
  const [chatVisibility, setChatVisibility] = useState<Record<string, boolean>>({});
  const [remoteClipboard, setRemoteClipboard] = useState<string>("");
  const [isControlEnabled, setIsControlEnabled] = useState<boolean>(true);
  const [isCapsLockActive, setIsCapsLockActive] = useState<boolean>(false);
  const [focusedSessionId, setFocusedSessionId] = useState<number | null>(null);

  // ─── MULTI-MONITOR ──────────────────────────────────────────────────────────
  // activeMonitor: monitor que el agente está capturando actualmente (1-based)
  // monitorCount: cantidad de monitores detectados en el PC remoto (viene de telemetría)
  const [activeMonitor, setActiveMonitor] = useState<number>(1);
  const [monitorCount, setMonitorCount] = useState<number>(1);

  // Cambiar monitor remotamente enviando set_monitor al agente
  const switchMonitor = async (sessionId: number, monitorIndex: number) => {
    setActiveMonitor(monitorIndex);
    await sendCentinelaControl(sessionId, { type: 'set_monitor', index: monitorIndex });
  };
  // ────────────────────────────────────────────────────────────────────────────

  // ─── FULLSCREEN REAL DEL VISOR REMOTO ───────────────────────────────────────
  // Cubre todo el monitor con SOLO la imagen remota + barra flotante auto-oculta
  const [isViewerFullscreen, setIsViewerFullscreen] = useState<boolean>(false);
  const [toolbarVisible, setToolbarVisible] = useState<boolean>(true);
  const toolbarTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enterViewerFullscreen = () => {
    setIsViewerFullscreen(true);
    setToolbarVisible(true);
    resetToolbarTimer();
    // También pedir fullscreen nativo del navegador para eliminar la barra de dirección
    document.documentElement.requestFullscreen().catch(() => {});
  };

  const exitViewerFullscreen = () => {
    setIsViewerFullscreen(false);
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
  };

  const resetToolbarTimer = () => {
    if (toolbarTimerRef.current) clearTimeout(toolbarTimerRef.current);
    setToolbarVisible(true);
    toolbarTimerRef.current = setTimeout(() => {
      setToolbarVisible(false);
    }, 3000); // Ocultar barra 3s después de la última acción del mouse
  };

  // Salir con Escape también cuando está en viewer fullscreen
  useEffect(() => {
    const handleKeyEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isViewerFullscreen) {
        exitViewerFullscreen();
      }
    };
    document.addEventListener('keydown', handleKeyEsc);
    return () => document.removeEventListener('keydown', handleKeyEsc);
  }, [isViewerFullscreen]);

  // Sincronizar si el usuario sale del fullscreen nativo del browser (F11 o barra del browser)
  useEffect(() => {
    const handleFsChange = () => {
      if (!document.fullscreenElement && isViewerFullscreen) {
        setIsViewerFullscreen(false);
      }
      // Forzar frame fresco en el agente tras cualquier cambio de fullscreen
      // (el viewport cambia de tamaño y el último frame queda "congelado")
      const _sid = new URLSearchParams(window.location.search).get('remote_device_id');
      const targetId = _sid ? parseInt(_sid) : focusedSessionId;
      if (targetId) {
        setTimeout(() => {
          sendCentinelaControl(targetId, { type: 'refresh_frame' });
        }, 200); // 200ms para que el browser termine la transición
      }

    };
    document.addEventListener('fullscreenchange', handleFsChange);
    return () => document.removeEventListener('fullscreenchange', handleFsChange);
  }, [isViewerFullscreen, focusedSessionId]);



  // ─── WEBSOCKET DE VIDEO (reemplaza HTTP polling para standalone) ───────────
  // Para el modo standalone (ventana de soporte individual), usamos WS push.
  // El hook maneja reconexión automática, ping y calidad en tiempo real.
  const standaloneDeviceId = standaloneIdInit ? parseInt(standaloneIdInit) : null;

  // ── LIVE VIDEO REF ─────────────────────────────────────────────────────────
  // Bypass React state para video en vivo: en lugar de setSessionFrames()
  // (que dispara un re-render completo en cada frame a 25 FPS), actualizamos
  // img.src directamente via DOM ref — 0ms de overhead React por frame.
  //
  // latestLiveFrameRef: guarda el último src para que si React re-renderiza
  //   por OTRA razón (ej: cambio de FPS indicator), el img no quede en blanco.
  //
  // ROLLBACK: cambiar applyFrame para que solo llame setSessionFrames(prev=>(...)
  //   y eliminar ref={setLiveImgRef} de los img tags.
  const liveCanvasRef       = useRef<HTMLCanvasElement | null>(null);
  const latestLiveFrameRef = useRef<string>('');   // último base64 para re-renders de React
  const rafIdRef         = useRef<number | null>(null);

  // Callback ref compartido
  const setLiveCanvasRef = (el: HTMLCanvasElement | null) => {
    liveCanvasRef.current = el;
  };

  const frameQueueRef = useRef<{base64: string, delta?: import('./api').DeltaMeta}[]>([]);
  const isProcessingQueueRef = useRef(false);

  const processFrameQueue = () => {
    if (isProcessingQueueRef.current || frameQueueRef.current.length === 0) return;
    isProcessingQueueRef.current = true;

    const frame = frameQueueRef.current.shift();
    if (!frame) {
      isProcessingQueueRef.current = false;
      return;
    }

    const img = new window.Image();
    img.src = `data:image/webp;base64,${frame.base64}`;
    img.decode().then(() => {
      requestAnimationFrame(() => {
        if (liveCanvasRef.current) {
          const ctx = liveCanvasRef.current.getContext('2d', { alpha: false });
          if (ctx) {
            if (!frame.delta && liveCanvasRef.current.width !== img.width) {
              liveCanvasRef.current.width = img.width;
              liveCanvasRef.current.height = img.height;
            }
            if (frame.delta) {
              ctx.drawImage(img, frame.delta.x, frame.delta.y, frame.delta.w, frame.delta.h);
            } else {
              ctx.drawImage(img, 0, 0);
            }
          }
        }
        isProcessingQueueRef.current = false;
        processFrameQueue();
      });
    }).catch((err) => {
      console.error(err);
      isProcessingQueueRef.current = false;
      processFrameQueue();
    });
  };

  const applyFrame = (base64: string, delta?: import('./api').DeltaMeta) => {
    const devId = standaloneDeviceId ?? activeSessions[0]?.id;
    if (!devId) return;

    // Guardar siempre para que re-renders de React tengan el frame correcto
    latestLiveFrameRef.current = base64;

    if (liveCanvasRef.current) {
      frameQueueRef.current.push({ base64, delta });
      processFrameQueue();
    } else {
      // ── FALLBACK: img no montada aún (primera conexión) ─────────────────
      setSessionFrames(prev => ({ ...prev, [devId]: base64 }));
    }
  };
  // ── FIN LIVE VIDEO REF ─────────────────────────────────────────────────────



  const handleViewerMessage = useCallback((msg: Record<string, unknown>) => {
    if (msg.type === 'session_list') {
      type WS = { id: number; name: string; username: string; state: string; current: boolean; };
      setWinSessions((msg.sessions as WS[]) ?? []);
    } else if (msg.type === 'session_switching') {
      setSessionSwitching(true);
    } else if (msg.type === 'login_result') {
      if (msg.success) {
        setSessionSwitching(true);
        setShowLoginModal(false);
      } else {
        setLoginError((msg.error as string) ?? 'Credenciales inválidas');
        setLoginLoading(false);
      }
    }
  }, []);

  const { sendCommand: sendViewerCommand } = useViewerWebSocket({
    deviceId: standaloneDeviceId ?? (activeSessions.length === 1 ? activeSessions[0].id : null),
    enabled: isAuthenticated && (!!standaloneDeviceId || activeSessions.length === 1),
    onFrame: (base64, delta) => {
      applyFrame(base64, delta);
      setWsViewerConnected(true);
    },
    onQuality: (fps, quality) => {
      setConnectionFps(fps);
      setConnectionQuality(quality);
    },
    onMessage: handleViewerMessage,
    onClose: () => setWsViewerConnected(false),
  });

  const connectionFpsRef = useRef(0);
  useEffect(() => {
    connectionFpsRef.current = connectionFps;
  }, [connectionFps]);

  const viewerStreamDeviceId = standaloneDeviceId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
  const streamPresetStorageKey = viewerStreamDeviceId != null ? `apollo_stream_preset_${viewerStreamDeviceId}` : null;
  const [streamPreset, setStreamPreset] = useState<StreamPreset>('auto');

  // ── ALTO RENDIMIENTO (HQ MODE) ──────────────────────────────────────────────
  const hqDeviceId = standaloneDeviceId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
  const hqStorageKey = hqDeviceId ? `hq_mode_${hqDeviceId}` : null;

  const [hqEnabled, setHqEnabled] = useState<boolean>(() =>
    hqStorageKey ? localStorage.getItem(hqStorageKey) === 'true' : false
  );
  const [hqState, setHqState] = useState<'connecting' | 'open' | 'closed' | 'off'>(() => 
    (hqStorageKey && localStorage.getItem(hqStorageKey) === 'true') ? 'open' : 'off'
  );
  const [hqReconnectAttempt, setHqReconnectAttempt] = useState(0);
  // ────────────────────────────────────────────────────────────────────────────

  useEffect(() => {
    if (!streamPresetStorageKey) return;
    const v = localStorage.getItem(streamPresetStorageKey);
    if (v === 'auto' || v === 'max' || v === 'balanced' || v === 'speed') setStreamPreset(v);
  }, [streamPresetStorageKey]);

  useEffect(() => {
    if (!streamPresetStorageKey) return;
    localStorage.setItem(streamPresetStorageKey, streamPreset);
  }, [streamPreset, streamPresetStorageKey]);

  const streamAutoTierRef = useRef(3);
  const streamLowFpsStreakRef = useRef(0);
  const streamHighFpsStreakRef = useRef(0);

  const sendStreamTier = useCallback(
    (tierIdx: number) => {
      const t = STREAM_QUALITY_TIERS[Math.max(0, Math.min(3, tierIdx))];
      sendViewerCommand({
        type: 'set_stream_params',
        max_width: t.max_width,
        webp_still: t.webp_still,
        webp_motion: t.webp_motion,
      });
    },
    [sendViewerCommand],
  );

  useEffect(() => {
    if (!wsViewerConnected || !viewerStreamDeviceId) return;
    if (streamPreset !== 'auto') {
      const idx = streamTierForManualPreset(streamPreset);
      streamAutoTierRef.current = idx;
      sendStreamTier(idx);
    }
  }, [wsViewerConnected, viewerStreamDeviceId, streamPreset, sendStreamTier]);

  useEffect(() => {
    if (!wsViewerConnected || !viewerStreamDeviceId || streamPreset !== 'auto' || hqEnabled) return;
    streamAutoTierRef.current = 3;
    streamLowFpsStreakRef.current = 0;
    streamHighFpsStreakRef.current = 0;
    sendStreamTier(3);
    const id = window.setInterval(() => {
      const fps = connectionFpsRef.current;
      let t = streamAutoTierRef.current;
      if (fps < REMOTE_STREAM_WORKABLE_FPS) {
        streamLowFpsStreakRef.current += 1;
        streamHighFpsStreakRef.current = 0;
        const urgent = fps <= 3;
        const needDown =
          urgent ? streamLowFpsStreakRef.current >= 1 : streamLowFpsStreakRef.current >= 2;
        if (needDown && t > 0) {
          t -= 1;
          streamLowFpsStreakRef.current = 0;
        }
      } else {
        streamLowFpsStreakRef.current = 0;
        if (fps >= REMOTE_STREAM_COMFORTABLE_FPS) {
          streamHighFpsStreakRef.current += 1;
          if (streamHighFpsStreakRef.current >= 3 && t < 3) {
            t += 1;
            streamHighFpsStreakRef.current = 0;
          }
        } else {
          streamHighFpsStreakRef.current = 0;
        }
      }
      if (t !== streamAutoTierRef.current) {
        streamAutoTierRef.current = t;
        sendStreamTier(t);
      }
    }, 2000);
    return () => window.clearInterval(id);
  }, [wsViewerConnected, viewerStreamDeviceId, streamPreset, hqEnabled, sendStreamTier]);

  /* Stream quality selector (compact, reused in header + fullscreen bar) */
  const streamQualitySelect = activeSessions.length === 1 ? (
    <select
      value={streamPreset}
      onChange={(e) => setStreamPreset(e.target.value as StreamPreset)}
      className="bg-slate-800/90 border border-white/10 rounded-lg text-[10px] sm:text-xs text-slate-200 px-2 py-1.5 max-w-[128px] sm:max-w-none"
      title={`Calidad WebP remoto. Auto baja si <${REMOTE_STREAM_WORKABLE_FPS} FPS (piso para trabajo). Máxima = resolución nativa.`}
    >
      <option value="auto">Calidad · Auto</option>
      <option value="max">Calidad · Máxima</option>
      <option value="balanced">Calidad · Equilibrada</option>
      <option value="speed">Calidad · Velocidad</option>
    </select>
  ) : null;

  // Pedir lista de sesiones al conectar (con retry)
  useEffect(() => {
    if (!wsViewerConnected) return;
    sendViewerCommand({ type: 'get_sessions' });
  }, [wsViewerConnected, sendViewerCommand]);

  // ─── SESIONES WINDOWS ─────────────────────────────────────────────────
  type WinSession = { id: number; name: string; username: string; state: string; current: boolean; };
  const [winSessions, setWinSessions] = useState<WinSession[]>([]);
  const [showSessionPicker, setShowSessionPicker] = useState(false);
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [loginCreds, setLoginCreds] = useState({ username: '', password: '', domain: '.' });
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [sessionSwitching, setSessionSwitching] = useState(false);
  // ─────────────────────────────────────────────────────────────────────

  // Refs eliminados para MSE (usando MJPEG nativo)

  const logFrontendToBackend = useCallback(async (message: string, level: string = 'INFO') => {
    if (!hqDeviceId) return;
    try {
      const token = localStorage.getItem('token');
      const authHeader = token ? `Bearer ${token}` : '';
      const { API_URL } = await import('./api');
      await fetch(`${API_URL}/centinelas/logs/frontend?device_id=${hqDeviceId}&message=${encodeURIComponent(message)}&level=${level}`, {
        method: 'POST',
        headers: {
          'Authorization': authHeader
        }
      });
    } catch (err) {
      console.error('Error logging to backend:', err);
    }
  }, [hqDeviceId]);

  // Capturador global de excepciones, errores y rechazos de promesas en la consola para telemetría
  useEffect(() => {
    if (!hqDeviceId) return;

    const handleGlobalError = (event: ErrorEvent) => {
      const msg = `[FRONTEND-CONSOLA-ERROR] ${event.message || 'Error sin mensaje'} en ${event.filename || 'desconocido'}:${event.lineno || 0}:${event.colno || 0}`;
      logFrontendToBackend(msg, 'ERROR');
    };

    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      const errorMsg = event.reason?.message || (typeof event.reason === 'object' ? JSON.stringify(event.reason) : String(event.reason));
      const msg = `[FRONTEND-CONSOLA-RECHAZO] Promesa no manejada: ${errorMsg}`;
      logFrontendToBackend(msg, 'ERROR');
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
    
    // Log de confirmación de versión
    logFrontendToBackend('[FRONTEND-TELEMETRÍA] Telemetría global de consola activada en el visor (v3.1.2-HQ)', 'INFO');

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [hqDeviceId, logFrontendToBackend]);

  // MSE and useHqViewerWebSocket have been removed in favor of MJPEG Turbo
  // via the standard viewer websocket.

  const toggleHqMode = () => {
    const next = !hqEnabled;
    setHqEnabled(next);
    setHqState(next ? 'open' : 'off');
    if (hqStorageKey) localStorage.setItem(hqStorageKey, String(next));
    
    // Notificar al backend/agente que active/desactive la transmision MJPEG HQ
    sendViewerCommand({ type: next ? 'start_hq' : 'stop_hq' });
  };
  
  const handleAltViewer = (e: React.MouseEvent) => {
    e.preventDefault();
    if (!hqDeviceId) return;
    
    // Buscar el dispositivo en activeSessions o buscarlo en la DB si estuviera disponible.
    // Asumimos que activeSessions[0] es el dispositivo actual en la vista remota principal.
    const activeDevice = standaloneDeviceId 
        ? null 
        : activeSessions.find(s => s.id === hqDeviceId);
        
    let id = activeDevice?.alt_remote_id || null;
    const storageKey = `alt_viewer_id_${hqDeviceId}`;
    
    if (!id) {
        id = localStorage.getItem(storageKey);
    }
    
    // Si presiona Shift o Ctrl, o no hay ID, pedimos uno nuevo
    if (!id || e.shiftKey || e.ctrlKey) {
      const promptText = id 
        ? `ID actual de RustDesk/Nativo: ${id}\nIngrese el nuevo ID de conexión nativa (en blanco para borrar):` 
        : `No se detectó un ID nativo automáticamente desde el Centinela.\nIngrese el ID de la conexión nativa de RustDesk manualmente:`;
      const newId = prompt(promptText, id || '');
      if (newId !== null) {
        id = newId.replace(/\s+/g, ''); // Limpiar espacios
        if (id) {
            localStorage.setItem(storageKey, id);
        } else {
            localStorage.removeItem(storageKey);
            return;
        }
      } else {
        return; // Cancelado
      }
    }

    if (id) {
      setNativeConnectionState('connecting');

      // 1. Usar un iframe oculto para abrir el protocolo sin recargar la página y evitar que el WebSocket se desconecte.
      let iframe = document.getElementById('native-protocol-iframe') as HTMLIFrameElement;
      if (!iframe) {
        iframe = document.createElement('iframe');
        iframe.id = 'native-protocol-iframe';
        iframe.style.display = 'none';
        document.body.appendChild(iframe);
      }
      iframe.src = `rustdesk://${id}`;

      // 2. Detección inteligente de lanzamiento exitoso:
      // Si el navegador abre con éxito la aplicación de RustDesk, la ventana del navegador perderá el foco (blur).
      // Si no la tiene instalada, el foco no se perderá nunca.
      let hasBlurred = false;
      const handleBlur = () => {
        hasBlurred = true;
      };
      window.addEventListener('blur', handleBlur);

      setTimeout(() => {
        window.removeEventListener('blur', handleBlur);
        if (hasBlurred) {
          setNativeConnectionState('success');
          // Volver a estado normal después de 4 segundos
          setTimeout(() => setNativeConnectionState('idle'), 4000);
        } else {
          setNativeConnectionState('error');
          alert(`❌ No se pudo abrir RustDesk automáticamente (ID: ${id})\n\n` +
                `Razones posibles:\n` +
                `1. No tienes la aplicación de RustDesk instalada en esta computadora.\n` +
                `2. RustDesk no tiene registrado su protocolo "rustdesk://" en tu Windows.\n\n` +
                `Por favor, abre la aplicación de RustDesk manualmente en tu PC e introduce el ID: ${id}`);
          setTimeout(() => setNativeConnectionState('idle'), 5000);
        }
      }, 1500);
    }
  };

  const getNativeButtonStyles = () => {
    switch (nativeConnectionState) {
      case 'connecting':
        return 'bg-amber-600 border-amber-500/30 text-amber-100 animate-pulse';
      case 'success':
        return 'bg-emerald-600 border-emerald-500/30 text-white shadow-emerald-500/20';
      case 'error':
        return 'bg-rose-600 border-rose-500/30 text-white shadow-rose-500/20';
      default:
        return 'bg-blue-600/80 border-blue-500/30 text-white hover:bg-blue-500/80';
    }
  };

  const getNativeButtonText = (short: boolean = false) => {
    switch (nativeConnectionState) {
      case 'connecting':
        return short ? 'Abriendo...' : '🚀 Abriendo...';
      case 'success':
        return short ? 'Conectado' : '✅ ¡Abierto!';
      case 'error':
        return short ? 'Error' : '❌ Error';
      default:
        return short ? 'Visor Nativo' : '🚀 Visor Nativo';
    }
  };


  
  useEffect(() => {
    if (wsViewerConnected && hqEnabled) {
      sendViewerCommand({ type: 'start_hq' });
    }
  }, [wsViewerConnected, hqEnabled, sendViewerCommand]);
  // ── FIN ALTO RENDIMIENTO ────────────────────────────────────────────────────




  // ─── NOTIFICACIONES DEL NAVEGADOR (Browser Notifications API) ─────────────
  // Solicita permiso al cargar y dispara alertas cuando un dispositivo cambia de estado
  const notificationPermissionRef = useRef<NotificationPermission>('default');

  useEffect(() => {
    // Pedir permiso de notificaciones al inicio de sesión autenticada
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission().then(p => {
        notificationPermissionRef.current = p;
      });
    } else if ('Notification' in window) {
      notificationPermissionRef.current = Notification.permission;
    }
  }, []);

  const sendBrowserNotification = (title: string, body: string, icon?: string) => {
    if ('Notification' in window && notificationPermissionRef.current === 'granted') {
      const n = new Notification(title, {
        body,
        icon: icon || '/apollo_logo.png',
        badge: '/apollo_logo.png',
        tag: title, // Agrupa notificaciones del mismo tipo (no spamea)
        silent: false,
      });
      // Auto-cerrar en 8 segundos
      setTimeout(() => n.close(), 8000);
      // También reproducir sonido sutil
      try {
        const ctx = new AudioContext();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.setValueAtTime(1100, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4);
        osc.start(ctx.currentTime);
        osc.stop(ctx.currentTime + 0.4);
      } catch (_) {}
    }
  };
  // ───────────────────────────────────────────────────────────────

  // Sincronizar título de ventana con Nombre de PC y Cliente de forma robusta
  useEffect(() => {
    if (standaloneIdInit && activeSessions.length > 0) {
      const session = activeSessions[0];
      if (session && session.device_name && session.device_name !== "Cargando Terminal...") {
        const clientName = session.client_name || session.razon_social || "Cliente";
        document.title = `🔴 [${clientName}] - ${session.device_name} | ApolloSupport`;
      }
    }
  }, [standaloneIdInit, activeSessions]);

  // Sincronizar foco activo automático de teclado
  useEffect(() => {
    if (activeSessions.length === 1) {
      setFocusedSessionId(activeSessions[0].id);
    } else if (activeSessions.length === 0) {
      setFocusedSessionId(null);
    }
  }, [activeSessions]);

  // Nuevos estados para Intervenciones
  const [interventions, setInterventions] = useState<any[]>([]);
  const [transferAreaId, setTransferAreaId] = useState<number | null>(null);
  const [attachment, setAttachment] = useState<File | null>(null);
  const [attachmentUrl, setAttachmentUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);

  const [areas, setAreas] = useState<any[]>([]);
  const [selectedArea, setSelectedArea] = useState<number | null>(null);

  // Estados de Personal, ABM y Perfil (NUEVO)
  const [users, setUsers] = useState<any[]>([]);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showUserAbmModal, setShowUserAbmModal] = useState(false);
  const [selectedUserForEdit, setSelectedUserForEdit] = useState<any>(null); // null para nuevo, user para editar
  const [profileForm, setProfileForm] = useState({
    nombre: '',
    full_name: '',
    celular: '',
    departamento: '',
    password: '',
    profile_picture: ''
  });
  const [userAbmForm, setUserAbmForm] = useState({
    nombre: '',
    email: '',
    full_name: '',
    password: '',
    rol: 'soporte',
    celular: '',
    departamento: 'Atención al Cliente',
    profile_picture: '',
    activo: true
  });

  // Estados de Historial de Sesión y Reporte IA (NUEVO)
  const [lastSupportSession, setLastSupportSession] = useState<any>(null);
  const [isLastSessionBannerDismissed, setIsLastSessionBannerDismissed] = useState<boolean>(false);
  const [showEndSessionModal, setShowEndSessionModal] = useState<boolean>(false);
  const [endSessionComment, setEndSessionComment] = useState<string>("");
  const [endSessionResult, setEndSessionResult] = useState<any>(null);
  const [isFinishingSession, setIsFinishingSession] = useState<boolean>(false);

  useEffect(() => {
    if (darkMode) document.body.classList.add('dark');
    else document.body.classList.remove('dark');
  }, [darkMode]);

  // --- DETECTOR DE INACTIVIDAD (Cierre de sesión automático tras 1 hora) ---
  const lastActivityRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!isAuthenticated) return;

    // Inicializar el tiempo de última actividad
    lastActivityRef.current = Date.now();

    const handleUserInteraction = () => {
      lastActivityRef.current = Date.now();
    };

    // Escuchar eventos globales de interacción física del usuario
    const events = ['mousemove', 'keydown', 'mousedown', 'scroll', 'touchstart'];
    events.forEach(event => {
      window.addEventListener(event, handleUserInteraction, { passive: true });
    });

    // Validar inactividad cada 10 segundos
    const checkInterval = setInterval(() => {
      const inactiveDuration = Date.now() - lastActivityRef.current;
      const oneHourMs = 1 * 60 * 60 * 1000; // 1 hora en ms

      if (inactiveDuration >= oneHourMs) {
        clearInterval(checkInterval);
        handleLogout();
        alert("🔒 Su sesión ha sido cerrada automáticamente por inactividad de más de 1 hora.");
      }
    }, 10000);

    return () => {
      events.forEach(event => {
        window.removeEventListener(event, handleUserInteraction);
      });
      clearInterval(checkInterval);
    };
  }, [isAuthenticated]);

  useEffect(() => {
    if (isAuthenticated) {
      const stored = localStorage.getItem('user');
      if (stored) {
        try {
          setUserProfile(JSON.parse(stored));
        } catch (e) {
          console.error("Error parsing user profile", e);
          handleLogout();
        }
      }
      loadData();
    }
  }, [isAuthenticated, selectedArea]);

  const loadData = () => {
    setLoading(true);
    Promise.all([
      getTickets(selectedArea || undefined),
      getClients(),
      getAreas(),
      getPendingCentinelas(),
      getUsers().catch(() => []) // Silencioso para evitar crash si hay problemas
    ]).then(([tData, cData, aData, pData, uData]) => {
      setTickets(tData);
      setClients(cData);
      setAreas(aData);
      setPendingDevices(pData || []);
      setUsers(uData || []);
      setLoading(false);
    }).catch((err) => {
      setLoading(false);
      if (err?.message === 'Sesión Expirada' || err?.message?.includes('401')) {
        handleLogout();
      } else {
        console.error("Error cargando datos:", err);
      }
    });
  }

  // Actualizar automáticamente la tarea y página del usuario en tiempo real
  useEffect(() => {
    if (isAuthenticated && userProfile) {
      let task = "Revisando el panel";
      let page = "Dashboard";
      
      if (activeTab === 'tickets') {
        page = "Bandeja Unificada";
        task = selectedArea ? `Viendo tickets de Sector: ${areas.find(a => a.id === selectedArea)?.nombre || ''}` : "Revisando Bandeja Unificada";
      } else if (activeTab === 'monitor') {
        page = "Terminal Remota";
        task = activeSessions.length > 0 
          ? `Asistiendo a PC: ${activeSessions.map(s => s.device_name).join(', ')}` 
          : "Explorando Flota de Terminales";
      } else if (activeTab === 'clients') {
        page = "Base Clientes";
        task = "Buscando/Editando Clientes";
      } else if (activeTab === 'licenses') {
        page = "Licencias";
        task = "Administrando Licencias Centinela";
      } else if (activeTab === 'settings') {
        page = "Ajustes";
        task = "Ajustando Configuración";
      } else if (activeTab === 'personnel') {
        page = "Plantel de Personal";
        task = "Monitoreando Actividad del Personal";
      }
      
      updateUserStatus(true, task, page)
        .then((updatedUser) => {
          // Mantener perfil sincronizado localmente con campos nuevos
          const stored = localStorage.getItem('user');
          if (stored) {
            const parsed = JSON.parse(stored);
            const merged = { ...parsed, ...updatedUser };
            localStorage.setItem('user', JSON.stringify(merged));
            setUserProfile(merged);
          }
        })
        .catch(err => console.error("Error actualizando estado online", err));
    }
  }, [activeTab, selectedArea, activeSessions, isAuthenticated]);

  // Heartbeat de actividad de personal y recarga de plantel
  useEffect(() => {
    let interval: any;
    if (isAuthenticated) {
      interval = setInterval(async () => {
        try {
          // Enviar heartbeat para mantener el estado is_online = True
          await updateUserStatus(true);
          
          // Si está en la pestaña de personal, recargar la lista para ver actividad en vivo
          if (activeTab === 'personnel') {
            const uData = await getUsers();
            setUsers(uData);
          }
        } catch (e) {
          console.error("Heartbeat error:", e);
        }
      }, 15000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab]);

  // Parámetro de URL para modo Ventana Independiente (Standalone Remote Window)
  const params = new URLSearchParams(window.location.search);
  const standaloneId = params.get('remote_device_id');

  useEffect(() => {
    let interval: any;
    if (isAuthenticated && (activeTab === 'monitor' || standaloneId)) {
      const fetchTelemetry = async () => {
        try {
          const telemetryData = await getActiveCentinelas();
          setCentinelas(telemetryData);
          const clientsData = await getClients();
          setClients(clientsData);
          const pendingData = await getPendingCentinelas();
          setPendingDevices(pendingData || []);

          if (standaloneId) {
            const devId = parseInt(standaloneId);
            let matchedDev = clientsData.flatMap((c: any) => c.devices || []).find((d: any) => d.id === devId);
            if (!matchedDev && pendingData) {
              matchedDev = pendingData.find((d: any) => d.id === devId);
            }
            if (matchedDev) {
              setActiveSessions([{ id: devId, device_name: matchedDev.device_name, ...matchedDev }]);
              const client = clientsData.find((c: any) => c.id === matchedDev.client_id);
              const clientName = client ? client.razon_social : "Cliente Pendiente";
              document.title = `🔴 ${matchedDev.device_name} - ${clientName} | ApolloSupport`;

              // Leer cantidad de monitores desde la telemetría en vivo del agente
              const liveTelem = telemetryData[String(devId)];
              if (liveTelem?.monitor_count) {
                setMonitorCount(liveTelem.monitor_count);
              }
            }
          }
        } catch (e: any) {
          if (e?.message === 'Sesión Expirada' || e?.message?.includes('401')) {
            handleLogout();
          } else {
            console.error("Error en telemetría:", e);
          }
        }
      };
      fetchTelemetry();
      interval = setInterval(fetchTelemetry, 3000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeTab, standaloneId]);

  // Poller de Chat en tiempo real para sesiones activas
  useEffect(() => {
    let interval: any;
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const isChatVisible = chatVisibility[String(devId)];
      if (isChatVisible) {
        const pollChat = () => {
          fetchChatHistory(devId);
        };
        pollChat();
        interval = setInterval(pollChat, 2000); // Polling cada 2 segundos
      }
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, standaloneId, chatVisibility]);

  // Poller de Portapapeles Remoto
  useEffect(() => {
    let interval: any;
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const pollClipboard = async () => {
        try {
          const text = await getCentinelaClipboard(devId);
          if (text !== undefined && text !== remoteClipboard) {
            setRemoteClipboard(text);
          }
        } catch (err) {
          console.error("Error polling clipboard", err);
        }
      };
      pollClipboard();
      interval = setInterval(pollClipboard, 3000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, standaloneId, remoteClipboard]);

  // Polling de frames — FALLBACK para multi-sesión o cuando el WS no está disponible.
  // Con 1 sesión y WS activo, el hook useViewerWebSocket ya entrega los frames por push.
  useEffect(() => {
    let active = true;
    let timeoutId: any;

    // Si el WS viewer está activo y solo hay 1 sesión, el WS ya está entregando frames.
    // El polling solo corre para multi-sesión o como fallback si el WS no conectó.
    const usePolling = isAuthenticated && activeSessions.length > 0 &&
      (activeSessions.length > 1 || !wsViewerConnected);

    if (usePolling) {
      const fetchFrames = async () => {
        if (!active) return;
        let changed = false;
        const updatedFrames: Record<string, string> = {};

        try {
          const fetchStart = performance.now();
          await Promise.all(activeSessions.map(async (s) => {
            const frame = await getCentinelaFrame(s.id);
            if (frame && frame !== sessionFramesRef.current[s.id]) {
              updatedFrames[s.id] = frame;
              changed = true;

              // Registrar timestamp de frame recibido para cálculo de FPS
              const now = performance.now();
              frameTimestampsRef.current.push(now);
              // Mantener solo los últimos 2 segundos de frames
              const twoSecsAgo = now - 2000;
              frameTimestampsRef.current = frameTimestampsRef.current.filter(t => t > twoSecsAgo);

              // Calcular FPS y calidad
              const fps = Math.round(frameTimestampsRef.current.length / 2);
              setConnectionFps(fps);
              setConnectionQuality(connectionQualityFromFps(fps));
            }
          }));

          if (changed && active) {
            setSessionFrames(prev => ({ ...prev, ...updatedFrames }));
          }
        } catch (err) {
          console.error("Error fetching frames", err);
        }

        if (active) {
          timeoutId = setTimeout(fetchFrames, 100);
        }
      };

      fetchFrames();
    } else {
      // Sin sesiones activas → resetear calidad
      setConnectionFps(0);
      setConnectionQuality('disconnected');
    }

    return () => {
      active = false;
      if (timeoutId) clearTimeout(timeoutId);
    };
  }, [isAuthenticated, activeSessions, wsViewerConnected]);

  useEffect(() => {
    const targetSessionId = standaloneId ? parseInt(standaloneId) : focusedSessionId;
    if (!targetSessionId) return;

    const handleKeyDown = async (e: KeyboardEvent) => {
      if (!isControlEnabled) return;
      const activeEl = document.activeElement;
      if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {
        return; // Ignorar si el usuario está escribiendo en el chat o en la consola del frontend
      }

      // 1. Ignorar si es una tecla modificadora sola
      if (['Shift', 'Control', 'Alt', 'Meta', 'CapsLock'].includes(e.key)) {
        return;
      }

      // Actualizar estado de CapsLock
      const isCaps = e.getModifierState && e.getModifierState('CapsLock');
      if (isCaps !== undefined) {
        setIsCapsLockActive(isCaps);
      }

      const isPaste = (e.ctrlKey || e.metaKey) && (e.key === 'v' || e.key === 'V');
      const isCopy = (e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'C');

      if (isPaste) {
        e.preventDefault();
        try {
          const text = await navigator.clipboard.readText();
          if (text) {
            await syncRemoteClipboard(targetSessionId, text);
          }
        } catch (err) {
          console.error("No se pudo leer el portapapeles local", err);
        }
        await sendCentinelaControl(targetSessionId, {
          type: 'key_press',
          key: 'ctrl+v'
        });
        return;
      }

      if (isCopy) {
        e.preventDefault();
        await sendCentinelaControl(targetSessionId, {
          type: 'key_press',
          key: 'ctrl+c'
        });
        // Esperar brevemente a que el agente actualice el portapapeles en el servidor y traerlo
        setTimeout(async () => {
          try {
            const text = await getCentinelaClipboard(targetSessionId);
            if (text) {
              setRemoteClipboard(text);
              await navigator.clipboard.writeText(text);
              setShowNotification("Portapapeles copiado al local.");
            }
          } catch (err) {}
        }, 500);
        return;
      }

      const specialKeys: Record<string, string> = {
        'ArrowUp': 'up',
        'ArrowDown': 'down',
        'ArrowLeft': 'left',
        'ArrowRight': 'right',
        'Escape': 'escape',
        'Tab': 'tab',
        'Backspace': 'backspace',
        ' ': 'space',
        'Enter': 'enter',
        'Delete': 'delete',
        'PageUp': 'pgup',
        'PageDown': 'pgdn',
        'Home': 'home',
        'End': 'end',
        'F1': 'f1', 'F2': 'f2', 'F3': 'f3', 'F4': 'f4', 'F5': 'f5', 'F6': 'f6',
        'F7': 'f7', 'F8': 'f8', 'F9': 'f9', 'F10': 'f10', 'F11': 'f11', 'F12': 'f12'
      };

      // Construir combinación de teclas con modificadores
      let hasModifier = e.ctrlKey || e.altKey || e.metaKey;
      let isSpecialKey = e.key in specialKeys;

      // Si tiene modificadores O es una tecla especial combinada con Shift (ej. Shift+ArrowRight)
      if (hasModifier || (e.shiftKey && isSpecialKey)) {
        e.preventDefault();
        let keyParts: string[] = [];
        if (e.ctrlKey || e.metaKey) keyParts.push('ctrl');
        if (e.altKey) keyParts.push('alt');
        if (e.shiftKey) keyParts.push('shift');

        const mainKey = isSpecialKey ? specialKeys[e.key] : e.key.toLowerCase();
        keyParts.push(mainKey);

        const combo = keyParts.join('+');
        await sendCentinelaControl(targetSessionId, {
          type: 'key_press',
          key: combo
        });
      } else if (isSpecialKey) {
        // Tecla especial sola (ej. ArrowUp, Escape, Tab, etc.)
        e.preventDefault();
        await sendCentinelaControl(targetSessionId, {
          type: 'key_press',
          key: specialKeys[e.key]
        });
      } else if (e.key.length === 1) {
        // Caracter estándar solo (o con Shift de texto estándar, ej. "A" o "!")
        e.preventDefault();
        await sendCentinelaControl(targetSessionId, {
          type: 'write_text',
          text: e.key
        });
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [standaloneId, focusedSessionId, remoteClipboard, isControlEnabled]);

  useEffect(() => {
    let interval: any;
    if (isAuthenticated) {
      const fetchAlerts = async () => {
        try {
          const alerts = await getCentinelaAlerts();
          setActiveAlerts(alerts);

          Object.entries(alerts).forEach(([id, list]: any) => {
            if (list.length > 0 && !activeAlerts[id]) {
              setShowNotification(`¡Alerta Crítica en PC #${id}!`);
              triggerPushNotification("⚠️ Alerta Crítica de Centinela", `¡Problema detectado en PC #${id}! Detalle: ${list.join(', ')}`, `/?remote_device_id=${id}`);
              setTimeout(() => setShowNotification(null), 5000);
            }
          });
        } catch (e: any) {
          if (e?.message === 'Sesión Expirada' || e?.message?.includes('401')) {
            handleLogout();
          } else {
            console.error("Error en alertas:", e);
          }
        }
      };
      fetchAlerts();
      interval = setInterval(fetchAlerts, 5000);
    }
    return () => clearInterval(interval);
  }, [isAuthenticated, activeAlerts]);


  const handleLogout = () => {
    logoutUser(); // Marcar offline en backend
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setIsAuthenticated(false);
  }

  const handleProfilePicChange = (e: React.ChangeEvent<HTMLInputElement>, isAbm: boolean) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        const base64String = reader.result as string;
        if (isAbm) {
          setUserAbmForm(prev => ({ ...prev, profile_picture: base64String }));
        } else {
          setProfileForm(prev => ({ ...prev, profile_picture: base64String }));
        }
      };
      reader.readAsDataURL(file);
    }
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profileForm.nombre) return;
    try {
      const updated = await updateUser(userProfile.id, {
        nombre: profileForm.nombre,
        full_name: profileForm.full_name,
        celular: profileForm.celular,
        password: profileForm.password || undefined,
        profile_picture: profileForm.profile_picture || undefined
      });
      // Sincronizar en localStorage y state
      const merged = { ...userProfile, ...updated };
      localStorage.setItem('user', JSON.stringify(merged));
      setUserProfile(merged);
      setShowProfileModal(false);
      loadData();
      setShowNotification("¡Tu perfil fue actualizado con éxito!");
      setTimeout(() => setShowNotification(null), 3000);
    } catch (err: any) {
      alert(err.message || "Error al actualizar perfil.");
    }
  };

  const handleSaveUserAbm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!userAbmForm.nombre || !userAbmForm.email || (!selectedUserForEdit && !userAbmForm.password)) {
      alert("Por favor completa los campos requeridos.");
      return;
    }
    try {
      if (selectedUserForEdit) {
        // Modificar existente
        await updateUser(selectedUserForEdit.id, {
          nombre: userAbmForm.nombre,
          email: userAbmForm.email,
          full_name: userAbmForm.full_name,
          password: userAbmForm.password || undefined,
          rol: userAbmForm.rol,
          celular: userAbmForm.celular,
          departamento: userAbmForm.departamento,
          profile_picture: userAbmForm.profile_picture || undefined,
          activo: userAbmForm.activo
        });
        setShowNotification(`Usuario ${userAbmForm.nombre} actualizado.`);
      } else {
        // Crear nuevo
        await createUser({
          nombre: userAbmForm.nombre,
          email: userAbmForm.email,
          full_name: userAbmForm.full_name,
          password: userAbmForm.password,
          rol: userAbmForm.rol,
          celular: userAbmForm.celular,
          departamento: userAbmForm.departamento,
          profile_picture: userAbmForm.profile_picture || undefined,
          activo: userAbmForm.activo
        });
        setShowNotification(`Usuario ${userAbmForm.nombre} creado.`);
      }
      setShowUserAbmModal(false);
      loadData();
      setTimeout(() => setShowNotification(null), 3000);
    } catch (err: any) {
      alert(err.message || "Error al guardar usuario.");
    }
  };

  const handleCreateTicket = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newClientId || !newSubject || !newDesc) return;
    setIsSubmitting(true);
    const created = await createTicket({
      client_id: parseInt(newClientId),
      asunto: newSubject,
      descripcion: newDesc,
      prioridad: newPriority
    });
    setIsSubmitting(false);
    if (created) {
      setIsModalOpen(false);
      setNewSubject(""); setNewDesc("");
      loadData();
    } else alert("Error de comunicación backend.");
  };

  const handleConsultarIA = async () => {
    if (!selectedTicket) return;
    setIsAiLoading(true);
    const result = await fetchAiAnalysis(selectedTicket.id);
    setAiSuggestion(result?.analysis || "Hubo un corte en la conexión neuronal. Intente nuevamente.");
    setIsAiLoading(false);
  }

  const openTicketModal = async (t: any) => {
    setSelectedTicket(t);
    setAiSuggestion(null);
    setInterventions(t.intervenciones || []);
    setTransferAreaId(null);
    setAttachment(null);
    setAttachmentUrl(null);
    // loadData() ya se llama en otros lugares si es necesario, 
    // pero aquí refrescamos la lista por si hubo cambios
    // loadData(); 
  }

  const closeTicketModal = () => {
    setSelectedTicket(null);
    setInterventions([]);
    setNewMessage("");
  }

  const toggleRemoteSession = async (centinela: any) => {
    const exists = activeSessions.find(s => s.id === centinela.id);
    if (exists) {
      const token = localStorage.getItem('token');
      await fetch(`${API_URL}/centinelas/devices/${centinela.id}/end-session`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${token}` }
      });

      setActiveSessions(activeSessions.filter(s => s.id !== centinela.id));
      const newFrames = { ...sessionFrames };
      delete newFrames[centinela.id];
      setSessionFrames(newFrames);
      loadData();
      sendBrowserNotification(
        '🔴 Sesión Cerrada',
        `Conexión con ${centinela.device_name || `Dispositivo #${centinela.id}`} finalizada.`
      );
    } else {
      setActiveSessions([...activeSessions, centinela]);
      if (!sessionCmds[centinela.id]) {
        setSessionCmds({ ...sessionCmds, [centinela.id]: { current: "", history: [] } });
      }
      sendBrowserNotification(
        '🟢 Sesión Iniciada',
        `Conectado a ${centinela.device_name || `Dispositivo #${centinela.id}`}.`
      );
    }
  };

  // Cargar el historial de la última sesión de soporte al iniciar conexión remota (NUEVO)
  useEffect(() => {
    if (isAuthenticated && standaloneId) {
      const devId = parseInt(standaloneId);
      const fetchLastSession = async () => {
        try {
          const token = localStorage.getItem('token');
          const response = await fetch(`${API_URL}/centinelas/devices/${devId}/last-session`, {
            headers: { 'Authorization': `Bearer ${token}` }
          });
          if (response.ok) {
            const data = await response.json();
            if (data) {
              setLastSupportSession(data);
            }
          }
        } catch (e) {
          console.error("Error fetching last session:", e);
        }
      };
      fetchLastSession();
    }
  }, [isAuthenticated, standaloneId]);

  const handleEndSessionSupport = async (deviceId: number) => {
    setIsFinishingSession(true);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/end-session`, {
        method: "POST",
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}` 
        },
        body: JSON.stringify({ comment: endSessionComment })
      });
      if (response.ok) {
        const data = await response.json();
        setEndSessionResult(data);
      } else {
        alert("Error al finalizar la sesión.");
      }
    } catch (e) {
      alert("Error de comunicación.");
    } finally {
      setIsFinishingSession(false);
    }
  };

  const handleImageInteraction = async (
    e: React.MouseEvent<HTMLElement>,
    deviceId: number,
    clickType: 'left' | 'right' | 'double'
  ) => {
    if (!isControlEnabled) return;
    setFocusedSessionId(deviceId);
    e.preventDefault();
    const coords = getCoordinates(e);

    if (coords) {
      await sendCentinelaControl(deviceId, {
        type: 'mouse_click',
        x: coords.x,
        y: coords.y,
        click_type: clickType
      });
    }
  };

  const getCoordinates = (e: React.MouseEvent<HTMLElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const target = e.currentTarget;
    let originalWidth = 0;
    let originalHeight = 0;

    if (target instanceof HTMLImageElement) {
      originalWidth = target.naturalWidth;
      originalHeight = target.naturalHeight;
    } else if (target instanceof HTMLCanvasElement) {
      originalWidth = target.width;
      originalHeight = target.height;
    }

    if (!originalWidth || !originalHeight) return null;

    const containerWidth = rect.width;
    const containerHeight = rect.height;

    const containerRatio = containerWidth / containerHeight;
    const imageRatio = originalWidth / originalHeight;

    let renderWidth = containerWidth;
    let renderHeight = containerHeight;
    let offsetX = 0;
    let offsetY = 0;

    if (containerRatio > imageRatio) {
      renderHeight = containerHeight;
      renderWidth = containerHeight * imageRatio;
      offsetX = (containerWidth - renderWidth) / 2;
    } else {
      renderWidth = containerWidth;
      renderHeight = containerWidth / imageRatio;
      offsetY = (containerHeight - renderHeight) / 2;
    }

    const clickX = e.clientX - rect.left - offsetX;
    const clickY = e.clientY - rect.top - offsetY;

    const x = clickX / renderWidth;
    const y = clickY / renderHeight;

    if (x >= 0 && x <= 1 && y >= 0 && y <= 1) {
      return { x, y };
    }
    return null;
  };

  const handleMouseDown = async (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    setFocusedSessionId(deviceId);
    // e.button: 0 = Izquierdo, 2 = Derecho
    const buttonMap: { [key: number]: string } = { 0: 'left', 2: 'right' };
    const button = buttonMap[e.button];
    if (!button) return;

    if (e.button === 2) {
      e.preventDefault();
      e.stopPropagation();
    }

    const coords = getCoordinates(e);
    if (coords) {
      await sendCentinelaControl(deviceId, {
        type: 'mouse_down',
        x: coords.x,
        y: coords.y,
        button
      });
    }
  };

  const handleMouseUp = async (e: React.MouseEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    const buttonMap: { [key: number]: string } = { 0: 'left', 2: 'right' };
    const button = buttonMap[e.button];
    if (!button) return;

    if (e.button === 2) {
      e.preventDefault();
      e.stopPropagation();
    }

    const coords = getCoordinates(e);
    if (coords) {
      await sendCentinelaControl(deviceId, {
        type: 'mouse_up',
        x: coords.x,
        y: coords.y,
        button
      });
    }
  };

  const handleImageWheel = async (e: React.WheelEvent<HTMLElement>, deviceId: number) => {
    if (!isControlEnabled) return;
    const direction = e.deltaY > 0 ? 'down' : 'up';
    const coords = getCoordinates(e as unknown as React.MouseEvent<HTMLElement>);
    await sendCentinelaControl(deviceId, {
      type: 'mouse_scroll',
      direction,
      amount: 3,
      ...(coords ? { x: coords.x, y: coords.y } : {})
    });
  };

  const handleSendCommand = async (clientId: number) => {
    const sessionInfo = sessionCmds[clientId];
    if (!sessionInfo?.current.trim()) return;

    const ok = await runCentinelaCommand(clientId, sessionInfo.current);
    if (ok) {
      setSessionCmds({
        ...sessionCmds,
        [clientId]: {
          current: "",
          history: [sessionInfo.current, ...sessionInfo.history].slice(0, 5)
        }
      });
      setShowNotification(`Comando enviado a PC #${clientId}`);
      setTimeout(() => setShowNotification(null), 3000);
    } else {
      alert("Error al enviar comando. ¿Está el agente conectado?");
    }
  }

  const handleSendIntervention = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTicket || (!newMessage.trim() && !attachmentUrl && !transferAreaId)) return;

    setIsSubmitting(true);
    const data = {
      mensaje: newMessage,
      tipo: transferAreaId ? 'transferencia' : 'comentario',
      to_area_id: transferAreaId || undefined,
      adjunto_url: attachmentUrl || undefined,
      adjunto_tipo: attachment ? (attachment.type.startsWith('audio') ? 'audio' : attachment.type.startsWith('image') ? 'imagen' : 'documento') : undefined
    };

    const sent = await addIntervention(selectedTicket.id, data);
    setIsSubmitting(false);

    if (sent) {
      setInterventions([...interventions, sent]);
      setNewMessage("");
      setTransferAreaId(null);
      setAttachment(null);
      setAttachmentUrl(null);
      loadData();
    }
  }

  const handleFileUpload = async (file: File) => {
    setIsUploading(true);
    const res = await uploadFile(file);
    setIsUploading(false);
    if (res) {
      setAttachment(file);
      setAttachmentUrl(res.url);
    } else alert("Error al subir archivo");
  }

  const handleCreateOrUpdateClient = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    let result;
    if (editingClient) result = await updateClient(editingClient, clientForm);
    else result = await createClient(clientForm);
    setIsSubmitting(false);

    if (result) {
      setIsClientModalOpen(false);
      setEditingClient(null);
      setClientForm({
        codigo: '',
        razon_social: '',
        nombre_fantasia: '',
        identificador_fiscal: '',
        cparte: '',
        version_apollo: '',
        telefono: '',
        email: '',
        localidad: '',
        fecha_vencimiento: '',
        modulos: 'Base, Facturación',
        apikey_apollo: '',
        remote_password: '',
        saldo: 0.0,
        vendedor_codigo: '',
        vendedor_nombre: '',
        clasificacion_codigo: '',
        clasificacion_nombre: '',
        extracto: '',
        cclifac: ''
      });
      loadData();
    } else alert("Error al procesar el cliente.");
  };

  const handleVerifyRemotePassword = async (deviceId: number, pin: string = "") => {
    const token = localStorage.getItem('token');
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/verify-password`, {
        method: "POST",
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ password: pin || "" })
      });
      if (response.ok) {
        const url = `${window.location.origin}${window.location.pathname}?remote_device_id=${deviceId}`;
        const windowName = `Remote_${deviceId}`;
        window.open(url, windowName, 'width=1280,height=800,menubar=no,status=no,toolbar=no');
        setShowNotification("Conexión iniciada.");
      } else {
        if (response.status === 401) {
          alert("Tu sesión de usuario ha expirado. Por favor, cierra sesión y vuelve a ingresar.");
          return;
        }
        let errMsg = "No se pudo iniciar la sesión remota.";
        try {
          const errData = await response.json();
          if (errData && errData.detail) errMsg = typeof errData.detail === 'string' ? errData.detail : errMsg;
        } catch { /* */ }
        alert(errMsg);
      }
    } catch (error) {
      alert("Error de red: No se pudo conectar con el servidor. Revisa si el backend de producción se encuentra activo.");
    }
  };

  const handleDeleteDevice = async (deviceId: number) => {
    if (window.confirm("¿Está seguro de que desea eliminar este dispositivo? Esto liberará un cupo en la licencia.")) {
      try {
        const ok = await deleteCentinelaDevice(deviceId);
        if (ok) {
          setShowNotification("Dispositivo eliminado correctamente.");
          setTimeout(() => setShowNotification(null), 3000);
          loadData();
        } else {
          alert("Error al eliminar el dispositivo.");
        }
      } catch (e) {
        alert("Error de comunicación con el servidor.");
      }
    }
  };

  const handleSaveDeviceNotes = async () => {
    if (!deviceNotesModal) return;
    try {
      const ok = await updateCentinelaDeviceNotes(deviceNotesModal.deviceId, deviceNotesModal.notes);
      if (ok) {
        setClients(prev => prev.map(c => ({
          ...c,
          devices: c.devices?.map((d: any) => d.id === deviceNotesModal.deviceId ? { ...d, notes: deviceNotesModal.notes } : d)
        })));
        setDeviceNotesModal(null);
        setShowNotification("Notas del dispositivo guardadas correctamente.");
        setTimeout(() => setShowNotification(null), 3000);
      } else {
        alert("Error al guardar notas.");
      }
    } catch (e: any) {
      alert("Error de comunicación: " + e.message);
    }
  };

  const handleAssignLicense = async () => {
    if (!assignModal || !assignClientId) return;
    try {
      const ok = await assignCentinelaLicense(assignModal.id, parseInt(assignClientId));
      if (ok) {
        setShowNotification(`Dispositivo asignado exitosamente.`);
        setTimeout(() => setShowNotification(null), 3000);
        setAssignModal(null);
        setAssignClientId("");
        loadData();
      } else {
        alert("Error al asignar la licencia.");
      }
    } catch (e: any) {
      alert("Error de comunicación: " + e.message);
    }
  };

  const sendRemoteChat = async (deviceId: number, message: string) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/chat`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ message, sender_type: 'tech' })
    });
    if (response.ok) fetchChatHistory(deviceId);
  };

  const fetchChatHistory = async (deviceId: number) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/chat`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.ok) {
      const data = await response.json();
      setSessionChats(prev => ({ ...prev, [deviceId]: data }));
    }
  };

  const syncRemoteClipboard = async (deviceId: number, text: string) => {
    const token = localStorage.getItem('token');
    await fetch(`${API_URL}/centinelas/devices/${deviceId}/clipboard`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ text })
    });
    setShowNotification("Portapapeles sincronizado.");
  };

  const fetchRemoteFiles = async (deviceId: number, path: string = "C:\\") => {
    const token = localStorage.getItem('token');
    setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], path, loading: true } }));
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        if (data.type === 'dir_list' || data.files) {
          setSessionFiles(prev => ({
            ...prev,
            [deviceId]: {
              path: data.path || path,
              files: data.files || [],
              loading: false,
              visible: true
            }
          }));
        } else {
          // Si el backend está cargando los archivos, reintentamos en 1 segundo
          setTimeout(() => fetchRemoteFiles(deviceId, path), 1000);
        }
      } else {
        setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], loading: false } }));
      }
    } catch (e) {
      setSessionFiles(prev => ({ ...prev, [deviceId]: { ...prev[deviceId], loading: false } }));
    }
  };

  const downloadRemoteFile = async (deviceId: number, path: string) => {
    const token = localStorage.getItem('token');
    setShowNotification("Esperando transmisión del archivo...");
    try {
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/download?path=${encodeURIComponent(path)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (!response.ok) {
        throw new Error("Error en la descarga");
      }
      const blob = await response.blob();
      const filename = path.split('\\').pop() || path.split('/').pop() || 'archivo_remoto';
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      setShowNotification("Archivo descargado con éxito.");
    } catch (err) {
      setShowNotification("Error al descargar archivo del agente.");
    }
  };

  const fetchLicenses = async () => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/licenses`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    if (response.ok) {
      const data = await response.json();
      setLicenses(data);
    }
  };

  const fetchTelemetryLogs = async () => {
    setLogsLoading(true);
    try {
      const devId = logsFilterDevice !== 'all' ? Number(logsFilterDevice) : undefined;
      const lvl = logsFilterLevel !== 'all' ? logsFilterLevel : undefined;
      const src = logsFilterSource !== 'all' ? logsFilterSource : undefined;
      const data = await getCentinelaLogs(devId, lvl, src, 100);
      setTelemetryLogs(data);
    } catch (err: any) {
      console.error("Error fetching telemetry logs:", err);
    } finally {
      setLogsLoading(false);
    }
  };

  const fetchDeviceLogs = async (deviceId: number) => {
    setDeviceLogsLoading(true);
    try {
      const data = await getCentinelaLogs(deviceId, undefined, undefined, 100);
      setDeviceLogs(data);
    } catch (err: any) {
      console.error("Error fetching device logs:", err);
    } finally {
      setDeviceLogsLoading(false);
    }
  };

  const handleClearTelemetryLogs = async (deviceId?: number | null) => {
    if (!window.confirm("¿Está seguro de que desea limpiar el historial de logs? Esta acción no se puede deshacer.")) return;
    try {
      await clearCentinelaLogs(deviceId);
      setShowNotification("Historial de logs limpiado con éxito.");
      if (deviceId) {
        fetchDeviceLogs(deviceId);
      } else {
        fetchTelemetryLogs();
      }
    } catch (err: any) {
      alert("Error al limpiar logs: " + err.message);
    }
  };

  // Poll para bitácora global de logs
  useEffect(() => {
    if (activeTab === 'logs') {
      fetchTelemetryLogs();
    }
  }, [activeTab, logsFilterDevice, logsFilterLevel, logsFilterSource]);

  useEffect(() => {
    if (activeTab !== 'logs' || !logsAutoRefresh) return;
    const interval = setInterval(() => {
      fetchTelemetryLogs();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeTab, logsAutoRefresh, logsFilterDevice, logsFilterLevel, logsFilterSource]);

  // Poll para logs de dispositivo en vivo (soporte standalone)
  useEffect(() => {
    const devId = standaloneDeviceId ?? (activeSessions.length === 1 ? activeSessions[0]?.id : null);
    if (!devId || !isDeviceLogsOpen) return;
    
    fetchDeviceLogs(devId);
    
    if (!logsAutoRefresh) return;
    const interval = setInterval(() => {
      fetchDeviceLogs(devId);
    }, 3000);
    return () => clearInterval(interval);
  }, [isDeviceLogsOpen, logsAutoRefresh, activeSessions]);

  const generateLicense = async (clientId: number, devices: number, days: number) => {
    const token = localStorage.getItem('token');
    const response = await fetch(`${API_URL}/licenses`, {
      method: "POST",
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
      body: JSON.stringify({ client_id: clientId, max_devices: devices, duration_days: days })
    });
    if (response.ok) {
      setShowNotification("Licencia generada con éxito.");
      fetchLicenses();
      setShowLicenseModal(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'licenses' || activeTab === 'monitor') fetchLicenses();
  }, [activeTab]);

  const handleUploadFile = async (deviceId: number, file: File) => {
    const token = localStorage.getItem('token');
    const currentPath = sessionFiles[deviceId]?.path || "C:\\";
    setShowNotification("Subiendo archivo al agente...");
    try {
      const formData = new FormData();
      formData.append('file', file);
      const response = await fetch(`${API_URL}/centinelas/devices/${deviceId}/files/upload?dest_path=${encodeURIComponent(currentPath)}`, {
        method: "POST",
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      if (response.ok) {
        setShowNotification("Archivo enviado con éxito al agente.");
        setTimeout(() => fetchRemoteFiles(deviceId, currentPath), 1500);
      } else {
        setShowNotification("Error al subir archivo.");
      }
    } catch (err) {
      setShowNotification("Error en la conexión al subir archivo.");
    }
  };

  const openClientModal = (c?: any) => {
    setClientActiveTab('basic');
    if (c) {
      setEditingClient(c.id);
      setClientForm({
        codigo: c.codigo || '',
        razon_social: c.razon_social,
        nombre_fantasia: c.nombre_fantasia || '',
        identificador_fiscal: c.identificador_fiscal || '',
        cparte: c.cparte || '',
        version_apollo: c.version_apollo || '',
        telefono: c.telefono || '',
        email: c.email || '',
        localidad: c.localidad || '',
        fecha_vencimiento: c.fecha_vencimiento ? c.fecha_vencimiento.split('T')[0] : '',
        modulos: c.modulos || 'Base, Facturación',
        apikey_apollo: c.apikey_apollo || '',
        remote_password: c.remote_password || '',
        saldo: c.saldo || 0.0,
        vendedor_codigo: c.vendedor_codigo || '',
        vendedor_nombre: c.vendedor_nombre || '',
        clasificacion_codigo: c.clasificacion_codigo || '',
        clasificacion_nombre: c.clasificacion_nombre || '',
        extracto: c.extracto || '',
        cclifac: c.cclifac || ''
      });
    } else {
      setEditingClient(null);
      setClientForm({
        codigo: '',
        razon_social: '',
        nombre_fantasia: '',
        identificador_fiscal: '',
        cparte: '',
        version_apollo: '',
        telefono: '',
        email: '',
        localidad: '',
        fecha_vencimiento: '',
        modulos: 'Base, Facturación',
        apikey_apollo: '',
        remote_password: '',
        saldo: 0.0,
        vendedor_codigo: '',
        vendedor_nombre: '',
        clasificacion_codigo: '',
        clasificacion_nombre: '',
        extracto: '',
        cclifac: ''
      });
    }
    setIsClientModalOpen(true);
  }

  if (!isAuthenticated) return <Login onLogin={() => setIsAuthenticated(true)} />;

  // --- RENDERING INDEPENDIENTE PARA SESIONES REMOTAS INDEPENDIENTES (STANDALONE WINDOWS) ---
  if (standaloneId) {
    const session = activeSessions[0];
    if (!session) {
      return (
        <div className="flex h-screen items-center justify-center bg-slate-950 text-white">
          <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
        </div>
      );
    }

    const frame = sessionFrames[session.id];
    const cmdInfo = sessionCmds[session.id] || { current: "", history: [] };
    const isChatOpen = !!chatVisibility[String(session.id)];
    const isFilesOpen = !!sessionFiles[session.id]?.visible;

    // ─── OVERLAY DE FULLSCREEN REAL DEL VISOR DECORADO (MANEJADO EN EL CONTENEDOR PRINCIPAL) ───

    return (
      <div className="flex h-screen w-screen flex-col bg-slate-950 text-white p-4 overflow-hidden select-none">
        {/* Cabecera Standalone */}
        <div className="flex flex-col sm:flex-row gap-3 justify-between items-start sm:items-center mb-3" style={{ display: isViewerFullscreen ? 'none' : 'flex' }}>
          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <span className={`w-3.5 h-3.5 rounded-full ${(session.is_online || frame) ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
            <h1 className="text-sm sm:text-lg font-black tracking-tight truncate max-w-[200px] sm:max-w-none">{session.device_name || "Soporte Remoto"}</h1>
            <span className="text-[10px] sm:text-xs bg-slate-800 text-slate-400 px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-md font-mono">ID: {session.id}</span>
            <span className={`text-[9px] sm:text-[10px] font-bold px-2 sm:px-2.5 py-0.5 sm:py-1 rounded-md uppercase tracking-wider ${(session.is_online || frame) ? (isControlEnabled ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/20 animate-pulse' : 'bg-amber-500/15 text-amber-400 border border-amber-500/20') : 'bg-red-500/15 text-red-400 border border-red-500/20'}`}>
              {!(session.is_online || frame) ? 'DESCONECTADO' : (isControlEnabled ? 'Control Remoto' : 'Solo Observando')}
            </span>
            {isCapsLockActive && (
              <span className="text-[9px] sm:text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2.5 py-1 rounded-md font-bold flex items-center gap-1 animate-pulse shadow-sm shadow-amber-500/10">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-ping" />
                🔠 MAYÚS ACTIVO
              </span>
            )}
            {/* Indicador de calidad de conexión en tiempo real */}
            {(session.is_online || frame) && (
              <span className={`text-[9px] sm:text-[10px] font-bold px-2 py-0.5 rounded-md flex items-center gap-1.5 border font-mono ${
                (connectionFps <= 2 || connectionQuality === 'excellent') ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                connectionQuality === 'good'      ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                                    'bg-red-500/10 text-red-400 border-red-500/20 animate-pulse'
              }`} title={`Calidad: ${connectionQuality} | ${connectionFps} FPS (objetivo trabajo ≥${REMOTE_STREAM_WORKABLE_FPS})`}>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  (connectionFps <= 2 || connectionQuality === 'excellent') ? 'bg-emerald-400' :
                  connectionQuality === 'good'      ? 'bg-amber-400' : 'bg-red-400 animate-ping'
                }`} />
                {connectionFps <= 2 ? 'Estable' : `${connectionFps} FPS`} · {
                  connectionFps <= 2 ? 'Óptima' :
                  connectionQuality === 'excellent' ? 'Cómoda' :
                  connectionQuality === 'good'      ? 'Mínima útil' : 'Bajo mínimo'
                }
              </span>
            )}
          </div>
          <div className="flex gap-2 w-full sm:w-auto flex-wrap">
            {/* Selector de Monitor (visible solo cuando hay 2+ monitores) */}
            {monitorCount > 1 && (
              <div className="flex items-center gap-1 bg-slate-800/80 rounded-xl px-2 py-1 border border-white/5">
                <span className="text-[9px] text-slate-400 font-bold mr-1 uppercase tracking-wider">Monitor</span>
                {Array.from({ length: monitorCount }, (_, i) => i + 1).map(idx => (
                  <button
                    key={idx}
                    onClick={() => switchMonitor(session.id, idx)}
                    className={`w-6 h-6 rounded-lg text-[10px] font-black transition-all ${
                      activeMonitor === idx
                        ? 'bg-brand-500 text-white shadow-sm shadow-brand-500/40'
                        : 'bg-slate-700 text-slate-400 hover:bg-slate-600'
                    }`}
                    title={`Cambiar a Monitor ${idx}`}
                  >
                    {idx}
                  </button>
                ))}
              </div>
            )}
            {/* 👤 SELECTOR DE SESIONES WINDOWS */}
            {activeSessions.length === 1 && (
              <div className="relative flex-shrink-0">
                <button
                  onClick={() => {
                    sendViewerCommand({ type: 'get_sessions' });
                    setShowSessionPicker(v => !v);
                  }}
                  className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border transition-all ${
                    sessionSwitching
                      ? 'bg-amber-600/70 border-amber-500/30 text-amber-100 animate-pulse'
                      : winSessions.length === 0
                        ? 'bg-slate-700 border-white/10 text-slate-500 hover:bg-slate-600'
                        : 'bg-slate-700 border-white/10 text-slate-300 hover:bg-slate-600 hover:text-white'
                  }`}
                  title="Cambiar sesión de usuario Windows"
                >
                  <span>👤</span>
                  <span className="hidden sm:inline">
                    {sessionSwitching ? 'Cambiando...' :
                     winSessions.find(s => s.current)?.username || 'Sesión'}
                  </span>
                </button>

                {/* Dropdown de sesiones */}
                {showSessionPicker && !sessionSwitching && (
                  <div className="absolute right-0 top-full mt-2 z-50 min-w-[220px] bg-slate-900 border border-white/10 rounded-xl shadow-2xl p-1 animate-in slide-in-from-top-2">
                    <div className="px-3 py-1.5 text-[10px] text-slate-500 font-bold uppercase tracking-widest border-b border-white/5 mb-1">
                      Sesiones Windows
                    </div>
                    {winSessions.length === 0 ? (
                      <div className="px-3 py-2 text-xs text-slate-500 italic">Cargando sesiones...</div>
                    ) : (
                      winSessions.map(s => (
                        <button
                          key={s.id}
                          onClick={() => {
                            setShowSessionPicker(false);
                            if (!s.current) {
                              sendViewerCommand({ type: 'switch_session', session_id: s.id });
                              setSessionSwitching(true);
                            }
                          }}
                          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all text-left ${
                            s.current
                              ? 'bg-brand-500/20 text-brand-300 cursor-default'
                              : 'hover:bg-slate-700 text-slate-300 cursor-pointer'
                          }`}
                        >
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            s.state?.toLowerCase().includes('activ') ? 'bg-green-400' :
                            s.state?.toLowerCase().includes('disc') ? 'bg-yellow-400' : 'bg-slate-500'
                          }`} />
                          <span className="flex-1 truncate">
                            {s.username || s.name || `Sesión ${s.id}`}
                          </span>
                          <span className="text-slate-500 text-[10px]">{s.state}</span>
                          {s.current && <span className="text-brand-400 text-[10px]">● actual</span>}
                        </button>
                      ))
                    )}
                    <div className="border-t border-white/5 mt-1 pt-1">
                      <button
                        onClick={() => { setShowSessionPicker(false); setShowLoginModal(true); setLoginError(''); }}
                        className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-slate-400 hover:bg-slate-700 hover:text-white transition-all text-left"
                      >
                        <span>🔑</span> Iniciar sesión con credenciales
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {streamQualitySelect}

            {/* ⚡ Alto Rendimiento — siempre visible */}

            <button
              onClick={toggleHqMode}
              className={`flex-shrink-0 px-3 py-2 rounded-xl text-xs font-bold border transition-all flex items-center gap-1.5 ${
                hqEnabled
                  ? 'bg-violet-600 border-violet-500/30 text-white shadow-violet-500/20 shadow-lg'
                  : 'bg-slate-700 border-white/10 text-slate-400 hover:bg-violet-700/50 hover:text-white'
              }`}
              title="Modo Alto Rendimiento: Turbo WebP Canvas a 30 FPS"
            >
              <span>⚡</span>
              <span className="hidden sm:inline">
                {hqEnabled ? 'HQ ON' : 'HQ'}
              </span>
            </button>

            {/* Botón de Pantalla Completa del Visor */}

            <button
              onClick={enterViewerFullscreen}
              className="flex-1 sm:flex-none bg-slate-800 hover:bg-slate-700 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all shadow-lg border border-white/5 flex items-center justify-center gap-2"
              title="Pantalla Completa del Visor Remoto"
            >
              <Maximize2 className="w-4 h-4 text-brand-400" /> <span className="hidden xs:inline">Pantalla Completa</span>
            </button>
            <button
              onClick={() => {
                setShowEndSessionModal(true);
              }}
              className="flex-1 sm:flex-none bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-xl text-xs font-bold transition-all shadow-lg text-center"
            >
              Cerrar Conexión
            </button>
          </div>
        </div>

        {/* ÚLTIMO ACCESO DETECTADO CON COMENTARIOS Y REPORTE IA (NUEVO) */}
        {lastSupportSession && !isLastSessionBannerDismissed && !isViewerFullscreen && (
          <div className="mb-3 p-4 rounded-2xl glass-dark border border-brand-500/20 text-slate-300 relative animate-in slide-in-from-top-4 flex flex-col md:flex-row gap-4 items-start justify-between shadow-lg">
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <span className="text-brand-400 text-[10px] font-black uppercase tracking-widest bg-brand-500/10 px-2 py-0.5 rounded-md">
                  ℹ️ Último Acceso de Soporte
                </span>
                <span className="text-slate-400 text-xs">
                  por <strong className="text-slate-200">{lastSupportSession.technician_name}</strong> el {new Date(lastSupportSession.end_time).toLocaleString()}
                </span>
                {lastSupportSession.duration && (
                  <span className="text-slate-500 text-[10px] font-mono bg-slate-900/50 px-1.5 py-0.5 rounded">
                    Duración: {Math.round(lastSupportSession.duration / 60)} min
                  </span>
                )}
              </div>
              
              {lastSupportSession.comments && (
                <p className="text-xs sm:text-sm text-slate-200 font-medium mb-2 pl-3 border-l-2 border-brand-500">
                  <span className="text-brand-400 font-bold text-[10px] uppercase tracking-wider block">Nota del Operador:</span>
                  "{lastSupportSession.comments}"
                </p>
              )}
              
              {lastSupportSession.ai_report && (
                <div className="mt-2 text-[11px] sm:text-xs text-slate-400 bg-slate-950/60 p-3 rounded-xl border border-white/5 font-sans leading-relaxed">
                  <span className="text-indigo-400 font-extrabold uppercase tracking-wider text-[10px] block mb-1 flex items-center gap-1">
                    <Sparkles className="w-3.5 h-3.5 animate-pulse text-indigo-400" /> Resumen de Actividad Generado por IA
                  </span>
                  <div className="text-slate-300 space-y-1">
                    {lastSupportSession.ai_report.split('\n').map((line: string, i: number) => {
                      if (line.trim().startsWith('*') || line.trim().startsWith('-')) {
                        return <div key={i} className="flex gap-1.5 items-start pl-1">
                          <span className="text-indigo-500 font-bold">•</span>
                          <span>{line.replace(/^[\*\-\s]+/, '')}</span>
                        </div>;
                      }
                      return <p key={i}>{line}</p>;
                    })}
                  </div>
                </div>
              )}
            </div>
            <button 
              onClick={() => setIsLastSessionBannerDismissed(true)} 
              className="text-slate-500 hover:text-white bg-slate-900 hover:bg-slate-800 p-2 rounded-xl transition-colors border border-white/5"
              title="Ocultar recordatorio"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Cuerpo Principal */}
        <div className="flex-1 flex flex-col lg:flex-row gap-4 overflow-y-auto lg:overflow-hidden min-h-0">
          {/* Pantalla Remota */}
          <div 
            className={isViewerFullscreen 
              ? "fixed inset-0 z-[9999] bg-black flex items-center justify-center select-none" 
              : "flex-1 bg-black rounded-2xl border border-white/5 flex items-center justify-center relative overflow-hidden min-h-0"}
            onMouseMove={isViewerFullscreen ? resetToolbarTimer : undefined}
            style={{ cursor: isViewerFullscreen ? (toolbarVisible ? 'default' : 'none') : 'default' }}
          >
            {(frame || latestLiveFrameRef.current || wsViewerConnected) ? (
              <div className="relative w-full h-full flex items-center justify-center">
                <canvas
                  ref={setLiveCanvasRef}
                  onMouseDown={(e) => handleMouseDown(e, session.id)}
                  onMouseUp={(e) => handleMouseUp(e, session.id)}
                  onDoubleClick={(e) => handleImageInteraction(e, session.id, 'double')}
                  onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); }}
                  onWheel={(e) => handleImageWheel(e, session.id)}
                  style={{ display: 'block' }}
                  className={`w-full h-full object-contain cursor-default select-none transition-all duration-500 ${(!session.is_online && !frame) ? 'filter blur-[4px] brightness-[0.35] grayscale contrast-75' : ''}`}
                />

                {/* Video HQ MSE removido en favor de MJPEG sobre WebSocket estandar */}

                {/* Overlay Estético de Conexión Perdida (NUEVO) */}
                {(!session.is_online && !frame) && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-950/40 backdrop-blur-[1px] p-6 text-center z-20 animate-in fade-in duration-300">
                    <div className="p-4 rounded-[2rem] border border-red-500/20 bg-red-500/10 text-red-400 animate-bounce mb-3 shadow-2xl shadow-red-500/10">
                      <AlertCircle className="w-8 h-8 animate-pulse text-red-500" />
                    </div>
                    <h3 className="text-sm sm:text-base font-black text-red-400 uppercase tracking-widest bg-red-500/5 border border-red-500/10 px-4 py-1 rounded-full">
                      Enlace Remoto Interrumpido
                    </h3>
                    <p className="text-[11px] sm:text-xs text-slate-400 mt-2 max-w-sm leading-relaxed">
                      El agente Centinela se ha desconectado de internet o la PC se apagó. El enlace se restablecerá automáticamente en cuanto vuelva a estar en línea.
                    </p>
                  </div>
                )}

                {/* ── Barra flotante auto-oculta en Fullscreen ── */}
                {isViewerFullscreen && (
                  <div
                    className="absolute top-0 left-0 right-0 z-30 transition-all duration-500"
                    style={{
                      opacity: toolbarVisible ? 1 : 0,
                      transform: toolbarVisible ? 'translateY(0)' : 'translateY(-100%)',
                      pointerEvents: toolbarVisible ? 'auto' : 'none',
                    }}
                  >
                    <div className="flex items-center justify-between gap-3 px-5 py-3"
                      style={{ background: 'linear-gradient(to bottom, rgba(2,6,23,0.96) 0%, rgba(2,6,23,0) 100%)' }}
                    >
                      {/* Info izquierda */}
                      <div className="flex items-center gap-3">
                        <span className={`w-2.5 h-2.5 rounded-full ${(session.is_online || frame) ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
                        <span className="text-white font-bold text-sm tracking-tight">{session.device_name || 'Soporte Remoto'}</span>
                        <span className="text-slate-400 text-xs font-mono bg-slate-800/70 px-2 py-0.5 rounded-md">ID: {session.id}</span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-md uppercase tracking-wider border ${isControlEnabled ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' : 'bg-amber-500/15 text-amber-400 border-amber-500/20'}`}>
                          {isControlEnabled ? '⚡ Control Activo' : '👁 Solo Observando'}
                        </span>
                        {isCapsLockActive && (
                          <span className="text-[10px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-md font-bold flex items-center gap-1 animate-pulse">
                            🔠 MAYÚS
                          </span>
                        )}
                        <span className="text-slate-500 text-[10px]">Mover el mouse para mostrar/ocultar barra · ESC para salir</span>
                      </div>

                      {/* Controles derecha */}
                      <div className="flex items-center gap-2">
                        {streamQualitySelect}
                        {/* ── ALTO RENDIMIENTO TOGGLE ── */}
                        <button
                          onClick={toggleHqMode}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                            hqEnabled
                              ? 'bg-violet-600/80 border-violet-500/30 text-white shadow-violet-500/20 shadow-lg'
                              : 'bg-slate-700/60 border-white/10 text-slate-400 hover:bg-violet-700/50 hover:text-white'
                          }`}
                          title="Modo Alto Rendimiento: Turbo WebP Canvas a 30 FPS"
                        >
                          {hqEnabled ? '⚡ HQ ON' : '⚡ Alto Rendimiento'}
                        </button>
                        <button
                          onClick={() => setIsControlEnabled(v => !v)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-all ${isControlEnabled ? 'bg-emerald-600/80 border-emerald-500/30 text-white hover:bg-red-600/80 hover:border-red-500/30' : 'bg-slate-700/80 border-white/10 text-slate-300 hover:bg-emerald-600/80'}`}
                          title="Alternar Control / Solo Ver"
                        >
                          {isControlEnabled ? '🖱 Control ON' : '👁 Solo Ver'}
                        </button>
                        <button
                          onClick={exitViewerFullscreen}
                          className="flex items-center gap-1.5 bg-red-600/80 hover:bg-red-600 border border-red-500/30 text-white px-3 py-1.5 rounded-lg text-xs font-bold transition-all shadow-lg"
                          title="Salir de Pantalla Completa (ESC)"
                        >
                          <Minimize className="w-3.5 h-3.5" /> Salir Fullscreen
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Indicador discreto de "mover mouse" en Fullscreen */}
                {isViewerFullscreen && !toolbarVisible && (
                  <div
                    className="absolute top-2 left-1/2 -translate-x-1/2 text-[10px] text-white/20 pointer-events-none select-none transition-opacity duration-500 z-30"
                  >
                    ↑ mover mouse para ver controles
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
                <span className="text-xs text-slate-500">Esperando imagen del cliente...</span>
              </div>
            )}

            {/* Panel de Herramientas Flotante */}
            <div className="absolute top-4 right-4 flex flex-col gap-2 z-30">
              <button
                onClick={() => setIsControlEnabled(!isControlEnabled)}
                className={`p-2.5 rounded-xl text-white shadow-lg border border-white/10 ${isControlEnabled ? 'bg-brand-500 hover:bg-brand-600' : 'bg-slate-700 hover:bg-slate-600'}`}
                title={isControlEnabled ? "Control Activo (Clic para Solo Observar)" : "Modo Observador (Clic para Controlar)"}
              >
                <Monitor size={18} className={isControlEnabled ? "text-white" : "text-slate-400"} />
              </button>
              <button
                onClick={() => {
                  const idStr = String(session.id);
                  if (!chatVisibility[idStr]) fetchChatHistory(session.id);
                  setChatVisibility(prev => ({ ...prev, [idStr]: !prev[idStr] }));
                }}
                className={`p-2.5 rounded-xl text-white shadow-lg border border-white/10 ${isChatOpen ? 'bg-brand-600' : 'bg-brand-500/80 hover:bg-brand-500'}`}
                title="Chat con Cliente"
              >
                <MessageSquare size={18} />
              </button>
              <button
                onClick={async () => {
                  try {
                    const text = await navigator.clipboard.readText();
                    syncRemoteClipboard(session.id, text);
                  } catch (err) {
                    const text = prompt("Ingrese el texto a enviar al portapapeles de la PC cliente:");
                    if (text !== null) syncRemoteClipboard(session.id, text);
                  }
                }}
                className="bg-blue-600/80 hover:bg-blue-600 p-2.5 rounded-xl text-white shadow-lg border border-white/10"
                title="Sincronizar Portapapeles"
              >
                <Clipboard size={18} />
              </button>
              <button
                onClick={() => {
                  const visible = !sessionFiles[session.id]?.visible;
                  if (visible) fetchRemoteFiles(session.id);
                  setSessionFiles(prev => ({ ...prev, [session.id]: { ...prev[session.id], visible } }));
                }}
                className={`p-2.5 rounded-xl text-white shadow-lg border border-white/10 ${isFilesOpen ? 'bg-emerald-600' : 'bg-emerald-500/80 hover:bg-emerald-500'}`}
                title="Explorador de Archivos"
              >
                <FileText size={18} />
              </button>
              <button
                onClick={() => {
                  setIsDeviceLogsOpen(prev => !prev);
                }}
                className={`p-2.5 rounded-xl text-white shadow-lg border border-white/10 ${isDeviceLogsOpen ? 'bg-violet-600 shadow-violet-500/20' : 'bg-violet-500/80 hover:bg-violet-500'}`}
                title="Bitácora de Logs de Telemetría"
              >
                <Terminal size={18} />
              </button>
            </div>
          </div>

          {/* Paneles de Apoyo: Chat, Archivos y Logs */}
          {(isChatOpen || isFilesOpen || isDeviceLogsOpen) && (
            <div className="w-full lg:w-80 flex flex-col gap-4 overflow-y-auto">
              {isChatOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[250px]">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Chat de Soporte</h3>
                  <div className="flex-1 overflow-y-auto space-y-2 mb-3 pr-1 text-xs">
                    {(sessionChats[session.id] || []).map((msg: any, i: number) => (
                      <div key={i} className={`p-2.5 rounded-xl max-w-[85%] ${msg.sender_type === 'tech' ? 'bg-brand-500 text-white ml-auto' : 'bg-slate-800 text-slate-300'}`}>
                        {msg.message}
                      </div>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      id={`chat-input-${session.id}`}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          const input = e.currentTarget;
                          if (input.value.trim()) {
                            sendRemoteChat(session.id, input.value.trim());
                            input.value = '';
                          }
                        }
                      }}
                      className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 py-2 text-xs outline-none"
                      placeholder="Escribe al cliente..."
                    />
                  </div>
                </div>
              )}

              {isFilesOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[250px]">
                  <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 mb-3">Archivos Remotos</h3>
                  <div className="flex items-center gap-2 mb-2">
                    <input
                      type="text"
                      id={`path-input-${session.id}`}
                      defaultValue={sessionFiles[session.id]?.path || "C:\\"}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          fetchRemoteFiles(session.id, e.currentTarget.value);
                        }
                      }}
                      className="flex-1 bg-black/40 border border-white/10 rounded-xl px-2.5 py-1.5 text-xs font-mono outline-none"
                    />
                  </div>
                  <div className="flex-1 overflow-y-auto space-y-1.5 text-xs font-mono">
                    {sessionFiles[session.id]?.loading ? (
                      <div className="text-slate-500 animate-pulse text-center mt-4">Leyendo disco remoto...</div>
                    ) : (
                      (sessionFiles[session.id]?.files || []).map((f: any, idx: number) => (
                        <div key={idx} className="flex justify-between items-center p-1.5 hover:bg-white/5 rounded-lg">
                          <span
                            onClick={() => f.is_dir && fetchRemoteFiles(session.id, f.path)}
                            className={`cursor-pointer ${f.is_dir ? 'text-brand-400 font-bold' : 'text-slate-300'}`}
                          >
                            {f.is_dir ? '📁' : '📄'} {f.name}
                          </span>
                          {!f.is_dir && (
                            <button
                              onClick={() => downloadRemoteFile(session.id, f.path)}
                              className="text-[10px] text-emerald-400 hover:underline"
                            >
                              Bajar
                            </button>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                  <div className="mt-2 pt-2 border-t border-white/5">
                    <input
                      type="file"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleUploadFile(session.id, file);
                      }}
                      className="text-[10px] text-slate-500 cursor-pointer"
                    />
                  </div>
                </div>
              )}

              {isDeviceLogsOpen && (
                <div className="flex-1 bg-slate-900 border border-white/5 rounded-2xl p-4 flex flex-col min-h-[300px]">
                  <div className="flex items-center justify-between mb-3 border-b border-white/5 pb-2">
                    <h3 className="text-xs font-black uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                      <Terminal size={14} className="text-violet-400 animate-pulse" /> Logs de Telemetría
                    </h3>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => fetchDeviceLogs(session.id)}
                        className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 text-[10px] font-bold transition-all"
                        title="Actualizar ahora"
                      >
                        🔄
                      </button>
                      <button
                        onClick={() => handleClearTelemetryLogs(session.id)}
                        className="p-1 rounded bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white text-[10px] font-bold transition-all"
                        title="Limpiar logs"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                  
                  {/* Feed de Logs */}
                  <div className="flex-1 overflow-y-auto space-y-2 mb-2 pr-1 font-mono text-[10px] leading-tight select-text scrollbar-thin max-h-[400px]">
                    {deviceLogsLoading && deviceLogs.length === 0 ? (
                      <div className="flex flex-col items-center justify-center h-full text-slate-500 py-8">
                        <div className="animate-spin rounded-full h-4 w-4 border-2 border-brand-500 border-t-transparent mb-2" />
                        <span>Cargando logs...</span>
                      </div>
                    ) : deviceLogs.length === 0 ? (
                      <div className="text-center text-slate-500 italic py-8">
                        No hay logs registrados para este dispositivo.
                      </div>
                    ) : (
                      deviceLogs.map((log: any) => {
                        let levelColor = "text-slate-300 bg-slate-800/40 border-slate-700/20";
                        if (log.level === 'DEBUG') levelColor = "text-cyan-400 bg-cyan-950/20 border-cyan-800/10";
                        if (log.level === 'WARNING') levelColor = "text-amber-400 bg-amber-950/20 border-amber-800/10 animate-pulse";
                        if (log.level === 'ERROR') levelColor = "text-red-400 bg-red-950/20 border-red-800/20 font-bold border shadow-sm shadow-red-500/5";

                        return (
                          <div key={log.id} className={`p-2 rounded-lg border bg-slate-950/40 hover:bg-slate-950/60 transition-all`}>
                            <div className="flex items-center justify-between gap-1 mb-1 text-[9px] text-slate-500 border-b border-white/5 pb-0.5">
                              <span className="font-sans">
                                {new Date(log.timestamp).toLocaleTimeString('es-AR')}
                              </span>
                              <span className={`px-1 rounded text-[8px] font-extrabold uppercase ${levelColor.split(' ').slice(0,2).join(' ')}`}>
                                {log.level}
                              </span>
                            </div>
                            <p className={`whitespace-pre-wrap break-all ${log.level === 'ERROR' ? 'text-red-300' : log.level === 'WARNING' ? 'text-amber-300' : 'text-slate-300'}`}>
                              {log.message}
                            </p>
                          </div>
                        );
                      })
                    )}
                  </div>
                  
                  {/* Pie de Panel */}
                  <div className="flex items-center justify-between text-[9px] text-slate-500 border-t border-white/5 pt-2">
                    <span className="flex items-center gap-1">
                      <span className={`w-1.5 h-1.5 rounded-full ${logsAutoRefresh ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                      {logsAutoRefresh ? 'Auto-refrescando' : 'Pausado'}
                    </span>
                    <button 
                      onClick={() => setLogsAutoRefresh(v => !v)}
                      className="text-brand-400 hover:text-brand-300 font-bold"
                    >
                      {logsAutoRefresh ? 'Pausar' : 'Activar'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Barra de Teclado, Consola y Teclas Rápidas */}
        <div className="mt-3 p-3 bg-slate-900 border border-white/5 rounded-2xl flex flex-col gap-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Consola */}
            <div className="flex gap-2 items-center">
              <span className="text-[10px] uppercase font-black text-slate-500 w-16">Consola:</span>
              <input
                type="text"
                value={cmdInfo.current}
                onChange={(e) => setSessionCmds({ ...sessionCmds, [session.id]: { ...cmdInfo, current: e.target.value } })}
                onKeyDown={(e) => e.key === 'Enter' && handleSendCommand(session.id)}
                className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-emerald-400 font-mono outline-none"
                placeholder="Comando de sistema..."
              />
              <button onClick={() => handleSendCommand(session.id)} className="bg-emerald-600 p-2 rounded-xl text-white hover:bg-emerald-700 transition-all">
                <ArrowUpRight size={16} />
              </button>
            </div>

            {/* Teclado */}
            <div className="flex gap-2 items-center">
              <span className="text-[10px] uppercase font-black text-slate-500 w-16">Teclado:</span>
              <input
                type="text"
                id={`text-input-${session.id}`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    const input = e.currentTarget;
                    if (input.value) {
                      sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                      input.value = '';
                    }
                  }
                }}
                className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-brand-400 font-mono outline-none"
                placeholder="Escribe texto y presiona Enter para escribirlo allá..."
              />
              <button
                onClick={() => {
                  const input = document.getElementById(`text-input-${session.id}`) as HTMLInputElement;
                  if (input && input.value) {
                    sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                    input.value = '';
                  }
                }}
                className="bg-brand-500 p-2 rounded-xl text-white hover:bg-brand-600 transition-all"
              >
                <Sparkles size={16} />
              </button>
            </div>
          </div>

          {/* Teclas Rápidas */}
          <div className="flex gap-2 items-center flex-wrap pl-0 md:pl-16">
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'enter' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ⏎ Enter
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'escape' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ⎋ Esc
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'tab' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ⇥ Tab
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'backspace' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ⌫ Borrar
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'space' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ␣ Espacio
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'ctrl+shift+enter' })} className="bg-brand-500/20 hover:bg-brand-500/40 text-[10px] font-extrabold text-brand-400 px-3 py-1.5 rounded-lg border border-brand-500/30 transition-all" title="Envia la combinación CTRL + SHIFT + ENTER a la PC remota">
              ⚡ Ctrl + Shift + Enter
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'ctrl+alt+del' })} className="bg-red-500/20 hover:bg-red-500/40 text-[10px] font-extrabold text-red-400 px-3 py-1.5 rounded-lg border border-red-500/30 transition-all" title="Envia la combinación de seguridad CTRL + ALT + SUP (Ctrl+Alt+Del) para desbloquear la pantalla de Windows">
              🚨 Ctrl + Alt + Sup
            </button>
            <span className="text-slate-600 text-xs font-bold px-2">|</span>
            {/* Flechas de Navegación */}
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'up' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ▲ Arriba
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'down' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ▼ Abajo
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'left' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ◀ Izquierda
            </button>
            <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'right' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
              ▶ Derecha
            </button>
          </div>
        </div>

        {/* MODAL DE COMENTARIO Y REPORTE IA AL FINALIZAR SESIÓN (NUEVO) */}
        {/* 🔑 MODAL LOGIN SESIÓN WINDOWS */}
        {showLoginModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 backdrop-blur-md p-4 animate-in fade-in">
            <div className="w-full max-w-sm p-6 rounded-2xl border border-white/10 glass-dark shadow-2xl flex flex-col gap-5 animate-in slide-in-from-bottom-8">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-violet-400 font-bold text-[10px] uppercase tracking-widest bg-violet-500/10 px-2 py-0.5 rounded-full">
                    Acceso Windows
                  </span>
                  <h3 className="text-base font-black text-white mt-1">Iniciar Sesión Remota</h3>
                </div>
                <button onClick={() => setShowLoginModal(false)} className="text-slate-500 hover:text-white p-1">✕</button>
              </div>

              <div className="flex flex-col gap-3">
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Usuario</label>
                  <input
                    type="text"
                    value={loginCreds.username}
                    onChange={e => setLoginCreds(c => ({...c, username: e.target.value}))}
                    placeholder="nombre.usuario"
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">
                    Dominio <span className="text-slate-600 font-normal normal-case">(opcional, dejar '.' para local)</span>
                  </label>
                  <input
                    type="text"
                    value={loginCreds.domain}
                    onChange={e => setLoginCreds(c => ({...c, domain: e.target.value}))}
                    placeholder="."
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider mb-1 block">Contraseña</label>
                  <input
                    type="password"
                    value={loginCreds.password}
                    onChange={e => setLoginCreds(c => ({...c, password: e.target.value}))}
                    placeholder="••••••••"
                    onKeyDown={e => {
                      if (e.key === 'Enter' && loginCreds.username && loginCreds.password) {
                        setLoginLoading(true); setLoginError('');
                        sendViewerCommand({ type: 'login_session', ...loginCreds });
                      }
                    }}
                    className="w-full bg-slate-800 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-slate-600 focus:outline-none focus:border-violet-500/50"
                  />
                </div>
                {loginError && (
                  <div className="text-red-400 text-xs bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                    ⚠ {loginError}
                  </div>
                )}
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => setShowLoginModal(false)}
                  className="flex-1 py-2 rounded-xl text-xs font-bold bg-slate-700 hover:bg-slate-600 text-slate-300 transition-all"
                >Cancelar</button>
                <button
                  onClick={() => {
                    if (!loginCreds.username || !loginCreds.password) return;
                    setLoginLoading(true); setLoginError('');
                    sendViewerCommand({ type: 'login_session', ...loginCreds });
                  }}
                  disabled={loginLoading || !loginCreds.username || !loginCreds.password}
                  className="flex-1 py-2 rounded-xl text-xs font-bold bg-violet-600 hover:bg-violet-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {loginLoading ? '⏳ Iniciando...' : '🔑 Iniciar Sesión'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* 🔄 OVERLAY CAMBIO DE SESION */}
        {sessionSwitching && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/80 backdrop-blur-md animate-in fade-in">
            <div className="text-center flex flex-col items-center gap-4">
              <div className="w-12 h-12 border-4 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <p className="text-white font-bold">Cambiando sesión...</p>
              <p className="text-slate-400 text-xs">El agente se reconectará en la nueva sesión</p>
            </div>
          </div>
        )}

        {showEndSessionModal && (

          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-950/90 backdrop-blur-md p-4 overflow-y-auto animate-in fade-in">
            <div className="w-full max-w-xl p-6 sm:p-8 rounded-[2rem] border border-brand-500/15 glass-dark shadow-2xl flex flex-col gap-6 animate-in slide-in-from-bottom-8">
              
              {/* Cabecera */}
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-indigo-400 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-indigo-500/10 px-3 py-1 rounded-full mb-2 inline-block">
                    Mantenimiento de Bitácora
                  </span>
                  <h3 className="text-lg sm:text-xl font-black text-white">Finalizar Sesión de Soporte</h3>
                </div>
                {!endSessionResult && (
                  <button 
                    onClick={() => setShowEndSessionModal(false)}
                    className="text-slate-400 hover:text-white p-2 hover:bg-white/5 rounded-xl transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                )}
              </div>

              {!endSessionResult ? (
                /* PASO 1: Ingresar Comentarios */
                <div className="flex flex-col gap-4">
                  <p className="text-xs text-slate-400">
                    Por favor, ingresa un comentario con los detalles de las tareas realizadas en este equipo. El sistema combinará estas notas con las acciones del terminal para compilar el reporte automático de IA.
                  </p>
                  
                  <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] sm:text-xs font-bold text-slate-400 uppercase tracking-wider">¿Qué se hizo en esta PC? *</label>
                    <textarea
                      value={endSessionComment}
                      onChange={(e) => setEndSessionComment(e.target.value)}
                      placeholder="Ej: Se destrabó spooler fiscal y se borraron archivos corruptos de FoxPro..."
                      className="bg-slate-900/50 border border-white/5 rounded-2xl p-4 text-sm text-white focus:outline-none focus:ring-2 focus:ring-brand-500 h-28 resize-none transition-all placeholder:text-slate-600"
                    />
                  </div>

                  <div className="flex gap-3 mt-4">
                    <button
                      type="button"
                      onClick={() => setShowEndSessionModal(false)}
                      className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white transition-colors"
                    >
                      Volver
                    </button>
                    <button
                      type="button"
                      disabled={isFinishingSession || !endSessionComment.trim()}
                      onClick={() => handleEndSessionSupport(session.id)}
                      className="flex-1 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider flex items-center justify-center gap-2"
                    >
                      {isFinishingSession ? (
                        <>
                          <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
                          Generando...
                        </>
                      ) : (
                        'Grabar y Generar Reporte'
                      )}
                    </button>
                  </div>
                </div>
              ) : (
                /* PASO 2: Mostrar reporte finalizado y reporte de IA */
                <div className="flex flex-col gap-4">
                  <div className="bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-2xl text-center">
                    <CheckCircle2 className="w-8 h-8 text-emerald-400 mx-auto mb-2" />
                    <h4 className="text-sm font-black text-emerald-400 uppercase tracking-wider">¡Sesión Cerrada con Éxito!</h4>
                    <p className="text-xs text-slate-400 mt-1">La bitácora y el análisis han sido almacenados de forma permanente.</p>
                  </div>

                  {endSessionResult.duration !== undefined && (
                    <div className="text-xs text-slate-500 text-center font-mono">
                      Duración total de conexión: <strong className="text-slate-300">{Math.round(endSessionResult.duration / 60)} minutos</strong>
                    </div>
                  )}

                  {endSessionResult.ai_report && (
                    <div className="bg-slate-900/50 border border-white/5 p-4 rounded-2xl flex flex-col gap-2">
                      <span className="text-indigo-400 font-black text-[10px] sm:text-xs uppercase tracking-widest flex items-center gap-1.5 mb-1">
                        <Sparkles className="w-4 h-4 text-indigo-400 animate-pulse" /> Reporte de Actividad Consolidado por IA
                      </span>
                      <div className="text-slate-300 text-xs sm:text-sm space-y-1 pl-1 font-sans leading-relaxed">
                        {endSessionResult.ai_report.split('\n').map((line: string, i: number) => {
                          if (line.trim().startsWith('*') || line.trim().startsWith('-')) {
                            return <div key={i} className="flex gap-1.5 items-start pl-1">
                              <span className="text-indigo-500 font-bold">•</span>
                              <span>{line.replace(/^[\*\-\s]+/, '')}</span>
                            </div>;
                          }
                          return <p key={i}>{line}</p>;
                        })}
                      </div>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => {
                      window.close();
                    }}
                    className="w-full bg-slate-800 hover:bg-slate-700 text-white font-extrabold py-3.5 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider mt-4"
                  >
                    Salir y Cerrar Ventana
                  </button>
                </div>
              )}

            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden selection:bg-brand-500/30">
      {/* Backdrop traslúcido para móvil */}
      {isSidebarOpen && (
        <div 
          onClick={() => setIsSidebarOpen(false)}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[40] lg:hidden animate-in fade-in duration-200"
        />
      )}

      <aside className={`
        fixed lg:static inset-y-0 left-0 w-64 flex flex-col transition-all duration-300 border-r z-[50]
        ${darkMode ? 'glass-dark border-dark-border bg-slate-950/95' : 'glass border-slate-200 bg-white'}
        ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
      `}>
        <div className="h-[72px] flex items-center px-6 border-b border-opacity-10 border-white">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-400 to-orange-600 flex items-center justify-center text-white font-bold text-xl mr-3 shadow-lg shadow-brand-500/30">A</div>
          <span className="text-xl font-extrabold tracking-tight">
            <span className="text-slate-800 dark:text-white">Apollo</span>
            <span className="text-brand-500">Support</span>
          </span>
        </div>

        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Vistas Principales</p>
            <NavItem icon={<Ticket size={20} />} text="Bandeja Unificada" badge={tickets.length > 0 ? tickets.length.toString() : ""} active={activeTab === 'tickets' && selectedArea === null} onClick={() => { setActiveTab('tickets'); setSelectedArea(null); setIsSidebarOpen(false); }} />
            <NavItem icon={<Monitor size={20} />} text="Terminal Remota" badge="En Vivo" active={activeTab === 'monitor'} onClick={() => { setActiveTab('monitor'); setIsSidebarOpen(false); }} />
            <NavItem icon={<Users size={20} />} text="Base Clientes" active={activeTab === 'clients'} onClick={() => { setActiveTab('clients'); setIsSidebarOpen(false); }} />
          </div>

          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sectores Operativos</p>
            {areas.map(area => (
              <NavItem
                key={area.id}
                icon={<Folder size={18} className={selectedArea === area.id ? "text-brand-500" : "text-slate-400"} />}
                text={area.nombre}
                active={activeTab === 'tickets' && selectedArea === area.id}
                onClick={() => { setActiveTab('tickets'); setSelectedArea(area.id); setIsSidebarOpen(false); }}
              />
            ))}
          </div>

          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Control Interno</p>
            <NavItem icon={<Activity size={20} />} text="Plantel de Personal" active={activeTab === 'personnel'} onClick={() => { setActiveTab('personnel'); setIsSidebarOpen(false); }} />
          </div>

          <div className="mb-4">
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Diagnóstico</p>
            <NavItem icon={<Terminal size={20} />} text="Bitácora de Logs" active={activeTab === 'logs'} onClick={() => { setActiveTab('logs'); setIsSidebarOpen(false); }} />
          </div>

          <div>
            <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-2 mb-2">Sistema</p>
            <NavItem icon={<Sparkles size={20} />} text="IA Copiloto" badge="Beta" onClick={() => setIsSidebarOpen(false)} />
            <NavItem icon={<FileText size={20} />} text="Licencias" active={activeTab === 'licenses'} onClick={() => { setActiveTab('licenses'); setIsSidebarOpen(false); }} />
            <NavItem icon={<Settings size={20} />} text="Ajustes" active={activeTab === 'settings'} onClick={() => { setActiveTab('settings'); setIsSidebarOpen(false); }} />
          </div>
        </nav>

        <div className="p-4 border-t border-opacity-10 border-white relative group">
          <div 
            onClick={() => {
              setProfileForm({
                nombre: userProfile?.nombre || '',
                full_name: userProfile?.full_name || '',
                celular: userProfile?.celular || '',
                departamento: userProfile?.departamento || '',
                password: '',
                profile_picture: userProfile?.profile_picture || ''
              });
              setShowProfileModal(true);
            }}
            className="flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors border border-transparent hover:border-white/10 shadow-sm cursor-pointer"
          >
            {userProfile?.profile_picture ? (
              <img src={userProfile.profile_picture} alt="Avatar" className="w-10 h-10 rounded-full shadow-md border-2 border-brand-500/50 object-cover" />
            ) : (
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-xs shadow-md border-2 border-brand-500/50 shrink-0">
                {(userProfile?.full_name || userProfile?.nombre || 'AG').substring(0, 2).toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate text-slate-800 dark:text-white">{userProfile?.full_name || userProfile?.nombre || 'Agente'}</p>
              <p className="text-xs text-brand-500 font-medium truncate uppercase">{userProfile?.rol || 'Soporte'} {userProfile?.departamento ? `| ${userProfile.departamento}` : ''}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="absolute right-6 top-[28px] p-2 rounded-full hidden group-hover:flex bg-red-500 text-white shadow-lg animate-in fade-in zoom-in transition hover:bg-red-600">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative w-full bg-slate-50 dark:bg-dark-bg/95 transition-colors">
        <div className="absolute top-[-15%] left-[10%] w-[50%] h-[50%] bg-brand-500/10 rounded-full blur-[140px] pointer-events-none" />

        <header className={`h-[72px] flex items-center justify-between px-4 sm:px-8 border-b transition-colors duration-300 z-10 ${darkMode ? 'bg-dark-bg/50 border-dark-border backdrop-blur-md' : 'bg-white/60 border-slate-200 backdrop-blur-md'}`}>
          <div className="flex items-center gap-3 sm:gap-4 flex-1 min-w-0">
            <button
              onClick={() => setIsSidebarOpen(true)}
              className="lg:hidden p-2 rounded-xl border border-slate-200 dark:border-dark-border hover:bg-slate-100 dark:hover:bg-white/5 transition-all text-slate-600 dark:text-slate-300"
            >
              <Menu size={20} />
            </button>
            <div className={`flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 rounded-xl w-full max-w-[150px] sm:max-w-xs md:max-w-md lg:w-96 transition-all ring-1 focus-within:ring-2 focus-within:ring-brand-500 ${darkMode ? 'bg-dark-card/50 ring-dark-border shadow-inner' : 'bg-white ring-slate-200 shadow-sm'}`}>
              <Search size={16} className="text-slate-400 shrink-0" />
              <input 
                type="text" 
                placeholder="Buscador global..." 
                value={globalSearchTerm}
                onChange={e => {
                  const val = e.target.value;
                  setGlobalSearchTerm(val);
                  setClientSearchTerm(val);
                }}
                className="bg-transparent border-none outline-none w-full text-xs sm:text-sm font-medium placeholder:text-slate-400" 
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2.5 rounded-full bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:border-brand-500/50 transition-all shadow-sm">
              <Bell size={18} className="text-slate-600 dark:text-slate-300" />
            </button>
            <button onClick={() => setDarkMode(!darkMode)} className="p-2.5 rounded-full bg-white dark:bg-dark-card border border-slate-200 dark:border-dark-border hover:border-brand-500/50 transition-all shadow-sm group">
              {darkMode ? <Sun size={18} className="text-amber-400 group-hover:scale-110" /> : <Moon size={18} className="text-indigo-500 group-hover:scale-110" />}
            </button>
          </div>
        </header>

        {showNotification && (
          <div className="fixed top-20 right-8 z-[100] animate-in slide-in-from-right-full">
            <div className="bg-red-600 text-white px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-4 border border-red-500 ring-4 ring-red-500/10">
              <Bell className="animate-bounce" />
              <div>
                <p className="font-black text-sm uppercase tracking-tighter">Atención Inmediata</p>
                <p className="text-xs font-bold opacity-90">{showNotification}</p>
              </div>
              <button onClick={() => setShowNotification(null)} className="ml-4 hover:bg-white/20 p-1 rounded-full transition-colors"><X size={16} /></button>
            </div>
          </div>
        )}

        <div className="flex-1 overflow-auto p-4 sm:p-8 z-10 relative">
          <div className="max-w-7xl mx-auto space-y-6 sm:space-y-8 animate-in fade-in duration-700">
            {activeTab === 'tickets' && (
              <>
                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                  <div><h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">Análisis Operativo</h1></div>
                  <button onClick={() => setIsModalOpen(true)} className="w-full sm:w-auto bg-brand-500 hover:bg-brand-600 text-white px-6 py-2.5 rounded-xl font-bold shadow-[0_0_15px_rgba(245,158,11,0.3)] transition-all hover:-translate-y-1 text-center text-xs sm:text-sm">
                    + Cargar Derivación
                  </button>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 pb-0"><h2 className="text-lg font-bold">Solicitudes Recientes</h2></div>
                  <div className="p-4 mt-2">
                    <div className="hidden md:grid grid-cols-12 gap-4 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">ID</div><div className="col-span-3">Empresa</div><div className="col-span-4">Asunto del Problema</div><div className="col-span-2">Estado</div><div className="col-span-2">Urgencia</div>
                    </div>
                    <div className="space-y-1 mt-2 min-h-[150px]">
                      {loading ? <div className="flex justify-center p-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-500"></div></div> :
                        tickets.length === 0 ? <div className="text-center p-8 text-slate-400">Excelente, sin tickets pendientes en cola.</div> :
                          tickets.map((t: any) => {
                            const c = clients.find(cl => cl.id === t.client_id);
                            return (
                              <div key={t.id} onClick={() => openTicketModal({ ...t, clientName: c?.razon_social })}>
                                <TicketRow id={`#${t.id}`} client={c ? c.razon_social : "Desconocido"} subject={t.asunto} status={t.estado} priority={t.prioridad} darkMode={darkMode} />
                              </div>
                            )
                          })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'monitor' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-8">
                <div className="flex items-end justify-between">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Flota de Terminales <span className="relative flex h-4 w-4"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span><span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span></span>
                    </h1>
                    <p className="text-slate-400 mt-2">Visor maestro de las computadoras registradas por cliente.</p>
                  </div>
                </div>

                {pendingDevices && pendingDevices.length > 0 && (
                  <div className="p-6 rounded-[2rem] bg-gradient-to-br from-indigo-500/10 via-purple-500/5 to-transparent border border-indigo-500/20 shadow-2xl space-y-4 animate-in zoom-in-95">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className="relative flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-indigo-500"></span>
                        </span>
                        <h2 className="text-lg font-black text-indigo-400">🚨 Terminales en Espera de Licencia ({pendingDevices.length})</h2>
                      </div>
                      <span className="text-xs font-bold text-slate-500 bg-slate-500/10 px-3 py-1 rounded-full uppercase">Autodetectado</span>
                    </div>
                    <p className="text-xs text-slate-400">
                      Estas terminales han iniciado el agente Centinela por primera vez sin configurar una clave de licencia. Puedes asignarlas a un cliente de inmediato para activarlas de forma remota y sin intervención del usuario.
                    </p>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-2">
                      {pendingDevices.map((dev: any) => (
                        <div key={dev.id} className="p-4 rounded-2xl border border-indigo-500/20 bg-slate-900/60 flex flex-col gap-3 hover:border-indigo-500/40 transition-all group">
                          {/* Cabecera: nombre + botones */}
                          <div className="flex items-start justify-between gap-2">
                            <div>
                              <span className="text-[10px] font-extrabold text-indigo-400 uppercase tracking-widest block">Nombre del Equipo</span>
                              <span className="text-sm font-black text-white">{dev.device_name}</span>
                            </div>
                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                onClick={() => {
                                  setAssignModal(dev);
                                  setAssignClientId("");
                                  setAssignSearchText("");
                                  setShowAssignDropdown(false);
                                }}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white font-extrabold text-[10px] px-3 py-2 rounded-xl transition-all shadow-md shadow-indigo-600/10 whitespace-nowrap"
                              >
                                Asignar Licencia
                              </button>
                              <button
                                onClick={() => handleDeleteDevice(dev.id)}
                                className="p-2 rounded-xl bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white transition-all"
                                title="Rechazar / Eliminar"
                              >
                                <Trash2 size={14} />
                              </button>
                            </div>
                          </div>

                          {/* Info de identificación */}
                          <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
                            {/* Fecha de registro */}
                            {dev.last_seen && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🕐 Detectado:</span>
                                <span className="font-bold text-slate-300">
                                  {new Date(dev.last_seen).toLocaleString('es-AR', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'})}
                                </span>
                              </div>
                            )}

                            {/* Sistema operativo */}
                            {(dev.system_info?.windows_name || dev.os) && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🪟</span>
                                <span className="font-semibold text-slate-300 truncate">{dev.system_info?.windows_name || dev.os}</span>
                                {dev.system_info?.windows_build && (
                                  <span className="text-slate-500 ml-1">Build {dev.system_info.windows_build}</span>
                                )}
                              </div>
                            )}

                            {/* Usuario logueado */}
                            {dev.system_info?.logged_user && (
                              <div className="col-span-2 flex items-center gap-1">
                                <span className="text-slate-500">👤</span>
                                <span className="font-bold text-cyan-400">{dev.system_info.user_full || dev.system_info.logged_user}</span>
                              </div>
                            )}

                            {/* CPU y RAM en vivo */}
                            {(dev.cpu !== null && dev.cpu !== undefined) && (
                              <div className="flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">⚡</span>
                                <span>CPU <span className="font-bold text-white">{dev.cpu}%</span></span>
                              </div>
                            )}
                            {(dev.ram !== null && dev.ram !== undefined) && (
                              <div className="flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🧠</span>
                                <span>RAM <span className="font-bold text-white">{dev.ram}%</span></span>
                              </div>
                            )}

                            {/* Último Windows Update */}
                            {dev.system_info?.last_windows_update && dev.system_info.last_windows_update !== 'No disponible' && (
                              <div className="col-span-2 flex items-center gap-1 text-slate-400">
                                <span className="text-slate-500">🔄 Último update:</span>
                                <span className="font-bold text-amber-400">{dev.system_info.last_windows_update}</span>
                              </div>
                            )}

                            {/* IPs */}
                            {dev.system_info?.network_ips && dev.system_info.network_ips.length > 0 && (
                              <div className="col-span-2 flex flex-wrap gap-1 mt-0.5">
                                {dev.system_info.network_ips.slice(0, 3).map((n: any, i: number) => (
                                  <span key={i} className="font-mono text-[9px] bg-slate-800 text-emerald-400 px-1.5 py-0.5 rounded-md border border-slate-700">
                                    {n.ip}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Propuesta de cliente por serial */}
                            {dev.proposed_client && (
                              <div className="col-span-2 flex items-center gap-1 mt-1 bg-indigo-500/10 border border-indigo-500/20 rounded-lg px-2 py-1">
                                <span className="text-indigo-400 text-[10px]">💡 Posible cliente:</span>
                                <span className="font-extrabold text-indigo-300 text-[10px]">{dev.proposed_client.razon_social}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                  {clients.filter(client => {
                    if (!globalSearchTerm) return true;
                    const term = globalSearchTerm.toLowerCase();
                    const matchSocial = client.razon_social?.toLowerCase().includes(term);
                    const matchFantasia = client.nombre_fantasia?.toLowerCase().includes(term);
                    const matchLocalidad = client.localidad?.toLowerCase().includes(term);
                    const matchCodigo = client.codigo?.toLowerCase().includes(term);
                    const matchFac = client.cclifac?.toLowerCase().includes(term);
                    return matchSocial || matchFantasia || matchLocalidad || matchCodigo || matchFac;
                  }).sort((a, b) => {
                    const aMaxSeen = a.devices && a.devices.length > 0
                      ? Math.max(...a.devices.map((d: any) => d.last_seen ? new Date(d.last_seen).getTime() : 0))
                      : 0;
                    const bMaxSeen = b.devices && b.devices.length > 0
                      ? Math.max(...b.devices.map((d: any) => d.last_seen ? new Date(d.last_seen).getTime() : 0))
                      : 0;
                    return bMaxSeen - aMaxSeen; // Descending (newest activity first)
                  }).map(client => {
                    const sortedDevices = [...(client.devices || [])].sort((da, db) => {
                      const daOnline = centinelas[da.id] ? 1 : 0;
                      const dbOnline = centinelas[db.id] ? 1 : 0;
                      if (daOnline !== dbOnline) return dbOnline - daOnline;
                      const daSeen = da.last_seen ? new Date(da.last_seen).getTime() : 0;
                      const dbSeen = db.last_seen ? new Date(db.last_seen).getTime() : 0;
                      return dbSeen - daSeen;
                    });

                    const clientLic = licenses.find(lic => lic.client_id === client.id);

                    return (
                      <div key={client.id} className={`p-6 rounded-[2rem] border shadow-2xl ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                        <h3 className="text-xl font-black mb-4 flex items-center justify-between text-brand-500">
                          {client.razon_social}
                          <span className="text-[10px] bg-brand-500/10 px-3 py-1 rounded-full uppercase tracking-widest">{client.devices?.length || 0} PCs</span>
                        </h3>

                        <div className="flex items-center gap-2 mb-3 -mt-2">
                          {clientLic ? (
                            <div className="flex items-center gap-2 bg-brand-500/10 text-brand-500 border border-brand-500/20 px-3 py-1.5 rounded-2xl text-xs font-mono select-all hover:bg-brand-500/20 transition-all cursor-pointer shadow-sm" title="Doble clic o clic largo para copiar clave">
                              🔑 <span className="font-extrabold tracking-wider">{clientLic.license_key}</span>
                            </div>
                          ) : (
                            <div className="flex items-center gap-1.5 bg-slate-500/10 text-slate-400 border border-slate-500/25 px-3 py-1.5 rounded-2xl text-[10px] font-black uppercase tracking-wider">
                              Sin Clave Soporte
                            </div>
                          )}
                        </div>

                        {/* Fila de Acciones de Gestión de Cliente (Siempre Visibles, Altamente Responsivas) */}
                        <div className="grid grid-cols-2 gap-2 mb-4">
                          {/* Botón Ver Extracto (Siempre Visible, Deshabilitado si no posee cclifac) */}
                          <button
                            onClick={() => {
                              if (!client.cclifac) {
                                alert(`El cliente ${client.razon_social} no posee un código de facturación (CCLIFAC) configurado en el sistema.`);
                                return;
                              }
                              handleOpenExtracto(client);
                            }}
                            className={`flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-2xl text-xs font-black transition-all border ${
                              client.cclifac
                                ? 'bg-indigo-500/10 hover:bg-indigo-500/25 text-indigo-400 border-indigo-500/20 hover:border-indigo-500/40 cursor-pointer shadow-sm hover:-translate-y-0.5'
                                : 'bg-slate-500/5 text-slate-500 border-slate-500/10 cursor-not-allowed opacity-40'
                            }`}
                            title={client.cclifac ? "Ver Extracto de Cuenta Corriente en Tiempo Real" : "No posee código de vinculación de facturación (CCLIFAC)"}
                          >
                            <FileText size={13} />
                            <span>Extracto ERP</span>
                          </button>

                          {/* Botón Administrar Activaciones/Licencias ERP (Siempre Visible y Activo) */}
                          <button
                            onClick={() => {
                              openClientModal(client);
                              setClientActiveTab('erp_licensing');
                            }}
                            className="flex items-center justify-center gap-1.5 px-3 py-2.5 bg-brand-500/10 hover:bg-brand-500/25 text-brand-500 border border-brand-500/20 hover:border-brand-500/40 rounded-2xl text-xs font-black transition-all shadow-sm cursor-pointer hover:-translate-y-0.5"
                            title="Gestionar Licencias, Seriales y Activaciones ERP"
                          >
                            <Key size={13} />
                            <span>Licencias ERP</span>
                          </button>
                        </div>

                        <div className="space-y-2">
                          {(!sortedDevices || sortedDevices.length === 0) ? (
                            <p className="text-xs text-slate-500 italic p-4 text-center">Sin dispositivos registrados aún.</p>
                          ) : (
                            sortedDevices.map((dev: any) => {
                              const telemetry = centinelas[dev.id];
                              const isOnline = !!telemetry;
                              const isBusy = dev.current_technician_id !== null;

                              return (
                                <div key={dev.id} className={`p-4 rounded-2xl border transition-all flex items-center justify-between group ${isOnline ? (isBusy ? 'bg-amber-500/5 border-amber-500/20' : 'bg-emerald-500/5 border-emerald-500/20') : 'bg-slate-500/5 border-slate-500/10 grayscale opacity-70'}`}>
                                  <div className="flex items-center gap-3">
                                    <div className={`w-3 h-3 rounded-full ${isOnline ? (isBusy ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.4)]' : 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.4)]') : 'bg-slate-400'}`} />
                                    <div>
                                      <div className="text-sm font-extrabold flex items-center gap-2">{dev.device_name}{(telemetry?.remote_password || dev.remote_password) && (<span className="text-[10px] font-mono bg-brand-500/10 text-brand-500 px-2.5 py-0.5 rounded-full flex items-center gap-1 shadow-sm">🔑 {telemetry?.remote_password || dev.remote_password}</span>)}</div>
                                      <div className="flex items-center gap-2 text-[9px] uppercase font-bold text-slate-500">
                                        {isOnline ? (
                                          <>CPU: {telemetry?.cpu || 0}% | RAM: {telemetry?.ram || 0}%</>
                                        ) : 'Desconectado'}
                                      </div>
                                      {/* Info extendida del sistema — viene de system_info en telemetría */}
                                      {isOnline && telemetry?.system_info && (
                                        <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 mt-0.5">
                                          {telemetry.system_info.logged_user && (
                                            <span className="text-[9px] text-cyan-400 font-bold">
                                              👤 {telemetry.system_info.user_full || telemetry.system_info.logged_user}
                                            </span>
                                          )}
                                          {telemetry.system_info.windows_name && (
                                            <span className="text-[9px] text-slate-400 font-semibold">
                                              🪟 {telemetry.system_info.windows_name}
                                            </span>
                                          )}
                                          {telemetry.system_info.last_windows_update && telemetry.system_info.last_windows_update !== 'No disponible' && (
                                            <span className="text-[9px] text-amber-400 font-semibold">
                                              🔄 Update: {telemetry.system_info.last_windows_update}
                                            </span>
                                          )}
                                          {telemetry.system_info.antivirus && telemetry.system_info.antivirus !== 'No detectado' && (
                                            <span className="text-[9px] text-emerald-400 font-semibold">
                                              🛡️ {telemetry.system_info.antivirus}
                                            </span>
                                          )}
                                        </div>
                                      )}
                                      {renderLastErpUpdate(dev.last_erp_update, telemetry)}
                                    </div>
                                  </div>

                                  <div className="flex items-center gap-2">
                                    {isBusy && (
                                      <div className="flex flex-col items-end mr-2">
                                        <span className="text-[8px] font-black text-amber-500 uppercase tracking-widest">Ocupado por</span>
                                        <span className="text-[10px] font-extrabold text-amber-400">{dev.technician_name || 'Técnico'}</span>
                                        <span className="text-[9px] font-bold text-slate-400">Hace {Math.floor((new Date().getTime() - new Date(dev.session_start).getTime()) / 60000)}m</span>
                                      </div>
                                    )}
                                  <button
                                    onClick={() => setDeviceNotesModal({ deviceId: dev.id, name: dev.device_name, notes: dev.notes || "" })}
                                    className={`p-2.5 rounded-xl transition-all shadow-sm ${
                                      dev.notes
                                        ? 'bg-purple-500/20 text-purple-400 hover:bg-purple-500 hover:text-white border border-purple-500/30'
                                        : 'bg-slate-500/10 hover:bg-slate-500 text-slate-400 hover:text-white border border-transparent'
                                    }`}
                                    title="Notas y Recordatorios (Claves Windows, etc.)"
                                  >
                                    <FileText size={16} />
                                  </button>
                                  <button
                                    onClick={() => {
                                      if (isOnline) {
                                        handleVerifyRemotePassword(dev.id, dev.remote_password);
                                      }
                                    }}
                                    disabled={!isOnline}
                                    className={`p-2.5 rounded-xl transition-all ${isOnline ? 'bg-brand-500 text-white hover:bg-brand-600 shadow-lg shadow-brand-500/20' : 'bg-slate-200 text-slate-400'}`}
                                  >
                                    <Monitor size={16} />
                                  </button>
                                  <button
                                    onClick={() => handleDeleteDevice(dev.id)}
                                    className="p-2.5 rounded-xl bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white transition-all shadow-sm"
                                    title="Eliminar dispositivo (libera cupo)"
                                  >
                                    <Trash2 size={16} />
                                  </button>
                                </div>
                              </div>
                            );
                          })
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              </div>
            )}

            {activeTab === 'clients' && (
              <>
                <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight">Base Maestra de Clientes</h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-2">Gestión centralizada de licencias y empresas ApolloGesCom.</p>
                  </div>
                  <div className="flex gap-3 w-full sm:w-auto">
                    <button
                      onClick={async () => {
                        setIsSyncing(true);
                        try {
                          await syncClientsFromDbf();
                          setShowNotification("¡Clientes sincronizados con CLIGESCO.DBF!");
                          setTimeout(() => setShowNotification(null), 3000);
                          loadData();
                        } catch (err: any) {
                          alert(err.message || "Error al sincronizar");
                        } finally {
                          setIsSyncing(false);
                        }
                      }}
                      disabled={isSyncing}
                      className={`flex items-center justify-center gap-2 w-full sm:w-auto px-5 py-2.5 rounded-xl font-bold shadow-md transition-all text-xs sm:text-sm border ${darkMode ? 'bg-slate-900 border-white/10 text-slate-300 hover:bg-slate-800' : 'bg-white border-slate-200 text-slate-700 hover:bg-slate-50'}`}
                    >
                      <Sparkles className={`w-4 h-4 text-brand-500 ${isSyncing ? 'animate-spin' : ''}`} />
                      {isSyncing ? 'Sincronizando...' : 'Sincronizar ERP'}
                    </button>
                    <button onClick={() => openClientModal()} className="w-full sm:w-auto bg-emerald-600 hover:bg-emerald-700 text-white px-6 py-2.5 rounded-xl font-bold shadow-lg transition-all hover:-translate-y-1 text-center text-xs sm:text-sm">
                      + Nueva Empresa
                    </button>
                  </div>
                </div>

                {/* Panel de Totalizadores */}
                <div className="flex mt-6 animate-in fade-in slide-in-from-top-4 duration-300">
                  {/* Card 1: Total Clientes Activos */}
                  <div className={`w-full sm:w-72 p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-slate-900/40 hover:bg-slate-900/60' : 'bg-white border-slate-200 hover:shadow-md hover:border-slate-300'}`}>
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Clientes Activos</p>
                        <h3 className="text-2xl sm:text-3xl font-extrabold text-slate-800 dark:text-white mt-2">
                          {clients.length}
                        </h3>
                      </div>
                      <div className={`p-3 rounded-xl ${darkMode ? 'bg-brand-500/10 text-brand-400' : 'bg-brand-50 text-brand-600'}`}>
                        <Users size={20} />
                      </div>
                    </div>
                    <div className="mt-4 flex items-center gap-1.5 text-xs text-slate-400">
                      <span className="font-semibold text-emerald-500">Sincronizados</span>
                      <span>desde CLIGESCO.DBF</span>
                    </div>
                  </div>
                </div>

                <div className={`rounded-2xl border p-1 shadow-sm mt-6 ${darkMode ? 'glass-dark border-dark-border' : 'bg-white border-slate-200'}`}>
                  <div className="p-5 flex flex-col sm:flex-row gap-4 sm:items-center justify-between border-b dark:border-dark-border/50">
                    <h2 className="text-lg font-bold">Empresas Registradas</h2>
                    <div className="relative w-full sm:w-80">
                      <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                      <input
                        type="text"
                        placeholder="Buscar por nombre, código, CUIT o localidad..."
                        value={clientSearchTerm}
                        onChange={e => setClientSearchTerm(e.target.value)}
                        className={`w-full pl-9 pr-4 py-2 rounded-xl text-sm border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-dark-bg border-dark-border text-white' : 'bg-slate-50 border-slate-200'}`}
                      />
                    </div>
                  </div>
                  <div className="p-4">
                    <div className="hidden md:grid grid-cols-12 gap-4 pb-3 border-b border-slate-100 dark:border-dark-border/50 text-xs font-bold text-slate-400 tracking-wider uppercase">
                      <div className="col-span-1 pl-2">CÓD.</div>
                      <div className="col-span-3">Razón Social / Fantasía</div>
                      <div className="col-span-2">CUIT / Email</div>
                      <div className="col-span-2">Módulos / Apollo</div>
                      <div className="col-span-2 text-right pr-4">Saldo ERP</div>
                      <div className="col-span-2 text-right pr-4">Estado / Acciones</div>
                    </div>
                    <div className="space-y-2 mt-2">
                      {clients
                        .filter(c => {
                          const term = clientSearchTerm.toLowerCase();
                          return (
                            (c.razon_social || '').toLowerCase().includes(term) ||
                            (c.nombre_fantasia || '').toLowerCase().includes(term) ||
                            (c.codigo || '').toLowerCase().includes(term) ||
                            (c.cclifac || '').toLowerCase().includes(term) ||
                            (c.identificador_fiscal || '').toLowerCase().includes(term) ||
                            (c.localidad || '').toLowerCase().includes(term)
                          );
                        })
                        .map((c: any) => {
                          const isExpired = c.fecha_vencimiento && new Date(c.fecha_vencimiento) < new Date();
                          const formattedSaldo = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(c.saldo || 0);
                          const isSaldoPendiente = (c.saldo || 0) > 0;
                          
                          return (
                            <div key={c.id} className={`
                              flex flex-col md:grid md:grid-cols-12 gap-3 md:gap-4 p-4 md:p-3.5 rounded-2xl items-start md:items-center
                              ${darkMode ? 'hover:bg-slate-800/60 bg-white/[0.01] border border-white/5 md:border-transparent md:bg-transparent' : 'hover:bg-slate-50 bg-slate-50/50 border border-slate-100 md:border-transparent md:bg-transparent'}
                              w-full
                            `}>
                              <div className="flex justify-between items-center w-full md:w-auto md:col-span-1">
                                <div className="flex flex-col items-start gap-0.5">
                                  <span className="text-[10px] font-mono font-bold bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-400 px-1.5 py-0.5 rounded" title="Código de Cliente ERP">
                                    {c.codigo || `-`}
                                  </span>
                                  {c.cclifac && (
                                    <span className="text-[9px] font-mono font-black text-brand-500 bg-brand-500/10 px-1.5 py-0.2 rounded" title="Código de Relación Facturación">
                                      {c.cclifac}
                                    </span>
                                  )}
                                </div>
                                <span className="md:hidden text-[9px] font-bold px-2 py-0.5 rounded bg-brand-500/10 text-brand-500">CLIENTE</span>
                              </div>
                              <div className="md:col-span-3 truncate w-full">
                                <div className="text-sm font-bold text-slate-800 dark:text-white leading-tight truncate" title={c.razon_social}>
                                  {c.razon_social}
                                </div>
                                <div className="flex items-center gap-2 mt-0.5">
                                  {c.nombre_fantasia && (
                                    <span className="text-[10px] text-slate-400 font-medium truncate max-w-[150px]">
                                      {c.nombre_fantasia}
                                    </span>
                                  )}
                                  {c.localidad && (
                                    <span className="text-[9px] bg-brand-500/10 text-brand-500 font-bold px-1.5 py-0.2 rounded uppercase">
                                      {c.localidad}
                                    </span>
                                  )}
                                </div>
                              </div>
                              <div className="flex flex-col w-full md:block md:col-span-2">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">CUIT / Contacto:</span>
                                <div className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 truncate font-mono">
                                  {c.identificador_fiscal || 'SIN CUIT'}
                                </div>
                                <div className="text-[10px] text-slate-400 truncate mt-0.5">
                                  {c.email || 'sin-email@dominio.com'}
                                </div>
                              </div>
                              <div className="flex flex-col md:block md:col-span-2 gap-1.5 w-full">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase">Módulos:</span>
                                <div className="flex flex-wrap gap-1">
                                  {c.modulos?.split(',').map((m: string) => (
                                    <span key={m} className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-white/5 text-slate-500 border dark:border-white/5 uppercase">{m.trim()}</span>
                                  ))}
                                </div>
                                {c.version_apollo && (
                                  <div className="text-[9px] text-brand-400 font-bold mt-1">
                                    V. APOLLO: {c.version_apollo}
                                  </div>
                                )}
                              </div>
                              <div className="flex justify-between items-center w-full md:block md:col-span-2 md:text-right pr-4 mt-1 md:mt-0">
                                <span className="md:hidden text-[10px] font-bold text-slate-400 uppercase font-mono">Saldo:</span>
                                <div className="flex items-center gap-1.5 md:justify-end">
                                  <div className={`text-sm font-black font-mono leading-tight ${isSaldoPendiente ? 'text-rose-500 dark:text-rose-400' : 'text-emerald-500 dark:text-emerald-400'}`}>
                                    {formattedSaldo}
                                  </div>
                                  <button
                                    onClick={async (e) => {
                                      e.stopPropagation();
                                      if (!c.cclifac) {
                                        alert("Este cliente no posee código de facturación (CCLIFAC) del ERP.");
                                        return;
                                      }
                                      try {
                                        const res = await getClientBalance(c.id);
                                        setClients(prev => prev.map(cl => cl.id === c.id ? { ...cl, saldo: res.saldo_real_erp } : cl));
                                        setShowNotification(`Saldo real ERP actualizado: ${new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(res.saldo_real_erp)}`);
                                        setTimeout(() => setShowNotification(null), 3500);
                                      } catch (err: any) {
                                        alert(err.message || "Error al actualizar saldo");
                                      }
                                    }}
                                    className="p-1 hover:bg-slate-100 dark:hover:bg-white/10 rounded text-indigo-400 hover:text-brand-500 transition-colors"
                                    title="Sincronizar saldo en vivo desde el ERP"
                                  >
                                    <Sparkles size={11} className="text-brand-500 animate-pulse" />
                                  </button>
                                </div>
                                {c.fecha_ultimo_pago && (
                                  <div className="text-[9px] text-slate-400 mt-0.5">
                                    Últ. Pago: {new Date(c.fecha_ultimo_pago).toLocaleDateString()}
                                  </div>
                                )}
                              </div>
                              <div className="flex justify-between items-center w-full md:col-span-2 md:justify-end gap-2 border-t md:border-t-0 border-slate-100 dark:border-white/5 pt-2 md:pt-0 mt-1 md:mt-0">
                                <button
                                  onClick={async () => { await toggleClientStatus(c.id); loadData(); }}
                                  className={`px-3 py-1.5 rounded-xl text-[10px] font-bold uppercase transition-all ${c.activo ? 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20' : 'bg-red-500/10 text-red-500 hover:bg-red-500/20'}`}
                                >
                                  {c.activo ? 'Activo' : 'Suspendido'}
                                </button>
                                {c.cclifac && (
                                  <button
                                    onClick={() => handleOpenExtracto(c)}
                                    className="flex items-center gap-1 p-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/20 rounded-xl transition-all"
                                    title="Ver Extracto de Cuenta Corriente del ERP"
                                  >
                                    <FileText size={14} />
                                    <span className="md:hidden text-xs font-bold">Extracto</span>
                                  </button>
                                )}
                                <button onClick={() => openClientModal(c)} className="flex items-center gap-1.5 p-2 bg-slate-100 hover:bg-brand-500/10 text-slate-500 hover:text-brand-500 rounded-xl transition-all border border-slate-200 dark:bg-white/5 dark:border-white/10">
                                  <Settings size={14} />
                                  <span className="md:hidden text-xs font-bold">Ajustar</span>
                                </button>
                              </div>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'personnel' && (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-6 duration-300">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Plantel de Personal
                      <span className="relative flex h-3 w-3">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
                      </span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-400 mt-1">Control de actividades, asistencia en vivo y ABM de personal.</p>
                  </div>
                  
                  {userProfile?.rol === 'admin' && (
                    <button
                      onClick={() => {
                        setSelectedUserForEdit(null); // Nuevo
                        setUserAbmForm({
                          nombre: '',
                          email: '',
                          full_name: '',
                          password: '',
                          rol: 'soporte',
                          celular: '',
                          departamento: 'Atención al Cliente',
                          profile_picture: '',
                          activo: true
                        });
                        setShowUserAbmModal(true);
                      }}
                      className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl font-bold shadow-lg shadow-brand-500/20 transition-all hover:-translate-y-1 text-xs sm:text-sm flex items-center justify-center gap-2"
                    >
                      <UserPlus size={18} />
                      + Registrar Personal
                    </button>
                  )}
                </div>

                {/* Tarjetas de Resumen del Plantel */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
                  {/* Total de Personal */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-slate-900/30' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-slate-400 uppercase tracking-widest">Total Plantel</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black">{users.length}</span>
                      <span className="text-xs font-bold text-slate-400">Colaboradores</span>
                    </div>
                  </div>
                  
                  {/* Conectados en Vivo */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-emerald-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-emerald-500 uppercase tracking-widest">En Línea</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-emerald-500">{users.filter(u => u.is_online).length}</span>
                      <span className="text-xs font-bold text-emerald-400">Activos en Vivo</span>
                    </div>
                  </div>

                  {/* Desarrollo */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-indigo-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-indigo-400 uppercase tracking-widest">Desarrollo</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-indigo-400">{users.filter(u => u.departamento === 'Desarrollo').length}</span>
                      <span className="text-xs font-bold text-indigo-400">Ingenieros</span>
                    </div>
                  </div>

                  {/* Atención al Cliente */}
                  <div className={`p-5 rounded-2xl border transition-all ${darkMode ? 'glass-dark border-dark-border bg-amber-500/5' : 'bg-white border-slate-200 shadow-sm'}`}>
                    <p className="text-xs font-bold text-amber-500 uppercase tracking-widest">Atención al Cliente</p>
                    <div className="flex items-baseline gap-2 mt-2">
                      <span className="text-3xl font-black text-amber-500">{users.filter(u => u.departamento === 'Atención al Cliente').length}</span>
                      <span className="text-xs font-bold text-amber-400">Agentes</span>
                    </div>
                  </div>
                </div>

                {/* Grid de Personal */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {users.map((u: any) => {
                    const isCurrentUser = u.id === userProfile?.id;
                    const depColor = u.departamento === 'Desarrollo' 
                      ? 'border-violet-500/30 text-violet-400 bg-violet-500/5' 
                      : u.departamento === 'Atención al Cliente'
                      ? 'border-sky-500/30 text-sky-400 bg-sky-500/5'
                      : u.departamento === 'Caja'
                      ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/5'
                      : 'border-teal-500/30 text-teal-400 bg-teal-500/5'; // Finanzas

                    return (
                      <div 
                        key={u.id} 
                        className={`p-6 rounded-3xl border flex flex-col justify-between transition-all hover:-translate-y-1 relative overflow-hidden ${
                          darkMode 
                            ? 'glass-dark border-dark-border bg-slate-900/40 hover:bg-slate-900/60' 
                            : 'bg-white border-slate-200 hover:shadow-lg hover:border-slate-300'
                        }`}
                      >
                        {/* Brillo ambiental si está online */}
                        {u.is_online && (
                          <div className="absolute top-0 right-0 w-32 h-32 bg-emerald-500/5 rounded-full blur-2xl pointer-events-none" />
                        )}

                        <div className="space-y-4">
                          {/* Cabecera de la Tarjeta */}
                          <div className="flex items-start gap-4 justify-between">
                            <div className="flex items-center gap-3">
                              {u.profile_picture ? (
                                <img src={u.profile_picture} alt={u.full_name} className="w-12 h-12 rounded-full border-2 border-brand-500/30 object-cover shadow-md" />
                              ) : (
                                <div className="w-12 h-12 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-sm shadow-md border-2 border-brand-500/30">
                                  {(u.full_name || u.nombre || 'AG').substring(0, 2).toUpperCase()}
                                </div>
                              )}
                              <div>
                                <h3 className="font-bold text-base text-slate-800 dark:text-white flex items-center gap-1.5">
                                  {u.full_name || u.nombre}
                                  {isCurrentUser && <span className="text-[9px] font-black bg-brand-500 text-white px-1.5 py-0.5 rounded-md uppercase">Tú</span>}
                                </h3>
                                <p className="text-xs text-slate-400">{u.email}</p>
                              </div>
                            </div>

                            {/* Badge de estado Online/Offline */}
                            {u.is_online ? (
                              <span className="flex items-center gap-1 bg-emerald-500/10 text-emerald-500 text-[10px] font-black px-2.5 py-1 rounded-full uppercase tracking-wider border border-emerald-500/20">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                Online
                              </span>
                            ) : (
                              <span className="text-[10px] font-black text-slate-400 px-2.5 py-1 rounded-full uppercase tracking-wider bg-slate-500/10 border border-transparent">
                                Offline
                              </span>
                            )}
                          </div>

                          {/* Sector / Departamento */}
                          <div className="flex flex-wrap gap-2 pt-1">
                            <span className={`text-[10px] font-black px-3 py-1 rounded-full border uppercase tracking-wide ${depColor}`}>
                              {u.departamento || 'Soporte'}
                            </span>
                            <span className="text-[10px] font-black px-3 py-1 rounded-full border border-slate-700 bg-slate-800/20 text-slate-400 uppercase tracking-wide">
                              {u.rol === 'admin' ? '🔑 Administrador' : '🛠️ Operador'}
                            </span>
                            {!u.activo && (
                              <span className="text-[10px] font-black px-3 py-1 rounded-full bg-red-500/10 text-red-500 border border-red-500/20 uppercase tracking-wide animate-pulse">
                                🚫 Suspendido
                              </span>
                            )}
                          </div>

                          {/* Estado de Actividad en Tiempo Real (Bloque de Control) */}
                          <div className={`p-4 rounded-2xl border ${darkMode ? 'bg-black/30 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                            <div className="space-y-3 text-xs">
                              {/* Página actual */}
                              <div className="flex items-center justify-between">
                                <span className="text-slate-400 font-semibold">📍 Pantalla actual:</span>
                                <span className="font-extrabold text-slate-700 dark:text-slate-300">
                                  {u.is_online ? (u.current_page || 'Dashboard') : 'Ninguna'}
                                </span>
                              </div>
                              {/* Tarea actual */}
                              <div className="flex items-start justify-between gap-4">
                                <span className="text-slate-400 font-semibold shrink-0">⚡ Actividad actual:</span>
                                <span className="font-extrabold text-brand-500 text-right truncate max-w-[150px]">
                                  {u.is_online ? (u.current_task || 'Inactivo') : 'Desconectado'}
                                </span>
                              </div>
                              {/* Última actividad */}
                              <div className="flex items-center justify-between">
                                <span className="text-slate-400 font-semibold">🕒 Actividad hace:</span>
                                <span className="font-bold text-slate-500">
                                  {u.last_activity ? `${Math.max(0, Math.floor((new Date().getTime() - new Date(u.last_activity).getTime()) / 60000))} minutos` : 'N/D'}
                                </span>
                              </div>
                            </div>
                          </div>

                          {/* Datos de contacto */}
                          <div className="flex items-center gap-3 pt-2 text-xs">
                            {u.celular ? (
                              <a 
                                href={`https://wa.me/${u.celular.replace(/\D/g, '')}`} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                className={`flex items-center gap-1.5 px-3 py-2 rounded-xl border transition-all ${
                                  darkMode 
                                    ? 'bg-slate-800/40 border-white/5 text-slate-300 hover:bg-slate-800' 
                                    : 'bg-slate-100 border-slate-200 text-slate-600 hover:bg-slate-200'
                                }`}
                              >
                                <Phone size={14} className="text-emerald-500" />
                                {u.celular}
                              </a>
                            ) : (
                              <span className="text-slate-500 italic text-xs">Celular no registrado</span>
                            )}
                          </div>
                        </div>

                        {/* Botones de acción (Admin Only) */}
                        {userProfile?.rol === 'admin' && (
                          <div className="flex items-center gap-2 border-t border-slate-200 dark:border-white/5 pt-4 mt-4">
                            <button
                              onClick={() => {
                                setSelectedUserForEdit(u);
                                setUserAbmForm({
                                  nombre: u.nombre || '',
                                  email: u.email || '',
                                  full_name: u.full_name || '',
                                  password: '', // En blanco para no cambiar
                                  rol: u.rol || 'soporte',
                                  celular: u.celular || '',
                                  departamento: u.departamento || 'Atención al Cliente',
                                  profile_picture: u.profile_picture || '',
                                  activo: u.activo
                                });
                                setShowUserAbmModal(true);
                              }}
                              className="flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-xs font-bold bg-brand-500/10 text-brand-500 hover:bg-brand-500/20 border border-brand-500/20 transition-all"
                            >
                              <Edit2 size={13} />
                              Modificar
                            </button>
                            {u.id !== userProfile?.id && (
                              <button
                                onClick={async () => {
                                  if (confirm(`¿Estás seguro de que deseas ${u.activo ? 'desactivar' : 'activar'} a ${u.full_name || u.nombre}?`)) {
                                    try {
                                      await toggleUserStatus(u.id);
                                      loadData();
                                      setShowNotification(`Estado de ${u.nombre} actualizado.`);
                                      setTimeout(() => setShowNotification(null), 3000);
                                    } catch (err: any) {
                                      alert(err.message || 'Error al cambiar estado.');
                                    }
                                  }
                                }}
                                className={`flex-1 py-2 rounded-xl text-xs font-bold uppercase border transition-all ${
                                  u.activo 
                                    ? 'bg-rose-500/10 text-rose-500 hover:bg-rose-500/20 border-rose-500/20' 
                                    : 'bg-emerald-500/10 text-emerald-500 hover:bg-emerald-500/20 border-emerald-500/20'
                                }`}
                              >
                                {u.activo ? 'Desactivar' : 'Activar'}
                              </button>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="max-w-2xl mx-auto py-12 animate-in slide-in-from-bottom-8">
                <div className={`p-10 rounded-3xl border shadow-2xl transition-all ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                  <div className="flex flex-col items-center text-center gap-6">
                    <img src="https://i.pravatar.cc/150?img=11" alt="Avatar" className="w-32 h-32 rounded-full border-4 border-brand-500/30 shadow-2xl" />
                    <div>
                      <h2 className="text-3xl font-black tracking-tighter">{userProfile?.nombre || 'Agente de Soporte'}</h2>
                      <p className="text-brand-500 font-extrabold uppercase tracking-[0.2em] text-sm mt-1">{userProfile?.rol || 'Soporte'}</p>
                    </div>
                  </div>

                  <div className="mt-12 space-y-6 pt-10 border-t border-slate-200 dark:border-white/5">
                    <div className="grid grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Correo Institucional</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>{userProfile?.email || 'soporte@apollo.com'}</div>
                      </div>
                      <div className="space-y-2">
                        <label className="text-xs font-bold text-slate-400 uppercase tracking-widest px-1">Contraseña</label>
                        <div className={`p-4 rounded-2xl border font-bold text-sm flex justify-between items-center ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-100 text-slate-600'}`}>
                          ••••••••••••
                          <button className="text-brand-500 hover:text-brand-400 text-[10px] uppercase font-black">Cambiar</button>
                        </div>
                      </div>
                    </div>

                    {/* Sección PWA e Installability */}
                    <div className="pt-6 border-t border-slate-200 dark:border-white/5 space-y-4">
                      <h4 className="text-xs font-black uppercase tracking-wider text-slate-400">Aplicación PWA y Alertas</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-amber-500 uppercase tracking-widest block mb-1">Notificaciones Push</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Recibe avisos nativos en tu escritorio en tiempo real ante alertas críticas de los clientes.</p>
                          </div>
                          <button
                            onClick={async () => {
                              if (!('Notification' in window)) {
                                alert("Este navegador no soporta notificaciones de escritorio.");
                                return;
                              }
                              const permission = await Notification.requestPermission();
                              if (permission === 'granted') {
                                triggerPushNotification("🔔 Notificaciones Activas", "¡Felicidades! Recibirás alertas del Centinela en tiempo real en tu escritorio.");
                              }
                            }}
                            className="bg-brand-500 hover:bg-brand-600 text-white font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center"
                          >
                            {('Notification' in window && Notification.permission === 'granted') ? '✓ Habilitadas' : 'Habilitar Notificaciones'}
                          </button>
                        </div>

                        <div className={`p-4 rounded-2xl border flex flex-col justify-between gap-3 ${darkMode ? 'bg-black/20 border-white/5' : 'bg-slate-50 border-slate-100'}`}>
                          <div>
                            <span className="text-xs font-black text-emerald-500 uppercase tracking-widest block mb-1">Instalación Local</span>
                            <p className="text-[11px] leading-relaxed text-slate-400">Instala ApolloSupport como una aplicación nativa en tu escritorio o teléfono móvil.</p>
                          </div>
                          <button
                            disabled={!deferredPrompt}
                            onClick={() => {
                              if (deferredPrompt) {
                                deferredPrompt.prompt();
                                deferredPrompt.userChoice.then((choiceResult: any) => {
                                  if (choiceResult.outcome === 'accepted') {
                                    console.log('Usuario aceptó la instalación PWA');
                                  }
                                  setDeferredPrompt(null);
                                });
                              } else {
                                alert("La app ya está instalada o tu navegador no ofrece la instalación en este momento.");
                              }
                            }}
                            className={`font-bold text-xs py-2.5 px-4 rounded-xl transition-all w-full text-center ${deferredPrompt ? 'bg-emerald-600 hover:bg-emerald-700 text-white cursor-pointer shadow-lg' : 'bg-slate-800 text-slate-500 cursor-not-allowed border border-white/5'}`}
                          >
                            {deferredPrompt ? 'Instalar App (PWA)' : '✓ Ya Instalado'}
                          </button>
                        </div>
                      </div>
                    </div>

                    <button onClick={handleLogout} className="w-full flex items-center justify-center gap-3 py-4 bg-red-600/10 hover:bg-red-600/20 text-red-500 rounded-2xl font-bold transition-all border border-red-500/20 mt-6">
                      <LogOut size={20} /> Cerrar Sesión
                    </button>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'licenses' && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4">
                <div className="flex justify-between items-center">
                  <div>
                    <h2 className="text-2xl font-black text-white">Central de Licenciamiento</h2>
                    <p className="text-slate-400 text-sm">Administra llaves de activación y límites comerciales.</p>
                  </div>
                  <button onClick={() => setShowLicenseModal(true)} className="bg-brand-500 hover:bg-brand-600 text-white px-5 py-2.5 rounded-xl text-sm font-bold flex items-center gap-2 shadow-lg transition-all">
                    <Plus size={18} /> Generar Nueva Licencia
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {licenses.filter(lic => {
                    if (!globalSearchTerm) return true;
                    const term = globalSearchTerm.toLowerCase();
                    const client = clients.find(c => c.id === lic.client_id);
                    
                    const matchKey = lic.license_key?.toLowerCase().includes(term);
                    const matchId = String(lic.client_id).includes(term);
                    const matchClientSocial = client?.razon_social?.toLowerCase().includes(term);
                    const matchClientFantasia = client?.nombre_fantasia?.toLowerCase().includes(term);
                    const matchClientCodigo = client?.codigo?.toLowerCase().includes(term);
                    const matchClientFac = client?.cclifac?.toLowerCase().includes(term);
                    
                    return matchKey || matchId || matchClientSocial || matchClientFantasia || matchClientCodigo || matchClientFac;
                  }).map((lic) => {
                    const client = clients.find(c => c.id === lic.client_id);
                    return (
                      <div key={lic.id} className="bg-slate-800/50 border border-white/5 rounded-2xl p-5 hover:border-brand-500/30 transition-all group">
                        <div className="flex justify-between items-start mb-4">
                          <span className={`px-2 py-1 rounded-md text-[10px] font-black uppercase tracking-widest ${lic.is_active ? 'bg-emerald-500/10 text-emerald-500' : 'bg-red-500/10 text-red-500'}`}>
                            {lic.is_active ? 'Activa' : 'Suspendida'}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">ID #{lic.id}</span>
                        </div>
                        <h3 className="text-lg font-mono font-bold text-white mb-1 select-all">{lic.license_key}</h3>
                        <div className="flex flex-wrap items-center gap-1.5 mb-4">
                          <span className="text-xs text-brand-400 font-bold truncate max-w-[180px]" title={client?.razon_social}>
                            {client ? client.razon_social : `Cliente ID: ${lic.client_id}`}
                          </span>
                          {client?.codigo && (
                            <span className="text-[9px] bg-slate-700/60 text-slate-300 font-mono px-1.5 py-0.5 rounded uppercase tracking-wider">
                              Cód: {client.codigo}
                            </span>
                          )}
                          {client?.cclifac && (
                            <span className="text-[9px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/10 font-mono px-1.5 py-0.5 rounded">
                              Fac: {client.cclifac}
                            </span>
                          )}
                        </div>
                        <div className="space-y-3">
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-500">Capacidad:</span>
                            <span className="text-white font-bold">{lic.max_devices} PCs</span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-slate-500">Expiración:</span>
                            <span className="text-brand-400 font-bold">{lic.expiry_date ? new Date(lic.expiry_date).toLocaleDateString() : 'Ilimitada'}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {activeTab === 'logs' && (
              <div className="space-y-8 animate-in slide-in-from-bottom-8">
                {/* Cabecera premium */}
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                  <div>
                    <h1 className="text-4xl font-extrabold tracking-tight flex items-center gap-3">
                      Bitácora de Telemetría <span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-violet-500"></span></span>
                    </h1>
                    <p className="text-slate-400 mt-2">Diagnóstico de eventos del agente Centinela y el servidor en tiempo real.</p>
                  </div>
                  
                  {/* Botones de acción */}
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => fetchTelemetryLogs()}
                      className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs px-4 py-3 rounded-2xl border border-white/5 transition-all shadow-md cursor-pointer"
                      title="Refrescar logs ahora"
                    >
                      🔄 Refrescar
                    </button>
                    <button
                      onClick={() => handleClearTelemetryLogs(null)}
                      className="flex items-center gap-2 bg-red-500/10 hover:bg-red-500 text-red-500 hover:text-white font-bold text-xs px-4 py-3 rounded-2xl border border-red-500/20 transition-all cursor-pointer"
                    >
                      🗑️ Limpiar Bitácora
                    </button>
                  </div>
                </div>

                {/* Filtros */}
                <div className={`p-6 rounded-[2rem] border shadow-2xl ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'} space-y-4`}>
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                    {/* Búsqueda */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Buscar Mensaje</label>
                      <div className="relative">
                        <Search size={14} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="text"
                          value={logsSearchTerm}
                          onChange={(e) => setLogsSearchTerm(e.target.value)}
                          className={`w-full pl-10 pr-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                            darkMode ? 'bg-black/30 border-white/10 text-white focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                          }`}
                          placeholder="Buscar término..."
                        />
                      </div>
                    </div>

                    {/* Dispositivo */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Filtrar por PC</label>
                      <select
                        value={logsFilterDevice}
                        onChange={(e) => setLogsFilterDevice(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">🖥️ Todos los Equipos</option>
                        {clients.flatMap(c => c.devices || []).map((dev: any) => (
                          <option key={dev.id} value={dev.id}>🖥️ {dev.device_name} (ID: {dev.id})</option>
                        ))}
                      </select>
                    </div>

                    {/* Nivel */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Nivel de Gravedad</label>
                      <select
                        value={logsFilterLevel}
                        onChange={(e) => setLogsFilterLevel(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">⚖️ Todos los niveles</option>
                        <option value="DEBUG">🔵 DEBUG</option>
                        <option value="INFO">🟢 INFO</option>
                        <option value="WARNING">🟡 WARNING</option>
                        <option value="ERROR">🔴 ERROR</option>
                      </select>
                    </div>

                    {/* Origen */}
                    <div className="flex flex-col gap-1.5">
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-widest px-1">Origen del Evento</label>
                      <select
                        value={logsFilterSource}
                        onChange={(e) => setLogsFilterSource(e.target.value)}
                        className={`w-full px-4 py-2.5 rounded-xl text-xs font-semibold outline-none border transition-all ${
                          darkMode ? 'bg-slate-900 border-white/10 text-slate-300 focus:border-brand-500' : 'bg-slate-50 border-slate-200 text-slate-700 focus:border-brand-500'
                        }`}
                      >
                        <option value="all">🔌 Todos los orígenes</option>
                        <option value="agent">🤖 Agente Centinela</option>
                        <option value="backend">☁️ Servidor Backend</option>
                      </select>
                    </div>
                  </div>

                  {/* Auto refresh status */}
                  <div className="flex items-center justify-between text-xs text-slate-500 pt-2 border-t border-slate-200 dark:border-white/5">
                    <div className="flex items-center gap-2">
                      <span className={`relative flex h-2.5 w-2.5 ${logsAutoRefresh ? 'inline-flex' : 'hidden'}`}>
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                      </span>
                      <span>
                        {logsAutoRefresh ? 'Auto-actualizando cada 3 segundos' : 'Actualización automática en pausa'}
                      </span>
                    </div>
                    <button
                      onClick={() => setLogsAutoRefresh(v => !v)}
                      className={`font-extrabold text-[10px] uppercase px-3 py-1.5 rounded-lg border transition-all ${
                        logsAutoRefresh 
                          ? 'bg-slate-800 border-white/5 text-slate-400 hover:text-white' 
                          : 'bg-brand-500/10 border-brand-500/20 text-brand-400 hover:bg-brand-500/20'
                      }`}
                    >
                      {logsAutoRefresh ? 'Pausar' : 'Activar Auto-Refresh'}
                    </button>
                  </div>
                </div>

                {/* Tabla de Logs */}
                <div className={`rounded-[2rem] border shadow-2xl overflow-hidden ${darkMode ? 'glass-dark border-brand-500/10' : 'bg-white border-slate-200'}`}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-xs">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-white/5 bg-slate-850 dark:bg-black/30 text-[10px] uppercase font-black tracking-wider text-slate-400">
                          <th className="py-4 px-6 w-24">Hora</th>
                          <th className="py-4 px-6 w-32">Nivel</th>
                          <th className="py-4 px-6 w-32">Origen</th>
                          <th className="py-4 px-6 w-48">PC / Dispositivo</th>
                          <th className="py-4 px-6">Mensaje</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-white/5 font-medium">
                        {logsLoading && telemetryLogs.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-12 text-center text-slate-500">
                              <div className="flex flex-col items-center justify-center gap-3">
                                <div className="animate-spin rounded-full h-8 w-8 border-4 border-brand-500 border-t-transparent" />
                                <span>Cargando bitácora de logs...</span>
                              </div>
                            </td>
                          </tr>
                        ) : telemetryLogs.filter(log => {
                          if (!logsSearchTerm) return true;
                          return log.message?.toLowerCase().includes(logsSearchTerm.toLowerCase());
                        }).length === 0 ? (
                          <tr>
                            <td colSpan={5} className="py-12 text-center text-slate-500 italic">
                              No se encontraron logs con los filtros aplicados.
                            </td>
                          </tr>
                        ) : (
                          telemetryLogs
                            .filter(log => {
                              if (!logsSearchTerm) return true;
                              return log.message?.toLowerCase().includes(logsSearchTerm.toLowerCase());
                            })
                            .map((log: any) => {
                              let levelBadge = "";
                              if (log.level === 'DEBUG') levelBadge = "bg-cyan-500/10 text-cyan-400 border border-cyan-500/20";
                              else if (log.level === 'WARNING') levelBadge = "bg-amber-500/10 text-amber-400 border border-amber-500/20 animate-pulse";
                              else if (log.level === 'ERROR') levelBadge = "bg-red-500/20 text-red-400 border border-red-500/30 font-black shadow-md shadow-red-500/5";
                              else levelBadge = "bg-emerald-500/10 text-emerald-400 border border-emerald-500/10";

                              const isAgent = log.source === 'agent';
                              const sourceBadge = isAgent 
                                ? "bg-orange-500/10 text-orange-400 border border-orange-500/20" 
                                : "bg-indigo-500/10 text-indigo-400 border border-indigo-500/20";

                              return (
                                <tr key={log.id} className="hover:bg-slate-900/40 dark:hover:bg-white/[0.02] transition-colors select-text">
                                  <td className="py-4 px-6 text-slate-400 font-mono whitespace-nowrap">
                                    {new Date(log.timestamp).toLocaleString('es-AR', {day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'})}
                                  </td>
                                  <td className="py-4 px-6">
                                    <span className={`px-2 py-1 rounded-full text-[9px] uppercase font-black ${levelBadge}`}>
                                      {log.level}
                                    </span>
                                  </td>
                                  <td className="py-4 px-6">
                                    <span className={`px-2.5 py-1 rounded-full text-[9px] uppercase font-bold ${sourceBadge}`}>
                                      {isAgent ? '🤖 Agente' : '☁️ Servidor'}
                                    </span>
                                  </td>
                                  <td className="py-4 px-6 font-bold text-slate-300">
                                    {log.device_id ? (
                                      <div className="flex flex-col">
                                        <span className="text-slate-200">{log.device_name}</span>
                                        <span className="text-[9px] text-slate-500 font-mono font-normal">ID: {log.device_id}</span>
                                      </div>
                                    ) : (
                                      <span className="text-slate-500 italic">No aplica</span>
                                    )}
                                  </td>
                                  <td className="py-4 px-6 font-mono text-slate-300 break-all whitespace-pre-wrap leading-relaxed max-w-xl">
                                    {log.message}
                                  </td>
                                </tr>
                              );
                            })
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {activeSessions.length > 0 && (
          <div className="absolute inset-0 z-[60] flex items-center justify-center bg-black/90 backdrop-blur-md animate-in fade-in p-8">
            <div className="w-full h-full flex flex-col gap-6 animate-in zoom-in-95">
              <div className="flex justify-between items-center text-white">
                <h2 className="text-2xl font-bold flex items-center gap-2">
                  <Monitor className="text-emerald-500" />
                  Centro de Comando Remoto ({activeSessions.length} Activas)
                </h2>
                <button onClick={() => setActiveSessions([])} className="hover:bg-white/10 p-2 rounded-full transition-colors"><X size={32} /></button>
              </div>

              <div className={`flex-1 grid gap-6 ${activeSessions.length === 1 ? 'grid-cols-1' : 'grid-cols-2 lg:grid-cols-3'} overflow-y-auto pr-2 custom-scrollbar`}>
                {activeSessions.map((session) => {
                  const frame = sessionFrames[session.id];
                  const cmdInfo = sessionCmds[session.id] || { current: "", history: [] };
                  const isFocused = focusedSessionId === session.id;
                  return (
                    <div key={session.id} className={`bg-slate-900 rounded-3xl overflow-hidden flex flex-col relative group shadow-2xl transition-all duration-300 border-2 ${isFocused ? 'border-brand-500 shadow-brand-500/15 ring-2 ring-brand-500/20 scale-[1.01]' : 'border-white/10'}`}>
                      {/* Cabecera de Sesión en Rejilla */}
                      <div className="flex items-center justify-between px-5 py-3 bg-slate-950/40 border-b border-white/5 select-none shrink-0">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${(session.is_online || frame) ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
                          <span className="text-xs font-black text-slate-200 truncate max-w-[140px]" title={session.device_name}>
                            {session.device_name || "PC Remota"}
                          </span>
                          <span className="text-[9px] bg-slate-800/60 text-slate-400 px-1.5 py-0.5 rounded font-mono font-bold">
                            #{session.id}
                          </span>
                        </div>
                        <div className="flex items-center gap-1.5">
                          {isFocused && (
                            <span className="text-[8px] bg-brand-500/20 text-brand-400 border border-brand-500/30 px-1.5 py-0.5 rounded font-extrabold flex items-center gap-1 animate-pulse">
                              ⌨️ CONTROL
                            </span>
                          )}
                          {isCapsLockActive && isFocused && (
                            <span className="text-[8px] bg-amber-500/20 text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded font-extrabold flex items-center gap-1 animate-pulse">
                              🔠 MAYÚS
                            </span>
                          )}
                        </div>
                      </div>

                      <div className="absolute top-16 right-4 z-20 flex flex-col gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button onClick={() => {
                          const idStr = String(session.id);
                          if (!chatVisibility[idStr]) fetchChatHistory(session.id);
                          setChatVisibility(prev => ({ ...prev, [idStr]: !prev[idStr] }));
                        }} className={`p-2 rounded-xl text-white shadow-lg border border-white/10 ${chatVisibility[String(session.id)] ? 'bg-brand-600' : 'bg-brand-500/80'}`}>
                          <MessageSquare size={16} />
                        </button>
                        <button onClick={async () => {
                          try {
                            const text = await navigator.clipboard.readText();
                            syncRemoteClipboard(session.id, text);
                          } catch (err) {
                            const text = prompt("Ingrese el texto a enviar al portapapeles de la PC cliente:");
                            if (text !== null) syncRemoteClipboard(session.id, text);
                          }
                        }} className="bg-blue-500/80 p-2 rounded-xl text-white shadow-lg border border-white/10">
                          <Clipboard size={16} />
                        </button>
                        <button onClick={() => fetchRemoteFiles(session.id)} className="bg-emerald-500/80 p-2 rounded-xl text-white shadow-lg border border-white/10">
                          <FileText size={16} />
                        </button>
                      </div>

                      <div className="flex-1 bg-black flex items-center justify-center relative min-h-[300px]">
                        {frame ? (
                          <img
                            src={frame.startsWith('blob:') || frame.startsWith('data:') ? frame : `data:image;base64,${frame}`}

                            onClick={(e) => handleImageInteraction(e, session.id, 'left')}
                            onDoubleClick={(e) => handleImageInteraction(e, session.id, 'double')}
                            onContextMenu={(e) => handleImageInteraction(e, session.id, 'right')}
                            className="w-full h-full object-contain cursor-crosshair select-none"
                            alt="Remote Screen"
                          />
                        ) : (
                          <div className="animate-spin rounded-full h-10 w-10 border-4 border-brand-500 border-t-transparent" />
                        )}
                      </div>

                      <div className="p-4 bg-slate-900 border-t border-white/5 flex flex-col gap-3">
                        {/* Consola Remota */}
                        <div className="flex gap-2 items-center">
                          <span className="text-[10px] uppercase font-black text-slate-500 w-16">Consola:</span>
                          <input
                            type="text"
                            value={cmdInfo.current}
                            onChange={(e) => setSessionCmds({ ...sessionCmds, [session.id]: { ...cmdInfo, current: e.target.value } })}
                            onKeyDown={(e) => e.key === 'Enter' && handleSendCommand(session.id)}
                            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-emerald-400 font-mono outline-none"
                            placeholder="Comando de sistema..."
                          />
                          <button onClick={() => handleSendCommand(session.id)} className="bg-emerald-600 p-2 rounded-xl text-white hover:bg-emerald-700 transition-all">
                            <ArrowUpRight size={16} />
                          </button>
                        </div>
                        
                        {/* Teclado Typist Remoto */}
                        <div className="flex gap-2 items-center">
                          <span className="text-[10px] uppercase font-black text-slate-500 w-16">Teclado:</span>
                          <input
                            type="text"
                            id={`text-input-${session.id}`}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') {
                                const input = e.currentTarget;
                                if (input.value) {
                                  sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                                  input.value = '';
                                }
                              }
                            }}
                            className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs text-brand-400 font-mono outline-none"
                            placeholder="Escribe texto y presiona Enter para escribirlo allá..."
                          />
                          <button
                            onClick={() => {
                              const input = document.getElementById(`text-input-${session.id}`) as HTMLInputElement;
                              if (input && input.value) {
                                sendCentinelaControl(session.id, { type: 'write_text', text: input.value });
                                input.value = '';
                              }
                            }}
                            className="bg-brand-500 p-2 rounded-xl text-white hover:bg-brand-600 transition-all"
                          >
                            <Sparkles size={16} />
                          </button>
                        </div>

                        {/* Teclas Rápidas */}
                        <div className="flex gap-2 items-center flex-wrap pl-16">
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'enter' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⏎ Enter
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'escape' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⎋ Esc
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'tab' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⇥ Tab
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'backspace' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ⌫ Borrar
                          </button>
                          <button onClick={() => sendCentinelaControl(session.id, { type: 'key_press', key: 'space' })} className="bg-slate-800 text-[10px] font-bold text-white px-3 py-1.5 rounded-lg border border-white/5 hover:bg-slate-700 transition-all">
                            ␣ Espacio
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {isClientModalOpen && (
          <div className="fixed inset-0 z-[70] flex items-center justify-center bg-slate-950/80 backdrop-blur-sm animate-in fade-in p-4 overflow-y-auto">
            <div className={`w-full ${clientActiveTab === 'erp_licensing' ? 'max-w-5xl font-sans' : 'max-w-2xl'} max-h-[90vh] flex flex-col p-6 rounded-3xl shadow-2xl border animate-in zoom-in-95 transition-all duration-300 ${darkMode ? 'bg-slate-900 border-white/10 text-white shadow-[0_0_50px_rgba(245,158,11,0.08)]' : 'bg-white border-slate-200 text-slate-800'}`}>
              <div className="flex justify-between items-center mb-6 border-b pb-4 dark:border-white/5 shrink-0">
                <div>
                  <h3 className="text-xl font-extrabold tracking-tight">
                    {editingClient ? 'Editar Información de Cliente' : 'Registrar Nuevo Cliente'}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">Configure todos los campos operativos y datos sincronizados del ERP.</p>
                </div>
                <button onClick={() => setIsClientModalOpen(false)} className="hover:bg-white/10 p-2 rounded-xl transition-all">
                  <X size={20} />
                </button>
              </div>

              {/* Tabs */}
              <div className="flex gap-2 border-b pb-3 mb-6 dark:border-white/5 overflow-x-auto shrink-0">
                {[
                  { id: 'basic', label: 'Básico' },
                  { id: 'erp', label: 'ERP & Cuenta' },
                  { id: 'support', label: 'Soporte & Licencia' },
                  ...(editingClient ? [{ id: 'erp_licensing', label: 'Activaciones ERP (MySQL)' }] : [])
                ].map(tab => (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setClientActiveTab(tab.id)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold transition-all whitespace-nowrap ${clientActiveTab === tab.id ? 'bg-brand-500 text-white shadow-md' : 'text-slate-400 hover:bg-white/5'}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              <form onSubmit={handleCreateOrUpdateClient} className="flex-1 flex flex-col min-h-0 space-y-0">
                <div className="flex-1 overflow-y-auto pr-1.5 space-y-6 min-h-0 custom-scrollbar mb-4 pb-2">
                {/* Tab: Básico */}
                {clientActiveTab === 'basic' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Código ERP / Cliente</label>
                      <input
                        placeholder="Ej. 0677"
                        disabled={!!editingClient}
                        value={clientForm.codigo}
                        onChange={e => setClientForm({ ...clientForm, codigo: e.target.value })}
                        className={`w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 ${editingClient ? 'opacity-60 cursor-not-allowed dark:border-white/5' : 'dark:border-white/10'}`}
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Relación Facturación (CCLIFAC)</label>
                      <input
                        placeholder="Ej. 0100154"
                        value={clientForm.cclifac}
                        onChange={e => setClientForm({ ...clientForm, cclifac: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">CUIT o DNI (Identificador Fiscal)</label>
                      <input
                        placeholder="Ej. 201506230"
                        value={clientForm.identificador_fiscal}
                        onChange={e => setClientForm({ ...clientForm, identificador_fiscal: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Razón Social</label>
                      <input
                        required
                        placeholder="Razón Social Legal de la Empresa"
                        value={clientForm.razon_social}
                        onChange={e => setClientForm({ ...clientForm, razon_social: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Fantasía</label>
                      <input
                        placeholder="Nombre comercial o fantasía"
                        value={clientForm.nombre_fantasia}
                        onChange={e => setClientForm({ ...clientForm, nombre_fantasia: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Localidad / Ciudad</label>
                      <input
                        placeholder="Ej. GUALEGUAYCHU"
                        value={clientForm.localidad}
                        onChange={e => setClientForm({ ...clientForm, localidad: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Teléfono de Contacto</label>
                      <input
                        placeholder="Teléfono"
                        value={clientForm.telefono}
                        onChange={e => setClientForm({ ...clientForm, telefono: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Email Principal</label>
                      <input
                        type="email"
                        placeholder="ejemplo@empresa.com"
                        value={clientForm.email}
                        onChange={e => setClientForm({ ...clientForm, email: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: ERP & Cuenta */}
                {clientActiveTab === 'erp' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Saldo Cuenta Corriente</label>
                      <div className={`p-4 rounded-2xl border flex items-center justify-between ${darkMode ? 'bg-black/20' : 'bg-slate-50'}`}>
                        <span className="text-xs text-slate-400 font-bold">Estado de Cuenta</span>
                        <span className={`text-xl font-black font-mono ${(clientForm.saldo || 0) > 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                          {new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(clientForm.saldo || 0)}
                        </span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Código Clasificación ERP</label>
                      <input
                        placeholder="Código Clas."
                        value={clientForm.clasificacion_codigo}
                        onChange={e => setClientForm({ ...clientForm, clasificacion_codigo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Clasificación</label>
                      <input
                        placeholder="Ej. DEBITO AUTOMATICO"
                        value={clientForm.clasificacion_nombre}
                        onChange={e => setClientForm({ ...clientForm, clasificacion_nombre: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Código Vendedor</label>
                      <input
                        placeholder="Código Vend."
                        value={clientForm.vendedor_codigo}
                        onChange={e => setClientForm({ ...clientForm, vendedor_codigo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Vendedor Asignado</label>
                      <input
                        placeholder="Nombre Vendedor"
                        value={clientForm.vendedor_nombre}
                        onChange={e => setClientForm({ ...clientForm, vendedor_nombre: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: Soporte & Licencia */}
                {clientActiveTab === 'support' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-in fade-in duration-200">
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Versión Apollo ERP</label>
                      <input
                        placeholder="Ej. E o 3"
                        value={clientForm.version_apollo}
                        onChange={e => setClientForm({ ...clientForm, version_apollo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div>
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Fecha Vencimiento Soporte</label>
                      <input
                        type="date"
                        value={clientForm.fecha_vencimiento}
                        onChange={e => setClientForm({ ...clientForm, fecha_vencimiento: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 text-slate-400"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Módulos Habilitados (Separados por coma)</label>
                      <input
                        placeholder="Base, Facturación, etc."
                        value={clientForm.modulos}
                        onChange={e => setClientForm({ ...clientForm, modulos: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">API Key de Integración Apollo</label>
                      <input
                        placeholder="Generada automáticamente o ingresada"
                        value={clientForm.apikey_apollo}
                        onChange={e => setClientForm({ ...clientForm, apikey_apollo: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                    <div className="md:col-span-2">
                      <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">PIN Acceso Soporte Remoto (Centinela)</label>
                      <input
                        type="text"
                        placeholder="PIN de acceso remoto"
                        value={clientForm.remote_password}
                        onChange={e => setClientForm({ ...clientForm, remote_password: e.target.value })}
                        className="w-full p-3 rounded-xl border bg-transparent text-sm outline-none focus:ring-2 focus:ring-brand-500 dark:border-white/10 font-mono"
                      />
                    </div>
                  </div>
                )}

                {/* Tab: Activaciones ERP (MySQL) */}
                {clientActiveTab === 'erp_licensing' && (
                  <div className="space-y-6 animate-in fade-in duration-200 text-slate-300">
                    <div className="flex flex-wrap gap-4 items-center justify-between bg-slate-900/50 p-4 rounded-2xl border border-white/5">
                      <div>
                        <h4 className="text-sm font-extrabold text-white">Licenciamiento de Cliente en Servidor Activo</h4>
                        <p className="text-xs text-slate-400 mt-0.5">Gestión directa de seriales y nodos en mysql1.apollogescom.com.ar</p>
                      </div>
                      <div className="flex gap-2 font-sans">
                        <button
                          type="button"
                          onClick={() => {
                            const randomHex = Math.random().toString(16).substring(2, 10).toUpperCase();
                            const serialSugg = `${clientForm.codigo}-VS32-${randomHex}-bf`;
                            const oneYearLater = new Date();
                            oneYearLater.setFullYear(oneYearLater.getFullYear() + 1);
                            const dateSugg = oneYearLater.toISOString().split('T')[0];

                            setNewSerialForm({
                              l_number: serialSugg,
                              l_date: dateSugg,
                              l_peri2016: 30,
                              l_raso: clientForm.razon_social || '',
                              l_nomfa: clientForm.nombre_fantasia || '',
                              l_cuit: clientForm.identificador_fiscal || '',
                              l_tele: clientForm.telefono || '',
                              l_locali: clientForm.localidad || ''
                            });
                            setShowNewSerialForm(true);
                          }}
                          className="bg-brand-500 hover:bg-brand-600 text-white px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 shadow-md animate-pulse hover:animate-none"
                        >
                          <Plus size={14} /> Registrar Nuevo Serial
                        </button>
                        <button
                          type="button"
                          onClick={() => loadErpLicenses(clientForm.codigo)}
                          className="bg-slate-800 hover:bg-slate-700 text-slate-300 px-3.5 py-2 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5 border border-white/5"
                        >
                          Recargar
                        </button>
                      </div>
                    </div>

                    {/* Formulario de Nuevo Serial */}
                    {showNewSerialForm && (
                      <div className="p-5 bg-slate-900/80 rounded-2xl border border-brand-500/30 space-y-4 animate-in slide-in-from-top-4 shadow-lg">
                        <div className="flex justify-between items-center border-b border-white/5 pb-2">
                          <h5 className="text-xs font-black text-brand-400 uppercase tracking-widest">Registrar Nuevo Serial Comercial</h5>
                          <button
                            type="button"
                            onClick={() => setShowNewSerialForm(false)}
                            className="text-slate-400 hover:text-white"
                          >
                            <X size={16} />
                          </button>
                        </div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-sans">
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Clave de Serial (Formato ERP)</label>
                            <input
                              required
                              value={newSerialForm.l_number}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_number: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white font-mono outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Fecha Vencimiento Inicial</label>
                            <input
                              type="date"
                              required
                              value={newSerialForm.l_date}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_date: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500 text-slate-400"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Días Renovación Automática (Auto-Ext)</label>
                            <input
                              type="number"
                              value={newSerialForm.l_peri2016}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_peri2016: parseInt(e.target.value) || 30 })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Razón Social</label>
                            <input
                              value={newSerialForm.l_raso}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_raso: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">CUIT</label>
                            <input
                              value={newSerialForm.l_cuit}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_cuit: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">Localidad</label>
                            <input
                              value={newSerialForm.l_locali}
                              onChange={e => setNewSerialForm({ ...newSerialForm, l_locali: e.target.value })}
                              className="w-full p-2.5 rounded-xl border border-white/10 bg-slate-950 text-white outline-none focus:ring-1 focus:ring-brand-500"
                            />
                          </div>
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <button
                            type="button"
                            onClick={() => setShowNewSerialForm(false)}
                            className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-750 text-slate-400 text-xs transition-colors"
                          >
                            Cancelar
                          </button>
                          <button
                            type="button"
                            onClick={handleCreateNewErpSerial}
                            className="px-3.5 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs transition-colors"
                          >
                            Guardar en MySQL
                          </button>
                        </div>
                      </div>
                    )}

                    {/* Tabla de Licencias */}
                    {isErpLicensesLoading ? (
                      <div className="flex justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-2 border-brand-500 border-t-transparent" />
                      </div>
                    ) : erpLicenses.length === 0 ? (
                      <div className="text-center py-8 bg-slate-900/30 border border-dashed border-white/5 rounded-2xl">
                        <AlertCircle className="w-8 h-8 text-slate-500 mx-auto mb-2" />
                        <p className="text-slate-400 text-xs">No se encontraron licencias comerciales en MySQL para este código de cliente ({clientForm.codigo}).</p>
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                        {/* Lista de Licencias */}
                        <div className="space-y-3 lg:col-span-5 w-full min-w-0">
                          <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block">Licencias del Cliente ({erpLicenses.length})</label>
                          
                          {/* Desktop View Table */}
                          <div className="hidden xl:block overflow-x-auto rounded-2xl border border-white/5 bg-slate-950/40">
                            <table className="w-full text-left border-collapse text-xs">
                              <thead>
                                <tr className="border-b border-white/5 bg-white/5 font-extrabold text-slate-400">
                                  <th className="p-3">Número de Serial</th>
                                  <th className="p-3">Vencimiento</th>
                                  <th className="p-3 text-center">Auto-Ext</th>
                                  <th className="p-3">Estado</th>
                                  <th className="p-3 text-right">Acciones</th>
                                </tr>
                              </thead>
                              <tbody>
                                {erpLicenses.map(lic => {
                                  const isSelected = selectedErpSerial === lic.l_number;
                                  return (
                                    <tr
                                      key={lic.l_number}
                                      onClick={() => {
                                        setSelectedErpSerial(lic.l_number);
                                        loadErpTerminals(lic.l_number);
                                      }}
                                      className={`border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors ${isSelected ? 'bg-brand-500/10 border-l-4 border-l-brand-500' : ''}`}
                                    >
                                      <td className="p-3 font-mono font-bold text-white whitespace-nowrap text-[11px]" title={lic.l_number}>{lic.l_number}</td>
                                      <td className="p-3 whitespace-nowrap">
                                        <div className="font-semibold text-slate-200 text-[11px]">{lic.l_date || "S/V"}</div>
                                        {lic.m_newdate && (
                                          <div className="text-[9px] text-brand-400">Forzado: {lic.m_newdate}</div>
                                        )}
                                      </td>
                                      <td className="p-3 text-center font-mono font-semibold text-slate-300 text-[11px]">{lic.l_peri2016} d</td>
                                      <td className="p-3">
                                        {lic.l_desact ? (
                                          <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold">DESACT</span>
                                        ) : (
                                          <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded-full text-[9px] font-bold">ACTIVA</span>
                                        )}
                                      </td>
                                      <td className="p-3 text-right whitespace-nowrap" onClick={e => e.stopPropagation()}>
                                        <div className="flex gap-1 justify-end">
                                          <button
                                            type="button"
                                            title="Configurar Cartel y Bloqueo"
                                            onClick={() => {
                                              setBannerForm({
                                                serial: lic.l_number,
                                                m_down: lic.m_down,
                                                m_newdate: lic.m_newdate || '',
                                                m_tipmsg: lic.m_tipmsg || 1,
                                                m_showmode: lic.m_showmode || '01',
                                                m_text: lic.m_text || ''
                                              });
                                              setShowBannerConfigModal(true);
                                            }}
                                            className="p-1 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg transition-colors border border-white/5"
                                          >
                                            <AlertCircle size={13} />
                                          </button>
                                          <button
                                            type="button"
                                            title="Cambiar Auto-Extensión"
                                            onClick={() => handleExtendErpLicense(lic.l_number, parseInt(lic.l_peri2016) || 30, lic.l_date)}
                                            className="p-1 bg-slate-800 hover:bg-slate-700 text-brand-400 rounded-lg transition-colors border border-white/5"
                                          >
                                            <Edit2 size={13} />
                                          </button>
                                          <button
                                            type="button"
                                            title={lic.l_desact ? "Activar Licencia" : "Desactivar Licencia"}
                                            onClick={() => handleToggleErpLicense(lic.l_number, lic.l_desact)}
                                            className={`p-1 rounded-lg transition-colors border border-white/5 ${lic.l_desact ? 'bg-emerald-950/50 hover:bg-emerald-900/50 text-emerald-400' : 'bg-red-950/50 hover:bg-red-900/50 text-red-400'}`}
                                          >
                                            <Shield size={13} />
                                          </button>
                                        </div>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>

                          {/* Mobile View / Intermediate Tablet Cards */}
                          <div className="block xl:hidden space-y-3">
                            {erpLicenses.map(lic => {
                              const isSelected = selectedErpSerial === lic.l_number;
                              return (
                                <div
                                  key={lic.l_number}
                                  onClick={() => {
                                    setSelectedErpSerial(lic.l_number);
                                    loadErpTerminals(lic.l_number);
                                  }}
                                  className={`p-3 rounded-2xl border transition-all cursor-pointer ${
                                    isSelected
                                      ? 'bg-brand-500/10 border-brand-500/40 shadow-lg shadow-brand-500/5'
                                      : 'bg-slate-950/20 border-white/5 hover:border-white/10'
                                  } space-y-2.5`}
                                >
                                  <div className="flex justify-between items-start text-left">
                                    <div>
                                      <span className="text-[11px] font-mono font-bold text-white block select-all">{lic.l_number}</span>
                                      <span className="text-[9px] text-slate-500 block mt-0.5">Vence: {lic.l_date || "S/V"}</span>
                                    </div>
                                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                                      <button
                                        type="button"
                                        title="Configurar Cartel y Bloqueo"
                                        onClick={() => {
                                          setBannerForm({
                                            serial: lic.l_number,
                                            m_down: lic.m_down,
                                            m_newdate: lic.m_newdate || '',
                                            m_tipmsg: lic.m_tipmsg || 1,
                                            m_showmode: lic.m_showmode || '01',
                                            m_text: lic.m_text || ''
                                          });
                                          setShowBannerConfigModal(true);
                                        }}
                                        className="p-1 bg-slate-800 hover:bg-slate-700 text-amber-400 rounded-lg transition-colors border border-white/5"
                                      >
                                        <AlertCircle size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        title="Cambiar Auto-Extensión"
                                        onClick={() => handleExtendErpLicense(lic.l_number, parseInt(lic.l_peri2016) || 30, lic.l_date)}
                                        className="p-1 bg-slate-800 hover:bg-slate-700 text-brand-400 rounded-lg transition-colors border border-white/5"
                                      >
                                        <Edit2 size={13} />
                                      </button>
                                      <button
                                        type="button"
                                        title={lic.l_desact ? "Activar Licencia" : "Desactivar Licencia"}
                                        onClick={() => handleToggleErpLicense(lic.l_number, lic.l_desact)}
                                        className={`p-1 rounded-lg transition-colors border border-white/5 ${lic.l_desact ? 'bg-emerald-950/50 hover:bg-emerald-900/50 text-emerald-400' : 'bg-red-950/50 hover:bg-red-900/50 text-red-400'}`}
                                      >
                                        <Shield size={13} />
                                      </button>
                                    </div>
                                  </div>

                                  <div className="flex flex-wrap gap-1.5 items-center text-[9px]">
                                    <div>
                                      {lic.l_desact ? (
                                        <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-1.5 py-0.5 rounded font-bold">DESACT</span>
                                      ) : (
                                        <span className="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-1.5 py-0.5 rounded font-bold">ACTIVA</span>
                                      )}
                                    </div>
                                    <div>
                                      <span className="bg-slate-800 text-slate-300 px-1.5 py-0.5 rounded font-semibold font-mono">Auto-Ext: {lic.l_peri2016}d</span>
                                    </div>
                                    {lic.m_down && (
                                      <span className="bg-red-500/10 text-red-400 border border-red-500/20 px-1 py-0.5 rounded font-bold">SUSPENDIDA</span>
                                    )}
                                    {lic.m_tipmsg > 1 && (
                                      <span className="bg-amber-500/15 text-amber-400 border border-amber-500/20 px-1 py-0.5 rounded font-bold flex items-center gap-0.5">
                                        CARTEL
                                      </span>
                                    )}
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        </div>

                        {/* Detalle de Nodos (Terminales) de la Licencia Seleccionada */}
                        <div className="space-y-3 lg:col-span-7 w-full min-w-0">
                          <div className="flex justify-between items-center">
                            <label className="text-[10px] font-black uppercase tracking-widest text-slate-500 block truncate text-left">
                              Terminales para <span className="font-mono text-white text-[11px] pl-1">{selectedErpSerial || 'ninguno'}</span>
                            </label>
                            {selectedErpSerial && (
                              <button
                                type="button"
                                onClick={() => loadErpTerminals(selectedErpSerial)}
                                className="text-[10px] font-bold text-slate-400 hover:text-white transition-colors flex items-center gap-1 shrink-0"
                              >
                                Actualizar Nodos
                              </button>
                            )}
                          </div>

                          {isErpTerminalsLoading ? (
                            <div className="flex justify-center py-6 bg-slate-950/20 rounded-2xl border border-white/5">
                              <div className="animate-spin rounded-full h-6 w-6 border-2 border-brand-500 border-t-transparent" />
                            </div>
                          ) : !selectedErpSerial ? (
                            <div className="text-center py-6 bg-slate-950/20 rounded-2xl border border-dashed border-white/5 text-slate-500 text-xs">
                              Seleccione un serial para visualizar sus computadoras terminales asociadas.
                            </div>
                          ) : erpTerminals.length === 0 ? (
                            <div className="text-center py-6 bg-slate-950/20 rounded-2xl border border-white/5 text-slate-400 text-xs">
                              No hay terminales registradas para este serial.
                            </div>
                          ) : (
                            <>
                              {/* Desktop View Table */}
                              <div className="hidden xl:block overflow-x-auto rounded-2xl border border-white/5 bg-slate-950/40 min-w-0 w-full">
                                <table className="w-full text-left border-collapse text-xs">
                                  <thead>
                                    <tr className="border-b border-white/5 bg-white/5 font-extrabold text-slate-400">
                                      <th className="p-3">Nombre PC (ID)</th>
                                      <th className="p-3">Usuario Windows</th>
                                      <th className="p-3">S.O.</th>
                                      <th className="p-3">Último Acceso</th>
                                      <th className="p-3">MAC / Placa</th>
                                      <th className="p-3">Ruta</th>
                                      <th className="p-3 text-right">Desact</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {erpTerminals.map(terminal => (
                                      <tr key={terminal.KeyID} className="border-b border-white/5 hover:bg-white/5 text-slate-300 font-sans">
                                        <td className="p-3 font-bold text-white whitespace-nowrap text-[11px]">{terminal.t_id || "Desconocida"}</td>
                                        <td className="p-3 whitespace-nowrap text-[11px]">{terminal.t_user || "N/A"}</td>
                                        <td className="p-3 text-slate-400 whitespace-nowrap text-[11px]">{terminal.t_OS || "Windows"}</td>
                                        <td className="p-3 whitespace-nowrap">
                                          <div className="font-semibold text-[11px]">{terminal.t_access || terminal.t_active || "N/A"}</div>
                                          <div className="text-[9px] text-slate-500">Reg: {terminal.t_active}</div>
                                        </td>
                                        <td className="p-3 font-mono text-[10px] text-slate-400 whitespace-nowrap">{terminal.t_netmac || "N/A"}</td>
                                        <td className="p-3 text-slate-400 max-w-[120px] truncate text-[11px]" title={terminal.t_path}>{terminal.t_path || "N/A"}</td>
                                        <td className="p-3 text-right whitespace-nowrap">
                                          <button
                                            type="button"
                                            onClick={() => handleDeactivateErpNode(terminal)}
                                            title="Desactivar / Bloquear esta PC"
                                            className="p-1 bg-red-950/45 hover:bg-red-900/60 text-red-400 rounded-lg transition-colors border border-red-500/10"
                                          >
                                            <Trash2 size={13} />
                                          </button>
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>

                              {/* Mobile View / Intermediate Tablet Cards */}
                              <div className="block xl:hidden space-y-3">
                                {erpTerminals.map(terminal => (
                                  <div key={terminal.KeyID} className="p-3 rounded-2xl border border-white/5 bg-slate-950/20 space-y-2 text-left">
                                    <div className="flex justify-between items-start gap-2">
                                      <div className="truncate">
                                        <span className="text-[11px] font-black text-white block truncate">{terminal.t_id || "Desconocida"}</span>
                                        <span className="text-[9px] text-slate-500 block">Usuario: {terminal.t_user || "N/A"}</span>
                                      </div>
                                      <button
                                        type="button"
                                        onClick={() => handleDeactivateErpNode(terminal)}
                                        title="Desactivar / Bloquear esta PC"
                                        className="p-1 bg-red-950/45 hover:bg-red-900/60 text-red-400 rounded-lg transition-colors border border-red-500/10 shrink-0"
                                      >
                                        <Trash2 size={13} />
                                      </button>
                                    </div>
                                    <div className="grid grid-cols-2 gap-2 text-[9px] font-sans">
                                      <div>
                                        <span className="text-slate-500 block font-bold tracking-wider">S.O.</span>
                                        <span className="text-slate-300 font-semibold">{terminal.t_OS || "Windows"}</span>
                                      </div>
                                      <div>
                                        <span className="text-slate-500 block font-bold tracking-wider">Acceso</span>
                                        <span className="text-slate-300 font-semibold">{terminal.t_access || terminal.t_active || "N/A"}</span>
                                      </div>
                                      <div className="col-span-2">
                                        <span className="text-slate-500 block font-bold tracking-wider">MAC / Placa</span>
                                        <span className="text-slate-400 font-mono font-semibold">{terminal.t_netmac || "N/A"}</span>
                                      </div>
                                      <div className="col-span-2">
                                        <span className="text-slate-500 block font-bold tracking-wider">Ruta Instalación</span>
                                        <span className="text-slate-400 font-semibold truncate block max-w-full" title={terminal.t_path}>{terminal.t_path || "N/A"}</span>
                                      </div>
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                </div>

                {clientActiveTab !== 'erp_licensing' ? (
                  <div className="flex gap-3 pt-4 border-t dark:border-white/5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsClientModalOpen(false)}
                      className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white transition-colors"
                    >
                      Cancelar
                    </button>
                    <button
                      type="submit"
                      disabled={isSubmitting}
                      className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider"
                    >
                      {isSubmitting ? 'Guardando...' : 'Guardar Cambios'}
                    </button>
                  </div>
                ) : (
                  <div className="flex gap-3 pt-4 border-t dark:border-white/5 shrink-0">
                    <button
                      type="button"
                      onClick={() => setIsClientModalOpen(false)}
                      className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 font-bold py-3 rounded-2xl shadow-lg transition-all text-sm uppercase tracking-wider text-center"
                    >
                      Cerrar Panel de Activaciones
                    </button>
                  </div>
                )}
              </form>
            </div>
          </div>
        )}

        {/* MODAL DEL TICKET (Derivador + IA Copiloto) */}
        {selectedTicket && (
          <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-slate-900/80 backdrop-blur-sm p-4 overflow-y-auto animate-in fade-in">
            <div className={`w-full max-w-4xl p-6 sm:p-8 rounded-[2rem] border shadow-2xl flex flex-col gap-6 animate-in slide-in-from-bottom-8 ${darkMode ? 'glass-dark border-brand-500/15' : 'bg-white border-slate-200'}`}>
              
              {/* Cabecera */}
              <div className="flex justify-between items-start gap-4">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-brand-500 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-brand-500/10 px-3 py-1 rounded-full">
                      Requerimiento #{selectedTicket.id}
                    </span>
                    <span className="text-slate-400 font-extrabold text-[10px] sm:text-xs uppercase tracking-widest bg-slate-500/10 px-3 py-1 rounded-full">
                      {selectedTicket.clientName}
                    </span>
                  </div>
                  <h2 className="text-xl sm:text-2xl font-black text-slate-800 dark:text-white leading-tight">
                    {selectedTicket.asunto}
                  </h2>
                </div>
                <button onClick={closeTicketModal} className="shrink-0 p-2 hover:bg-red-500/10 rounded-full transition-colors group">
                  <X size={24} className="text-slate-400 group-hover:text-red-500 transition-colors" />
                </button>
              </div>

              {/* Grid Principal: Izquierda (Detalle e Intervenciones) | Derecha (IA Copiloto y Control Remoto) */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 overflow-hidden">
                
                {/* Columna Izquierda: Historial e Intervención (7 cols) */}
                <div className="lg:col-span-7 flex flex-col gap-4">
                  <div className={`p-5 rounded-2xl border flex flex-col gap-4 max-h-[480px] overflow-y-auto custom-scrollbar ${darkMode ? 'bg-dark-bg/60 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                    
                    {/* Requerimiento Original */}
                    <div className="border-l-4 border-brand-500 pl-4 py-1 mb-2 bg-brand-500/5 p-3 rounded-r-xl">
                      <p className="text-[9px] font-black text-brand-500 uppercase tracking-widest mb-1">Descripción del Problema</p>
                      <p className="text-sm font-semibold text-slate-700 dark:text-slate-200 whitespace-pre-wrap">{selectedTicket.descripcion}</p>
                    </div>

                    {/* Intervenciones */}
                    <div className="space-y-5">
                      {interventions.length === 0 ? (
                        <p className="text-xs text-slate-500 italic text-center p-4">No hay intervenciones previas registradas.</p>
                      ) : (
                        interventions.map((inv: any) => (
                          <div key={inv.id} className="relative pl-6 animate-in fade-in slide-in-from-left-2 transition-all">
                            <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-slate-200 dark:bg-white/10" />
                            <div className="absolute left-[-4px] top-2 w-2 h-2 rounded-full bg-brand-500 ring-4 ring-brand-500/10 shadow-[0_0_8px_rgba(245,158,11,0.3)]" />

                            <div className="flex justify-between items-start mb-1.5">
                              <div>
                                <span className="text-[11px] font-extrabold text-slate-800 dark:text-slate-200">{inv.usuario?.full_name || 'Sistema'}</span>
                                {inv.area_destino && (
                                  <span className="ml-2 text-[8px] font-black px-2 py-0.5 rounded-md bg-brand-500/15 text-brand-500 uppercase tracking-widest border border-brand-500/10">
                                    Pase a {inv.area_destino.nombre}
                                  </span>
                                )}
                              </div>
                              <span className="text-[8px] font-bold text-slate-500 uppercase">{new Date(inv.fecha_creacion).toLocaleString()}</span>
                            </div>

                            <div className={`p-4 rounded-2xl text-xs sm:text-sm ${darkMode ? 'bg-white/5 border border-white/5 text-slate-300' : 'bg-white border border-slate-200 shadow-sm text-slate-700'}`}>
                              {inv.mensaje && <p className="leading-relaxed whitespace-pre-wrap">{inv.mensaje}</p>}

                              {inv.adjunto_url && (
                                <div className="mt-2 p-2.5 rounded-xl bg-black/20 border border-white/5 flex items-center gap-2.5">
                                  <FileText size={16} className="text-brand-400" />
                                  <div className="flex-1 min-w-0">
                                    <p className="text-[11px] font-extrabold truncate">{inv.adjunto_url.split('/').pop()}</p>
                                    <p className="text-[8px] text-slate-500 uppercase">{inv.adjunto_tipo}</p>
                                  </div>
                                  <a href={`${API_URL.replace('/api', '')}/uploads/${inv.adjunto_url.split('/').pop()}`} target="_blank" rel="noreferrer" className="text-brand-500 hover:text-brand-400"><ArrowUpRight size={14} /></a>
                                </div>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Formulario de Intervención */}
                  <form onSubmit={handleSendIntervention} className={`p-4 rounded-2xl border space-y-4 ${darkMode ? 'bg-dark-bg/30 border-white/5' : 'bg-slate-50 border-slate-200'}`}>
                    <textarea
                      value={newMessage}
                      onChange={e => setNewMessage(e.target.value)}
                      placeholder="Escribe un comentario técnico o pase de área..."
                      rows={2}
                      className={`w-full p-3 rounded-xl border outline-none text-xs sm:text-sm transition-all resize-none ${darkMode ? 'bg-black/20 border-white/5 text-white focus:border-brand-500/50' : 'bg-white border-slate-200 focus:border-brand-500'}`}
                    />

                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div className="flex flex-wrap gap-2">
                        <select
                          value={transferAreaId || ""}
                          onChange={e => setTransferAreaId(e.target.value ? parseInt(e.target.value) : null)}
                          className={`text-[10px] font-black px-3 py-2 rounded-xl border outline-none transition-all uppercase tracking-wider ${darkMode ? 'bg-black/20 border-white/5 text-slate-300' : 'bg-slate-50 border-slate-200'}`}
                        >
                          <option value="">Soporte (Sector Actual)</option>
                          {areas.filter(a => a.id !== selectedTicket.current_area_id).map(a => (
                            <option key={a.id} value={a.id}>Derivar a {a.nombre}</option>
                          ))}
                        </select>

                        <label className={`cursor-pointer p-2 rounded-xl border transition-all flex items-center gap-1.5 ${attachment ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white/5 border-white/10 text-slate-400 hover:text-brand-500'}`}>
                          {isUploading ? <div className="animate-spin h-3 w-3 border-2 border-brand-500 border-t-transparent" /> : <Plus size={14} />}
                          <span className="text-[9px] font-black uppercase tracking-wider">{attachment ? attachment.name.slice(0,10) + '...' : 'Subir Adjunto'}</span>
                          <input type="file" className="hidden" onChange={e => e.target.files?.[0] && handleFileUpload(e.target.files[0])} />
                        </label>
                      </div>

                      <button
                        type="submit"
                        disabled={isSubmitting || (!newMessage.trim() && !attachmentUrl && !transferAreaId)}
                        className="bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white px-5 py-2.5 rounded-xl text-xs font-black uppercase tracking-wider shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-center"
                      >
                        {isSubmitting ? 'Registrando...' : 'Grabar Intervención'}
                      </button>
                    </div>
                  </form>
                </div>

                {/* Columna Derecha: IA Copiloto y Control Remoto (5 cols) */}
                <div className="lg:col-span-5 flex flex-col gap-4">
                  
                  {/* Panel de IA Copiloto */}
                  <div className="p-5 rounded-2xl border bg-gradient-to-br from-indigo-500/5 to-transparent border-indigo-500/20 shadow-xl flex flex-col gap-4">
                    <h3 className="text-sm font-black flex items-center gap-2 text-indigo-400 uppercase tracking-widest border-b border-indigo-500/10 pb-2">
                      <Sparkles size={16} className="animate-pulse text-indigo-400" /> Copiloto Inteligente IA
                    </h3>
                    
                    {!aiSuggestion ? (
                      <div className="text-center py-4 space-y-3">
                        <p className="text-xs text-slate-400 leading-relaxed font-medium">
                          Analiza el incidente con el motor neuronal de Apollo para diagnosticar causas raíz (FoxPro, Spooler, Índices CDX), proponer acciones rápidas y redactar respuestas empáticas para clientes y pases técnicos a desarrollo.
                        </p>
                        <button
                          onClick={handleConsultarIA}
                          disabled={isAiLoading}
                          className="w-full bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-700 hover:to-blue-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all text-xs sm:text-sm uppercase tracking-wider"
                        >
                          {isAiLoading ? 'Analizando Diagnóstico Completo...' : 'Consultar Solución IA'}
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        <div className="max-h-[340px] overflow-y-auto pr-2 custom-scrollbar">
                          {renderAiAnalysisText(aiSuggestion)}
                        </div>
                        <div className="flex gap-2 border-t border-indigo-500/10 pt-3">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(aiSuggestion);
                              setShowNotification("Análisis completo copiado al portapapeles.");
                              setTimeout(() => setShowNotification(null), 3000);
                            }}
                            className="flex-1 py-2 text-[10px] font-black text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 rounded-xl uppercase tracking-wider border border-indigo-500/15 transition-all"
                          >
                            Copiar Análisis
                          </button>
                          <button
                            onClick={() => setAiSuggestion(null)}
                            className="py-2 px-3 text-[10px] font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-xl border border-white/5 uppercase transition-all"
                          >
                            Volver a Consultar
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Panel de Mantenimiento Remoto Directo */}
                  <div className="p-5 rounded-2xl border border-slate-500/10 bg-slate-500/5 shadow-xl flex flex-col gap-4">
                    <h3 className="text-sm font-black flex items-center gap-2 text-slate-300 uppercase tracking-widest border-b border-white/5 pb-2">
                      <Monitor size={16} className="text-brand-500" /> Diagnóstico y Control de PCs
                    </h3>
                    
                    <div className="space-y-3.5">
                      {(() => {
                        const client = clients.find(c => c.id === selectedTicket.client_id);
                        if (!client || !client.devices || client.devices.length === 0) {
                          return <p className="text-xs text-slate-500 italic text-center py-2">Sin terminales registradas para este cliente.</p>;
                        }
                        return client.devices.map((dev: any) => {
                          const isOnline = centinelas[dev.id];
                          return (
                            <div key={dev.id} className={`p-3.5 rounded-xl border flex flex-col gap-2.5 transition-all ${isOnline ? 'bg-brand-500/5 border-brand-500/25' : 'bg-slate-500/5 border-slate-500/10 opacity-70'}`}>
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2.5">
                                  <div className={`w-2 h-2 rounded-full ${isOnline ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse' : 'bg-slate-400'}`} />
                                  <span className="text-xs font-extrabold text-white">{dev.device_name}</span>
                                </div>
                                <span className="text-[8px] font-mono font-bold text-slate-500 uppercase">ID #{dev.id}</span>
                              </div>

                              {isOnline ? (
                                <div className="grid grid-cols-3 gap-2.5">
                                  <button
                                    onClick={async () => {
                                      const ok = await runCentinelaCommand(dev.id, "net stop spooler && net start spooler");
                                      if (ok) {
                                        setShowNotification("Comando de Spooler enviado con éxito.");
                                        setTimeout(() => setShowNotification(null), 3000);
                                      }
                                    }}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-brand-500 bg-brand-500/10 hover:bg-brand-500/25 border border-brand-500/20 rounded-xl transition-all text-center"
                                  >
                                    Spooler
                                  </button>
                                  <button
                                    onClick={async () => {
                                      const ok = await runCentinelaCommand(dev.id, "del /q /s %temp%\\*");
                                      if (ok) {
                                        setShowNotification("Comando de Limpieza de Temporales enviado.");
                                        setTimeout(() => setShowNotification(null), 3000);
                                      }
                                    }}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-red-400 bg-red-500/10 hover:bg-red-500/25 border border-red-500/20 rounded-xl transition-all text-center"
                                  >
                                    Limpiar Temp
                                  </button>
                                  <button
                                    onClick={() => handleVerifyRemotePassword(dev.id, dev.remote_password)}
                                    className="py-2 px-1 text-[8px] font-black uppercase text-white bg-brand-500 hover:bg-brand-600 rounded-xl transition-all text-center"
                                  >
                                    Control
                                  </button>
                                </div>
                              ) : (
                                <p className="text-[9px] text-slate-500 italic">Desconectado. Visto por última vez: {dev.last_seen ? new Date(dev.last_seen).toLocaleDateString() : 'NUNCA'}</p>
                              )}
                            </div>
                          );
                        });
                      })()}
                    </div>
                  </div>

                </div>
              </div>

            </div>
          </div>
        )}

      </main>

      {showBannerConfigModal && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-6 max-w-lg w-full space-y-6 shadow-2xl animate-in zoom-in-95 text-slate-300">
            <div className="flex justify-between items-center border-b border-white/5 pb-4">
              <div>
                <h3 className="text-lg font-black text-white flex items-center gap-2 font-sans">
                  <AlertCircle className="text-amber-500 animate-pulse" /> Control y Configuración de Cartel ERP
                </h3>
                <p className="text-[11px] text-slate-400 mt-1">Serial Licencia: <span className="font-mono font-bold text-slate-200">{bannerForm.serial}</span></p>
              </div>
              <button onClick={() => setShowBannerConfigModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveBannerConfig} className="space-y-4 text-xs font-sans">
              {/* Suspender Licencia */}
              <div className="flex items-center justify-between bg-slate-800/40 p-4 rounded-xl border border-white/5">
                <div>
                  <label className="text-sm font-bold text-white block">Suspender Licencia de Forma Preventiva</label>
                  <p className="text-[10px] text-slate-400">Si se activa, impedirá el inicio y uso del ERP para todas las terminales.</p>
                </div>
                <input
                  type="checkbox"
                  checked={bannerForm.m_down}
                  onChange={e => setBannerForm({ ...bannerForm, m_down: e.target.checked })}
                  className="w-5 h-5 accent-brand-500 cursor-pointer"
                />
              </div>

              {/* Forzar Vencimiento */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Forzar Vencimiento Manual (Ignorar Fecha de Serial)</label>
                <input
                  type="date"
                  value={bannerForm.m_newdate}
                  onChange={e => setBannerForm({ ...bannerForm, m_newdate: e.target.value })}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs"
                />
                <p className="text-[9px] text-slate-500 mt-1 font-sans">Deje vacío para respetar el vencimiento regular de la licencia.</p>
              </div>

              {/* Tipo de Mensaje */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Tipo de Cartel / Mensaje de Advertencia</label>
                <select
                  value={bannerForm.m_tipmsg}
                  onChange={e => setBannerForm({ ...bannerForm, m_tipmsg: parseInt(e.target.value) || 1 })}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs"
                >
                  {erpTemplates.map(t => (
                    <option key={t.id} value={t.id}>{t.label}</option>
                  ))}
                </select>
              </div>

              {/* Modo de Muestra */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Modo de Muestra en Escritorio FoxPro</label>
                <select
                  value={bannerForm.m_showmode}
                  onChange={e => setBannerForm({ ...bannerForm, m_showmode: e.target.value })}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs font-sans"
                >
                  <option value="01">Mostrar en cada inicio (Recomendado)</option>
                  <option value="02">Mostrar aleatoriamente durante el uso</option>
                  <option value="03">Bloqueo de pantalla inmediato (No permite operar)</option>
                </select>
              </div>

              {/* Mensaje de Cartel */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1.5">Mensaje Particular (Aparecerá en el cartel del usuario)</label>
                <textarea
                  value={bannerForm.m_text}
                  onChange={e => setBannerForm({ ...bannerForm, m_text: e.target.value })}
                  placeholder="Ej. Estimado cliente, detectamos facturas impagas de soporte. Por favor regularice su situación llamando al 0800-APOLLO."
                  rows={3}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-xs resize-none"
                />
              </div>

              {/* Botones de acción */}
              <div className="flex gap-3 pt-2 font-sans">
                <button
                  type="button"
                  onClick={() => setShowBannerConfigModal(false)}
                  className="flex-1 py-2.5 rounded-xl border border-white/10 text-slate-400 hover:text-white transition-all text-xs font-bold"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-500 text-white font-black uppercase tracking-wider transition-all text-xs shadow-md"
                >
                  Aplicar Cambios en MySQL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showLicenseModal && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-white flex items-center gap-2">
                <Sparkles className="text-brand-500" /> Generar Licencia
              </h3>
              <button onClick={() => setShowLicenseModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>
            
            <div className="space-y-4">
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Cliente Asociado</label>
                <select 
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-sm" 
                  value={licClientId}
                  onChange={(e) => setLicClientId(e.target.value)}
                >
                  <option value="">Seleccione un cliente...</option>
                  {clients.map(c => <option key={c.id} value={c.id}>{c.razon_social}</option>)}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Límite de PCs</label>
                  <input 
                    type="number" 
                    min={1}
                    max={1000}
                    className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold" 
                    value={licMaxDevices}
                    onChange={(e) => setLicMaxDevices(parseInt(e.target.value) || 5)}
                    placeholder="Ej. 40"
                  />
                </div>
                
                <div>
                  <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Duración (Días)</label>
                  <input 
                    type="number" 
                    min={1}
                    max={36500}
                    className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3 text-white outline-none focus:border-brand-500 transition-all text-sm" 
                    value={licDurationDays}
                    onChange={(e) => setLicDurationDays(parseInt(e.target.value) || 365)}
                    placeholder="Ej. 365"
                  />
                </div>
              </div>

              <div className="pt-4">
                <button 
                  onClick={() => {
                    if (!licClientId) {
                      alert("Por favor seleccione un cliente.");
                      return;
                    }
                    generateLicense(parseInt(licClientId), licMaxDevices, licDurationDays);
                  }} 
                  className="w-full bg-brand-500 hover:bg-brand-600 active:scale-[0.98] text-white font-black py-4 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Crear Llave de Activación
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {deviceNotesModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-8 max-w-lg w-full space-y-6 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-white flex items-center gap-2">
                <FileText className="text-purple-500 animate-pulse" /> Notas de {deviceNotesModal.name}
              </h3>
              <button onClick={() => setDeviceNotesModal(null)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Guarda recordatorios, claves de Windows, usuarios de red o cualquier anotación importante sobre esta terminal.
              </p>

              <div>
                <textarea
                  rows={10}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-2xl px-4 py-3.5 text-white outline-none focus:border-purple-500 focus:ring-2 focus:ring-purple-500/20 transition-all text-sm font-mono"
                  value={deviceNotesModal.notes}
                  onChange={(e) => setDeviceNotesModal({ ...deviceNotesModal, notes: e.target.value })}
                  placeholder="Escribe aquí las claves de Windows, usuarios de red o notas..."
                />
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  onClick={() => setDeviceNotesModal(null)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleSaveDeviceNotes}
                  className="flex-1 bg-purple-600 hover:bg-purple-700 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-purple-500/20 hover:shadow-purple-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Notas
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {assignModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-indigo-500/30 rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-white flex items-center gap-2">
                <Sparkles className="text-indigo-500 animate-pulse" /> Activar Terminal
              </h3>
              <button onClick={() => setAssignModal(null)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <p className="text-xs text-slate-400">
                Selecciona la empresa o cliente al que deseas asignar la PC <strong className="text-white">{assignModal.device_name}</strong>. El agente Centinela recibirá la licencia asignada automáticamente.
              </p>

              {/* Información de ERP ApolloGesCom detectado */}
              <div className="bg-slate-800/50 border border-white/5 rounded-2xl p-4 space-y-3">
                <span className="text-[10px] font-black text-indigo-400 block tracking-widest uppercase">Detección de Sistema Apollo</span>
                {assignModal.apollo_serials && assignModal.apollo_serials.length > 0 ? (
                  <div className="space-y-2">
                    <p className="text-[11px] text-slate-300">
                      Se detectó el ERP instalado en la terminal con los siguientes números de serie:
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {assignModal.apollo_serials.map((s: string, idx: number) => (
                        <span key={idx} className="bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-mono text-[10px] px-2 py-0.5 rounded-lg">
                          🔑 {s}
                        </span>
                      ))}
                    </div>
                    
                    {assignModal.proposed_client ? (
                      <div className="bg-emerald-500/10 border border-emerald-500/25 rounded-xl p-3 mt-3 space-y-2">
                        <p className="text-[11px] text-emerald-400 font-bold flex items-center gap-1">
                          ✨ Cliente Propuesto Detectado
                        </p>
                        <p className="text-[10px] text-slate-300 leading-relaxed">
                          El prefijo coincide con el cliente <strong>{assignModal.proposed_client.razon_social}</strong> ({assignModal.proposed_client.codigo}).
                        </p>
                        <button
                          type="button"
                          onClick={() => {
                            setAssignClientId(String(assignModal.proposed_client.id));
                            setAssignSearchText(`${assignModal.proposed_client.razon_social} (${assignModal.proposed_client.codigo || ''})`);
                          }}
                          className="w-full bg-emerald-600/95 hover:bg-emerald-500 text-white font-extrabold text-[10px] py-2 rounded-xl transition-all shadow-md shadow-emerald-600/10 active:scale-[0.98]"
                        >
                          Asociar Automáticamente
                        </button>
                      </div>
                    ) : (
                      <p className="text-[10px] text-amber-400 italic mt-1 bg-amber-500/5 border border-amber-500/10 p-2 rounded-lg">
                        ⚠️ Ningún cliente registrado coincide con los primeros 4 dígitos de estos seriales.
                      </p>
                    )}
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic bg-slate-950/20 p-2 rounded-lg border border-white/5">
                    ❌ No se encontró el ERP ApolloGesCom instalado en el registro de esta PC.
                  </p>
                )}
              </div>

              <div className="relative">
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2 font-mono">Empresa / Cliente</label>
                <div className="relative">
                  <input
                    type="text"
                    className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-indigo-500 transition-all text-sm font-bold placeholder:text-slate-500"
                    placeholder="Escribe el nombre o código para filtrar..."
                    value={assignSearchText}
                    onChange={(e) => {
                      setAssignSearchText(e.target.value);
                      setAssignClientId("");
                      setShowAssignDropdown(true);
                    }}
                    onFocus={() => setShowAssignDropdown(true)}
                  />
                  {assignClientId && (
                    <span className="absolute right-3 top-3.5 text-xs text-emerald-400 font-bold flex items-center gap-1 bg-emerald-500/10 px-2.5 py-0.5 rounded-full">
                      ✓ Seleccionado
                    </span>
                  )}
                </div>

                {showAssignDropdown && (
                  <>
                    {/* Backdrop to close the dropdown on click outside */}
                    <div className="fixed inset-0 z-10" onClick={() => setShowAssignDropdown(false)} />
                    
                    <div className="absolute left-0 right-0 mt-1 max-h-60 overflow-y-auto bg-slate-800 border border-white/10 rounded-xl shadow-2xl z-20 scrollbar-thin divide-y divide-white/5 animate-in slide-in-from-top-2 duration-150">
                      {clients
                        .filter(c => {
                          if (!assignSearchText) return true;
                          const term = assignSearchText.toLowerCase();
                          return c.razon_social?.toLowerCase().includes(term) || c.codigo?.toLowerCase().includes(term);
                        })
                        .slice(0, 80)
                        .map(c => (
                          <div
                            key={c.id}
                            className="p-3 text-xs text-slate-300 hover:bg-indigo-600 hover:text-white cursor-pointer transition-all font-semibold flex items-center justify-between"
                            onClick={() => {
                              setAssignClientId(String(c.id));
                              setAssignSearchText(`${c.razon_social} (${c.codigo || ''})`);
                              setShowAssignDropdown(false);
                            }}
                          >
                            <span>{c.razon_social}</span>
                            <span className="text-[10px] bg-white/10 px-2 py-0.5 rounded font-bold">{c.codigo || 'S/C'}</span>
                          </div>
                        ))
                      }
                      {clients.filter(c => {
                        if (!assignSearchText) return true;
                        const term = assignSearchText.toLowerCase();
                        return c.razon_social?.toLowerCase().includes(term) || c.codigo?.toLowerCase().includes(term);
                      }).length === 0 && (
                        <p className="p-4 text-xs text-slate-500 italic text-center">No se encontraron clientes coincidentes.</p>
                      )}
                    </div>
                  </>
                )}
              </div>

              <div className="flex gap-3 pt-4">
                <button
                  onClick={() => setAssignModal(null)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  onClick={handleAssignLicense}
                  disabled={!assignClientId}
                  className="flex-1 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-indigo-500/20 hover:shadow-indigo-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Activar y Vincular
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showProfileModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl animate-in zoom-in-95">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-white flex items-center gap-2">
                <Camera className="text-brand-500 animate-pulse" /> Mi Perfil de Agente
              </h3>
              <button onClick={() => setShowProfileModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveProfile} className="space-y-4">
              {/* Imagen de Perfil y Preview */}
              <div className="flex flex-col items-center gap-3">
                {profileForm.profile_picture ? (
                  <img src={profileForm.profile_picture} alt="Preview" className="w-24 h-24 rounded-full border-4 border-brand-500/50 object-cover shadow-lg" />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg border-4 border-brand-500/30">
                    {(profileForm.full_name || profileForm.nombre || 'AG').substring(0, 2).toUpperCase()}
                  </div>
                )}
                
                <label className="cursor-pointer bg-brand-500/10 hover:bg-brand-500/20 text-brand-500 text-xs font-bold px-4 py-2 rounded-xl border border-brand-500/20 transition-all flex items-center gap-1.5 shadow-sm">
                  <Camera size={14} />
                  Cambiar Foto de Perfil
                  <input type="file" accept="image/*" onChange={(e) => handleProfilePicChange(e, false)} className="hidden" />
                </label>
              </div>

              {/* Nombre de Usuario */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Usuario (Login)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={profileForm.nombre}
                  onChange={(e) => setProfileForm({ ...profileForm, nombre: e.target.value })}
                />
              </div>

              {/* Nombre Completo */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Completo (Mostrar)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={profileForm.full_name}
                  onChange={(e) => setProfileForm({ ...profileForm, full_name: e.target.value })}
                />
              </div>

              {/* Celular */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Celular de Contacto</label>
                <input
                  type="text"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Ej. +543446123456"
                  value={profileForm.celular}
                  onChange={(e) => setProfileForm({ ...profileForm, celular: e.target.value })}
                />
              </div>

              {/* Nueva Contraseña (Opcional) */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nueva Contraseña (Dejar vacío para mantener)</label>
                <input
                  type="password"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Escribe para cambiar..."
                  value={profileForm.password}
                  onChange={(e) => setProfileForm({ ...profileForm, password: e.target.value })}
                />
              </div>

              {/* Botones de Acción */}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowProfileModal(false)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-brand-500 hover:bg-brand-600 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Perfil
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showUserAbmModal && (
        <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/80 backdrop-blur-md p-4 animate-in fade-in">
          <div className="bg-slate-900 border border-brand-500/20 rounded-3xl p-8 max-w-md w-full space-y-6 shadow-2xl animate-in zoom-in-95 max-h-[90vh] overflow-y-auto scrollbar-thin">
            <div className="flex justify-between items-center">
              <h3 className="text-xl font-black text-white flex items-center gap-2">
                <Shield className="text-brand-500 animate-pulse" /> {selectedUserForEdit ? 'Editar Miembro del Plantel' : 'Registrar Nuevo Personal'}
              </h3>
              <button onClick={() => setShowUserAbmModal(false)} className="hover:bg-white/10 p-2 rounded-xl text-slate-400 transition-all">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSaveUserAbm} className="space-y-4">
              {/* Imagen de Perfil y Preview */}
              <div className="flex flex-col items-center gap-3">
                {userAbmForm.profile_picture ? (
                  <img src={userAbmForm.profile_picture} alt="Preview" className="w-24 h-24 rounded-full border-4 border-brand-500/50 object-cover shadow-lg" />
                ) : (
                  <div className="w-24 h-24 rounded-full bg-gradient-to-br from-brand-400 to-orange-500 flex items-center justify-center text-white font-bold text-3xl shadow-lg border-4 border-brand-500/30">
                    {(userAbmForm.full_name || userAbmForm.nombre || 'AG').substring(0, 2).toUpperCase()}
                  </div>
                )}
                
                <label className="cursor-pointer bg-brand-500/10 hover:bg-brand-500/20 text-brand-500 text-xs font-bold px-4 py-2 rounded-xl border border-brand-500/20 transition-all flex items-center gap-1.5 shadow-sm">
                  <Camera size={14} />
                  Subir Foto de Perfil
                  <input type="file" accept="image/*" onChange={(e) => handleProfilePicChange(e, true)} className="hidden" />
                </label>
              </div>

              {/* Nombre de Usuario */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Usuario (Login)</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={userAbmForm.nombre}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, nombre: e.target.value })}
                />
              </div>

              {/* Email */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Email Oficial</label>
                <input
                  type="email" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="ejemplo@masteris.com"
                  value={userAbmForm.email}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, email: e.target.value })}
                />
              </div>

              {/* Nombre Completo */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Nombre Completo</label>
                <input
                  type="text" required
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  value={userAbmForm.full_name}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, full_name: e.target.value })}
                />
              </div>

              {/* Contraseña */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">
                  Contraseña {selectedUserForEdit ? '(Dejar vacío para mantener)' : '(Requerido)'}
                </label>
                <input
                  type="password"
                  required={!selectedUserForEdit}
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder={selectedUserForEdit ? "Sin cambios..." : "Contraseña inicial (ej: user1234)"}
                  value={userAbmForm.password}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, password: e.target.value })}
                />
              </div>

              {/* Rol */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Rol del Sistema</label>
                <select
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold"
                  value={userAbmForm.rol}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, rol: e.target.value })}
                >
                  <option value="soporte">Soporte Técnico (Operador)</option>
                  <option value="desarrollo">Desarrollador</option>
                  <option value="admin">Administrador del Sistema</option>
                </select>
              </div>

              {/* Departamento */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Departamento de la Empresa</label>
                <select
                  className="w-full bg-slate-800 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold"
                  value={userAbmForm.departamento}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, departamento: e.target.value })}
                >
                  <option value="Desarrollo">Desarrollo (Ingeniería)</option>
                  <option value="Atención al Cliente">Atención al Cliente (Soporte)</option>
                  <option value="Caja">Caja</option>
                  <option value="Finanzas">Finanzas</option>
                </select>
              </div>

              {/* Celular */}
              <div>
                <label className="text-xs font-bold text-slate-400 uppercase tracking-widest block mb-2">Celular de Contacto</label>
                <input
                  type="text"
                  className="w-full bg-slate-800/80 border border-white/10 rounded-xl px-4 py-3.5 text-white outline-none focus:border-brand-500 transition-all text-sm font-bold placeholder:text-slate-500"
                  placeholder="Ej. +543446123456"
                  value={userAbmForm.celular}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, celular: e.target.value })}
                />
              </div>

              {/* Estado Activo */}
              <div className="flex items-center gap-3 py-2">
                <input
                  type="checkbox"
                  id="user_abm_activo"
                  className="w-4 h-4 rounded text-brand-500 focus:ring-brand-500 bg-slate-800 border-white/10"
                  checked={userAbmForm.activo}
                  onChange={(e) => setUserAbmForm({ ...userAbmForm, activo: e.target.checked })}
                />
                <label htmlFor="user_abm_activo" className="text-xs font-bold text-slate-300 uppercase tracking-wider cursor-pointer">
                  Usuario Activo (Permitir Ingreso)
                </label>
              </div>

              {/* Botones de Acción */}
              <div className="flex gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowUserAbmModal(false)}
                  className="flex-1 py-3 text-sm font-bold text-slate-400 hover:text-white hover:bg-white/5 rounded-2xl transition-all"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  className="flex-1 bg-brand-500 hover:bg-brand-600 text-white font-extrabold py-3 rounded-2xl shadow-lg shadow-brand-500/20 hover:shadow-brand-500/30 transition-all text-sm uppercase tracking-wider"
                >
                  Guardar Usuario
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal de Extracto General (ERP) con Diseño Ultra-Premium Glass */}
      {showExtractoModal.isOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
          <div className={`relative w-full max-w-4xl rounded-3xl p-6 sm:p-8 flex flex-col max-h-[90vh] shadow-2xl border animate-in zoom-in-95 duration-200 ${darkMode ? 'glass-dark border-white/10 text-white' : 'bg-white border-slate-200 text-slate-800'}`}>
            
            {/* Cabecera */}
            <div className="flex justify-between items-start gap-4 border-b pb-4 dark:border-white/10">
              <div>
                <span className="text-[10px] uppercase font-black tracking-widest text-brand-500 bg-brand-500/10 px-2.5 py-1 rounded-full">
                  Conexión ERP Activa
                </span>
                <h3 className="text-xl sm:text-2xl font-black mt-2 leading-none">
                  Extracto de Cuenta: <span className="text-brand-500">{showExtractoModal.client?.razon_social}</span>
                </h3>
                <p className="text-xs text-slate-400 mt-1 font-medium">
                  Código ERP: <strong className="font-mono text-slate-300">{showExtractoModal.client?.codigo}</strong> | CUIT: <strong className="font-mono text-slate-300">{showExtractoModal.client?.identificador_fiscal || "Sin CUIT"}</strong>
                </p>
              </div>
              <button
                onClick={() => setShowExtractoModal(prev => ({ ...prev, isOpen: false }))}
                className="hover:bg-red-500/10 hover:text-red-500 p-2 rounded-xl transition-all"
              >
                <X size={20} />
              </button>
            </div>

            {/* Filtros de Fecha */}
            <div className="flex flex-col sm:flex-row gap-3 items-end justify-between bg-slate-500/5 border dark:border-white/5 p-4 rounded-2xl mt-4">
              <div className="grid grid-cols-2 gap-3 w-full sm:w-auto">
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Fecha Desde</label>
                  <input
                    type="date"
                    value={showExtractoModal.desde}
                    onChange={(e) => setShowExtractoModal({ ...showExtractoModal, desde: e.target.value })}
                    className={`w-full rounded-xl px-3 py-2 text-xs border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-slate-900 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                  />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1.5">Fecha Hasta</label>
                  <input
                    type="date"
                    value={showExtractoModal.hasta}
                    onChange={(e) => setShowExtractoModal({ ...showExtractoModal, hasta: e.target.value })}
                    className={`w-full rounded-xl px-3 py-2 text-xs border outline-none focus:ring-2 focus:ring-brand-500 ${darkMode ? 'bg-slate-900 border-white/10 text-white' : 'bg-white border-slate-200'}`}
                  />
                </div>
              </div>
              <button
                onClick={() => handleOpenExtracto(showExtractoModal.client, showExtractoModal.desde, showExtractoModal.hasta)}
                disabled={showExtractoModal.loading}
                className="w-full sm:w-auto bg-brand-500 hover:bg-brand-600 text-white text-xs font-bold px-5 py-2.5 rounded-xl transition-all shadow-md"
              >
                {showExtractoModal.loading ? "Consultando..." : "Filtrar Extracto"}
              </button>
            </div>

            {/* Grilla de Resultados */}
            <div className="flex-1 overflow-y-auto mt-4 min-h-[250px] pr-1">
              {showExtractoModal.loading ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <Sparkles className="w-8 h-8 text-indigo-400 animate-spin" />
                  <p className="text-sm text-slate-400 font-bold animate-pulse">Sincronizando con el motor de gestión Harbour...</p>
                </div>
              ) : showExtractoModal.data.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-20 text-slate-400 text-sm font-semibold">
                  <FileText size={32} className="text-slate-500 mb-2" />
                  No se registran comprobantes en el rango de fechas seleccionado.
                </div>
              ) : (
                <div className="border border-white/5 dark:border-white/5 rounded-2xl overflow-hidden">
                  <div className="hidden sm:grid grid-cols-12 gap-3 p-3 text-[10px] font-bold text-slate-400 uppercase tracking-wider bg-slate-500/10 border-b dark:border-white/5">
                    <div className="col-span-2">Fecha</div>
                    <div className="col-span-4">Comprobante / Detalle</div>
                    <div className="col-span-2 text-right">Importe</div>
                    <div className="col-span-2 text-right">Saldo</div>
                    <div className="col-span-2 text-center">Acciones</div>
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-white/5 max-h-[40vh] overflow-y-auto">
                    {showExtractoModal.data.map((row, idx) => {
                      const importe = parseFloat(row.Importe || 0);
                      const saldo = parseFloat(row.Saldo || 0);
                      
                      const fmtImporte = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(importe);
                      const fmtSaldo = new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(saldo);
                      
                      // Formatear fecha
                      let cleanDate = row.Fecha;
                      if (cleanDate && cleanDate.includes('-')) {
                        const parts = cleanDate.split('T')[0].split('-');
                        if (parts.length === 3) {
                          cleanDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
                        }
                      }
                      
                      return (
                        <div key={idx} className={`flex flex-col sm:grid sm:grid-cols-12 gap-2 sm:gap-3 p-3 items-start sm:items-center text-xs font-semibold ${darkMode ? 'hover:bg-white/5' : 'hover:bg-slate-50'} border-b border-slate-100 dark:border-white/5`}>
                          <div className="sm:col-span-2 font-mono text-slate-400 text-[10px] sm:text-xs">{cleanDate}</div>
                          <div className="sm:col-span-4 truncate font-bold leading-tight w-full text-left" title={row.Documento}>
                            {row.Documento}
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-1 sm:mt-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Importe</span>
                            <div className={`sm:col-span-2 text-right font-black font-mono ${importe < 0 ? 'text-rose-500' : 'text-emerald-500'}`}>
                              {fmtImporte}
                            </div>
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-1 sm:mt-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Saldo</span>
                            <div className="sm:col-span-2 text-right font-extrabold font-mono text-slate-300">
                              {fmtSaldo}
                            </div>
                          </div>
                          <div className="flex sm:contents justify-between w-full mt-2 sm:mt-0 items-center border-t border-dashed border-white/5 pt-2 sm:pt-0 sm:border-0">
                            <span className="sm:hidden text-[10px] text-slate-500 uppercase font-bold">Acción</span>
                            <div className="sm:col-span-2 flex justify-center w-auto">
                              {row.CodFac ? (
                                <button
                                  onClick={() => viewVoucherPdf(row.CodFac)}
                                  className="flex items-center gap-1.5 px-3 py-1 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/10 hover:border-rose-500/30 rounded-lg text-[10px] font-black uppercase transition-all shadow-sm"
                                  title="Visualizar Comprobante original del ERP en formato PDF"
                                >
                                  <FileText size={11} />
                                  PDF
                                </button>
                              ) : (
                                <span className="text-[10px] text-slate-500 font-bold font-mono">-</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Totalizadores en el Pie */}
            <div className="flex flex-col sm:flex-row justify-between items-center border-t pt-4 mt-6 dark:border-white/10 gap-3">
              <div className="flex gap-4">
                <div className="text-xs">
                  <span className="text-slate-400">Total Comprobantes:</span> <strong className="text-white">{showExtractoModal.data.length}</strong>
                </div>
                <div className="text-xs">
                  <span className="text-slate-400">Saldo Actual en ERP:</span> <strong className="text-emerald-400 font-mono font-black">{new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS' }).format(showExtractoModal.client?.saldo || 0)}</strong>
                </div>
              </div>
              <button
                onClick={() => setShowExtractoModal(prev => ({ ...prev, isOpen: false }))}
                className="w-full sm:w-auto bg-slate-800 hover:bg-slate-700 text-white text-xs font-bold px-6 py-2.5 rounded-xl transition-all border border-white/10"
              >
                Cerrar Ventana
              </button>
            </div>
            
          </div>
        </div>
      )}
    </div>
  );
}

const NavItem = ({ icon, text, active, badge, onClick }: any) => (
  <button onClick={onClick} className={`w-full flex items-center justify-between px-4 py-3.5 rounded-xl transition-all group ${active ? 'bg-gradient-to-r from-brand-500/20 to-transparent text-brand-500 font-extrabold' : 'text-slate-400 hover:bg-white/5'}`}>
    <div className="flex items-center gap-3 text-sm"><span>{icon}</span>{text}</div>
    {badge && <span className="text-[10px] font-extrabold px-2.5 py-1 rounded-full bg-slate-800 text-slate-400">{badge}</span>}
  </button>
);

const TicketRow = ({ id, client, subject, status, priority, darkMode }: any) => {
  const statusColors: any = { 'nuevo': 'text-blue-500 bg-blue-500/10', 'en_curso': 'text-brand-500 bg-brand-500/10', 'resuelto': 'text-emerald-500 bg-emerald-500/10' };
  return (
    <div className={`grid grid-cols-12 gap-4 p-3.5 rounded-xl items-center cursor-pointer transition-all ${darkMode ? 'hover:bg-white/5' : 'hover:bg-slate-50'}`}>
      <div className="col-span-1 text-xs font-bold text-slate-500">{id}</div>
      <div className="col-span-3 text-sm font-extrabold text-brand-500 truncate">{client}</div>
      <div className="col-span-4 text-sm truncate">{subject}</div>
      <div className="col-span-2"><span className={`px-3 py-1 rounded-full text-[10px] font-bold uppercase ${statusColors[status.toLowerCase()] || 'text-slate-400 bg-slate-400/10'}`}>{status}</span></div>
      <div className="col-span-2 text-xs font-bold capitalize">{priority}</div>
    </div>
  );
};


